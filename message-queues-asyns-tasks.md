# Cola de Tareas Asíncronas — Redis + Celery

## Contexto

Este documento describe la implementación del sistema de **cola de tareas asíncronas** en HealthCore, utilizando **Redis como broker** y **Celery como framework de tareas**. El objetivo principal es **desacoplar las operaciones pesadas de la API** para que los endpoints respondan inmediatamente (HTTP 202 Accepted) mientras un worker independiente procesa la tarea en segundo plano.

## Arquitectura

```
┌─────────────┐      ┌──────────┐      ┌─────────────┐      ┌──────────┐
│  Cliente    │      │  Redis   │      │   Worker    │      │  TinyDB  │
│  (HTTP)     │─────→│ (Broker) │─────→│ (Celery)    │──3──→│  (DLQ)   │
└──────┬──────┘      └──────────┘      └─────────────┘      └──────────┘
       │ 1. POST /incidents/analyze        │                      │
       │    → 202 {task_id, status}        │ 2. Procesa CSV       │
       │                                   │    (sync)            │
       │ 4. GET /tasks/{task_id}           │    si falla 3v       │
       │    → {status: success, result}    │    → DLQ             │
       ◄───────────────────────────────────┘                      │
       │                                                          │
       │ 5. GET /tasks/{task_id}                                  │
       │    → {status: failure, dlq: {...}} ◄─────────────────────┘
```

### Roles

| Componente | Rol | Descripción |
|---|---|---|
| **FastAPI** | **Productor** | Recibe la solicitud HTTP, crea un mensaje ligero y lo deposita en la cola Redis. Devuelve 202 Accepted inmediatamente con `task_id` y `status: PENDING`. Incluye header `Location: /tasks/{task_id}`. |
| **Redis** | **Broker** | Almacenamiento persistente de mensajes en memoria. Si el worker se cae, los mensajes no se pierden. Política `noeviction`. También actúa como result backend para almacenar resultados de tareas completadas. |
| **Celery Worker** | **Consumidor** | Proceso independiente que escucha la cola, toma mensajes de uno en uno y los procesa. Corre en un contenedor Docker separado con `concurrency=4`. |
| **Flower** | **Monitor** | Interfaz web para inspeccionar colas, workers y tareas en tiempo real. Accesible en `http://localhost:5555`. |
| **TinyDB (DLQ)** | **Dead Letter Queue** | Almacena tareas que fallaron tras 3 intentos con `task_id`, `attempt`, `error`, `exc_type` y `timestamp`. El endpoint GET /tasks/{task_id} consulta la DLQ cuando una tarea está en estado FAILURE. |

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
  container_name: healthcore-redis
  hostname: redis
  command: ["redis-server", "--appendonly", "yes", "--maxmemory-policy", "noeviction"]
  ports: ["6379:6379"]
  volumes: ["redis-data:/data"]
  networks: [healthcore-net]
  restart: unless-stopped

flower:
  image: mher/flower:2.0
  container_name: healthcore-flower
  hostname: flower
  ports: ["5555:5555"]
  environment:
    CELERY_BROKER_URL: "${REDIS_URL:-redis://redis:6379/0}"
    CELERY_RESULT_BACKEND: "${REDIS_URL:-redis://redis:6379/0}"
    FLOWER_UNAUTHENTICATED_API: "1"
  depends_on: [redis]
  networks: [healthcore-net]
  restart: unless-stopped

celery-worker:
  build:
    context: .
    dockerfile: services/Dockerfile
  container_name: healthcore-celery-worker
  hostname: celery-worker
  env_file: [.env]
  environment:
    REDIS_URL: "${REDIS_URL:-redis://redis:6379/0}"
    PYTHONPATH: "/workspace"
  volumes:
    - ./services:/workspace/services
    - ./data:/workspace/data
  depends_on: [redis]
  networks: [healthcore-net]
  restart: unless-stopped
  working_dir: /workspace
  command: >
    celery -A services.celery_app worker
    --loglevel=info --concurrency=4
    --max-tasks-per-child=100
    --without-gossip --without-mingle --without-heartbeat -E
```

### 2. Módulo Celery (`services/celery_app.py`)

- **Instancia**: `Celery("healthcore", broker=REDIS_URL, backend=REDIS_URL)` — Redis es tanto broker como result backend.
- **Colas**: `healthcore.default` (por defecto) y `healthcore.dlq` (cola DLQ explícita en Celery).
- **Tarea**: `analyze_incidents_csv` — recibe `csv_content` (string) y `filename`, ejecuta `analyze_csv_text`, devuelve el reporte con `source_file`, `report`, `csv_export`, `analyzed_at` y `duration_seconds`.
- **Tarea base**: `HealthCoreTask(Task)` — clase abstracta con `on_failure` que persiste en TinyDB cuando se agotan los reintentos.
- **Configuración de reintentos**:
  - `autoretry_for=(Exception,)` — reintenta ante cualquier excepción.
  - `max_retries=3`, `default_retry_delay=10`.
  - `retry_backoff=True` → backoff exponencial: 10s, 20s, 40s.
  - `retry_backoff_max=300` (5 min máximo entre reintentos).
  - `retry_jitter=True` (ruido aleatorio para evitar tormentas).
- **Trazabilidad**: cada ejecución registra `task_id`, `filename`, `duration` (con `time.monotonic()`), `total`, `valid` e `invalid` mediante `get_task_logger`.
- **Señales**: `task_success`, `task_failure` (con traceback), `task_retry` (con intento actual), `task_revoked` para logging completo del ciclo de vida.
- **DLQ**: cuando `on_failure` se dispara tras agotar reintentos, se persiste en TinyDB (`data/process/task_dlq.json`) con `task_id`, `task_name`, `attempt`, `error`, `exc_type`, `args`, `kwargs` y `timestamp`.
- **Red**: todos los servicios se comunican por nombre Docker dentro de `healthcore-net`. La variable de entorno `REDIS_URL` se resuelve como `redis://redis:6379/0` dentro del contenedor.

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
        content={
            "task_id": task.id,
            "status": "PENDING",
            "detail": (
                "La tarea ha sido encolada. "
                "Consulta GET /tasks/{task_id} para obtener el resultado."
            )
        },
        headers={"Location": f"/tasks/{task.id}"},
    )
```

### 4. Endpoint de consulta (`GET /tasks/{task_id}`)

```python
@router.get("/{task_id}")
def get_task_status(task_id: str):
    """Consulta el estado actual de una tarea asíncrona.

    Args:
        task_id: ID de la tarea devuelto por el endpoint que la encoló.

    Returns:
        Dict con:
        - status: pending | started | success | failure
        - result: resultado (si SUCCESS)
        - error: mensaje de error (si FAILURE)
        - dlq: entrada en Dead Letter Queue (si FAILURE)
        - task_id: el identificador de la tarea
    """
    async_result = celery_app.AsyncResult(task_id)

    # Normalizar a minúsculas como espera el cliente
    state = async_result.state.lower()

    response = {
        "task_id": task_id,
        "status": state,
    }

    if state == "pending":
        response["info"] = "La tarea está en la cola esperando ser procesada."

    elif state == "started":
        response["info"] = "La tarea está siendo procesada."

    elif state == "success":
        response["result"] = async_result.result

    elif state == "failure":
        # Extraer información del error de forma segura
        result = async_result.result
        if isinstance(result, Exception):
            response["error"] = str(result)
        elif isinstance(result, dict):
            response["error"] = result.get("error", str(result))
        else:
            response["error"] = str(result) if result else "Unknown error"

        # Si la tarea está en DLQ, indicarlo
        from pathlib import Path
        from tinydb import TinyDB
        from services.celery_app import DLQ_DB_PATH

        db_path = Path(DLQ_DB_PATH)
        if db_path.exists():
            db = TinyDB(str(db_path))
            dlq_entries = db.table("task_dlq").search(
                lambda doc: doc.get("task_id") == task_id
            )
            if dlq_entries:
                response["dlq"] = dlq_entries[-1]  # última entrada
            db.close()

    return response
```

Estados posibles:

| status | Significado |
|---|---|
| `pending` | Tarea en cola, ningún worker la ha tomado aún |
| `started` | Un worker está procesándola |
| `success` | Tarea completada, `result` disponible |
| `failure` | Tarea falló tras agotar reintentos; en DLQ (si `error` + `dlq` presentes) |

### 5. Dead Letter Queue (DLQ)

Cuando una tarea supera `max_retries=3`, el método `on_failure` de `HealthCoreTask` registra en la DLQ:

```json
{
  "task_id": "uuid-del-task",
  "task_name": "analyze_incidents_csv",
  "attempt": 3,
  "error": "ValueError: CSV inválido: faltan columnas requeridas: incident_id",
  "exc_type": "ValueError",
  "args": "[\"csv_content...\"]",
  "kwargs": "{\"filename\": \"test.csv\"}",
  "timestamp": "2026-10-24T12:00:00+00:00"
}
```

La DLQ se persiste en `data/process/task_dlq.json` usando TinyDB. Cuando el endpoint `GET /tasks/{task_id}` detecta que una tarea está en estado `failure`, consulta automáticamente la DLQ y añade un campo `dlq` con la entrada correspondiente:

```json
GET /tasks/ddc8085d-24f9-4c63-85e2-24d9fafed904
→ {
    "task_id": "ddc8085d-24f9-4c63-85e2-24d9fafed904",
    "status": "failure",
    "error": "CSV inválido: faltan columnas...",
    "dlq": {
        "task_id": "ddc8085d-...",
        "task_name": "analyze_incidents_csv",
        "attempt": 3,
        "error": "CSV inválido: ...",
        "exc_type": "ValueError",
        "timestamp": "2026-10-24T22:13:XX+00:00"
    }
}
```

### 5.1. Cola healthcore.dlq en Celery

Además de la DLQ persistente en TinyDB, se define una **cola DLQ explícita en Celery** (`healthcore.dlq`). Las tareas que fallan irreversiblemente pueden redirigirse a esta cola para inspección manual sin perder el mensaje original:

```python
celery_app.conf.update(
    task_queues={
        "healthcore.default": {
            "exchange": "healthcore",
            "routing_key": "healthcore.default",
        },
        "healthcore.dlq": {
            "exchange": "healthcore.dlq",
            "routing_key": "healthcore.dlq",
        },
    },
)
```

### 6. Señales Celery (logging con trazabilidad)

El módulo `celery_app.py` registra **señales** que proporcionan trazabilidad completa del ciclo de vida de cada tarea:

| Señal | Propósito | Información registrada |
|---|---|---|
| `task_success` | Tarea completada correctamente | Nombre de la tarea |
| `task_failure` | Tarea fallida | `task_id`, mensaje de error, traceback (primeros 500 chars) |
| `task_retry` | Reintento automático | `task_id`, número de intento, razón del fallo, traceback |
| `task_revoked` | Tarea revocada | `task_id`, fecha de expiración |
| `on_after_configure` | Worker iniciado | Broker URL, backend URL, colas configuradas |

Además, la propia tarea `analyze_incidents_csv` utiliza `get_task_logger` para registrar con `time.monotonic()`:
- **STARTED**: `task_id`, `filename`, `csv_size`
- **SUCCESS**: `task_id`, `filename`, `duration` (segundos), `total`, `valid`, `invalid`

### 7. Configuración completa de Celery

| Parámetro | Valor | Propósito |
|---|---|---|
| `task_serializer` | `json` | Serialización ligera de mensajes |
| `result_serializer` | `json` | Resultados en JSON |
| `task_acks_late` | `True` | Worker confirma tarea solo al completar |
| `task_reject_on_worker_lost` | `True` | Tarea se reencola si el worker se cae |
| `task_track_started` | `True` | Permite ver estado `started` |
| `task_soft_time_limit` | `300` (5 min) | Timeout suave por tarea |
| `task_time_limit` | `330` (5:30) | Timeout duro por tarea |
| `result_expires` | `604800` (7 días) | Resultados expiran a los 7 días |
| `task_default_queue` | `healthcore.default` | Cola por defecto |
| `max_retries` | `3` | Reintentos antes de DLQ |
| `retry_backoff` | `True` | Backoff exponencial: 10s, 20s, 40s |
| `retry_backoff_max` | `300` (5 min) | Máximo entre reintentos |
| `retry_jitter` | `True` | Añade ruido aleatorio para evitar tormentas de reintentos |

## Flujo completo

```
CLIENTE                     API (FastAPI)               REDIS               WORKER
   │                              │                        │                   │
   │  POST /api/incidents/analyze │                        │                   │
   │  (CSV file)                  │                        │                   │
   │─────────────────────────────→│                        │                   │
   │                              │  task.delay(content)   │                   │
   │                              │───────────────────────→│                   │
   │                              │     (message en cola)  │                   │
   │  202 Accepted                │                        │                   │
   │  {task_id, status:PENDING}   │                        │                   │
   │←─────────────────────────────│                        │                   │
   │                              │                        │  worker toma msg  │
   │                              │                        │←──────────────────│
   │                              │                        │                   │
   │  GET /tasks/{task_id}        │                        │  procesa CSV...   │
   │─────────────────────────────→│                        │                   │
   │  {status: started}           │                        │                   │
   │←─────────────────────────────│                        │                   │
   │                              │                        │  resultado listo  │
   │                              │                        │──────────────────→│
   │                              │                        │  (Redis backend)  │
   │  GET /tasks/{task_id}        │                        │                   │
   │─────────────────────────────→│                        │                   │
   │  {status: success, result}   │                        │                   │
   │←─────────────────────────────│                        │                   │
   │                              │                        │  si falla 3 veces │
   │                              │                        │────→ DLQ (TinyDB) │
```

### Desarrollo local (máquina host)

```bash
# 1. Iniciar Redis
docker compose up redis -d

# 2. Iniciar Flower (monitoreo) — dentro del contenedor Docker
docker compose up flower -d
# Abrir http://localhost:5555

# Alternativa: Flower local (si el contenedor no conecta con Redis)
cd services/api
PYTHONPATH=".." celery -A services.celery_app flower --loglevel=info

# 3. Iniciar worker (con flag -E para emitir eventos)
cd services/api
PYTHONPATH=".." celery -A services.celery_app worker \
  --loglevel=info \
  --concurrency=2 \
  --max-tasks-per-child=100 \
  --without-gossip \
  --without-mingle \
  --without-heartbeat \
  -E

# 4. Iniciar API
cd services/api && uvicorn main:app --reload --port 8000
```

### Desarrollo con Docker Compose (todo incluido)

El `docker-compose.yml` incluye el servicio `celery-worker` con recarga automática:

```yaml
celery-worker:
  build:
    context: .
    dockerfile: services/Dockerfile
  container_name: healthcore-celery-worker
  hostname: celery-worker
  env_file:
    - .env
  environment:
    REDIS_URL: "${REDIS_URL:-redis://redis:6379/0}"
    PYTHONPATH: "/workspace"
  volumes:
    - ./services:/workspace/services
    - ./data:/workspace/data
  depends_on:
    redis:
      condition: service_started
  networks:
    - healthcore-net
  restart: unless-stopped
  working_dir: /workspace
  command: >
    celery -A services.celery_app worker
    --loglevel=info
    --concurrency=4
    --max-tasks-per-child=100
    --without-gossip
    --without-mingle
    --without-heartbeat
    -E
```

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
# {
#   "task_id": "abc-123",
#   "status": "PENDING",
#   "detail": "La tarea ha sido encolada. Consulta GET /tasks/{task_id} para obtener el resultado."
# }
# Header: Location: /tasks/abc-123

# 2. Consultar estado (tarea completada)
curl http://localhost:8000/tasks/abc-123

# Respuesta:
# {
#   "task_id": "abc-123",
#   "status": "success",
#   "result": { "source_file": "...", "report": {...} }
# }

# 3. Consultar estado (tarea fallida con DLQ)
curl http://localhost:8000/tasks/task-fallida-999

# Respuesta:
# {
#   "task_id": "task-fallida-999",
#   "status": "failure",
#   "error": "CSV inválido: faltan columnas...",
#   "dlq": {
#     "task_id": "task-fallida-999",
#     "attempt": 3,
#     "error": "CSV inválido: ...",
#     "exc_type": "ValueError",
#     "timestamp": "2026-10-24T22:13:00+00:00"
#   }
# }
```

## Monitoreo con Flower

Flower está disponible en `http://localhost:5555` y proporciona:

- **Dashboard**: workers activos, tareas por segundo, colas.
- **Tasks**: historial completo de tareas con estado, duración y resultado.
- **Broker**: información sobre Redis (mensajes en cola, conexiones).
- **Workers**: lista de workers, suscripción a colas, tareas activas.

### Requisitos para que Flower muestre tareas

Si abres Flower y ves el panel vacío (sin tareas), verifica estos tres puntos:

1. **Worker con flag `-E` (--events)**: el worker debe arrancar con `-E` para emitir eventos. Sin este flag Flower no recibe notificaciones de tareas.
   ```bash
   celery -A services.celery_app worker --loglevel=info -E
   ```
   En los logs del worker debe aparecer: `task events: ON`.

2. **Variable `CELERY_RESULT_BACKEND`**: Flower necesita el result backend para mostrar tareas completadas/fallidas. El servicio `flower` en `docker-compose.yml` debe tener:
   ```yaml
   environment:
     CELERY_BROKER_URL: "${REDIS_URL:-redis://redis:6379/0}"
     CELERY_RESULT_BACKEND: "${REDIS_URL:-redis://redis:6379/0}"
   ```

3. **Flower 2.0 requiere `FLOWER_UNAUTHENTICATED_API=1`**: sin esta variable, Flower 2.0 no expone su API REST (endpoints `/api/tasks`, `/api/workers`, etc.), por lo que las tareas no se muestran en el panel.
   ```yaml
   environment:
     FLOWER_UNAUTHENTICATED_API: "1"
   ```

### Verificar que las tareas aparecen

Una vez que Flower está corriendo con todo configurado, envía una tarea de prueba:

```bash
# Tarea con datos válidos (debería aparecer como SUCCESS)
cd /workspaces/elige-tu-empresa-wendy-sanchez/services/api
PYTHONPATH=".." python -c "
from services.celery_app import analyze_incidents_csv
result = analyze_incidents_csv.delay(
    csv_content='incident_id,date,clinic_id,country,category,description,status,patient_id,satisfaction_score\n1,2025-01-01,CLI-001,Colombia,administrativo,test,abierto,PAC-001,4'
)
print('Tarea enviada. ID:', result.id)
"
```

Luego revisa http://localhost:5555 — la tarea debe aparecer en la pestaña **Tasks**.

Para ver tareas desde la API REST de Flower:

```bash
curl -s http://localhost:5555/api/tasks?limit=10 | python3 -c "
import json, sys
data = json.load(sys.stdin)
tasks = data if isinstance(data, dict) else {}
states = {}
for tid, info in tasks.items():
    s = info.get('state', 'unknown')
    states.setdefault(s, 0)
    states[s] += 1
print(f'Total tareas: {len(tasks)}')
print(f'Por estado: {states}')
"
```

### Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| Flower panel vacío (0 tareas) | Worker sin flag `-E` | Reiniciar worker con `-E`. Verificar que los logs digan `task events: ON`. |
| Flower no muestra tareas SUCCESS/FAILURE | Falta `CELERY_RESULT_BACKEND` | Añadir la variable al servicio Flower y reiniciar. |
| Flower API REST devuelve 404/403 | Falta `FLOWER_UNAUTHENTICATED_API` | Añadir `FLOWER_UNAUTHENTICATED_API: "1"` y reiniciar Flower. |
| Flower loguea "timeout connecting to server" | Flower dentro del contenedor no alcanza Redis | Verificar que la red Docker funcione. Como alternativa, ejecutar Flower localmente: `celery -A services.celery_app flower -l info` desde `services/api/`. |
| Worker no procesa tareas encoladas | Worker no conectado a la misma cola | Verificar `task_default_queue` y que el worker escuche en la cola correcta. |

## Tareas futuras / mejoras

- [ ] Migrar DLQ de TinyDB a PostgreSQL cuando el volumen lo requiera.
- [ ] Implementar colas prioritarias (salud crítica vs. administrativo).
- [ ] Integrar alertas (Slack/email) cuando una tarea caiga en DLQ.
- [ ] Implementar dashboard interno de estado de tareas (vs. depender de Flower en producción).
- [ ] Añadir tests de integración con Redis en pytest usando `factories` o `mock`.

> ✅ **Implementado**: `task_soft_time_limit=300` y `task_time_limit=330` ya están configurados en la tarea `analyze_incidents_csv`.

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