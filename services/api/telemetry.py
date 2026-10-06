from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StrictStr, field_validator, model_validator

TELEMETRY_ENDPOINT = os.getenv("TELEMETRY_ENDPOINT", "http://localhost:8000/telemetry/events")
REGISTRY = json.loads(
    (Path(__file__).resolve().parents[2] / "docs/telemetry/event-schemas.json").read_text()
)
CONTRACTS = {event["event_type"]: event for event in REGISTRY["events"]}
ISO_TIMESTAMP = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?(?:Z|[+-][0-9]{2}:[0-9]{2})"
OpaqueId = Annotated[StrictStr, Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


def validate_property_privacy(name: str, value: JsonValue) -> None:
    rules = REGISTRY["privacyValidation"]
    if name in rules["registeredEventProperties"] and value not in CONTRACTS:
        raise ValueError("Unapproved telemetry event reference")
    if name in rules["routeProperties"] and value not in rules["routes"]:
        raise ValueError("Unapproved telemetry route")
    pattern = rules["propertyPatterns"].get(name)
    if pattern and (not isinstance(value, str) or re.fullmatch(pattern, value) is None):
        raise ValueError("Unapproved telemetry property value")
    allowed = rules["propertyEnums"].get(name)
    if allowed and value not in allowed:
        raise ValueError("Unapproved telemetry dimension")


def validate_property(value: JsonValue, rule: dict) -> None:
    expected = rule["type"]
    valid = {
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": type(value) in (int, float),
        "boolean": type(value) is bool,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
    }.get(expected, False)
    if not valid:
        raise ValueError("Invalid property type")
    if "enum" in rule and value not in rule["enum"]:
        raise ValueError("Invalid property enum")
    for bound, comparison in (("minimum", lambda actual, limit: actual < limit), ("maximum", lambda actual, limit: actual > limit)):
        if bound in rule and comparison(value, rule[bound]):
            raise ValueError("Property outside allowed range")
    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0) or len(value) > rule.get("maxLength", 8192):
            raise ValueError("Invalid property length")
        if "pattern" in rule and re.search(rule["pattern"], value) is None:
            raise ValueError("Invalid property pattern")
        if rule.get("format") == "date":
            date.fromisoformat(value)
        if rule.get("format") == "date-time":
            if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
                raise ValueError("Timezone required")


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    eventId: StrictStr
    timestamp: AwareDatetime
    sessionId: OpaqueId
    userId: OpaqueId
    event_type: StrictStr
    schemaVersion: StrictStr
    requestId: OpaqueId
    properties: dict[str, JsonValue]

    @field_validator("eventId")
    @classmethod
    def valid_event_id(cls, value: str) -> str:
        UUID(value)
        return value

    @field_validator("timestamp", mode="before")
    @classmethod
    def iso_timestamp(cls, value: object) -> object:
        if not isinstance(value, datetime) and (not isinstance(value, str) or re.fullmatch(ISO_TIMESTAMP, value) is None):
            raise ValueError("ISO timestamp required")
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> TelemetryEvent:
        contract = CONTRACTS.get(self.event_type)
        if contract is None or self.schemaVersion != contract["schemaVersion"]:
            raise ValueError("Unknown event contract")
        if set(self.properties) - set(contract["propertiesAllowlist"]):
            raise ValueError("Unknown event properties")
        if set(contract["requiredProperties"]) - set(self.properties):
            raise ValueError("Missing event properties")
        for name, value in self.properties.items():
            validate_property(value, contract["properties"][name])
            validate_property_privacy(name, value)
        if len(self.model_dump_json().encode()) > REGISTRY["validationRules"]["maxEventBytes"]:
            raise ValueError("Event too large")
        return self


class TelemetryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[TelemetryEvent] = Field(min_length=1, max_length=100)


class TelemetryReceipt(BaseModel):
    received: int