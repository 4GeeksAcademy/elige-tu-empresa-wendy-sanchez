#!/usr/bin/env python3
"""Lote mixto: eventos válidos e inválidos → respuesta {received, stored, rejected}."""

import json, os, sys, textwrap
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[1] / "services/api"
load_dotenv(API_DIR / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL no encontrado"); sys.exit(1)

sys.path.insert(0, str(API_DIR))
from sqlalchemy import text as sa_text
from sqlmodel import Session, create_engine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from database import get_db
from routes.telemetry import router

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
with engine.connect() as conn:
    conn.execute(sa_text("""
        CREATE TABLE IF NOT EXISTS telemetry_events (
            id BIGSERIAL PRIMARY KEY, event_id VARCHAR(36) NOT NULL UNIQUE,
            timestamp TIMESTAMPTZ NOT NULL, session_id VARCHAR(128) NOT NULL,
            user_id VARCHAR(128) NOT NULL, event_type VARCHAR(64) NOT NULL,
            schema_version VARCHAR(16) NOT NULL, request_id VARCHAR(128) NOT NULL,
            tags JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.commit()

app = FastAPI(); app.include_router(router)
def sdep():  # session dependency override
    with Session(engine) as session:
        yield session
app.dependency_overrides[get_db] = sdep
client = TestClient(app)

# ── Construir lote mixto: 5 eventos ─────────────────────────────
def evt(**kw):
    d = {
        "eventId": str(uuid4()), "timestamp": "2026-10-10T12:00:00Z",
        "sessionId": "sess-mix-abcdef123456", "userId": "user-mix-abcdef123456",
        "requestId": "req-mix-abcdef123456",
        "event_type": "auth_logout_completed", "schemaVersion": "1.0.0",
        "properties": {"application": "backoffice", "logout_reason": "user_action"},
    }
    d.update(kw)
    return d

batch = [
    evt(),  # 1: válido
    evt(event_type="zzz_unknown_event"),  # 2: event_type no registrado
    evt(event_type="inbound_order_created", schemaVersion="1.0.0",
        properties={"clinic_id": 1, "country": "US", "product_id": 5,
                    "product_category": "ppe", "quantity": 100,
                    "vendor_ref": "a" * 64}),  # 3: válido
    evt(properties={"application": "backoffice", "email": "private@x.com"}),  # 4: email PII
    {"eventId": str(uuid4()), "timestamp": "2026-10-10T12:00:00Z",
     "sessionId": "sess-mix-abcdef123456", "userId": "user-mix-abcdef123456",
     "requestId": "req-mix-abcdef123456",
     "event_type": "service_health_check_failed", "schemaVersion": "1.0.0",
     "properties": {"service": "backoffice", "check_name": "synthetic_route",
                    "failure_code": "unexpected_status", "duration_ms": 150,
                    "consecutive_failures": 3}},  # 5: válido
]

r = client.post("/telemetry/events", json={"events": batch})
print()
print(json.dumps(r.json(), indent=4))
print()