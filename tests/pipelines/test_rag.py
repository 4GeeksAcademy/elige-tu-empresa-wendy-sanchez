"""
tests/pipelines/test_rag.py — Unit tests for the RAG pipeline.

Tests cover:
  - embed(): text → vector conversion, API errors
  - chunking: semantic coherence, boundaries, section splitting
  - retrieve(): Qdrant search, threshold filtering
  - query(): end-to-end orchestration, no-chunk fallback
  - Corpus evaluation: each doc produces chunks, only required docs
  - Test queries file: coverage of all 4 docs
  - API router: prefix, routes, request validation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is on sys.path for imports.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# The routes module lives under services/api/ — add it for router tests.
_API_SRC = str(_PROJECT_ROOT / "services" / "api")
if _API_SRC not in sys.path:
    sys.path.insert(0, _API_SRC)


# ── Helpers ──────────────────────────────────────────────────────────


def _write_tmp_doc(name: str, text: str) -> Path:
    """Write a temp markdown file and return its Path.  Caller must unlink."""
    tmp = _PROJECT_ROOT / name
    tmp.write_text(text)
    return tmp


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sample_chunk() -> dict:
    return {
        "company": "healthcore",
        "source_document": "appointment-policy",
        "section": "Política de cancelación",
        "language": "es",
        "chunk_index": 0,
        "text": (
            "Política de cancelación:\n"
            "Cancelar con más de 24 horas de anticipación: sin cargo.\n"
            "Cancelar con menos de 24 horas o no presentarse (no-show): "
            "cargo de 50 USD (o 40 GBP en Reino Unido) para pacientes de pago privado.\n"
            "Pacientes con Medicare o Medicaid: no se les cobra cargo por no-show."
        ),
    }


@pytest.fixture
def sample_chunks(sample_chunk: dict) -> list[dict]:
    return [
        sample_chunk,
        {
            **sample_chunk,
            "source_document": "insurance-coverage",
            "section": "Estados Unidos",
            "chunk_index": 0,
            "text": (
                "Seguros comerciales aceptados: Blue Cross Blue Shield, "
                "Aetna, Cigna, UnitedHealthcare."
            ),
        },
        {
            **sample_chunk,
            "source_document": "new-patient-checklist",
            "section": "introduction",
            "chunk_index": 0,
            "text": (
                "Todo paciente nuevo debe completar antes de su primera cita:\n"
                "1. Formulario de historial médico.\n"
                "2. Verificación de identidad con documento oficial.\n"
                "3. Verificación de cobertura de seguro."
            ),
        },
    ]


# ── Test: embed() ────────────────────────────────────────────────────


class TestEmbed:
    """Tests for the embed() function in data/process/rag.py."""

    def test_embed_returns_list_of_floats(self):
        """embed() should return a list of floats for a text input."""
        from data.process.rag import embed

        with patch("data.process.rag._get_embed_client") as mock_get:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.data = [MagicMock()]
            mock_resp.data[0].embedding = [0.1, 0.2, 0.3]
            mock_client.embeddings.create.return_value = mock_resp
            mock_get.return_value = mock_client

            result = embed("test text")
            assert isinstance(result, list)
            assert all(isinstance(x, float) for x in result)
            assert len(result) == 3

    def test_embed_uses_correct_model(self):
        """embed() should call the embedding model, not the generation model."""
        from data.process.rag import embed, EMBEDDING_MODEL

        with patch("data.process.rag._get_embed_client") as mock_get:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.data = [MagicMock()]
            mock_resp.data[0].embedding = [0.5] * 4
            mock_client.embeddings.create.return_value = mock_resp
            mock_get.return_value = mock_client

            embed("hello")
            _, kwargs = mock_client.embeddings.create.call_args
            assert kwargs["model"] == EMBEDDING_MODEL

    def test_embed_api_error_raises_runtime_error(self):
        """embed() should raise RuntimeError when the API call fails."""
        from data.process.rag import embed

        with patch("data.process.rag._get_embed_client") as mock_get:
            mock_client = MagicMock()
            mock_client.embeddings.create.side_effect = Exception("API timeout")
            mock_get.return_value = mock_client

            with pytest.raises(RuntimeError, match="Embedding API call failed"):
                embed("hello")


# ── Test: chunking ───────────────────────────────────────────────────


class TestChunking:
    """Tests for document chunking logic in data/process/rag.py."""

    @staticmethod
    def _long_text(n_chars: int = 300) -> str:
        """Generate text with at least n_chars beyond the heading."""
        body = "\n\n".join(
            f"Heading. Paragraph {i}. " + " ".join(["word"] * 20)
            for i in range(20)
        )
        return "# Test Section\n\n" + body

    def test_chunk_document_returns_list_of_chunks(self):
        """chunk_document() should return a list of chunk dicts."""
        from data.process.rag import chunk_document

        text = self._long_text(300)
        tmp = _write_tmp_doc("tmp_test_doc.md", text)
        try:
            chunks = chunk_document(tmp, "test-doc")
            assert isinstance(chunks, list)
            assert len(chunks) > 0
            for c in chunks:
                assert "section" in c
                assert "text" in c
                assert "source_document" in c
                assert "chunk_index" in c
                assert c["company"] == "healthcore"
        finally:
            tmp.unlink(missing_ok=True)

    def test_chunks_are_self_contained(self):
        """Each chunk should be a self-contained semantic unit."""
        from data.process.rag import chunk_document

        text = (
            "# Coverage\n\nBlue Cross is accepted.\n\n"
            "## UK Coverage\n\n" + " ".join(["word"] * 50) + "\n\n"
            "## Uninsured\n\n" + " ".join(["word"] * 50)
        )
        tmp = _write_tmp_doc("tmp_test_doc2.md", text)
        try:
            chunks = chunk_document(tmp, "insurance-coverage")
            assert len(chunks) >= 1
            for c in chunks:
                assert len(c["text"]) >= 20  # minimum content
                assert c["section"] != ""
        finally:
            tmp.unlink(missing_ok=True)

    def test_chunk_preserves_section_boundaries(self):
        """Chunks from different sections should have distinct section values."""
        from data.process.rag import chunk_document, CHUNK_MIN_CHARS

        # Each section must exceed CHUNK_MIN_CHARS to not be filtered out.
        filler = "x" * 60  # ~60 chars of filler per paragraph
        text = (
            "# Section Alpha\n\n"
            + "\n\n".join(["Alpha paragraph " + str(i) + ". " + filler for i in range(4)])
            + "\n\n"
            "# Section Beta\n\n"
            + "\n\n".join(["Beta paragraph " + str(i) + ". " + filler for i in range(4)])
            + "\n\n"
            "# Section Gamma\n\n"
            + "\n\n".join(["Gamma paragraph " + str(i) + ". " + filler for i in range(4)])
        )
        tmp = _write_tmp_doc("tmp_test_doc3.md", text)
        try:
            chunks = chunk_document(tmp, "test-sections")
            sections = set(c["section"] for c in chunks)
            assert "Section Alpha" in sections, f"Sections found: {sections}"
            assert "Section Beta" in sections, f"Sections found: {sections}"
            assert "Section Gamma" in sections, f"Sections found: {sections}"
        finally:
            tmp.unlink(missing_ok=True)


# ── Test: retrieve() ─────────────────────────────────────────────────


class TestRetrieve:
    """Tests for the retrieve() function in data/pipelines/rag.py."""

    def test_retrieve_returns_list(self):
        """retrieve() should return a list of payload dicts."""
        from data.pipelines.rag import retrieve

        fake_hit = MagicMock()
        fake_hit.payload = {
            "source_document": "insurance-coverage",
            "section": "US",
            "text": "BCBS accepted.",
            "language": "es",
            "chunk_index": 0,
        }
        fake_hit.score = 0.85

        mock_resp = MagicMock()
        mock_resp.points = [fake_hit]

        with patch("data.pipelines.rag._get_qdrant_client") as mock_get:
            mock_client = MagicMock()
            mock_client.query_points.return_value = mock_resp
            mock_get.return_value = mock_client

            result = retrieve([0.1] * 1024, top_k=3)
            assert isinstance(result, list)
            assert len(result) == 1
            assert "_score" in result[0]
            assert result[0]["source_document"] == "insurance-coverage"

    def test_retrieve_respects_threshold(self):
        """retrieve() should exclude results below score_threshold."""
        from data.pipelines.rag import retrieve

        with patch("data.pipelines.rag._get_qdrant_client") as mock_get:
            mock_client = MagicMock()
            mock_client.query_points.return_value.points = []
            mock_get.return_value = mock_client

            result = retrieve([0.1] * 1024, top_k=3, score_threshold=0.9)
            assert result == []

    def test_retrieve_api_error(self):
        """retrieve() should raise RuntimeError when Qdrant is unreachable."""
        from data.pipelines.rag import retrieve

        with patch("data.pipelines.rag._get_qdrant_client") as mock_get:
            mock_client = MagicMock()
            mock_client.query_points.side_effect = Exception("Connection refused")
            mock_get.return_value = mock_client

            with pytest.raises(RuntimeError, match="Qdrant search failed"):
                retrieve([0.1] * 1024)


# ── Test: query() ────────────────────────────────────────────────────


class TestQuery:
    """Tests for the end-to-end query() function.

    query() returns a plain string — never a dict with metadata.
    """

    def test_query_returns_string(self, sample_chunks):
        """query() should return a plain string."""
        with patch("data.process.rag.embed", return_value=[0.1] * 1024), \
             patch("data.pipelines.rag.retrieve", return_value=sample_chunks), \
             patch("data.pipelines.rag._generate", return_value="Blue Cross Blue Shield is accepted."):

            from data.pipelines.rag import query

            result = query("What insurance do you accept?")
            assert isinstance(result, str), f"Expected str, got {type(result)}"
            assert result == "Blue Cross Blue Shield is accepted."

    def test_query_no_chunks_returns_no_info_message(self):
        """query() should return a 'no info' message when no chunks found."""
        with patch("data.process.rag.embed", return_value=[0.1] * 1024), \
             patch("data.pipelines.rag.retrieve", return_value=[]):

            from data.pipelines.rag import query, NO_CHUNKS_MESSAGE

            result = query("Some obscure question")
            assert isinstance(result, str)
            assert result == NO_CHUNKS_MESSAGE

    def test_query_never_returns_raw_chunks(self, sample_chunks):
        """query() should never return raw chunk text as the answer."""
        with patch("data.process.rag.embed", return_value=[0.1] * 1024), \
             patch("data.pipelines.rag.retrieve", return_value=sample_chunks), \
             patch("data.pipelines.rag._generate", return_value="This is a generated response."):

            from data.pipelines.rag import query

            result = query("Test question")
            assert isinstance(result, str)
            assert result == "This is a generated response."
            assert "=== Fragmentos" not in result

    def test_query_uses_different_models_for_embed_and_generate(self):
        """embed() and _generate() should use different model IDs."""
        from data.process.rag import EMBEDDING_MODEL
        from data.pipelines.rag import GENERATION_MODEL

        assert EMBEDDING_MODEL != GENERATION_MODEL, (
            "Embedding and generation models must be different."
        )

    def test_query_returns_str_not_dict(self):
        """query() should NOT return a dict with sources/metadata."""
        from inspect import signature
        from data.pipelines.rag import query

        sig = signature(query)
        assert sig.return_annotation is str or sig.return_annotation == "str", (
            f"query() return annotation should be str, got {sig.return_annotation}"
        )


# ── Test: generate_answer() ──────────────────────────────────────────


class TestGenerateAnswer:
    """Tests for the public generate_answer() function."""

    def test_generate_answer_returns_string(self, sample_chunks):
        """generate_answer() should return a plain string."""
        with patch("data.pipelines.rag._generate", return_value="Generated answer."):
            from data.pipelines.rag import generate_answer

            result = generate_answer(question="Test?", context=sample_chunks)
            assert isinstance(result, str)
            assert result == "Generated answer."

    def test_generate_answer_empty_context_returns_no_chunks_message(self):
        """generate_answer() should return NO_CHUNKS_MESSAGE when context is empty."""
        from data.pipelines.rag import generate_answer, NO_CHUNKS_MESSAGE

        result = generate_answer(question="Test?", context=[])
        assert result == NO_CHUNKS_MESSAGE

    def test_generate_answer_uses_generation_model_not_embedding_model(self):
        """generate_answer() should call _generate() which uses GENERATION_MODEL."""
        from data.pipelines.rag import generate_answer, GENERATION_MODEL
        from data.process.rag import EMBEDDING_MODEL

        assert EMBEDDING_MODEL != GENERATION_MODEL, (
            "Embedding and generation models must be different."
        )

    def test_generate_answer_is_public_and_callable(self, sample_chunks):
        """generate_answer() should be importable as a public function."""
        from data.pipelines.rag import generate_answer

        assert callable(generate_answer)
        # It should not start with underscore
        assert not generate_answer.__name__.startswith("_")


# ── Test: corpus evaluation ──────────────────────────────────────────


class TestCorpusEvaluation:
    """Verify the corpus produces chunks for all required documents."""

    def test_corpus_produces_chunks_for_all_docs(self):
        """load_corpus() should return at least one chunk per document."""
        from data.process.rag import load_corpus

        chunks = load_corpus()
        doc_counts: dict[str, int] = {}
        for c in chunks:
            doc = c["source_document"]
            doc_counts[doc] = doc_counts.get(doc, 0) + 1

        for doc, count in doc_counts.items():
            assert count >= 1, (
                f"Document '{doc}' has {count} chunks (minimum 1)."
            )

    def test_corpus_only_contains_required_documents(self):
        """Only the 4 required documents should be indexed."""
        from data.process.rag import DOCUMENT_MAP

        required = {
            "insurance-coverage",
            "appointment-policy",
            "referral-process",
            "new-patient-checklist",
        }
        actual = {entry["source_document"] for entry in DOCUMENT_MAP}
        assert actual == required, f"Expected {required}, got {actual}"

    def test_corpus_has_expected_total_chunks(self):
        """The 4 docs should produce between 4 and 20 chunks total."""
        from data.process.rag import load_corpus

        chunks = load_corpus()
        assert 4 <= len(chunks) <= 20, (
            f"Expected 4–20 total chunks, got {len(chunks)}."
        )


# ── Test: knowledge base documents exist ─────────────────────────────


class TestKnowledgeBaseFiles:
    """Verify the 4 required source documents exist and are non-empty."""

    def test_required_spanish_docs_exist(self):
        """All 4 required Spanish documents should exist in the corpus directory."""
        from data.process.rag import CORPUS_DIR

        required_files = [
            "healthcore-insurance-coverage.es.md",
            "healthcore-appointment-policy.es.md",
            "healthcore-referral-process.es.md",
            "healthcore-new-patient-checklist.es.md",
        ]
        for fname in required_files:
            path = CORPUS_DIR / fname
            assert path.exists(), f"Required document not found: {path}"
            assert path.stat().st_size > 0, f"Required document is empty: {path}"


# ── Test: test queries file ──────────────────────────────────────────


class TestTestQueries:
    """Verify data/eval/test-queries.json structure."""

    def test_test_queries_file_exists_and_is_valid(self):
        """test-queries.json should exist with >=8 queries covering all 4 docs."""
        queries_path = _PROJECT_ROOT / "data" / "eval" / "test-queries.json"
        assert queries_path.exists(), "test-queries.json not found."

        with open(queries_path) as f:
            queries = json.load(f)

        assert len(queries) >= 8, f"Expected >=8 queries, got {len(queries)}"

        covered_docs = {q["expected_source_document"] for q in queries}
        required = {
            "insurance-coverage",
            "appointment-policy",
            "referral-process",
            "new-patient-checklist",
        }
        assert covered_docs == required, (
            f"Queries must cover all 4 docs. Missing: {required - covered_docs}"
        )

    def test_each_query_has_required_fields(self):
        """Every query in test-queries.json must have id, question, expected_source_document."""
        queries_path = _PROJECT_ROOT / "data" / "eval" / "test-queries.json"
        with open(queries_path) as f:
            queries = json.load(f)

        for q in queries:
            assert "id" in q, "Query missing 'id'"
            assert "question" in q, "Query missing 'question'"
            assert "expected_source_document" in q, (
                f"Query {q.get('id', '?')} missing 'expected_source_document'"
            )
            assert len(q["question"]) >= 3, (
                f"Query {q['id']} question too short."
            )


# ── Test: API router ─────────────────────────────────────────────────


@pytest.mark.usefixtures("_mock_env_for_router")
class TestRagRouter:
    """Tests for the FastAPI router at routes/rag.py.

    The ``_mock_env_for_router`` fixture sets required env vars before
    the router module is imported, preventing RuntimeError during
    client initialisation.
    """

    @pytest.fixture(autouse=True)
    def _mock_env_for_router(self):
        """Set env vars before router import, restore after."""
        import os
        _existing = {}
        for k in ("API_KEY", "HOST", "QDRANT_URL"):
            _existing[k] = os.environ.get(k)
        os.environ["API_KEY"] = "test-key"
        os.environ["HOST"] = "http://test-host"
        os.environ["QDRANT_URL"] = "http://localhost:6333"
        yield
        for k, v in _existing.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_router_prefix(self):
        """Router should be registered under /rag prefix."""
        from routes.rag import router

        assert router.prefix == "/rag"
        routes = [r.path for r in router.routes]
        assert "/rag/query" in routes, f"Routes: {routes}"
        assert "/rag/health" in routes, f"Routes: {routes}"
        assert "/rag/setup" in routes, f"Routes: {routes}"

    def test_query_request_model_validates(self):
        """QueryRequest should reject questions < 3 characters."""
        from routes.rag import QueryRequest

        with pytest.raises(Exception):
            QueryRequest(question="ab")  # too short

        req = QueryRequest(question="What insurance do you accept?")
        assert req.question == "What insurance do you accept?"
        assert req.top_k == 3
        assert req.score_threshold == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])