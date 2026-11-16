# HealthCore — AI Engineering Company Project

![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.22-purple)](https://langchain-ai.github.io/langgraph/)
[![Python](https://img.shields.io/badge/Python-3.14-yellow)](https://python.org)

> _Instrucciones en español en [README.es.md](./README.es.md)._

**HealthCore** is a multi-site ambulatory care network operating 12 clinics across the US and UK. This repository implements the digital systems, tools, and AI agents built by its internal **HealthCore Digital** unit to modernize operations, improve patient experience, and enable data-driven decisions.

📄 The full company briefing is in [`CONTEXT.md`](./CONTEXT.md).

---

## 📦 Deliverables

| # | Deliverable | Stack | Status |
|---|-------------|-------|--------|
| 1 | **Corporate Website** — Bilingual (EN/ES) landing page with Schema.org markup and patient inquiry form | HTML, Tailwind CSS, vanilla JS | ✅ Complete |
| 2 | **Talent Pipeline Tracker** — Candidate management with filters, detail view, status updates, and notes | Next.js 19, React 19, TypeScript | ✅ Complete |
| 3 | **Suppliers Directory** — Centralized supplier registry with rate tracking, status changes, and soft-delete audit trail | FastAPI, Pydantic v2, TinyDB | ✅ Complete |
| 4 | **Authentication & User Management** — JWT login, registration, full password recovery flow, USER/ADMIN roles | FastAPI, python-jose, bcrypt, Resend | ✅ Complete |
| 5 | **Incidents Management System** — Standalone API for patient incidents with CSV legacy analysis and frontend | FastAPI (port 8010), TinyDB, Next.js | ✅ Complete |
| 6 | **Medical Supply Inventory** — 6 REST endpoints, stock calculated as net of deliveries minus consumption, 4 frontend pages | FastAPI, SQLModel, Supabase PostgreSQL | ✅ Complete |
| 7 | **Async Task Queue** — Redis + Celery with exponential backoff, Dead Letter Queue in TinyDB, Flower monitoring | Redis 7, Celery, Docker Compose | ✅ Complete |
| 8 | **Telemetry Pipeline & Dashboard** — 5 pandas metrics, standalone auth server, 5-panel backoffice dashboard | FastAPI, pandas, Supabase, Next.js | ✅ Complete |
| 9 | **Monthly Reporting** — ETL pipeline (Prefect 3), KPI API (port 8001), supply performance dashboard per clinic | Prefect, FastAPI, Supabase PostgreSQL | ✅ Complete |
| 10 | **Sales Forecast Model** — XGBoost regression with strict temporal 8/2 split, 12 causal features, anti-leak audit, bias/variance evaluation | XGBoost, scikit-learn, pandas, matplotlib | ✅ Complete |
| 11 | **RAG Knowledge Base** — Retrieval-Augmented Generation over HealthCore policy documents (insurance, appointments, referrals, checklists) | Qdrant, pplx-embed-v1, DeepSeek-v4, FastAPI | ✅ Complete |
| 12 | **LangGraph Support Agent** — Decision graph wrapping RAG pipeline with explicit state, checkpointing, tracing, and HTTP endpoint | LangGraph 1.2.22, MemorySaver, httpx | ✅ Complete |
| 13 | **LangGraph Agent — External Tools** — Added real-time incident and inventory query tools. Auto-routing between RAG, tools, or both via regex classification (no LLM). 5s timeout, honest fallback. 32 tests. | LangGraph, httpx, regex | ✅ Complete |

---

## 🏗️ Architecture Overview

```text
uis/                        # User interfaces
├── website/                #   Public website (Next.js) + RAG Q&A page
├── backoffice/             #   Admin panel (Next.js): suppliers, inventory, incidents, telemetry, reporting
└── talent-pipeline-tracker/#   Candidate tracker (Next.js)

services/                   # Backend services
├── api/                    #   Main FastAPI (port 8000) — auth, suppliers, inventory, agent endpoint
├── incidents-api/          #   Incidents FastAPI (port 8010) — standalone
├── reporting/              #   Reporting FastAPI (port 8001) — monthly KPIs
├── telemetry/              #   Telemetry analysis + standalone auth server
├── agent/                  #   LangGraph agent — graph, tools, routes
├── celery_app.py           #   Celery app — async task definitions
├── nightly/                #   Nightly export job — background process
└── job_runner.py           #   State machine for job orchestration

data/                       # Data layer
├── raw/                    #   Raw data (CSV)
├── process/                #   Processed data, TinyDB databases
├── pipelines/              #   RAG pipeline, ETL pipeline
├── eval/                   #   Test queries, evaluation reports
└── migrations/             #   Database migration SQL

agents/                     # Agent templates and tool documentation
docs/                       # Architecture, RAG design, telemetry plan
scripts/                    # CLI tools: sales forecast, model evaluation, nightly export, seed data
tests/                      # Test suites: pipelines, nightly, agent, RAG, evaluation
```

**Backend architecture:** Most APIs use TinyDB for auth and operational data. Inventory and reporting use Supabase PostgreSQL. A standalone auth server avoids SQLModel/Python 3.14 incompatibility.

**Docker:** Services communicate via Docker Compose under `healthcore-net`. See [`docker-compose.yml`](./docker-compose.yml).

---

## 🔧 Quick Start

```bash
# Prerequisites: Python 3.14, Node 22, uv 0.13+, Docker (optional)
uv sync                      # Install Python dependencies
cd uis/backoffice && npm install  # Install frontend dependencies
cd uis/website && npm install
```

### Run APIs

```bash
# Main API (port 8000) — auth, suppliers, inventory
uv run uvicorn services.api.main:app --reload --port 8000

# Incidents API (port 8010)
uv run uvicorn services.incidents-api.main:app --reload --port 8010

# Reporting API (port 8001)
uv run uvicorn services.reporting.main:app --reload --port 8001

# Telemetry standalone server (port 8000)
uv run python services/telemetry/server_standalone.py

# RAG standalone server (port 8000 — avoids SQLModel)
uv run python services/api/routes/rag_standalone.py
```

### Run Frontends

```bash
cd uis/backoffice && npm run dev      # Backoffice (port 3401)
cd uis/website && npm run dev          # Website (port 3402)
cd uis/talent-pipeline-tracker && npm run dev  # Tracker (port 3403)
```

### Run Tests

```bash
# All pipeline tests (agent, RAG, sales forecast, temporal CV)
uv run python -m pytest tests/pipelines/ -v

# Agent-specific (32 tests)
uv run python -m pytest tests/pipelines/test_agent_graph.py -v

# RAG-specific (26 tests)
uv run python -m pytest tests/pipelines/test_rag.py -v

# Sales forecast (19 tests)
uv run python -m pytest tests/pipelines/test_sales_forecast_split.py -v

# Nightly job (30 tests)
.venv-nightly/bin/python -m pytest tests/nightly -q
```

### Run Docker Stack

```bash
docker compose up --build    # Builds and starts all services
```

---

## 🧠 LangGraph Agent — Key Details

The support agent is implemented as a LangGraph `StateGraph` with **10 nodes** and **7 conditional routers**. It reuses existing RAG functions (`retrieve`, `generate_answer`) without rewriting them.

**Nodes:** `receive_question` → `classify_query` → (tool and/or RAG) → `synthesize_tool_answer` / `generate_answer` → END

- **Classification:** Regex-based (no LLM needed). Decides between RAG, incident tool, inventory tool, or a combination.
- **Tools:** Read-only (GET). Query real incident and inventory services. 5s timeout. All errors produce honest fallback responses.
- **Tracing:** Each run produces a JSON trace persisted to `services/agent/traces/{run_id}.json`.
- **Endpoint:** `POST /agent/query` (thin FastAPI layer — no business logic).
- **Docs:** [`agente-soporte-langgraph.md`](./agente-soporte-langgraph.md) (Spanish).

---

## 📊 Sales Forecast Model — Key Details

XGBoost regression trained on 84 months (2016–2023), tested on 24 unseen months (2024–2025). No data leakage. Walk-forward validation.

- **Metrics (test):** RMSE $154.9K (5.5% of mean revenue), MAPE 3.5%, Gini 0.82, K²/R² 0.81
- **Variability band:** ±$265K (87.5% empirical coverage)
- **Bias/varianza diagnosis:** Overfitting confirmed — CV gap 28.7×. Corrective actions documented.
- **Docs:** [`predic-ventas-model-regresion.md`](./predic-ventas-model-regresion.md) (Spanish).

---

## 📚 RAG Knowledge Base — Key Details

Retrieval-Augmented Generation over 4 HealthCore policy documents. Embedded with `pplx-embed-v1` (1024-dim) into Qdrant. Generates answers with `deepseek-v4-flash`.

- **12 chunks** (3 per document), 450 chars max, 140 chars min
- **Recall@3:** 100% (8/8 test queries)
- **Frontend:** Q&A chat page on the public website (`uis/website/app/rag/`)
- **Docs:** [`docs/rag/rag-design.md`](./docs/rag/rag-design.md) (EN) / [`rag-design.es.md`](./docs/rag/rag-design.es.md) (ES)

---

## 📁 Key Documentation

| File | Content |
|------|---------|
| [`CONTEXT.md`](./CONTEXT.md) | Full company briefing (HealthCore, departments, problems) |
| [`agente-soporte-langgraph.md`](./agente-soporte-langgraph.md) | LangGraph agent architecture (Part 1 + Part 2) |
| [`predic-ventas-model-regresion.md`](./predic-ventas-model-regresion.md) | Sales forecast model design and audit |
| [`docs/rag/rag-design.md`](./docs/rag/rag-design.md) | RAG knowledge base design |
| [`background-processes.md`](./background-processes.md) | Background job architecture |
| [`docs/ARCHITECTURE_PROPOSAL.md`](./docs/ARCHITECTURE_PROPOSAL.md) | Overall architecture proposal |
| [`memory-bank/`](./memory-bank/) | Development progress, active context, system patterns |

---

## 🧪 Testing Philosophy

- **Pipeline tests** (`tests/pipelines/`) cover agent, RAG, and sales forecast — all runnable with `uv run python -m pytest`
- Agent tests include: graph compilation, conditional routing, traceability, grounded RAG behavior, tool routing (5 tests), tool fallback behavior (5 tests), and mixed synthesis (2 tests)
- All test suites pass as gate before feature branches merge
- Audit-driven development: each deliverable has verifiable acceptance criteria


---

## Project-specific notes

- This repository currently includes a bilingual static website (`index.html`, `index.es.html`, `application.html`, `application.es.html`) and form validation logic in `validation.js`.
- A Next.js app for Talent Pipeline Tracker exists in `uis/talent-pipeline-tracker`.
- TypeScript validation commands currently available:
  - `npm run typecheck`
  - `cd uis/talent-pipeline-tracker && npm run typecheck`

---

**Developer Wendy Sanchez**
