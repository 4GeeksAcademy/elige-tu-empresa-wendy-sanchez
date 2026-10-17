"""Subflow de publicaci\u00f3n de performance de cl\u00ednicas \u2014 upsert, verifica y finaliza.

Vocabulario de dominio:
- **publishing** (publicaci\u00f3n): carga de resultados en la tabla destino
  ``reporting.monthly_clinic_supply_performance`` para consumo del dashboard.
- **clinic performance**: indicadores de desempe\u00f1o por cl\u00ednica en el periodo.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from prefect import flow, task
from prefect.logging import get_run_logger

from data.pipelines.database import get_target_engine
from data.pipelines.load import upsert_monthly_kpis
from data.pipelines.run_store import update_pipeline_run

logger = logging.getLogger(__name__)


# ── Tasks ────────────────────────────────────────────────────────────


@task(
    retries=2,
    retry_delay_seconds=30,
    name="publish_clinic_kpis",
)
def task_publish_clinic_kpis(
    kpi_rows: list[dict],
    month_start_dt: datetime,
    warnings: list[str],
) -> tuple[int, int]:
    """Publica (upsert) los KPI de insumos en la tabla destino.

    **Reintentos:** 2 con 30s de espera \u2014 la BD destino puede tener
    contenci\u00f3n transaccional.

    Es **idempotente**: ``ON CONFLICT ... DO UPDATE`` reemplaza valores.

    Returns:
        (inserted, updated) \u2014 filas insertadas y actualizadas.
    """
    run_logger = get_run_logger()
    target_engine = get_target_engine()
    month_start = month_start_dt.date() if isinstance(month_start_dt, datetime) else month_start_dt
    inserted, updated = upsert_monthly_kpis(target_engine, kpi_rows, month_start)

    run_logger.info(
        "Publicaci\u00f3n completada: %d insertadas, %d actualizadas",
        inserted,
        updated,
    )
    return inserted, updated


@task(
    name="verify_published_results",
)
def task_verify_published_results(
    kpi_rows: list[dict],
    inserted: int,
    updated: int,
) -> list[str]:
    """Verifica que los KPI publicados sean consistentes.

    Returns:
        Lista de advertencias (vac\u00eda si todo ok).
    """
    run_logger = get_run_logger()
    warnings: list[str] = []
    expected = len(kpi_rows)
    total = inserted + updated

    if total != expected:
        msg = f"Discrepancia en publicaci\u00f3n: esperados {expected}, publicados {total}"
        run_logger.warning(msg)
        warnings.append(msg)

    if inserted == 0 and updated == 0 and expected > 0:
        msg = "No se insert\u00f3 ni actualiz\u00f3 ninguna fila (posible error upstream)"
        run_logger.warning(msg)
        warnings.append(msg)

    return warnings


@task(
    retries=1,
    retry_delay_seconds=15,
    name="finalize_run_log",
)
def task_finalize_run_log(
    run_id: UUID,
    status: str,
    events_read: int,
    events_valid: int,
    events_rejected: int,
    events_deduplicated: int,
    rows_inserted: int,
    rows_updated: int,
    warning_count: int,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Finaliza el registro de ejecuci\u00f3n del pipeline.

    Args:
        run_id: UUID de la ejecuci\u00f3n.
        status: ``completed`` o ``failed``.
        events_read: Total de eventos le\u00eddos.
        events_valid: Eventos v\u00e1lidos.
        events_rejected: Eventos rechazados.
        events_deduplicated: Duplicados eliminados.
        rows_inserted: Filas insertadas.
        rows_updated: Filas actualizadas.
        warning_count: N\u00famero de advertencias.
        error_message: Mensaje de error (si corresponde).

    Returns:
        Diccionario confirmando finalizaci\u00f3n.
    """
    run_logger = get_run_logger()
    target_engine = get_target_engine()

    update_pipeline_run(
        target_engine,
        run_id,
        current_phase="completed",
        checkpoint="finalized",
        status=status,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        warning_count=warning_count,
        error_message=error_message,
    )

    run_logger.info(
        "Registro finalizado: run_id=%s, status=%s, eventos=%d/%d/%d, filas=%d/%d",
        run_id, status,
        events_read, events_valid, events_rejected,
        rows_inserted, rows_updated,
    )

    return {
        "run_id": str(run_id),
        "final_status": status,
    }


# ── Subflow ──────────────────────────────────────────────────────────


@flow(
    name="subflow_clinic_performance_publishing",
    log_prints=True,
)
def subflow_clinic_performance_publishing(
    run_id: UUID,
    month_start_dt: datetime,
    kpi_rows: list[dict],
    events_read: int,
    events_valid: int,
    events_rejected: int,
    events_deduplicated: int,
    warnings: list[str],
    aggregation_failed: bool = False,
) -> dict[str, Any]:
    """Subflow de publicaci\u00f3n: persiste KPIs, verifica y finaliza.

    Args:
        run_id: UUID de la ejecuci\u00f3n.
        month_start_dt: L\u00edmite UTC del periodo.
        kpi_rows: Lista de filas KPI a insertar.
        events_read: Eventos le\u00eddos.
        events_valid: Eventos v\u00e1lidos.
        events_rejected: Eventos rechazados.
        events_deduplicated: Duplicados eliminados.
        warnings: Advertencias acumuladas.
        aggregation_failed: Si la agregaci\u00f3n fall\u00f3.

    Returns:
        Diccionario con contadores finales, estado y metadatos.
    """
    run_logger = get_run_logger()
    warning_count = len(warnings)
    final_status = "completed"

    if aggregation_failed:
        final_status = "failed"
        inserted = updated = 0
        run_logger.warning("Pipeline marcado como fallido (agregaci\u00f3n de KPI err\u00f3nea).")
    else:
        # 1. Upsert idempotente
        inserted, updated = task_publish_clinic_kpis(kpi_rows, month_start_dt, warnings)

        # 2. Verificar resultados
        verif_warnings = task_verify_published_results(kpi_rows, inserted, updated)
        warning_count += len(verif_warnings)
        warnings.extend(verif_warnings)

        # 3. Actualizar checkpoint
        target_engine = get_target_engine()
        update_pipeline_run(
            target_engine,
            run_id,
            current_phase="publish",
            checkpoint="published",
            rows_inserted=inserted,
            rows_updated=updated,
        )

    # 4. Finalizar log de ejecuci\u00f3n
    error_message = warnings[0] if (aggregation_failed and warnings) else None
    task_finalize_run_log(
        run_id=run_id,
        status=final_status,
        events_read=events_read,
        events_valid=events_valid,
        events_rejected=events_rejected,
        events_deduplicated=events_deduplicated,
        rows_inserted=inserted,
        rows_updated=updated,
        warning_count=warning_count,
        error_message=error_message,
    )

    return {
        "run_id": str(run_id),
        "status": final_status,
        "month_start": month_start_dt.isoformat() if isinstance(month_start_dt, datetime) else str(month_start_dt),
        "month_end": "",  # se completa en el flow principal
        "events_read": events_read,
        "events_valid": events_valid,
        "events_rejected": events_rejected,
        "events_deduplicated": events_deduplicated,
        "rows_inserted": inserted,
        "rows_updated": updated,
        "warning_count": warning_count,
        "error_message": error_message,
    }
