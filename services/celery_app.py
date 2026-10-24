"""
Módulo Celery — Configuración y tareas asíncronas.

Arquitectura:
  ┌────────────┐     ┌──────────┐     ┌──────────┐
  │  FastAPI   │────→│  Redis   │────→│  Worker  │
  │ (Producer) │     │ (Broker) │     │(Consumer)│
  └────────────┘     └──────────┘     └──────────┘

La API (productor) encola tareas ligeras (solo metadatos). El worker
(consumidor) las ejecuta en un proceso separado. Redis actúa como broker
y result backend. Si una tarea falla 3 veces, pasa a Dead Letter Queue.

Uso:
    # Terminal 1: Worker
    celery -A services.celery_app worker --loglevel=info

    # Terminal 2: Monitor (opcional)
    celery -A services.celery_app flower --port=5555

    # O via Docker Compose (recomendado en desarrollo):
    docker compose up redis flower
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from celery import Celery, Task
from celery.signals import task_failure, task_revoked, task_retry, task_success
from celery.utils.log import get_task_logger

# ── Logger ─────────────────────────────────────────────────────────────
logger = logging.getLogger("celery.task")

# ── Configuración desde entorno ────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Creación de la instancia Celery ────────────────────────────────────
# Usamos Redis como broker (cola de mensajes) y como result backend
# (almacenamiento de resultados de tareas).
celery_app = Celery(
    "healthcore",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["services.celery_app"],  # self-include para discovery de tareas
)

# ── Configuración por defecto ──────────────────────────────────────────
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # ── Reintentos automáticos ─────────────────────────────────────────
    task_acks_late=True,           # El worker confirma la tarea solo cuando termina
    task_reject_on_worker_lost=True,  # Si el worker se cae, la tarea va a otra cola
    task_track_started=True,       # Permite ver estado "started"
    task_soft_time_limit=300,      # 5 minutos soft limit
    task_time_limit=330,           # 5:30 hard limit
    result_expires=3600 * 24 * 7,  # Resultados expiran a los 7 días
    # ── Colas ──────────────────────────────────────────────────────────
    task_default_queue="healthcore.default",
    task_queues={
        "healthcore.default": {
            "exchange": "healthcore",
            "routing_key": "healthcore.default",
        },
        "healthcore.dlq": {
            "exchange": "healthcore.dlq",
            "routing_key": "healthcore.dlq",
        },
    },
)


# ── Dead Letter Queue (DLQ) ───────────────────────────────────────────
# Base de datos TinyDB para registrar tareas fallidas que superaron
# max_retries. Se persiste en data/process/task_dlq.json

DLQ_DB_PATH = os.getenv(
    "DLQ_DB_PATH",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "data",
        "process",
        "task_dlq.json",
    ),
)


def _record_dlq(
    task_id: str,
    attempt: int,
    error_message: str,
    exc_type: str = "unknown",
    task_name: str | None = None,
    args: list | None = None,
    kwargs: dict | None = None,
) -> None:
    """Registra una tarea en la Dead Letter Queue cuando supera max_retries.

    Persiste en TinyDB con:
    - task_id: ID único de la tarea Celery
    - attempt: número de intento en el que falló definitivamente
    - error: mensaje de error del último fallo
    - exc_type: tipo de excepción
    - task_name: nombre de la tarea que falló
    - timestamp: momento del registro (UTC ISO)
    """
    from tinydb import TinyDB

    db_path = Path(DLQ_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = TinyDB(str(db_path))
    table = db.table("task_dlq")
    table.insert(
        {
            "task_id": task_id,
            "task_name": task_name or "unknown",
            "attempt": attempt,
            "error": error_message,
            "exc_type": exc_type,
            "args": json.dumps(args or []),
            "kwargs": json.dumps(kwargs or {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    db.close()
    logger.error(
        "DLQ: task_id=%s attempt=%d error=%s",
        task_id,
        attempt,
        error_message,
    )


# ── Base Task personalizada con DLQ automática ─────────────────────────


class HealthCoreTask(Task):
    """Task base que captura fallos tras max_retries y los envía a DLQ."""

    abstract = True
    max_retries = 3
    default_retry_delay = 10  # segundos iniciales (backoff exponencial)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Se ejecuta cuando la tarea falla definitivamente (tras agotar reintentos).

        Registra el fallo en la DLQ y luego delega en el comportamiento
        por defecto de Celery.
        """
        _record_dlq(
            task_id=task_id,
            attempt=self.max_retries,
            error_message=str(exc),
            exc_type=type(exc).__name__,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)


# ── Tareas ─────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    base=HealthCoreTask,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,       # backoff exponencial: 10s, 20s, 40s
    retry_backoff_max=300,    # máximo 5 minutos entre reintentos
    retry_jitter=True,        # añade algo de ruido aleatorio
    name="analyze_incidents_csv",
    soft_time_limit=300,
    time_limit=330,
)
def analyze_incidents_csv(self, csv_content: str, filename: str) -> dict[str, Any]:
    """Analiza un CSV de incidencias de forma asíncrona.

    Esta es la operación pesada que originalmente se ejecutaba de forma
    síncrona en POST /api/incidents/analyze. Al moverla a Celery:
    - La API responde 202 Accepted inmediatamente con un task_id.
    - El worker procesa el CSV en segundo plano.
    - El cliente consulta GET /tasks/{task_id} para obtener el resultado.

    Args:
        csv_content: Contenido del CSV en UTF-8 (texto plano).
        filename: Nombre original del fichero para trazabilidad.

    Returns:
        Dict con el reporte de análisis (mismo formato que analyze_csv_text).

    Raises:
        ValueError: Si el CSV está vacío o tiene formato inválido.
        Exception: Cualquier error durante el análisis (autoretry_for lo captura).
    """
    from services.api.incidents_analysis import analyze_csv_text, report_to_csv_text

    # Logger específico de la tarea con trazabilidad completa
    task_logger = get_task_logger(__name__)
    task_logger.info(
        "Task STARTED: task_id=%s filename=%s csv_size=%d",
        self.request.id,
        filename,
        len(csv_content),
    )

    start_time = time.monotonic()

    if not csv_content or csv_content.strip() == "":
        raise ValueError("El fichero CSV está vacío")

    report = analyze_csv_text(csv_content)
    csv_export = report_to_csv_text(report)

    duration = time.monotonic() - start_time

    result = {
        "source_file": filename,
        "report": report,
        "csv_export": csv_export,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(duration, 3),
    }

    task_logger.info(
        "Task SUCCESS: task_id=%s filename=%s duration=%.3fs total=%d valid=%d invalid=%d",
        self.request.id,
        filename,
        duration,
        report["total"],
        report["valid"],
        report["invalid"],
    )

    return result


# ── Señales para logging con duración, intento y estado ────────────────


@task_success.connect
def log_task_success(sender=None, **kwargs):
    logger.info("Task succeeded: %s", sender)


@task_failure.connect
def log_task_failure(sender=None, task_id=None, exception=None, einfo=None, **kwargs):
    """Registra el fallo con el mensaje de error completo."""
    error_msg = str(exception)
    traceback_str = str(einfo) if einfo else ""
    logger.warning(
        "Task FAILED: task_id=%s error=%s\n%s",
        task_id,
        error_msg,
        traceback_str[:500] if traceback_str else "(no traceback)",
    )


@task_retry.connect
def log_task_retry(sender=None, request=None, reason=None, einfo=None, **kwargs):
    """Registra cada reintento con número de intento, razón y duración acumulada."""
    error_msg = str(reason) if reason else "unknown"
    traceback_str = str(einfo) if einfo else ""
    _task_id = request.id if request else "unknown"
    _retries = int(request.retries) + 1 if request and hasattr(request, "retries") else "?"
    _max = getattr(sender, "max_retries", "?")
    _traceback = traceback_str[:500] if traceback_str else "(no traceback)"
    # Preformateado completo para evitar que el formateador de Celery
    # vuelva a interpretar placeholders y falle por tipo de dato incorrecto.
    msg = (
        f"Task RETRY: task_id={_task_id} "
        f"attempt={_retries}/{_max} "
        f"reason={error_msg}\n{_traceback}"
    )
    logger.info(msg)


@task_revoked.connect
def log_task_revoked(sender=None, request=None, **kwargs):
    logger.info(
        "Task REVOKED: task_id=%s expire=%s",
        request.id if request else "unknown",
        request.expires if request and hasattr(request, "expires") else "N/A",
    )


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Configura logging de heartbeat del worker para observabilidad."""
    logger.info(
        "Celery worker configured: broker=%s backend=%s queues=%s",
        sender.conf.broker_url,
        sender.conf.result_backend,
        list(sender.conf.task_queues.keys()) if sender.conf.task_queues else "default",
    )


# ── Punto de entrada para lanzar worker desde la terminal ─────────────

if __name__ == "__main__":
    celery_app.start()