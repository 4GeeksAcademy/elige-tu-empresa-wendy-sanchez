# System Pattern

## Patrón general del repositorio
Monorepo de aprendizaje orientado a hitos, con separación por dominios:
- uis/: interfaces (HTML estático y apps Next.js: website, backoffice, talent-pipeline-tracker).
- src/: utilidades TypeScript de lógica de negocio (modelo, colecciones, búsqueda, transformaciones, validaciones).
- services/api/: backend FastAPI (análisis de incidencias + directorio de proveedores).
- packages/, data/, skills/, workflows/: estructura preparada para escalado en hitos posteriores.

## Patrones de código observados

### 1) Separation of concerns
- Tipos y entidades en módulos dedicados.
- Utilidades puras separadas por responsabilidad (filtrado, búsqueda, agregaciones, validación).
- Componentes UI desacoplados de acceso a datos mediante services/api.ts.

### 2) Functional core
- Funciones de negocio mayormente puras en src/utils.
- Entradas y salidas tipadas con TypeScript estricto.
- Manejo explícito de casos borde: arrays vacíos, datos no encontrados, fechas inválidas.

### 3) Cliente API centralizado
- Wrapper request genérico en tracker para GET/POST/PUT/PATCH/DELETE.
- Normalización de errores HTTP a mensajes consumibles por UI.
- Construcción de query params desde estado de filtros.

### 4) Estado local por vista/componente
- Estado de red y formularios acotado en componentes cliente de Next.js.
- No prop drilling profundo; la lógica se concentra por pantalla.
- Feedback de operaciones asíncronas en el mismo contexto de uso.

### 5) UX y validación en tiempo real
- Formulario de paciente con validaciones realtime + submit guard.
- Uso de mensajes específicos por campo según reglas de negocio.
- Campos condicionales (insurance, patient_id) controlados por selecciones previas.

## Patrones de navegación
- Listado -> detalle con preservación de contexto de filtros vía query string.
- Operaciones del detalle (estado/etapa/notas/edición) sin salir de la página.

## Patrones del backend (services/api)

### 6) Capas por responsabilidad
- models.py: modelos Pydantic y enums de dominio.
- database.py: inicialización única de TinyDB y resolución de la ruta del fichero.
- routes/: un router por dominio, montado en main.py.
- seed.py: datos iniciales del CONTEXT, ejecutable como script.

### 7) Modelos de entrada y salida separados
- SupplierCreate / SupplierReplace para lo que envía el cliente.
- Supplier para la respuesta, con los campos que genera el sistema (id, updated_at, archived_at).
- Los campos generados por el sistema se ignoran si el cliente los envía.

### 8) Trazabilidad temporal
- updated_at sella exclusivamente los cambios de tarifa (auditorías de coste).
- archived_at sella la baja del proveedor. No se mezclan semánticas en un mismo campo.

### 9) Seeder idempotente
- Comprueba existencia por nombre antes de insertar y reporta insertados/omitidos/total por consola.

## Patrones de Docker

### 10) Comunicación por nombre Docker
- Los servicios se comunican usando nombres de servicio definidos en docker-compose.yml (`backend`, `incidents-backend`) en lugar de `localhost`.
- Las variables de entorno (`.env`) contienen URLs con nombres Docker: `SUPPLIERS_API_URL=http://backend:8000`, `INCIDENTS_API_URL=http://backend:8000`.
- Los route handlers y rewrites de Next.js (`next.config.ts`) usan estas variables de entorno.

### 11) Multi-etapa con Dev/Prod separados
- `uis/Dockerfile`: etapa `install` (dependencias) → `builder` (compilación) → `development` (dev con hot-reload via Turbopack). Sin `--only=production` para incluir devDependencies necesarias en runtime.
- `services/Dockerfile`: usa `uv` para instalar dependencias, entrypoint bash que selecciona entre api e incidents-api según variable `SERVICE_NAME`.

### 12) Bind mounts + volumes anónimos
- **Bind mounts** para hot-reload: `./uis:/workspace/uis` refleja cambios en vivo en website y backoffice.
- **Volumen especial**: `./src:/workspace/uis/backoffice/src` monta las utilidades compartidas dentro del proyecto backoffice, permitiendo que Turbopack resuelva imports como `../src/...`.
- **Volúmenes anónimos** para `node_modules` en cada proyecto Next.js, evitando que el bind mount sobreescriba `node_modules` del contenedor.

### 13) Graceful skip de dependencias externas
- `init_supabase_schema()` verifica si `DATABASE_URL` está configurada antes de conectar. Si está vacía, omite la inicialización gracefulmente con un log informativo. Esto permite desarrollo local sin Supabase sin necesidad de variables dummy.

### 14) Imágenes no optimizadas en contenedor
- `next.config.ts` del website usa `images: { unoptimized: true }` porque el contenedor no resuelve DNS externo, evitando errores `EAI_AGAIN` al intentar optimizar imágenes de terceros (Unsplash). La carga directa desde el navegador funciona sin problemas.

## Patrones de infraestructura y desarrollo

### 15) Proxy de API en el backoffice
- app/api/** reenvía al backend y traduce los errores 422 de FastAPI a mensajes legibles por campo.
- El navegador nunca habla directamente con FastAPI: evita CORS y oculta la URL interna del backend.

### 16) Docker multi-servicio para desarrollo
- Cada servicio tiene su propio `Dockerfile` y `.dockerignore` en su directorio.
- `docker-compose.yml` en raíz orquesta todos los servicios con red bridge explícita.
- Los contenedores se comunican por nombre de servicio Docker, no por localhost.
- Bind mounts del código fuente permiten hot-reload sin reconstruir imágenes.
- Volúmenes anónimos para `node_modules` evitan que el bind mount del host sobrescriba las dependencias instaladas en el contenedor.

### 17) Entrypoint dinámico
- `services/entrypoint.sh` selecciona el comando uvicorn según variable `SERVICE_NAME` (api→:8000, incidents-api→:8010).
- `uis/start.sh` lanza ambos Next.js en paralelo con manejo de señales SIGTERM/SIGINT.

### 18) Optimización de contexto Docker
- `.dockerignore` raíz excluye node_modules, .env, __pycache__, .next, .venv, .git del contexto de build (reduce ~987 kB → ~10.5 kB).
- Cada subdirectorio (uis/, services/) tiene su propio `.dockerignore` para filtros adicionales específicos.

### 19) Configuración dual de TypeScript para tests
- `tsconfig.json` principal: configuración estricta de producción, excluye `__tests__`.
- `tsconfig.test.json`: extiende el principal, añade `types: ["jest", "node"]`, incluye `__tests__`.
- `jest.config.ts` apunta al `tsconfig.test.json` para que Jest tenga los tipos correctos.
- Esto evita contaminar el ámbito de producción con tipos de test (@types/jest).

### 20) Schemas de serialización: entrada y salida separados (backend)
- **Modelos Pydantic de entrada** (`*Create`, `*Update`, `*Replace`): definen exactamente lo que el cliente debe enviar, sin campos generados por el sistema.
- **Modelos de salida para listado** (`*ListItem`, `*Public`): más ligeros que los de detalle, excluyen campos pesados o claves foráneas internas.
- **Modelos de salida para detalle/escritura** (`Supplier`, `IncidentResponse`): incluyen todos los campos que el consumidor necesita tras una operación.
- **Modelos de mensaje genérico** (`MessageResponse`): para flujos donde solo se devuelve un texto (auth no autenticado).
- **Modelos de respuesta compuesta** (`AnalysisResponse` con `AnalysisSummary` y `AnalysisPercentages` anidados): estructuras complejas completamente tipadas.
- **RootResponse**: schema explícito para endpoints de descubrimiento, eliminando `response_model=dict`.

### 21) Patrón de telemetría: única función pública `track()`
- **`lib/telemetry.ts`** exporta `track()` como la única API pública para emitir eventos de telemetría desde el frontend.
- Componentes, hooks y servicios auxiliares llaman a `track(eventType, properties)` — ningún otro código hace fetch directo a `/api/telemetry/events`.
- **`TelemetryService.control.ts`** se refactorizó de un fetch pipeline independiente a `recordTelemetryControl()` que valida propiedades y llama a `track()`. Esto eliminó la violación arquitectónica de tener dos pipelines de fetch en el frontend.
- **`lib/telemetryEndpoint.ts`** resuelve la URL del endpoint, transformando loopback en ruta proxy de Next.js para el navegador.
- **`app/api/telemetry/events/route.ts`** es el único route handler que hace fetch al backend, usando `TelemetryService.server.ts`.

### 22) Patrón de telemetría: stacked decorators en backend
- **`routes/telemetry.py`** usa `@router.post` apilados en el mismo handler para registrar `/telemetry/events` y `/telemetry/control`:
  ```python
  @router.post("/telemetry/events")
  @router.post("/telemetry/control")
  async def receive_telemetry(batch: TelemetryBatch):
      ...
      return TelemetryReceipt(received=N)
  ```
- Ambos endpoints retornan el mismo schema `TelemetryReceipt(received=N)`.
- La validación Pydantic aplica las 41 reglas de contrato del catálogo antes de aceptar un lote.

### 23) Patrón de telemetría: gestión de procesos backend
- En Codespaces, pueden existir múltiples procesos FastAPI en distintos puertos. Es necesario verificar el proceso correcto con `ps aux | grep uvicorn`, matar los obsoletos, y reiniciar en el puerto correcto con `--reload`.
- OpenAPI `/docs` confirma qué rutas están registradas en el proceso activo.

### 24) Patrón de refactorización frontend: capa de datos compartida
- **Tipos de dominio en `types/`**: cada módulo de negocio (incident, supplier) tiene su archivo de tipos compartido.
- **Constantes y mapeos en `lib/`**: labels, colores, opciones de select, API_BASE — todo centralizado para evitar duplicación entre componentes.
- **Clientes HTTP en `lib/`**: un único `httpClient.ts` para todo el backoffice, con `request<T>()`, `extractErrorMessage()`, `ApiError`. Los módulos específicos importan desde ahí.

### 25) Patrón de componentes UI reutilizables
- **`LoadingSpinner`**: spinner animado con props `message`, `fullPage`, `size` (sm/md/lg).
- **`ErrorMessage`**: bloque de error con props `title`, `message`, `onRetry`, `variant` (error/warning/info).
- **`EmptyState`**: estado de lista vacía con props `message`, `description`, `icon`, `action`.
- Todos en `components/ui/` con barrel export desde `index.ts`.

### 30) Patrón de telemetría: análisis pipeline con pandas (backend standalone)
- **`services/telemetry/analysis.py`** define 5 funciones independientes que siguen el mismo patrón: SQL (`pandas.read_sql`) → DataFrame → conversión de tipos → groupby/agregación → retorno como `list[dict]`.
- **`run_all()`** orquesta las 5 funciones y devuelve un diccionario con todas las métricas, servido por `GET /telemetry/report`.
- Cada función gestiona su propia consulta SQL y transformación pandas — no hay estado compartido entre funciones.
- **`auth_failure_rate_by_day()`**: filtra `event_type IN ('auth_login_failed', 'auth_login_succeeded')`, groupby fecha, pivot para failed/succeeded, `failure_rate_pct = (failed / total * 100).where(total > 0, 0).round(2)`.

### 31) Patrón de telemetría: servidor standalone (evita SQLModel)
- **`services/telemetry/server_standalone.py`**: FastAPI que NO importa `services/api/models.py` (evita `TypeError: issubclass()` de SQLModel 0.0.42 en Python 3.14).
- Importa directamente `analysis.py` y `auth_standalone.py` desde el mismo directorio.
- Endpoints: `GET /telemetry/report` (caché 60s en memoria), `POST /auth/login`, `GET /auth/me`, `GET /health`.
- **Caché**: diccionario en memoria con `time.monotonic()` + TTL 60s para el reporte. Sin dependencias externas.

### 32) Patrón de telemetría: módulo auth standalone (bcrypt + JWT + TinyDB)
- **`services/telemetry/auth_standalone.py`**: autenticación autónoma que no depende de `services/api/` ni de `models.py`.
- Funciones: `verify_password()`, `hash_password()`, `get_user_by_email()`, `get_user_by_id()`, `get_profile_by_user_id()`, `create_access_token()`, `decode_access_token()`.
- Lee `JWT_SECRET_KEY` de entorno (cargado desde `services/api/.env`).
- Usa passlib con bcrypt para hash de contraseñas y python-jose para JWT (HS256, 30 min).
- Consulta TinyDB directamente (`data/process/suppliers_db.json`) en tablas `users` y `profiles`.

### 33) Patrón de telemetría: dashboard con proxy rewrite
- **`uis/backoffice/app/telemetry/page.tsx`**: página protegida por AuthGuard con 5 paneles visuales.
- Cada panel llama a `fetch('/api/telemetry/report')` con `date_from`/`date_to` como query params opcionales.
- El proxy en `next.config.ts` (`/api/telemetry/report` → `http://localhost:8000/telemetry/report`) resuelve la llamada en servidor.
- No hay route handler intermedio — al usar rewrite directo, se eliminó el route handler bugado anterior que usaba `base.protocol` (propiedad JS URL inválida).

## Patrones del proceso de segundo plano (script nocturno de telemetría)

### 34) Patrón: proceso 100% independiente de la API
- El job nocturno es un **proceso externo** (cron del SO o contenedor scheduler dedicado) que **no importa** FastAPI/uvicorn/starlette/APScheduler.
- Disparo por crontab `0 2 * * *` UTC o contenedor Docker dedicado; NUNCA vía lifespan/APScheduler/@repeat_every en la API (requisito explícito del proceso de segundo plano).
- El CLI `scripts/nightly_export.py` es el único entrypoint: imprime JSON + exit code (0 = ok, 1 = falló) para vigilancia desde cron.

### 35) Patrón: máquina de estados en BD como distributed lock
- La tabla `job_runs` (job_name, target_date, status) es el control de estado e idempotencia.
- **El lock ES el estado `processing`**: la toma es un UPDATE atómico `pending → processing` con `WHERE status='pending'` (rowcount==1 ⇒ ganó). No hay tabla/flag de bloqueo separado.
- 2.ª instancia: ve `processing` ⇒ aborta en silencio (exit 0, outcome `aborted`); ve `completed` ⇒ noop (outcome `noop_export`) — idempotencia por `(job_name, target_date)`.
- Fallo ⇒ `failed` con `error_message` (nunca queda `processing` zombi). Reintento vía `reset_failed_to_pending` (transición atómica solo desde `failed`, nunca desde `processing`).

### 36) Patrón: observabilidad con logger estable + helper log_result
- Logger dedicado `healthcore.nightly` + helper `log_result()` centralizado en `services/job_runner.py`.
- Formato normalizado por línea: `event=... job=nightly_export status=... outcome=... target_date=... ts=...`.
- INFO para inicio/fin/omisión por duplicado/abort; ERROR con `exc_info=True` para fallos. Sin `logger.exception` crudo (una sola fuente de verdad).
- **Auth**: login via `POST /api/auth/login` → rewrite → `localhost:8000/auth/login` → JWT. `GET /api/auth/me` → rewrite → `localhost:8000/auth/me`.

## Patrones de cola de tareas asíncronas (Redis + Celery)

### 37) Patrón: Cola de Tareas Asíncronas — Productor-Consumidor (Redis + Celery)
- **FastAPI actúa como Productor**: recibe la solicitud HTTP, crea un mensaje ligero (solo metadatos y referencias, nunca blobs completos), y lo deposita en la cola Redis mediante `task.delay()`. Responde **202 Accepted** inmediatamente con `task_id` y `status: PENDING`. Incluye header `Location: /tasks/{task_id}`.
- **Redis actúa como Broker y Result Backend**: almacena mensajes en memoria con persistencia AOF. Política `noeviction` para garantizar que nunca se descartan mensajes por falta de memoria. Configurado con `--appendonly yes --maxmemory-policy noeviction`.
- **Celery Worker actúa como Consumidor**: proceso independiente (contenedor Docker separado) que escucha la cola, toma mensajes de uno en uno y los procesa. Corre con `concurrency=4` y flag `-E` para emitir eventos a Flower.
- **Flower actúa como Monitor**: interfaz web en `http://localhost:5555` para inspeccionar colas, workers y tareas en tiempo real. Requiere que el worker arranque con `-E` (events).
- **Dead Letter Queue (DLQ)**: las tareas que fallan tras `max_retries=3` se persisten en TinyDB (`data/process/task_dlq.json`) con `task_id`, `task_name`, `attempt`, `error`, `exc_type`, `args`, `kwargs`, `timestamp`. El endpoint `GET /tasks/{task_id}` consulta automáticamente la DLQ cuando el estado es `failure`.
- **Reglas**: mensajes ligeros (solo metadatos), productor y consumidor son procesos distintos, broker persistente (Redis AOF + noeviction).

### 38) Patrón: Task Base con DLQ automática (HealthCoreTask)
- **`HealthCoreTask(Task)`**: clase base abstracta de Celery que extiende `Task` y añade DLQ automática.
- **`abstract = True`**: no se puede instanciar directamente, solo como base de tareas concretas.
- **`max_retries = 3`** y **`default_retry_delay = 10`**: valores por defecto para reintentos.
- **`on_failure()`**: sobrescrito para persistir el fallo en TinyDB (`task_id`, `attempt=max_retries`, `error`, `exc_type`, `task_name`, `args`, `kwargs`, `timestamp`) antes de delegar en `super().on_failure()`. Esto garantiza que toda tarea que herede de `HealthCoreTask` tenga registro en DLQ automáticamente.
- **Uso**: decorar la tarea con `@celery_app.task(bind=True, base=HealthCoreTask, ...)`.

### 39) Patrón: Reintentos con backoff exponencial y jitter
- **`autoretry_for=(Exception,)`**: reintenta automáticamente ante cualquier excepción.
- **`max_retries=3`**: máximo 3 intentos totales (1 original + 2 reintentos).
- **`retry_backoff=True`**: backoff exponencial — 10s, 20s, 40s.
- **`retry_backoff_max=300`**: límite superior de 5 minutos entre reintentos.
- **`retry_jitter=True`**: añade ruido aleatorio (± unos segundos) para evitar tormentas de reintentos (thundering herd).
- **`task_acks_late=True`**: el worker confirma la tarea solo al completar exitosamente. Si el worker se cae durante el procesamiento, la tarea se reencola automáticamente.
- **`task_reject_on_worker_lost=True`**: si el worker se pierde inesperadamente, la tarea se reencola para otro worker.

### 40) Patrón: Señales Celery para trazabilidad del ciclo de vida
- **`task_success`**: registra nombre de la tarea al completarse correctamente.
- **`task_failure`**: registra `task_id`, mensaje de error y traceback (primeros 500 caracteres).
- **`task_retry`**: registra `task_id`, número de intento (`attempt={_retries}/{_max}`), razón del fallo y traceback. Usa preformateo para evitar que Celery reinterprete placeholders.
- **`task_revoked`**: registra `task_id` y fecha de expiración.
- **`on_after_configure`**: registra broker URL, backend URL y colas configuradas al iniciar el worker.

### 41) Patrón: Cola DLQ explícita en Celery
- Además de la DLQ persistente en TinyDB, se define una **cola DLQ explícita** en Celery (`healthcore.dlq`) con su propio exchange y routing key.
- Las tareas que fallan irreversiblemente pueden redirigirse a esta cola para inspección manual sin perder el mensaje original.
- Configuración: `task_queues={"healthcore.default": {...}, "healthcore.dlq": {...}}`.
- Esto permite que un worker dedicado a la cola DLQ procese (o simplemente acumule) las tareas fallidas.

### 42) Patrón: Logging con get_task_logger y time.monotonic()
- La tarea `analyze_incidents_csv` usa `get_task_logger(__name__)` para logging específico de la tarea con trazabilidad.
- Registra **STARTED** con `task_id`, `filename`, `csv_size`.
- Registra **SUCCESS** con `task_id`, `filename`, `duration` (segundos con `time.monotonic()`), `total`, `valid`, `invalid`.
- `time.monotonic()` es más fiable que `time.time()` para medir duración (no afectado por cambios de hora del sistema).

## Patrones de servicios standalone e infraestructura de datos

### 43) Patrón de servicios standalone para evitar SQLModel crash
- **Problema**: Python 3.14 + SQLModel 0.0.48 causa `TypeError: issubclass() arg 1 must be a class` al cargar `MedicalSupply(SQLModel, table=True)` en `models.py:315`.
- **Solución**: Crear servidores FastAPI independientes que no importan `models.py`:
  - `services/telemetry/server_standalone.py` — telemetría + auth (puerto 8000)
  - `services/api/auth_standalone.py` — auth-only (puerto 8000, coexiste)
  - `services/reporting/main.py` — reporting API (puerto 8001)
- Cada servicio standalone replica solo las funciones necesarias (bcrypt, JWT, consultas TinyDB/SQLAlchemy) sin tocar SQLModel.
- **Regla**: Si un nuevo endpoint no necesita modelos SQLModel, debe implementarse como servicio standalone, no en `main.py`.

### 44) Patrón de Reporting — API independiente con JWT compartido
- `services/reporting/` es una API FastAPI completamente independiente (puerto 8001) que comparte la misma `JWT_SECRET_KEY` con el API principal.
- `auth.py` usa `OAuth2PasswordBearer(tokenUrl="/auth/login")` para extraer y validar tokens sin acceder a base de datos de usuarios.
- No replica usuarios, perfiles ni roles — solo verifica que el token es válido (firma + expiración).
- Los endpoints de reporting se protegen con `_user_id: int = Depends(get_current_user_id)`.

### 45) Patrón de Clinic Name Mapping
- Los IDs internos de clínica (`clinic-001`, ..., `clinic-010`) se mapean a nombres reales mediante un diccionario plano en el backend.
- `CLINIC_NAMES` en `services/reporting/routes/reporting.py` asigna cada ID a un nombre descriptivo.
- El frontend muestra `{clinic.clinic_name || clinic.clinic_id}` como fallback.
- El mapeo se centraliza en el backend para evitar duplicación entre frontends.
- Fuentes del mapeo: `BRANCH_LABELS` en `uis/backoffice/lib/incidents.ts` + `CLINIC_TO_BRANCH` en `packages/shared/python/incident_model.py`.

### 46) Patrón de pipeline de datos con Prefect 3.x
- **`data/pipelines/`** implementa un pipeline ETL con Prefect 3.8.8.
- **Fases**: extract → transform → load, cada una en su propio módulo.
- **Restricción Prefect 3.x**: `@flow` objects NO tienen método `.submit()`. Las flows deben ejecutarse mediante llamada directa o dentro de un `@task`.
- **Workaround**: Usar try/except para llamar directamente al subflow, capturando cualquier error de flujo.
- **Runner**: `trigger_monthly_clinic_supply_performance()` en `runner.py` orquesta todo el pipeline.
- **Run Store**: `run_store.py` persiste metadatos de cada ejecución en tabla `pipeline_runs`.
- **Demo Data**: Cuando el pipeline no puede ejecutarse (Prefect incompatibilidad, PgBouncer), se insertan datos demo directamente en la tabla destino para verificar la cadena E2E.

### 47) Patrón de Supabase PgBouncer workaround
- Supabase usa PgBouncer (pooler) en modo transaccional, lo que causa conflictos de prepared statement cache en queries repetidas con named parameters estilo SQLAlchemy.
- **Solución**: Usar `sqlalchemy.text()` con raw SQL en lugar de `text("... :param")` con named parameters.
- Alternativamente, configurar `connect_args={"options": "-c prepared_statement_cache_size=0"}` al crear el engine.
- Este workaround es necesario solo para tablas en Supabase PostgreSQL vía pooler.

## Patrones de alto rendimiento (caché, lazy loading, timing)

### 26) Patrón de caché — Cache-Aside (backend)
- **Estrategia cache-aside**: el código pregunta primero a la caché (`cache.get(key)`); si existe el valor, lo devuelve sin tocar la base de datos. Si no existe, ejecuta la operación (consulta DB, cálculo), almacena el resultado en caché con `cache.set(key, value, ttl)`, y lo devuelve.
- **Clave única por combinación de parámetros**: en endpoints con filtros (GET /incidents), la clave incluye todos los parámetros de consulta serializados para que cada combinación de filtros tenga su propia entrada en caché.
- **Invalidación por prefijo de clave**: en lugar de rastrear claves individuales, se invalida un prefijo completo (`\"incidents:list\"` → elimina todas las claves que empiecen por `\"incidents:list:\"`). Es más simple y seguro que la invalidación selectiva.
- **TTL cortos (30-60s)**: se prioriza la frescura de datos sobre el ahorro máximo de consultas. Suficiente para reducir carga repetitiva sin riesgos de obsolescencia.

### 27) Patrón de Lazy Loading (frontend)
- **`next/dynamic` con `ssr: false`**: los componentes pesados que no se ven en carga inicial se importan dinámicamente. `ssr: false` evita que el servidor los procese, dejando la descarga al navegador bajo demanda.
- **Extracción a archivo independiente**: para poder usar `next/dynamic`, el componente debe estar en un archivo separado con `export default`. No funciona con exportaciones nombradas inline.

### 28) Patrón de `useMemo` con dependencias explícitas (frontend)
- Cada `useMemo` declara exactamente las variables de las que depende en su array de dependencias. Si el valor usa `sortedClaims`, la dependencia es `[sortedClaims]` — no la lista original.
- Esto evita recálculos en cadena: si cambia una variable que no afecta a cierto cómputo, ese cómputo no se repite.
- Los valores computados (derivados de otros `useMemo`) se encadenan correctamente respetando el grafo de dependencias.

### 29) Patrón de Timing Middleware (backend)
- Middleware FastAPI que captura el tiempo de inicio antes de procesar la request y calcula la diferencia después de enviar la respuesta.
- Loggea al formato: `METODO /ruta → CODIGO (X.XXms)` para permitir identificación de cuellos de botella sin herramientas externas de APM.
- No interfiere con el flujo de la request ni añade latencia medible.
