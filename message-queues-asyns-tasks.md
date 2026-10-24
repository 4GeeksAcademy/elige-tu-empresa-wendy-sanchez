# Cola de Tareas Asíncronas — Redis + Celery

## Contexto

Este documento describe la implementación del sistema de **cola de tareas asíncronas** en HealthCore, utilizando **Redis como broker** y **Celery como framework de tareas**. El objetivo principal es **desacoplar las operaciones pesadas de la API** para que los endpoints respondan inmediatamente (HTTP 202 Accepted) mientras un worker independiente procesa la tarea en segundo plano.

## Arquitectura

```
┌─────────────┐      ┌──────────┐      ┌─────────────┐
│  Cliente    │      │  Redis   │      │   Worker    │
│  (HTTP)     │─────→│ (Broker) │─────→│ (Celery)    │
└──────┬──────┘      └──────────┘      └──────┬──────┘
       │ 1. POST /analyze                      │ 2. Procesa CSV
       │    → 202 {task_id}                    │    (sync)
       │                                       │
       │ 3. GET /tasks/{task_id}               │
       │    → {state: SUCCESS, result: ...}    │
       ◄───────────────────────────────────────┘
```

### Roles

| Componente | Rol | Descripción |
|---|---|---|
| **FastAPI** | **Productor** | Recibe la solicitud HTTP, crea un mensaje ligero y lo deposita en la cola Redis. Devuelve 202 Accepted inmediatamente. |
| **Redis** | **Broker** | Almacenamiento persistente de mensajes en memoria. Si el worker se cae, los mensajes no se pierden. Política `noeviction`. |
| **Celery Worker** | **Consumidor** | Proceso independiente que escucha la cola, toma mensajes de uno en uno y los procesa. Corre en un contenedor separado. |
| **Flower** | **Monitor** | Interfaz web para inspeccionar colas, workers y tareas en tiempo real. |
| **TinyDB (DLQ)** | **Dead Letter Queue** | Almacena tareas que fallaron tras 3 intentos con task_id, error y timestamp. |

### Reglas del patrón Productor-Consumidor

1. **Los mensajes son ligeros**: nunca se pone un blob completo (imagen, documento) en el mensaje. Solo metadatos y referencias.
2. **Productor y consumidor son procesos distintos**: la API nunca ejecuta la tarea pesada; solo la encola.
3. **El broker es persistente**: Redis con AOF (Append-Only File) y `noeviction` garantiza que los mensajes no se pierden.

## Decisiones técnicas

### ¿Por qué Celery?

- **Madurez**: ecosistema estable, documentación extensa, usado en producción desde 2009.
- **Flexibilidad**: soporta múltiples brokers (Redis, RabbitMQ, SQS) y backends de resultados.
- **Reintentos nativos**: `autoretry_for`, `max_retries`, `retry_backoff` resuelven el 80% de los casos de fallo.
- **Monitoreo**: Flower proporciona visibilidad inmediata de colas, workers y tareas.
- **Integración con FastAPI**: ambas son bibliotecas Python que se integran sin fricción.

### ¿Por qué Redis como broker?

- **Ya es estándar**: Redis es el broker más común con Celery en desarrollo.
- **Velocidad**: operaciones sub-milisegundo para encolar/desencolar.
- **Persistencia opcional**: con AOF activado, los mensajes sobreviven a reinicios.
- **Política noeviction**: garantiza que nunca se descarten mensajes por falta de memoria (crítico para una cola de tareas).

### ¿Por qué noeviction?

Redis por defecto puede eliminar claves cuando alcanza el límite de memoria (`maxmemory`). Para un broker de mensajería esto es inaceptable: perderíamos tareas. `noeviction` lanza errores en escritura en lugar de borrar datos, forzándonos a dimensionar correctamente la memoria o añadir alertas.

### ¿Por qué TinyDB para la DLQ en lugar de Redis?

- **Persistencia duradera**: la DLQ debe sobrevivir a reinicios de Redis.
- **Auditabilidad**: un fichero JSON es fácilmente exportable, consultable y backupable.
- **Simplicidad**: para el volumen esperado de fallos, TinyDB es suficiente. En producción se migraría a PostgreSQL.

## Implementación

### 1. Infraestructura (docker-compose.yml)

```yaml
redis:
  image: redis:7-alpine
  command: ["redis-server", "--appendonly", "yes", "--maxmemory-policy", "noeviction"]

flower:
  image: mher/flower:2.0
  ports: ["5555:5555"]
  environment:
    CELERY_BROKER_URL: "${REDIS_URL}"

celery-worker:
  build: ./services/Dockerfile
  working_dir: /workspace
  command: celery -A services.celery_app worker --loglevel=info ...
```

### 2. Módulo Celery (`services/celery_app.py`)

- **Instancia**: `Celery("healthcore", broker=REDIS_URL, backend=REDIS_URL)`
- **Tarea**: `analyze_incidents_csv` — recibe contenido CSV como string, ejecuta `analyze_csv_text`, devuelve el reporte.
- **Reintentos**: `max_retries=3`, `retry_backoff=True` (10s, 20s, 40s), `retry_jitter=True`.
- **DLQ**: cuando `on_failure` se dispara tras agotar reintentos, se persiste en TinyDB (`data/process/task_dlq.json`).

### 3. Endpoint convertido (`POST /api/incidents/analyze`)

**Antes (síncrono):**
```python
@app.post("/api/incidents/analyze", response_model=AnalysisResponse)
async def analyze_incidents(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8")
    report = analyze_csv_text(text)  # ← Bloquea la respuesta
    return AnalysisResponse(...)     # ← El cliente espera
```

**Después (asíncrono):**
```python
@app.post("/api/incidents/analyze", status_code=202)
async def analyze_incidents(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8")
    task = celery_analyze_task.delay(csv_content=text, filename=file.filename)
    return JSONResponse(
        status_code=202,
        content={"task_id": task.id, "status": "PENDING", ...},
    )
```

### 4. Endpoint de consulta (`GET /tasks/{task_id}`)

```python
@router.get("/{task_id}")
def get_task_status(task_id: str):
    async_result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "state": async_result.state,  # PENDING | STARTED | SUCCESS | FAILURE
        "result": async_result.result if SUCCESS else None,
        "error": str(async_result.result) if FAILURE else None,
    }
```

Estados posibles:
| State | Significado |
|---|---|
| `PENDING` | Tarea en cola, ningún worker la ha tomado aún |
| `STARTED` | Un worker está procesándola |
| `SUCCESS` | Tarea completada, `result` disponible |
| `FAILURE` | Tarea falló tras reintentos, en DLQ |

### 5. Dead Letter Queue (DLQ)

Cuando una tarea supera `max_retries=3`, el método `on_failure` de `HealthCoreTask` registra:

```json
{
  "task_id": "uuid-del-task",
  "task_name": "analyze_incidents_csv",
  "attempt": 3,
  "error": "ValueError: CSV inválido",
  "exc_type": "ValueError",
  "timestamp": "2026-10-24T12:00:00Z"
}
```

La DLQ se persiste en `data/process/task_dlq.json` usando TinyDB. Si la tarea está en DLQ, el endpoint `GET /tasks/{task_id}` incluye un campo `dlq` con la información del fallo.

## Flujo completo

```
CLIENTE                     API (FastAPI)               REDIS               WORKER
   │                            │                        │                   │
   │  POST /api/incidents/analyze │                        │                   │
   │  (CSV file)                  │                        │                   │
   │─────────────────────────────→│                        │                   │
   │                              │  task.delay(content)   │                   │
   │                              │────────────────────────→│                  │
   │                              │     (message en cola)   │                   │
   │  202 Accepted                │                        │                   │
   │  {task_id, status:PENDING}   │                        │                   │
   │←─────────────────────────────│                        │                   │
   │                              │                        │  worker toma msg  │
   │                              │                        │←──────────────────│
   │                              │                        │                   │
   │  GET /tasks/{task_id}        │                        │  procesa CSV...   │
   │─────────────────────────────→│                        │                   │
   │  {state: STARTED}            │                        │                   │
   │←─────────────────────────────│                        │                   │
   │                              │                        │  resultado listo  │
   │                              │                        │──────────────────→│
   │                              │                        │  (Redis backend)  │
   │  GET /tasks/{task_id}        │                        │                   │
   │─────────────────────────────→│                        │                   │
   │  {state: SUCCESS, result}    │                        │                   │
   │←─────────────────────────────│                        │                   │
```

## Cómo ejecutar

### Desarrollo local (máquina host)

```bash
# 1. Iniciar Redis
docker compose up redis -d

# 2. Iniciar Flower (monitoreo)
docker compose up flower -d
# Abrir http://localhost:5555

# 3. Iniciar worker
celery -A services.celery_app worker --loglevel=info --concurrency=4

# 4. Iniciar API
cd services/api && uvicorn main:app --reload --port 8000
```

### Desarrollo con Docker Compose (todo incluido)

```bash
# Arrancar todos los servicios
docker compose up --build -d

# Ver logs del worker
docker compose logs -f celery-worker

# Acceder a Flower
open http://localhost:5555
```

### Probar el flujo asíncrono

```bash
# 1. Encolar una tarea
curl -X POST http://localhost:8000/api/incidents/analyze \
  -F "file=@scripts/incidents-healthcore.csv"

# Respuesta:
# {"task_id": "abc-123", "status": "PENDING", ...}

# 2. Consultar estado
curl http://localhost:8000/tasks/abc-123

# Respuesta:
# {"task_id": "abc-123", "state": "SUCCESS", "result": {...}}
```

## Monitoreo con Flower

Flower está disponible en `http://localhost:5555` y proporciona:

- **Dashboard**: workers activos, tareas por segundo, colas.
- **Tasks**: historial completo de tareas con estado, duración y resultado.
- **Broker**: información sobre Redis (mensajes en cola, conexiones).
- **Workers**: lista de workers, suscripción a colas, tareas activas.

## Tareas futuras / mejoras

- [ ] Migrar DLQ de TinyDB a PostgreSQL cuando el volumen lo requiera.
- [ ] Implementar colas prioritarias (salud crítica vs. administrativo).
- [ ] Añadir `task_soft_time_limit` configurable por tarea.
- [ ] Integrar alertas (Slack/email) cuando una tarea caiga en DLQ.
- [ ] Implementar dashboard interno de estado de tareas (vs. depender de Flower en producción).
- [ ] Añadir tests de integración con Redis en pytest usando `factories` o `mock`.

---

## Justificación de endpoints convertidos a asíncronos

A continuación se detalla la justificación de cada endpoint seleccionado para ser convertido a tarea asíncrona, siguiendo los criterios: **latencia de ejecución**, **impacto en la experiencia del cliente**, **criticidad de la respuesta inmediata** y **frecuencia de uso**.

### ✅ `POST /api/incidents/analyze` — Análisis de CSV de incidencias

**Convertido.** Endpoint principal del hito de demo.

| Criterio | Evaluación |
|---|---|
| **Latencia** | Alta. El análisis de un CSV de incidencias requiere parsear cientos de registros, validar datos, ejecutar heurísticas de clasificación y generar un reporte estructurado. Para el fichero `incidents-healthcore.csv` (~100 filas) toma varios segundos; con volúmenes reales (miles de filas) puede exceder timeouts HTTP. |
| **Experiencia de cliente** | Crítica. Un usuario esperando frente al navegador que la respuesta tarde >5s provoca abandonos o reintentos. Con 202 Accepted el usuario sabe que la tarea está en cola y puede consultar el progreso. |
| **Respuesta inmediata necesaria** | No. El cliente no necesita el resultado en la misma llamada; puede pollingear GET /tasks/{task_id}. |
| **Frecuencia** | Media-alta en demo y uso real (varios análisis por minuto). |
| **Justificación** | Operación CPU-bound que no requiere respuesta sincrónica. El resultado (reporte + CSV exportado) se consulta posteriormente. Es el caso de uso perfecto para una cola de tareas. |

### ⬜ `GET /inventory/orders/export` — Exportación de histórico de órdenes

**Candidato.** No convertido aún.

| Criterio | Evaluación |
|---|---|
| **Latencia** | Alta. Itera sobre **todas** las órdenes (inbound y outbound) de la base de datos, genera un CSV en memoria y lo devuelve como adjunto. Con cientos de miles de registros puede tardar decenas de segundos y consumir mucha RAM. |
| **Experiencia de cliente** | Aceptable como sincrónico solo para rangos pequeños. Para exportaciones grandes el cliente recibe un timeout de conexión. |
| **Respuesta inmediata necesaria** | No. El cliente espera un fichero, no una respuesta interactiva. Es mejor encolar, devolver task_id y enviar el CSV por email o notificación cuando esté listo. |
| **Frecuencia** | Baja. Exportaciones ocasionales (usuarios administrativos). |
| **Justificación** | Operación pesada de lectura masiva + generación de fichero. El resultado (CSV) no necesita entregarse en la misma conexión HTTP. Al convertirlo a asíncrono se evitan timeouts de red y se reduce la carga de memoria en el proceso de la API. |

### ⬜ `POST /inventory/snapshots` — Captura de snapshot de stock

**Candidato.** No convertido aún.

| Criterio | Evaluación |
|---|---|
| **Latencia** | Alta. Itera sobre todos los suministros médicos y, para cada uno, calcula el stock en cada una de las 12 clínicas. Para un catálogo de ~100 productos son 1200 consultas a base de datos + emisión de señales de telemetría. |
| **Experiencia de cliente** | Pobre como sincrónico. El endpoint devuelve solo un contador, pero el cliente espera mientras se ejecutan todas las consultas. |
| **Respuesta inmediata necesaria** | No. El snapshot es una operación de mantenimiento que podría ejecutarse incluso con un cron. El contador de filas capturadas se puede obtener después. |
| **Frecuencia** | Baja. Se ejecuta bajo demanda o programada. |
| **Justificación** | Operación de barrido completo de la base de datos con emisión de telemetía. No hay razón para bloquear al cliente. Al ser asíncrono, además, se podría programar como tarea periódica (celery beat) sin modificar el endpoint. |

### ⬜ `POST /telemetry/events` — Ingesta de eventos de telemetría

**Candidato.** No convertido aún.

| Criterio | Evaluación |
|---|---|
| **Latencia** | Media. Cada evento se valida individualmente con Pydantic y se inserta en base de datos en bulk. Para lotes de 100 eventos la operación completa toma entre 200ms y 1s. |
| **Experiencia de cliente** | Aceptable como sincrónico porque el cliente (navegador, dispositivo IoT) no bloquea su flujo principal mientras espera la confirmación. Sin embargo, en picos de telemetría la API puede ralentizarse. |
| **Respuesta inmediata necesaria** | Parcial. El cliente espera un recibo (`received`, `stored`, `rejected`), pero no necesita que los eventos estén ya persistidos. Un recibo optimista (202 Accepted + task_id) es suficiente. |
| **Frecuencia** | Muy alta. Cientos o miles de lotes por minuto en producción. |
| **Justificación** | Aunque cada lote individual es rápido, la alta frecuencia de este endpoint lo convierte en un cuello de botella. Al encolar los eventos en Redis, la API responde inmediatamente y el worker los inserta en lotes más grandes (batch insert), mejorando el rendimiento general. |

### ⬜ `GET /telemetry/report` — Reporte de métricas operacionales

**Candidato.** No convertido aún.

| Criterio | Evaluación |
|---|---|
| **Latencia** | Alta. Ejecuta un pipeline completo de análisis agregando eventos por tipo, ventana temporal, usuario, etc. Incluye consultas agregadas a la base de datos que pueden tardar varios segundos. |
| **Experiencia de cliente** | Mala como sincrónico si el reporte es grande o el periodo es largo. El cliente (dashboard interno) se queda cargando. |
| **Respuesta inmediata necesaria** | No. Los reportes se consumen en dashboards que pueden mostrar "generando..." mientras la tarea se completa. |
| **Frecuencia** | Media. Consultas bajo demanda desde el panel administrativo o integraciones externas. |
| **Justificación** | El típico "report endpoint" que en producción siempre se convierte en async. Al ser una operación puramente de lectura agregada, no hay efecto secundario que requiera sincronía. Se puede cachear el resultado del worker en Redis y servirlo desde la API sin recalcular. |

### ⬜ `POST /inventory/products/import` — Importación masiva de productos

**Candidato.** Endpoint hipotético para carga batch.

| Criterio | Evaluación |
|---|---|
| **Latencia** | Muy alta. Insertar cientos de productos con validaciones por SKU, categorías y países requiere múltiples consultas a base de datos. |
| **Experiencia de cliente** | Mala. El cliente (panel administrativo) se bloquearía durante segundos o minutos. |
| **Respuesta inmediata necesaria** | No. El resultado es un reporte de cuántos se importaron y cuántos fallaron. |
| **Frecuencia** | Baja (cargas periódicas desde ERP). |
| **Justificación** | Endpoint clásico de importación batch que debe ser asíncrono para no bloquear la API. Se incluye como candidato futuro. |

### ⬜ `POST /inventory/orders/reconcile-batch` — Reconciliación masiva de stock

**Candidato.** Endpoint hipotético para reconciliación batch.

| Criterio | Evaluación |
|---|---|
| **Latencia** | Muy alta. Cada reconciliación calcula diferencia contra ledger y genera señales de alerta. Un batch de 50+ reconciliaciones puede saturar el proceso. |
| **Experiencia de cliente** | Mala. El cliente espera hasta que todas las reconciliaciones se completen. |
| **Respuesta inmediata necesaria** | No. El resultado agregado (cuántas discrepancias, cuántas alertas) no necesita entregarse en la misma llamada. |
| **Frecuencia** | Baja. Reconciliaciones periódicas de inventario físico. |
| **Justificación** | Similar a importación batch. Las operaciones de reconciliación son independientes entre sí y se benefician del paralelismo del worker con `concurrency=2+`. |

---

### Resumen de prioridad

| Prioridad | Endpoint | Justificación |
|---|---|---|
| ✅ **Hecho** | `POST /api/incidents/analyze` | CPU-bound, cliente no necesita respuesta sincrónica |
| 🥇 **Alta** | `GET /inventory/orders/export` | Lectura masiva + generación de fichero, evita timeouts |
| 🥇 **Alta** | `POST /inventory/snapshots` | Barrido completo BD, emisión masiva de señales |
| 🥇 **Alta** | `GET /telemetry/report` | Pipeline agregado pesado, típico report endpoint |
| 🥈 **Media** | `POST /telemetry/events` | Alta frecuencia, alivia cuello de botella en ingesta |
| 🥉 **Futura** | `POST /inventory/products/import` | Importación batch (endpoint hipotético) |
| 🥉 **Futura** | `POST /inventory/orders/reconcile-batch` | Reconciliación batch (endpoint hipotético) |

Los endpoints de **prioridad alta** comparten el patrón: operación de **lectura/escritura masiva** que **no requiere respuesta sincrónica** y cuya latencia **supera el umbral de tolerancia del cliente** (>2s). Los de **prioridad media** (telemetría) se benefician más por **frecuencia** que por latencia unitaria. Los **futuros** son hipotéticos pero siguen el mismo patrón de importación/reconciliación batch.

---

## Referencias

- [Celery Documentation](https://docs.celeryq.dev/)
- [Redis as a Celery Broker](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)
- [Flower — Celery Monitor](https://flower.readthedocs.io/)
- [FastAPI + Celery Pattern](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Dead Letter Queue Pattern](https://en.wikipedia.org/wiki/Dead_letter_queue)