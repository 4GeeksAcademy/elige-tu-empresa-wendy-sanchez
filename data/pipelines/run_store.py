"""Almacén de metadatos de ejecución — lectura/escritura en ``reporting.pipeline_runs``.

Funciones de datos que importan los endpoints de ``services/reporting/``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


# ── Creación de registro ──────────────────────────────────────────────


def create_pipeline_run(
    target_engine,
    flow_name: str = "monthly_clinic_supply_performance_flow",
    month_start: datetime | None = None,
    month_end: datetime | None = None,
    trigger_source: str = "manual",
) -> UUID:
    """Crea un registro de ejecución con estado ``running`` y lo persiste.

    Args:
        target_engine: Motor SQLAlchemy de escritura.
        flow_name: Nombre del flow Prefect.
        month_start: Inicio del periodo. Por defecto, primer día del mes actual.
        month_end: Fin del periodo. Por defecto, último día del mes actual.
        trigger_source: ``scheduled``, ``manual`` o ``recalculation``.

    Returns:
        ``run_id`` (UUID) de la ejecución creada.
    """
    now = datetime.utcnow()
    if month_start is None:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_end is None:
        # Último día del mes
        next_month = month_start.replace(day=28) + __import__("datetime").timedelta(days=4)
        month_end = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif isinstance(month_end, datetime):
        pass  # ya es datetime

    run_id = uuid4()

    stmt = sa_text("""
        INSERT INTO reporting.pipeline_runs
            (run_id, flow_name, status, current_phase, trigger_source,
             month_start, month_end, started_at)
        VALUES
            (:run_id, :flow_name, 'running', 'extract', :trigger_source,
             :month_start, :month_end, :started_at)
    """)

    with target_engine.begin() as conn:
        conn.execute(
            stmt,
            {
                "run_id": run_id,
                "flow_name": flow_name,
                "trigger_source": trigger_source,
                "month_start": month_start.date() if isinstance(month_start, datetime) else month_start,
                "month_end": month_end.date() if isinstance(month_end, datetime) else month_end,
                "started_at": now,
            },
        )

    logger.info("Pipeline run creado: run_id=%s", run_id)
    return run_id


# ── Actualización de registro ─────────────────────────────────────────


def update_pipeline_run(
    target_engine,
    run_id: UUID,
    *,
    status: str | None = None,
    current_phase: str | None = None,
    checkpoint: str | None = None,
    events_read: int | None = None,
    events_valid: int | None = None,
    events_rejected: int | None = None,
    events_deduplicated: int | None = None,
    rows_inserted: int | None = None,
    rows_updated: int | None = None,
    warning_count: int | None = None,
    error_message: str | None = None,
    prefect_flow_run_id: str | None = None,
) -> None:
    """Actualiza los campos de un registro de ejecución.

    Solo los campos con valor distinto de ``None`` se actualizan.
    Si ``status`` es ``completed`` o ``failed``, se establece ``finished_at``.
    """
    fields_to_set: list[str] = []
    params: dict = {"run_id": run_id}

    if status is not None:
        fields_to_set.append("status = :status")
        params["status"] = status
    if current_phase is not None:
        fields_to_set.append("current_phase = :current_phase")
        params["current_phase"] = current_phase
    if checkpoint is not None:
        fields_to_set.append("checkpoint = :checkpoint")
        params["checkpoint"] = checkpoint
    if events_read is not None:
        fields_to_set.append("events_read = :events_read")
        params["events_read"] = events_read
    if events_valid is not None:
        fields_to_set.append("events_valid = :events_valid")
        params["events_valid"] = events_valid
    if events_rejected is not None:
        fields_to_set.append("events_rejected = :events_rejected")
        params["events_rejected"] = events_rejected
    if events_deduplicated is not None:
        fields_to_set.append("events_deduplicated = :events_deduplicated")
        params["events_deduplicated"] = events_deduplicated
    if rows_inserted is not None:
        fields_to_set.append("rows_inserted = :rows_inserted")
        params["rows_inserted"] = rows_inserted
    if rows_updated is not None:
        fields_to_set.append("rows_updated = :rows_updated")
        params["rows_updated"] = rows_updated
    if warning_count is not None:
        fields_to_set.append("warning_count = :warning_count")
        params["warning_count"] = warning_count
    if error_message is not None:
        fields_to_set.append("error_message = :error_message")
        params["error_message"] = error_message
    if prefect_flow_run_id is not None:
        fields_to_set.append("prefect_flow_run_id = :prefect_flow_run_id")
        params["prefect_flow_run_id"] = prefect_flow_run_id

    # Si es estado terminal, poner finished_at
    if status in ("completed", "failed"):
        fields_to_set.append("finished_at = :finished_at")
        params["finished_at"] = datetime.utcnow()

    if not fields_to_set:
        logger.warning("update_pipeline_run llamado sin campos que actualizar.")
        return

    stmt = sa_text(
        f"UPDATE reporting.pipeline_runs SET "
        f"{', '.join(fields_to_set)} "
        f"WHERE run_id = :run_id"
    )

    with target_engine.begin() as conn:
        conn.execute(stmt, params)

    logger.info("Pipeline run %s actualizado: %s", run_id, status or "progreso")



# ── Bloqueo de concurrencia ──────────────────────────


def has_active_run_for_period(
    target_engine,
    month_start: datetime,
) -> tuple[bool, str | None]:
    """Verifica si ya existe una ejecucion activa para el mismo periodo.

    Una ejecucion se considera activa si su estado es ``running`` y su
    ``month_start`` coincide con el solicitado.

    Args:
        target_engine: Motor SQLAlchemy de escritura.
        month_start: Inicio del periodo a verificar.

    Returns:
        (has_active, active_run_id) - ``has_active`` es ``True`` si existe
        una ejecucion activa, y ``active_run_id`` es su UUID (o ``None``).
    """
    stmt = sa_text("""
        SELECT run_id, status
        FROM reporting.pipeline_runs
        WHERE month_start = :month_start
          AND status = 'running'
        ORDER BY started_at DESC
        LIMIT 1
    """)
    with target_engine.connect() as conn:
        row = conn.execute(
            stmt,
            {"month_start": month_start.date() if isinstance(month_start, datetime) else month_start}
        ).mappings().one_or_none()

    if row is not None:
        logger.warning(
            "Concurrencia detectada: ya existe una ejecucion activa "
            "(run_id=%s, month_start=%s) para el periodo solicitado",
            row["run_id"],
            month_start,
        )
        return True, str(row["run_id"])

    return False, None


# ── Consulta del último registro ──────────────────────────────────────


def get_latest_pipeline_run(target_engine) -> dict | None:
    """Devuelve la ejecución más reciente (por ``started_at``).

    Returns:
        Dict con los campos de la fila, o ``None`` si no hay ejecuciones.
    """
    stmt = sa_text("""
        SELECT *
        FROM reporting.pipeline_runs
        ORDER BY started_at DESC
        LIMIT 1
    """)
    with target_engine.connect() as conn:
        row = conn.execute(stmt).mappings().one_or_none()
    if row is None:
        return None
    result = dict(row)
    # Convertir tipos no serializables
    for key in ("run_id", "invalidates_run_id"):
        if isinstance(result.get(key), UUID):
            result[key] = str(result[key])
    for key in ("started_at", "finished_at"):
        if isinstance(result.get(key), datetime):
            result[key] = result[key].isoformat()
    return result