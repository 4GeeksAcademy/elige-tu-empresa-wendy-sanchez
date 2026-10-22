"""Control de estado de ``job_runs`` — máquina de estados y lock del job nocturno.

Módulo de ``services/`` que implementa la CAPA DE CONTROL DE ESTADO del script
nocturno de telemetría (Hito 7): crear, actualizar y consultar filas de
``job_runs``.

Concepto arquitectónico: **en procesamiento en segundo plano, un dato no existe
solo como dato — existe como un estado.**

Máquina de estados canónica::

    pending -> processing -> completed
                      \\-> failed
                (reintento) -> pending

- **pending**:     se crea el registro ANTES de empezar (espera de ejecución).
- **processing**:  se actualiza al inicio, ANTES de hacer ningún trabajo. Esto
                   impide que otro proceso tome la misma tarea (es el lock).
- **completed**:   solo si todo terminó bien.
- **failed**:      ante cualquier excepción. NUNCA debe quedar en processing.
- failed -> pending: reintento EXPLÍCITO y atómico (solo desde failed, nunca
  desde processing — así no se puede robar el lock).

El distributed lock ES el estado ``processing`` de la fila de ``job_runs`` —
no una tabla, columna ni flag aparte:

- Al iniciar, una instancia pasa la fila de su (job_name, target_date) a
  ``processing``.
- Si otra instancia encuentra una fila ``processing`` para el mismo día,
  ABORTA SILENCIOSAMENTE (el lock está tomado).
- Al terminar —bien o mal— la fila pasa a ``completed``/``failed``, lo que
  LIBERA el lock.

Helper de consultas para idempotencia/lock:
- ``has_processing_lock(job_name, target_date)`` — True si hay lock tomado.
- ``has_completed_for_date(job_name, target_date)`` — True si el día ya terminó
  bien (idempotencia: no re-exportar).

Observabilidad (Hito 7 §6): ``log_result(**kwargs)`` emite una línea de log
NORMALIZADA con timestamp (``ts``), nombre del job (``job``) y estado
resultante (``status``). Eventos normales a INFO; excepciones a ERROR. Sin
``log_result`` no hay una forma fiable de cumplir "cada línea lleva timestamp,
job y estado" — cada llamada la construiría a mano.

Capas: la tabla ``job_runs`` es la capa de ORQUESTACIÓN NOCTURNA. NO es un
duplicado de ``reporting.pipeline_runs`` (ETL interno del Hito 6) — capas
distintas (ver background-processes.md).

El módulo soporta Postgres (producción, vía ``DATABASE_URL``) y SQLite
(desarrollo/tests, vía ``file:``), con __casi__ el mismo SQL — separado por el
dialecto detectado. La migración es idempotente y se auto-aplica en cada uso
(``ensure_schema``).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator

from sqlalchemy import create_engine, inspect, text as sa_text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)

# Logger fijo y estable para las líneas del job nocturno. Se usa un nombre
# dedicado (no el módulo) para que cualquier proceso —cron, contenedor,
# test— pueda capturarlas con un solo selector y para que las líneas no
# dependan de la clase/estructura interna de servicios/.
_JOB_LOGGER = logging.getLogger("healthcore.nightly")

# Formato normalizado del log de una ejecución (observabilidad, Hito 7 §6).
# Cada línea lleva: timestamp ISO, nombre del job y estado resultante.
_LOG_FORMAT = (
    "event=%(event)s job=%(job)s status=%(status)s "
    "outcome=%(outcome)s target_date=%(target_date)s ts=%(ts)s"
)


def log_result(
    *,
    event: str,
    job: str,
    status: str,
    outcome: str = "",
    target_date: str = "",
    level: int = logging.INFO,
    extra: dict[str, str] | None = None,
    exc_info: bool = False,
) -> None:
    """Emite una línea de log NORMALIZADA para el job nocturno.

    Requisito de observabilidad (Hito 7 §6): cada línea de log incluye
    timestamp (``ts``), nombre del job (``job``) y estado resultante
    (``status``). Los eventos normales (inicio, fin, omisión por duplicado)
    van a INFO; las excepciones a ERROR (``level=logging.ERROR`` + ``exc_info``
    para el stack trace).

    Ejemplo de línea:
        event=started job=nightly_export status=processing outcome=processing \
        target_date=2026-10-20 ts=2026-10-22T02:00:00Z
    """
    record = {
        "event": event,
        "job": job,
        "status": status,
        "outcome": outcome,
        "target_date": target_date,
        "ts": _now().isoformat(),
    }
    if extra:
        record.update(extra)
    _JOB_LOGGER.log(level, _LOG_FORMAT, record, exc_info=exc_info)

# Máquina de estados canónica
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

VALID_STATUSES = (STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED)

# Nombre del job registrado en job_runs (job_name)
JOB_NAME_NIGHTLY_EXPORT = "nightly_export"

# Migraciones que este módulo garantiza antes de usar job_runs.
# DDL de SQLite (dev/tests). El espejo Postgres de producción vive en
# _ensure_schema_postgres() y en data/migrations/0002_job_runs.sql.
_MIGRATIONS = {
    1: """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version    INTEGER PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    2: """
    CREATE TABLE IF NOT EXISTS job_runs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        job_name      VARCHAR(64) NOT NULL,
        target_date   DATE        NOT NULL,
        status        VARCHAR(16) NOT NULL DEFAULT 'pending',
        started_at    TIMESTAMPTZ,
        finished_at   TIMESTAMPTZ,
        error_message TEXT,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        exported_rows INTEGER,
        csv_path      TEXT,
        CONSTRAINT uq_job_runs_job_target UNIQUE (job_name, target_date)
    )
    """,
    3: """
    CREATE INDEX IF NOT EXISTS idx_job_runs_job_target
        ON job_runs (job_name, target_date)
    """,
}


def _now() -> datetime:
    """Timestamp actual en UTC (aware), canon para esta máquina de estados."""
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    """Estados válidos de una fila de job_runs."""

    PENDING = STATUS_PENDING
    PROCESSING = STATUS_PROCESSING
    COMPLETED = STATUS_COMPLETED
    FAILED = STATUS_FAILED


def build_engine(database_url: str | None = None) -> Engine:
    """Crea el engine de base de datos para job_runs.

    Prioridad: `database_url` explícito > `DATABASE_URL` del entorno.
    Si nada está configurado y el sistema no tiene Postgres, usa SQLite en
    memoria (útil para runbook local y para tests). En producción SIEMPRE se
    espera `DATABASE_URL` apuntando al mismo Postgres que guarda
    `telemetry_events` y `reporting.pipeline_runs`.
    """
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        logger.warning(
            "DATABASE_URL no configurada → usando SQLite en memoria. "
            "Solo apto para desarrollo/local; en producción defina DATABASE_URL."
        )
        url = "sqlite+pysqlite:///:memory:"
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        # SQLite no soporta pool_pre_ping; un solo thread es suficiente aquí.
        kwargs.pop("pool_pre_ping", None)
    return create_engine(url, **kwargs)


def is_postgres(engine: Engine) -> bool:
    """True si el dialecto del engine es PostgreSQL."""
    return engine.dialect.name == "postgresql"


def ensure_schema(engine: Engine) -> None:
    """Aplica las migraciones pendientes de forma idempotente (la primera vez).

    Sobre Postgres usa el DDL de producción; sobre SQLite, el DDL de
    desarrollo. Llamar cada arranque es seguro (``IF NOT EXISTS`` +
    ``schema_migrations``).
    """
    if is_postgres(engine):
        _ensure_schema_postgres(engine)
    else:
        _ensure_schema_sqlite(engine)


def _ensure_schema_sqlite(engine: Engine) -> None:
    """Crea tablas y migración de versión en SQLite (dev/tests)."""
    with engine.begin() as conn:
        conn.execute(sa_text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
        for version in sorted(_MIGRATIONS):
            existing = conn.execute(sa_text("SELECT 1 FROM schema_migrations WHERE version = :v"), {"v": version}).scalar()
            if not existing:
                conn.execute(sa_text(_MIGRATIONS[version]))
                conn.execute(sa_text("INSERT INTO schema_migrations (version) VALUES (:v)"), {"v": version})


def _ensure_schema_postgres(engine: Engine) -> None:
    """Crea job_runs con el DDL de producción (PostgreSQL / Supabase)."""
    with engine.begin() as conn:
        conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INTEGER PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS job_runs (
                id            BIGSERIAL    PRIMARY KEY,
                job_name      VARCHAR(64)  NOT NULL,
                target_date   DATE         NOT NULL,
                status        VARCHAR(16)  NOT NULL DEFAULT 'pending',
                started_at    TIMESTAMPTZ,
                finished_at   TIMESTAMPTZ,
                error_message TEXT,
                created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
                exported_rows INTEGER,
                csv_path      TEXT,
                CONSTRAINT uq_job_runs_job_target UNIQUE (job_name, target_date),
                CONSTRAINT chk_job_runs_status CHECK (
                    status IN ('pending', 'processing', 'completed', 'failed')
                )
            )
        """))
        conn.execute(sa_text("CREATE INDEX IF NOT EXISTS idx_job_runs_job_target ON job_runs (job_name, target_date)"))


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convierte una Row/RowMapping de SQLAlchemy a dict serializable."""
    if row is None:
        return {}
    data = dict(row)
    for key in ("target_date",):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            data[key] = str(data[key])
    for key in ("started_at", "finished_at", "created_at"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            data[key] = data[key].isoformat()
    return data


def find_job_run(engine: Engine, job_name: str, target_date, run_id: int | None = None) -> dict[str, Any] | None:
    """Devuelve la fila de job_runs para (job_name, target_date), o por run_id.

    Usado como FUENTE DE IDEMPOTENCIA: si ya existe una fila para ese día, el
    script puede decidir no volver a exportar (o re-exportar, según estado).
    """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    with engine.connect() as conn:
        if run_id is not None:
            row = conn.execute(sa_text("SELECT * FROM job_runs WHERE id = :id"), {"id": run_id}).mappings().one_or_none()
        else:
            row = conn.execute(
                sa_text("SELECT * FROM job_runs WHERE job_name = :job_name AND target_date = :target_date"),
                {"job_name": job_name, "target_date": target_date},
            ).mappings().one_or_none()
    if row is None:
        return None
    return _row_to_dict(row)


def list_job_runs(engine: Engine, limit: int = 50, job_name: str | None = None) -> list[dict[str, Any]]:
    """Página de las últimas ejecuciones, para observabilidad."""
    stmt = sa_text(f"SELECT * FROM job_runs{' WHERE job_name = :job_name' if job_name else ''} ORDER BY created_at DESC LIMIT :limit")
    params: dict[str, Any] = {"limit": limit}
    if job_name:
        params["job_name"] = job_name
    with engine.connect() as conn:
        rows = conn.execute(stmt, params).mappings().all()
    return [_row_to_dict(r) for r in rows]


def create_job_run(engine: Engine, job_name: str, target_date, status: str = STATUS_PENDING) -> dict[str, Any]:
    """Crea el registro de la ejecución ANTES de empezar (transición → pending).

    Args:
        status: estado del registro recién creado. Por defecto ``pending``.
                Para pruebas puedes pedir directamente ``completed``/``failed``.

    Raises:
        IntegrityError: si ya existe una fila para (job_name, target_date) —
                        en ese caso el job ya fue registrado (es idempotente
                        a nivel de fila única por día).
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Estado inválido: {status}")
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    stmt = sa_text("""
        INSERT INTO job_runs (job_name, target_date, status, created_at)
        VALUES (:job_name, :target_date, :status, :now)
    """)
    created = _now()
    with engine.begin() as conn:
        conn.execute(
            stmt,
            {"job_name": job_name, "target_date": target_date, "status": status, "now": created},
        )
    row = find_job_run(engine, job_name, target_date)
    if row is None:
        row = {"job_name": job_name, "target_date": str(target_date), "status": status}
    return row


def has_processing_lock(engine: Engine, job_name: str, target_date) -> bool:
    """True si la fila (job_name, target_date) está en ``processing``.

    Es EL test del lock distribuido: si otra instancia está en ``processing``
    para ese día, esta llamada devuelve ``True`` y el script debe ABORTAR
    silenciosamente. El lock ES el estado, así que leerlo es suficiente
    (la toma real es ``mark_processing``, un UPDATE atómico).
    """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    with engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT status FROM job_runs WHERE job_name = :job_name AND target_date = :target_date"),
            {"job_name": job_name, "target_date": target_date},
        ).mappings().one_or_none()
    return bool(row and row["status"] == STATUS_PROCESSING)


def has_completed_for_date(engine: Engine, job_name: str, target_date) -> bool:
    """True si (job_name, target_date) ya terminó con éxito (completed).

    Es LA fuente de IDEMPOTENCIA por día: si ya existe una fila ``completed``
    para el día, el script NO debe volver a exportar el CSV ni relanzar el
    pipeline (registrar omisión por duplicado). Filtrar por día SIN job_name
    no basta: la clave de idempotencia es (job_name, target_date).
    """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    with engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT status FROM job_runs WHERE job_name = :job_name AND target_date = :target_date"),
            {"job_name": job_name, "target_date": target_date},
        ).mappings().one_or_none()
    return bool(row and row["status"] == STATUS_COMPLETED)


def mark_processing(engine: Engine, job_name: str, target_date) -> bool:
    """Transición pending → processing (TOMA EL LOCK).

    Esta es LA operación atómica que IMPIDE dos ejecuciones en paralelo:
    - UPDATE + filas afectadas = 1  → lock tomado por esta instancia.
    - UPDATE + filas afectadas = 0  → otra instancia ya lo tiene (o nunca
      existió pending) → devolver ``False`` para abortar SILENCIOSAMENTE.

    Un único UPDATE condicional ``WHERE status = 'pending'`` no necesita
    tabla/flag de bloqueo adicional: el lock ES el estado.
    """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    stmt = sa_text("""
        UPDATE job_runs
           SET status = :processing, started_at = :now
         WHERE job_name = :job_name
           AND target_date = :target_date
           AND status = :pending
    """)
    with engine.begin() as conn:
        result = conn.execute(
            stmt,
            {
                "job_name": job_name,
                "target_date": target_date,
                "processing": STATUS_PROCESSING,
                "pending": STATUS_PENDING,
                "now": _now(),
            },
        )
    return result.rowcount == 1


def reset_failed_to_pending(engine: Engine, job_name: str, target_date) -> bool:
    """Transición failed → pending (REARME para reintento del mismo día).

    Es atómica y SOLO permite salir de ``failed`` (nunca de ``processing``):
    un job en progreso no puede ser robado por otro proceso. Después de este
    rearme, ``mark_processing`` podrá tomar el lock correctamente en un nuevo
    intento.
    """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    stmt = sa_text("""
        UPDATE job_runs
           SET status = :pending, started_at = NULL, finished_at = NULL,
               error_message = NULL
         WHERE job_name = :job_name
           AND target_date = :target_date
           AND status = :failed
    """)
    with engine.begin() as conn:
        result = conn.execute(
            stmt,
            {
                "job_name": job_name,
                "target_date": target_date,
                "pending": STATUS_PENDING,
                "failed": STATUS_FAILED,
            },
        )
    return result.rowcount == 1


def mark_completed(engine: Engine, job_name: str, target_date, *, exported_rows: int | None = None, csv_path: str | None = None) -> bool:
    """Transición processing → completed (LIBERA EL LOCK)."""
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    stmt = sa_text("""
        UPDATE job_runs
           SET status = :completed, finished_at = :now,
               exported_rows = :exported_rows, csv_path = :csv_path
         WHERE job_name = :job_name AND target_date = :target_date
    """)
    with engine.begin() as conn:
        result = conn.execute(
            stmt,
            {
                "job_name": job_name,
                "target_date": target_date,
                "completed": STATUS_COMPLETED,
                "now": _now(),
                "exported_rows": exported_rows,
                "csv_path": csv_path,
            },
        )
    return result.rowcount == 1


def mark_failed(engine: Engine, job_name: str, target_date, *, error_message: str | None = None) -> bool:
    """Transición processing → failed (LIBERA EL LOCK dejando constancia).

    ARQUITECTURA: cualquier excepción capturada en el script debe llamar a
    esta función. Un registro jamás debe quedar en ``processing``.
    """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    stmt = sa_text("""
        UPDATE job_runs
           SET status = :failed, finished_at = :now, error_message = :error_message
         WHERE job_name = :job_name AND target_date = :target_date
    """)
    with engine.begin() as conn:
        result = conn.execute(
            stmt,
            {
                "job_name": job_name,
                "target_date": target_date,
                "failed": STATUS_FAILED,
                "now": _now(),
                "error_message": error_message,
            },
        )
    return result.rowcount == 1


__all__ = [
    "STATUS_PENDING",
    "STATUS_PROCESSING",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "VALID_STATUSES",
    "JOB_NAME_NIGHTLY_EXPORT",
    "JobStatus",
    "build_engine",
    "is_postgres",
    "ensure_schema",
    "find_job_run",
    "list_job_runs",
    "create_job_run",
    "has_processing_lock",
    "has_completed_for_date",
    "mark_processing",
    "mark_completed",
    "mark_failed",
    "reset_failed_to_pending",
    "log_result",
]