"""Control de tasa para el endpoint de restablecimiento de contraseña.

Previene abusos limitando el número de solicitudes de restablecimiento
por dirección de email en una ventana de tiempo configurable.

Los datos se persisten en la tabla ``password_reset_rate_limits`` de TinyDB.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import database

# Número máximo de solicitudes de restablecimiento permitidas por email
# en la ventana de tiempo configurada.
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5"))
RATE_LIMIT_WINDOW_MINUTES = int(os.getenv("RATE_LIMIT_WINDOW_MINUTES", "60"))


def _now() -> datetime:
    """Devuelve el timestamp UTC actual."""
    return datetime.now(timezone.utc)


def check_rate_limit(email: str) -> bool:
    """Verifica si el email ha superado el límite de solicitudes en la ventana.

    Devuelve ``True`` si la solicitud está dentro del límite (permitida),
    ``False`` si se ha superado el límite (denegada).
    """
    table = database.get_rate_limits_table()
    window_start = _now() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    # Limpiar entradas antiguas (ventana expirada) para esta dirección.
    # Usamos doc_id para eliminar registros concretos de TinyDB.
    stale_ids: list[int] = []
    for doc in table:
        if doc.get("email") == email:
            ts = doc.get("timestamp")
            if ts is None or datetime.fromisoformat(ts) < window_start:
                stale_ids.append(doc.doc_id)

    for doc_id in stale_ids:
        table.remove(doc_ids=[doc_id])

    # Contar solicitudes activas (dentro de la ventana) para este email.
    active_count = table.count(
        lambda d: d.get("email") == email
        and datetime.fromisoformat(d["timestamp"]) >= window_start
    )

    if active_count >= RATE_LIMIT_MAX_REQUESTS:
        return False

    # Registrar la nueva solicitud.
    table.insert({"email": email, "timestamp": _now().isoformat()})
    return True