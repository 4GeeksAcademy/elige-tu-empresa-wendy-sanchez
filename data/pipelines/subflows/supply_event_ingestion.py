"""Subflow de ingesta de eventos de insumos — resuelve el periodo y obtiene eventos.

Vocabulario de dominio:
- **supply** (insumo): producto clínico (medicamento, EPP, consumible, equipo).
- **ingestion** (ingesta): extracción de eventos de origen para procesamiento.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta, date
from typing import Any
from uuid import UUID

from prefect import flow, task
from prefect.logging import get_run_logger

from data.pipelines.database import (
    get_source_engine,
    get_target_engine,
)
from data.pipelines.extract import extract_telemetry_events
from data.pipelines.run_store import create_pipeline_run

logger = logging.getLogger(__name__)


# ── Tasks ────────────────────────────────────────────────────────────


@task(
    retries=2,
    retry_delay_seconds=30,
    name="resolve_period",
)
def task_resolve_period(
    month_start: str | date | datetime | None,
) -> tuple[datetime, datetime]:
    """Resuelve y valida el periodo mensual a procesar.

    Args:
        month_start: Fecha o string en formato ``YYYY-MM-DD``.
            Si es ``None``, usa el primer día del mes anterior.

    Returns:
        (month_start_dt, month_end_dt) — tupla de datetimes UTC.
    """
    run_logger = get_run_logger()
    now = datetime.utcnow()

    if month_start is None:
        first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_start_dt = first_of_this - timedelta(days=1)
        month_start_dt = month_start_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif isinstance(month_start, str):
        month_start_dt = datetime.strptime(month_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    elif isinstance(month_start, date) and not isinstance(month_start, datetime):
        month_start_dt = datetime.combine(month_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    else:
        month_start_dt = month_start
        if month_start_dt.tzinfo is None:
            month_start_dt = month_start_dt.replace(tzinfo=timezone.utc)

    month_end_dt = (month_start_dt.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    run_logger.info(
        "Periodo resuelto: %s \u2192 %s",
        month_start_dt.isoformat(),
        month_end_dt.isoformat(),
    )
    return month_start_dt, month_end_dt


@task(
    retries=3,
    retry_delay_seconds=60,
    name="ingest_supply_events",
)
def task_ingest_supply_events(
    month_start_dt: datetime,
    month_end_dt: datetime,
    run_id: UUID | None,
) -> tuple[list[dict], int]:
    """Ingesta eventos de insumos desde ``telemetry_events`` (solo lectura).

    Extrae los eventos del periodo.

    **Reintentos:** 3 con 60s de espera \u2014 la BD origen es un servicio externo.

    Returns:
        (events, events_read) \u2014 lista de eventos y contador.
    """
    run_logger = get_run_logger()
    source_engine = get_source_engine()
    events = extract_telemetry_events(source_engine, month_start_dt, month_end_dt)
    run_logger.info("Ingestados %d eventos de insumos", len(events))
    return events, len(events)


# ── Subflow ──────────────────────────────────────────────────────────


@flow(
    name="subflow_supply_event_ingestion",
    log_prints=True,
)
def subflow_supply_event_ingestion(
    month_start: str | date | datetime | None = None,
    trigger_source: str = "manual",
) -> dict[str, Any]:
    """Subflow de ingesta: resuelve el periodo, crea el registro y extrae eventos.

    Args:
        month_start: Primer d\u00eda del mes a procesar.
        trigger_source: ``scheduled``, ``manual`` o ``recalculation``.

    Returns:
        Diccionario con:
        - ``month_start_dt``, ``month_end_dt`` \u2014 l\u00edmites UTC del periodo.
        - ``run_id`` \u2014 UUID de la ejecuci\u00f3n reci\u00e9n creada.
        - ``events`` \u2014 lista de eventos extra\u00eddos.
        - ``events_read`` \u2014 n\u00famero total de eventos le\u00eddos.
    """
    run_logger = get_run_logger()

    # 1. Resolver periodo
    month_start_dt, month_end_dt = task_resolve_period(month_start)

    # 2. Crear registro de ejecuci\u00f3n en la BD destino
    target_engine = get_target_engine()
    run_id = create_pipeline_run(
        target_engine,
        month_start=month_start_dt,
        month_end=month_end_dt,
        trigger_source=trigger_source,
    )
    run_logger.info("Ejecuci\u00f3n registrada: run_id=%s", run_id)

    # 3. Extraer eventos
    events, events_read = task_ingest_supply_events(month_start_dt, month_end_dt, run_id)

    return {
        "month_start_dt": month_start_dt,
        "month_end_dt": month_end_dt,
        "run_id": run_id,
        "events": events,
        "events_read": events_read,
    }
