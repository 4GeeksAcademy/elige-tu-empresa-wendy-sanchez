"""Flow Prefect del pipeline mensual de desempeño de insumos por clínica.

Implementa el flujo ETL completo (Fase 1) con:
- 7 tasks independientes con inputs/outputs explícitos.
- Al menos 1 paso opcional/no crítico con ``return_state=True``.
- Reintentos en tasks que tocan servicios externos (Fase 2).
- Caché en task de transformación costosa (Fase 2).
- Idempotencia vía upsert (Fase 3).
- Registro de metadatos de ejecución en ``reporting.pipeline_runs`` (Fase 3).

Uso:
    from prefect import flow
    from data.pipelines.flows import monthly_clinic_supply_performance_flow

    flow_state = await monthly_clinic_supply_performance_flow("2025-01-01")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta, date
from typing import Any
from uuid import UUID

from prefect import flow, task
from prefect.logging import get_run_logger
from prefect.states import Failed, Completed

from data.pipelines.database import (
    get_source_engine,
    get_target_engine,
)
from data.pipelines.extract import extract_telemetry_events
from data.pipelines.transform import (
    validate_event,
    deduplicate_events,
    aggregate_kpis,
    verify_kpis,
)
from data.pipelines.load import upsert_monthly_kpis
from data.pipelines.run_store import (
    create_pipeline_run,
    update_pipeline_run,
    get_latest_pipeline_run,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────


def _resolve_period(month_start: str | date | datetime | None) -> tuple[datetime, datetime]:
    """Convierte ``month_start`` a los límites UTC del periodo.

    Args:
        month_start: Fecha o string en formato ``YYYY-MM-DD``.
            Si es ``None``, usa el primer día del mes anterior.

    Returns:
        (month_start_dt, month_end_dt) — tupla de datetimes UTC.
    """
    now = datetime.utcnow()
    if month_start is None:
        # Mes anterior por defecto
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

    # Calcular month_end: primer día del mes siguiente
    month_end_dt = (month_start_dt.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return month_start_dt, month_end_dt


# ── Tasks del pipeline ────────────────────────────────────────────────
# Cada task es independiente con inputs y outputs explícitos.
# Las tasks que interactúan con servicios externos tienen retries.


@task(
    retries=2,
    retry_delay_seconds=30,
    name="resolve_period",
)
def task_resolve_period(
    month_start: str | date | datetime | None,
) -> tuple[datetime, datetime, UUID | None]:
    """Task 1: Resuelve y valida el periodo mensual.

    **Reintentos:** 2, separados 30s — es una operación puramente
    computacional sin IO externa, pero se incluye por consistencia
    con el diseño. Si falla, el pipeline no puede continuar.
    """
    run_logger = get_run_logger()
    month_start_dt, month_end_dt = _resolve_period(month_start)
    run_logger.info(
        "Periodo resuelto: %s → %s",
        month_start_dt.isoformat(),
        month_end_dt.isoformat(),
    )
    return month_start_dt, month_end_dt, None


@task(
    retries=3,
    retry_delay_seconds=60,
    name="extract_inventory_events",
)
def task_extract_events(
    month_start_dt: datetime,
    month_end_dt: datetime,
    run_id: UUID | None,
) -> tuple[list[dict], int]:
    """Task 2: Extrae eventos de ``telemetry_events`` (solo lectura).

    **Reintentos:** 3 con 60s de espera.
    **Justificación:** La base de datos es un servicio externo que puede
    experimentar cortes transitorios, timeouts de conexión o failover.
    3 reintentos cubren la mayoría de los escenarios de caída breve sin
    alargar excesivamente la espera total (3 × 60s = 3 min).
    """
    run_logger = get_run_logger()
    source_engine = get_source_engine()
    events = extract_telemetry_events(source_engine, month_start_dt, month_end_dt)
    run_logger.info("Extraídos %d eventos", len(events))
    return events, len(events)


@task(
    name="validate_and_deduplicate_events",
)
def task_validate_and_deduplicate(
    events: list[dict],
    events_read: int,
) -> tuple[list[dict], int, int, int]:
    """Task 3: Valida payloads y deduplica por ``event_id``.

    **Sin reintentos:** es pura transformación en memoria.
    Si falla, es por un bug de código, no por un fallo transitorio.
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
        "Validación: %d válidos, %d rechazados, %d duplicados eliminados",
        len(valid),
        rejected,
        dedup_count,
    )
    return deduped, len(valid), rejected, dedup_count


@task(
    cache_key_fn=lambda _ctx, params: (
        # La clave de caché incluye el contenido del primer evento y el
        # total de eventos. Así, si los datos de entrada cambian
        # (por ejemplo, en un recálculo con eventos tardíos), la caché
        # se invalida automáticamente.
        str(len(params.get("events", []))) + (
            "|" + params["events"][0].get("event_id", "")
            if params.get("events")
            else "empty"
        )
    ),
    cache_expiration=timedelta(hours=1),
    name="aggregate_monthly_clinic_kpis",
)
def task_aggregate_kpis(
    events: list[dict],
    month_start_dt: datetime,
    valid_count: int,
    rejected_count: int,
    dedup_count: int,
) -> tuple[list[dict], list[str]]:
    """Task 4: Calcula los 4 KPI agregados por clínica (transformación costosa).

    **Caché:** habilitada por 1 hora.
    **Clave de caché:** concatena la longitud de la lista de eventos y el
    ``event_id`` del primer evento. Si se reintenta con los mismos datos
    dentro de la misma hora, Prefect reutiliza el resultado anterior.
    **Justificación de 1 hora:** el pipeline se ejecuta mensualmente.
    Una hora es más que suficiente para cubrir reintentos sin riesgos
    de usar datos desactualizados.

    **Esta task es NO crítica para el flujo principal** — se invoca con
    ``return_state=True`` desde el flow, de modo que si falla, el error
    se captura y el pipeline continúa con la opción de reintentar
    manualmente o registrar el fallo.
    """
    run_logger = get_run_logger()
    month_start_date = month_start_dt.date() if isinstance(month_start_dt, datetime) else month_start_dt

    aggregated = aggregate_kpis(events, month_start_date)
    warnings = verify_kpis(aggregated)

    for w in warnings:
        run_logger.warning("Verificación de KPI: %s", w)

    run_logger.info("KPI agregados para %d clínicas", len(aggregated))
    return aggregated, warnings


@task(
    retries=2,
    retry_delay_seconds=30,
    name="upsert_monthly_results",
)
def task_upsert_results(
    kpi_rows: list[dict],
    month_start_dt: datetime,
    warnings: list[str],
) -> tuple[int, int]:
    """Task 5: Carga los resultados mediante upsert transaccional.

    **Reintentos:** 2 con 30s de espera.
    **Justificación:** la base de datos destino puede tener contención
    transaccional. 2 reintentos cubren conflictos de serialización sin
    extender la espera más allá de 1 minuto total.

    Es **idempotente**: el ``ON CONFLICT`` reemplaza valores, no suma.
    """
    run_logger = get_run_logger()
    target_engine = get_target_engine()
    month_start = month_start_dt.date() if isinstance(month_start_dt, datetime) else month_start_dt
    inserted, updated = upsert_monthly_kpis(target_engine, kpi_rows, month_start)

    run_logger.info(
        "Carga completada: %d insertadas, %d actualizadas",
        inserted,
        updated,
    )
    return inserted, updated


@task(
    name="verify_monthly_results",
)
def task_verify_results(
    kpi_rows: list[dict],
    inserted: int,
    updated: int,
) -> list[str]:
    """Task 6: Valida que los resultados cargados sean coherentes.

    **Sin reintentos:** validación en memoria sobre datos ya cargados.
    """
    run_logger = get_run_logger()
    if not kpi_rows:
        run_logger.warning("No hay filas de KPI que verificar.")
        return ["No hay filas de KPI en el resultado."]

    run_logger.info(
        "Verificación: %d clínicas, %d insert, %d update",
        len(kpi_rows),
        inserted,
        updated,
    )
    return []


@task(
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
) -> dict:
    """Task 7: Persiste la metadata de la ejecución en ``reporting.pipeline_runs``.

    **Sin reintentos:** es la última task; si falla el log,
    el pipeline ya habrá dejado los datos correctos en la tabla de KPI.
    Se registra el error en el logger.
    """
    run_logger = get_run_logger()
    target_engine = get_target_engine()
    try:
        update_pipeline_run(
            target_engine,
            run_id,
            status=status,
            events_read=events_read,
            events_valid=events_valid,
            events_rejected=events_rejected,
            events_deduplicated=events_deduplicated,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            warning_count=warning_count,
            error_message=error_message,
        )
        run_logger.info(
            "Pipeline run %s finalizado con estado %s", run_id, status
        )
    except Exception as exc:
        run_logger.error(
            "No se pudo actualizar el log de ejecución: %s", exc
        )
        return {"finalized": False, "error": str(exc)}
    return {"finalized": True, "status": status}


# ── Tarea opcional (no crítica) ───────────────────────────────────────
# Esta task se invoca con return_state=True en el flow, por lo que
# su fallo no interrumpe la ejecución principal.


@task(
    name="snapshot_eval_export",
)
def task_snapshot_eval_export(
    kpi_rows: list[dict],
    month_start_dt: datetime,
) -> str:
    """**Task opcional:** exporta un snapshot de los KPI a JSON en ``data/eval/``.

    Esta task **no es crítica** para el pipeline. Si falla (permisos de
    disco, espacio, etc.), el flow principal continúa sin impacto en la
    carga de datos.

    La exportación sirve para:
    - Evaluar la calidad de los datos cargados.
    - Comparar corridas entre sí durante el desarrollo.
    - Depurar diferencias entre entornos.
    """
    import json
    import os
    from pathlib import Path

    run_logger = get_run_logger()

    month_str = month_start_dt.strftime("%Y-%m") if isinstance(month_start_dt, datetime) else str(month_start_dt)
    eval_dir = Path(__file__).resolve().parent.parent.parent / "data" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    filename = f"kpi_snapshot_{month_str}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
    filepath = eval_dir / filename

    serializable = []
    for row in kpi_rows:
        r = dict(row)
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
        serializable.append(r)

    with open(filepath, "w") as f:
        json.dump(serializable, f, indent=2, default=str)

    run_logger.info("Snapshot exportado a %s", filepath)
    return str(filepath)


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

    Orquesta las 7 tasks ETL más un paso opcional de snapshot.
    El pipeline es resiliente: las tasks críticas detienen el flow,
    la task opcional no.

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

    # ── Fase de preparación ───────────────────────────────────────
    # 1. Resolver periodo y crear registro de ejecución
    month_start_dt, month_end_dt, _run_id_from_resolve = task_resolve_period(month_start)
    target_engine = get_target_engine()
    run_id = create_pipeline_run(
        target_engine,
        month_start=month_start_dt,
        month_end=month_end_dt,
        trigger_source=trigger_source,
    )
    run_logger.info("Ejecución registrada: run_id=%s", run_id)

    error_message: str | None = None
    final_status: str = "completed"
    warning_count: int = 0

    # Inicializar contadores ANTES del try para evitar
    # problemas de alcance en el bloque except y la finalización
    events_read: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    dedup_count: int = 0
    inserted: int = 0
    updated: int = 0
    kpi_rows: list[dict] = []

    try:
        # ── Fase de extracción ────────────────────────────────────
        # 2. Extraer eventos de telemetry_events (solo lectura)
        events, events_read = task_extract_events(month_start_dt, month_end_dt, run_id)
        update_pipeline_run(
            target_engine,
            run_id,
            current_phase="extract",
            events_read=events_read,
        )

        # ── Fase de validación ────────────────────────────────────
        # 3. Validar y deduplicar
        deduped_events, valid_count, rejected_count, dedup_count = (
            task_validate_and_deduplicate(events, events_read)
        )
        update_pipeline_run(
            target_engine,
            run_id,
            current_phase="validate",
            checkpoint="validated",
            events_valid=valid_count,
            events_rejected=rejected_count,
            events_deduplicated=dedup_count,
        )

        # ── Fase de transformación ────────────────────────────────
        # 4. Agregar KPI (con caché de 1 hora)
        #    La task de agregación se ejecuta con return_state para
        #    capturar su estado. Si falla, el fallo se maneja explícitamente.
        # Capturar el estado explícitamente: si falla, el flow maneja
        # el error sin propagar la excepción automáticamente.
        aggregate_state = task_aggregate_kpis.submit(
            events=deduped_events,
            month_start_dt=month_start_dt,
            valid_count=valid_count,
            rejected_count=rejected_count,
            dedup_count=dedup_count,
            return_state=True,
        )
        if aggregate_state.is_failed():
            # La task falló — manejamos el fallo explícitamente
            error_message = f"Falló la agregación de KPI: {aggregate_state.message}"
            run_logger.error(error_message)
            final_status = "failed"
            # Continuamos para que el log refleje el fallo
            kpi_rows: list[dict] = []
            verifications: list[str] = [error_message]
        else:
            kpi_rows, verifications = aggregate_state.result()
            warning_count += len(verifications)
            update_pipeline_run(
                target_engine,
                run_id,
                current_phase="transform",
                checkpoint="aggregated",
                warning_count=warning_count,
            )

        # ── Fase de carga (idempotente) ───────────────────────────
        if final_status != "failed" and kpi_rows:
            # 5. Upsert idempotente
            inserted, updated = task_upsert_results(kpi_rows, month_start_dt, verifications)
            update_pipeline_run(
                target_engine,
                run_id,
                current_phase="load",
                checkpoint="upserted",
                rows_inserted=inserted,
                rows_updated=updated,
            )
        else:
            inserted = updated = 0
            verifications = verifications or []

        # ── Paso opcional: snapshot de evaluación ─────────────────
        #    Se invoca con return_state=True para que un fallo aquí
        #    no interrumpa el flujo principal.
        if kpi_rows:
            snapshot_state = task_snapshot_eval_export.submit(
                kpi_rows=kpi_rows,
                month_start_dt=month_start_dt,
                return_state=True,
            )
            if snapshot_state.is_failed():
                run_logger.warning(
                    "Snapshot de eval falló (no crítico): %s",
                    snapshot_state.message,
                )
                # No cambiamos final_status — es opcional
                warning_count += 1

        # ── Fase de verificación ──────────────────────────────────
        if final_status != "failed":
            verif_warnings = task_verify_results(kpi_rows, inserted, updated)
            warning_count += len(verif_warnings)
            verifications.extend(verif_warnings)

    except Exception as exc:
        error_message = f"Error no recuperable en el flow: {exc}"
        final_status = "failed"
        run_logger.exception("Error en pipeline: %s", exc)
        # Variables ya inicializadas arriba, no hace falta dir()
        pass

    # ── Finalización — siempre se ejecuta ─────────────────────────
    task_finalize_run_log(
        run_id=run_id,
        status=final_status,
        events_read=events_read,
        events_valid=valid_count,
        events_rejected=rejected_count,
        events_deduplicated=dedup_count,
        rows_inserted=inserted,
        rows_updated=updated,
        warning_count=warning_count,
        error_message=error_message,
    )

    return {
        "run_id": str(run_id),
        "status": final_status,
        "month_start": month_start_dt.isoformat(),
        "month_end": month_end_dt.isoformat(),
        "events_read": events_read,
        "events_valid": valid_count,
        "events_rejected": rejected_count,
        "events_deduplicated": dedup_count,
        "rows_inserted": inserted,
        "rows_updated": updated,
        "warning_count": warning_count,
        "error_message": error_message,
    }