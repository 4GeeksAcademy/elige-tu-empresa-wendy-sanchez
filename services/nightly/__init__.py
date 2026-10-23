"""Servicio de orquestación nocturna (proceso de segundo plano).

Lógica de estado y control de ejecuciones del script nocturno de exportación
de telemetría. Independiente de la API FastAPI: corre como proceso aparte en
cron (o scheduler equivalente) y escribe únicamente en la tabla ``job_runs``.

Módulos:
- ``services.job_runner`` — CONTROL DE ESTADO de ``job_runs`` (migración
  idempotente, máquina de estados pending → processing → completed|failed,
  lock vía estado, helpers ``has_processing_lock`` / ``has_completed_for_date``,
  y logging normalizado ``log_result`` sobre el logger ``healthcore.nightly``).
  Vive en ``services/`` (no dentro de este paquete) por ser la capa de servicios.
- ``services.nightly.nightly_service`` — orquestación (export CSV +
  subprocess del pipeline, logs INFO/ERROR del job).
"""

from services.nightly.nightly_service import run_nightly

__all__ = ["run_nightly"]
__version__ = "1.0.0"