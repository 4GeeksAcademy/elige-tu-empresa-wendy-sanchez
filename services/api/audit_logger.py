"""Registro de auditoría de eventos de restablecimiento de contraseña.

Cada evento relevante del flujo de recuperación de contraseña se persiste
en la tabla ``password_reset_audit`` de TinyDB con timestamp UTC e
información adicional (email, dirección IP, resultado, metadata).

Solo se registran eventos cuando la funcionalidad está habilitada
(``PASSWORD_RESET_AUDIT_ENABLED``, activo por defecto).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import database

AUDIT_ENABLED = os.getenv("PASSWORD_RESET_AUDIT_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
    "on",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_reset_event(
    *,
    event: str,
    email: str | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
    status: str = "info",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persiste un evento de auditoría del flujo de restablecimiento.

    Parámetros:
        event: Identificador del evento (p.ej. ``forgot_password_requested``).
        email: Dirección de email asociada (si aplica).
        user_id: ID del usuario autenticado (si aplica).
        ip_address: Dirección IP de origen de la solicitud, si está disponible.
        status: Nivel del evento (``info``, ``success``, ``warning``, ``error``).
        metadata: Dict opcional con contexto adicional del evento.
    """
    if not AUDIT_ENABLED:
        return

    record = {
        "timestamp": _now(),
        "event": event,
        "email": email,
        "user_id": user_id,
        "ip_address": ip_address,
        "status": status,
        "metadata": metadata or {},
    }
    # Eliminamos claves con valor None para mantener el registro limpio.
    database.get_audit_log_table().insert({k: v for k, v in record.items() if v is not None})