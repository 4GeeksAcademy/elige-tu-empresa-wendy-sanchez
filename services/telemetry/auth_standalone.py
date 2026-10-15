"""Auth utilities for the standalone telemetry server.

Self-contained: does NOT import from services/api/ to avoid the
Python 3.14 + SQLModel incompatibility crash.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.hash import bcrypt
from tinydb import TinyDB, Query

_API_DIR = Path(__file__).resolve().parent.parent / "api"
load_dotenv(_API_DIR / ".env")

_TINYDB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "process" / "suppliers_db.json"

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-not-for-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def _get_users_table():
    os.makedirs(_TINYDB_PATH.parent, exist_ok=True)
    db = TinyDB(str(_TINYDB_PATH), indent=2, ensure_ascii=False)
    return db.table("users")


def _get_profiles_table():
    os.makedirs(_TINYDB_PATH.parent, exist_ok=True)
    db = TinyDB(str(_TINYDB_PATH), indent=2, ensure_ascii=False)
    return db.table("profiles")


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)


def get_user_by_email(email: str) -> dict | None:
    users = _get_users_table()
    doc = users.get(Query().email == email)
    if doc is None:
        return None
    return {"id": doc.doc_id, **doc}


def get_user_by_id(user_id: int) -> dict | None:
    users = _get_users_table()
    doc = users.get(doc_id=user_id)
    if doc is None:
        return None
    return {"id": doc.doc_id, **doc}


def get_profile_by_user_id(user_id: int) -> dict | None:
    profiles = _get_profiles_table()
    docs = profiles.search(Query().user_id == user_id)
    if not docs:
        return None
    doc = docs[0]
    return {"id": doc.doc_id, **doc}


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns the payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None