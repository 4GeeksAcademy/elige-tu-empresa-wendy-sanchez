"""CSV-level validation — reusable from the original incidents-file-analyzer."""

from __future__ import annotations

import re

# ── CSV-level constants (from incidents_analysis.py) ────────────────────

VALID_CLINICS: dict[str, str] = {
    "US-TX-01": "US",
    "US-TX-02": "US",
    "US-TX-03": "US",
    "US-FL-01": "US",
    "US-FL-02": "US",
    "US-FL-03": "US",
    "US-GA-01": "US",
    "US-GA-02": "US",
    "US-GA-03": "US",
    "UK-LON-01": "UK",
    "UK-LON-02": "UK",
    "UK-MAN-01": "UK",
}

VALID_CSV_CATEGORIES = {
    "APPOINTMENT",
    "BILLING",
    "CLINICAL_CARE",
    "ACCESSIBILITY",
    "ADMINISTRATIVE",
}

VALID_CSV_STATUSES = {"OPEN", "CLOSED", "DISCARDED"}

PATIENT_ID_RE = re.compile(r"^PAT-[A-Za-z0-9]{6}$")


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def validate_csv_record(row: dict[str, str]) -> list[str]:
    """Validate a raw CSV row against the legacy analyzer rules.

    Returns a list of error codes (empty = valid).
    """
    reasons: list[str] = []

    clinic_id = (row.get("clinic_id") or "").strip()
    country = (row.get("country") or "").strip()
    category = (row.get("category") or "").strip()
    description = (row.get("description") or "").strip()
    status = (row.get("status") or "").strip()
    patient_id = (row.get("patient_id") or "").strip()
    score = _to_int(row.get("satisfaction_score"))

    if clinic_id not in VALID_CLINICS:
        reasons.append("invalid_clinic")
    elif country != VALID_CLINICS[clinic_id]:
        reasons.append("country_clinic_mismatch")

    if category not in VALID_CSV_CATEGORIES:
        reasons.append("invalid_category")

    if len(description) < 5:
        reasons.append("empty_description")

    if not PATIENT_ID_RE.match(patient_id):
        reasons.append("missing_patient_id")

    if status == "CLOSED" and score is None:
        reasons.append("closed_no_score")

    if score is not None and (score < 1 or score > 5):
        reasons.append("score_out_of_range")

    if status not in VALID_CSV_STATUSES:
        reasons.append("invalid_status")

    return reasons