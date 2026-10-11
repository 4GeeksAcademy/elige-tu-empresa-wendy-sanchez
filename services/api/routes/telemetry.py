from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database import get_db, get_sql_engine
from telemetry import TelemetryEvent, TelemetryReceipt

# Importar el pipeline de análisis (desde services/telemetry)
import sys
from pathlib import Path

_TELEMETRY_DIR = Path(__file__).resolve().parents[2] / "telemetry"
if str(_TELEMETRY_DIR) not in sys.path:
    sys.path.insert(0, str(_TELEMETRY_DIR))

from analysis import run_all  # type: ignore[import-untyped]

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger("api.telemetry")

# ── Caché en memoria para el reporte ─────────────────────────────────────
_report_cache: dict[str, tuple[float, dict]] = {}
_REPORT_CACHE_TTL = 60  # segundos


def _cache_key(start: datetime, end: datetime) -> str:
    return f"report:{start.isoformat()}:{end.isoformat()}"


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


# ── Reporte de telemetría ────────────────────────────────────────────────────


@router.get("/report")
def telemetry_report(
    start_date: Optional[str] = Query(None, description="Inicio ISO 8601 (UTC). Por defecto: now - 7d."),
    end_date: Optional[str] = Query(None, description="Fin ISO 8601 (UTC). Por defecto: now."),
) -> JSONResponse:
    """Reporte de métricas operacionales para la ventana especificada.

    El pipeline de análisis se ejecuta en una función separada (run_all),
    nunca dentro del endpoint. El resultado se cachea 60 segundos.
    Si se solicita la misma combinación start_date/end_date dentro del TTL,
    se devuelve el valor cacheado sin recalcular.
    """
    # 1. Resolver ventana de fechas
    now = datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat(start_date) if start_date else (now - timedelta(days=7))
        end = datetime.fromisoformat(end_date) if end_date else now
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Formato de fecha inválido: {exc}")

    # Asegurar timezone-aware (asumir UTC si no tiene zona)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    # 2. Comprobar caché
    cache_key = _cache_key(start, end)
    now_ts = time.monotonic()
    cached = _report_cache.get(cache_key)
    if cached is not None:
        expires_at, value = cached
        if now_ts < expires_at:
            logger.debug("Report cache HIT: %s", cache_key)
            return JSONResponse(content=value)

    # 3. Ejecutar pipeline (solo si no hay caché válida)
    logger.debug("Report cache MISS: %s", cache_key)
    engine = get_sql_engine()
    try:
        metrics = run_all(engine, start, end)
    except Exception as exc:
        logger.exception("Error ejecutando el pipeline de análisis")
        raise HTTPException(status_code=500, detail=f"Error en el pipeline de análisis: {exc}")

    response = {
        "period": {
            "from": start.isoformat(),
            "to": end.isoformat(),
        },
        "metrics": metrics,
    }

    # 4. Almacenar en caché con TTL
    _report_cache[cache_key] = (now_ts + _REPORT_CACHE_TTL, response)

    return JSONResponse(content=response)