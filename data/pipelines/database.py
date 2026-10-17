"""Conexión a base de datos para el pipeline — solo lectura en fuente, escritura en reporting.

Arquitectura de dos motores:
  - ``source_engine``: apunta a ``telemetry_events`` con un rol de **solo lectura**.
  - ``target_engine``: apunta al mismo servidor pero con permisos de escritura
    sobre el esquema ``reporting`` (nunca escribe en ``telemetry_events``).

Ambos motores se inicializan de forma perezosa (lazy) y se reutilizan
durante la vida del proceso.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Cargar .env desde services/api/ (donde ya existe)
_API_DIR = (
    Path(__file__).resolve().parent.parent.parent / "services" / "api"
)
_ENV_FILE = _API_DIR / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)
    logger.info("Cargado .env desde %s", _ENV_FILE)

_DATABASE_URL: str | None = os.getenv("DATABASE_URL")

_source_engine: Engine | None = None
_target_engine: Engine | None = None


# ── Motores ───────────────────────────────────────────────────────────


def get_source_engine() -> Engine:
    """Motor de solo lectura para ``telemetry_events``.

    Lanza ``RuntimeError`` si ``DATABASE_URL`` no está configurada.
    """
    global _source_engine
    if _source_engine is None:
        if not _DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL no está configurada. "
                "Defínela en services/api/.env o en el entorno."
            )
        _source_engine = create_engine(
            _DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            # Forzar que las consultas sean explícitamente de solo lectura.
            # En PostgreSQL se traduce en SET TRANSACTION READ ONLY.
        )
        logger.info("source_engine inicializado (solo lectura).")
    return _source_engine


def get_target_engine() -> Engine:
    """Motor con permisos de escritura sobre el esquema ``reporting``.

    Usar exclusivamente para operaciones DML/DDL en tablas del esquema
    ``reporting``. **Nunca escribir en ``telemetry_events``**.
    """
    global _target_engine
    if _target_engine is None:
        if not _DATABASE_URL:
            raise RuntimeError("DATABASE_URL no está configurada.")
        _target_engine = create_engine(
            _DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
        )
        logger.info("target_engine inicializado (permisos de escritura).")
    return _target_engine


# ── Inicialización del esquema reporting ──────────────────────────────


def init_reporting_schema() -> None:
    """Crea el esquema ``reporting`` y sus tablas si no existen.

    Es seguro llamarlo múltiples veces (``IF NOT EXISTS``).
    """
    if not _DATABASE_URL:
        logger.info("DATABASE_URL no configurada. Omitiendo inicialización.")
        return

    engine = get_target_engine()
    with engine.connect() as conn:
        conn.execute(sa_text("CREATE SCHEMA IF NOT EXISTS reporting;"))

        conn.execute(
            sa_text("""
                CREATE TABLE IF NOT EXISTS reporting.monthly_clinic_supply_performance (
                    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    clinic_id               text NOT NULL,
                    country                 text NOT NULL,
                    month_start             date NOT NULL,
                    total_supply_cost       numeric NOT NULL DEFAULT 0,
                    supply_consumption_count integer NOT NULL DEFAULT 0,
                    critical_stockout_count integer NOT NULL DEFAULT 0,
                    expiry_risk_count       integer NOT NULL DEFAULT 0,
                    currency                text NOT NULL,
                    computed_at             timestamptz NOT NULL DEFAULT now(),
                    UNIQUE (clinic_id, month_start)
                );
            """)
        )

        conn.execute(
            sa_text("""
                CREATE TABLE IF NOT EXISTS reporting.pipeline_runs (
                    run_id              uuid PRIMARY KEY,
                    flow_name           text NOT NULL,
                    status              text NOT NULL,
                    current_phase       text,
                    checkpoint          text,
                    trigger_source      text NOT NULL DEFAULT 'scheduled',
                    recalculation_reason text,
                    invalidates_run_id  uuid REFERENCES reporting.pipeline_runs(run_id),
                    month_start         date NOT NULL,
                    month_end           date NOT NULL,
                    started_at          timestamptz NOT NULL,
                    finished_at         timestamptz,
                    events_read         integer NOT NULL DEFAULT 0,
                    events_valid        integer NOT NULL DEFAULT 0,
                    events_rejected     integer NOT NULL DEFAULT 0,
                    events_deduplicated integer NOT NULL DEFAULT 0,
                    rows_inserted       integer NOT NULL DEFAULT 0,
                    rows_updated        integer NOT NULL DEFAULT 0,
                    warning_count       integer NOT NULL DEFAULT 0,
                    error_message       text,
                    prefect_flow_run_id text
                );
            """)
        )
        conn.commit()
    logger.info("Esquema reporting inicializado.")


# ── Helper para sesiones ─────────────────────────────────────────────


def get_source_session() -> Generator:
    """Yield de una sesión de solo lectura desde el motor fuente."""
    from sqlalchemy.orm import Session

    engine = get_source_engine()
    with Session(engine) as session:
        yield session


def get_target_session() -> Generator:
    """Yield de una sesión de escritura desde el motor destino."""
    from sqlalchemy.orm import Session

    engine = get_target_engine()
    with Session(engine) as session:
        yield session