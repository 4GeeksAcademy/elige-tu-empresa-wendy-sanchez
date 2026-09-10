"""Incident model — Pydantic models for API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"


class IncidentOrigin(str, Enum):
    CUSTOMER = "customer"
    BRANCH = "branch"
    INTERNAL = "internal"


class IncidentCategory(str, Enum):
    CLINICAL_EQUIPMENT = "clinical_equipment"
    IT_SYSTEM = "it_system"
    BILLING_ERROR = "billing_error"
    COMPLIANCE_BREACH = "compliance_breach"
    PATIENT_EXPERIENCE = "patient_experience"
    STAFF_ISSUE = "staff_issue"
    FACILITY_ISSUE = "facility_issue"
    REFERRAL_ISSUE = "referral_issue"
    OTHER = "other"


VALID_BRANCHES = {
    "central", "austin_north", "dallas_uptown", "houston_med_center",
    "san_antonio_west", "miami_brickell", "miami_doral", "orlando_east",
    "tampa_bay", "atlanta_midtown", "savannah", "london_city",
    "london_west", "manchester_central",
}

BRANCH_LABELS: dict[str, str] = {
    "central": "Central — Austin Main Clinic",
    "austin_north": "Austin — North",
    "dallas_uptown": "Dallas Uptown",
    "houston_med_center": "Houston Medical Center",
    "san_antonio_west": "San Antonio West",
    "miami_brickell": "Miami Brickell",
    "miami_doral": "Miami Doral",
    "orlando_east": "Orlando East",
    "tampa_bay": "Tampa Bay",
    "atlanta_midtown": "Atlanta Midtown",
    "savannah": "Savannah",
    "london_city": "London City",
    "london_west": "London West End",
    "manchester_central": "Manchester Central",
}


class IncidentBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=10, max_length=2000)
    category: IncidentCategory
    status: IncidentStatus = IncidentStatus.OPEN
    origin: IncidentOrigin
    branch: str = Field(min_length=1)

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: str) -> str:
        if value not in VALID_BRANCHES:
            raise ValueError(
                f"Invalid branch '{value}'. Allowed: {', '.join(sorted(VALID_BRANCHES))}"
            )
        return value


class IncidentCreate(IncidentBase):
    """Payload for creating an incident. System sets created_at/updated_at."""


class IncidentUpdate(BaseModel):
    """Partial update payload — all fields optional."""
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, min_length=10, max_length=2000)
    category: Optional[IncidentCategory] = None
    status: Optional[IncidentStatus] = None
    branch: Optional[str] = Field(default=None, min_length=1)

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in VALID_BRANCHES:
            raise ValueError(
                f"Invalid branch '{value}'. Allowed: {', '.join(sorted(VALID_BRANCHES))}"
            )
        return value


class IncidentResponse(IncidentBase):
    id: int
    created_at: str
    updated_at: str
    branch_label: str = ""

    @model_validator(mode="after")
    def set_branch_label(self) -> "IncidentResponse":
        self.branch_label = BRANCH_LABELS.get(self.branch, self.branch)
        return self


class IncidentSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_branch: dict[str, int]
    by_origin: dict[str, int]