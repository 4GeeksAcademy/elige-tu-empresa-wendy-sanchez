"""Control de tasa para el endpoint de restablecimiento de contraseña.

Previene abusos limitando el número de solicitudes de restablecimiento
por dirección de email en una ventana de tiempo configurable.

Los datos se persisten en la tabla ``password_reset_rate_limits`` de TinyDB.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import database

logger = logging.getLogger(__name__)

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
    try:
        table = database.get_rate_limits_table()
    except Exception:
        logger.exception("Error al acceder a la tabla de rate limit para %s", email)
        return True

    window_start = _now() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    # Limpiar entradas antiguas (ventana expirada) para esta dirección.
    _clean_stale_entries(table, email, window_start)

    try:
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
    except Exception:
        logger.exception("Error al contar/insertar rate limit para %s", email)
        return True


def _clean_stale_entries(table, email: str, window_start: datetime) -> None:
    """Elimina entradas antiguas para un email, ignorando fallos de TinyDB."""
    try:
        stale_ids: list[int] = []
        for doc in table:
            if doc.get("email") == email:
                ts = doc.get("timestamp")
                if ts is None or datetime.fromisoformat(ts) < window_start:
                    stale_ids.append(doc.doc_id)
        if stale_ids:
            table.remove(doc_ids=stale_ids)
    except Exception:
        logger.exception("Error al limpiar entradas antiguas de rate limit para %s", email)