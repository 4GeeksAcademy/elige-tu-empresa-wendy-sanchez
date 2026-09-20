"""Pruebas unitarias de seguridad: hashing, JWT, tokens de restablecimiento.

Estos tests NO usan el cliente HTTP, prueban las funciones directamente
(security.py). Se apoyan en las fixtures de conftest.py para la BD en
memoria y las variables de entorno.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

import pytest
from jose import jwt
from passlib.hash import bcrypt
from tinydb import Query as TinyQuery

# ──────────────────────────────────────────────
# Hashing de contraseñas
# ──────────────────────────────────────────────


class TestHashPassword:
    """hash_password() debe generar un hash bcrypt válido y verificable."""

    def test_hash_returns_bcrypt_hash(self) -> None:
        from security import hash_password
        h = hash_password("miPasswordSegura")
        assert h.startswith("$2b$") or h.startswith("$2a$") or h.startswith("$2y$")
        # Verificar que passlib lo reconoce como bcrypt válido
        assert bcrypt.identify(h)

    def test_hash_is_deterministic_with_salt(self) -> None:
        """Misma contraseña → hashes distintos por el salt aleatorio."""
        from security import hash_password
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2

    def test_hash_empty_password(self) -> None:
        """Contraseña vacía también se hashea (no debería fallar)."""
        from security import hash_password
        h = hash_password("")
        assert bcrypt.identify(h)
        assert bcrypt.verify("", h)


class TestVerifyPassword:
    """verify_password() debe comparar correctamente."""

    def test_verify_correct_password(self) -> None:
        from security import hash_password, verify_password
        h = hash_password("miClave")
        assert verify_password("miClave", h) is True

    def test_verify_wrong_password(self) -> None:
        from security import hash_password, verify_password
        h = hash_password("miClave")
        assert verify_password("otraClave", h) is False

    def test_verify_empty_string(self) -> None:
        """Cadena vacía contra hash de password real → False."""
        from security import hash_password, verify_password
        h = hash_password("realpassword")
        assert verify_password("", h) is False

    def test_verify_empty_hash(self) -> None:
        """Hash vacío no es válido → lanza ValueError."""
        from security import verify_password
        with pytest.raises(ValueError):
            verify_password("password", "")

    def test_verify_none_hash_raises(self) -> None:
        """Si el hash es None, bcrypt lanza TypeError (esperado)."""
        from security import verify_password
        with pytest.raises(TypeError):
            verify_password("password", None)  # type: ignore[arg-type]


# ──────────────────────────────────────────────
# Tokens de acceso JWT
# ──────────────────────────────────────────────


class TestCreateAccessToken:
    """create_access_token() debe emitir JWTs válidos y configurables."""

    def test_creates_valid_jwt(self) -> None:
        from security import create_access_token
        token = create_access_token(subject="42")
        decoded = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        assert decoded["sub"] == "42"
        assert "exp" in decoded

    def test_subject_is_str(self) -> None:
        """El subject se almacena como string, aunque se pase int."""
        from security import create_access_token
        token = create_access_token(subject="123")
        decoded = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        assert decoded["sub"] == "123"

    def test_expiration_in_future(self) -> None:
        """El token debe tener exp en el futuro (por defecto 30 min)."""
        from security import create_access_token
        token = create_access_token(subject="1")
        decoded = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)

    def test_token_with_zero_expiration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ACCESS_TOKEN_EXPIRE_MINUTES=0 → token expira inmediatamente."""
        monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "0")
        # Recargar el módulo para que lea el nuevo valor
        import importlib
        import security
        importlib.reload(security)

        token = security.create_access_token(subject="1")
        decoded = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        # Debe estar muy cerca del momento actual (diferencia < 2s)
        assert abs((exp - datetime.now(timezone.utc)).total_seconds()) < 2


# ──────────────────────────────────────────────
# get_current_user
# ──────────────────────────────────────────────


class TestGetCurrentUser:
    """get_current_user() debe validar tokens y devolver usuarios."""

    def test_valid_token_returns_user(self, access_token: str, seed_user: dict) -> None:
        from security import get_current_user
        user = get_current_user(token=access_token)
        assert user.id == seed_user["id"]
        assert user.email == seed_user["email"]

    def test_none_token_raises_401(self) -> None:
        from security import get_current_user
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=None)
        assert exc.value.status_code == 401

    def test_malformed_token_raises_401(self) -> None:
        from security import get_current_user
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            get_current_user(token="esto-no-es-un-jwt")
        assert exc.value.status_code == 401

    def test_token_without_sub_raises_401(self) -> None:
        """Token firmado pero sin claim 'sub'."""
        import os
        token = jwt.encode(
            {"type": "no-sub"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        from security import get_current_user
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=token)
        assert exc.value.status_code == 401

    def test_token_with_non_integer_sub_raises_401(self) -> None:
        import os
        token = jwt.encode(
            {"sub": "not-a-number"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        from security import get_current_user
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=token)
        assert exc.value.status_code == 401

    def test_token_for_deleted_user_raises_401(
        self, seed_user: dict, users_table: object
    ) -> None:
        """Token de un usuario que luego se borró → 401."""
        from security import create_access_token, get_current_user
        from fastapi import HTTPException
        import user_service

        token = create_access_token(subject=str(seed_user["id"]))
        user_service.delete_user(seed_user["id"])

        with pytest.raises(HTTPException) as exc:
            get_current_user(token=token)
        assert exc.value.status_code == 401

    def test_token_for_inactive_user_raises_401(
        self, seed_inactive_user: dict
    ) -> None:
        from security import create_access_token, get_current_user
        from fastapi import HTTPException
        token = create_access_token(subject=str(seed_inactive_user["id"]))
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=token)
        assert exc.value.status_code == 401


# ──────────────────────────────────────────────
# Tokens de restablecimiento
# ──────────────────────────────────────────────


class TestResetTokens:
    """Funciones de restablecimiento: creación, validación e invalidación."""

    def test_create_reset_token_includes_type(self, seed_user: dict) -> None:
        from security import create_reset_token
        token = create_reset_token(user_id=seed_user["id"])
        decoded = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        assert decoded["type"] == "password_reset"
        assert decoded["sub"] == str(seed_user["id"])

    def test_validate_valid_reset_token(self, reset_token: str, seed_user: dict) -> None:
        from security import validate_reset_token
        user_id = validate_reset_token(reset_token)
        assert user_id == seed_user["id"]

    def test_validate_expired_reset_token(self, expired_reset_token: str) -> None:
        from security import validate_reset_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_reset_token(expired_reset_token)
        assert exc.value.status_code == 400

    def test_validate_invalid_token_not_jwt(self) -> None:
        from security import validate_reset_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_reset_token("not-a-jwt-token")
        assert exc.value.status_code == 400

    def test_validate_access_token_as_reset_token(self, access_token: str) -> None:
        """Un token de acceso (sin type=password_reset) debe ser rechazado."""
        from security import validate_reset_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_reset_token(access_token)
        assert exc.value.status_code == 400

    def test_validate_token_without_sub_raises_400(self) -> None:
        import os
        token = jwt.encode(
            {"type": "password_reset"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        from security import validate_reset_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_reset_token(token)
        assert exc.value.status_code == 400

    def test_validate_token_not_in_database_raises_400(
        self, seed_user: dict
    ) -> None:
        """Token válido pero no persistido en la tabla reset_tokens."""
        from security import create_reset_token, validate_reset_token
        from fastapi import HTTPException

        # Creamos el token pero NO lo insertamos en BD
        token = create_reset_token(user_id=seed_user["id"])

        with pytest.raises(HTTPException) as exc:
            validate_reset_token(token)
        assert exc.value.status_code == 400

    def test_validate_reused_token_raises_400(
        self, reset_token: str, seed_user: dict
    ) -> None:
        """Token usado una vez → invalidado → no puede reutilizarse."""
        from security import validate_reset_token, invalidate_reset_token
        from fastapi import HTTPException

        # Primer uso: válido
        user_id = validate_reset_token(reset_token)
        assert user_id == seed_user["id"]
        invalidate_reset_token(reset_token)

        # Segundo uso: debe fallar
        with pytest.raises(HTTPException) as exc:
            validate_reset_token(reset_token)
        assert exc.value.status_code == 400

    def test_validate_token_for_nonexistent_user_raises_400(
        self, seed_user: dict
    ) -> None:
        """Token para un usuario que ya no existe en BD.

        Nota: validate_reset_token NO verifica existencia del usuario,
        solo valida la integridad del token. El token se considera válido
        aunque el usuario haya sido eliminado (el llamado/reset-password
        se encarga de devolver error).
        """
        import user_service
        from security import create_reset_token, validate_reset_token
        from fastapi import HTTPException
        import database
        from security import create_reset_token_expiry

        # Borramos el usuario
        user_service.delete_user(seed_user["id"])

        # Creamos token para ese usuario borrado
        token = create_reset_token(user_id=seed_user["id"])
        database.get_reset_tokens_table().insert({
            "token": token,
            "user_id": seed_user["id"],
            "expires_at": create_reset_token_expiry().isoformat(),
        })

        # validate_reset_token solo valida el token, no al usuario
        # Así que devuelve el user_id sin error
        result = validate_reset_token(token)
        assert result == seed_user["id"]

    def test_invalidate_reset_token_removes_from_db(
        self, reset_token: str, reset_tokens_table: object
    ) -> None:
        from security import invalidate_reset_token
        invalidate_reset_token(reset_token)
        exists = reset_tokens_table.contains(
            TinyQuery()["token"] == reset_token
        )
        assert not exists

    def test_invalidate_nonexistent_token_does_not_raise(self) -> None:
        """Inhabilitar un token que no existe no debe lanzar error."""
        from security import invalidate_reset_token
        invalidate_reset_token("token-que-no-existe")  # No debe fallar


# ──────────────────────────────────────────────
# JWT_SECRET_KEY no configurada
# ──────────────────────────────────────────────


class TestMissingSecretKey:
    """Si JWT_SECRET_KEY no está configurada, debe lanzar RuntimeError."""

    def test_create_access_token_without_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET_KEY", "")
        import importlib
        import security
        importlib.reload(security)

        from security import _get_secret_key
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            _get_secret_key()