"""Shared validation logic for Incident model — reusable between seed script and API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from incident_model import (
    VALID_INCIDENT_CATEGORIES,
    VALID_INCIDENT_ORIGINS,
    VALID_INCIDENT_STATUSES,
    VALID_BRANCHES,
)


def validate_incident(incident: dict) -> list[str]:
    """Validate an incident dict against business rules.

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    title = (incident.get("title") or "").strip()
    if not title:
        errors.append("title_required")
    elif len(title) < 2:
        errors.append("title_too_short")

    description = (incident.get("description") or "").strip()
    if not description:
        errors.append("description_required")

    category = (incident.get("category") or "").strip()
    if category not in VALID_INCIDENT_CATEGORIES:
        errors.append("invalid_category")

    status = (incident.get("status") or "").strip()
    if status not in VALID_INCIDENT_STATUSES:
        errors.append("invalid_status")

    origin = (incident.get("origin") or "").strip()
    if origin not in VALID_INCIDENT_ORIGINS:
        errors.append("invalid_origin")

    branch = (incident.get("branch") or "").strip()
    if not branch:
        errors.append("branch_required")
    elif branch not in VALID_BRANCHES:
        errors.append("invalid_branch")

    return errors


def validate_incident_create(payload: dict) -> list[str]:
    """Validate an incident creation payload (from form/API)."""
    errors: list[str] = []

    title = (payload.get("title") or "").strip()
    if not title:
        errors.append("title_required")
    elif len(title) > 200:
        errors.append("title_too_long")

    description = (payload.get("description") or "").strip()
    if not description:
        errors.append("description_required")
    elif len(description) < 10:
        errors.append("description_too_short")
    elif len(description) > 2000:
        errors.append("description_too_long")

    category = (payload.get("category") or "").strip()
    if category not in VALID_INCIDENT_CATEGORIES:
        errors.append("invalid_category")

    status = (payload.get("status") or "").strip()
    if status and status not in VALID_INCIDENT_STATUSES:
        errors.append("invalid_status")

    origin = (payload.get("origin") or "").strip()
    if origin not in VALID_INCIDENT_ORIGINS:
        errors.append("invalid_origin")

    branch = (payload.get("branch") or "").strip()
    if not branch:
        errors.append("branch_required")
    elif branch not in VALID_BRANCHES:
        errors.append("invalid_branch")

    return errors


def format_validation_errors(errors: list[str]) -> list[str]:
    """Convert validation error codes to human-readable messages."""
    messages = {
        "title_required": "Title is required",
        "title_too_short": "Title must be at least 2 characters",
        "title_too_long": "Title must not exceed 200 characters",
        "description_required": "Description is required",
        "description_too_short": "Description must be at least 10 characters",
        "description_too_long": "Description must not exceed 2000 characters",
        "invalid_category": "Invalid category",
        "invalid_status": "Invalid status",
        "invalid_origin": "Invalid origin",
        "branch_required": "Branch is required",
        "invalid_branch": "Invalid branch",
    }
    return [messages.get(e, e) for e in errors]