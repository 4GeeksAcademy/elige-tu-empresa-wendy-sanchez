# Documento de Diseño RAG — HealthCore Knowledge Base

## 1. Arquitectura General

```
┌──────────────────────────────────────────────────────┐
│                 Pregunta del Usuario                 │
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
│             Respuesta natural (str)                  │
└──────────────────────────────────────────────────────┘
```

**Cinco funciones principales, cada una con una única responsabilidad:**

| Función | Módulo | Responsabilidad |
|---|---|---|
| `setup()` | `data/process/rag.py` | Leer documentos fuente, fragmentar, embedding, indexar en Qdrant |
| `embed(text)` | `data/process/rag.py` | Convertir texto → vector usando modelo de embedding dedicado |
| `retrieve(query, *, k, min_score)` | `data/pipelines/rag.py` | Embedear *query* internamente, búsqueda vectorial en Qdrant, devolver payloads de los top-k fragmentos |
| `generate_answer(question, context)` | `data/pipelines/rag.py` | Construir prompt a partir de fragmentos + pregunta, llamar al LLM, devolver str plano |
| `query(question, *, k, min_score)` | `data/pipelines/rag.py` | Orquestar retrieve + generate_answer, devolver str plano |

## 2. Modelos

| Propósito | ID del Modelo | Proveedor |
|---|---|---|
| **Embedding** | `madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` | 4Geeks AI (OpenRouter) |
| **Generación** | `madrid-spain/openrouter/deepseek/deepseek-v4-flash` | 4Geeks AI (OpenRouter) |

- **Modelo de embedding** produce vectores de 1024 dimensiones. Se usa exclusivamente en `embed()`.
- **Modelo de generación** es un LLM conversacional. Se usa exclusivamente en `generate_answer()`.
- Ambos se acceden vía API compatible con OpenAI en `HOST` con `API_KEY`.

## 3. Colección: `healthcore_knowledge`

### Configuración del vector
- Distancia: `Cosine`
- Dimensión: `1024`

### Esquema del payload

```json
{
  "company": "healthcore",
  "source_document": "insurance-coverage | appointment-policy | referral-process | new-patient-checklist",
  "section": "encabezado o subsección del documento fuente",
  "language": "es",
  "chunk_index": 0,
  "text": "texto completo del fragmento"
}
```

### Campos indexados del payload (para filtrado)
- `source_document` — keyword
- `language` — keyword

### Estrategia de idempotencia: **Clean-and-reload**

En desarrollo, `setup()` elimina y recrea la colección en cada ejecución.
Esto evita duplicados sin mantener estado de IDs externos.
Para producción, cambiar a UUIDs deterministas basados en hash del contenido.

**Razón:** La base de conocimiento es pequeña (4 documentos, ~12 fragmentos).
Clean-and-reload es simple, correcto y rápido. Los IDs deterministas (basados en hash)
están documentados como ruta de actualización a producción.

## 4. Estrategia de Fragmentación

**Fragmentación semántica por documento.**

| Documento | Secciones | Mín. fragmentos |
|---|---|---|
| `healthcore-insurance-coverage.es.md` | Cobertura EEUU, cobertura UK, no asegurados | ≥3 |
| `healthcore-appointment-policy.es.md` | Reserva, cancelación, recordatorios, no-show | ≥3 |
| `healthcore-referral-process.es.md` | Pasos del proceso, tiempos, escalación | ≥3 |
| `healthcore-new-patient-checklist.es.md` | Pre-cita, documentos, consentimiento | ≥3 |

**Reglas:**
- Nunca dividir en medio de una oración o párrafo.
- Cada fragmento es autocontenido.
- Los encabezados se usan como payload `section`.
- Los fragmentos preservan la estructura Markdown.

## 5. Parámetros de Recuperación

| Parámetro | Valor por Defecto | Razón |
|---|---|---|
| `k` | 5 | Recall@3 ≥ 80% según CONTEXT.md; k=5 da margen sobre el mínimo requerido. |
| `min_score` | 0.5 | Límite inferior de similitud coseno; evita ruido. Elegido observando la distribución de puntuaciones en consultas de prueba. |
| `rerank` | No (v1) | Puede añadirse después como paso sin estado entre retrieve y generate. |

**Comportamiento con puntuación baja:** Si ningún fragmento supera `min_score`,
`retrieve()` devuelve lista vacía y `query()` responde:
*"No tengo información suficiente en la base de conocimiento para responder esta pregunta."*

## 6. Plantilla del Prompt de Generación

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

## 7. Consultas de Prueba

Archivo: `data/eval/test-queries.json`
8 consultas que cubren los 4 documentos, con documento fuente esperado y verificación de fidelidad.

## 8. KPIs — Indicadores Clave de Rendimiento

| KPI | Objetivo | Método |
|---|---|---|
| Recall@3 | ≥ 80% | Evaluación manual contra test-queries.json (requisito de CONTEXT.md) |
| Fidelidad (Faithfulness) | 100% | Cada respuesta verificada contra los fragmentos fuente |
| Cobertura de umbral | 100% | Todas las consultas bajo el umbral devuelven la respuesta "sin información" |

## 9. Estructura de Archivos

```
docs/company-knowledge-base/
  healthcore-insurance-coverage.es.md       ← Corpus fuente
  healthcore-appointment-policy.es.md       ← Corpus fuente
  healthcore-referral-process.es.md         ← Corpus fuente
  healthcore-new-patient-checklist.es.md    ← Corpus fuente
data/process/rag.py                         ← setup(), embed()
data/pipelines/rag.py                       ← retrieve(), query()
services/api/routes/rag.py                  ← Router FastAPI
services/api/routes/knowledge.py            ← Endpoint público /knowledge/query
uis/backoffice/components/KnowledgePanel.tsx ← UI React
tests/pipelines/test_rag.py                 ← Tests unitarios
docs/rag/rag-design.es.md                   ← Este documento
data/eval/test-queries.json                 ← Consultas de evaluación
```

## 10. Flujo RAG Extremo a Extremo

La siguiente secuencia numerada traza una pregunta del coordinador a través
de todo el pipeline hasta la respuesta final.

```
┌─────────┐     ┌──────────────────┐     ┌────────────┐
│ Usuario │     │  Router FastAPI  │     │  Qdrant    │
│ Consulta│ ──► │  /knowledge/query│     │  (almacén  │
│         │     │  POST            │     │  vectorial)│
└─────────┘     └────────┬─────────┘     └────────────┘
                         │                       ▲
                         ▼                       │
                  ┌──────────────┐               │
                  │ query()      │               │
                  │  (orquest.)  │               │
                  └──────┬───────┘               │
                         │                       │
              ┌──────────▼──────────┐            │
              │  1. retrieve()      │────────────┘
              │     embed(query)    │  2. query_points()
              │     → vector        │     (coseno, 1024d)
              │     → búsq. Qdrant  │
              │     → chunks[ ]     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 3. generate_answer() │
              │    _build_context()  │ ──► prompt con chunks
              │    _generate()       │ ──► llamada LLM
              │    → str             │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  4. Respuesta        │
              │  {"answer": "..."}   │
              └──────────────────────┘
```

### Paso a paso

| Paso | Qué ocurre | Ubicación en el código |
|---|---|---|
| **0. Setup (una vez)** | `setup()` lee los 4 archivos `.es.md` de `docs/company-knowledge-base/`, los parsea en secciones Markdown, fragmenta cada sección (mín 200 chars, máx 1500 chars por fragmento), embe be cada fragmento con `embed()` y lo indexa en la colección Qdrant `healthcore_knowledge`. | `data/process/rag.py::setup()` → `load_corpus()` → `chunk_document()` → `embed()` → Qdrant upsert |
| **1. Retrieve** | `query("¿Qué seguros?")` llama a `retrieve("¿Qué seguros?")`. Dentro de `retrieve()`: (a) importa y llama a `embed()` de `data.process.rag` — esto usa el modelo de **embedding** (`pplx-embed-v1-0.6b`, 1024‑dim), no el de generación. (b) envía el vector resultante a Qdrant vía `query_points()` con distancia `coseno`, `limit=k` (default 5), `score_threshold=min_score` (default 0.5). (c) Devuelve los payloads con `_score` añadido. | `data/pipelines/rag.py::retrieve()` |
| **2. Filtro por umbral** | Qdrant devuelve como máximo `k` resultados, pero `score_threshold` excluye los que estén por debajo de 0.5. Si **todos** los resultados están por debajo del umbral, `retrieve()` devuelve `[]`. Esto cumple la regla de CONTEXT.md: sin información → no inventar datos. | `query_points(…, score_threshold=…)` |
| **3. Construir contexto** | `generate_answer()` recibe la lista de fragmentos. `_build_context()` formatea cada fragmento como `[Fuente N: doc — section]\ntext`, unidos por dobles saltos de línea. Si la lista está vacía, se devuelve `NO_CHUNKS_MESSAGE` inmediatamente sin llamar al LLM. | `data/pipelines/rag.py::generate_answer()` → `_build_context()` |
| **4. Generar** | `_generate()` llena la plantilla `SYSTEM_PROMPT` con `{context}` y `{question}`, luego llama al modelo de **generación** (`deepseek-v4-flash`, chat completions, temperature 0.3, max_tokens 2000). Devuelve la respuesta en texto plano. Un fallback maneja `content=None` (modelos de razonamiento) extrayendo la última frase de `reasoning_content`. | `data/pipelines/rag.py::_generate()` |
| **5. Respuesta** | El string sube: `_generate()` → `generate_answer()` → `query()` → `query_knowledge()` → `QueryResponse(answer=…)` → HTTP 200 JSON. | `services/api/routes/knowledge.py::query_knowledge()` |

### Lo que NO ocurre
- Los fragmentos crudos o puntuaciones de similitud **nunca** se devuelven al usuario.
- El modelo de embedding (`pplx-embed-v1-0.6b`) **nunca** se usa para generación, y viceversa.
- No hay lógica de negocio ni prompt engineering duplicados en los endpoints — solo llaman a `query()` / `retrieve()` + `generate_answer()`.

---

## 11. Estrategia de Fragmentación — Detalle

### Por qué esta estrategia encaja con el corpus

Los 4 documentos fuente son archivos Markdown cortos y estructurados (≈1 000 caracteres cada uno, un solo encabezado principal). Por esto:

1. **Cada documento cabe en un fragmento.** Cada doc tiene un encabezado `# Título` seguido de párrafos. El fragmentador lee todo el cuerpo de la sección, y como está por debajo de `CHUNK_MAX_CHARS=1500`, se queda como un solo fragmento. No es necesario dividir entre secciones.

2. **Las unidades semánticas se preservan naturalmente.** Cada documento trata de un tema: cobertura de seguros, política de citas, proceso de referencias o checklist de pacientes nuevos. Mantener cada uno como un fragmento único garantiza que ninguna regla o condición se corta a mitad de un párrafo.

3. **Los encabezados se convierten en metadatos de sección.** El `# Título` es parseado por `_parse_markdown_sections()` y se convierte en el campo `section` del payload. Esto permite al LLM saber exactamente de qué documento proviene el fragmento.

### Parámetros

| Parámetro | Valor | Por qué |
|---|---|---|
| `CHUNK_MIN_CHARS` | 200 | Descartar secciones casi vacías (ningún documento está por debajo). |
| `CHUNK_MAX_CHARS` | 1 500 | Límite de seguridad; si un documento crece en el futuro, los párrafos se acumulan en búferes que se vacían en este límite. Ningún párrafo se divide. |
| `Solapamiento (overlap)` | 0 (ninguno) | Los documentos son cortos y monotemáticos; el solapamiento añadiría vectores duplicados sin beneficio. |

### Conteo real de fragmentos

| Documento | Fragmentos | Encabezado de sección | Rango de tamaño (chars) |
|---|---|---|---|
| `healthcore-insurance-coverage.es.md` | 1 | `Cobertura de Seguros Aceptados` | 1 090 |
| `healthcore-appointment-policy.es.md` | 1 | `Política de Citas y Cancelaciones` | 952 |
| `healthcore-referral-process.es.md` | 1 | `Proceso de Referencia Interna` | 1 132 |
| `new-patient-checklist.es.md` | 1 | `Checklist para Pacientes Nuevos` | 943 |
| **Total** | **4** | — | 943–1 132 |

### Qué se evitó
- **Cortes a mitad de párrafo.** El fragmentador acumula párrafos completos y solo vacía el búfer cuando el siguiente párrafo superaría `CHUNK_MAX_CHARS`. Esto garantiza unidades coherentes.
- **Contexto de sección perdido.** El encabezado de sección se registra por fragmento, así que incluso si un documento futuro fuera lo suficientemente grande para dividirse, cada fragmento conservaría su nombre de sección.
- **Reglas de negocio huérfanas.** Reglas como "Pacientes con Medicare/Medicaid: no se les cobra cargo por no-show" son párrafos cortos que caben cómodamente. Un fragmentador que dividiera por conteo fijo de tokens podría haber separado la condición ("Medicare/Medicaid") de la consecuencia ("no charge").

---

## 12. Prácticas de Embeddings

### Separación de modelos

| Rol | ID del modelo | Variable de cliente | Usado en |
|---|---|---|---|
| **Embedding** | `madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` | `_embed_client` (`data/process/rag.py`) | `embed()` durante indexación (setup) y recuperación (retrieve) |
| **Generación** | `madrid-spain/openrouter/deepseek/deepseek-v4-flash` | `_gen_client` (`data/pipelines/rag.py`) | `_generate()` solamente |

Ambos son proporcionados por el endpoint OpenRouter de 4Geeks Academy. El modelo de embedding **no** se usa para generación y el modelo de generación **no** se usa para embeddings. Son clientes completamente separados con claves API independientes (o la misma clave en el mismo host, si `EMBEDDING_API_KEY`/`EMBEDDING_HOST` no están sobreescritos en `.env`).

### Uso consistente de embed()

`embed()` vive en `data/process/rag.py` y es la **única** función que llama a la API de embeddings. Se usa:
- **Al indexar:** `setup()` → `load_corpus()` → `chunk_document()` → `embed(chunk["text"])` para cada fragmento.
- **Al recuperar:** `retrieve()` importa `from data.process.rag import embed` (dentro del cuerpo de la función, para evitar imports circulares) y llama a `embed(query)` para convertir la pregunta del usuario en un vector.

Como la misma función `embed()` se llama en ambos caminos, la representación vectorial es idéntica para el mismo texto, ya sea como fragmento almacenado o como consulta.

### Detalles del vector

| Propiedad | Valor |
|---|---|
| Modelo | `pplx-embed-v1-0.6b` (Perplexity, vía OpenRouter) |
| Dimensión de salida | **1024** |
| Métrica de distancia | **Coseno** (configurada en Qdrant `VectorParams`) |
| Búsqueda Qdrant | `client.query_points(…, score_threshold=…)` — devuelve ≤k resultados, ordenados por similitud descendente |

### Umbral de similitud (min_score)

| Aspecto | Detalle |
|---|---|
| Valor por defecto | `0.5` |
| Cómo se aplica | Se pasa como `score_threshold` a `query_points()` de Qdrant. Cuando `min_score=0.0`, el umbral se desactiva (`None` enviado a Qdrant, devolviendo todos los k resultados). |
| Por qué 0.5 | Elegido empíricamente ejecutando las 8 consultas de prueba y observando la distribución de puntuaciones coseno. Las puntuaciones ≥ 0.5 devuelven sistemáticamente fragmentos relevantes; las puntuaciones por debajo de 0.5 son ruido de temas no relacionados. |
| Comportamiento cuando ningún fragmento pasa | `retrieve()` devuelve `[]` → `generate_answer([])` devuelve `NO_CHUNKS_MESSAGE` → el usuario ve "No encontré información relevante…". |
| Notas de ajuste | 0.5 es conservador. Con solo 4 fragmentos en el corpus, en la práctica la puntuación del top‑1 suele ser > 0.7 para preguntas relevantes. El umbral protege principalmente contra preguntas fuera de tema que devuelven falsos positivos con baja puntuación. |

### Preprocesado antes del embedding

El pipeline aplica un **preprocesado mínimo e idempotente** — solo lo necesario para producir una cadena de texto limpia para el modelo de embedding:

1. **Eliminar espacios en blanco** de cada párrafo (`p.strip()`) y de los encabezados de sección (`heading_match.group(2).strip()`).
2. **Normalizar finales de línea** leyendo el archivo con `read_text(encoding="utf‑8")` — no se necesita conversión CRLF→LF en sistemas modernos.
3. **Sin minúsculas, sin eliminación de stop‑words, sin stemming.** Estas técnicas no benefician a los modelos de embedding basados en transformadores (que usan tokenización por subpalabras y manejan mayúsculas/minúsculas de forma natural).
4. **Sin desescapado de HTML/entidades.** Los documentos fuente son Markdown plano sin entidades HTML.

El mismo preprocesado se aplica tanto al indexar (a través de `chunk_document()`) como al recuperar (la pregunta del usuario se pasa a `embed()` tal cual, solo con el `strip()` del llamador). Esto garantiza que el embedding vea el texto en el mismo formato en ambos caminos.

### Configuración de la API de Embedding

```python
# data/process/rag.py
EMBEDDING_MODEL = "madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b"
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY") or os.getenv("API_KEY")
EMBEDDING_HOST    = os.getenv("EMBEDDING_HOST")    or os.getenv("HOST")

client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_HOST + "/v1")
resp = client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
vector = resp.data[0].embedding
```

La misma librería compatible con OpenAI (`openai` de Python) maneja tanto embeddings como chat completions, pero con diferentes instancias de cliente apuntando a diferentes URLs base o modelos.

---

## 13. Ruta de Actualización a Producción

1. UUIDs deterministas (hash de `source_document + chunk_index + text`) en lugar de clean-and-reload.
2. Añadir reranker (ej. Cohere o BGE) entre retrieve y generate.
3. Expansión de consultas / HyDE para mejorar la recuperación.
4. Añadir respuestas streaming desde el modelo de generación.
5. Marco de evaluación A/B para tamaño de fragmento y parámetros de recuperación.