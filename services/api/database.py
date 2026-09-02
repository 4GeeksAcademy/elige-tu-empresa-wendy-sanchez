from __future__ import annotations

import os
from pathlib import Path

from tinydb import TinyDB
from tinydb.table import Table

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "process" / "suppliers_db.json"
SUPPLIERS_TABLE = "suppliers"

_db: TinyDB | None = None


def get_db_path() -> Path:
    raw_path = os.getenv("HEALTHCORE_DB_PATH")
    return Path(raw_path).expanduser().resolve() if raw_path else DEFAULT_DB_PATH


def get_db() -> TinyDB:
    global _db
    if _db is None:
        path = get_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _db = TinyDB(path, indent=2, ensure_ascii=False)
    return _db


def get_suppliers_table() -> Table:
    return get_db().table(SUPPLIERS_TABLE)


def close_db() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None
