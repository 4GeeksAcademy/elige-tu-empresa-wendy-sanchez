"""HealthCore Incidents API — FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.incidents import router as incidents_router

app = FastAPI(title="HealthCore Incidents API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router)


@app.get("/")
def root() -> dict:
    return {
        "service": "HealthCore Incidents API",
        "docs": "/docs",
        "incidents": "/api/incidents",
        "summary": "/api/incidents/summary",
    }