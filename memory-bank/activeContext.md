# Active Context

## Entregables activos en el repositorio

### Telemetría: correcciones de auditoría (2026-10-06)
- Reglas de privacidad compartidas cierran valores sensibles en campos allowlisted; timestamp ISO estricto y expiración restaurada con identidad efímera segura.
- Productor `services/api/telemetry_delivery.py` captura señales en origen y las envía por lotes sin depender del navegador. Caducidad se deduplica tras acuse del stub. Cola en memoria, sin almacenamiento analítico.
- Proxy frontend delega HTTP a `TelemetryService.server.ts`; componentes siguen usando solo `track()`.
- Verificado: 152 pruebas backend y 59 frontend; integración real de middleware → lote de cinco obligatorios + alta → stub 200. Canario de auditoría bloqueado.
- Pendientes: recorrido completo en Chromium, cuatro errores TypeScript preexistentes y persistencia/outbox futura. Reiniciar backend para activar el nuevo worker.

### Telemetría: conectividad de navegador (2026-10-06)
- Endpoints públicos loopback pasan por `/api/telemetry/events` del backoffice, evitando apuntar al localhost del operador en Codespaces. Colectores externos mantienen su URL.
- Proxy con `TELEMETRY_ENDPOINT` de servidor y soporte de backend interno mediante `SUPPLIERS_API_URL`; no reenvía cookies ni Authorization al colector.
- Verificado: 14 pruebas focalizadas y lint pasan; lote real de dos eventos responde 200 a través de Next.js. El recorrido completo de navegador de fases 3/4 sigue sin completarse.

### Telemetría: fase 1 (2026-10-06)
- Stub `POST /telemetry/events` en router propio: valida lotes y contratos del catálogo, registra solo cantidad/tipos y responde `{ "received": N }` sin persistencia.
- `TelemetryEvent` reutilizable en `services/api/telemetry.py`; configuración backend mediante `TELEMETRY_ENDPOINT`. Catálogo incluido en la imagen Docker.
- Servicio, variable pública e instrumentación frontend pendientes por indicación expresa del usuario. Verificación: 16 pruebas focalizadas pasan, sin Supabase.

### Telemetría: fase 2 (2026-10-06)
- Servicio único `uis/backoffice/lib/telemetry.ts`: cola en memoria, lotes cada 10 s/20 eventos, beacon al ocultar/cerrar y tres reintentos con backoff. Sin instrumentación de negocio.
- Sesión en memoria enlazada a auth; captura autenticada desactivada hasta recibir `telemetry_user_id` HMAC. El usuario rechazó ampliar el backend en esta fase. No enviar email, ID interno ni JWT al colector.
- Configuración de `NEXT_PUBLIC_TELEMETRY_ENDPOINT` pendiente en el archivo local bloqueado para edición. Avances documentados solo al final de `docs/telemetry/telemetry-plan.md`, después del plan original.
- Diez pruebas focalizadas pasan; tipos focalizados sin errores. Typecheck global: 11 errores ajenos; aviso lint de AuthContext confirmado en HEAD. Dependencias locales reportan 28 vulnerabilidades, sin cambios de lockfiles.

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
- **cache.py**: MemoryCache singleton con dict + time.monotonic() expiry e invalidación por prefijo.
- **main.py**: timing middleware que loggea método/ruta/status/tiempo en ms.
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
- `routes/incidents.py`: CRUD de incidencias (GET listado con filtros, POST crear, GET/PUT por ID, DELETE) con caché en GET /summary (TTL 60s) y GET / list (TTL 30s) e invalidación en los 4 write endpoints.
- **cache.py**: MemoryCache singleton para incidencias.
- **main.py**: timing middleware que loggea método/ruta/status/tiempo en ms.
- `tests/`: conftest.py, helpers.py, test_incidents.py (tests funcionales).
- Proxy en next.config.ts: `/api/incidents/*` → `http://127.0.0.1:8010/api/incidents/*`

### 9) Frontend de Incidencias (uis/backoffice)
- `/incidents` — página principal con `IncidentsAnalyzerClient` (subida de CSV y análisis).
- `/incidents/list` — listado de incidencias registradas con filtros.
- `/incidents/register` — formulario de registro de nueva incidencia.
- `/incidents/summary` — resumen/estadísticas de incidencias.
- `/incidents-manager` — página de gestión de incidencias con `IncidentsManagerClient`.
- Componentes: `IncidentListPanel`, `IncidentRegisterForm`, `IncidentSummaryPanel`, `IncidentsAnalyzerClient`, `IncidentsManagerClient`.
- **Optimización de carga**: `AnalysisResultsPanel` (~200 líneas) y `IncidentFormPanel` (~150 líneas) extraídos a archivos independientes e importados con `next/dynamic` + `ssr: false` para lazy loading.
- **Página principal optimizada**: `app/page.tsx` con 7 wrappers `useMemo` para valores derivados (denialRate, payerRates, locationNoShowRates, weeklyNoShowCost, sortedClaims, binaryIndex, linearClaim, cmeReport) que evitan recálculos en cada render.

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

### 19) Backend — Auditoría de serialización (completada)

Se realizó una auditoría exhaustiva de serialización sobre **38 endpoints** (31 de HealthCore API + 7 de Incidents API), documentada en `docs/serialization-audit.md`.

**Hallazgos iniciales:**
- 21 endpoints ✅ serializados correctamente (55%)
- 14 endpoints ⚠️ parcialmente serializados (37%) — esquemas compartidos entre listado/detalle, exposición de FK interna (`user_id`), schemas sin nombre (`dict[str,str]`)
- 3 endpoints ❌ sin serializar (8%) — raíces y análisis de incidencias sin `response_model`

**Cambios implementados (8 schemas Pydantic nuevos, 14 endpoints actualizados):**
| Schema | Propósito |
|---|---|
| `ProfilePublic` | Perfil sin `user_id` (FK interna) |
| `MessageResponse` | Mensaje genérico para auth flows |
| `SupplierListItem` | Listado ligero de proveedores (sin `notes`) |
| `AnalysisResponse` / `AnalysisSummary` / `AnalysisPercentages` | Respuesta tipada de análisis de incidentes |
| `RootResponse` (x2) | Root de descubrimiento (Main API + Incidents API) |

**Endpoints actualizados:**
- Auth: forgot/reset/change → `MessageResponse` (antes `dict[str,str]`)
- Auth/me: ahora convierte Profile → ProfilePublic (oculta `user_id`)
- Profiles: GET/PUT → `ProfilePublic`
- Suppliers: 3 listados → `SupplierListItem` (sin campo `notes`)
- Main API: Root → `RootResponse`, analyze/sample → `AnalysisResponse`
- Incidents API: Root → `RootResponse`, summary → `IncidentSummary`

**Verificación:** 180 tests pasan (113 API + 67 Incidents API). Todos los endpoints verificados via OpenAPI `/docs`.

---

### 20) Frontend — Auditoría Lighthouse y refactorización (completada)

Se ejecutó auditoría con Lighthouse sobre website (EN/ES) y backoffice, documentada en `audit/AUDIT.md`. Se aplicaron correcciones documentadas en `audit/REPORT.md`.

---

### 21) Optimización integral de caché — Frontend + Backend (completada)

Se realizó una optimización integral de caching en toda la aplicación (frontend y backend) para reducir latencia, carga en base de datos y tamaño de bundle. Todo documentado en `CACHING_REPORT.md`.

**Frontend — useMemo (página principal del backoffice):**
- 7 wrappers con `useMemo` en `uis/backoffice/app/page.tsx` para valores derivados que se computan desde listas estáticas: `denialRate`, `payerRates`, `locationNoShowRates`, `weeklyNoShowCost`, `sortedClaims`, `binaryIndex`, `linearClaim`, `cmeReport`.
- Cada `useMemo` depende de las variables que realmente necesita (ej: `[sortedClaims]` para los que usan la lista ordenada), evitando recálculos innecesarios en cada render.
- Impacto: se eliminan ~7 operaciones O(n) + 1 O(n log n) por render.

**Frontend — Lazy Loading (2 componentes):**
- `IncidentsAnalyzerClient.tsx`: `AnalysisResultsPanel` (~200 líneas, 15-20 KB) ahora se importa con `next/dynamic` y `{ ssr: false }`. Solo se descarga cuando el usuario sube un CSV y recibe resultados.
- `IncidentsManagerClient.tsx`: `IncidentFormPanel` (~150 líneas, 10-15 KB) ahora se importa con `next/dynamic` y `{ ssr: false }`. Solo se descarga cuando el usuario hace clic en "New" o "Edit".
- Ambos componentes extraídos a archivos independientes para poder ser importados dinámicamente.

**Backend — MemoryCache (ambas APIs):**
- Creado `services/api/cache.py` y `services/incidents-api/cache.py`: clase `MemoryCache` singleton con almacenamiento en `dict`, expiración por `time.monotonic()`, invalidación por prefijo de clave, y métodos `get(key)`, `set(key, value, ttl)`, `invalidate(prefix)`.
- Patrón cache-aside: check cache → hit → devolver; miss → computar → guardar en caché → devolver.
- Es una solución ligera sin dependencias externas (no Redis), con la limitación de que no persiste entre reinicios ni comparte estado entre workers.

**Backend — Caché en HealthCore API (inventario):**
- `GET /products` cacheado con clave `"inventory:products:list"`, TTL 30 segundos.
- Invalidación del prefijo `"inventory:products"` en:
  - `POST /products` (crear producto)
  - `POST /orders/inbound` (entrada de stock)
  - `POST /orders/outbound` (salida de stock)
- Justificación TTL 30s: el inventario cambia con frecuencia (consumos clínicos continuos), pero 30 segundos de desfase es aceptable para la visibilidad operativa.

**Backend — Caché en Incidents API:**
- `GET /summary` cacheado con clave `"incidents:summary"`, TTL 60 segundos. El resumen (conteos por estado/categoría/origen) no necesita ser instantáneo para un dashboard.
- `GET / list` cacheado con clave dinámica `"incidents:list:s:{status}|c:{category}|o:{origin}|b:{branch}"`, TTL 30 segundos. Cada combinación de filtros tiene su propia entrada en caché.
- Invalidación de ambos prefijos (`"incidents:summary"` e `"incidents:list"`) en:
  - `POST /` (crear incidencia)
  - `PUT /{id}` (actualizar)
  - `PATCH /{id}/status` (cambiar estado)
  - `DELETE /{id}` (eliminar)

**Bugs encontrados y corregidos durante la auditoría:**
1. **Dead code en `get_summary()`**: la línea `cache.set(...)` estaba después de `return`, por lo que NUNCA se guardaba el resumen en caché. Ningún test lo detectó porque TinyDB es rápido en datasets pequeños.
2. **Invalidación incompleta**: `_invalidate_summary_cache()` solo limpiaba `"incidents:summary"`, pero no `"incidents:list"`. Al crear una incidencia, el listado con filtros seguía mostrando datos obsoletos.

**Timing middleware (ambas APIs):**
- Agregado middleware en `main.py` de ambas APIs que registra: método, ruta, código de estado y tiempo de respuesta en milisegundos.
- Las métricas se loggean a consola con el formato: `"METHOD /path → 200 (12.34ms)"`.
- Sirve para identificar los próximos cuellos de botella con datos reales.

**Pruebas y verificación:**
- 82/82 tests pasan (sin regresiones).
- 0 errores de TypeScript en backoffice.
- 0 errores de Python en ambas APIs.
- Documentación completa en `CACHING_REPORT.md` (679 líneas) con:
  - Analogías para lectores no técnicos (post-it, restaurante, maleta, supermercado)
  - Tablas "Antes/Después" por cada decisión
  - Desglose de costes por operación ("Traducción a números")
  - Análisis de riesgos por trade-off ("¿Qué tan grave es?")
  - Justificación detallada de cada TTL
  - Sección "¿Qué no se cacheó y por qué?" con análisis por endpoint
  - Glosario de 12 términos técnicos en lenguaje sencillo

**Resultados Lighthouse iniciales:**
| Aplicación | Performance | Accessibility | Best Practices | SEO |
|---|---|---|---|---|
| Website (EN) | 97 | 100 | 77 | 63 |
| Website (ES) | 83 | 100 | 77 | 63 |
| Backoffice | 80 | 96 | 100 | 60 |

**Mejoras implementadas:**

1. **Extracción de tipos y constantes de incidencias (Caso 1):**
   - Creados `types/incident.ts` y `lib/incidents.ts`
   - Eliminadas ~255 líneas de tipos/constantes duplicadas en 4 componentes
   - Unificados `BRANCHES` / `VALID_BRANCHES` como `BRANCH_OPTIONS`
   - Lighthouse: Website EN 97→98, Website ES 83→98

2. **Consolidación de cliente HTTP (Caso 2):**
   - Creado `lib/httpClient.ts` como único cliente HTTP del backoffice
   - Eliminados `authHttpClient.ts` (~75 líneas) y ~120 líneas de HTTP duplicado en `suppliersApi` e `inventoryApi`
   - Unificado manejo de 401, extracción de errores, `ApiError`
   - Lighthouse: sin cambios (refactorización interna)

3. **Reducción de JavaScript no utilizado (Mejora 1):**
   - Habilitado `experimental.optimizePackageImports` en website y backoffice
   - Instalado `@next/bundle-analyzer` + script `analyze` en ambos proyectos
   - Lighthouse: sin cambios inmediatos (medidas preventivas)

4. **Optimización de LCP (Mejora 2):**
   - Añadida prop `priority` a imagen hero en `LandingPage.tsx`
   - Beneficia las 3 rutas del website (`, `/en`, `/es`)
   - Lighthouse: Website EN 98→99

5. **Abstracción de estados de UI (Mejora 6):**
   - Creados `LoadingSpinner`, `ErrorMessage`, `EmptyState` en `components/ui/`
   - Refactorizados 5 componentes del backoffice (~90 líneas eliminadas)
   - Lighthouse: Website ES 98→99, Backoffice 80→81

**Mejoras descartadas:**
- Mejora 5 (SEO/noindex): Correcto y deseable en proyecto personal
- Mejora 7 (minificación): Next.js ya minifica en producción

**Validación:** TypeScript sin errores nuevos en todos los cambios. Build de website exitoso. Backoffice tiene error preexistente de module resolution con `../src/` (no relacionado con los cambios).
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
