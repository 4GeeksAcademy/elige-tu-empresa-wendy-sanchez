"""
data/process/rag.py — Chunking, embedding & indexing pipeline.

Responsibilities:
  setup()   — Read corpus, chunk, embed, index into Qdrant.
  embed()   — Convert text → vector using the dedicated embedding model.

These two functions live together because indexing depends on both
chunking (document structure knowledge) and embedding (vector generation).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────
# Loaded from .env — set by 4Geeks for AI Engineering students.
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL",
    "madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b",
)
LLM_API_KEY: str | None = os.getenv("API_KEY")
LLM_HOST: str | None = os.getenv("HOST")

# If no separate embedding key/host, we reuse the same LLM endpoint
# (the provider serves both embeddings and chat on the same API).
EMBEDDING_API_KEY: str | None = os.getenv("EMBEDDING_API_KEY") or LLM_API_KEY
EMBEDDING_HOST: str | None = os.getenv("EMBEDDING_HOST") or LLM_HOST

# Named-entity collection name (must match CONTEXT.md spec).
QDRANT_COLLECTION: str = "healthcore_knowledge"

# Chunks are smaller than raw docs to fit in context windows.
CHUNK_MIN_CHARS: int = 200
CHUNK_MAX_CHARS: int = 500

# Path to the knowledge base folder.
CORPUS_DIR: Path = (
    Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"
)

# ── OpenAI client (dedicated for embeddings) ──────────────────────────
_embed_client: OpenAI | None = None


def _get_embed_client() -> OpenAI:
    """Lazy-init the OpenAI client pointing at the embedding endpoint."""
    global _embed_client
    if _embed_client is None:
        if not EMBEDDING_API_KEY or not EMBEDDING_HOST:
            raise RuntimeError(
                "EMBEDDING_API_KEY / EMBEDDING_HOST not set in .env. "
                "Ensure API_KEY and HOST are configured."
            )
        _embed_client = OpenAI(
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_HOST.rstrip("/") + "/v1",
        )
    return _embed_client


# ── embed() — single responsibility: text → vector ───────────────────


def embed(text: str) -> list[float]:
    """Convert *text* into a dense vector using the dedicated embedding model.

    This function is the **only** place the embedding model is called.
    It is used both for indexing (setup) and for retrieval (query).

    Args:
        text: Plain text to embed.

    Returns:
        A list of floats representing the embedding vector (1024-dim for the
        pplx-embed-v1-0.6b model).

    Raises:
        RuntimeError: If the embedding API is unreachable or returns an error.
    """
    client = _get_embed_client()
    try:
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[text],
        )
    except Exception as exc:
        raise RuntimeError(f"Embedding API call failed: {exc}") from exc

    if not resp.data:
        raise RuntimeError("Embedding API returned empty data.")
    return resp.data[0].embedding


# ── Chunking ──────────────────────────────────────────────────────────


def _parse_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split a Markdown document into (heading, content) sections.

    Returns a list of (section_title, body_text) tuples.
    The first section before any heading gets "introduction" as its title.
    """
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_heading: str = "introduction"
    current_lines: list[str] = []

    for line in lines:
        heading_match = re.match(r"^(#{1,3})\s+(.*)", line)
        if heading_match:
            # flush previous section
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_heading, body))
            current_heading = heading_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # flush last section
    body = "\n".join(current_lines).strip()
    if body:
        sections.append((current_heading, body))

    return sections


def _chunk_section(
    title: str,
    body: str,
    source_document: str,
    language: str,
    chunk_index_start: int = 0,
) -> list[dict[str, Any]]:
    """Split a single section's body into coherent chunks.

    Each chunk is a dict ready to be embedded and indexed.
    """
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    buffer_len = 0

    for para in paragraphs:
        # If adding this paragraph would exceed max chars, flush the buffer.
        if buffer_len + len(para) > CHUNK_MAX_CHARS and buffer:
            chunk_text = "\n\n".join(buffer)
            if len(chunk_text) >= CHUNK_MIN_CHARS:
                chunks.append({
                    "section": title,
                    "text": chunk_text,
                    "source_document": source_document,
                    "language": language,
                })
            buffer = [para]
            buffer_len = len(para)
        else:
            buffer.append(para)
            buffer_len += len(para) + 2  # +2 for the "\n\n" separator

    # flush remaining buffer
    if buffer:
        chunk_text = "\n\n".join(buffer)
        if len(chunk_text) >= CHUNK_MIN_CHARS:
            chunks.append({
                "section": title,
                "text": chunk_text,
                "source_document": source_document,
                "language": language,
            })

    # If a single paragraph is huge (> max_chars), split it by sentences.
    final_chunks: list[dict[str, Any]] = []
    for c in chunks:
        if len(c["text"]) > CHUNK_MAX_CHARS:
            final_chunks.extend(_split_long_chunk(c))
        else:
            final_chunks.append(c)

    # Assign chunk_index
    for i, c in enumerate(final_chunks):
        c["chunk_index"] = chunk_index_start + i

    return final_chunks


def _split_long_chunk(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a single long chunk by sentence boundaries."""
    text = chunk["text"]
    # Simple sentence splitting: look for .!? followed by space and capital letter.
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜ])", text)
    sub_chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    buffer_len = 0

    for sent in sentences:
        if buffer_len + len(sent) > CHUNK_MAX_CHARS and buffer:
            sub_chunks.append({
                **chunk,
                "text": " ".join(buffer),
            })
            buffer = [sent]
            buffer_len = len(sent)
        else:
            buffer.append(sent)
            buffer_len += len(sent) + 1

    if buffer:
        sub_chunks.append({**chunk, "text": " ".join(buffer)})

    return sub_chunks if sub_chunks else [chunk]


def chunk_document(
    file_path: Path,
    source_document: str,
    language: str = "es",
) -> list[dict[str, Any]]:
    """Read a Markdown file and split it into semantically coherent chunks.

    Each chunk carries payload fields required by the Qdrant schema:
    source_document, section, language, chunk_index, text, company.
    """
    text = file_path.read_text(encoding="utf-8")
    sections = _parse_markdown_sections(text)
    all_chunks: list[dict[str, Any]] = []
    chunk_idx = 0

    for title, body in sections:
        section_chunks = _chunk_section(
            title=title,
            body=body,
            source_document=source_document,
            language=language,
            chunk_index_start=chunk_idx,
        )
        all_chunks.extend(section_chunks)
        chunk_idx += len(section_chunks)

    # Tag every chunk with the company name.
    for c in all_chunks:
        c["company"] = "healthcore"

    return all_chunks


# ── Document map — maps source doc names to CONTEXT.md filenames ──────
# These are the 4 required documents listed in CONTEXT.md section 2.
DOCUMENT_MAP: list[dict[str, str]] = [
    {
        "filename": "healthcore-insurance-coverage.es.md",
        "source_document": "insurance-coverage",
        "language": "es",
    },
    {
        "filename": "healthcore-appointment-policy.es.md",
        "source_document": "appointment-policy",
        "language": "es",
    },
    {
        "filename": "healthcore-referral-process.es.md",
        "source_document": "referral-process",
        "language": "es",
    },
    {
        "filename": "healthcore-new-patient-checklist.es.md",
        "source_document": "new-patient-checklist",
        "language": "es",
    },
]


def load_corpus() -> list[dict[str, Any]]:
    """Load all documents from the knowledge base and return chunks.

    Returns:
        A flat list of chunk dicts, each with payload fields + chunk text.
    """
    all_chunks: list[dict[str, Any]] = []
    for entry in DOCUMENT_MAP:
        file_path = CORPUS_DIR / entry["filename"]
        if not file_path.exists():
            logger.warning("Corpus file not found, skipping: %s", file_path)
            continue
        chunks = chunk_document(
            file_path=file_path,
            source_document=entry["source_document"],
            language=entry["language"],
        )
        logger.info(
            "Chunked %s → %d chunks",
            entry["filename"],
            len(chunks),
        )
        all_chunks.extend(chunks)

    logger.info("Total chunks loaded: %d", len(all_chunks))
    return all_chunks


# ── Qdrant indexer ───────────────────────────────────────────────────


def _get_qdrant_url() -> str:
    """Return the Qdrant endpoint URL from env or default to localhost."""
    return os.getenv("QDRANT_URL", "http://localhost:6333")


def _build_point(
    chunk: dict[str, Any],
    vector: list[float],
) -> dict[str, Any]:
    """Build a Qdrant point from a chunk dict + its embedding vector.

    Uses a deterministic UUID derived from source_document + chunk_index.
    This is the foundation for idempotency in the clean-and-reload strategy
    (deterministic IDs make upserts idempotent even without clean-and-reload).
    """
    source = chunk["source_document"]
    idx = chunk["chunk_index"]
    # Deterministic UUID v5 in a namespace-like hash.
    unique_str = f"{source}:{idx}"
    point_id = hashlib.md5(unique_str.encode()).hexdigest()

    return {
        "id": point_id,
        "vector": vector,
        "payload": {
            "company": chunk.get("company", "healthcore"),
            "source_document": source,
            "section": chunk.get("section", ""),
            "language": chunk.get("language", "es"),
            "chunk_index": idx,
            "text": chunk["text"],
        },
    }


def setup() -> None:
    """Read the knowledge base, chunk, embed, and index into Qdrant.

    This function is idempotent in development: it uses **clean-and-reload**
    (deletes the collection if it exists, then recreates it and inserts all
    points).  This avoids duplicates without maintaining external state.

    For production, replace with deterministic-upsert (same deterministic IDs
    used here, but `upsert` instead of `recreate_collection`).

    Raises:
        RuntimeError: If Qdrant is unreachable or embedding/indexing fails.
    """
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import UnexpectedResponse
    from qdrant_client.models import (
        Distance,
        VectorParams,
        CreateCollection,
    )

    # 1. Load corpus → chunks
    chunks = load_corpus()
    if not chunks:
        logger.warning("No chunks loaded — nothing to index.")
        return

    # 2. Connect to Qdrant
    qdrant_url = _get_qdrant_url()
    logger.info("Connecting to Qdrant at %s", qdrant_url)
    client = QdrantClient(host=qdrant_url.replace("http://", "").replace(":6333", ""), port=6333)
    # Actually parse correctly
    from urllib.parse import urlparse
    parsed = urlparse(qdrant_url)
    client = QdrantClient(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6333,
    )

    # 3. Clean-and-reload strategy
    existing = client.get_collections()
    collection_names = [c.name for c in existing.collections]
    if QDRANT_COLLECTION in collection_names:
        logger.info("Recreating collection '%s' (clean-and-reload)", QDRANT_COLLECTION)
        client.delete_collection(QDRANT_COLLECTION)

    logger.info("Creating collection '%s' (dim=%d)", QDRANT_COLLECTION, 1024)
    client.create_collection(
        QDRANT_COLLECTION,
        vectors_config=VectorParams(
            size=1024,
            distance=Distance.COSINE,
        ),
    )

    # 4. Embed & index each chunk
    points: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        vector = embed(chunk["text"])
        point = _build_point(chunk, vector)
        points.append(point)

        # Batch upload every 10 points to avoid large payloads.
        if len(points) >= 10:
            _upload_batch(client, points)
            points = []

    # Upload remaining
    if points:
        _upload_batch(client, points)

    logger.info("Indexing complete: %d chunks in '%s'.", len(chunks), QDRANT_COLLECTION)


def _upload_batch(client: Any, points: list[dict[str, Any]]) -> None:
    """Upload a batch of points to Qdrant."""
    from qdrant_client.models import PointStruct

    batch = [
        PointStruct(
            id=p["id"],
            vector=p["vector"],
            payload=p["payload"],
        )
        for p in points
    ]
    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=batch,
    )
    logger.debug("Uploaded batch of %d points.", len(batch))


# ── CLI entrypoint ───────────────────────────────────────────────────
# Allows running `python -m data.process.rag` to index the corpus.

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup()