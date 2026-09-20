"""Fixtures compartidas para todos los tests de la API de autenticación.

Proporcionan:
- Un cliente de pruebas (TestClient de FastAPI) con la app real.
- Una base de datos TinyDB en memoria (no toca el archivo real).
- Usuarios semilla para los tests de login, /me, etc.
- Tokens pre-generados para tests que los necesitan.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

# Forzamos variables de entorno ANTES de importar la app para que
# database.py, security.py y audit_logger.py las lean con estos valores.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("RESET_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("RATE_LIMIT_MAX_REQUESTS", "5")
os.environ.setdefault("RATE_LIMIT_WINDOW_MINUTES", "60")
os.environ.setdefault("PASSWORD_RESET_AUDIT_ENABLED", "false")


# ────────────────────────────────────────────────────────
# Fixtures de base de datos en memoria
# ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _in_memory_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sustituye la base de datos TinyDB por una instancia en memoria.

    Esta fixture se ejecuta automáticamente en cada test, garantizando
    que ningún test use la base de datos real ni deje residuos entre tests.
    """
    # MemoryStorage es una clase de tinydb.storages que almacena todo en RAM
    db = TinyDB(storage=MemoryStorage)

    def mock_get_db() -> TinyDB:
        return db

    monkeypatch.setattr("database._db", None)
    monkeypatch.setattr("database.get_tinydb", mock_get_db)


# ────────────────────────────────────────────────────────
# Fixtures de clientes HTTP
# ────────────────────────────────────────────────────────


@pytest.fixture()
def client() -> TestClient:
    """Cliente HTTP de pruebas montado sobre la app FastAPI real."""
    # Import tardío para que las env vars estén definidas antes.
    from main import app

    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c


# ────────────────────────────────────────────────────────
# Fixtures de base de datos y tablas
# ────────────────────────────────────────────────────────


@pytest.fixture()
def users_table(client: TestClient) -> object:
    """Referencia a la tabla de usuarios (TinyDB)."""
    import database
    return database.get_users_table()


@pytest.fixture()
def profiles_table(client: TestClient) -> object:
    import database
    return database.get_profiles_table()


@pytest.fixture()
def reset_tokens_table(client: TestClient) -> object:
    import database
    return database.get_reset_tokens_table()


@pytest.fixture()
def rate_limits_table(client: TestClient) -> object:
    import database
    return database.get_rate_limits_table()


@pytest.fixture()
def audit_log_table(client: TestClient) -> object:
    import database
    return database.get_audit_log_table()


# ────────────────────────────────────────────────────────
# Fixtures de usuario semilla
# ────────────────────────────────────────────────────────


@pytest.fixture()
def seed_user(client: TestClient) -> dict:
    """Crea un usuario de prueba en la BD y devuelve sus datos.

    El usuario creado tiene:
        email = "test@healthcore.com"
        password = "securepassword123"
        is_active = True
        role = "user"
        name = "Test User"
        phone = "+1-555-0100"
        address = "123 Test St"
    """
    import user_service
    from models import Role
    from security import hash_password

    user = user_service.create_user(
        email="test@healthcore.com",
        hashed_password=hash_password("securepassword123"),
        role=Role.USER,
    )
    user_service.create_profile(
        user_id=user.id,
        name="Test User",
        phone="+1-555-0100",
        address="123 Test St",
    )

    return {
        "id": user.id,
        "email": "test@healthcore.com",
        "password": "securepassword123",
        "role": Role.USER,
    }


@pytest.fixture()
def seed_admin(client: TestClient) -> dict:
    """Crea un usuario administrador de prueba."""
    import user_service
    from models import Role
    from security import hash_password

    user = user_service.create_user(
        email="admin@healthcore.com",
        hashed_password=hash_password("adminpass456"),
        role=Role.ADMIN,
    )
    user_service.create_profile(
        user_id=user.id,
        name="Admin User",
        phone="+1-555-0200",
        address="456 Admin St",
    )

    return {
        "id": user.id,
        "email": "admin@healthcore.com",
        "password": "adminpass456",
        "role": Role.ADMIN,
    }


@pytest.fixture()
def seed_inactive_user(client: TestClient) -> dict:
    """Crea un usuario inactivo (no puede hacer login ni usar /me)."""
    import user_service
    from models import Role
    from security import hash_password

    user = user_service.create_user(
        email="inactive@healthcore.com",
        hashed_password=hash_password("inactivepass789"),
        role=Role.USER,
    )
    user_service.update_user(user.id, {"is_active": False})

    return {
        "id": user.id,
        "email": "inactive@healthcore.com",
        "password": "inactivepass789",
    }


# ────────────────────────────────────────────────────────
# Fixtures de tokens JWT
# ────────────────────────────────────────────────────────


@pytest.fixture()
def access_token(seed_user: dict) -> str:
    """Genera un token JWT de acceso válido para seed_user."""
    from security import create_access_token
    return create_access_token(subject=str(seed_user["id"]))


@pytest.fixture()
def admin_access_token(seed_admin: dict) -> str:
    """Genera un token JWT de acceso válido para seed_admin."""
    from security import create_access_token
    return create_access_token(subject=str(seed_admin["id"]))


@pytest.fixture()
def expired_access_token(seed_user: dict) -> str:
    """Genera un token JWT expirado con fecha en el pasado."""
    from datetime import datetime, timezone, timedelta
    from jose import jwt
    import os

    expire = datetime.now(timezone.utc) - timedelta(minutes=1)
    payload = {"sub": str(seed_user["id"]), "exp": expire}
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")


@pytest.fixture()
def reset_token(seed_user: dict) -> str:
    """Genera un token de restablecimiento válido y lo persiste en BD."""
    from security import create_reset_token, create_reset_token_expiry
    import database

    token = create_reset_token(user_id=seed_user["id"])
    database.get_reset_tokens_table().insert({
        "token": token,
        "user_id": seed_user["id"],
        "expires_at": create_reset_token_expiry().isoformat(),
    })
    return token


@pytest.fixture()
def expired_reset_token(seed_user: dict) -> str:
    """Genera un token de restablecimiento expirado."""
    import os
    from datetime import datetime, timezone, timedelta
    from jose import jwt

    expire = datetime.now(timezone.utc) - timedelta(minutes=1)
    payload = {
        "sub": str(seed_user["id"]),
        "type": "password_reset",
        "exp": expire,
    }
    token = jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")

    import database
    database.get_reset_tokens_table().insert({
        "token": token,
        "user_id": seed_user["id"],
        "expires_at": expire.isoformat(),
    })
    return token