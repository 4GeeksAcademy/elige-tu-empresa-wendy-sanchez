"""Router de estado de tareas asíncronas — GET /tasks/{task_id}.

Permite al cliente consultar el estado y resultado de una tarea encolada
mediante Celery. Los estados posibles son:
  - PENDING:   la tarea está en la cola, aún no la tomó ningún worker
  - STARTED:   un worker comenzó a procesarla
  - SUCCESS:   la tarea terminó correctamente (result disponible)
  - FAILURE:   la tarea falló tras agotar reintentos (error disponible)

Uso desde el cliente:
  1. POST /api/incidents/analyze  → 202 {"task_id": "...", "status": "PENDING"}
  2. GET  /tasks/{task_id}        → {"status": "success", "result": {...}}
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from services.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
def get_task_status(task_id: str):
    """Consulta el estado actual de una tarea asíncrona.

    Args:
        task_id: ID de la tarea devuelto por el endpoint que la encoló.

    Returns:
        Dict con:
        - status: pending | started | success | failure
        - result: resultado (si SUCCESS)
        - error: mensaje de error (si FAILURE)
        - task_id: el identificador de la tarea
    """
    async_result = celery_app.AsyncResult(task_id)

    # Normalizar a minúsculas como espera el cliente
    state = async_result.state.lower()

    response = {
        "task_id": task_id,
        "status": state,
    }

    if state == "pending":
        response["info"] = "La tarea está en la cola esperando ser procesada."

    elif state == "started":
        response["info"] = "La tarea está siendo procesada."

    elif state == "success":
        response["result"] = async_result.result

    elif state == "failure":
        # Extraer información del error de forma segura
        result = async_result.result
        if isinstance(result, Exception):
            response["error"] = str(result)
        elif isinstance(result, dict):
            response["error"] = result.get("error", str(result))
        else:
            response["error"] = str(result) if result else "Unknown error"

        # Si la tarea está en DLQ, indicarlo
        from pathlib import Path
        from tinydb import TinyDB
        from services.celery_app import DLQ_DB_PATH

        db_path = Path(DLQ_DB_PATH)
        if db_path.exists():
            db = TinyDB(str(db_path))
            dlq_entries = db.table("task_dlq").search(
                lambda doc: doc.get("task_id") == task_id
            )
            if dlq_entries:
                response["dlq"] = dlq_entries[-1]  # última entrada
            db.close()

    return response