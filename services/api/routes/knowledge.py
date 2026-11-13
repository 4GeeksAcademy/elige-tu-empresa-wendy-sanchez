"""
routes/knowledge.py — FastAPI router for /knowledge/query endpoint.

Endpoints:
  POST /knowledge/query — Ask a question to the HealthCore knowledge base.
                          Returns only the generated answer string.

Business rules (enforced by the generation prompt):
  - Answers use ONLY the retrieved context — never invented data.
  - Unlisted insurers → must verify with billing (Tom Callahan).
  - Never apply no-show charges to Medicare/Medicaid patients.
  - Distinguish US vs UK when the question doesn't specify a country.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from data.pipelines.rag import query as rag_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ── Request / Response models ────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Pregunta del coordinador sobre políticas de HealthCore.",
    )


class QueryResponse(BaseModel):
    answer: str = Field(
        ...,
        description="Respuesta generada por el modelo basada en la base de conocimiento.",
    )


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/query", response_model=QueryResponse)
def query_knowledge(req: QueryRequest) -> QueryResponse:
    """Answer a question using the HealthCore knowledge base (RAG).

    This endpoint delegates directly to ``data.pipelines.rag.query()`` —
    no retrieval or generation logic is duplicated here.  The pipeline
    embeds the question, retrieves relevant chunks from Qdrant, builds
    a prompt, and calls the generation LLM.

    The response is **always** a generated answer string — never raw
    Qdrant results, chunk lists, or similarity scores.  Those may be
    logged server-side for debugging.

    Raises:
        503: If the Qdrant or LLM backend is unreachable.
        422: If the question is too short (< 3 characters) or too long.
    """
    try:
        answer = rag_query(question=req.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return QueryResponse(answer=answer)