# Active Context

## Entregables activos en el repositorio

### 1) Landing y formulario bilingüe
- index.html e index.es.html: secciones corporativas de HealthCore con JSON-LD requerido.
- application.html y application.es.html: formulario de consulta de pacientes.
- validation.js: validaciones de negocio, estados de error/correcto, mensajes y comportamiento dinámico.

### 2) Utilidades TypeScript de negocio (src/)
- types/models.ts: entidades Claim, Appointment, Clinician, Location y reportes CME.
- utils/collections.ts: filtros, ordenamientos y agrupaciones.
- utils/search.ts: busqueda lineal y binaria.
- utils/transformations.ts: agregaciones y métricas (denial rate, no-show cost, CME report).
- utils/validations.ts: validaciones de claim y clinician + thresholds.

### 3) Talent Pipeline Tracker (Next.js)
- app/page.tsx: listado, filtros por query params, búsqueda y alta de candidatura.
- app/candidates/[id]/page.tsx + components/CandidateDetailClient.tsx: detalle, PATCH de estado/etapa, notas y reemplazo de registro.
- components/CandidateForm.tsx: formulario reutilizable de alta/edición.
- services/api.ts: cliente HTTP centralizado con autenticación JWT (Bearer token desde localStorage).
- types/candidate.ts y lib/validation.ts: contrato de datos y validación.
- **Autenticación**: lib/auth.ts (tipos y utilidades de token), lib/AuthContext.tsx (React Context), components/AuthGuard.tsx (guard de rutas con PUBLIC_ROUTES), components/TrackerHeader.tsx (controles de sesión), app/AuthShell.tsx (composición provider+guard+header), app/login/page.tsx, app/register/page.tsx, app/account/profile/page.tsx — login/registro llama directamente a NEXT_PUBLIC_API_URL (FastAPI).

### 4) API HealthCore — Directorio de Proveedores + Autenticación (services/api)
- models.py: modelos Pydantic (Supplier, SupplierCreate, SupplierReplace, SupplierRateUpdate, SupplierStatusUpdate, User, UserCreate, UserOut, UserUpdate, LoginRequest, Token, MeResponse, ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest, Profile, ProfileUpdate, Role enum) con enums de país, moneda, categoría, estado y acuerdo de cumplimiento, más validador de coherencia moneda-país.
- database.py: inicialización de TinyDB (data/process/suppliers_db.json, override con HEALTHCARE_DB_PATH) + get_sql_engine() para Supabase PostgreSQL + init_supabase_schema() + get_db() session generator.
- security.py: JWT stateless con bcrypt (hash/verify), OAuth2PasswordBearer, create_access_token, get_current_user, create_reset_token/validate/invalidate.
- user_service.py: CRUD de usuarios y perfiles en TinyDB (create_user, get_user_by_email, get_user_by_id, list_users, update_user, create_profile, get_profile_by_user_id, update_profile_by_user_id).
- audit_logger.py: registro de eventos de restablecimiento de contraseña en tabla `password_reset_audit` de TinyDB.
- email_service.py: envío de emails transaccionales mediante Resend (simulado en consola si no hay RESEND_API_KEY).
- rate_limiter.py: control de tasa para forgot-password (5 solicitudes por email cada 60 minutos).
- incidents_analysis.py: analizador de CSV de incidencias de pacientes (parseo, validación de clínicas/categorías/orígenes, reportes con conteo por tipo).
- routes/suppliers.py: listado con filtros, búsqueda por país y por categoría, alta, reemplazo, PATCH de tarifa (registra updated_at), PATCH de estado y DELETE como baja lógica (suspende y sella archived_at, no borra).
- routes/auth.py: POST /auth/login (JWT), GET /auth/me (perfil actual), POST /auth/forgot-password, POST /auth/reset-password, POST /auth/change-password.
- routes/profiles.py: GET/PUT /profiles/me (lectura y actualización del perfil del usuario autenticado).
- routes/users.py: CRUD de usuarios (POST /users con hash de password + creación de perfil, GET /users listado, GET/PUT/DELETE por ID).
- routes/inventory.py: API de inventario con SQLModel + Supabase.
- seed.py: carga idempotente de 15 proveedores (`seed_suppliers()`) + inventario (`seed_inventory()`: 6 supplies, 4 deliveries, 3 consumptions). Ejecutable como `uv run seed`.
- tests/ (9 archivos): conftest.py con seed_user + seed_admin fixtures, tests para login, forgot/reset/change password, /me, user_service, security.
- pyproject.toml: dependencias y scripts.

### 6) Módulo de Inventario — Backend (FastAPI + SQLModel + Supabase PostgreSQL)
- **Archivo router:** `services/api/routes/inventory.py`
- **Modelos SQLModel:** `MedicalSupply`, `SupplyDelivery`, `SupplyConsumption` (añadidos en `services/api/models.py`)
- **Schemas Pydantic separados:** `services/api/schemas.py` (MedicalSupplyCreate/Response, SupplyDeliveryCreate/Response, SupplyConsumptionCreate/Response)
- **Base de datos:** Supabase PostgreSQL (`postgresql://postgres.vtuwongbxvyirfaxpqtt:iinCXLIg3QT9pwQH@aws-1-eu-west-1.pooler.supabase.com:6543/postgres`)
- **Inicialización:** `init_supabase_schema()` en `database.py`, llamado desde `lifespan` de `main.py`
- **6 endpoints** bajo prefijo `/inventory`:
  - `GET /inventory/products` — lista con stock calculado
  - `POST /inventory/products` — crear suministro
  - `GET /inventory/products/{id}` — detalle con stock
  - `POST /inventory/orders/inbound` — registrar entrada (SupplyDelivery)
  - `POST /inventory/orders/outbound` — registrar salida (SupplyConsumption), rechaza stock negativo con 400
  - `GET /inventory/orders` — historial completo con datos del suministro
- **Reglas de negocio:** stock calculado (nunca almacenado), stock insuficiente → HTTP 400, consumption_type validado, clinic_id 1-12, user_uuid referencia TinyDB
- **Seed data:** `seed.py` → `seed_inventory()` con 6 supplies, 4 deliveries, 3 consumptions (ya ejecutado, 8 productos en Supabase)

### 7) Módulo de Inventario — Frontend (uis/backoffice)
- **Capa API dedicada:** `uis/backoffice/lib/inventoryApi.ts` — centraliza TODAS las llamadas, sin fetch directo en componentes
- **Proxy Next.js:** `next.config.ts` rewrite `/api/inventory/*` → `http://127.0.0.1:8000/inventory/*`
- **4 páginas protegidas:**
  - `/inventory/products` — tabla con código de color (rojo=crítico, ámbar=bajo, verde=saludable), botones "Entrada"/"Salida" por fila
  - `/inventory/orders/inbound` — formulario: selector producto, cantidad, proveedor, clínica; feedback éxito/error
  - `/inventory/orders/outbound` — formulario con **stock reactivo** (fetchProduct por API al seleccionar), advertencia cliente si cantidad > stock, botón deshabilitado
  - `/inventory/orders` — historial solo lectura con tarjetas: borde verde (entrada) / ámbar (salida), nombre, SKU, cantidad, detalle, clínica, fecha, user_uuid
- **Umbrales de stock:** ≤0 = critical (rojo), <20 = low (ámbar), ≥20 = healthy (verde)
- **Helpers:** `getStockLevel`, `getStockLevelColor`, `getStockLevelLabel` en inventoryApi.ts
- **Error handling:** Clase `ApiError`, `extractErrorMessage()` extrae detail de la API, errores 400 visibles en UI
- **Autenticación:** misma que el resto del backoffice (AuthGuard + `if (!user) return null`)
- **Header actualizado:** BackofficeHeader.tsx con links: 📦 Stock, 📥 Registrar Entrada, 📤 Registrar Salida, 📋 Historial

### 8) API de Incidencias (services/incidents-api)
- **API independiente** en FastAPI (puerto 8010), separada de la API principal de proveedores.
- `models.py`: IncidentCreate, IncidentResponse, IncidentUpdate con categorías, orígenes, estados, clinic_id.
- `database.py`: inicialización de TinyDB específica para incidencias.
- `routes/incidents.py`: CRUD de incidencias (GET listado con filtros, POST crear, GET/PUT por ID, DELETE).
- `main.py`: app FastAPI con CORS abierto y manejadores de errores globales.
- `tests/`: conftest.py, helpers.py, test_incidents.py (tests funcionales).
- Proxy en next.config.ts: `/api/incidents/*` → `http://127.0.0.1:8010/api/incidents/*`

### 9) Frontend de Incidencias (uis/backoffice)
- `/incidents` — página principal con `IncidentsAnalyzerClient` (subida de CSV y análisis).
- `/incidents/list` — listado de incidencias registradas con filtros.
- `/incidents/register` — formulario de registro de nueva incidencia.
- `/incidents/summary` — resumen/estadísticas de incidencias.
- `/incidents-manager` — página de gestión de incidencias con `IncidentsManagerClient`.
- Componentes: `IncidentListPanel`, `IncidentRegisterForm`, `IncidentSummaryPanel`, `IncidentsAnalyzerClient`, `IncidentsManagerClient`.

### 10) Website público (uis/website)
- Aplicación Next.js independiente para el sitio público de HealthCore.
- `app/`: páginas públicas (sin autenticación).
- `components/`: componentes de UI del sitio público.
- `data/`: datos estáticos del sitio.
- `types/`: tipos TypeScript del sitio.
- Configurado con ESLint, Next.js config, PostCSS, Tailwind CSS.

### 11) Scripts de análisis (scripts/)
- `analyze.py`: script de análisis de datos.
- `seed_incidents.py`: seed de incidencias desde CSV.

### 12) Dockerización completa del monorepo para desarrollo
- **Objetivo**: Cualquier miembro del equipo ejecuta `docker compose up` desde la raíz y toda la plataforma está operativa.
- **3 servicios** en `docker-compose.yml`:
  - `uis`: website (Next.js, puerto 3000) + backoffice (Next.js, puerto 3001)
  - `backend`: FastAPI principal (proveedores, auth, inventario, puerto 8000)
  - `incidents-backend`: FastAPI de incidencias (puerto 8010)
- **Red Docker explícita**: `healthcore-net` (bridge)
- **Comunicación entre servicios**: por nombre Docker (`http://backend:8000`, `http://incidents-backend:8010`), no por localhost.
- **Bind mounts** para hot-reload en desarrollo (cambios locales → reflejados en el contenedor).
- **Volúmenes anónimos** para `node_modules` (evita sobreescribir con bind mount del host).

### 13) Archivos Docker creados
- **`docker-compose.yml`** (raíz): orquestación de 3 servicios con `env_file: .env`, red `healthcore-net`, bind mounts, healthcheck opcional.
- **`uis/Dockerfile`**: imagen multi-etapa Node 22 Alpine (base → deps-website → deps-backoffice → runner). EXPOSE 3000 3001. CMD `start.sh`.
- **`uis/start.sh`**: arranca ambos Next.js en paralelo (website:3000, backoffice:3001) con trap SIGTERM/SIGINT + wait.
- **`uis/.dockerignore`**: excluye node_modules, .next, .env, .log del contexto Docker de uis.
- **`services/Dockerfile`**: imagen Python 3.12-slim + uv. Copia ambos requirements.txt, los instala, copia `services/api` y `services/incidents-api`. EXPOSE 8000 8010.
- **`services/entrypoint.sh`**: entrypoint dinámico según `SERVICE_NAME` (api→8000, incidents-api→8010) con `uvicorn --reload`.
- **`services/.dockerignore`**: excluye `__pycache__`, `*.pyc`, `.env*`, `tests/`, `*.log`.
- **`.dockerignore`** (raíz): reduce drásticamente el contexto de build (node_modules, .env, `__pycache__`, `.next`, `.venv`, etc.).

### 14) Actualización de URLs para entorno Docker
- **Route handlers** (`authProxy.ts`, `suppliersProxy.ts`, `suppliersServer.ts`, `inventoryApi.ts`): fallbacks cambiados de `127.0.0.1:8000` a `http://backend:8000`.
- **`next.config.ts`**: rewrites actualizados de `127.0.0.1` a nombres Docker (`backend:8000`, `incidents-backend:8010`).
- **`IncidentsManagerClient.tsx`**: API_BASE cambiado de URL fija a relativa (`""`) para que pase por proxy Next.js.
- **`.env`**: `SUPPLIERS_API_URL=http://backend:8000`, `INCIDENTS_API_URL=http://backend:8000`, `NEXT_PUBLIC_INVENTORY_API_URL=http://backend:8000`, `NEXT_PUBLIC_INCIDENTS_API_URL=/api/incidents`.

### 15) Correcciones aplicadas
- **Bug corregido**: `INCIDENTS_API_URL` estaba en `backend:8010` pero el servicio backend solo escucha en `:8000`. Se usaba como fallback para auth/suppliers. Corregido a `backend:8000`.
- **`.dockerignore` raíz**: no existía inicialmente. El contexto de build pasó de ~987 kB a ~10.5 kB.
- **`requirements.txt`**: se añadieron `sqlmodel>=0.0.42` y `psycopg2-binary>=2.9.13` que estaban en `pyproject.toml` pero no en `requirements.txt`.
- **`.gitignore`**: se añadieron `.env.local` y `.env.*.local`.

### 16) Pruebas y verificación
- **`docker compose build`**: las 3 imágenes se construyen exitosamente.
- **Tests unitarios del backoffice**: 11/11 tests pasan con `npx jest` (0.723s).
- **TypeScript**: todos los errores resueltos (45 problemas iniciales en `suppliersProxy.test.ts`).
- **Configuración de tests**: `tsconfig.test.json` creado con `types: ["jest", "node"]`, `jest.config.ts` actualizado para usarlo, `__tests__` excluido del `tsconfig.json` principal.

### 17) Correcciones runtime (docker compose up)
- **Problema**: Backoffice (3001) daba error 500 — `Module not found: Can't resolve '../../../src/utils/transformations'`
  - **Causa raíz**: Turbopack no resuelve imports fuera del directorio del proyecto, aunque `experimental: { externalDir: true }` esté configurado. El volumen de `src/` estaba montado en `/workspace/src/` pero el import `../../../src/` queda fuera del árbol de resolución de Turbopack.
  - **Solución**: se montó `./src:/workspace/uis/backoffice/src` en docker-compose.yml para que la carpeta `src/` esté dentro del proyecto backoffice. Los imports en `app/page.tsx` se cambiaron de `../../../src/...` a `../src/...`.
  - **Alternativa descartada**: `NEXT_DISABLE_TURBOPACK=1` + `@healthcore/*` path alias (Webpack tampoco resolvía bien externalDir).
- **Problema**: Backend (8000) crasheaba al arrancar — `RuntimeError: DATABASE_URL no está configurada`
  - **Causa raíz**: `init_supabase_schema()` llamaba a `get_sql_engine()` que lanza error si `DATABASE_URL` está vacía.
  - **Solución**: `init_supabase_schema()` ahora verifica si `DATABASE_URL` existe antes de llamar a `get_sql_engine()`. Añadido `logger.info` skip graceful. Añadido `import logging` en database.py.
- **Problema**: Website (3000) mostraba imágenes rotas — error `getaddrinfo EAI_AGAIN images.unsplash.com`
  - **Causa raíz**: El contenedor Docker no resuelve DNS externo. Next.js intenta optimizar imágenes (descargarlas, redimensionarlas, convertirlas) en el servidor y eso falla.
  - **Solución**: `images: { unoptimized: true }` en `uis/website/next.config.ts`. Ahora el navegador carga las imágenes directamente de Unsplash.

### 18) Estado actual de los servicios (docker compose up)
| Puerto | Servicio | Estado | URL |
|--------|----------|--------|-----|
| 3000 | Website (Next.js) | ✅ 200 | http://localhost:3000 |
| 3001 | Backoffice (Next.js) | ✅ 200 | http://localhost:3001 |
| 8000 | HealthCore API (FastAPI) | ✅ Arrancó sin Supabase | http://localhost:8000/docs |
| 8010 | Incidents API (FastAPI) | ✅ 200 | http://localhost:8010 |

- `incidents-healthcore.csv` / `incidents-COMPANY.csv`: datos históricos de incidencias.
- `results.csv`: resultados de análisis.
- app/suppliers/page.tsx: Server Component que hace la carga inicial y enlaza desde el menú.
- components/SuppliersDirectoryClient.tsx: tabla con filtros por país y categoría sin recarga, alta con validación en cliente, edición de tarifa inline y botones Suspender/Activar y Eliminar por fila.
- Tres estados visuales: Activo (verde), Suspendido (ámbar) y Eliminado (rojo, con fecha de baja).
- app/api/suppliers/**: route handlers que proxean a la API FastAPI (SUPPLIERS_API_URL) con forwarding del header Authorization.
- lib/suppliersApi.ts, lib/suppliersProxy.ts y lib/suppliersServer.ts: cliente HTTP, proxy con formateo de errores 422 y carga server-side.
- types/supplier.ts: contrato de datos alineado con los modelos Pydantic.
- **Autenticación**: lib/auth.ts (tipos y utilidades de token), lib/AuthContext.tsx (React Context con proxy a /api/auth/me), lib/authHttpClient.ts (cliente HTTP con Bearer token + manejo 401), components/AuthGuard.tsx (guard de rutas con PUBLIC_ROUTES), components/BackofficeHeader.tsx (controles de sesión), app/AuthShell.tsx (composición provider+guard+header), app/login/page.tsx, app/register/page.tsx, app/account/profile/page.tsx — login/registro llama a los proxies Next.js (/api/auth/login, /api/users) que reenvían a FastAPI.

## Decisiones de diseño vigentes
- **Autenticación vía React Context + localStorage**: El token JWT se almacena en localStorage (clave `healthcore_token`) y se adjunta como `Authorization: Bearer` a cada llamada protegida. No se usa middleware de Next.js. El provider se inicializa en el cliente, lee el token al montar y verifica la sesión con GET /auth/me. Al recibir 401 en cualquier llamada, se limpia el token y se redirige a /login.
- **Dos APIs backend separadas**: La API principal (proveedores, auth, inventario) corre en puerto 8000. La API de incidencias corre en puerto 8010 como servicio independiente.
- **Dos arquitecturas de proxy**: Backoffice usa route handlers de Next.js (`app/api/*`) para auth, suppliers y profiles (propagan Authorization). Inventario usa rewrites de `next.config.ts` para `/api/inventory/*`. Incidencias usa rewrites para `/api/incidents/*`.
- **Website público (Hito 1) no afectado**: La app `uis/website` no contiene referencias a AuthProvider, AuthGuard, useAuth ni al token, cumpliendo el requisito de solo proteger backoffice y tracker.
- **Talent Pipeline Tracker llama directamente** a `NEXT_PUBLIC_API_URL` desde el navegador (FastAPI), sin proxies.
- **El CONTEXT manda**: `status` solo admite "active" y "suspended". No se añadió un tercer valor "deleted" pese a necesitarse el concepto de baja.
- El botón Eliminar ejecuta DELETE, que archiva el registro (`archived_at`) en lugar de borrarlo.
- Suspender y Eliminar son acciones distintas: la primera es una pausa reversible sin fecha; la segunda cierra la relación dejando constancia del momento.
- **Inventario usa SQLModel + Supabase PostgreSQL** para datos operativos, mientras que **usuarios/autenticación siguen en TinyDB** (sin tabla User en SQLModel).
- **`current_stock` es campo calculado** (no almacenado): `SUM(deliveries) - SUM(consumptions)`.
- **Flujo completo de restablecimiento de contraseña**: forgot-password con rate limiting, email mediante Resend (o simulación local), reset-password con token único de un solo uso y expiración, change-password con verificación de contraseña actual.

## Resumen de arquitectura documentado en memory-bank

### techContext.md contiene:
- 13 decisiones de arquitectura documentadas con su rationale.
- 11 restricciones técnicas (campos CONTEXT, bilingüismo, stock calculado, umbrales inventario).
- 19 comandos útiles para todos los servicios, builds, tests y seeds.

### systemPattern.md contiene:
- Descripción de 3 rutas de proxy distintas (route handlers vs rewrites).
- Patrón de capa API dedicada para inventario.
- Patrón de stock reactivo.
- 5 principios arquitectónicos del proyecto (modularidad, validación en borde, inmutabilidad de inventario, autenticación desacoplada, consistencia con CONTEXT).

## Estado operacional observado
- Typecheck de raiz sin errores.
- Typecheck de uis/talent-pipeline-tracker sin errores.
- Typecheck de uis/backoffice sin errores.
- Typecheck de uis/website sin errores (no afectado por auth).
- API de proveedores auditada extremo a extremo: validaciones 422, 404, filtros, seeder idempotente y persistencia tras reiniciar uvicorn.
- Autenticación implementada en backoffice y tracker: login, registro, perfil, guard de rutas, headers Authorization, manejo 401, flujo completo de restablecimiento de contraseña.
- API de inventario funcional en Supabase PostgreSQL: 8 productos con stock calculado.
- Frontend de inventario con 4 páginas operativas, auditado contra 10 criterios — todos cumplidos.
- API de incidencias operativa en puerto 8010 con tests funcionales.
- Frontend de incidencias con 5 páginas/componentes.
- Website público (uis/website) como aplicación Next.js independiente.
- Scripts de análisis de datos (scripts/analyze.py, seed_incidents.py).
- Estructuras preparadas para escalado: agents/, skills/, workflows/, docs/, infra/.
