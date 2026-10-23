# Tech Context

## Stack técnologico

### Raíz del repositorio
- TypeScript 5.x
- Configuración estricta en tsconfig.json (strict, noImplicitAny, noUnusedLocals, noUnusedParameters).
- Script de validación: npm run typecheck.

### Sitio estático (hito web)
- HTML semántico (index/application en EN y ES).
- Tailwind CSS via CDN para estilos utilitarios.
- JavaScript vanilla en validation.js para validación del formulario.
- Datos estructurados Schema.org (MedicalOrganization + MedicalClinic) en landing.

### UI Talent Pipeline Tracker (uis/talent-pipeline-tracker)
- Next.js (App Router), React 19, TypeScript.
- Tailwind CSS 4 para estilos.
- ESLint configurado.
- Cliente fetch nativo para integración con API externa (NEXT_PUBLIC_API_URL).
- Autenticación JWT con localStorage.

### API HealthCore — Principal (services/api)
- Python 3.12, gestionado con uv (pyproject.toml en services/api, .venv local).
- **FastAPI + Uvicorn** para servir la API.
- **Pydantic v2** para modelado y validación de datos.
- **TinyDB** como almacenamiento en JSON para usuarios, proveedores y autenticación.
- **SQLModel 0.0.42** (SQLAlchemy 2.0.54) como ORM para inventario en Supabase PostgreSQL.
- **psycopg2-binary 2.9.13** como driver de PostgreSQL.
- **python-jose** para JWT (emisión y validación de tokens).
- **passlib + bcrypt** para hash de contraseñas.
- **Resend API** para envío de emails transaccionales.
- **requests** para llamadas HTTP externas (Resend).
- **dotenv** para configuración de variables de entorno.
- **pytest** para tests (9 archivos de test en services/api/tests/).
- **Cobertura**: `.coverage` en services/incidents-api.
- Scripts: `uv run seed` (carga inicial), `uv run uvicorn main:app --port 8000 --reload`.
- Ruta de TinyDB de proveedores: data/process/suppliers_db.json, sobreescribible con HEALTHCARE_DB_PATH.
- Ruta de TinyDB de usuarios/auth: services/api/db.json (creado automáticamente).
- Variables de entorno requeridas: JWT_SECRET_KEY, y opcionalmente RESEND_API_KEY, SUPABASE_URL, SUPABASE_KEY, HEALTHCORE_DB_PATH, RATE_LIMIT_MAX_REQUESTS, ACCESS_TOKEN_EXPIRE_MINUTES, etc.

### API de Incidencias (services/incidents-api)
- FastAPI independiente, puerto 8010.
- TinyDB como almacenamiento.
- pytest con tests funcionales (conftest.py, helpers.py, test_incidents.py).
- Análisis de CSV: `incidents_analysis.py` en services/api/.

### UI Backoffice (uis/backoffice)
- **Next.js 16** (App Router), **React 19**, **Tailwind CSS 4**.
- **TypeScript** estricto.
- ESLint configurado (eslint.config.mjs).
- Route handlers en `app/api/**` que actúan de proxy hacia FastAPI (SUPPLIERS_API_URL, por defecto http://127.0.0.1:8000). Útiles para auth (login, me, forgot-password, change-password, reset-password), profiles (me), users y suppliers.
- Rewrites en `next.config.ts`:
  - `/api/inventory/*` → `http://127.0.0.1:8000/inventory/*` (inventario, puerto 8000)
  - `/api/incidents/*` → `http://127.0.0.1:8010/api/incidents/*` (incidencias, puerto 8010)
- **Auth**: React Context (AuthProvider) + AuthGuard + localStorage (clave `healthcore_token`).
- **Capas de cliente HTTP**:
  - `lib/inventoryApi.ts` — cliente centralizado de inventario (con ApiError, extractErrorMessage, helpers de stock)
  - `lib/suppliersApi.ts` + `lib/suppliersProxy.ts` + `lib/suppliersServer.ts` — tres capas para proveedores
  - `lib/auth.ts` — utilidades de token (getToken, setToken, removeToken)
  - `lib/authHttpClient.ts` — cliente HTTP genérico con Bearer token y manejo 401
  - `lib/AuthContext.tsx` — React Context de autenticación
  - `lib/authProxy.ts` — proxy server-side de auth para route handlers
- **Componentes**: AuthGuard, BackofficeHeader (con links de inventario), SuppliersDirectoryClient, y 5 componentes de incidencias (IncidentListPanel, IncidentRegisterForm, IncidentSummaryPanel, IncidentsAnalyzerClient, IncidentsManagerClient).
- **Páginas protegidas**: /suppliers, /inventory/* (4), /incidents/* (5), /incidents-manager, /account/profile, /account/change-password.
- **Páginas públicas**: /login, /register, /forgot-password, /reset-password.

### UI Website público (uis/website)
- Next.js (App Router), React, TypeScript.
- Tailwind CSS 4.
- ESLint configurado.
- Sin autenticación — sitio público corporativo de HealthCore.
- Carga inicial en Server Component; refetch client-side solo desde event handlers.

### Telemetría — Servidor Standalone (services/telemetry)
- **`server_standalone.py`**: FastAPI independiente (puerto 8000) que evita SQLModel 0.0.42 (incompatible con Python 3.14 — `TypeError: issubclass()` en `models.py` L315).
- **`analysis.py`**: Pipeline de análisis con **pandas** + `read_sql()` sobre **Supabase PostgreSQL**. 5 funciones métricas: `events_per_day()`, `error_rate_by_type()`, `latency_percentiles_by_route()`, `event_type_distribution()`, `auth_failure_rate_by_day()`. Orquestadas por `run_all()` → `GET /telemetry/report`.
- **`auth_standalone.py`**: Módulo de autenticación autónomo (passlib bcrypt + python-jose JWT + TinyDB). No depende de `services/api/models.py`.
- **`seed_auth_users.py`**: Script autónomo para crear usuarios en TinyDB (admin@healthcore.com / adminpass456, test@healthcore.com / securepassword123).
- **Dependencias**: FastAPI, uvicorn, pandas, python-jose, passlib, bcrypt, TinyDB, supabase (opcional).
- **Caché**: diccionario en memoria con `time.monotonic()` + TTL 60s para el reporte.
- **Auth endpoints**: `POST /auth/login` (JWT), `GET /auth/me` (perfil+rol).
- **Variables de entorno**: `JWT_SECRET_KEY` (desde `services/api/.env`).

### Telemetría — Dashboard (uis/backoffice)
- **Página**: `app/telemetry/page.tsx` — 5 paneles visuales protegidos por AuthGuard.
- **Proxy**: rewrite en `next.config.ts`: `/api/telemetry/report` → `http://localhost:8000/telemetry/report`.
- **Navegación**: enlace "Telemetry" en BackofficeHeader.

### Telemetría — Documentación y esquemas
- **`docs/telemetry/event-schemas.json`**: Catálogo de 41 eventos (5 obligatorios, 36 oportunidades).
- **`docs/telemetry/telemetry-plan.md`**: Plan de telemetría completo con fases 1-5, arquitectura, decisiones técnicas.

### Proceso de segundo plano — Script nocturno de telemetría (independiente de la API)
- **Entorno de tests**: `.venv-nightly/` (raíz, gitignoreado): sqlalchemy 2.1.6, pandas 3.1.0, pytest 9.1.1, python-dotenv. Python 3.14. **Driver Postgres añadido**: `psycopg` 3.3.6 (+`psycopg2-binary` 2.9.13) para conexión a Supabase (el esquema `postgresql://` de SQLAlchemy 2.x requiere psycopg v3).
- **`.env` (raíz)**: `DATABASE_URL` de Supabase (`postgresql://...pooler.supabase.com:6543`). Ni `job_runner.py` ni el CLI cargan `.env` automáticamente — leen con `os.getenv()`. Para pruebas manuales hay que `load_dotenv()` o exportar la var.
- **Supabase verificado (2026-10-22, solo lectura)**: Postgres 17.6 OK; `telemetry_events` = **31 filas** (2026-10-04 al 2026-10-11; pico 2026-10-10=12). `job_runs`/`schema_migrations` **aún NO existen** (el job los auto-crearía con `ensure_schema`). Para un futuro humo completo: `--target-date 2026-10-10`.
- **Supabase — humo completo ejecutado (2026-10-22)**: corrida real con `--skip-pipeline --target-date 2026-10-10` → OUTCOME `completed`, 12 filas exportadas a `data/raw/telemetry_2026-10-10.csv`, fila en `job_runs` en `completed` con `exported_rows=12`. Idempotencia: 2ª corrida → `noop_export`. Se verificó la rama **Postgres** por primera vez contra Postgres real (BIGSERIAL, `now()`, UNIQUE(job_name,target_date), CHECK status). **Hallazgo**: `_ensure_schema_postgres` NO inserta versiones en `schema_migrations` (count 0), a diferencia de `_ensure_schema_sqlite`. DDL Postgres hardcodeado, sin versionar por fila en esa rama.
- **`services/job_runner.py`** (CONTROL DE ESTADO): estados `pending → processing → completed | failed` + reintento `failed → pending`. El lock ES el estado `processing` (UPDATE atómico `WHERE status='pending'`). Helpers: `has_processing_lock`, `has_completed_for_date`, `mark_processing`, `reset_failed_to_pending`, `mark_completed`, `mark_failed`, `log_result`. Logger estable `healthcore.nightly`.
- **`services/nightly/nightly_service.py`**: orquestación `run_nightly()` (export CSV → subprocess pipeline → registro). `_DEFAULT_PIPELINE_CMD = "python -m data.pipelines.runner"` (pipeline real del Hito 6).
- **`scripts/nightly_export.py`**: CLI con flags `--skip-pipeline`, `--force`, `--target-date`, `--list`, `--dry-run`. Salida JSON; exit 0 (completed/noop_export/aborted) / 1 (failed).
- **Tabla `job_runs`**: UNIQUE(job_name, target_date), DDL en `data/migrations/0002_job_runs.sql`. Auto-migración `ensure_schema` (versionada en `schema_migrations`, _MIGRATIONS 1-3).
- **Dual dialecto SQL**: SQLite (dev/tests, `CURRENT_TIMESTAMP` / `INTEGER PRIMARY KEY AUTOINCREMENT`) y Postgres/Supabase (prod, `now()` / `BIGSERIAL`) vía `sqlalchemy.text()`.
- **Disparo**: crontab `0 2 * * *` UTC o contenedor scheduler dedicado (recomendado en prod). PROHIBIDO dentro de FastAPI (no APScheduler/@repeat_every/lifespan). `TARGET_DATE=YYYY-MM-DD` (env o `--target-date`) para override.
- **Demo de auditoría**: `scripts/_audit_hito7_demo.py` — reproducible, lanza 2 instancias CLI reales en carrera contra BD SQLite compartida.

## Decisiones de arquitectura tomadas
1. Mantener hito web y hito Next.js coexistiendo en el mismo repo para evaluación incremental.
2. Centralizar tipos de dominio del tracker en types/candidate.ts.
3. Encapsular llamadas API en un módulo único de servicios.
4. Implementar validación de formularios en librerías dedicadas (validation.js y lib/validation.ts).
5. Priorizar funciones puras para lógica de negocio en src/utils.
6. Validar en el borde con Pydantic: las reglas de negocio del CONTEXT (moneda por país, tarifa positiva, enums de estado y categoría) se rechazan con 422 antes de tocar TinyDB.
7. Baja lógica en el directorio de proveedores: DELETE no borra, marca `archived_at`. `status` conserva únicamente los valores del CONTEXT.
8. No cargar datos en useEffect en el backoffice: la carga inicial es server-side y evita la regla react-hooks/set-state-in-effect.
9. **Arquitectura dual de BD**: TinyDB para usuarios/auth/proveedores, Supabase PostgreSQL para inventario. El modelo User NO existe en SQLModel.
10. **Dos APIs separadas**: API principal (puerto 8000) para proveedores, auth, inventario. API de incidencias (puerto 8010) independiente.
11. **Dos estrategias de proxy**: route handlers de Next.js para auth/suppliers (permiten lógica server-side como forwardHeaders), rewrites de next.config.ts para inventario/incidencias (más simples, sin lógica intermedia).
12. **Capa API dedicada para inventario**: inventoryApi.ts centraliza todas las llamadas. Ningún componente de inventario hace fetch directo. Esto contrasta con el patrón anterior donde algunos componentes podían tener fetch inline.
13. **Stock reactivo en frontend**: al seleccionar un producto en el formulario de salida, se dispara fetchProduct() para obtener el stock fresco de la API. No confía solo en el listado inicial.
14. **Dockerización para desarrollo**: contenedores separados por servicio, comunicación por nombre Docker, bind mounts para hot-reload.
15. **Configuración dual de tsconfig**: `tsconfig.json` principal para producción (excluye `__tests__`), `tsconfig.test.json` para Jest (con `types: ["jest", "node"]`).
16. **Init_supabase_schema graceful skip**: `database.py` verifica `if not DATABASE_URL:` antes de llamar a `get_sql_engine()`, permitiendo desarrollo local sin Supabase. La función retorna silenciosamente con un mensaje informativo en logs.
17. **Montaje `src/` dentro del proyecto (Turbopack compatibility)**: Para que Turbopack resuelva imports compartidos, `./src:/workspace/uis/backoffice/src` se monta dentro del directorio del proyecto backoffice. Los imports cambian de `../../../src/...` a `../src/...`. Esto evita el error de Turbopack de no resolver imports fuera del directorio del proyecto.
18. **Desactivación de optimización de imágenes en contenedor**: `next.config.ts` del website usa `images: { unoptimized: true }` para que el navegador cargue imágenes externas (Unsplash) directamente, evitando errores `EAI_AGAIN` por falta de resolución DNS en el contenedor.
19. **Serialización explícita en todos los endpoints backend**: 38/38 endpoints tienen `response_model` declarado. Schemas separados para entrada/salida, listado/detalle, y mensajes genéricos. Ningún endpoint expone contraseñas hasheadas, tokens internos, FK internas (`user_id`) ni campos pesados en listados (`notes`).
20. **Cliente HTTP único del backoffice (`lib/httpClient.ts`)**: Consolida la lógica de fetch + JWT + error handling que antes estaba duplicada en 3 archivos. Exporta `request<T>()`, `jsonRequest()`, `ApiError`, `extractErrorMessage()`, `ValidationIssue`.
21. **Componentes UI reutilizables (`components/ui/`)**: `LoadingSpinner`, `ErrorMessage`, `EmptyState` — abstraen los patrones de estado de carga/error/vacío que antes estaban implementados inline en cada componente.
22. **Optimización de imágenes LCP**: Prop `priority` en Next.js Image para la imagen hero del website, que genera `fetchpriority="high"` + `<link rel="preload">` + elimina `loading="lazy"`.
23. **Telemetría — única función pública `track()`**: Todo evento de telemetría frontend se emite exclusivamente mediante `track(eventType, properties)` del módulo `lib/telemetry.ts`. Componentes, hooks y servicios auxiliares (`TelemetryService.control.ts`) llaman a `track()` — nunca hacen fetch directo ni mantienen colas propias.
24. **Telemetría — canal de control unificado**: `TelemetryService.control.ts` se refactorizó para eliminar su fetch pipeline independiente. `recordTelemetryControl()` valida propiedades y llama a `track()`. Los eventos de diagnóstico (`telemetry_delivery_failed`, `api_retry_exhausted`, `telemetry_event_dropped`) se envían por el mismo canal `/api/telemetry/events` en frontend. El backend sí mantiene `control_queue` separada en `telemetry_delivery.py` para evitar recursión en servidor.
25. **Telemetría — proxy de conectividad**: `telemetryEndpoint.ts` transforma URLs loopback (`localhost`, `127.0.0.1`) en `/api/telemetry/events` para el navegador. El route handler de Next.js reenvía al backend via `TelemetryService.server.ts`. `TELEMETRY_ENDPOINT` tiene prioridad; fallback a `SUPPLIERS_API_URL` en Docker.
26. **Telemetría — stacked decorators en backend**: El router `telemetry.py` registra `/telemetry/events` y `/telemetry/control` mediante `@router.post` apilados en el mismo handler. Ambos retornan `TelemetryReceipt(received=N)`.
27. **Telemetría — backend dual detectado**: En Codespaces pueden existir múltiples procesos FastAPI. Es crítico matar procesos anteriores y reiniciar con `uvicorn main:app --port 8000 --reload` para activar código fresco. Verificar OpenAPI `/docs` confirma que ambas rutas de telemetría están registradas.
28. **Telemetría — servidor standalone para evitar SQLModel crash**: La API principal (`services/api/main.py`) no arranca en Python 3.14 porque SQLModel 0.0.42 causa `TypeError: issubclass() arg 1 must be a class`. La solución no es degradar Python sino crear `services/telemetry/server_standalone.py` que no importa `models.py`. Este servidor coexiste en el mismo puerto 8000 y sirve telemetría + auth.
29. **Telemetría — seed de usuarios autónomo**: `seed_auth_users.py` es un script independiente que escribe en TinyDB sin depender de `models.py` ni de `database.py`. Usa passlib directamente para hashear contraseñas. Esto evita el crash de SQLModel al importar modelos. Los usuarios se escriben en la tabla `users` de `data/process/suppliers_db.json`.
30. **Telemetría — dashboard sin route handler intermedio**: A diferencia de auth/suppliers que usan route handlers Next.js con lógica server-side, el dashboard de telemetría usa un rewrite directo en `next.config.ts`. Esto es más simple y evita bugs como el anterior `base.protocol` (propiedad URL inválida en JavaScript). El rewrite `/api/telemetry/report` → `http://localhost:8000/telemetry/report` resuelve la llamada en servidor sin código intermedio.

## Docker y orquestación

### docker-compose.yml (raíz)
- **Red**: `healthcore-net` (bridge explícito).
- **Servicios**: `uis` (Node.js), `backend` (Python), `incidents-backend` (Python).
- **Contexto de build**: siempre `.` (raíz), con `.dockerignore` para filtrar.
- **Montajes**: bind mounts de código fuente + volúmenes anónimos para `node_modules`.
- **Variables de entorno**: via `env_file: .env`.
- **Comunicación**: por nombre de servicio Docker (`http://backend:8000`, `http://incidents-backend:8010`).

### uis/Dockerfile
- **Imagen base**: `node:22-alpine`.
- **3 etapas**: base, deps-website, deps-backoffice, runner.
- **Puertos**: 3000 (website) y 3001 (backoffice).
- **Entrypoint**: `start.sh` que lanza ambos Next.js en paralelo con `npm run dev`.

### services/Dockerfile
- **Imagen base**: `python:3.12-slim`.
- **Instalación**: `pip install uv` → `uv pip install --system` desde ambos `requirements.txt`.
- **Puertos**: 8000 (api) y 8010 (incidents-api).
- **Entrypoint**: `entrypoint.sh` que selecciona `uvicorn` según `SERVICE_NAME`.

### Variables de entorno para Docker (.env)
- `SUPPLIERS_API_URL=http://backend:8000`
- `INCIDENTS_API_URL=http://backend:8000` (¡no backend:8010!)
- `NEXT_PUBLIC_INVENTORY_API_URL=http://backend:8000`
- `NEXT_PUBLIC_INCIDENTS_API_URL=/api/incidents`
- `JWT_SECRET_KEY=dev-secret-not-for-production`
- `RESEND_API_KEY=` (vacío, simulación en consola)

## Tests y TypeScript

### Jest (uis/backoffice)
- `jest.config.ts` configurado con `ts-jest` y `tsconfig.test.json`.
- `tsconfig.test.json`: extiende `tsconfig.json`, añade `types: ["jest", "node"]`, incluye `__tests__`.
- 11 tests pasando (0.723s): suppliers proxy, auth, suppliers API.
- Ejecución: `npx jest` desde `uis/backoffice/`.

### TypeScript
- `__tests__` excluido del `tsconfig.json` principal para evitar conflictos de tipos.
- Recarga de ventana VS Code necesaria después de cambios en tsconfig (TypeScript cachea el proyecto).

## Restricciones técnicas
- El contenido y campos deben seguir exactamente CONTEXT.md para cumplir evaluación.
- Bilingüismo obligatorio en la experiencia pública (EN/ES).
- API URL del tracker depende de variable de entorno NEXT_PUBLIC_API_URL.
- Validación de TypeScript exigida sin errores en raíz y en UI Next.js.
- `status` de proveedor limitado a "active" y "suspended": no ampliar el enum aunque el negocio pida más estados.
- data/process/suppliers_db.json y services/api/.venv están en .gitignore: son artefactos regenerables.
- **Inventario**: `current_stock` no se almacena ni se modifica directamente. Solo se cambia mediante órdenes.
- **Inventario**: `consumption_type` validado en schema Pydantic, solo `"clinical_use"` y `"expiry_waste"`.
- **Inventario**: stock insuficiente → HTTP 400 antes de escribir en BD.
- **Inventario**: los datos de inventario son operativos, no PHI (confirmado por Claire Whitfield).
- El proyecto tiene estructura de plantilla; no todo el monorepo está operativo en runtime aún.
- **Serialización**: los endpoints de auth no autenticados (forgot/reset/change-password) deben devolver solo `message` — nunca reenviar el email en la respuesta.
- **Serialización**: los schemas de listado deben ser más ligeros que los de detalle (sin `notes` en proveedores, sin `user_id` en perfiles).
- **Caché — MemoryCache**: implementación ligera con `dict` + `time.monotonic()` para expiración. No requiere dependencias externas (no Redis). La invalidación es por prefijo de clave, no selectiva.
- **Caché — Limitación**: la caché en memoria no persiste entre reinicios del servidor ni comparte estado entre workers. Si la aplicación escala horizontalmente, cada worker tendrá entradas de caché independientes y el beneficio se reduce. Para multi-worker se requiere migrar a Redis.
- **Caché — TTLs**: se usan TTLs cortos (30-60 segundos) para equilibrar frescura de datos con reducción de carga. No se usan TTLs largos (>5 min) en ningún endpoint por la naturaleza operativa de los datos.
- **Caché — Frontend (useMemo)**: la dependencia explícita en el array de `useMemo` es crítica para evitar recálculos en cadena. Si un `useMemo` depende de otro valor computado, debe declarar esa dependencia (ej: `[sortedClaims]`).
- **Caché — Lazy Loading**: los componentes importados con `next/dynamic` y `ssr: false` se descargan bajo demanda desde el navegador. El servidor no los procesa en SSR. Requieren `export default` en un archivo independiente.

## Comandos útiles
- Preview estático en Codespaces: npx --yes serve . --listen 4173 --no-clipboard
- Typecheck raiz: npm run typecheck
- Tracker dev: cd uis/talent-pipeline-tracker && npm run dev
- Tracker typecheck: cd uis/talent-pipeline-tracker && npm run typecheck
- Seed de proveedores: cd services/api && uv run seed (falla desde la raíz: el pyproject vive en services/api)
- Seed de inventario: el mismo `uv run seed` incluye seed_inventory()
- API dev (principal): cd services/api && uv run uvicorn main:app --port 8000 --reload
- API dev (incidencias): cd services/incidents-api && uv run uvicorn main:app --port 8010 --reload
- Backoffice dev: cd uis/backoffice && npm run dev (http://localhost:3000)
- Backoffice build: cd uis/backoffice && npm run build
- Backoffice checks: cd uis/backoffice && npm run typecheck && npm run lint
- Tests API principal: cd services/api && uv run pytest
- Tests API incidencias: cd services/incidents-api && uv run pytest
- Website dev: cd uis/website && npm run dev
- Login test admin: admin@healthcore.com / Admin123! (creado vía API)
- Login telemetry admin: admin@healthcore.com / adminpass456 (seed en TinyDB)
- Login telemetry test: test@healthcore.com / securepassword123 (seed en TinyDB)
- Servidor standalone telemetry: cd services/telemetry && python server_standalone.py (puerto 8000)
- Seed usuarios telemetry: cd services/telemetry && python seed_auth_users.py
- Analysis pipeline test: cd services/telemetry && python -c "from analysis import *; r=run_all(); print({k: len(v) for k,v in r.items()})"
- Dashboard telemetry: http://localhost:3000/telemetry (backoffice, requiere login)
- **Auth Standalone**: `cd services/api && python auth_standalone.py` (puerto 8000, login + /me)
- **Reporting API**: `cd services/reporting && uvicorn main:app --host 0.0.0.0 --port 8001 --reload`
- **Reporting Dashboard**: http://localhost:3001/reporting (backoffice, requiere login)
- **Pipeline (Prefect)**: `cd data/pipelines && python -c "from runner import trigger_monthly_clinic_supply_performance; print(trigger_monthly_clinic_supply_performance())"`

## Servicios de Reporting y Pipeline

### Auth Standalone (`services/api/auth_standalone.py`)
- **Propósito**: Servidor FastAPI ligero que provee únicamente `POST /auth/login` y `GET /auth/me` para el backoffice.
- **Stack**: bcrypt + python-jose (JWT HS256, 24h expiración) + TinyDB (`data/process/suppliers_db.json`).
- **CORS**: permitido para todos los orígenes (desarrollo).
- **No depende de SQLModel ni Supabase**: evita el crash de `models.py` L315 en Python 3.14.
- **Credenciales semilla**: `admin@healthcore.com` / `adminpass456` (admin), `test@healthcore.com` / `securepassword123` (user).
- **Bug corregido**: `/auth/me` cambiado de query param a `Header(None)` para leer correctamente `Authorization: Bearer <token>`.

### Reporting API (`services/reporting/`)
- **Propósito**: API independiente (puerto 8001) que expone KPIs mensuales de suministros por clínica.
- **Stack**: FastAPI + SQLAlchemy (text()) + Supabase PostgreSQL.
- **Auth**: `OAuth2PasswordBearer` con misma `JWT_SECRET_KEY` que `services/api/`. Valida tokens sin acceder a base de datos de usuarios.
- **Endpoints**:
  - `GET /reporting/monthly-clinic-supply-performance` — lista KPIs del último periodo o por mes específico
  - `GET /reporting/pipeline-runs/latest` — última ejecución del pipeline
  - `POST /reporting/pipeline-runs` — disparo manual del pipeline
- **Clinic Name Mapping**: `CLINIC_NAMES` dict en `routes/reporting.py` asigna nombres reales a IDs `clinic-001`..`clinic-010`.
- **Tabla destino**: `reporting.monthly_clinic_supply_performance` en Supabase PostgreSQL.

### Pipeline de Datos (`data/pipelines/`)
- **Orquestador**: Prefect 3.8.8.
- **Componentes**:
  - `extract.py`: Extracción de datos fuente (telemetry_events + suppliers).
  - `transform.py`: Transformación y agregación — Bug corregido: int clinic_id crasheaba `.strip()`.
  - `load.py`: Carga en tabla destino reporting.
  - `flows.py`: Flujos Prefect (`@flow`) — Bug corregido: `.submit()` no soportado en Prefect 3.x para `@flow` objects.
  - `runner.py`: `trigger_monthly_clinic_supply_performance()` — entry point de ejecución.
  - `run_store.py`: Persistencia de metadatos de ejecución en tabla `pipeline_runs`.
  - `database.py`: Conexiones SQLAlchemy a base de datos destino (Supabase PostgreSQL).
  - `models.py`: Modelos de datos del pipeline.
  - `PIPELINE_DESIGN.md`: Documento de diseño (archivo ignorado por Copilot).
- **Limitaciones conocidas**:
  - Prefect 3.8.8: `@flow` objects no tienen `.submit()`. Llamar directamente.
  - Supabase PgBouncer: prepared statement cache conflict. Usar raw SQL.
  - Python 3.14 + SQLModel 0.0.48: `TypeError: issubclass()` — servicios standalone evitan el crash.

### Demo Data (Reporting)
- 10 filas insertadas directamente en `reporting.monthly_clinic_supply_performance` para Octubre 2026.
- 5 clínicas US (USD) + 5 clínicas UK (GBP).
- Coste total mensual: $13,251.25.

### Dashboard Reporting (`uis/backoffice/app/reporting/page.tsx`)
- Página protegida por AuthGuard en `/reporting`.
- Tabla de KPIs y resumen visual.
- Proxy en `next.config.ts`: `/api/reporting/:path*` → `http://localhost:8001/reporting/:path*`.
- **Fix JWT**: Reemplazado `fetch(url)` por `request<T>(url)` (httpClient.ts) para incluir Bearer token.
