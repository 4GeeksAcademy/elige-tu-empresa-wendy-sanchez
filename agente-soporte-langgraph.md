# Agente de Soporte LangGraph — Documentación (Parte 1)

## 1. Resumen Ejecutivo

Este documento describe la migración del agente de soporte RAG de HealthCore desde un flujo lineal (retrieve → generate) a un **grafo de LangGraph** con estado explícito, nodos de una sola responsabilidad, aristas condicionales trazables y checkpointing en cada transición.

**Objetivo:** que el flujo de razonamiento quede explícito como un grafo — cada paso, cada decisión de enrutamiento y cada resultado se pueda trazar, evaluar y auditar de forma independiente.

---

## 2. Arquitectura

### 2.1 Estructura de directorios

```
services/
  agent/
    __init__.py          # Docstring del paquete
    graph.py             # Grafo LangGraph: estado, nodos, aristas, compilación
    routes.py            # Endpoint FastAPI (POST /agent/query, GET /agent/trace/{id})
    traces/              # Trazas persistidas en disco (JSON consultable)

tests/
  pipelines/
    test_agent_graph.py  # 20 evals del agente (compilación, enrutamiento, traza, RAG, endpoint)

data/
  pipelines/
    rag.py               # retrieve() y generate_answer() — reutilizados sin duplicar
```

### 2.2 Principios de diseño

1. **Estado mínimo y explícito** — El `AgentState` contiene solo lo que cada nodo necesita para decidir: `question`, `retrieved_chunks`, `answer`, `error`. No incluye el historial completo de la conversación.

2. **Nodos con responsabilidad única** — Cada nodo hace exactamente una cosa:
   - `receive_question`: valida la entrada
   - `retrieve_context`: recupera fragmentos de Qdrant
   - `generate_answer`: genera respuesta con el contexto ya recuperado
   - `respond_no_info`: responde con honestidad cuando no hay contexto
   - `handle_error`: maneja errores con mensajes amigables

3. **Aristas condicionales explícitas** — Tres bifurcaciones reales:
   - `route_after_receive`: pregunta vacía/corta → END, válida → retrieve
   - `route_after_retrieve`: error → handle_error, sin chunks → no_info, con chunks → generate
   - `route_after_generate`: error → handle_error, ok → END

4. **Compilación en tiempo de build** — El grafo se compila al importar el módulo. Errores estructurales (nodos desconectados, estado mal tipado) se detectan al arrancar, no en producción.

5. **Trazabilidad completa** — Cada corrida produce:
   - Un `trace_events` con cada nodo ejecutado, timestamp y metadatos
   - Un `routing_log` con cada decisión de enrutamiento
   - Un archivo JSON persistido en `services/agent/traces/<run_id>.json`

---

## 3. El Grafo

### 3.1 Diagrama de flujo

```
                    ┌──────────────────┐
                    │ receive_question │  (valida la entrada)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ ¿Pregunta valida?│
                    └────┬─────────┬───┘
                  ┌──────┘         └───────┐
                  ▼                        ▼
          ┌────────────────┐             ╔════╗
          │retrieve_context│             ║ END║
          └───────┬────────┘             ╚════╝
                  │
         ┌────────▼────────┐
         │  ¿Resultado?    │
         └────┬─────┬───┬──┘
      ┌───────┘     │   └────────┐
      ▼             ▼            ▼
┌──────────┐ ┌───────────┐ ┌──────────────┐
│handle_err│ │respond_no │ │generate_ans  │
│          │ │_info      │ │wer           │
└────┬─────┘ └─────┬─────┘ └──────┬───────┘
     │             │              │
     │        ┌────▼───┐   ┌────▼────┐
     │        ║  END   ║   │ ¿Error? │
     │        ╚════════╝   └──┬───┬──┘
     │                  ┌─────┘   └────┐
     │                  ▼              ▼
     │           ┌──────────┐      ╔════╗
     └───────────►handle_err│      ║ END║
                 └────┬─────┘      ╚════╝
                      ▼
                  ╔════╗
                  ║ END║
                  ╚════╝
```

### 3.2 Estado del grafo (`AgentState`)

| Campo | Tipo | Reducer | Descripción |
|-------|------|---------|-------------|
| `question` | `str` | — | Pregunta original del usuario |
| `retrieved_chunks` | `list[dict]` | — | Fragmentos recuperados de Qdrant |
| `answer` | `str` | — | Respuesta generada o mensaje de fallback |
| `error` | `Optional[str]` | — | Mensaje de error si un nodo falló |
| `question_valid` | `bool` | — | Indica si la pregunta es válida |
| `trace_events` | `list[dict]` | `_accumulate_list` | Eventos estructurados de cada nodo |
| `routing_log` | `list[str]` | `_accumulate_list` | Decisiones de enrutamiento |

**Uso de `Annotated` con `_accumulate_list`:** las listas `trace_events` y `routing_log` usan un reducer personalizado que acumula entradas de todos los nodos en lugar de reemplazarlas. Esto permite que el estado final contenga el historial completo de la corrida.

### 3.3 Nodos

| Nodo | Función | Input | Output | Responsabilidad |
|------|---------|-------|--------|-----------------|
| `receive_question` | `node_receive_question` | `question` | `error` o `question_valid=True` | Validar que la pregunta no esté vacía ni sea demasiado corta |
| `retrieve_context` | `node_retrieve_context` | `question` | `retrieved_chunks` o `error` | Llamar a `data.pipelines.rag.retrieve()` |
| `generate_answer` | `node_generate_answer` | `question` + `retrieved_chunks` | `answer` o `error` | Llamar a `data.pipelines.rag.generate_answer()` |
| `respond_no_info` | `node_respond_no_info` | — | `answer` (mensaje de "no tengo info") | Responder con honestidad sin alucinar |
| `handle_error` | `node_handle_error` | `error` | `answer` (mensaje amigable) | Capturar errores sin exponer stack traces |

### 3.4 Aristas condicionales

| Desde | Router | Condiciones |
|-------|--------|-------------|
| `receive_question` | `route_after_receive` | `error` o `question_valid=False` → END; válida → `classify_query` |
| `classify_query` | `route_after_classify` | Según `routing_decision`: `rag` → `retrieve_context`, `incident` → `query_incident`, etc. |
| `query_incident` / `query_inventory` | `route_after_tool` | Si decisión combinada → `retrieve_context`; si tool-only → `synthesize_tool_answer` |
| `retrieve_context` | `route_after_retrieve_v2` | `error` → `handle_error`; con RAG → `generate_answer`; con tools (sin RAG) → `synthesize_tool_answer`; sin nada → `respond_no_info` |
| `generate_answer` | `route_after_generate` | `error` → `handle_error`; con tools pendientes (resultados o errores) → `synthesize_tool_answer`; ok → END |

### 3.5 Compilación

El grafo se compila al importar `services/agent/graph.py`:

```python
try:
    agent_graph = _compile_graph()
    logger.info("Grafo LangGraph compilado correctamente con %d nodos.", len(agent_graph.nodes))
except Exception as exc:
    logger.critical("Error al compilar el grafo LangGraph: %s", exc)
    raise
```

El `MemorySaver` se usa como checkpointing en memoria para cada transición de estado.

---

## 4. Integración con el código RAG existente

### 4.1 Reutilización, no duplicación

El grafo **reutiliza** las funciones existentes de `data/pipelines/rag.py`:

- **`retrieve(question, k, min_score)`** — el nodo `retrieve_context` la llama directamente
- **`generate_answer(question, context)`** — el nodo `generate_answer` la llama con los chunks ya recuperados

No se implementó un nuevo `query()` monolítico dentro del grafo. Cada nodo llama a la función correspondiente de forma independiente.

### 4.2 Contrato de nodos

```
NODO retrieve_context
  Input:  question (str)
  Llama:  data.pipelines.rag.retrieve(question, k=5, min_score=0.3)
  Output: retrieved_chunks (list[dict]) o error

NODO generate_answer
  Input:  question (str), retrieved_chunks (list[dict])
  Llama:  data.pipelines.rag.generate_answer(question, context=retrieved_chunks)
  Output: answer (str) o error
  NOTA:   NO ejecuta retrieve() internamente
```

---

## 5. Endpoint API

### 5.1 `POST /agent/query`

Reemplaza/convive con el endpoint RAG existente (`POST /rag/query`).

**Request:**
```json
{
  "question": "¿Cobran cargo por no-show a pacientes de Medicare?"
}
```

**Response (200):**
```json
{
  "answer": "No, los pacientes de Medicare o Medicaid no están sujetos al cargo por no-show en HealthCore.",
  "run_id": "a1b2c3d4-..."
}
```

**Response (422) — pregunta inválida:**
```json
{
  "detail": "La pregunta no puede estar vacía."
}
```

**Response (503) — error interno:**
```json
{
  "detail": "Ocurrió un error al procesar tu solicitud. Por favor intenta de nuevo más tarde."
}
```

### 5.2 `GET /agent/trace/{run_id}`

Recupera la traza completa de una corrida.

**Response:**
```json
{
  "run_id": "a1b2c3d4-...",
  "question": "¿Cobran cargo por no-show a pacientes de Medicare?",
  "answer": "No, ...",
  "error": null,
  "routing_log": [
    "receive_question → classify_query (pregunta válida)",
    "classify_query → rag",
    "retrieve_context → generate_answer (3 fragmentos recuperados)",
    "generate_answer → END (respuesta generada)"
  ],
  "events": [
    {"node": "receive_question", "status": "ok", "timestamp": "...", "metadata": {"question_length": 47}},
    {"node": "retrieve_context", "status": "ok", "timestamp": "...", "metadata": {"num_chunks": 3}},
    {"node": "generate_answer", "status": "ok", "timestamp": "...", "metadata": {"answer_length": 98}}
  ],
  "num_chunks_retrieved": 3,
  "timestamp": "2026-11-14T..."
}
```

### 5.3 `GET /agent/traces`

Lista las N trazas más recientes (sin eventos completos).

---

## 6. Evaluación y Tests

### 6.1 Evals (32 tests en `tests/pipelines/test_agent_graph.py`)

| Clase | # Tests | ¿Qué verifica? |
|-------|---------|----------------|
| `TestGraphCompilation` | 3 | El grafo compila, tiene todos los nodos, entry point correcto |
| `TestConditionalRouting` | 7 | Cada arista condicional enruta correctamente según el estado |
| `TestTraceability` | 4 | Cada corrida produce trace persistido, consultable, con eventos y routing_log |
| `TestRAGBehavior` | 4 | El comportamiento RAG está anclado en los datos: retrieve antes que generate, Medicare no paga no-show verificado con fake LLM (solo responde con contexto), etc. |
| `TestAgentEndpoint` | 2 | El endpoint existe con prefijo correcto y delega en `run_agent()` |
| `TestExternalToolRouting` (Parte 2) | 5 | Clasificación de preguntas en 5 dominios (incident, rag, inventory, combinado, default) |
| `TestToolFallbackBehavior` (Parte 2) | 5 | Timeout, 404, synthesize con fallos, extracción de IDs, trace_events con decisión |
| `TestMixedSynthesis` (Parte 2) | 2 | Síntesis rag+incident combina ambas fuentes; fallo de tool en modo combinado incluye RAG + error honesto |

### 6.1.1 Fake LLM para verificar grounding

El test `test_medicare_no_show_policy_grounded` NO usa un mock de `generate_answer` con
una respuesta prefabricada. En su lugar usa `_fake_generate_answer_grounded`:

```python
def _fake_generate_answer_grounded(question, context):
    """Fake LLM que SOLO puede contestar con el texto del contexto."""
    if not context:
        return "No tengo información en los documentos disponibles..."
    texts = [chunk.get("text", "") for chunk in context]
    # Busca keywords de la pregunta en los fragmentos
    ...
    if best_text:
        return f"Según la documentación de HealthCore:\n{best_text.strip()}"
    return "No encontré información relevante..."
```

Esto garantiza que:
1. El fragmento correcto se recuperó (`retrieve_context` funcionó)
2. Ese fragmento se pasó a `generate_answer` (el enrutamiento funciona)
3. La respuesta contiene palabras textuales del fragmento (grounding real)

Si el fragmento no se recuperara o no se pasara al generador, el fake LLM
devolvería un fallback genérico y las aserciones fallarían.

### 6.2 Trazabilidad como requisito de aceptación

Un eval pasa solo si:
1. La respuesta es correcta según la base de conocimiento
2. El trace prueba que los nodos se ejecutaron en el orden correcto
3. El routing_log registra cada decisión de enrutamiento

**Ejemplo (eval `test_medicare_no_show_policy_grounded`):**
- Entrada: "¿Cobran cargo por no-show a pacientes de Medicare?"
- Criterio: La respuesta debe contener palabras del fragmento (`"no-show"`, `"medicare"`, `"cargo"`),
  y el trace debe mostrar `retrieve_context` → `generate_answer`.
- **No se mockea la respuesta**: se usa un fake LLM que solo puede responder con el contexto.

### 6.3 Cómo ejecutar los tests

```bash
# Tests del agente LangGraph
uv run pytest tests/pipelines/test_agent_graph.py -v

# Tests RAG existentes (deben seguir pasando)
uv run pytest tests/pipelines/test_rag.py -v

# Todos los tests
uv run pytest tests/pipelines/ -v
```

---

## 7. Dependencias

```toml
[project.dependencies]
langgraph = ">=1.2.22"
# Las demás dependencias (fastapi, qdrant-client, openai, etc.) ya estaban
```

Instalación:
```bash
uv add langgraph
```

---

## 8. Checkpointing y Tracing

### 8.1 Checkpointing

Se usa `MemorySaver` de LangGraph para checkpointing en memoria. Cada transición de estado relevante se guarda, permitiendo:
- Inspeccionar el estado en cualquier punto de la corrida
- Retomar una corrida desde un checkpoint previo
- Depurar errores de enrutamiento

En producción, se reemplazaría por un saver persistente (Postgres, SQLite, etc.).

### 8.2 Tracing estructurado

Cada corrida produce un archivo JSON en `services/agent/traces/<run_id>.json`:

```json
{
  "run_id": "...",
  "question": "...",
  "answer": "...",
  "error": null,
  "routing_log": [...],
  "events": [
    {"node": "...", "status": "ok", "timestamp": "...", "metadata": {...}},
    ...
  ],
  "num_chunks_retrieved": 3,
  "final_answer_length": 98,
  "timestamp": "..."
}
```

Funciones para consultar trazas:
- `get_trace(run_id: str)` — recupera una traza por ID
- `list_traces(limit: int = 20)` — lista trazas recientes

**Nota:** `persist_trace()` usa `encoding="utf-8"` al escribir el archivo JSON
para garantizar portabilidad con Windows (caracteres Unicode como `→`).
Las funciones de consulta (`get_trace`, `list_traces`) también leen con `encoding="utf-8"`.

---

## 9. Lo que NO cambió

- **Las funciones RAG** `retrieve()`, `generate_answer()` y `query()` en `data/pipelines/rag.py` no se modificaron.
- **El proceso de indexación** `data/process/rag.py` no se modificó.
- **Los tests RAG existentes** (`tests/pipelines/test_rag.py`) siguen pasando (26/26).
- **El comportamiento de negocio** sigue anclado en las políticas de CONTEXT.md (Medicare/Medicaid no paga no-show, seguros no listados requieren verificación con Tom Callahan, etc.).

---

## 10. Checklist de cumplimiento

- [x] Grafo compilado antes de cualquier ejecución (falla en tiempo de build)
- [x] Estado mínimo y explícito (no el historial completo de la conversación)
- [x] Cada nodo tiene una sola responsabilidad
- [x] Aristas condicionales con condiciones reales (no línea recta)
- [x] `retrieve()` y `generate_answer()` son nodos separados
- [x] Reutilización del código RAG existente (sin duplicar)
- [x] Checkpointing en cada transición de estado
- [x] Trazas persistidas y consultables después de la corrida
- [x] Endpoint sin lógica de negocio propia
- [x] 20 evals (Parte 1) que verifican compilación, enrutamiento, trazabilidad y comportamiento RAG + 12 evals (Parte 2) que verifican tools externas, fallback y síntesis mixta
- [x] Respuestas de error sin stack traces crudos (503 con mensaje genérico, sin `str(exc)`)
- [x] `persist_trace()` escribe con `encoding="utf-8"` (portabilidad Windows)
- [x] Test de grounding con fake LLM (no mock prefabricado) — verifica que `generate_answer` recibe el fragmento y la respuesta sale de él

---

# Parte 2 — Herramientas fuera del RAG

## 1. Resumen

En la Parte 1 el agente solo sabía consultar la base de conocimiento (RAG). En la Parte 2 se le añaden **tools externas** que consultan datos operativos en tiempo real:

- **`query_incident`**: consulta el gestor de incidentes (GET /api/incidents y GET /api/incidents/{id}).
- **`query_inventory`** (extra): consulta el gestor de inventario (GET /inventory/products).

El agente **decide automáticamente** si necesita RAG, una tool, o ambos, sin que el usuario tenga que indicarlo.

## 2. ¿Por qué no indexar tickets en el RAG?

Los tickets cambian de estado en tiempo real (open → in_progress → resolved). Una copia indexada en Qdrant queda desactualizada en el momento en que alguien cambia el estado. Una tool que llama directamente al endpoint del gestor de incidentes siempre devuelve el dato actual.

| Fuente | Tipo de dato | Actualización |
|--------|-------------|---------------|
| RAG (Qdrant) | Conocimiento (políticas, procedimientos) | Relativamente estable |
| Tool (HTTP) | Datos operativos (tickets, stock) | Tiempo real |

## 3. Estructura de directorios (Parte 2)

```
services/
  agent/
    __init__.py
    graph.py              ← Actualizado: nuevos nodos y aristas para tools
    routes.py             ← Sin cambios (el endpoint POST /agent/query es el mismo)
    traces/
    tools/                ← NUEVO: paquete de tools externas
      __init__.py         ← _get_service_url() helper
      incidents.py        ← query_incident_by_id(), query_incidents_list()
      inventory.py        ← query_product_by_id(), query_products_list()

tests/
  pipelines/
    test_agent_graph.py   ← Actualizado: +12 nuevos evals (Parte 2)
```

## 4. Contrato de las tools

### 4.1 Tool de incidentes (obligatoria)

| Aspecto | Detalle |
|---------|---------|
| **Entrada** | `ticket_id: int` (opcional) o filtros: `status`, `category`, `origin`, `branch` |
| **Salida** | `id, title, status, category, origin, branch, branch_label, description_preview, created_at, updated_at` |
| **Endpoint real** | `GET /api/incidents/{id}` o `GET /api/incidents?status=...&category=...` |
| **Timeout** | **5 segundos** — explícito, numérico, en `_INCIDENTS_TIMEOUT_S` |
| **Solo lectura** | Sí — solo GET. Nunca crea, actualiza ni elimina tickets |
| **Autenticación** | El servicio de incidentes **NO requiere autenticación** (sin JWT). Esto es por diseño en el despliegue actual; para producción añadir auth. |
| **URL base** | `INCIDENTS_API_URL` (env) → fallback `http://incidents-backend:8010` |

**Ejemplo de llamada desde el grafo:**

```python
from services.agent.tools.incidents import query_incident_by_id

result = query_incident_by_id(2)
# → {"id": 2, "status": "open", "category": "it_system", ...}
``````

### 4.2 Tool de inventario (extra)

| Aspecto | Detalle |
|---------|---------|
| **Entrada** | `product_id: int` (opcional) o filtros: `category`, `name_search` |
| **Salida** | `id, name, sku, category, unit, current_stock, expiry_date, country` |
| **Endpoint real** | `GET /inventory/products/{id}` o `GET /inventory/products?category=...` |
| **Timeout** | **5 segundos** — explícito en `_INVENTORY_TIMEOUT_S` |
| **Solo lectura** | Sí — solo GET |
| **Autenticación** | Requiere JWT Bearer token. Se lee de `AGENT_JWT_TOKEN` (env). Sin token devuelve 401 → fallback honesto |
| **URL base** | `INVENTORY_API_URL` (env) → fallback `http://backend:8000` |

## 5. El grafo actualizado (Parte 1 + Parte 2)

### 5.1 Diagrama de flujo

```
                    ┌──────────────────┐
                    │ receive_question │  (valida la entrada)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ ¿Pregunta valida?│
                    └────┬─────────┬───┘
                  ┌──────┘         └───────┐
                  ▼                        ▼
          ┌───────────────┐             ╔════╗
          │ classify_query│             ║ END║
          └───────┬───────┘             ╚════╝
                  │
        ┌─────────┼──────────────┐
        ▼         ▼              ▼
  ┌─────────┐ ┌────────┐ ┌──────────┐
  │retrieve │ │query_  │ │query_    │
  │_context │ │incident│ │inventory │
  └────┬────┘ └───┬────┘ └─────┬────┘
       │          │            │
       │    ┌─────┴─────┐      │
       │    ▼           ▼      │
       │ ┌────────┐ ┌────────┐ │
       │ │synthe- │ │retrieve│ │
       │ │size    │ │_context│ │
       │ │_tool   │ │(si     │ │
       │ │_answer │ │rag+tool│ │
       │ └────────┘ └────┬───┘ │
       │                 │     │
       │          ┌──────┘     │
       │          ▼            ▼
       │   ┌────────────┐  ┌──────────────┐
       │   │generate_   │  │synthesize_   │
       │   │answer /    │  │tool_answer/  │
       │   │respond_no  │  │handle_error  │
       │   │_info       │  │              │
       │   └────────────┘  └──────────────┘
       ▼           ▼              ▼
    ╔════╗     ╔════╗        ╔════╗
    ║ END║     ║ END║        ║ END║
    ╚════╝     ╚════╝        ╚════╝
```

### 5.2 Estado del grafo — campos nuevos (Parte 2)

| Campo | Tipo | Reducer | Descripción |
|-------|------|---------|-------------|
| `routing_decision` | `str` | — | `"rag"`, `"incident"`, `"inventory"`, `"rag+incident"`, `"rag+inventory"` |
| `tool_results` | `list[dict]` | `_accumulate_list` | Resultados normalizados de las tools |
| `tool_errors` | `list[str]` | `_accumulate_list` | Errores de las tools (fallback) |

### 5.3 Nodos nuevos (Parte 2)

| Nodo | Función | Input | Output | Responsabilidad |
|------|---------|-------|--------|----------------|
| `classify_query` | `node_classify_query` | `question` | `routing_decision` | Clasificar la pregunta: RAG, tool, o ambos |
| `query_incident` | `node_query_incident` | `question` | `tool_results` / `tool_errors` | Consultar gestor de incidentes (HTTP, timeout 5s) |
| `query_inventory` | `node_query_inventory` | `question` | `tool_results` / `tool_errors` | Consultar gestor de inventario (HTTP, timeout 5s) |
| `synthesize_tool_answer` | `node_synthesize_tool_answer` | `tool_results` + `tool_errors` | `answer` | Sintetizar respuesta legible desde datos de tools |

### 5.4 Aristas condicionales nuevas

| Desde | Router | Lógica |
|-------|--------|--------|
| `receive_question` | `route_after_receive` | Ahora enruta a `classify_query` en vez de directamente a `retrieve_context` |
| `classify_query` | `route_after_classify` | Según `routing_decision`: si es `"rag"` → `retrieve_context`; `"incident"` → `query_incident`; `"inventory"` → `query_inventory`; etc. |
| `query_incident` / `query_inventory` | `route_after_tool` | Si era combinado (`rag+incident`, `rag+inventory`) → `retrieve_context`; si solo tool → `synthesize_tool_answer` |
| `retrieve_context` | `route_after_retrieve_v2` | Como la original + detecta si hay `tool_results` para enrutar a `synthesize_tool_answer`. **Prioridad**: RAG → generate_answer; tools sin RAG → synthesize; ambos → RAG primero. |
| `generate_answer` | `route_after_generate` | Si hay tools pendientes (`tool_results` o `tool_errors`) → `synthesize_tool_answer`; si no → END |

## 6. Clasificación de preguntas

El nodo `classify_query` analiza la pregunta con **patrones léxicos** (regex), no necesita un LLM para decidir la fuente:

### Patrones para incidentes
```python
incident_patterns = [
    r"\bticket\b", r"\bincidente\b", r"\bestado\s+del?\s+(ticket|incidente|caso)\b",
    r"\btickets?\b", r"\bticket\s+\d+\b", r"\b#\d+\b",
    r"\bseguimiento\b", r"\bpendiente\b", r"\bcerrado\b",
    r"\ben\s+progreso\b", r"\bresuelto\b"
]
```

### Patrones para inventario
```python
inventory_patterns = [
    r"\bstock\b", r"\binventario\b", r"\bproducto\b", r"\bsuministro\b",
    r"\btenemos\s+stock\b", r"\bcu[aá]nto\s+stock\b", r"\bdisponible\b",
    r"\bhay\s+stock\b", r"\bsku\b", r"\bmedicamento\b", r"\binsumo\b"
]
```

### Regla de decisión
- Si solo hay patrones de incidentes → `"incident"`
- Si solo hay patrones de inventario → `"inventory"`
- Si solo hay patrones RAG → `"rag"`
- Si hay patrones de incidentes + RAG → `"rag+incident"`
- Si hay patrones de inventario + RAG → `"rag+inventory"`
- Si no hay patrones claros → `"rag"` (fallback por defecto)

## 7. Timeout y fallback

Todas las tools usan `httpx.Client(timeout=5)` con manejo explícito de:

| Escenario | Comportamiento |
|-----------|---------------|
| Timeout (>5s) | `tool_errors` contiene mensaje: "El servicio no respondió en Xs" |
| Conexión rechazada | `tool_errors` contiene mensaje de conexión fallida |
| HTTP 404 | `tool_errors` contiene "No existe un ticket/producto con ID X" |
| HTTP 401 (solo inventario) | `tool_errors` contiene mensaje de autenticación fallida |
| HTTP 500+ | `tool_errors` contiene mensaje genérico |
| Éxito | `tool_results` contiene datos normalizados |

Cuando todas las tools fallan, `node_synthesize_tool_answer` produce una respuesta honesta como:

> "No pude completar la consulta solicitada: [error]. Por favor verifica que los datos estén disponibles o intenta de nuevo más tarde."

## 8. Trazabilidad (Parte 2)

El trace ahora incluye eventos de los nuevos nodos. Ejemplo para pregunta de incidente:

```json
{
  "events": [
    {"node": "receive_question", "status": "ok", "metadata": {"question_length": 28}},
    {"node": "classify_query", "status": "ok", "metadata": {"decision": "incident", "has_incident": true, "has_inventory": false, "has_rag": false}},
    {"node": "query_incident", "status": "ok", "metadata": {"num_results": 1}},
    {"node": "synthesize_tool_answer", "status": "ok", "metadata": {"decision": "incident", "num_results": 1}}
  ],
  "routing_log": [
    "receive_question → classify_query (pregunta válida)",
    "classify_query → incident",
    "query_incident → 1 resultado(s)",
    "synthesize_tool_answer → respuesta (1 resultado(s))"
  ]
}
```

Cada evento del nodo `classify_query` incluye en `metadata` la decisión y los flags booleanos `has_incident`, `has_inventory`, `has_rag` — así se puede auditar por qué el agente eligió esa fuente.

## 9. Evaluación y Tests (Parte 2)

### 9.1 Nuevos evals (12 tests añadidos)

| Clase | # Tests | ¿Qué verifica? |
|-------|---------|----------------|
| `TestExternalToolRouting` | 5 | El enrutamiento automático: incidente → tool, política → RAG, stock → inventario, mixto → ambos, genérico → RAG |
| `TestToolFallbackBehavior` | 5 | Timeout → respuesta honesta, ticket no encontrado → error, synthesis con fallos → honestidad, extracción de IDs, trace events contienen decisión |
| `TestMixedSynthesis` | 2 | Síntesis rag+incident combina RAG y tool; modo combinado con falla de tool incluye RAG + error honesto |

**Total: 32 tests** (20 Parte 1 + 12 Parte 2)

### 9.2 Tests clave

```python
def test_classify_query_routes_incident_to_incident_tool(self):
    """Pregunta sobre un ticket/incidente debe clasificarse como 'incident'."""
    state = build_initial_state("¿En qué estado está el ticket 2?")
    result = node_classify_query(state)
    assert "incident" in result["routing_decision"]

def test_classify_query_routes_policy_to_rag(self):
    """Pregunta sobre política debe clasificarse como 'rag'."""
    state = build_initial_state("¿Cuál es la política de cancelación de citas?")
    result = node_classify_query(state)
    assert result["routing_decision"] == "rag"

def test_tool_timeout_returns_honest_fallback(self):
    """Timeout en tool debe producir respuesta honesta, no datos inventados."""
    # Simula timeout de httpx
    with patch("services.agent.tools.incidents.httpx.Client.get", _timeout_get):
        result = node_query_incident(state)
    assert len(result["tool_errors"]) > 0
    assert "no respondió" in error_text

def test_incident_tool_extracts_ticket_id_from_question(self):
    """Extrae IDs de distintos formatos: 'ticket 2', '#123', 'caso 456'."""
    assert _extract_ticket_id("ticket 2") == 2
    assert _extract_ticket_id("incidente #123") == 123
```

### 9.3 Cómo ejecutar

```bash
# Todos los tests del agente (Parte 1 + Parte 2)
uv run pytest tests/pipelines/test_agent_graph.py -v

# Tests específicos de tools externas y síntesis mixta
uv run pytest tests/pipelines/test_agent_graph.py -v -k "TestExternalToolRouting or TestToolFallbackBehavior or TestMixedSynthesis"
```

## 10. Notas sobre autenticación

- **Incidents API**: No requiere autenticación en el despliegue actual. Para producción se recomienda añadir JWT o API key.
- **Inventory API**: Requiere JWT Bearer token. La tool lee el token de la variable de entorno `AGENT_JWT_TOKEN`. Si no está configurada, la tool devuelve un error controlado (HTTP 401) y el grafo responde con fallback honesto. **No se hardcodea ningún token en el código.**

## 10.1 Corrección de bugs — Síntesis mixta y trazas (2026-11-15)

### Bug 1: Síntesis mixta rag+incident descartaba el contexto RAG
**Problema**: `route_after_retrieve_v2` iba directo a `synthesize_tool_answer` cuando había `tool_results`, saltándose `generate_answer` y perdiendo el contexto político de RAG.
**Solución**: Se reordenó la prioridad: si hay `retrieved_chunks` (contexto RAG), siempre va primero a `generate_answer`, independientemente de `tool_results`. Luego `route_after_generate` redirige a `synthesize_tool_answer`.

### Bug 2: Prueba de timeout real bloqueaba 5 segundos la suite de tests
**Problema**: El test de timeout usaba `sleep(5)` para forzar el timeout de httpx.
**Solución**: Reemplazado por monkeypatch del timeout en `httpx.Client` dentro del test. Ahora el timeout se simula en milisegundos.

### Bug 3: Clasificación combinada no detectaba "política" + "ticket"
**Problema**: El clasificador léxico no detectaba `rag+incident` cuando ambas señales estaban presentes (ej: "¿cuál es la política de no-show del ticket 2?").
**Solución**: `node_classify_query` ahora usa prioridad combinada: si hay incidente y RAG → `"rag+incident"`. Se reescribieron los patrones RAG para incluir términos operativos ("cobro", "cargo", "no-show", "medicare", "cancelación", "horario", "consentimiento").

### Bug 4: Trazas del script `regenerate_traces.py` tenían timestamps sub-ms (mockeadas)
**Problema**: El script mockeaba `retrieve` y `generate_answer`, produciendo timestamps irreales (~1ms).
**Solución**: Se eliminaron todos los mocks. Ahora llama a servicios reales (Qdrant, LLM e Incidents API). Timestamps reales obtenidos:
- RAG puro (Medicare no-show): **5,788ms**
- Incidente puro (ticket 2): **41ms** con `branch_label = "London West End"` (antes decía "London — West")
- RAG+Incidente combinado: **2,892ms**
- RAG+Incidente con fallo de tool: **1,649ms**

## 11. Checklist de cumplimiento (Parte 2)

- [x] Tool `query_incident` implementada — lee del gestor de incidentes real (GET /api/incidents)
- [x] Tool `query_inventory` implementada — lee del gestor de inventario real (GET /inventory/products)
- [x] Contrato tipado de entrada/salida documentado
- [x] Solo lectura (GET) — nunca crea, actualiza ni elimina datos
- [x] Timeout explícito de 5 segundos para cada tool
- [x] Ruta de fallback: si la tool falla, el agente responde con honestidad
- [x] Enrutamiento automático: el agente decide RAG, tool o ambos sin intervención del usuario
- [x] Sin datos simulados — las tools llaman a servicios reales
- [x] Sin auth hardcodeada — las credenciales se leen de entorno
- [x] 12 nuevos evals que verifican enrutamiento, fallback y síntesis mixta
- [x] Trazabilidad: el trace muestra qué fuente se usó y en qué orden
- [x] 32/32 tests pasando