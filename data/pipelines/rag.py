"""
data/pipelines/rag.py — Retrieval & generation pipeline.

Responsibilities:
  retrieve()        — Given a question string, embed it, search Qdrant, and
                      return top-k relevant chunk payloads.
  generate_answer() — Build prompt from chunks + question and call the
                      generation LLM.
  query()           — End-to-end: retrieve context, generate final answer via
                      LLM.  Returns a plain string.

These three functions are separated so:
  - retrieve() and generate_answer() can be used independently by future
    agents (e.g. a LangGraph agent that needs to reuse both without
    re-embedding or re-wrapping the monolithic query).
  - The team can swap out the retriever (e.g., replace Qdrant with Pinecone)
    or the generator (e.g., swap DeepSeek for GPT) independently.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────
GENERATION_MODEL: str = os.getenv(
    "GENERATION_MODEL",
    "madrid-spain/openrouter/deepseek/deepseek-v4-flash",
)
LLM_API_KEY: str | None = os.getenv("API_KEY")
LLM_HOST: str | None = os.getenv("HOST")

# Qdrant collection name (must match data/process/rag.py).
QDRANT_COLLECTION: str = "healthcore_knowledge"

# Retrieval defaults.
DEFAULT_K: int = 5
DEFAULT_MIN_SCORE: float = 0.3

# ── OpenAI client (dedicated for generation — NEVER used for embeddings) ──
_gen_client: OpenAI | None = None


def _get_gen_client() -> OpenAI:
    """Lazy-init the OpenAI client pointing at the LLM generation endpoint."""
    global _gen_client
    if _gen_client is None:
        if not LLM_API_KEY or not LLM_HOST:
            raise RuntimeError(
                "API_KEY / HOST not set in .env. "
                "Cannot initialise generation client."
            )
        _gen_client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_HOST.rstrip("/") + "/v1",
        )
    return _gen_client


# ── Qdrant client ────────────────────────────────────────────────────
_qdrant_client: Any | None = None


def _get_qdrant_client() -> Any:
    """Lazy-init the Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from urllib.parse import urlparse

        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        parsed = urlparse(qdrant_url)
        _qdrant_client = QdrantClient(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6333,
        )
    return _qdrant_client


# ── retrieve() — embed + vector search ───────────────────────────────


def retrieve(
    query: str,
    *,
    k: int = DEFAULT_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[dict[str, Any]]:
    """Embed *query*, then search Qdrant for the *k* most similar chunks.

    Points below *min_score* cosine similarity are excluded.  Returns
    plain payload dicts (not raw Qdrant SDK objects).

    Args:
        query: Natural language question (embedded internally).
        k: Number of nearest neighbours to retrieve.
        min_score: Minimum cosine similarity threshold; results below
            this are discarded.  Set to 0.0 to disable.

    Returns:
        A list of payload dicts, each containing at minimum:
        ``source_document``, ``section``, ``text``, ``chunk_index``,
        ``language``, ``company``, and ``_score``.

        Ordered by descending similarity.  Empty list if no results
        meet the threshold.

    Raises:
        RuntimeError: If Qdrant or the embedding API is unreachable.
    """
    from data.process.rag import embed

    vector = embed(query)
    client = _get_qdrant_client()
    try:
        resp = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vector,
            limit=k,
            score_threshold=min_score if min_score > 0.0 else None,
            with_payload=True,
        )
    except Exception as exc:
        raise RuntimeError(f"Qdrant search failed: {exc}") from exc

    chunks: list[dict[str, Any]] = []
    for hit in resp.points:
        payload = hit.payload or {}
        payload["_score"] = round(hit.score, 4)
        chunks.append(payload)

    logger.info("Retrieved %d chunks (k=%d, min_score=%.2f).", len(chunks), k, min_score)
    return chunks


# ── Generation ───────────────────────────────────────────────────────

SYSTEM_PROMPT: str = (
    "Eres un asistente experto de HealthCore, la red de clínicas ambulatorias. "
    "Responde la pregunta del coordinador usando ÚNICAMENTE la información "
    "de los fragmentos proporcionados a continuación.\n\n"
    "Si los fragmentos no contienen la información necesaria, responde:\n"
    '"No tengo información suficiente en la base de conocimiento para responder esta pregunta."\n\n'
    "Nunca inventes coberturas de seguro, tarifas, ni políticas que no aparezcan "
    "en los fragmentos. Si la pregunta es sobre cobertura de un seguro no listado, "
    "indica que debe verificarse con el equipo de facturación (Tom Callahan).\n\n"
    "=== Fragmentos recuperados ===\n{context}\n\n"
    "=== Pregunta ===\n{question}\n\n"
    "=== Respuesta ==="
)

NO_INFO_MESSAGE: str = (
    "No tengo información suficiente en la base de conocimiento "
    "para responder esta pregunta."
)

NO_CHUNKS_MESSAGE: str = (
    "No encontré información relevante en la base de conocimiento "
    "para responder tu pregunta. Intenta reformularla o contacta a "
    "tu coordinador de pacientes."
)


def _build_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a single context string for the prompt."""
    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Fuente {i}: {chunk.get('source_document', 'desconocida')} "
            f"— {chunk.get('section', 'general')}]\n"
            f"{chunk.get('text', '')}"
        )
    return "\n\n".join(parts)


def _generate(
    question: str,
    context: str,
    system_prompt: str | None = None,
) -> str:
    """Call the generation LLM with a prompt built from context + question.

    Uses the **generation** model only — never the embedding model.
    """
    client = _get_gen_client()
    prompt = (system_prompt or SYSTEM_PROMPT).format(
        context=context,
        question=question,
    )

    try:
        resp = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
    except Exception as exc:
        raise RuntimeError(f"Generation API call failed: {exc}") from exc

    message = resp.choices[0].message
    # Some reasoning models (e.g. DeepSeek v4 Flash) may return content as None
    # when all available tokens are consumed by reasoning.  In that case, try to
    # fall back to the last sentence of the reasoning content, or return the
    # standard no-info message.
    content = message.content

    if content is None:
        logger.warning("Generation returned content=None (reasoning consumed all tokens).")
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            # Extract last sentence as a fallback answer
            sentences = reasoning.strip().split(". ")
            if len(sentences) > 1:
                fallback = sentences[-1].rstrip(".")
                if fallback:
                    return fallback.strip()
        return NO_INFO_MESSAGE

    if not content.strip():
        logger.warning("Generation returned empty content.")
        return NO_INFO_MESSAGE

    return content.strip()


# ── generate_answer() — public, separate generation step ─────────────


def generate_answer(question: str, context: list[dict[str, Any]]) -> str:
    """Generate a final answer from *question* and retrieved *context* chunks.

    This is a **public** function so future agents (e.g. LangGraph) can call
    retrieve() and generate_answer() as independent steps without re-embedding
    or re-wrapping a monolithic query().

    Args:
        question: The original user question.
        context: List of chunk dicts returned by retrieve().

    Returns:
        The generated answer as a plain string.
    """
    if not context:
        logger.info("generate_answer called with empty context.")
        return NO_CHUNKS_MESSAGE

    context_str = _build_context(context)
    return _generate(
        question=question,
        context=context_str,
    )


# ── query() — end-to-end orchestrator ────────────────────────────────

# NOTE: This is the ONLY function that external consumers (endpoints, agents)
# should call.  It composes retrieve() + generate_answer().


def query(
    question: str,
    *,
    k: int = DEFAULT_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> str:
    """Answer a *question* using the RAG pipeline.

    This is the **only** function that external consumers should call.
    It composes ``retrieve()`` + ``generate_answer()``, ensuring the
    orchestration logic lives in one place.

    Steps:
        1. Retrieve relevant chunks from Qdrant (embeds internally).
        2. Generate a final answer via LLM using the chunks as context.

    The response **never** returns raw chunks to the user — it always goes
    through the LLM.

    Args:
        question: Natural language question from a coordinator.
        k: Number of chunks to retrieve.
        min_score: Minimum similarity threshold (cosine).

    Returns:
        The generated answer as a plain string.
    """
    logger.info("Query: '%s'", question[:100])

    chunks = retrieve(question, k=k, min_score=min_score)
    return generate_answer(question=question, context=chunks)
