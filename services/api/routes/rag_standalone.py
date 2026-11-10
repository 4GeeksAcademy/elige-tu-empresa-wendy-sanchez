#!/usr/bin/env python3
"""
Standalone RAG API server for HealthCore.

Launches only the RAG endpoints without requiring the full services/api
application (which has Python 3.14 / SQLModel compatibility issues).

Usage:
    QDRANT_URL=http://localhost:6333 uv run python3 services/api/routes/rag_standalone.py

Or via uvicorn directly:
    cd services/api && QDRANT_URL=http://localhost:6333 uv run uvicorn rag_standalone:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Path setup ────────────────────────────────────────────────────
# The routes/ package lives under services/api/.
API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(API_DIR, "..", ".."))

for p in [PROJECT_ROOT, API_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from routes.rag import router as rag_router  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HealthCore RAG API",
    description="Retrieval-Augmented Generation for patient coordinators",
    version="0.1.0",
)

# CORS — allow the Next.js frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_router)

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("RAG_HOST", "0.0.0.0")
    port = int(os.getenv("RAG_PORT", "8000"))
    logger.info("Starting RAG standalone server on %s:%s", host, port)
    uvicorn.run("rag_standalone:app", host=host, port=port, reload=False)