# Documento de Diseño RAG — HealthCore Knowledge Base

## 1. Arquitectura General

```
┌──────────────────────────────────────────────────────┐
│                 Pregunta del Usuario                  │
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
│                    │   question, context)  │           │
│                    │   → str               │           │
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
| `k` | 5 | Recall@5 ≥ 90%; mayor que top_k=3 de v1 para cobertura más amplia. |
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
| Recall@5 | ≥ 90% | Evaluación manual contra test-queries.json |
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

## 10. Ruta de Actualización a Producción

1. UUIDs deterministas (hash de `source_document + chunk_index + text`) en lugar de clean-and-reload.
2. Añadir reranker (ej. Cohere o BGE) entre retrieve y generate.
3. Expansión de consultas / HyDE para mejorar la recuperación.
4. Añadir respuestas streaming desde el modelo de generación.
5. Marco de evaluación A/B para tamaño de fragmento y parámetros de recuperación.