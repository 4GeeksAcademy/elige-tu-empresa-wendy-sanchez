"""CSV transformer — converts CSV rows from the legacy analyzer format into Incident model dicts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from incident_model import (
    CLINIC_TO_BRANCH,
    CSV_CATEGORY_TO_MODEL,
    CSV_STATUS_TO_MODEL,
    Incident,
    VALID_BRANCHES,
)
from validations import validate_incident


def parse_date(date_str: str) -> Optional[str]:
    """Parse YYYY-MM-DD date string → ISO 8601 UTC datetime string."""
    if not date_str or not date_str.strip():
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def csv_row_to_incident(row: dict[str, str]) -> tuple[Optional[dict], list[str]]:
    """Transform a CSV row into an Incident dict ready for DB insertion.

    Returns (incident_dict, errors). If errors is non-empty, the record is invalid.
    The incident_dict is None when errors prevent full transformation.
    """
    errors: list[str] = []

    # ── Title: first 120 chars of description, trimmed ──
    description_raw = (row.get("description") or "").strip()
    title = description_raw[:120].strip()
    if not title:
        errors.append("title_empty_from_description")

    # ── Description: copy literally ──
    description = description_raw

    # ── Category mapping ──
    csv_category = (row.get("category") or "").strip()
    category = CSV_CATEGORY_TO_MODEL.get(csv_category, "")
    if not category:
        errors.append(f"unmappable_category:{csv_category}")

    # ── Status mapping ──
    csv_status = (row.get("status") or "").strip()
    status = CSV_STATUS_TO_MODEL.get(csv_status, "")
    if not status:
        errors.append(f"unmappable_status:{csv_status}")

    # ── Origin: always "customer" for seed ──
    origin = "customer"

    # ── Branch mapping ──
    clinic_id = (row.get("clinic_id") or "").strip()
    branch = CLINIC_TO_BRANCH.get(clinic_id, "central")

    # ── Date ──
    date_str = (row.get("date") or "").strip()
    created_at = parse_date(date_str)
    if created_at is None:
        errors.append("invalid_date")

    # ── Build incident dict ──
    incident_dict = {
        "title": title,
        "description": description,
        "category": category,
        "status": status,
        "origin": origin,
        "branch": branch,
        "created_at": created_at,
        "updated_at": created_at,  # same as created_at on insert
    }

    # ── Run shared validation ──
    validation_errors = validate_incident(incident_dict)
    errors.extend(validation_errors)

    if errors:
        return None, errors

    return incident_dict, []


def get_csv_incident_id(row: dict[str, str]) -> str:
    """Return the unique identifier from the CSV row for idempotency checks."""
    return (row.get("incident_id") or "").strip()