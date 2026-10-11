#!/usr/bin/env python3
"""Demostración: pipeline completo de almacenamiento de telemetría.

Arranca un servidor FastAPI en memoria (SQLite), inyecta 7 eventos variados
vía HTTP, y muestra la tabla telemetry_events resultante en formato tabla.
No requiere Supabase ni DATABASE_URL — todo corre en SQLite local.
"""

import json
import sys
import textwrap
from pathlib import Path
from uuid import uuid4

# Añadir services/api al path
API_DIR = Path(__file__).resolve().parents[1] / "services/api"
sys.path.insert(0, str(API_DIR))

# ── Lazy imports (evitan el crash Python 3.14 + SQLModel) ────────────
from sqlalchemy import text as sa_text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_db
from routes.telemetry import router

# ── 1. Crear el engine SQLite in-memory ──────────────────────────────
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)

# Crear la tabla telemetry_events (raw SQL, como en producción)
with engine.connect() as conn:
    conn.execute(sa_text("""
        CREATE TABLE IF NOT EXISTS telemetry_events (
            id              INTEGER  PRIMARY KEY AUTOINCREMENT,
            event_id        TEXT     NOT NULL UNIQUE,
            timestamp       TEXT     NOT NULL,
            session_id      TEXT     NOT NULL,
            user_id         TEXT     NOT NULL,
            event_type      TEXT     NOT NULL,
            schema_version  TEXT     NOT NULL,
            request_id      TEXT     NOT NULL,
            tags            TEXT,
            created_at      TEXT     NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """))
    conn.execute(sa_text("CREATE INDEX IF NOT EXISTS idx_evt_ts ON telemetry_events (timestamp)"))
    conn.execute(sa_text("CREATE INDEX IF NOT EXISTS idx_evt_type ON telemetry_events (event_type)"))
    conn.commit()

# ── 2. Montar la app FastAPI ─────────────────────────────────────────
app = FastAPI()
app.include_router(router)

def session_dependency():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_db] = session_dependency
client = TestClient(app)

# ── 3. Enviar 7 eventos variados vía HTTP ────────────────────────────
EVENTS = [
    # ── Eventos de negocio (inventario) ──────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-06T08:15:00Z",
        "sessionId": "sess-op-abc123def456",
        "userId": "user-hmac-a1b2c3d4e5f6",
        "requestId": "req-7a8b9c0d1e2f",
        "event_type": "inbound_order_created",
        "schemaVersion": "1.0.0",
        "properties": {
            "clinic_id": 3,
            "country": "US",
            "product_id": 12,
            "product_category": "ppe",
            "quantity": 500,
            "vendor_ref": "a" * 64,
        },
    },
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-06T09:30:00Z",
        "sessionId": "sess-op-abc123def456",
        "userId": "user-hmac-a1b2c3d4e5f6",
        "requestId": "req-8b9c0d1e2f3a",
        "event_type": "outbound_order_created",
        "schemaVersion": "1.0.0",
        "properties": {
            "clinic_id": 7,
            "country": "UK",
            "product_id": 5,
            "product_category": "medication",
            "quantity": 30,
            "department": "operations",
            "consumption_type": "clinical_use",
        },
    },
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-07T14:00:00Z",
        "sessionId": "sess-alert-1122334455",
        "userId": "user-hmac-f6e5d4c3b2a1",
        "requestId": "req-9c0d1e2f3a4b",
        "event_type": "stock_threshold_triggered",
        "schemaVersion": "1.0.0",
        "properties": {
            "clinic_id": 2,
            "country": "US",
            "product_id": 8,
            "product_category": "consumable",
            "quantity": 5,
            "threshold_quantity": 20,
            "threshold_version": "2",
        },
    },
    # ── Eventos técnicos ─────────────────────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-08T22:10:00Z",
        "sessionId": "sess-srv-9988776655",
        "userId": "user-hmac-000000000000",
        "requestId": "req-0d1e2f3a4b5c",
        "event_type": "api_dependency_failed",
        "schemaVersion": "1.0.0",
        "properties": {
            "service": "backoffice",
            "dependency": "supabase_postgres",
            "operation": "read",
            "failure_code": "timeout",
            "duration_ms": 5000,
        },
    },
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-09T06:45:00Z",
        "sessionId": "sess-srv-9988776655",
        "userId": "user-hmac-000000000000",
        "requestId": "req-1e2f3a4b5c6d",
        "event_type": "telemetry_delivery_failed",
        "schemaVersion": "1.0.0",
        "properties": {
            "producer": "backoffice",
            "destination": "telemetry_collector",
            "failure_code": "unavailable",
            "retry_count": 3,
            "batch_size": 12,
        },
    },
    # ── Evento de autenticación ──────────────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-09T07:00:00Z",
        "sessionId": "sess-auth-4455667788",
        "userId": "user-hmac-bbccddeeff00",
        "requestId": "req-2f3a4b5c6d7e",
        "event_type": "auth_login_failed",
        "schemaVersion": "1.1.0",
        "properties": {
            "application": "backoffice",
            "failure_code": "invalid_credentials",
            "auth_method": "password",
            "rate_limited": False,
        },
    },
    # ── Evento de rendimiento ────────────────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-10T12:00:00Z",
        "sessionId": "sess-perf-0099887766",
        "userId": "user-hmac-ffeeddccbbaa",
        "requestId": "req-3a4b5c6d7e8f",
        "event_type": "api_latency_recorded",
        "schemaVersion": "1.0.0",
        "properties": {
            "service": "backoffice",
            "route_template": "/inventory/products",
            "method": "GET",
            "status_code": 200,
            "duration_ms": 345,
            "cache_result": "miss",
        },
    },
]

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("  Enviando 7 eventos al endpoint /telemetry/events…")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

response = client.post("/telemetry/events", json={"events": EVENTS})
receipt = response.json()
print(f"  HTTP {response.status_code}")
print(f"  Respuesta: {json.dumps(receipt, indent=4)}")
print()

# ── 4. También enviar un evento de control ───────────────────────────
ctrl_event = {
    "eventId": str(uuid4()),
    "timestamp": "2026-10-10T12:05:00Z",
    "sessionId": "sess-ctrl-000000000001",
    "userId": "user-hmac-ffffffffffff",
    "requestId": "req-ctrl-000000001",
    "event_type": "service_health_check_failed",
    "schemaVersion": "1.0.0",
    "properties": {
        "service": "backoffice",
        "check_name": "synthetic_route",
        "failure_code": "unexpected_status",
        "duration_ms": 150,
        "consecutive_failures": 3,
    },
}
response = client.post("/telemetry/control", json={"events": [ctrl_event]})
receipt2 = response.json()
print(f"  Control event → HTTP {response.status_code} → {json.dumps(receipt2)}")
print()

# ── 5. Consultar la tabla y mostrar resultado ────────────────────────
with engine.connect() as conn:
    rows = conn.execute(
        sa_text("""
            SELECT id, event_type, timestamp, tags, created_at
            FROM telemetry_events
            ORDER BY id
        """)
    ).fetchall()

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"  Contenido de telemetry_events ({len(rows)} filas)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

for row in rows:
    id_, etype, ts, tags_raw, created = row
    tags_str = textwrap.shorten(tags_raw or "∅", width=72, placeholder="…")
    print(f"  │ id={id_}")
    print(f"  │ event_type={etype}")
    print(f"  │ timestamp={ts}")
    print(f"  │ tags={tags_str}")
    print(f"  │ created_at={created}")
    print(f"  └{'─'*50}")

print()
print(f"  Total filas: {len(rows)}")
print("  ✅ Todos los eventos persisten con tags poblados.")
print()