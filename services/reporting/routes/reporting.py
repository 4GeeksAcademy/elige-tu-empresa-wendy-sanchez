"""Endpoints de la API de reporting para HealthCore.

Implementa los 3 endpoints diseñados en PIPELINE_DESIGN.md sección 10.
Sigue las mismas convenciones de autenticación que services/api/.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from data.pipelines.database import get_target_engine
from data.pipelines.run_store import get_latest_pipeline_run
from data.pipelines.runner import trigger_monthly_clinic_supply_performance
from services.reporting.auth import get_current_user_id
from services.reporting.queries import get_monthly_clinic_supply_performance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reporting", tags=["reporting"])


# ── Modelos de respuesta ──────────────────────────────────────────────


class PipelineRunOut(BaseModel):
    """Modelo de respuesta para una ejecucion del pipeline."""

    run_id: str
    flow_name: str
    status: str
    current_phase: str | None = None
    checkpoint: str | None = None
    trigger_source: str = "scheduled"
    month_start: str | None = None
    month_end: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    events_read: int = 0
    events_valid: int = 0
    events_rejected: int = 0
    events_deduplicated: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    warning_count: int = 0
    error_message: str | None = None


class PipelineRunTriggerOut(BaseModel):
    """Modelo de respuesta al disparar una ejecucion."""

    run_id: str
    status: str
    message: str
    month_start: str | None = None
    month_end: str | None = None


class ClinicKpiOut(BaseModel):
    """KPI de una sola clinica para un mes determinado.

    Sin per-clinic ``month_start`` ni ``computed_at``: esos campos
    viven en el wrapper ``MonthlyKpisResponse``. Coincide con el
    contrato JSON de CONTEXT.md.
    """

    clinic_id: str
    country: str
    total_supply_cost: float = 0.0
    supply_consumption_count: int = 0
    critical_stockout_count: int = 0
    expiry_risk_count: int = 0
    currency: str


class MonthlyKpisResponse(BaseModel):
    """Envoltura del response de KPI -- coincide con el contrato de CONTEXT.md.

    .. code-block:: json

        {
          "month_start": "2026-07-01",
          "clinics": [ { "clinic_id": "...", ... } ]
        }
    """

    month_start: str
    clinics: list[ClinicKpiOut]


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get(
    "/pipeline-runs/latest",
    response_model=PipelineRunOut | dict,
    summary="Consulta el estado de la ultima ejecucion del pipeline",
    description=(
        "Devuelve la ejecucion mas reciente del pipeline "
        "con sus metadatos y contadores. No inicia una nueva ejecucion."
    ),
)
async def get_latest_run(
    _user_id: int = Depends(get_current_user_id),
):
    """``GET /reporting/pipeline-runs/latest`` -- consulta de estado.

    Funcion de datos importada: ``data.pipelines.run_store.get_latest_pipeline_run()``.
    """
    engine = get_target_engine()
    run = get_latest_pipeline_run(engine)

    if run is None:
        return {"message": "No hay ejecuciones registradas.", "run": None}

    return run


@router.post(
    "/pipeline-runs",
    response_model=PipelineRunTriggerOut,
    summary="Dispara manualmente una ejecucion del pipeline",
    description=(
        "Acepta opcionalmente ``month_start`` (YYYY-MM-DD, primer dia del mes). "
        "Devuelve el identificador y estado inicial de la ejecucion. "
        "No bloquea la peticion esperando el informe completo."
    ),
)
async def trigger_run(
    month_start: Optional[str] = Query(
        default=None,
        description="Primer dia del mes a procesar (YYYY-MM-DD). "
        "Por defecto: mes anterior.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    _user_id: int = Depends(get_current_user_id),
):
    """``POST /reporting/pipeline-runs`` -- disparo manual.

    Funcion de datos importada:
    ``data.pipelines.runner.trigger_monthly_clinic_supply_performance()``.
    """
    # Validar formato de mes
    if month_start:
        try:
            datetime.strptime(month_start, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de mes invalido: {month_start}. Use YYYY-MM-DD.",
            )

    result = trigger_monthly_clinic_supply_performance(
        month_start=month_start,
        trigger_source="manual",
    )

    return PipelineRunTriggerOut(
        run_id=result.get("run_id", ""),
        status=result.get("status", "unknown"),
        message="Pipeline ejecutado correctamente."
        if result.get("status") == "completed"
        else f"Pipeline finalizo con estado: {result.get('status')}",
        month_start=result.get("month_start"),
        month_end=result.get("month_end"),
    )


@router.get(
    "/monthly-clinic-supply-performance",
    response_model=MonthlyKpisResponse | dict,
    summary="Consulta los KPI mensuales para el dashboard",
    description=(
        "Acepta ``month_start`` opcional (YYYY-MM-DD). "
        "Si se omite, devuelve el ultimo periodo calculado disponible. "
        "Devuelve todas las filas disponibles para ese mes con los 4 KPI. "
        "La respuesta sigue el contrato definido en CONTEXT.md: "
        "un objeto con ``month_start`` y ``clinics``."
    ),
)
async def get_monthly_kpis(
    month_start: Optional[str] = Query(
        default=None,
        description="Primer dia del mes (YYYY-MM-DD). "
        "Por defecto: ultimo periodo disponible.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    _user_id: int = Depends(get_current_user_id),
):
    """``GET /reporting/monthly-clinic-supply-performance`` -- consulta de KPI.

    Funcion de datos importada:
    ``services.reporting.queries.get_monthly_clinic_supply_performance()``.
    """
    engine = get_target_engine()
    rows = get_monthly_clinic_supply_performance(engine, month_start)

    if not rows:
        return {
            "message": "No hay datos disponibles para el periodo solicitado.",
            "data": [],
        }

    # Extraer month_start del primer registro
    current_month = rows[0].get("month_start", str(datetime.now().date()))

    clinics = []
    for r in rows:
        clinics.append(ClinicKpiOut(
            clinic_id=r.get("clinic_id", ""),
            country=r.get("country", ""),
            total_supply_cost=float(r.get("total_supply_cost", 0)),
            supply_consumption_count=int(r.get("supply_consumption_count", 0)),
            critical_stockout_count=int(r.get("critical_stockout_count", 0)),
            expiry_risk_count=int(r.get("expiry_risk_count", 0)),
            currency=r.get("currency", "USD"),
        ))

    return MonthlyKpisResponse(
        month_start=current_month,
        clinics=clinics,
    )
