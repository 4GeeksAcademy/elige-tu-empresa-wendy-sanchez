"""Orquestación del job nocturno — lógica de proceso independiente de la API.

Este módulo implementa EXACTAMENTE la máquina de estados del script nocturno:

    1.  Crear el registro en ``job_runs`` (estado ``pending``) ANTES de nada.
    2.  ``mark_processing(...)`` — transición atómica pending → processing.
        - Si devuelve ``False``, OTRA INSTANCIA ya está corriendo para ese día
          → abortar SILENCIOSAMENTE (único resultado "noop/aborted").
    3.  Exportar ``telemetry_events`` del día objetivo a
        ``data/raw/telemetry_<YYYY-MM-DD>.csv``  (CSV = backup, no input del
        pipeline).
    4.  Lanzar el subprocess del pipeline (Hito 6) y, si falla, abrir una
        excepción (que derivará en estado ``failed``).
    5.  ``mark_completed(...)`` — solo si TODO terminó bien.
    6(alt). ``mark_failed(exc)`` — ante CUALQUIER excepción. Nunca se queda en
        ``processing`` (sin registros zombi).

Observabilidad (Hito 7 §6): los eventos normales —inicio, fin y omisión por
duplicado— se registran a nivel INFO; las excepciones a nivel ERROR. Cada
línea de log incluye timestamp, nombre del job (``job=nightly_export``) y
estado resultante (``status=...``) gracias al helper ``log_result`` de
``services.job_runner``. Los logs de detalle interno (export, pipeline)
también llevan el nombre del job para mantener el formato unificado.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import text as sa_text
from sqlalchemy.engine import Connection, Engine

from services.job_runner import (
    JOB_NAME_NIGHTLY_EXPORT,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    build_engine,
    create_job_run,
    ensure_schema,
    find_job_run,
    log_result,
    mark_completed,
    mark_failed,
    mark_processing,
    reset_failed_to_pending,
)

logger = logging.getLogger(__name__)

# ── Constantes de convención (según CONTEXT del Hito 7) ────────────────

# "Ayer" = día calendario anterior en UTC.
TARGET_DATE = "TARGET_DATE"          # sobrescribe la fecha objetivo para pruebas

_DEFAULT_PIPELINE_CMD = "python -m data.pipelines.runner"


def default_export_dir() -> Path:
    """data/raw/ relativo a la raíz del proyecto."""
    here = Path(__file__).resolve()
    # services/nightly/nightly_service.py -> raíz (3 niveles arriba)
    return here.parents[2] / "data" / "raw"


def csv_path_for(target_date: date, export_dir: Path | None = None) -> Path:
    """Convención de nombre de fichero: data/raw/telemetry_YYYY-MM-DD.csv"""
    export_dir = export_dir or default_export_dir()
    return export_dir / f"telemetry_{target_date.isoformat()}.csv"


def target_date_from_env() -> date:
    """Día objetivo: 'ayer' UTC, o TARGET_DATE=YYYY-MM-DD si está definida."""
    raw = os.getenv(TARGET_DATE)
    if raw:
        return date.fromisoformat(raw)
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def export_telemetry_events(
    engine: Engine,
    target_date: date,
    export_dir: Path | None = None,
) -> tuple[int, Path]:
    """Exporta los eventos de telemetría del día a CSV (backup, no pipeline).

    Args:
        engine: Engine de SOLO LECTURA contra ``telemetry_events``.
        target_date: día calendario (UTC) a exportar.
        export_dir: carpeta destino (por defecto data/raw).

    Returns:
        (filas_exportadas, ruta_del_csv)

    El rango [target_date 00:00, target_date+1 00:00) en UTC garantiza que
    "ayer" calendario incluya TODOS los eventos de ese día.

    IDEMPOTENCIA DE ARCHIVO: el CSV es un snapshot de backup/auditoría. Si el
    archivo ``telemetry_YYYY-MM-DD.csv`` YA EXISTE, no se re-escribe: se
    devuelve ``(0, ruta)`` para que el flujo siga (el pipeline lee de BD, no
    de este archivo). Solo se escribe cuando el archivo NO existe.
    """
    export_dir = export_dir or default_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    path = csv_path_for(target_date, export_dir)

    if path.exists():
        # Snapshot ya generado previamente → no re-exportar (backup inmutable).
        log_result(
            event="export_skipped",
            job=JOB_NAME_NIGHTLY_EXPORT,
            status=STATUS_PROCESSING,
            outcome="processing",
            target_date=str(target_date),
            extra={"csv_path": str(path), "reason": "snapshot_preview"},
        )
        return 0, path

    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    query = sa_text("""
        SELECT timestamp, event_type, tags
        FROM telemetry_events
        WHERE timestamp >= :start AND timestamp < :end
        ORDER BY timestamp
    """)

    with engine.connect() as conn:
        rows = conn.execute(query, {"start": start, "end": end}).mappings().all()

    # Escribir CSV manualmente en UTF-8 (sin dependencia de pandas).
    _write_csv(path, rows)

    log_result(
        event="export_done",
        job=JOB_NAME_NIGHTLY_EXPORT,
        status=STATUS_PROCESSING,
        outcome="processing",
        target_date=str(target_date),
        extra={"exported_rows": str(len(rows)), "csv_path": str(path)},
    )
    return len(rows), path


def _write_csv(path: Path, rows) -> None:
    """Serializa filas (mappings) con timestamp, event_type y tags a CSV."""
    import csv
    import json

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "event_type", "tags"])
        for row in rows:
            timestamp = row["timestamp"]
            if not isinstance(timestamp, str):
                timestamp = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
            tags = row["tags"]
            if tags is not None and not isinstance(tags, str):
                tags = json.dumps(tags)
            writer.writerow([timestamp, row["event_type"], tags])


def run_pipeline_subprocess(
    target_date: date | None = None,
    command: list[str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """Lanza el pipeline del Hito 6 como subprocess independiente.

    Referencia del CONTEXT: ``python -m data.pipelines.telemetry_kpi_daily.run
    --no-prefect``, ajustado al entry point real de este repo:
    ``python -m data.pipelines.runner`` (pipeline mensual de supply
    performance). El script nocturno NO espera a que el pipeline termine de
    transformar/load: delega y registra en job_runs lo que lanzó.

    Como el pipeline es independiente y ya persiste en
    ``reporting.pipeline_runs`` él mismo, aquí solo se captura que el comando
    pudo ejecutarse; si el comando devuelve código de salida != 0 se levanta
    una excepción → propagará a ``failed`` en job_runs.
    """
    command = command or _DEFAULT_PIPELINE_CMD.split(maxsplit=2)  # normaliza a lista
    if isinstance(command, str):
        command = command.split()
    cwd = cwd or Path(__file__).resolve().parents[2]

    env = os.environ.copy()
    if target_date is not None and TARGET_DATE not in env:
        env[TARGET_DATE] = target_date.isoformat()

    log_result(
        event="launch_pipeline",
        job=JOB_NAME_NIGHTLY_EXPORT,
        status=STATUS_PROCESSING,
        outcome="processing",
        target_date=str(target_date) if target_date else "",
        extra={"command": " ".join(command)},
    )
    result = subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Pipeline no arrancó correctamente (exit={result.returncode}). "
            f"stderr: {result.stderr[-500:]}"
        )
    return result


def run_nightly(
    engine: Engine | None = None,
    target_date: date | None = None,
    export_dir: Path | None = None,
    pipeline_command: list[str] | None = None,
    skip_pipeline: bool = False,
    force: bool = False,
) -> dict:
    """Ejecuta una corrida completa del job nocturno y devuelve su outcome.

    Args:
        engine: engine de BD (si no se pasa, se crea uno con DATABASE_URL).
        target_date: día objetivo (por defecto 'ayer' UTC / TARGET_DATE).
        export_dir: carpeta de exportación (por defecto data/raw).
        pipeline_command: comando del pipeline a lanzar como subprocess.
        skip_pipeline: solo exportar CSV (sin lanzar el pipeline). Útil para
            reset de export o debug.
        force: si True, re-ejecuta aunque ya exista fila completed para el día.

    Returns:
        dict con outcome estandarizado:
            {"outcome": ..., "status": ..., "run_id": ...,
             "target_date": ..., "csv_path": ..., "exported_rows": ...}

        Outcomes posibles:
            - "completed":  todo bien (o noop_export si ya estaba completed).
            - "aborted":    lock tomado por otra instancia (aborta silencioso).
            - "failed":     excepción capturada (el registro queda failed).
    """
    engine = engine or build_engine()
    ensure_schema(engine)
    target_date = target_date or target_date_from_env()
    if isinstance(target_date, datetime):
        target_date = target_date.date()

    # ── 1. Registro en pending ANTES de hacer nada ─────────────────────
    # Si ya existe una fila completed para el día (ejecución previa exitosa),
    # el job es IDEMPOTENTE: no volvemos a exportar.
    existing = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, target_date)
    if existing is not None and not force:
        if existing["status"] == STATUS_COMPLETED:
            # Noop IDEMPOTENTE: el día ya terminó bien → no re-exportar.
            log_result(
                event="skip_duplicate",
                job=JOB_NAME_NIGHTLY_EXPORT,
                status=STATUS_COMPLETED,
                outcome="noop_export",
                target_date=str(target_date),
            )
            return {
                "outcome": "noop_export",
                "status": STATUS_COMPLETED,
                "run_id": existing.get("id"),
                "target_date": str(target_date),
                "csv_path": existing.get("csv_path"),
                "exported_rows": existing.get("exported_rows"),
            }
        if existing["status"] == STATUS_PROCESSING:
            # Lock tomado por otra instancia → abortar silenciosamente.
            log_result(
                event="aborted",
                job=JOB_NAME_NIGHTLY_EXPORT,
                status=STATUS_PROCESSING,
                outcome="aborted",
                target_date=str(target_date),
            )
            return {
                "outcome": "aborted",
                "status": STATUS_PROCESSING,
                "run_id": existing.get("id"),
                "target_date": str(target_date),
            }
        if existing["status"] == STATUS_FAILED:
            # Reintento natural del mismo día: rearmar failed → pending
            # (transición atómica; nunca rearma desde processing, así no se
            # puede robar el lock a una instancia viva).
            reset_failed_to_pending(engine, JOB_NAME_NIGHTLY_EXPORT, target_date)

    # ── 2. Asegurar fila pending ───────────────────────────────────────
    if existing is None:
        try:
            create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, target_date, status="pending")
        except Exception as exc:  # IntegrityError si otra instancia ganó la carrera
            # Otra instancia creó la fila más rápido → reintentar mark_processing.
            logger.warning("No se pudo crear job_run (posible carrera): %s", exc)

    # ── 3. Tomar el lock: pending → processing (ATÓMICO) ───────────────
    if not mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, target_date):
        log_result(
            event="aborted_lock",
            job=JOB_NAME_NIGHTLY_EXPORT,
            status=STATUS_PROCESSING,
            outcome="aborted",
            target_date=str(target_date),
        )
        return {
            "outcome": "aborted",
            "status": STATUS_PROCESSING,
            "target_date": str(target_date),
        }

    # Lock tomado → INICIO real del trabajo (log INFO normalizado).
    log_result(
        event="started",
        job=JOB_NAME_NIGHTLY_EXPORT,
        status=STATUS_PROCESSING,
        outcome="processing",
        target_date=str(target_date),
    )

    # ── 4. Trabajo real (con captura → failed) ─────────────────────────
    try:
        # 4a. Exportar CSV (backup, nunca input del pipeline)
        exported, csv_path = export_telemetry_events(engine, target_date, export_dir=export_dir)

        # 4b. Lanzar el pipeline como subprocess independiente
        if not skip_pipeline:
            run_pipeline_subprocess(target_date=target_date, command=pipeline_command)
        else:
            log_result(
                event="skip_pipeline",
                job=JOB_NAME_NIGHTLY_EXPORT,
                status=STATUS_PROCESSING,
                outcome="processing",
                target_date=str(target_date),
            )

        # 4c. Completar (LIBERA el lock)
        mark_completed(
            engine,
            JOB_NAME_NIGHTLY_EXPORT,
            target_date,
            exported_rows=exported,
            csv_path=str(csv_path),
        )
        # FIN con éxito (INFO normalizado).
        log_result(
            event="finished",
            job=JOB_NAME_NIGHTLY_EXPORT,
            status=STATUS_COMPLETED,
            outcome="completed",
            target_date=str(target_date),
            extra={"csv_path": str(csv_path), "exported_rows": str(exported)},
        )
        return {
            "outcome": "completed",
            "status": STATUS_COMPLETED,
            "target_date": str(target_date),
            "csv_path": str(csv_path),
            "exported_rows": exported,
        }
    except Exception as exc:  # noqa: BLE001 — cualquier error → failed
        error_msg = f"{type(exc).__name__}: {exc}"
        mark_failed(
            engine,
            JOB_NAME_NIGHTLY_EXPORT,
            target_date,
            error_message=error_msg,
        )
        # Cualquier excepción → estado failed (nunca processing; sin zombis).
        # La línea de log (ERROR) incluye job, estado y stack trace (exc_info).
        log_result(
            event="failed",
            job=JOB_NAME_NIGHTLY_EXPORT,
            status=STATUS_FAILED,
            outcome="failed",
            target_date=str(target_date),
            level=logging.ERROR,
            extra={"error": error_msg},
            exc_info=True,
        )
        return {
            "outcome": "failed",
            "status": STATUS_FAILED,
            "target_date": str(target_date),
            "error_message": error_msg,
        }