"""HealthCore Incidents API — FastAPI application."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import RootResponse

from routes.incidents import router as incidents_router

timing_logger = logging.getLogger("incidents-api.timing")
logger = logging.getLogger(__name__)

app = FastAPI(title="HealthCore Incidents API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Timing Middleware ────────────────────────────────────────────────


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000  # ms
    timing_logger.info(
        "%s %s → %s | %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response


app.include_router(incidents_router)


# ── Global exception handlers ──────────────────────────────────────────


@app.exception_handler(RequestValidationError)
async def validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return user-friendly validation errors, never the full stack trace."""
    errors: list[dict] = []
    for e in exc.errors():
        field = ".".join(str(loc) for loc in e.get("loc", []) if loc != "body")
        msg = e.get("msg", "Invalid value")
        errors.append(
            {
                "field": field or "body",
                "message": msg,
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: never expose stack traces to the client."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later."
        },
    )


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service="HealthCore Incidents API",
        docs="/docs",
        incidents="/api/incidents",
        summary="/api/incidents/summary",
    )