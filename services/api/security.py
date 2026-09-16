"""Autenticación JWT stateless: hashing de contraseñas, emisión y validación de tokens."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt
from tinydb import Query as TinyQuery

import database
import user_service
from models import User

load_dotenv()

logger = logging.getLogger(__name__)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30"))

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.verify(password, hashed_password)


def _get_secret_key() -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY no está configurada. Define esta variable en el fichero .env"
        )
    return JWT_SECRET_KEY


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, _get_secret_key(), algorithm=JWT_ALGORITHM)


def get_current_user(token: str | None = Depends(_oauth2_scheme)) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o ausentes",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise unauthorized

    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[JWT_ALGORITHM])
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            logger.warning("Token JWT válido pero sin 'sub': %s...", token[:20])
            raise unauthorized
        user_id = int(user_id_raw)
    except JWTError:
        logger.warning("Token JWT inválido rechazado (posible ataque): %s...", token[:20])
        raise unauthorized from None
    except ValueError:
        logger.warning("'sub' no entero en token JWT: %s...", token[:20])
        raise unauthorized from None

    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


# ──────────────────────────────────────────────
# Tokens de restablecimiento de contraseña
# ──────────────────────────────────────────────

# Código de propósito para separar tokens de acceso y de restablecimiento.
# Evita que un token de acceso JWT pueda usarse como token de reset y viceversa.
_RESET_TOKEN_TYPE = "password_reset"


def create_reset_token(user_id: int) -> str:
    """Genera un token JWT firmado de corta duración para restablecer la contraseña."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "type": _RESET_TOKEN_TYPE, "exp": expire}
    return jwt.encode(payload, _get_secret_key(), algorithm=JWT_ALGORITHM)


def create_reset_token_expiry() -> datetime:
    """Momento UTC en el que un token de restablecimiento deja de ser válido."""
    return datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)


def validate_reset_token(token: str) -> int:
    """Valida un token de restablecimiento (firma + expiración) y devuelve el user_id.

    Lanza HTTPException 400 si el token es inválido, ha expirado o ya se usó.
    """
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="El enlace de restablecimiento no es válido o ha expirado.",
    )

    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[JWT_ALGORITHM])
    except JWTError:
        logger.warning("Token de restablecimiento inválido (posible ataque): %s...", token[:20])
        raise invalid from None

    if payload.get("type") != _RESET_TOKEN_TYPE:
        logger.warning(
            "Token con type incorrecto en restablecimiento: %s",
            payload.get("type"),
        )
        raise invalid

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        logger.warning("Token de restablecimiento sin 'sub': %s...", token[:20])
        raise invalid
    try:
        user_id = int(user_id_raw)
    except ValueError:
        logger.warning("'sub' no entero en token de restablecimiento: %s...", token[:20])
        raise invalid from None

    # Comprobar que el token no se haya utilizado ya (invalidate-on-use).
    token_exists = database.get_reset_tokens_table().contains(
        TinyQuery()["token"] == token
    )
    if not token_exists:
        raise invalid

    return user_id


def invalidate_reset_token(token: str) -> None:
    """Invalida un token de restablecimiento tras su uso para que no pueda reutilizarse."""
    database.get_reset_tokens_table().remove(
        TinyQuery()["token"] == token
    )
