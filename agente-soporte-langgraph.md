# Agente de Soporte LangGraph — Documentación

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
| `receive_question` | `route_after_receive` | `error` o `question_valid=False` → END; válida → `retrieve_context` |
| `retrieve_context` | `route_after_retrieve` | `error` → `handle_error`; sin chunks → `respond_no_info`; con chunks → `generate_answer` |
| `generate_answer` | `route_after_generate` | `error` → `handle_error`; ok → END |

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
    "receive_question → retrieve_context (pregunta válida)",
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

### 6.1 Evals (20 tests en `tests/pipelines/test_agent_graph.py`)

| Clase | # Tests | ¿Qué verifica? |
|-------|---------|----------------|
| `TestGraphCompilation` | 3 | El grafo compila, tiene todos los nodos, entry point correcto |
| `TestConditionalRouting` | 7 | Cada arista condicional enruta correctamente según el estado |
| `TestTraceability` | 4 | Cada corrida produce trace persistido, consultable, con eventos y routing_log |
| `TestRAGBehavior` | 4 | El comportamiento RAG está anclado en los datos: retrieve antes que generate, Medicare no paga no-show verificado con fake LLM (solo responde con contexto), etc. |
| `TestAgentEndpoint` | 2 | El endpoint existe con prefijo correcto y delega en `run_agent()` |

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
- [x] 20 evals que verifican compilación, enrutamiento, trazabilidad y comportamiento RAG
- [x] Respuestas de error sin stack traces crudos (503 con mensaje genérico, sin `str(exc)`)
- [x] `persist_trace()` escribe con `encoding="utf-8"` (portabilidad Windows)
- [x] Test de grounding con fake LLM (no mock prefabricado) — verifica que `generate_answer` recibe el fragmento y la respuesta sale de él