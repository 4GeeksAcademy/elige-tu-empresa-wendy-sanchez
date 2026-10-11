"""Seed a default admin user in TinyDB for the backoffice login.

Works without importing services/api/models.py (which crashes on Python 3.14
due to SQLModel incompatibility).

Usage:
    python services/telemetry/seed_auth_users.py
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from passlib.hash import bcrypt
from tinydb import TinyDB, Query

# TinyDB path (same as database.py)
_TINYDB_PATH = Path(__file__).resolve().parents[2] / "data" / "process" / "suppliers_db.json"
_USERS_TABLE = "users"
_PROFILES_TABLE = "profiles"

_ADMIN_EMAIL = "admin@healthcore.com"
_ADMIN_PASS = "adminpass456"

_TEST_EMAIL = "test@healthcore.com"
_TEST_PASS = "securepassword123"


def _get_db() -> TinyDB:
    os.makedirs(_TINYDB_PATH.parent, exist_ok=True)
    return TinyDB(str(_TINYDB_PATH), indent=2, ensure_ascii=False)


def seed_user(email: str, password: str, role: str, name: str, phone: str) -> bool:
    db = _get_db()
    users = db.table(_USERS_TABLE)
    profiles = db.table(_PROFILES_TABLE)

    # Check if user already exists
    existing = users.get(Query().email == email)
    if existing:
        print(f"✓ Usuario {email} ya existe (id={existing.doc_id}).")
        return True

    # Create user
    hashed = bcrypt.hash(password)
    now = datetime.now(timezone.utc).isoformat()
    user_doc_id = users.insert({
        "email": email,
        "hashed_password": hashed,
        "is_active": True,
        "role": role,
        "created_at": now,
    })

    # Create profile
    profiles.insert({
        "user_id": user_doc_id,
        "name": name,
        "phone": phone,
        "address": None,
    })

    print(f"✓ Usuario creado: {email} / {password}  (id={user_doc_id}, role={role})")
    return True


def main():
    print("=== Seed de usuarios para backoffice ===\n")
    print(f"Base de datos: {_TINYDB_PATH}\n")
    seed_user(_ADMIN_EMAIL, _ADMIN_PASS, "admin", "Admin HealthCore", "+1-555-0000")
    seed_user(_TEST_EMAIL, _TEST_PASS, "user", "Test User", "+1-555-0100")
    print("\n¡Listo! Los usuarios están disponibles en TinyDB.")
    print("\nCredenciales:")
    print(f"  Admin: {_ADMIN_EMAIL} / {_ADMIN_PASS}")
    print(f"  Test:  {_TEST_EMAIL} / {_TEST_PASS}")


if __name__ == "__main__":
    main()