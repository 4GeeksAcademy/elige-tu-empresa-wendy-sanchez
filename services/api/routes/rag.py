"""
routes/rag.py — FastAPI router for RAG knowledge base queries.

All query logic lives in ``data.pipelines.rag.query()`` — this router is a
thin wrapper that maps the result into endpoint-specific response models.

Endpoints:
  POST /rag/query  — Ask a question to the HealthCore knowledge base.
  GET  /rag/health — Check Qdrant connectivity and collection status.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from data.process.rag import setup as index_corpus
from data.pipelines.rag import retrieve, generate_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


# ── Request / Response models ────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Pregunta del coordinador sobre políticas de HealthCore.",
    )
    k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Número de fragmentos a recuperar.",
    )
    min_score: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Umbral mínimo de similitud (coseno).",
    )


class SourceItem(BaseModel):
    source_document: str
    section: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    chunks_retrieved: int
    min_score: float


class HealthResponse(BaseModel):
    status: str
    collection: str
    points_count: int


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/query", response_model=QueryResponse)
def query_knowledge_base(req: QueryRequest) -> QueryResponse:
    """Answer a question using the HealthCore knowledge base (RAG).

    Uses ``retrieve()`` + ``generate_answer()`` separately (rather than
    ``query()``) so that the source chunks can be returned in the response
    for debugging / validation.

    **Business rules enforced by the LLM prompt:**
    - No invented insurance coverages, fees, or policies.
    - Unlisted insurers → must verify with billing (Tom Callahan).
    - Never apply no-show charges to Medicare/Medicaid patients.
    - Distinguish US vs UK when the question doesn't specify a country.
    """
    try:
        chunks = retrieve(
            req.question,
            k=req.k,
            min_score=req.min_score,
        )
        answer = generate_answer(question=req.question, context=chunks)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return QueryResponse(
        answer=answer,
        sources=[
            SourceItem(
                source_document=c.get("source_document", ""),
                section=c.get("section", ""),
                score=c.get("_score", 0.0),
            )
            for c in chunks
        ],
        chunks_retrieved=len(chunks),
        min_score=req.min_score,
    )


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check that the Qdrant collection exists and has points."""
    from urllib.parse import urlparse
    import os

    from qdrant_client import QdrantClient

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    parsed = urlparse(qdrant_url)
    client = QdrantClient(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6333,
    )

    try:
        collection_info = client.get_collection("healthcore_knowledge")
        points_count = collection_info.points_count
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Qdrant collection not available: {exc}",
        ) from exc

    return HealthResponse(
        status="ok",
        collection="healthcore_knowledge",
        points_count=points_count,
    )


@router.post("/setup", status_code=201)
def setup_knowledge_base() -> dict:
    """(Re)index the knowledge base: chunk, embed, and load into Qdrant.

    This is idempotent via clean-and-reload strategy.
    """
    try:
        index_corpus()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"status": "indexed", "collection": "healthcore_knowledge"}