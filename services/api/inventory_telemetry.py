import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Response
from sqlmodel import Session

from models import InventoryAlertState, MedicalSupply
from telemetry import CONTRACTS, validate_property, validate_property_privacy
from telemetry_delivery import enqueue_signal

CATEGORIES = {"ppe": "ppe", "medications": "medication", "consumables": "consumable", "wound_care": "consumable", "diagnostics": "consumable"}
logger = logging.getLogger("api.telemetry")


def dimensions(supply: MedicalSupply, clinic_id: int, quantity: int) -> dict:
    return {"clinic_id": clinic_id, "country": "US" if clinic_id <= 9 else "UK",
            "product_id": supply.id, "product_category": CATEGORIES.get(supply.category, ""), "quantity": quantity}


def signal(event_type: str, properties: dict, dedup_key: str | None = None) -> dict | None:
    contract = CONTRACTS[event_type]
    if set(properties) - set(contract["propertiesAllowlist"]) or set(contract["requiredProperties"]) - set(properties):
        logger.warning("Telemetry signal dropped: contract")
        return None
    try:
        for name, value in properties.items():
            validate_property(value, contract["properties"][name])
            validate_property_privacy(name, value)
    except (ValueError, TypeError):
        logger.warning("Telemetry signal dropped: properties")
        return None
    event = {"event_type": event_type, "properties": properties, "eventId": str(uuid4()),
             "timestamp": datetime.now(timezone.utc).isoformat()}
    if dedup_key:
        event["_dedup_key"] = dedup_key
    try:
        if enqueue_signal(event):
            event["_server_owned"] = True
    except Exception:
        logger.warning("Telemetry signal discarded: enqueue")
    return event


def attach_signals(response: Response, signals: list[dict]) -> None:
    valid = [event for event in signals if event]
    if valid:
        response.headers["X-Telemetry-Events"] = json.dumps(valid, separators=(",", ":"))


def capture_expiry(supply: MedicalSupply, session: Session, stock_for_clinic) -> list[dict]:
    try:
        events = expiry_signals(supply, session, stock_for_clinic)
        session.commit()
        return events
    except Exception:
        session.rollback()
        logger.warning("Telemetry signal dropped: expiry_detection")
        return []


def expiry_signals(supply: MedicalSupply, session: Session, stock_for_clinic) -> list[dict]:
    if supply.expiry_date is None:
        return []
    days = (supply.expiry_date - datetime.now(timezone.utc).date()).days
    if not 0 <= days <= 30:
        return []
    events = []
    for clinic_id in range(1, 13):
        quantity = stock_for_clinic(supply.id, session, clinic_id)
        key = f"expiry:{supply.id}:{clinic_id}:{supply.expiry_date.isoformat()}"
        if quantity > 0 and session.get(InventoryAlertState, key) is None:
            event = signal("supply_expiry_flagged", {
                **dimensions(supply, clinic_id, quantity), "days_to_expiry": days, "expiry_window_days": 30,
            }, dedup_key=key)
            if event:
                events.append(event)
    return events