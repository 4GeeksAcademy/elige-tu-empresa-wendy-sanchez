# RAG Design Document — HealthCore Knowledge Base

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                   User Question                      │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│              query(question: str) → str               │
│  ┌───────────────┐          ┌──────────────────────┐  │
│  │embed(question)│          │   retrieve(vector)   │  │
│  │ → vector      │          │ → chunks[ ]          │  │
│  └──────┬────────┘          └────────┬─────────────┘  │
│         │          ┌─────────────────▼────┐           │
│         └─────────►  LLM Generation       │           │
│                    │ (prompt = context +  │           │
│                    │  question)           │           │
│                    └──────────────────────┘           │
└───────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 Natural response                     │
└──────────────────────────────────────────────────────┘
```

**Four core functions, each with a single responsibility:**

| Function | Module | Responsibility |
|---|---|---|
| `setup()` | `data/process/rag.py` | Read source docs, chunk, embed, index into Qdrant |
| `embed(text)` | `data/process/rag.py` | Convert text → vector using dedicated embedding model |
| `retrieve(vector, top_k)` | `data/pipelines/rag.py` | Vector search in Qdrant, return top-k chunks |
| `query(question)` | `data/pipelines/rag.py` | Orchestrate embed + retrieve + LLM generate |

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

| Parameter | Value | Rationale |
|---|---|---|
| `top_k` | 3 | Recall@3 ≥ 80% target |
| `score_threshold` | 0.5 | Cosine similarity floor; avoids noise. Chosen by observing score distribution on test queries. |
| `rerank` | No (v1) | Can be added later as a stateless step between retrieve and generate. |

**Low-score behaviour:** If no chunk exceeds `score_threshold`, `retrieve()` returns
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
| Recall@3 | ≥ 80% | Manual evaluation against test-queries.json |
| Faithfulness | 100% | Each response verified against source chunks |
| Threshold coverage | 100% | All queries below threshold return the "no info" answer |

## 9. Files Layout

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

## 10. Production Upgrade Path

1. Deterministic UUIDs (hash of `source_document + chunk_index + text`) instead of clean-and-reload.
2. Add reranker (e.g., Cohere or BGE) between retrieve and generate.
3. Query expansion / HyDE for better retrieval.
4. Add streaming responses from the generation model.
5. A/B evaluation framework for chunk size and retrieval parameters.