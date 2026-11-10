# RAG Design Document — HealthCore Knowledge Base

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                   User Question                      │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│              query(question: str, *, k=5,             │
│                         min_score=0.5) → str          │
│  ┌───────────────┐          ┌──────────────────────┐  │
│  │embed(question)│          │  retrieve(query:     │  │
│  │ → vector      │          │   str, *, k,         │  │
│  └──────┬────────┘          │   min_score)         │  │
│         │                   │ → list[dict]         │  │
│         │                   └────────┬─────────────┘  │
│         │          ┌─────────────────▼────┐           │
│         └─────────►  generate_answer(     │           │
│                    │   question, context) │           │
│                    │   → str              │           │
│                    └──────────────────────┘           │
└───────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 Natural response (str)               │
└──────────────────────────────────────────────────────┘
```

**Five core functions, each with a single responsibility:**

| Function | Module | Responsibility |
|---|---|---|
| `setup()` | `data/process/rag.py` | Read source docs, chunk, embed, index into Qdrant |
| `embed(text)` | `data/process/rag.py` | Convert text → vector using dedicated embedding model |
| `retrieve(query, *, k, min_score)` | `data/pipelines/rag.py` | Embed *query* internally, vector search in Qdrant, return top-k payload dicts |
| `generate_answer(question, context)` | `data/pipelines/rag.py` | Build prompt from chunks + question, call LLM, return plain str |
| `query(question, *, k, min_score)` | `data/pipelines/rag.py` | Orchestrate retrieve + generate_answer, return plain str |

## 2. Models

| Purpose | Model ID | Provider |
|---|---|---|
| **Embedding** | `madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` | 4Geeks AI (OpenRouter) |
| **Generation** | `madrid-spain/openrouter/deepseek/deepseek-v4-flash` | 4Geeks AI (OpenRouter) |

- **Embedding model** produces 1024-dim vectors. Used exclusively in `embed()`.
- **Generation model** is a chat LLM. Used exclusively in `query()`.
- Both accessed via OpenAI-compatible API at `HOST` with `API_KEY`.

## 3. Collection: `healthcore_knowledge`

### Vector config
- Distance: `Cosine`
- Dimension: `1024`

### Payload schema

```json
{
  "company": "healthcore",
  "source_document": "insurance-coverage | appointment-policy | referral-process | new-patient-checklist",
  "section": "header or subsection from source",
  "language": "es",
  "chunk_index": 0,
  "text": "full text of the chunk"
}
```

### Payload indexed fields (for filtering)
- `source_document` — keyword
- `language` — keyword

### Idempotency strategy: **Clean-and-reload**

In development, `setup()` deletes and recreates the collection on each run.
This avoids duplicates without maintaining external ID state.
For production, switch to deterministic UUIDs from chunk content hashes.

**Rationale:** The knowledge base is small (4 documents, ~dozen chunks).
Clean-and-reload is simple, correct, and fast. Deterministic IDs (hash-based)
are documented as the production upgrade path.

## 4. Chunking Strategy

**Per-document, semantic-aware chunking.**

| Document | Sections | Min chunks |
|---|---|---|
| `healthcore-insurance-coverage.es.md` | US coverage, UK coverage, uninsured | ≥3 |
| `healthcore-appointment-policy.es.md` | Booking, cancellation, reminders, no-shows | ≥3 |
| `healthcore-referral-process.es.md` | Process steps, timing, escalation | ≥3 |
| `healthcore-new-patient-checklist.es.md` | Pre-appointment, documents, consent | ≥3 |

**Rules:**
- Never split mid-sentence or mid-paragraph.
- Each chunk is self-contained.
- Headers are used as `section` payload.
- Chunks preserve Markdown structure.

## 5. Retrieval Parameters

| Parameter | Default | Rationale |
|---|---|---|
| `k` | 5 | Recall@3 ≥ 80% target per CONTEXT.md; k=5 gives headroom above the minimum threshold. |
| `min_score` | 0.5 | Cosine similarity floor; avoids noise. Chosen by observing score distribution on test queries. |
| `rerank` | No (v1) | Can be added later as a stateless step between retrieve and generate. |

**Low-score behaviour:** If no chunk exceeds `min_score`, `retrieve()` returns
empty list and `query()` responds: *"No tengo información suficiente en la base de conocimiento para responder esta pregunta."*

## 6. Generation Prompt Template

```
Eres un asistente experto de HealthCore, la red de clínicas ambulatorias.
Responde la pregunta del coordinador usando ÚNICAMENTE la información
de los fragmentos proporcionados a continuación.

Si los fragmentos no contienen la información necesaria, responde:
"No tengo información suficiente en la base de conocimiento para responder
esta pregunta."

Nunca inventes coberturas de seguro, tarifas, ni políticas que no aparezcan
en los fragmentos. Si la pregunta es sobre cobertura de un seguro no listado,
indica que debe verificarse con el equipo de facturación (Tom Callahan).

=== Fragmentos recuperados ===
{context}

=== Pregunta ===
{question}
```

## 7. Test Queries

File: `data/eval/test-queries.json`
8 queries covering all 4 documents, with expected source document & faithfulness check.

## 8. KPI Targets

| KPI | Target | Method |
|---|---|---|
| Recall@3 | ≥ 80% | Manual evaluation against test-queries.json (CONTEXT.md requirement) |
| Faithfulness | 100% | Each response verified against source chunks |
| Threshold coverage | 100% | All queries below threshold return the "no info" answer |

## 9. End-to-End RAG Flow

The following numbered sequence traces a question from the coordinator through
the entire pipeline to the final answer.

```
┌─────────┐     ┌──────────────────┐     ┌────────────┐
│  User   │     │ FastAPI Router   │     │  Qdrant    │
│  Query  │ ──► │ /knowledge/query │     │  (vector   │
│         │     │ POST             │     │   store)   │
└─────────┘     └────────┬─────────┘     └────────────┘
                         │                       ▲
                         ▼                       │
                  ┌──────────────┐               │
                  │ query()      │               │
                  │  (orchestr.) │               │
                  └──────┬───────┘               │
                         │                       │
              ┌──────────▼──────────┐            │
              │  1. retrieve()      │────────────┘
              │     embed(query)    │  2. query_points()
              │     → vector        │     (cosine, 1024d)
              │     → Qdrant search │
              │     → chunks[ ]     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 3. generate_answer() │
              │    _build_context()  │ ──► prompt with chunks
              │    _generate()       │ ──► LLM call
              │    → str             │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 4. Response          │
              │    {"answer": "..."} │
              └──────────────────────┘
```

### Step-by-step

| Step | What happens | Code location |
|---|---|---|
| **0. Setup (one-time)** | `setup()` reads 4 `.es.md` files from `docs/company-knowledge-base/`, parses them into Markdown sections, chunks each section (min 200 chars, max 1500 chars per chunk), embeds every chunk with `embed()`, and indexes into Qdrant collection `healthcore_knowledge`. | `data/process/rag.py::setup()` → `load_corpus()` → `chunk_document()` → `embed()` → Qdrant upsert |
| **1. Retrieve** | `query("¿Qué seguros?")` calls `retrieve("¿Qué seguros?")`. Inside `retrieve()`: (a) imports and calls `embed("¿Qué seguros?")` from `data.process.rag` — this calls the **embedding** model (`pplx-embed-v1-0.6b`, 1024‑dim), not the generation model. (b) Sends the resulting vector to Qdrant via `query_points()` with `cosine` distance, `limit=k` (default 5), `score_threshold=min_score` (default 0.5). (c) Returns payload dicts with `_score` appended. | `data/pipelines/rag.py::retrieve()` |
| **2. Filter by threshold** | Qdrant returns at most `k` results, but `score_threshold` excludes any below 0.5. If **all** results are below threshold, `retrieve()` returns `[]`. This satisfies the CONTEXT.md rule: no info → no invented facts. | `query_points(…, score_threshold=…)` |
| **3. Build context** | `generate_answer()` receives the chunk list. `_build_context()` formats each chunk as `[Fuente N: doc — section]\ntext`, joined by double newlines. If the list is empty, `NO_CHUNKS_MESSAGE` is returned immediately without calling the LLM. | `data/pipelines/rag.py::generate_answer()` → `_build_context()` |
| **4. Generate** | `_generate()` fills the `SYSTEM_PROMPT` template with `{context}` and `{question}`, then calls the **generation** model (`deepseek-v4-flash`, chat completions, temperature 0.3, max_tokens 2000). The plain-text answer is returned. A fallback handles `content=None` (reasoning models) by extracting the last sentence from `reasoning_content`. | `data/pipelines/rag.py::_generate()` |
| **5. Response** | The string bubbles back: `_generate()` → `generate_answer()` → `query()` → `query_knowledge()` → `QueryResponse(answer=…)` → HTTP 200 JSON. | `services/api/routes/knowledge.py::query_knowledge()` |

### What does NOT happen
- Raw chunks or similarity scores are **never** returned to the user.
- The embedding model (`pplx-embed-v1-0.6b`) is **never** used for generation, and vice versa.
- No prompt engineering or business logic leaks into the endpoints — they only call `query()` / `retrieve()` + `generate_answer()`.

---

## 10. Chunking Strategy — Detailed

_See §4 for the summary; this section provides the full technical details._

### Why this strategy fits the corpus

The 4 source documents are short, structured Markdown files (each ≈1 000 chars, single top‑level heading). Because of this:

1. **Every document fits in one chunk.** Each doc has one `# Title` heading followed by paragraphs. The chunker reads the whole section body, and since it's under `CHUNK_MAX_CHARS=1500`, it stays as a single chunk. No splitting across sections is needed.

2. **Semantic units are naturally preserved.** Each document is about one topic: insurance coverage, appointment policy, referral process, or new-patient checklist. Keeping each as one chunk guarantees no rule or condition is cut mid‑paragraph.

3. **Headers become section metadata.** The `# Title` is parsed by `_parse_markdown_sections()` and becomes the `section` payload field. This lets the LLM know exactly which document the chunk came from.

### Parameters

| Parameter | Value | Why |
|---|---|---|
| `CHUNK_MIN_CHARS` | 200 | Discard near‑empty sections (no document is below this). |
| `CHUNK_MAX_CHARS` | 1 500 | Safety limit; if a document grows in the future, paragraphs still accumulate into buffers that are flushed at this boundary. No paragraph is ever split. |
| `Overlap` | 0 (none) | Documents are short and single‑topic; overlap would add duplicate vectors without benefit. |

### Actual chunk counts

| Document | Chunks | Section heading | Size range (chars) |
|---|---|---|---|
| `healthcore-insurance-coverage.es.md` | 1 | `Cobertura de Seguros Aceptados` | 1 090 |
| `healthcore-appointment-policy.es.md` | 1 | `Política de Citas y Cancelaciones` | 952 |
| `healthcore-referral-process.es.md` | 1 | `Proceso de Referencia Interna` | 1 132 |
| `new-patient-checklist.es.md` | 1 | `Checklist para Pacientes Nuevos` | 943 |
| **Total** | **4** | — | 943–1 132 |

### What was avoided
- **Mid‑paragraph cuts.** The chunker accumulates whole paragraphs and only flushes when the next paragraph would push the buffer over `CHUNK_MAX_CHARS`. This guarantees coherent units.
- **Lost section context.** The section heading is recorded per‑chunk, so even if a future document were large enough to split, each chunk would still carry its section name.
- **Orphaned business rules.** Rules like "Medicare/Medicaid patients: no no-show charge" are short paragraphs that fit comfortably. A chunker that splits by fixed token count could have separated the condition ("Medicare/Medicaid") from the consequence ("no charge").

---

## 11. Embedding Practices

### Model separation

| Role | Model ID | Client variable | Used in |
|---|---|---|---|
| **Embedding** | `madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` | `_embed_client` (`data/process/rag.py`) | `embed()` during index (setup) and retrieval (retrieve) |
| **Generation** | `madrid-spain/openrouter/deepseek/deepseek-v4-flash` | `_gen_client` (`data/pipelines/rag.py`) | `_generate()` only |

Both are provided by 4Geeks Academy's OpenRouter endpoint. The embedding model is **not** used for generation and the generation model is **not** used for embeddings. They are completely separate clients with separate API keys (or the same key at the same host, if `EMBEDDING_API_KEY`/`EMBEDDING_HOST` are not overridden in `.env`).

### Consistent use of embed()

`embed()` lives in `data/process/rag.py` and is the **only** function that calls the embedding API. It is used:
- **At index time:** `setup()` → `load_corpus()` → `chunk_document()` → `embed(chunk["text"])` for every chunk.
- **At retrieval time:** `retrieve()` imports `from data.process.rag import embed` (inside the function body, to avoid circular imports) and calls `embed(query)` to convert the user's question into a vector.

Because the same `embed()` function is called in both paths, the vector representation is guaranteed to be identical for the same text, whether it appears as a stored chunk or as a query.

### Vector details

| Property | Value |
|---|---|
| Model | `pplx-embed-v1-0.6b` (Perplexity, via OpenRouter) |
| Output dimension | **1024** |
| Distance metric | **Cosine** (configured in Qdrant `VectorParams`) |
| Qdrant search | `client.query_points(…, score_threshold=…)` — returns ≤k results, sorted by similarity descending |

### Similarity threshold (min_score)

| Aspect | Detail |
|---|---|
| Default | `0.5` |
| How it's applied | Passed as `score_threshold` to Qdrant's `query_points()`. When `min_score=0.0`, the threshold is disabled (`None` sent to Qdrant, returning all k results). |
| Why 0.5 | Chosen empirically by running the 8 test queries and observing the distribution of cosine scores. Scores ≥ 0.5 consistently return relevant chunks; scores below 0.5 are noise from unrelated topics. |
| Behaviour when no chunks pass | `retrieve()` returns `[]` → `generate_answer([])` returns `NO_CHUNKS_MESSAGE` → the user sees "No encontré información relevante…". |
| Tuning notes | 0.5 is conservative. With only 4 chunks in the corpus, in practice the top‑1 score is usually > 0.7 for relevant questions. The threshold mainly protects against off‑topic questions returning low‑scoring false positives. |

### Preprocessing before embedding

The pipeline applies **minimal, idempotent preprocessing** — only what is needed to produce a clean text string for the embedding model:

1. **Strip whitespace** from each paragraph (`p.strip()`) and from section headings (`heading_match.group(2).strip()`).
2. **Normalise line endings** by reading the file with `read_text(encoding="utf‑8")` — no CRLF→LF conversion needed on modern systems.
3. **No lowercasing, no stop‑word removal, no stemming.** These techniques are not beneficial for embedding models based on transformer architectures (which are subword‑tokenised and handle casing naturally).
4. **No HTML/entity unescaping.** The source documents are plain Markdown without HTML entities.

The same preprocessing is applied at index time (through `chunk_document()`) and at retrieval time (the user's question is passed to `embed()` as‑is, stripped only by the caller). This ensures the embedding sees text in the same format in both paths.

### Embedding API configuration

```python
# data/process/rag.py
EMBEDDING_MODEL = "madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b"
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY") or os.getenv("API_KEY")
EMBEDDING_HOST    = os.getenv("EMBEDDING_HOST")    or os.getenv("HOST")

client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_HOST + "/v1")
resp = client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
vector = resp.data[0].embedding
```

The same OpenAI‑compatible library (`openai` Python package) handles both embeddings and chat completions, but with different client instances pointing at different base URLs or models.

---

## 12. Files Layout

```
docs/company-knowledge-base/
  healthcore-insurance-coverage.es.md       ← Source corpus
  healthcore-appointment-policy.es.md       ← Source corpus
  healthcore-referral-process.es.md         ← Source corpus
  healthcore-new-patient-checklist.es.md    ← Source corpus
data/process/rag.py                         ← setup(), embed()
data/pipelines/rag.py                       ← retrieve(), query()
services/api/routes/rag.py                  ← FastAPI router
uis/website/app/rag/page.tsx                ← UI component
tests/pipelines/test_rag.py                 ← Unit tests
docs/rag/rag-design.md                      ← This document
data/eval/test-queries.json                 ← Evaluation queries
```

## 13. Production Upgrade Path

1. Deterministic UUIDs (hash of `source_document + chunk_index + text`) instead of clean-and-reload.
2. Add reranker (e.g., Cohere or BGE) between retrieve and generate.
3. Query expansion / HyDE for better retrieval.
4. Add streaming responses from the generation model.
5. A/B evaluation framework for chunk size and retrieval parameters.