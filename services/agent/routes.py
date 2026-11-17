"""
routes/agent.py — FastAPI router para el agente LangGraph de soporte.

Endpoints:
  POST /agent/query  — Ejecuta el grafo del agente y devuelve la respuesta.
  GET  /agent/trace/{run_id}  — Recupera la traza de una corrida específica.
  GET  /agent/traces  — Lista las trazas recientes.

El endpoint NO contiene lógica de negocio — solo invoca el grafo compilado.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.agent.graph import run_agent, get_trace, list_traces

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ── Request / Response models ────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Pregunta del coordinador sobre políticas de HealthCore.",
    )


class TraceEventItem(BaseModel):
    node: str
    status: str
    timestamp: str
    routing: str | None = None
    metadata: dict | None = None


class QueryResponse(BaseModel):
    answer: str = Field(
        ...,
        description="Respuesta generada por el agente basada en la base de conocimiento.",
    )
    run_id: str = Field(
        ...,
        description="Identificador único de la corrida. Úsalo para recuperar la traza.",
    )


class TraceResponse(BaseModel):
    run_id: str
    question: str
    answer: str
    error: str | None = None
    routing_log: list[str] = []
    events: list[dict] = []
    num_chunks_retrieved: int = 0
    timestamp: str = ""


class TracesListItem(BaseModel):
    run_id: str
    question: str
    num_events: int
    error: str | None = None
    timestamp: str = ""


class TracesListResponse(BaseModel):
    traces: list[TracesListItem]


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/query", response_model=QueryResponse)
async def agent_query(req: QueryRequest) -> QueryResponse:
    """Ejecuta el agente de soporte LangGraph para responder una pregunta.

    El flujo completo:
      1. Recibe y valida la pregunta.
      2. Recupera contexto relevante de la base de conocimiento (Qdrant).
      3. Genera una respuesta usando el contexto recuperado.
      4. Persiste la traza completa de la corrida.

    El endpoint no contiene lógica de negocio — solo invoca el grafo.
    Si el grafo falla en cualquier nodo, responde con un mensaje de error claro.
    """
    import uuid
    run_id = str(uuid.uuid4())

    try:
        final_state = await run_agent(question=req.question, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ocurrió un error al procesar tu solicitud. "
                "Por favor intenta de nuevo más tarde."
            ),
        ) from None

    # Si el grafo terminó con error pero aún así produjo estado final
    if final_state.get("error") and not final_state.get("answer"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Ocurrió un error al procesar tu solicitud. "
                "Por favor intenta de nuevo más tarde."
            ),
        )

    return QueryResponse(
        answer=final_state.get("answer", ""),
        run_id=run_id,
    )


@router.get("/trace/{run_id}", response_model=TraceResponse)
def get_agent_trace(run_id: str) -> TraceResponse:
    """Recupera la traza completa de una corrida del agente.

    La traza incluye:
      - La pregunta original.
      - La respuesta final.
      - Los eventos de cada nodo ejecutado (en orden).
      - El log de enrutamiento (decisiones en cada bifurcación).
      - Errores si los hubo.

    Útil para debugging, auditoría y evaluación del comportamiento del agente.
    """
    trace = get_trace(run_id)
    if trace is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró traza para run_id '{run_id}'.",
        )

    return TraceResponse(
        run_id=trace.get("run_id", run_id),
        question=trace.get("question", ""),
        answer=trace.get("answer", ""),
        error=trace.get("error"),
        routing_log=trace.get("routing_log", []),
        events=trace.get("events", []),
        num_chunks_retrieved=trace.get("num_chunks_retrieved", 0),
        timestamp=trace.get("timestamp", ""),
    )


@router.get("/traces", response_model=TracesListResponse)
def list_agent_traces(limit: int = 20) -> TracesListResponse:
    """Lista las trazas más recientes del agente (sin eventos completos).

    Args:
        limit: Número máximo de trazas a devolver (default 20).
    """
    traces = list_traces(limit=limit)
    return TracesListResponse(
        traces=[
            TracesListItem(
                run_id=t.get("run_id", ""),
                question=t.get("question", ""),
                num_events=t.get("num_events", 0),
                error=t.get("error"),
                timestamp=t.get("timestamp", ""),
            )
            for t in traces
        ]
    )