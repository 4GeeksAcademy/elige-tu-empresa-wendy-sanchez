"""Incident model definition shared between seed script and API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


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


VALID_INCIDENT_STATUSES = {s.value for s in IncidentStatus}
VALID_INCIDENT_ORIGINS = {o.value for o in IncidentOrigin}
VALID_INCIDENT_CATEGORIES = {c.value for c in IncidentCategory}

# Branch values (database values)
VALID_BRANCHES = {
    "central",
    "austin_north",
    "dallas_uptown",
    "houston_med_center",
    "san_antonio_west",
    "miami_brickell",
    "miami_doral",
    "orlando_east",
    "tampa_bay",
    "atlanta_midtown",
    "savannah",
    "london_city",
    "london_west",
    "manchester_central",
}

# CSV clinic_id → branch mapping
CLINIC_TO_BRANCH: dict[str, str] = {
    "US-TX-01": "central",
    "US-TX-02": "austin_north",
    "US-TX-03": "houston_med_center",
    "US-FL-01": "miami_brickell",
    "US-FL-02": "orlando_east",
    "US-FL-03": "tampa_bay",
    "US-GA-01": "atlanta_midtown",
    "US-GA-02": "atlanta_midtown",
    "US-GA-03": "savannah",
    "UK-LON-01": "london_city",
    "UK-LON-02": "london_west",
    "UK-MAN-01": "manchester_central",
}

# CSV status → model status mapping
CSV_STATUS_TO_MODEL: dict[str, str] = {
    "OPEN": "open",
    "CLOSED": "resolved",
    "DISCARDED": "discarded",
}

# CSV category → model category mapping
CSV_CATEGORY_TO_MODEL: dict[str, str] = {
    "APPOINTMENT": "patient_experience",
    "BILLING": "billing_error",
    "CLINICAL_CARE": "patient_experience",
    "ACCESSIBILITY": "patient_experience",
    "ADMINISTRATIVE": "other",
}


@dataclass
class Incident:
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    category: str = ""
    status: str = "open"
    origin: str = "customer"
    branch: str = "central"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "origin": self.origin,
            "branch": self.branch,
        }
        if self.created_at is not None:
            d["created_at"] = self.created_at
        if self.updated_at is not None:
            d["updated_at"] = self.updated_at
        return d