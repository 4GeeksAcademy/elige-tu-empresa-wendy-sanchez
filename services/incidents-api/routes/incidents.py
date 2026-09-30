"""Incidents CRUD + summary API routes."""

from __future__ import annotations

import logging
from collections import Counter
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from tinydb import Query as TinyQuery

from cache import cache
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
IncidentQuery = TinyQuery()

# ── Constantes de caché ──────────────────────────────────────────────
# GET /api/incidents/summary: TTL 60s. El resumen agrega todos los incidentes
# en contadores. Los datos cambian con cada operación de escritura (crear,
# actualizar, eliminar), pero la mayoría de las lecturas son de consulta.
# 60s es un intercambio aceptable: en el peor caso un incidente nuevo tarda
# hasta 60s en reflejarse en el summary. Para tableros de monitoreo esto es
# perfectamente razonable.
_SUMMARY_CACHE_TTL = 60
_SUMMARY_CACHE_KEY = "incidents:summary"

# ── Allowed status transitions ────────────────────────────────────────────
# open        → in_progress, discarded
# in_progress → resolved, discarded
# resolved    → (final)
# discarded   → (final)

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    IncidentStatus.OPEN.value: {
        IncidentStatus.IN_PROGRESS.value,
        IncidentStatus.DISCARDED.value,
    },
    IncidentStatus.IN_PROGRESS.value: {
        IncidentStatus.RESOLVED.value,
        IncidentStatus.DISCARDED.value,
    },
    IncidentStatus.RESOLVED.value: set(),
    IncidentStatus.DISCARDED.value: set(),
}

# ── Status update payload ─────────────────────────────────────────────────


class StatusUpdatePayload(BaseModel):
    status: IncidentStatus = Field(..., description="New status value")


# ── Helpers ───────────────────────────────────────────────────────────────


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


def _invalidate_summary_cache() -> None:
    """Invalida el summary y las listas cacheadas tras cualquier escritura.

    Cualquier cambio (crear, actualizar, eliminar) afecta tanto al resumen
    agregado como a todas las combinaciones de filtros de la lista.

    Prefijos invalidados:
      - "incidents:summary" → el resumen agregado
      - "incidents:list"    → todas las variantes filtradas
    """
    count = 0
    count += cache.invalidate("incidents:summary")
    count += cache.invalidate("incidents:list")
    if count:
        logger.info("Incidents cache invalidated (%d entries)", count)


# ── List with optional filters ──────────────────────────────────────────


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    status: IncidentStatus | None = Query(default=None),
    category: IncidentCategory | None = Query(default=None),
    origin: IncidentOrigin | None = Query(default=None),
    branch: str | None = Query(default=None),
) -> list[IncidentResponse]:
    # Construir clave de caché específica para los filtros
    filters = f"s:{status}|c:{category}|o:{origin}|b:{branch}"
    cache_key = f"incidents:list:{filters}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    incidents = _read_all()
    if status is not None:
        incidents = [i for i in incidents if i.status == status.value]
    if category is not None:
        incidents = [i for i in incidents if i.category == category.value]
    if origin is not None:
        incidents = [i for i in incidents if i.origin == origin.value]
    if branch is not None:
        incidents = [i for i in incidents if i.branch == branch]

    cache.set(cache_key, incidents, ttl_seconds=30)
    return incidents


# ── Summary (MUST come before /{incident_id} to avoid route conflict) ──


@router.get("/summary", response_model=IncidentSummary)
def get_summary() -> IncidentSummary:
    cached = cache.get(_SUMMARY_CACHE_KEY)
    if cached is not None:
        return cached

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

    result = IncidentSummary(
        total=total,
        by_status=dict(status_counter),
        by_category=dict(category_counter),
        by_branch=dict(branch_counter),
        by_origin=dict(origin_counter),
    )

    cache.set(_SUMMARY_CACHE_KEY, result, _SUMMARY_CACHE_TTL)
    return result


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

    _invalidate_summary_cache()

    return _to_response(doc_id, record)


# ── Update incident (full edit) ─────────────────────────────────────────


@router.patch("/{incident_id}", response_model=IncidentResponse)
def update_incident(incident_id: int, payload: IncidentUpdate) -> IncidentResponse:
    current = _read_one(incident_id)

    changes: dict = {}
    update_data = payload.model_dump(exclude_none=True, mode="json")
    for key in ("title", "description", "category", "status", "branch"):
        if key in update_data:
            changes[key] = update_data[key]

    if changes:
        changes["updated_at"] = utc_now().isoformat()
        get_incidents_table().update(changes, doc_ids=[incident_id])

    _invalidate_summary_cache()

    return _read_one(incident_id)


# ── Status transition (PATCH /{id}/status) ──────────────────────────────


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(
    incident_id: int, payload: StatusUpdatePayload
) -> IncidentResponse:
    current = _read_one(incident_id)
    current_status = current.status.value  # enum → str
    new_status = payload.status.value

    allowed = _ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition: from '{current_status}' "
                f"to '{new_status}'. "
                f"Allowed transitions from '{current_status}': "
                f"{', '.join(sorted(allowed)) if allowed else 'none (final state)'}."
            ),
        )

    get_incidents_table().update(
        {"status": new_status, "updated_at": utc_now().isoformat()},
        doc_ids=[incident_id],
    )

    _invalidate_summary_cache()

    return _read_one(incident_id)


# ── Delete incident ─────────────────────────────────────────────────────


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_incident(incident_id: int) -> None:
    _read_one(incident_id)  # ensure exists
    get_incidents_table().remove(doc_ids=[incident_id])
    _invalidate_summary_cache()