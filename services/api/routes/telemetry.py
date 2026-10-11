from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from telemetry import TelemetryEvent, TelemetryReceipt

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger("api.telemetry")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _insert_events(db, rows: list[dict]) -> None:
    """Bulk-insert telemetry events via raw SQL.

    Uses a single executemany statement for performance.  This avoids
    SQLModel ORM overhead and sidesteps a Python 3.14 / SQLModel compat
    issue triggered when loading model classes with Enum fields.
    SQLite (tests) and PostgreSQL (production) both support named binds.
    """
    from sqlalchemy import text as sa_text

    stmt = sa_text(
        """INSERT INTO telemetry_events
        (event_id, timestamp, session_id, user_id, event_type,
         schema_version, request_id, tags, created_at)
        VALUES (:event_id, :timestamp, :session_id, :user_id, :event_type,
                :schema_version, :request_id, :tags, :created_at)
        ON CONFLICT (event_id) DO NOTHING"""
    )
    now = datetime.now(timezone.utc)
    params = [
        {
            "event_id": r["event_id"],
            "timestamp": r["timestamp"],
            "session_id": r["session_id"],
            "user_id": r["user_id"],
            "event_type": r["event_type"],
            "schema_version": r["schema_version"],
            "request_id": r["request_id"],
            # Serialize to JSON string so it works with both SQLite and
            # PostgreSQL (where it will be cast to JSONB via column type).
            "tags": json.dumps(r["tags"]) if r.get("tags") else None,
            "created_at": now,
        }
        for r in rows
    ]
    if params:
        db.execute(stmt, params)
        db.commit()


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/events", response_model=TelemetryReceipt)
@router.post("/control", response_model=TelemetryReceipt)
def receive_events(body: dict, db=Depends(get_db)) -> TelemetryReceipt:
    """Receive a telemetry batch with per-event validation.

    Accepts the envelope loosely: { "events": [...] } where each element
    is a raw dict.  Each event is validated individually against the
    TelemetryEvent Pydantic contract.  Valid events are bulk-inserted;
    invalid events are counted and rejected without affecting the rest
    of the batch.
    """
    raw_events = body.get("events", [])
    if not isinstance(raw_events, list):
        raise HTTPException(status_code=422, detail="'events' must be an array")
    if len(raw_events) > 100:
        raise HTTPException(status_code=422, detail="Batch exceeds maximum of 100 events")

    received = len(raw_events)
    validated: list[TelemetryEvent] = []
    rejected = 0

    for raw in raw_events:
        if not isinstance(raw, dict):
            rejected += 1
            continue
        try:
            event = TelemetryEvent.model_validate(raw)
            validated.append(event)
        except (ValueError, TypeError, Exception):
            rejected += 1
            continue

    if validated:
        rows = [
            {
                "event_id": event.eventId,
                "timestamp": event.timestamp,
                "session_id": event.sessionId,
                "user_id": event.userId,
                "event_type": event.event_type,
                "schema_version": event.schemaVersion,
                "request_id": event.requestId,
                "tags": event.properties,
            }
            for event in validated
        ]
        _insert_events(db, rows)
        stored = len(rows)
        logger.info(
            "Telemetry received=%d stored=%d rejected=%d event_types=%s",
            received, stored, rejected,
            [e.event_type for e in validated],
        )
    else:
        stored = 0
        logger.info("Telemetry received=%d stored=0 rejected=%d", received, rejected)

    return TelemetryReceipt(received=received, stored=stored, rejected=rejected)