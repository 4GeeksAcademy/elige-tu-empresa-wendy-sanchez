"""Servidor de autenticación standalone para el backoffice.

Corre en el puerto 8000 y provee únicamente los endpoints que necesita
el backoffice de HealthCore: /auth/login y /auth/me.

Usa TinyDB para usuarios (la misma DB de services/api/) y JWT para tokens.
No depende de SQLModel ni de Supabase.

Uso:
    python services/api/auth_standalone.py
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from datetime import datetime, timezone

import bcrypt
import jwt as pyjwt
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from tinydb import TinyDB, Query
import uvicorn

# ── Config ───────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TINYDB_PATH = _PROJECT_ROOT / "data" / "process" / "suppliers_db.json"
_USERS_TABLE = "users"
_PROFILES_TABLE = "profiles"

# Cargar .env desde services/api/
load_dotenv(_PROJECT_ROOT / "services" / "api" / ".env")

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-generate-a-random-secret")
JWT_ALGORITHM: str = "HS256"
TOKEN_EXPIRE_SECONDS: int = 86400  # 24 horas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("auth_standalone")


# ── Modelos ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfilePublic(BaseModel):
    id: int
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class MeResponse(BaseModel):
    email: str
    role: str
    profile: ProfilePublic | None = None
    telemetry_user_id: str | None = None


# ── TinyDB helpers ───────────────────────────────────────────────────

def _get_db() -> TinyDB:
    os.makedirs(_TINYDB_PATH.parent, exist_ok=True)
    return TinyDB(str(_TINYDB_PATH))


def _pseudonym(user_id: int) -> str:
    """Genera un seudónimo para telemetría (mismo algoritmo que telemetry_identity)."""
    import hashlib
    raw = f"hc::{user_id}::anon"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── FastAPI app ──────────────────────────────────────────────────────

app = FastAPI(
    title="HealthCore Auth (standalone)",
    description="Servidor de autenticación ligero para el backoffice. No usa SQLModel ni Supabase.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    db = _get_db()
    users = db.table(_USERS_TABLE)
    User = Query()

    user_docs = users.search(User.email == payload.email)
    if not user_docs:
        logger.warning("Intento de login para email no registrado: %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    user = user_docs[0]
    if not user.get("is_active", False):
        logger.warning("Intento de login para usuario inactivo: %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    stored_hash = user.get("hashed_password", "")
    if not stored_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    try:
        valid = bcrypt.checkpw(payload.password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        logger.exception("Error al verificar contraseña")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno de autenticación",
        )

    if not valid:
        logger.warning("Contraseña incorrecta para: %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    # Generar token JWT
    user_id = user.doc_id if hasattr(user, "doc_id") else user.get("id", 0)
    now = int(time.time())
    payload_jwt = {
        "sub": str(user_id),
        "email": user["email"],
        "role": user.get("role", "user"),
        "iat": now,
        "exp": now + TOKEN_EXPIRE_SECONDS,
    }
    access_token = pyjwt.encode(payload_jwt, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    logger.info("Login exitoso: user_id=%s email=%s role=%s", user_id, payload.email, user.get("role"))
    return TokenResponse(access_token=access_token)


@app.get("/auth/me", response_model=MeResponse)
def read_me(authorization: str | None = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o ausentes",
        )

    # Extraer token del header
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o ausentes",
        )

    try:
        payload = pyjwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        logger.warning("Token JWT expirado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o ausentes",
        )
    except pyjwt.InvalidTokenError:
        logger.warning("Token JWT inválido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o ausentes",
        )

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o ausentes",
        )

    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o ausentes",
        )

    # Buscar perfil en TinyDB
    db = _get_db()
    profiles = db.table(_PROFILES_TABLE)
    Profile = Query()
    profile_doc = profiles.get(Profile.user_id == user_id)

    profile = None
    if profile_doc:
        profile = ProfilePublic(
            id=profile_doc.doc_id if hasattr(profile_doc, "doc_id") else 0,
            name=profile_doc.get("name"),
            phone=profile_doc.get("phone"),
            address=profile_doc.get("address"),
        )

    logger.info("Token válido para user_id=%s", user_id)
    return MeResponse(
        email=payload.get("email", "unknown"),
        role=payload.get("role", "user"),
        profile=profile,
        telemetry_user_id=_pseudonym(user_id),
    )


# ── Health check ─────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-standalone"}


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔐 HealthCore Auth Standalone")
    print(f"   TinyDB: {_TINYDB_PATH}")
    print(f"   Puerto: 8000")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000)