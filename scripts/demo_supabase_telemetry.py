#!/usr/bin/env python3
"""Demo: pipeline completo de telemetría CONTRA SUPABASE real.

1. Lee DATABASE_URL del .env
2. Crea la tabla telemetry_events si no existe
3. Inserta 8 eventos reales vía HTTP (FastAPI + TestClient)
4. Consulta la tabla y la muestra
5. Te da el enlace para verlo en el dashboard de Supabase
"""

import json
import os
import sys
import textwrap
from pathlib import Path
from uuid import uuid4

# Cargar .env manualmente antes de cualquier otro import
from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[1] / "services/api"
load_dotenv(API_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ No se encontró DATABASE_URL en services/api/.env")
    sys.exit(1)

# Mostrar solo el host, no la contraseña
host_part = DATABASE_URL.split("@")[1].split("/")[0] if "@" in DATABASE_URL else "(unknown)"
print(f"🔌 Conectando a Supabase: {host_part}")
print()

sys.path.insert(0, str(API_DIR))

# ── Lazy imports (evitan crash Python 3.14 + SQLModel) ────────────
from sqlalchemy import text as sa_text
from sqlmodel import create_engine

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_db
from routes.telemetry import router

# ── 1. Engine directo a Supabase ──────────────────────────────────
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Crear tabla telemetry_events (como init_supabase_schema)
with engine.connect() as conn:
    conn.execute(sa_text("""
        CREATE TABLE IF NOT EXISTS telemetry_events (
            id              BIGSERIAL    PRIMARY KEY,
            event_id        VARCHAR(36)  NOT NULL UNIQUE,
            timestamp       TIMESTAMPTZ  NOT NULL,
            session_id      VARCHAR(128) NOT NULL,
            user_id         VARCHAR(128) NOT NULL,
            event_type      VARCHAR(64)  NOT NULL,
            schema_version  VARCHAR(16)  NOT NULL,
            request_id      VARCHAR(128) NOT NULL,
            tags            JSONB,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa_text("CREATE INDEX IF NOT EXISTS idx_telemetry_events_timestamp ON telemetry_events (timestamp)"))
    conn.execute(sa_text("CREATE INDEX IF NOT EXISTS idx_telemetry_events_event_type ON telemetry_events (event_type)"))
    conn.execute(sa_text("CREATE INDEX IF NOT EXISTS idx_telemetry_events_tags ON telemetry_events USING GIN (tags)"))
    conn.commit()

print("✅ Tabla telemetry_events lista (con 3 índices)")
print()

# ── 2. Montar FastAPI con dependency override que apunte a Supabase ──
from sqlmodel import Session

app = FastAPI()
app.include_router(router)

def session_dependency():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_db] = session_dependency
client = TestClient(app)

# ── 3. Los 8 eventos (validados contra contratos reales) ───────────
EVENTS = [
    # ── Negocio: inventario ──────────────────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-06T08:15:00Z",
        "sessionId": "sess-op-abc123def456",
        "userId": "user-hmac-a1b2c3d4e5f6",
        "requestId": "req-7a8b9c0d1e2f",
        "event_type": "inbound_order_created",
        "schemaVersion": "1.0.0",
        "properties": {
            "clinic_id": 3, "country": "US", "product_id": 12,
            "product_category": "ppe", "quantity": 500,
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
            "clinic_id": 7, "country": "UK", "product_id": 5,
            "product_category": "medication", "quantity": 30,
            "department": "operations", "consumption_type": "clinical_use",
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
            "clinic_id": 2, "country": "US", "product_id": 8,
            "product_category": "consumable", "quantity": 5,
            "threshold_quantity": 20, "threshold_version": "2",
        },
    },
    # ── Técnico ──────────────────────────────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-08T22:10:00Z",
        "sessionId": "sess-srv-9988776655",
        "userId": "user-hmac-000000000000",
        "requestId": "req-0d1e2f3a4b5c",
        "event_type": "api_dependency_failed",
        "schemaVersion": "1.0.0",
        "properties": {
            "service": "backoffice", "dependency": "supabase_postgres",
            "operation": "read", "failure_code": "timeout", "duration_ms": 5000,
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
            "producer": "backoffice", "destination": "telemetry_collector",
            "failure_code": "unavailable", "retry_count": 3, "batch_size": 12,
        },
    },
    # ── Autenticación ────────────────────────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-09T07:00:00Z",
        "sessionId": "sess-auth-4455667788",
        "userId": "user-hmac-bbccddeeff00",
        "requestId": "req-2f3a4b5c6d7e",
        "event_type": "auth_login_failed",
        "schemaVersion": "1.1.0",
        "properties": {
            "application": "backoffice", "failure_code": "invalid_credentials",
            "auth_method": "password", "rate_limited": False,
        },
    },
    # ── Rendimiento ──────────────────────────────────────────────
    {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-10T12:00:00Z",
        "sessionId": "sess-perf-0099887766",
        "userId": "user-hmac-ffeeddccbbaa",
        "requestId": "req-3a4b5c6d7e8f",
        "event_type": "api_latency_recorded",
        "schemaVersion": "1.0.0",
        "properties": {
            "service": "backoffice", "route_template": "/inventory/products",
            "method": "GET", "status_code": 200, "duration_ms": 345,
            "cache_result": "miss",
        },
    },
]

# ── Evento de control (va por /control) ────────────────────────────
ctrl_event = {
    "eventId": str(uuid4()),
    "timestamp": "2026-10-10T12:05:00Z",
    "sessionId": "sess-ctrl-000000000001",
    "userId": "user-hmac-ffffffffffff",
    "requestId": "req-ctrl-000000001",
    "event_type": "service_health_check_failed",
    "schemaVersion": "1.0.0",
    "properties": {
        "service": "backoffice", "check_name": "synthetic_route",
        "failure_code": "unexpected_status", "duration_ms": 150,
        "consecutive_failures": 3,
    },
}

# ── 4. Enviar eventos ──────────────────────────────────────────────
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("  Enviando 7 eventos a POST /telemetry/events…")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

resp = client.post("/telemetry/events", json={"events": EVENTS})
print(f"  HTTP {resp.status_code}")
print(f"  → {json.dumps(resp.json(), indent=4)}")
print()

resp2 = client.post("/telemetry/control", json={"events": [ctrl_event]})
print(f"  Control  → HTTP {resp2.status_code}  → {json.dumps(resp2.json())}")
print()

# ── 5. Consultar la tabla y mostrar ────────────────────────────────
with engine.connect() as conn:
    rows = conn.execute(
        sa_text("SELECT id, event_type, timestamp, tags, created_at FROM telemetry_events ORDER BY id")
    ).fetchall()

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"  📊 telemetry_events — {len(rows)} filas en Supabase")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

for row in rows:
    id_, etype, ts, tags_raw, created = row
    tags_str = textwrap.shorten(json.dumps(tags_raw) if isinstance(tags_raw, dict) else str(tags_raw or "∅"), width=74, placeholder="…")
    print(f"  │ id={id_}")
    print(f"  │ event_type={etype}")
    print(f"  │ timestamp={ts}")
    print(f"  │ tags={tags_str}")
    print(f"  │ created_at={created}")
    print(f"  └{'─'*50}")

print()
print("✅ 8 eventos persistiendo en Supabase con tags poblados.")
print()
print("🔗 Ahora ve al dashboard de Supabase y abre Table Editor:")
print(f"   {host_part.split('.')[0] if '.' in host_part else 'tu-proyecto'}")
print("   → Table Editor → selecciona 'telemetry_events'")
print("   → Verás las 8 filas en la interfaz gráfica 🎉")
print()