from __future__ import annotations

import logging
import time
from uuid import UUID, uuid4
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from database import init_supabase_schema
from incidents_analysis import analyze_csv_text, report_to_csv_text
from models import AnalysisPercentages, AnalysisResponse, AnalysisSummary, RootResponse
from routes.auth import router as auth_router
from routes.inventory import router as inventory_router
from routes.profiles import router as profiles_router
from routes.suppliers import router as suppliers_router
from routes.telemetry import router as telemetry_router
from routes.users import router as users_router
from telemetry import TELEMETRY_ENDPOINT
import telemetry_delivery

timing_logger = logging.getLogger("api.timing")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Inicializa el esquema de Supabase al arrancar la aplicación."""
    init_supabase_schema()
    logger.info("Supabase schema initialized (tables created if not exist).")
    telemetry_delivery.service.start()
    try:
        yield
    finally:
        telemetry_delivery.service.stop()


app = FastAPI(title="HealthCore API", version="1.1.0", lifespan=lifespan)
app.state.telemetry_endpoint = TELEMETRY_ENDPOINT

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Telemetry-Events", "X-Request-ID"],
)


# ── Timing Middleware ────────────────────────────────────────────────
# Mide la latencia de cada petición. Los logs se usan para identificar
# candidatos a caché: latencia alta + frecuencia alta + datos estables.


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    try:
        request_id = str(UUID(request.headers.get("X-Request-ID", "")))
    except ValueError:
        request_id = str(uuid4())
    request.state.telemetry_request_id = request_id
    start = time.perf_counter()
    request.state.telemetry_started_at = start
    context_token = telemetry_delivery.request_context.set(request)
    try:
        response = await call_next(request)
        if response.status_code in {401, 403} and request.url.path not in {"/auth/login", "/telemetry/events"}:
            from inventory_telemetry import signal
            from telemetry import normalized_route
            signal("auth_authorization_denied", {"application": "backoffice", "route_template": normalized_route(request.url.path),
                "method": request.method, "denial_code": "unauthenticated" if response.status_code == 401 else "forbidden",
                "role_group": getattr(request.state, "telemetry_role", "unknown")})
    finally:
        telemetry_delivery.request_context.reset(context_token)
    telemetry_delivery.capture_inventory_signals(request, response)
    response.headers["X-Request-ID"] = request_id
    duration = (time.perf_counter() - start) * 1000  # ms
    timing_logger.info(
        "%s %s → %s | %.1fms requestId=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration,
        request_id,
    )
    return response


app.include_router(suppliers_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(telemetry_router)


# ── Global exception handlers ──────────────────────────────────────────


@app.exception_handler(RequestValidationError)
async def validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return user-friendly validation errors, never the full stack trace."""
    errors: list[dict] = []
    operation = {"/inventory/orders/inbound": "inbound", "/inventory/orders/outbound": "outbound", "/inventory/products": "product_create"}.get(request.url.path)
    for e in exc.errors():
        field = ".".join(str(loc) for loc in e.get("loc", []) if loc != "body")
        msg = e.get("msg", "Invalid value")
        if operation and field in {"supply_id", "quantity", "clinic_id", "consumption_type", "vendor_name", "department"}:
            from inventory_telemetry import signal
            kind = e.get("type", "")
            code = "required" if kind == "missing" else "out_of_range" if "greater" in kind or "less" in kind else "invalid_enum" if field in {"department", "consumption_type"} else "invalid_format"
            signal("inventory_order_validation_failed", {"operation": operation, "field_name": field, "validation_code": code})
        errors.append(
            {
                "field": field or "body",
                "message": msg,
            }
        )
    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: never expose stack traces to the client."""
    from sqlalchemy.exc import SQLAlchemyError
    from telemetry_delivery import record_control
    if isinstance(exc, (SQLAlchemyError, OSError)) and not request.url.path.startswith("/telemetry"):
        record_control("api_dependency_failed", {"service": "healthcore_api", "dependency": "supabase_postgres" if isinstance(exc, SQLAlchemyError) else "tinydb",
            "operation": "read" if request.method == "GET" else "write", "failure_code": "unavailable",
            "duration_ms": min(300000, round((time.perf_counter() - getattr(request.state, "telemetry_started_at", time.perf_counter())) * 1000))})
    logger.error("Unhandled exception class=%s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Ocurrió un error inesperado. Inténtalo de nuevo más tarde."
        },
    )


_last_report: dict | None = None
_last_csv_export: str | None = None
_repo_root = Path(__file__).resolve().parents[2]
_health_failures = 0


@app.get("/health/ready", response_model=dict)
def health_ready():
    global _health_failures
    from database import get_sql_engine
    from sqlalchemy import text
    started = time.perf_counter()
    try:
        with get_sql_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        _health_failures = 0
        return {"ready": True}
    except Exception:
        _health_failures += 1
        telemetry_delivery.record_control("service_health_check_failed", {"service": "healthcore_api", "check_name": "readiness", "failure_code": "dependency_failed",
            "duration_ms": min(300000, round((time.perf_counter() - started) * 1000)), "consecutive_failures": min(1000, _health_failures)})
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service="HealthCore API",
        docs="/docs",
        analyze="/api/incidents/analyze",
        analyze_sample="/api/incidents/analyze/sample",
        export="/api/incidents/results/export",
        suppliers="/api/suppliers",
        suppliers_by_country="/api/suppliers/by-country/{country}",
        suppliers_by_category="/api/suppliers/by-category/{category}",
    )


@app.post("/api/incidents/analyze", response_model=AnalysisResponse)
async def analyze_incidents(file: UploadFile = File(...)) -> AnalysisResponse:
    if file.filename is None or file.filename.strip() == "":
        raise HTTPException(status_code=400, detail="Debes enviar un fichero CSV")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Formato inválido: el fichero debe ser .csv")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El fichero CSV está vacío")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Codificación inválida: el fichero debe estar en UTF-8",
        ) from exc

    try:
        report = analyze_csv_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    global _last_report
    global _last_csv_export
    _last_report = report
    _last_csv_export = report_to_csv_text(report)

    return AnalysisResponse(
        source_file=file.filename,
        summary=AnalysisSummary(
            total=report["total"],
            valid=report["valid"],
            invalid=report["invalid"],
            invalid_breakdown=report["invalid_breakdown"],
            category_counts=report["category_counts"],
            status_counts=report["status_counts"],
            country_counts=report["country_counts"],
            score_counts={str(k): v for k, v in report["score_counts"].items()},
            scored_cases=report["scored_cases"],
            closed_cases=report["closed_cases"],
            average_score=report["average_score"],
            percentages=AnalysisPercentages(
                categories=report["percentages"]["categories"],
                statuses=report["percentages"]["statuses"],
                countries=report["percentages"]["countries"],
            ),
        ),
    )


@app.post("/api/incidents/analyze/sample", response_model=AnalysisResponse)
def analyze_sample_incidents() -> AnalysisResponse:
    sample_path = _repo_root / "scripts" / "incidents-healthcore.csv"
    if not sample_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No se encontró el CSV de muestra en la ruta esperada.",
        )

    text = sample_path.read_text(encoding="utf-8")
    try:
        report = analyze_csv_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    global _last_report
    global _last_csv_export
    _last_report = report
    _last_csv_export = report_to_csv_text(report)

    return AnalysisResponse(
        source_file=sample_path.name,
        summary=AnalysisSummary(
            total=report["total"],
            valid=report["valid"],
            invalid=report["invalid"],
            invalid_breakdown=report["invalid_breakdown"],
            category_counts=report["category_counts"],
            status_counts=report["status_counts"],
            country_counts=report["country_counts"],
            score_counts={str(k): v for k, v in report["score_counts"].items()},
            scored_cases=report["scored_cases"],
            closed_cases=report["closed_cases"],
            average_score=report["average_score"],
            percentages=AnalysisPercentages(
                categories=report["percentages"]["categories"],
                statuses=report["percentages"]["statuses"],
                countries=report["percentages"]["countries"],
            ),
        ),
    )


@app.get("/api/incidents/results/export")
def export_last_results() -> Response:
    if _last_report is None or _last_csv_export is None:
        raise HTTPException(
            status_code=404,
            detail="No hay resultados para exportar. Ejecuta primero POST /api/incidents/analyze",
        )

    return Response(
        content=_last_csv_export,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )
