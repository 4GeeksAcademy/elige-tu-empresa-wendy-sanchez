"""Fixtures compartidos para los tests de la Incidents API."""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

# ── Monkey-patch la DB ANTES de importar los módulos de la app ──────────
import database as db_module

original_get_path = db_module.get_db_path

# Singleton en memoria — misma instancia para la app y los tests
_memory_db: TinyDB | None = None


def _in_memory_db() -> TinyDB:
    global _memory_db
    if _memory_db is None:
        _memory_db = TinyDB(storage=MemoryStorage)
    return _memory_db


db_module.get_db = _in_memory_db


@pytest.fixture(autouse=True)
def auto_clean_db() -> Generator[None, None, None]:
    """Limpia la tabla de incidents entre tests para evitar acoplamiento."""
    yield
    table = db_module.get_incidents_table()
    table.truncate()


@pytest.fixture
def db() -> TinyDB:
    """Devuelve la instancia TinyDB en memoria (ya monkey-patched)."""
    return db_module.get_db()


@pytest.fixture
def incidents_table():
    """Devuelve la tabla de incidents."""
    return db_module.get_incidents_table()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Cliente de prueba contra la FastAPI real (sin mock)."""
    from main import app

    with TestClient(app) as c:
        yield c