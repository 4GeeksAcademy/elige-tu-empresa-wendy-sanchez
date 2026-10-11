"""Standalone telemetry report server — sin dependencia de SQLModel.

Uso:
    uvicorn telemetry.server_standalone:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    GET  /telemetry/report?start_date=...&end_date=...
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env antes de cualquier import que lo necesite
_API_DIR = Path(__file__).resolve().parent.parent / "api"
load_dotenv(_API_DIR / ".env")

# Importar el pipeline de análisis directamente
_TELEMETRY_DIR = Path(__file__).resolve().parent
if str(_TELEMETRY_DIR) not in sys.path:
    sys.path.insert(0, str(_TELEMETRY_DIR))

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text as sa_text


# ── FastAPI app ────────────────────────────────────────────────────────

app = FastAPI(title="HealthCore Telemetry Report API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Engine compartido ─────────────────────────────────────────────────

_engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
)


# ── Caché en memoria ─────────────────────────────────────────────────

import time as _time

_report_cache: dict[str, tuple[float, dict]] = {}
_REPORT_CACHE_TTL = 60


def _cache_key(start: datetime, end: datetime) -> str:
    return f"report:{start.isoformat()}:{end.isoformat()}"


# ── Endpoint ───────────────────────────────────────────────────────────

@app.get("/telemetry/report")
def telemetry_report(
    start_date: Optional[str] = Query(None, description="Inicio ISO 8601 (UTC). Por defecto: now - 7d."),
    end_date: Optional[str] = Query(None, description="Fin ISO 8601 (UTC). Por defecto: now."),
) -> JSONResponse:
    # 1. Resolver ventana de fechas
    now = datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat(start_date) if start_date else (now - timedelta(days=7))
        end = datetime.fromisoformat(end_date) if end_date else now
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Formato de fecha inválido: {exc}")

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    # 2. Comprobar caché
    cache_key = _cache_key(start, end)
    now_ts = _time.monotonic()
    cached = _report_cache.get(cache_key)
    if cached is not None:
        expires_at, value = cached
        if now_ts < expires_at:
            return JSONResponse(content=value)

    # 3. Ejecutar pipeline
    from analysis import run_all

    try:
        metrics = run_all(_engine, start, end)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en el pipeline de análisis: {exc}")

    response = {
        "period": {
            "from": start.isoformat(),
            "to": end.isoformat(),
        },
        "metrics": metrics,
    }

    _report_cache[cache_key] = (now_ts + _REPORT_CACHE_TTL, response)
    return JSONResponse(content=response)


# ── Auth endpoints ──────────────────────────────────────────────────────

from auth_standalone import (
    verify_password,
    get_user_by_email,
    get_user_by_id,
    get_profile_by_user_id,
    create_access_token,
    decode_access_token,
)


class _LoginRequest(BaseModel):
    email: EmailStr
    password: str


class _Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class _ProfilePublic(BaseModel):
    id: int
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class _MeResponse(BaseModel):
    email: str
    role: str
    profile: _ProfilePublic | None = None
    telemetry_user_id: str | None = None


@app.post("/auth/login", response_model=_Token)
def auth_login(payload: _LoginRequest) -> _Token:
    user = get_user_by_email(payload.email)
    if user is None or not user.get("is_active", False) or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Email o contraseña incorrectos",
        )

    access_token = create_access_token(subject=str(user["id"]))
    return _Token(access_token=access_token)


def _get_current_user_or_none(authorization: str | None = Header(None)) -> dict | None:
    """Extract current user from Authorization header. Returns None on failure."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    try:
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        return None
    return get_user_by_id(user_id)


@app.get("/auth/me", response_model=_MeResponse)
def auth_me(authorization: str | None = Header(None)):
    user = _get_current_user_or_none(authorization)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas o ausentes",
        )

    profile = get_profile_by_user_id(user["id"])
    profile_public = None
    if profile is not None:
        profile_public = _ProfilePublic(
            id=profile["id"],
            name=profile.get("name"),
            phone=profile.get("phone"),
            address=profile.get("address"),
        )

    # Simple pseudonym: hash the user_id with a basic hash
    import hashlib
    telemetry_id = hashlib.sha256(f"telemetry:{user['id']}".encode()).hexdigest()[:16]

    return _MeResponse(
        email=user["email"],
        role=user.get("role", "user"),
        profile=profile_public,
        telemetry_user_id=telemetry_id,
    )


@app.get("/health")
def health():
    return {"status": "ok", "engine": "sqlalchemy"}