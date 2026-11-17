# HealthCore — Proyecto de Ingeniería IA

![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.22-purple)](https://langchain-ai.github.io/langgraph/)
[![Python](https://img.shields.io/badge/Python-3.14-yellow)](https://python.org)

> _English instructions in [README.md](./README.md)._

**HealthCore** es una red de atención ambulatoria que opera 12 clínicas en Estados Unidos y Reino Unido. Este repositorio implementa los sistemas digitales, herramientas y agentes de IA construidos por su unidad interna **HealthCore Digital** para modernizar las operaciones, mejorar la experiencia del paciente y habilitar decisiones basadas en datos.

📄 La descripción completa de la empresa está en [`CONTEXT.md`](./CONTEXT.md).

---

## 📦 Entregables

| # | Entregable | Stack | Estado |
|---|------------|-------|--------|
| 1 | **Sitio Web Corporativo** — Landing page bilingüe (EN/ES) con marcado Schema.org y formulario de consulta | HTML, Tailwind CSS, vanilla JS | ✅ Completado |
| 2 | **Talent Pipeline Tracker** — Gestión de candidatos con filtros, vista detalle, actualización de estado y notas | Next.js 19, React 19, TypeScript | ✅ Completado |
| 3 | **Directorio de Proveedores** — Registro centralizado con tarifas, cambios de estado y baja con auditoría | FastAPI, Pydantic v2, TinyDB | ✅ Completado |
| 4 | **Autenticación y Usuarios** — Login JWT, registro, recuperación de contraseña completa, roles USER/ADMIN | FastAPI, python-jose, bcrypt, Resend | ✅ Completado |
| 5 | **Sistema de Incidencias** — API independiente para incidencias de pacientes con análisis CSV legacy y frontend | FastAPI (puerto 8010), TinyDB, Next.js | ✅ Completado |
| 6 | **Inventario de Suministros Médicos** — 6 endpoints REST, stock calculado como neto de entradas menos salidas, 4 páginas frontend | FastAPI, SQLModel, Supabase PostgreSQL | ✅ Completado |
| 7 | **Cola de Tareas Asíncronas** — Redis + Celery con backoff exponencial, Dead Letter Queue en TinyDB, monitorización Flower | Redis 7, Celery, Docker Compose | ✅ Completado |
| 8 | **Pipeline de Telemetría y Dashboard** — 5 métricas pandas, servidor auth standalone, dashboard de 5 paneles | FastAPI, pandas, Supabase, Next.js | ✅ Completado |
| 9 | **Reporting Mensual** — Pipeline ETL (Prefect 3), API de KPIs (puerto 8001), dashboard de rendimiento por clínica | Prefect, FastAPI, Supabase PostgreSQL | ✅ Completado |
| 10 | **Modelo de Pronóstico de Ventas** — Regresión XGBoost con split temporal estricto 8/2, 12 features causales, auditoría anti-fuga, evaluación sesgo/varianza | XGBoost, scikit-learn, pandas, matplotlib | ✅ Completado |
| 11 | **Base de Conocimiento RAG** — Generación Aumentada por Recuperación sobre documentos de políticas de HealthCore | Qdrant, pplx-embed-v1, DeepSeek-v4, FastAPI | ✅ Completado |
| 12 | **Agente de Soporte LangGraph** — Grafo de decisión que envuelve el pipeline RAG con estado explícito, checkpointing, trazabilidad y endpoint HTTP | LangGraph 1.2.22, MemorySaver, httpx | ✅ Completado |
| 13 | **Agente LangGraph — Tools Externas** — Añadidas herramientas de consulta en tiempo real a incidencias e inventario. Enrutamiento automático entre RAG, tools o ambos mediante clasificación regex (sin LLM). Timeout 5s, fallback honesto. 32 tests. | LangGraph, httpx, regex | ✅ Completado |

---

## 🏗️ Arquitectura General

```text
uis/                        # Interfaces de usuario
├── website/                #   Sitio público (Next.js) + página Q&A RAG
├── backoffice/             #   Panel admin (Next.js): proveedores, inventario, incidencias, telemetría, reporting
└── talent-pipeline-tracker/#   Seguimiento de candidatos (Next.js)

services/                   # Servicios backend
├── api/                    #   FastAPI principal (puerto 8000) — auth, proveedores, inventario, endpoint agente
├── incidents-api/          #   FastAPI incidencias (puerto 8010) — standalone
├── reporting/              #   FastAPI reporting (puerto 8001) — KPIs mensuales
├── telemetry/              #   Análisis de telemetría + servidor auth standalone
├── agent/                  #   Agente LangGraph — grafo, tools, rutas
├── celery_app.py           #   App Celery — definiciones de tareas asíncronas
├── nightly/                #   Job nocturno de exportación — proceso en segundo plano
└── job_runner.py           #   Máquina de estados para orquestación de trabajos

data/                       # Capa de datos
├── raw/                    #   Datos crudos (CSV)
├── process/                #   Datos procesados, bases TinyDB
├── pipelines/              #   Pipeline RAG, pipeline ETL
├── eval/                   #   Consultas de prueba, informes de evaluación
└── migrations/             #   Migraciones SQL

agents/                     # Plantillas de agentes y documentación de herramientas
docs/                       # Arquitectura, diseño RAG, plan de telemetría
scripts/                    # Herramientas CLI: pronóstico ventas, evaluación modelo, exportación nocturna, seed
tests/                      # Suites de tests: pipelines, nightly, agente, RAG, evaluación
```

**Arquitectura backend:** La mayoría de las APIs usan TinyDB para auth y datos operativos. Inventario y reporting usan Supabase PostgreSQL. Un servidor auth standalone evita la incompatibilidad SQLModel/Python 3.14.

**Docker:** Los servicios se comunican mediante Docker Compose bajo la red `healthcore-net`. Ver [`docker-compose.yml`](./docker-compose.yml).

---

## 🔧 Inicio Rápido

```bash
# Requisitos: Python 3.14, Node 22, uv 0.13+, Docker (opcional)
uv sync                      # Instalar dependencias Python
cd uis/backoffice && npm install  # Instalar dependencias frontend
cd uis/website && npm install
```

### Ejecutar APIs

```bash
# API principal (puerto 8000) — auth, proveedores, inventario
uv run uvicorn services.api.main:app --reload --port 8000

# API de incidencias (puerto 8010)
uv run uvicorn services.incidents-api.main:app --reload --port 8010

# API de reporting (puerto 8001)
uv run uvicorn services.reporting.main:app --reload --port 8001

# Servidor telemetría standalone (puerto 8000)
uv run python services/telemetry/server_standalone.py

# Servidor RAG standalone (puerto 8000 — evita SQLModel)
uv run python services/api/routes/rag_standalone.py
```

### Ejecutar Frontends

```bash
cd uis/backoffice && npm run dev      # Backoffice (puerto 3001)
cd uis/website && npm run dev          # Sitio web (puerto 3000)
cd uis/talent-pipeline-tracker && npm run dev  # Tracker (puerto 3000 por defecto)
```

### Ejecutar Tests

```bash
# Todos los tests de pipelines (agente, RAG, pronóstico ventas, CV temporal)
uv run python -m pytest tests/pipelines/ -v

# Tests del agente (32 tests)
uv run python -m pytest tests/pipelines/test_agent_graph.py -v

# Tests de RAG (26 tests)
uv run python -m pytest tests/pipelines/test_rag.py -v

# Tests de pronóstico de ventas (19 tests)
uv run python -m pytest tests/pipelines/test_sales_forecast_split.py -v

# Tests del job nocturno (30 tests)
.venv-nightly/bin/python -m pytest tests/nightly -q
```

### Ejecutar Stack Docker

```bash
docker compose up --build    # Construye e inicia todos los servicios
```

---

## 🧠 Agente LangGraph — Detalles Clave

El agente de soporte está implementado como un `StateGraph` de LangGraph con **10 nodos** y **7 enrutadores condicionales**. Reutiliza las funciones RAG existentes (`retrieve`, `generate_answer`) sin reescribirlas.

**Nodos:** `receive_question` → `classify_query` → (tool y/o RAG) → `synthesize_tool_answer` / `generate_answer` → END

- **Clasificación:** Basada en regex (sin LLM). Decide entre RAG, tool de incidencias, tool de inventario, o una combinación.
- **Tools:** Solo lectura (GET). Consultan los servicios reales de incidencias e inventario. Timeout 5s. Todos los errores producen respuestas de fallback honestas.
- **Trazabilidad:** Cada ejecución produce un trace JSON persistido en `services/agent/traces/{run_id}.json`.
- **Endpoint:** `POST /agent/query` (capa FastAPI delgada — sin lógica de negocio).
- **Documentación:** [`agente-soporte-langgraph.md`](./agente-soporte-langgraph.md)

---

## 📊 Modelo de Pronóstico de Ventas — Detalles Clave

Regresión XGBoost entrenada con 84 meses (2016–2023), probada en 24 meses no vistos (2024–2025). Sin fuga de datos. Validación walk-forward.

- **Métricas (test):** RMSE $154.9K (5.5% del ingreso medio), MAPE 3.5%, Gini 0.82, K²/R² 0.81
- **Banda de variabilidad:** ±$265K (cobertura empírica 87.5%)
- **Diagnóstico sesgo/varianza:** Overfitting confirmado — brecha CV 28.7×. Acciones correctivas documentadas.
- **Documentación:** [`predic-ventas-model-regresion.md`](./predic-ventas-model-regresion.md)

---

## 📚 Base de Conocimiento RAG — Detalles Clave

Generación Aumentada por Recuperación sobre 4 documentos de políticas de HealthCore. Embeddings con `pplx-embed-v1` (1024-dim) en Qdrant. Genera respuestas con `deepseek-v4-flash`.

- **12 fragmentos** (3 por documento), 450 chars máx, 140 chars mín
- **Recall@3:** 100% (8/8 consultas de prueba)
- **Frontend:** Página de chat Q&A en el sitio web público (`uis/website/app/rag/`)
- **Documentación:** [`docs/rag/rag-design.es.md`](./docs/rag/rag-design.es.md) (ES) / [`rag-design.md`](./docs/rag/rag-design.md) (EN)

---

## 📁 Documentación Clave

| Archivo | Contenido |
|---------|-----------|
| [`CONTEXT.md`](./CONTEXT.md) | Descripción completa de la empresa (HealthCore, departamentos, problemas) |
| [`agente-soporte-langgraph.md`](./agente-soporte-langgraph.md) | Arquitectura del agente LangGraph (Parte 1 + Parte 2) |
| [`predic-ventas-model-regresion.md`](./predic-ventas-model-regresion.md) | Diseño y auditoría del modelo de pronóstico de ventas |
| [`docs/rag/rag-design.es.md`](./docs/rag/rag-design.es.md) | Diseño de la base de conocimiento RAG |
| [`background-processes.md`](./background-processes.md) | Arquitectura del proceso en segundo plano |
| [`docs/ARCHITECTURE_PROPOSAL.md`](./docs/ARCHITECTURE_PROPOSAL.md) | Propuesta de arquitectura general |
| [`memory-bank/`](./memory-bank/) | Progreso del desarrollo, contexto activo, patrones del sistema |

---

## 🧪 Filosofía de Testing

- **Tests de pipelines** (`tests/pipelines/`) cubren agente, RAG y pronóstico de ventas — todos ejecutables con `uv run python -m pytest`
- Los tests del agente incluyen: compilación del grafo, enrutamiento condicional, trazabilidad, comportamiento RAG fundamentado, enrutamiento de tools (5 tests), comportamiento de fallback de tools (5 tests) y síntesis mixta (2 tests)
- Todas las suites de tests pasan como puerta de entrada antes de fusionar ramas de funcionalidad
- Desarrollo impulsado por auditoría: cada entregable tiene criterios de aceptación verificables


---

## Notas específicas del proyecto

- Este repositorio incluye actualmente un sitio web estático bilingüe (`index.html`, `index.es.html`, `application.html`, `application.es.html`) y lógica de validación de formularios en `validation.js`.
- Existe una aplicación Next.js para «Talent Pipeline Tracker» en `uis/talent-pipeline-tracker`.
- Comandos de validación de TypeScript disponibles actualmente:
  - `npm run typecheck`
  - `cd uis/talent-pipeline-tracker && npm run typecheck`

---

**Developer Wendy Sanchez**
