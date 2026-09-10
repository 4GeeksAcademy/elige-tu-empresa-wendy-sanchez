"""Incidents CRUD + summary API routes."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Query, status
from tinydb import Query as TinyQuery

from database import get_incidents_table
from models import (
    IncidentCategory,
    IncidentCreate,
    IncidentOrigin,
    IncidentResponse,
    IncidentStatus,
    IncidentSummary,
    IncidentUpdate,
    utc_now,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
IncidentQuery = TinyQuery()


def _to_response(doc_id: int, record: dict) -> IncidentResponse:
    return IncidentResponse(id=doc_id, **record)


def _read_all() -> list[IncidentResponse]:
    return [
        _to_response(doc.doc_id, dict(doc))
        for doc in get_incidents_table().all()
    ]


def _read_one(incident_id: int) -> IncidentResponse:
    doc = get_incidents_table().get(doc_id=incident_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found",
        )
    return _to_response(doc.doc_id, dict(doc))


# ── List with optional filters ──────────────────────────────────────────


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    status: IncidentStatus | None = Query(default=None),
    category: IncidentCategory | None = Query(default=None),
    origin: IncidentOrigin | None = Query(default=None),
    branch: str | None = Query(default=None),
) -> list[IncidentResponse]:
    incidents = _read_all()
    if status is not None:
        incidents = [i for i in incidents if i.status == status.value]
    if category is not None:
        incidents = [i for i in incidents if i.category == category.value]
    if origin is not None:
        incidents = [i for i in incidents if i.origin == origin.value]
    if branch is not None:
        incidents = [i for i in incidents if i.branch == branch]
    return incidents


# ── Summary (MUST come before /{incident_id} to avoid route conflict) ──


@router.get("/summary", response_model=IncidentSummary)
def get_summary() -> IncidentSummary:
    incidents = get_incidents_table().all()

    total = len(incidents)
    status_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    branch_counter: Counter[str] = Counter()
    origin_counter: Counter[str] = Counter()

    for doc in incidents:
        status_counter[doc.get("status", "unknown")] += 1
        category_counter[doc.get("category", "unknown")] += 1
        branch_counter[doc.get("branch", "unknown")] += 1
        origin_counter[doc.get("origin", "unknown")] += 1

    return IncidentSummary(
        total=total,
        by_status=dict(status_counter),
        by_category=dict(category_counter),
        by_branch=dict(branch_counter),
        by_origin=dict(origin_counter),
    )


# ── Get single incident ─────────────────────────────────────────────────


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int) -> IncidentResponse:
    return _read_one(incident_id)


# ── Create incident ─────────────────────────────────────────────────────


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate) -> IncidentResponse:
    table = get_incidents_table()
    now = utc_now().isoformat()
    record = payload.model_dump(mode="json")
    record["created_at"] = now
    record["updated_at"] = now
    doc_id = table.insert(record)
    return _to_response(doc_id, record)


# ── Update incident ─────────────────────────────────────────────────────


@router.patch("/{incident_id}", response_model=IncidentResponse)
def update_incident(incident_id: int, payload: IncidentUpdate) -> IncidentResponse:
    current = _read_one(incident_id)

    # Map the current object to a dict for update
    changes: dict = {}
    update_data = payload.model_dump(exclude_none=True, mode="json")
    for key in ("title", "description", "category", "status", "branch"):
        if key in update_data:
            changes[key] = update_data[key]

    if changes:
        changes["updated_at"] = utc_now().isoformat()
        get_incidents_table().update(changes, doc_ids=[incident_id])

    return _read_one(incident_id)


# ── Delete incident ─────────────────────────────────────────────────────


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_incident(incident_id: int) -> None:
    _read_one(incident_id)  # ensure exists
    get_incidents_table().remove(doc_ids=[incident_id])


@router.get("/summary", response_model=IncidentSummary)
def get_summary() -> IncidentSummary:
    incidents = get_incidents_table().all()

    total = len(incidents)
    status_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    branch_counter: Counter[str] = Counter()
    origin_counter: Counter[str] = Counter()

    for doc in incidents:
        status_counter[doc.get("status", "unknown")] += 1
        category_counter[doc.get("category", "unknown")] += 1
        branch_counter[doc.get("branch", "unknown")] += 1
        origin_counter[doc.get("origin", "unknown")] += 1

    return IncidentSummary(
        total=total,
        by_status=dict(status_counter),
        by_category=dict(category_counter),
        by_branch=dict(branch_counter),
        by_origin=dict(origin_counter),
    )