"""Servicio de reporting — FastAPI standalone.

Provee los 3 endpoints de consulta y disparo del pipeline.
Es un módulo independiente de ``services/telemetry/``.

Uso:
    uvicorn services.reporting.main:app --host 0.0.0.0 --port 8001 --reload
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Asegurar que el proyecto raíz está en sys.path para imports absolutos
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Cargar .env desde services/api/
_API_DIR = _PROJECT_ROOT / "services" / "api"
load_dotenv(_API_DIR / ".env")

from services.reporting.routes.reporting import router as reporting_router

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────

app = FastAPI(
    title="HealthCore Reporting API",
    description=(
        "API independiente de reporting para el pipeline mensual de "
        "desempeño de insumos por clínica. No modifica telemetry_events."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────

app.include_router(reporting_router)


# ── Health check ──────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
async def health_check():
    """Health check del servicio de reporting."""
    return {
        "status": "ok",
        "service": "reporting",
        "version": "1.0.0",
    }


# ── Inicialización del esquema al arrancar ───────────────────────────


@app.on_event("startup")
async def on_startup():
    """Inicializa el esquema reporting en la BD al arrancar."""
    if not os.getenv("DATABASE_URL"):
        logger.warning(
            "DATABASE_URL no configurada. "
            "El esquema reporting no se inicializará."
        )
        return
    try:
        from data.pipelines.database import init_reporting_schema

        init_reporting_schema()
        logger.info("Esquema reporting inicializado correctamente.")
    except Exception as exc:
        logger.error("Error al inicializar esquema reporting: %s", exc)