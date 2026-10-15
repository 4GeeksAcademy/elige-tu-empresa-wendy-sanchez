"""Standalone telemetry API server — evita la incompatibilidad SQLModel + Python 3.14.

Uso:
    uvicorn telemetry.server:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /telemetry/report?start_date=...&end_date=...
    POST /telemetry/events
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Asegurar que podemos importar analysis.py ──────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── FastAPI app ────────────────────────────────────────────────────────

app = FastAPI(title="HealthCore Telemetry API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# ── Montar enrutador de telemetría (con GET /report y POST /events) ──
#
# Importamos el router de services/api/routes/telemetry.py.
# Este router NO depende de models.py, solo de database.py que a su vez
# usa SQLAlchemy engine directamente (sin SQLModel).

_API_ROUTES_DIR = _THIS_DIR.parent / "api" / "routes"
if str(_API_ROUTES_DIR) not in sys.path:
    sys.path.insert(0, str(_API_ROUTES_DIR))

# Necesitamos database.py desde services/api/
_API_DIR = _THIS_DIR.parent / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

def _build_app():
    """Importa el router y lo monta — función separada para manejar imports perezosos."""
    from routes.telemetry import router as telemetry_router
    app.include_router(telemetry_router)
    return app

app = _build_app()