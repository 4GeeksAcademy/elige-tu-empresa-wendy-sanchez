"""Autenticación JWT para el servicio de reporting.

Sigue las mismas convenciones que ``services/api/security.py``:
- Token JWT en cabecera ``Authorization: Bearer <token>``.
- Validación con la misma ``JWT_SECRET_KEY`` y ``JWT_ALGORITHM``.
- Devuelve el ``user_id`` (subject) contenido en el token.
- Loguea intentos fallidos con pseudónimo.

No replica la carga completa de ``get_current_user`` de services/api/ porque
el reporting no necesita acceder a la base de datos de usuarios ni a perfiles.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

# ── Cargar .env desde services/api/ (comparte configuración) ──────────
_API_DIR = os.path.join(os.path.dirname(__file__), "..", "api")
load_dotenv(os.path.join(_API_DIR, ".env"))

logger = logging.getLogger(__name__)

# ── Configuración (lee las mismas variables que el API principal) ─────
JWT_SECRET_KEY: Optional[str] = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",  # mismo path que el API principal
    auto_error=False,
)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o ausentes",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user_id(
    token: Optional[str] = Depends(_oauth2_scheme),
) -> int:
    """Valida un token JWT y devuelve el ``user_id`` (subject).

    Es el equivalento ligero de ``security.get_current_user()`` del API
    principal: verifica la firma, expiración y formato, pero sin consultar
    la base de datos de usuarios ni perfiles.

    Raises:
        HTTPException 401 si el token falta, expiró o es inválido.
    """
    if token is None:
        logger.warning("Intento de acceso sin token")
        raise UNAUTHORIZED

    if not JWT_SECRET_KEY:
        logger.critical(
            "JWT_SECRET_KEY no configurada. "
            "Define esta variable en services/api/.env"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de configuración del servicio",
        )

    try:
        payload = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
    except ExpiredSignatureError:
        logger.warning("Token JWT expirado rechazado")
        raise UNAUTHORIZED from None
    except JWTError:
        logger.warning("Token JWT con firma inválida rechazado")
        raise UNAUTHORIZED from None

    user_id_raw: object = payload.get("sub")
    if user_id_raw is None:
        logger.warning("Token JWT sin campo 'sub'")
        raise UNAUTHORIZED

    try:
        user_id = int(user_id_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        logger.warning("Token JWT con 'sub' no numérico: %s", type(user_id_raw).__name__)
        raise UNAUTHORIZED

    exp = payload.get("exp")
    if exp is not None:
        try:
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
            if exp_dt < datetime.now(timezone.utc):
                logger.warning("Token JWT expirado (timestamp) rechazado")
                raise UNAUTHORIZED
        except (OSError, OverflowError, ValueError):
            logger.warning("Token JWT con 'exp' inválido")
            raise UNAUTHORIZED

    logger.info(
        "Token JWT válido para user_id=%s",
        user_id,
    )
    return user_id