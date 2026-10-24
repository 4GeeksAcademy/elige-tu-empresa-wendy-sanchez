# AI Engineering Company Project — Student Template

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_Base template for transversal projects in the AI Engineering Career Program — 4Geeks Academy._

> _Instrucciones disponibles en español en [README.es.md](./README.es.md)._

---

## Purpose

This repository is the **starter template** for transversal projects. You will work on real company scenarios (Brasaland, TrackFlow, Nexova), building deliverables that map to course milestones (Web, Programming, Backend, Telemetry, RAG, Agents, Workflows, Real-time).

- Create a template from this repository.
- Replace the placeholder `CONTEXT.md` with your assigned company context.
- Use `skills/` and the directory-level `README.md` files as working guidance.

---

## Current status of the template

The repository currently provides a **base folder structure and documentation skeleton**. It does not include runnable apps or global scripts yet.

- `CONTEXT.md` is a placeholder and must be replaced with your assigned company context.
- There is no root `AGENTS.md` yet.
- Shared package metadata exists in `packages/shared/package.json` (`@repo/shared-types`), but no workspace runner is configured at root.

---

## Repository structure

```text
ai-engineering-company-project-monorepo/
├── README.md
├── README.es.md
├── CONTEXT.md                # Placeholder to be replaced with assigned context
├── agents/                   # Agent patterns/templates and tools docs
├── data/                     # raw, process, pipelines, eval
├── docs/                     # Project and architecture documentation
├── infra/                    # Docker, Terraform, deployment configs
├── internal/                 # CLIs, packaged migration scripts, internal utilities
├── mcps/                     # Model Context Protocol (MCP) Servers
├── packages/
│   └── shared/               # Shared package (@repo/shared-types)
├── scripts/                  # Script conventions/documentation
├── services/                 # APIs and background workers
├── shared/                   # Shared assets/conventions at repo level
├── skills/                   # Reusable agent skills
├── uis/                      # User interfaces (React, Next.js, Streamlit, HTML)
└── workflows/                # Automation/orchestration documentation
```

---

## How to start

1. **Use this repository as a template** and create your own project repo.
2. **Clone** your repository (or open it in Codespaces).
3. **Replace** `CONTEXT.md` with the full context for your assigned company.
4. **Review** each top-level folder `README.md` to understand intended responsibilities (`uis/`, `services/`, `data/`, `skills/`, etc.).
5. **Start implementing** milestone deliverables in `uis/` and `services/`, reusing `packages/shared/` and `data/` as needed.

## Run locally in Codespaces (npx)

To preview the static landing pages from the repository root:

```bash
npx --yes serve . --listen 4173 --no-clipboard
```

Then open port `4173` and visit:

- `http://localhost:4173/index.html` (English)
- `http://localhost:4173/index.es.html` (Spanish)

---

## Celery Worker — Procesamiento Asíncrono de Tareas

El proyecto utiliza **Celery** + **Redis** para ejecutar operaciones pesadas (como el análisis de CSV de incidencias) en segundo plano, liberando la API y evitando timeouts.

### Arquitectura

```
FastAPI (Producer)  ──encola──→  Redis (Broker/Backend)  ──consume──→  Celery Worker
       │                              │
       └── 202 {task_id}              └── resultado persistido
```

### Cómo iniciar el Worker

**Opción 1 — Local (desde la raíz del proyecto):**

```bash
# Asegúrate de tener las dependencias instaladas
cd services/api && uv sync

# Activar el entorno virtual (opcional, según configuración)
# source services/api/.venv/bin/activate

# Iniciar el worker (usando la ruta absoluta del .venv)
PYTHONPATH="/workspace:${PYTHONPATH:-}" services/api/.venv/bin/celery -A services.celery_app worker --loglevel=info
```

**Opción 2 — Docker Compose (recomendado en desarrollo):**

```bash
docker compose up redis flower celery-worker
```

Esto levanta:
- **Redis** en `localhost:6379` (broker y backend)
- **Flower** en `http://localhost:5555` (panel de monitoreo)
- **Celery Worker** conectado automáticamente al broker

### Cómo monitorear

1. **Flower Dashboard:** Abre `http://localhost:5555` en el navegador.
   - Muestra workers activos, tareas en cola, tareas completadas/fallidas.
   - Permite revocar tareas y ver trazas detalladas.

2. **Logs del worker:** Si usas Docker Compose:
   ```bash
   docker compose logs -f celery-worker
   ```

3. **Dead Letter Queue (DLQ):** Las tareas que fallan tras agotar reintentos se persisten en:
   ```bash
   cat data/process/task_dlq.json
   ```
   Cada entrada incluye `task_id`, `attempt`, `error`, `timestamp`.

### Cómo usar desde la API

```bash
# 1. Encolar un análisis
curl -X POST http://localhost:8000/api/incidents/analyze \
  -F "file=@scripts/incidents-healthcore.csv"

# Respuesta: 202 Accepted
# {"task_id": "abc-123", "status": "PENDING", "detail": "La tarea ha sido encolada..."}

# 2. Consultar el estado
curl http://localhost:8000/tasks/abc-123

# Respuesta según estado:
# {"task_id": "abc-123", "status": "pending"}
# {"task_id": "abc-123", "status": "started"}
# {"task_id": "abc-123", "status": "success", "result": {...}}
# {"task_id": "abc-123", "status": "failure", "error": "..."}
```

### Estados de tarea

| Estado    | Significado                                  |
|-----------|----------------------------------------------|
| `pending` | En cola, esperando un worker                 |
| `started` | Worker comenzó a procesar                    |
| `success` | Completada exitosamente (result disponible)  |
| `failure` | Falló tras agotar reintentos (error disponible) |

### Reintentos y DLQ

- **max_retries:** 3 reintentos automáticos.
- **backoff exponencial:** 10s → 20s → 40s (con jitter).
- **DLQ:** Tras el tercer fallo, la tarea se registra en `data/process/task_dlq.json` con el error completo.

---

## Milestones (reference)

| Milestone | Focus        | Typical deliverables                        |
| --------- | ------------ | ------------------------------------------- |
| 0         | Prework      | Environment setup, first prompts            |
| 1         | Web          | Corporate website, forms, SEO               |
| 2         | Programming  | Business logic, scoring, calculations       |
| 3         | AI-driven UI | AI-generated interfaces                     |
| 4         | Next.js      | Portals, loyalty app, operations UI         |
| 5         | Backend      | Central API (locations, menus, sales, etc.) |
| 6         | Telemetry    | Data pipeline, dashboards                   |
| 7         | RAG & Memory | Semantic knowledge base, search             |
| 8         | Agents       | Support, onboarding, training agents        |
| 9         | Workflows    | n8n automations                             |
| 10        | Real-time    | Live dashboards, alerts, streaming          |

---

## Links

- [4Geeks Academy — AI Engineering](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)
- [How to start a coding project](https://4geeks.com/lesson/how-to-start-a-project)

---

## Contributors

This template was built as part of the 4Geeks Academy AI Engineering Career Program by [@marcogonzalo](https://www.linkedin.com/in/marcogonzalo) and [@alezanchezr](https://x.com/alesanchezr) and many other contributors. Find out more about our [AI Engineering Course](https://4geeksacademy.com/en/career-programs/ai-engineering), and [other courses](https://4geeksacademy.com/en/program-comparison).

You can find other templates and resources like this at the [4Geeks Academy GitHub page](https://github.com/4geeksacademy).

_This template is maintained by 4Geeks Academy for the AI Engineering track. For exclusive use in the programme._

---

## Project-specific notes (added)

- This repository currently includes a bilingual static website (`index.html`, `index.es.html`, `application.html`, `application.es.html`) and form validation logic in `validation.js`.
- A Next.js app for Talent Pipeline Tracker exists in `uis/talent-pipeline-tracker`.
- TypeScript validation commands currently available:
  - `npm run typecheck`
  - `cd uis/talent-pipeline-tracker && npm run typecheck`
- Root license information: **Pending definition**.
