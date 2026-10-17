"""Subflow de c\u00e1lculo de KPI de insumos \u2014 valida, deduplica y agrega m\u00e9tricas.

Vocabulario de dominio:
- **supply KPI**: m\u00e9trica de negocio sobre insumos (costo total, volumen de
  consumo, frecuencia de quiebre cr\u00edtico, riesgo de vencimiento).
- **clinic supply KPI**: KPI de insumos desagregado por cl\u00ednica.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from prefect import flow, task
from prefect.logging import get_run_logger

from data.pipelines.transform import (
    validate_event,
    deduplicate_events,
    aggregate_kpis,
    verify_kpis,
)

logger = logging.getLogger(__name__)


# ── Tasks ────────────────────────────────────────────────────────────


@task(
    name="validate_and_deduplicate_events",
)
def task_validate_and_deduplicate_events(
    events: list[dict],
    events_read: int,
) -> tuple[list[dict], int, int, int]:
    """Valida payloads y deduplica por ``event_id``.

    Sin reintentos: es transformaci\u00f3n pura en memoria.

    Returns:
        (deduped_events, valid_count, rejected_count, dedup_count).
    """
    run_logger = get_run_logger()
    valid: list[dict] = []
    rejected = 0

    for ev in events:
        is_valid, reason = validate_event(ev)
        if is_valid:
            valid.append(ev)
        else:
            rejected += 1
            run_logger.warning(
                "Evento rechazado %s: %s",
                ev.get("event_id", "N/A"),
                reason,
            )

    deduped, dedup_count = deduplicate_events(valid)

    run_logger.info(
        "Validaci\u00f3n: %d v\u00e1lidos, %d rechazados, %d duplicados eliminados",
        len(valid),
        rejected,
        dedup_count,
    )
    return deduped, len(valid), rejected, dedup_count


@task(
    cache_key_fn=lambda _ctx, params: (
        str(len(params.get("events", [])))
        + "|"
        + (params["events"][0].get("event_id", "") if params.get("events") else "empty")
    ),
    cache_expiration=timedelta(hours=1),
    name="aggregate_clinic_supply_kpis",
)
def task_aggregate_clinic_supply_kpis(
    events: list[dict],
    month_start_dt: datetime,
    valid_count: int,
    rejected_count: int,
    dedup_count: int,
) -> tuple[list[dict], list[str]]:
    """Calcula los 4 KPI de insumos agregados por cl\u00ednica.

    Los KPI calculados son:
    1. **Costo de insumos por cl\u00ednica** (``total_supply_cost``)
    2. **Volumen de consumo de insumos** (``supply_consumption_count``)
    3. **Frecuencia de quiebre cr\u00edtico** (``critical_stockout_count``)
    4. **Conteo de riesgo de vencimiento** (``expiry_risk_count``)

    **Cach\u00e9:** habilitada por 1 hora.
    **Esta task es NO cr\u00edtica** \u2014 se invoca con ``return_state=True``
    desde el subflow, de modo que si falla el error se captura.

    Returns:
        (kpi_rows, warnings) \u2014 lista de filas KPI y advertencias.
    """
    run_logger = get_run_logger()
    month_start_date = month_start_dt.date() if isinstance(month_start_dt, datetime) else month_start_dt

    aggregated = aggregate_kpis(events, month_start_date)
    warnings = verify_kpis(aggregated)

    for w in warnings:
        run_logger.warning("Verificaci\u00f3n de KPI: %s", w)

    run_logger.info("KPI agregados para %d cl\u00ednicas", len(aggregated))
    return aggregated, warnings


# ── Subflow ──────────────────────────────────────────────────────────


@flow(
    name="subflow_supply_kpi_calculation",
    log_prints=True,
)
def subflow_supply_kpi_calculation(
    events: list[dict],
    month_start_dt: datetime,
    events_read: int,
) -> dict[str, Any]:
    """Subflow de c\u00e1lculo: valida, deduplica y agrega KPI de insumos.

    La tarea de agregaci\u00f3n se ejecuta con ``return_state=True`` para
    capturar fallos sin interrumpir el flujo principal.

    Args:
        events: Lista de eventos extra\u00eddos.
        month_start_dt: L\u00edmite UTC del periodo.
        events_read: Contador de eventos le\u00eddos (para trazabilidad).

    Returns:
        Diccionario con:
        - ``kpi_rows`` \u2014 lista de filas KPI (puede ser vac\u00eda si fall\u00f3).
        - ``warnings`` \u2014 advertencias de validaci\u00f3n/verificaci\u00f3n.
        - ``valid_count``, ``rejected_count``, ``dedup_count`` \u2014 contadores.
        - ``aggregation_failed`` \u2014 booleano indicando si la agregaci\u00f3n fall\u00f3.
        - ``aggregation_error`` \u2014 mensaje de error si fall\u00f3.
    """
    run_logger = get_run_logger()

    # 1. Validar y deduplicar
    deduped_events, valid_count, rejected_count, dedup_count = (
        task_validate_and_deduplicate_events(events, events_read)
    )

    # 2. Agregar KPIs (con return_state por ser task no cr\u00edtica)
    aggregate_state = task_aggregate_clinic_supply_kpis.submit(
        events=deduped_events,
        month_start_dt=month_start_dt,
        valid_count=valid_count,
        rejected_count=rejected_count,
        dedup_count=dedup_count,
        return_state=True,
    )

    if aggregate_state.is_failed():
        error_msg = f"Fall\u00f3 la agregaci\u00f3n de KPI: {aggregate_state.message}"
        run_logger.error(error_msg)
        return {
            "kpi_rows": [],
            "warnings": [error_msg],
            "valid_count": valid_count,
            "rejected_count": rejected_count,
            "dedup_count": dedup_count,
            "aggregation_failed": True,
            "aggregation_error": aggregate_state.message,
        }

    kpi_rows, verifications = aggregate_state.result()

    return {
        "kpi_rows": kpi_rows,
        "warnings": verifications,
        "valid_count": valid_count,
        "rejected_count": rejected_count,
        "dedup_count": dedup_count,
        "aggregation_failed": False,
        "aggregation_error": None,
    }
