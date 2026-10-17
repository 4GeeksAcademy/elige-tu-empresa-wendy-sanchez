"""Flow Prefect del pipeline mensual de desempeño de insumos por clínica.

Implementa el flujo ETL completo orquestando 4 subflows:
1. :func:`subflow_supply_event_ingestion` — resuelve el periodo y extrae eventos.
2. :func:`subflow_supply_kpi_calculation` — valida, deduplica y agrega KPIs.
3. :func:`subflow_clinic_kpi_snapshot` — exporta snapshot a JSON (opcional).
4. :func:`subflow_clinic_performance_publishing` — persiste resultados y finaliza la ejecución.

Uso:
    from prefect import flow
    from data.pipelines.flows import monthly_clinic_supply_performance_flow

    result = monthly_clinic_supply_performance_flow("2025-01-01")
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any

from prefect import flow
from prefect.logging import get_run_logger

from data.pipelines.database import get_target_engine
from data.pipelines.run_store import update_pipeline_run
from data.pipelines.subflows import (
    subflow_supply_event_ingestion,
    subflow_supply_kpi_calculation,
    subflow_clinic_performance_publishing,
    subflow_clinic_kpi_snapshot,
)

logger = logging.getLogger(__name__)


# ── Flow principal ────────────────────────────────────────────────────


@flow(
    name="monthly_clinic_supply_performance_flow",
    log_prints=True,
)
def monthly_clinic_supply_performance_flow(
    month_start: str | date | datetime | None = None,
    trigger_source: str = "manual",
) -> dict[str, Any]:
    """Flow Prefect del pipeline mensual de desempeño de insumos por clínica.

    Orquesta los 4 subflows ETL. El subflow de snapshot se invoca con
    ``return_state=True`` para que un fallo no interrumpa el flujo principal.

    Args:
        month_start: Primer día del mes en formato ``YYYY-MM-DD``
            o como objeto ``date``/``datetime``. Si es ``None``, se usa
            el mes anterior.
        trigger_source: ``scheduled``, ``manual`` o ``recalculation``.

    Returns:
        Dict con metadatos de la ejecución: ``run_id``, ``status``,
        ``month_start``, contadores, etc.
    """
    run_logger = get_run_logger()

    # ── Fase 1: Extracción ──────────────────────────────────────
    # Resuelve el periodo, crea el registro y extrae eventos
    extraction_result = subflow_supply_event_ingestion(
        month_start=month_start,
        trigger_source=trigger_source,
    )

    month_start_dt: datetime = extraction_result["month_start_dt"]
    month_end_dt: datetime = extraction_result["month_end_dt"]
    run_id = extraction_result["run_id"]
    events: list[dict] = extraction_result["events"]
    events_read: int = extraction_result["events_read"]

    run_logger.info(
        "Fase 1 — Extracción completada: %d eventos, run_id=%s",
        events_read,
        run_id,
    )

    # ── Fase 2: Transformación ──────────────────────────────────
    # Valida, deduplica y agrega KPIs (agregación con return_state)
    transform_result = subflow_supply_kpi_calculation(
        events=events,
        month_start_dt=month_start_dt,
        events_read=events_read,
    )

    kpi_rows: list[dict] = transform_result["kpi_rows"]
    warnings: list[str] = transform_result["warnings"]
    valid_count: int = transform_result["valid_count"]
    rejected_count: int = transform_result["rejected_count"]
    dedup_count: int = transform_result["dedup_count"]
    aggregation_failed: bool = transform_result["aggregation_failed"]

    run_logger.info(
        "Fase 2 — Transformación completada: %d válidos, %d rechazados, "
        "%d duplicados, agregación=%s",
        valid_count,
        rejected_count,
        dedup_count,
        "fallida" if aggregation_failed else "exitosa",
    )

    # ── Paso opcional: Snapshot (no crítico) ────────────────────
    # Se ejecuta con try/except para no interrumpir el flujo principal
    if kpi_rows and not aggregation_failed:
        try:
            snapshot_result = subflow_clinic_kpi_snapshot(
                kpi_rows=kpi_rows,
                month_start_dt=month_start_dt,
            )
            if snapshot_result and snapshot_result.get("snapshot_path"):
                run_logger.info("Snapshot exportado a %s", snapshot_result["snapshot_path"])
        except Exception as snap_exc:
            run_logger.warning(
                "Snapshot de KPI falló (no crítico): %s", snap_exc,
            )
            warnings.append(f"Snapshot falló: {snap_exc}")

    # ── Fase 3: Carga y finalización ────────────────────────────
    # Persiste KPIs, verifica y actualiza el log de ejecución
    loading_result = subflow_clinic_performance_publishing(
        run_id=run_id,
        month_start_dt=month_start_dt,
        kpi_rows=kpi_rows if not aggregation_failed else [],
        events_read=events_read,
        events_valid=valid_count,
        events_rejected=rejected_count,
        events_deduplicated=dedup_count,
        warnings=warnings,
        aggregation_failed=aggregation_failed,
    )

    # Completar campos que faltan en el resultado de loading
    loading_result["month_end"] = month_end_dt.isoformat()

    run_logger.info(
        "Pipeline finalizado: status=%s, run_id=%s",
        loading_result.get("status"),
        loading_result.get("run_id"),
    )

    return loading_result
