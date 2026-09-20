from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator, Generator

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB
from tinydb.table import Table

load_dotenv()

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "process" / "suppliers_db.json"
SUPPLIERS_TABLE = "suppliers"
USERS_TABLE = "users"
PROFILES_TABLE = "profiles"
RESET_TOKENS_TABLE = "reset_tokens"
RATE_LIMITS_TABLE = "password_reset_rate_limits"
AUDIT_LOG_TABLE = "password_reset_audit"

_db: TinyDB | None = None

# ── SQLModel / Supabase engine ───────────────────────────────────────

DATABASE_URL: str | None = os.getenv("DATABASE_URL")

_engine = None


def get_sql_engine():
    """Lazy-init the SQLModel engine pointing to Supabase (PostgreSQL)."""
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL no está configurada. "
                "Define esta variable en el fichero .env"
            )
        _engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    return _engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLModel session per request."""
    engine = get_sql_engine()
    with Session(engine) as session:
        yield session


def init_supabase_schema() -> None:
    """Create all tables in Supabase on application startup."""
    engine = get_sql_engine()
    SQLModel.metadata.create_all(engine)


# ── TinyDB existing ──────────────────────────────────────────────────


def get_db_path() -> Path:
    raw_path = os.getenv("HEALTHCORE_DB_PATH")
    return Path(raw_path).expanduser().resolve() if raw_path else DEFAULT_DB_PATH


def get_tinydb() -> TinyDB:
    global _db
    if _db is None:
        path = get_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _db = TinyDB(path, indent=2, ensure_ascii=False)
    return _db


def get_suppliers_table() -> Table:
    return get_tinydb().table(SUPPLIERS_TABLE)


def get_users_table() -> Table:
    return get_tinydb().table(USERS_TABLE)


def get_profiles_table() -> Table:
    return get_tinydb().table(PROFILES_TABLE)


def get_reset_tokens_table() -> Table:
    return get_tinydb().table(RESET_TOKENS_TABLE)


def get_rate_limits_table() -> Table:
    """Tabla para control de tasa: impide abusos en /forgot-password por email."""
    return get_tinydb().table(RATE_LIMITS_TABLE)


def get_audit_log_table() -> Table:
    """Registro de auditoría de eventos de restablecimiento de contraseña."""
    return get_tinydb().table(AUDIT_LOG_TABLE)


def close_db() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None
