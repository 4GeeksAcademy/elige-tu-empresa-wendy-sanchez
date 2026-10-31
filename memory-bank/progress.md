# Progress

## Estado actual del desarrollo

### Modelo de pronóstico de ventas — Regresión con XGBoost (2026-10-31)
- **Completado**: pipeline completo de pronóstico de ingresos mensuales en `scripts/sales_forecast/{data,metrics,model,visualize}.py` con entrypoint `scripts/train_sales_forecast.py` (7 pasos: carga → validación → features → split → entrenamiento → métricas → gráfico).
- **Completado**: split temporal estricto 8 años/2 años — entrenamiento 2016-01..2023-12 (96 meses − 12 de warm-up = 84 efectivos) y prueba 2024-01..2025-12 (24 meses que el modelo nunca vio). Invariantes verificados en código con `_assert_split_invariants()`.
- **Completado**: features causales solo con información pasada — `rev_lag_1`, `rev_lag_2`, `rev_lag_12`, `rev_ma_3`, `rev_min_12`, `rev_max_12`, `rev_std_12`, `month_num`, `season`, `trend_index`, `visits_count`, `avg_revenue_per_visit_usd`. `StandardScaler` ajustado SOLO con el conjunto de entrenamiento.
- **Completado**: XGBoost regularizado (`max_depth=4`, `lr=0.03`, `gamma=0.5`, `reg_alpha=0.5`, `reg_lambda=2.0`, `random_state=42`) con justificación escrita frente a Random Forest.
- **Completado**: las 4 métricas exigidas calculadas sobre el conjunto de prueba — MSE 24.754.766.765,26 USD² (= 5,6032 % del ingreso medio mensual al cuadrado), PSI de nivel 6,0325 y PSI de crecimiento ajustado 0,2718, Gini predictivo 0,8261, K2/R² 0,8044. Añadida MAPE 3,646 % (peor mes 8,849 %).
- **Completado**: visualización con banda de variabilidad ±1,96σ = ±$270.451 (σ = $137.985 calculada como RMS de los RMSE walk-forward). Cobertura empírica 21/24 meses (87,5 %).
- **Completado**: validación walk-forward que reentrena por año (RMSE 2024 = $138.528, 2025 = $137.440) usando solo datos anteriores a cada año.
- **Completado**: artefactos exportados a `reports/sales_forecast/metrics.json` y `forecast_vs_real.png`; documentación íntegra en `predic-ventas-model-regresion.md`.
- **Tests**: `tests/pipelines/test_sales_forecast_split.py` — **14/14 en verde** (6 de split/anti-fuga, 5 de invariantes del dataset, 2 de regresión de nombres de features, 1 de predicción fuera de muestra).
- **Auditoría (2026-10-31)**: **7/7 acceptance criteria ✅** verificados en ejecución con recálculo independiente de las métricas (no se confió en la documentación). Hallazgos corregidos: (a) `test_escalado_ajustado_solo_con_entrenamiento` era tautológico → reemplazado por reconstrucción exacta `(x−μ_train)/σ_train` comparada contra la hipótesis con fuga, **validado con mutation test** (inyectar `fit(train+test)` hace fallar el test); (b) `rev_ma_12` era un máximo rodante con nombre de media móvil → renombrado a `rev_max_12`, `rev_mi_12` → `rev_min_12`; (c) docstring decía "~107 filas" → corregido a 84; (d) `year_num` era código muerto → eliminado. Métricas reproducidas idénticas bit a bit tras el refactor.
- **Hallazgo documentado, no corregido (correcto por diseño)**: el PSI de nivel es alto (6,03) porque el ingreso medio crece de $2,81 M (train) a $3,37 M (test). No es una fuga ni un fallo del modelo: en una serie con crecimiento estructural el PSI de nivel mide el crecimiento. Se añadió el PSI de crecimiento ajustado (0,2718 → "moderado") y se redujeron los bins de 10 a 5 porque con solo 12 puntos de crecimiento los bins de 10 dejaban ~1 observación por bin y el ruido inflaba el valor.
- **Branch**: `feature/sales-forecast-model`. `CONTEXT.md` **NO modificado** (ruta protegida); el script valida contra él pero no lo edita.

### Cola de Tareas Asíncronas — Redis + Celery (2026-10-24)
- **Completado**: Sistema de cola de tareas asíncronas para desacoplar operaciones pesadas de la API usando Redis como broker y Celery como framework de tareas.
- **Completado**: `services/celery_app.py` — instancia Celery con Redis como broker y result backend, tarea `analyze_incidents_csv`, clase base `HealthCoreTask` con DLQ automática en `on_failure`.
- **Completado**: Configuración de reintentos (`autoretry_for`, `max_retries=3`, `retry_backoff=True`, `retry_jitter=True`), colas (`healthcore.default`, `healthcore.dlq`), señales Celery (`task_success`, `task_failure`, `task_retry`, `task_revoked`).
- **Completado**: Dead Letter Queue con TinyDB persistida en `data/process/task_dlq.json` — registro automático tras agotar reintentos con `task_id`, `task_name`, `attempt`, `error`, `exc_type`, `timestamp`.
- **Completado**: Endpoint `POST /api/incidents/analyze` refactorizado de síncrono a asíncrono — ahora responde 202 Accepted con `task_id` y encola en Celery. Header `Location: /tasks/{task_id}`.
- **Completado**: Endpoint `GET /tasks/{task_id}` — consulta el estado de la tarea (`pending | started | success | failure`), resultado, error, y entrada DLQ si falló.
- **Completado**: Infraestructura Docker — 3 nuevos servicios en `docker-compose.yml`: `redis` (Redis 7-alpine con AOF y noeviction), `flower` (mher/flower:2.0 con monitoreo en :5555), `celery-worker` (concurrency=4, flag -E para eventos, red healthcore-net).
- **Auditoría**: **10/10 criterios ✅** — Redis responde PING, encolado en 29.61ms media, estados correctos, reintentos con backoff, DLQ funcional, worker conectado, payloads ligeros, Flower accesible.
- **Archivos**: `services/celery_app.py`, `services/api/routes/tasks.py`, `services/api/main.py` (endpoint async), `docker-compose.yml` (redis, flower, celery-worker).

### Proceso de segundo plano — Job nocturno de telemetría (2026-10-22)
- **Completado**: `job_runs` (orquestación nocturna) creado como capa propia, distinta de `reporting.pipeline_runs` (ETL Hito 6). DDL `data/migrations/0002_job_runs.sql` + auto-migración idempotente.
- **Completado**: `services/job_runner.py` (CONTROL DE ESTADO: estados + lock atómico = `processing` + helpers `has_processing_lock`/`has_completed_for_date` + `log_result`), `services/nightly/nightly_service.py` (orquestación: export CSV → subprocess pipeline → registros), `scripts/nightly_export.py` (CLI con flags `--skip-pipeline`, `--force`, `--target-date`, `--list`, `--dry-run`).
- **Completado**: idempotencia por día (noop si `completed`), aborto silencioso si otra instancia tiene el lock, `failed` con `error_message` ante excepción, reintento `failed → pending`.
- **Completado (spec #5 — Disparador)**: `background-processes.md` con decisión cron `0 2 * * *`, instalación del crontab, opción de contenedor scheduler dedicado (recomendada en prod) y prohibición explícita de APScheduler/@repeat_every/lifespan. `TARGET_DATE` documentada como var opcional para pruebas.
- **Completado (spec #6 — Observabilidad)**: logger estable `healthcore.nightly`, formato normalizado `event=... job=nightly_export status=... ts=...` vía `log_result()`; INFO para inicio/fin/omisión por duplicado y ERROR para excepciones con traceback. Tests con `caplog` añadidos.
- **Tests**: **30/30** pasan (`.venv-nightly/bin/python -m pytest tests/nightly -q`).
- **Auditoría del proceso — 10/10 criterios ✅**: análisis estático (AST: sin imports de fastapi/uvicorn/starlette/apscheduler en los módulos del job) + demostración en vivo `scripts/_audit_hito7_demo.py` (Dos instancias CLI reales a la vez contra una BD SQLite compartida). Resultados: C3 una instancia completa y la otra hace noop/aborta; C3b lock retenido → aborted; C4 idempotencia → noop_export; C5 fallo forzado → failed con error_message (sin estados processing zombi); C6 CSV `telemetry_YYYY-MM-DD.csv` en `data/raw/` con cabeceras timestamp/event_type/tags y contenido correcto. Demo reproducible (`exit=0`) y limpia su residuo de `data/raw/`.
- **Hallazgos y soluciones (documentados en `background-processes.md` §11)**: (1) reintento tras fallo: `mark_processing` no permitía `failed→pending`, se añadió `reset_failed_to_pending` atómico solo desde `failed`; (2) módulo de control de estado movido a `services/job_runner.py` (spec); (3) logger estable `healthcore.nightly` + `log_result()` (sin `logger.exception` crudo) para pasar los tests `caplog`; (4) pipeline real del Hito 6 es `python -m data.pipelines.runner` (no `telemetry_kpi_daily`); (5) concurrencia verificada en vivo.
- **Completado (2026-10-22, re-etiquetado)**: aclarado que este proyecto es un **proceso de segundo plano intermedio** (entre el hito 6 y un hito futuro), NO "Hito 7". Eliminadas las referencias a "Hito 7" en `background-processes.md`, `memory-bank/*.md`, `services/job_runner.py`, `services/nightly/__init__.py`, `services/nightly/nightly_service.py`, `tests/nightly/*.py` y `scripts/_audit_hito7_demo.py` → "proceso de segundo plano". **Borrado `AUDITORIA_HITO7.md`** (redundante con `background-processes.md` §11). Solo se corrigieron textos; los nombres de archivo NO se renombraron (`scripts/_audit_hito7_demo.py` conserva su nombre). Refactoring de docstrings sin impacto funcional: 30/30 tests siguen en verde.
- **Completado (supabase humo - solo conexión, 2026-10-22)**: `DATABASE_URL` en `.env` raíz; conexión de SOLO LECTURA a Supabase verificada (Postgres 17.6, pooler eu-west-1, 31 filas en `telemetry_events` entre 2026-10-04 y 2026-10-11, pico 2026-10-10=12). No se escribió nada (decisión del usuario). Instalado `psycopg` v3 + `psycopg2-binary` en `.venv-nightly` para el driver. `job_runs`/`schema_migrations` aún inexistentes en Supabase — el job los auto-crearía. Para futuro humo completo: `--target-date 2026-10-10`.
- **Completado (humo completo Supabase, 2026-10-22)**: corrida real contra Supabase con `--skip-pipeline --target-date 2026-10-10`. OUTCOME `completed`, **12 filas** exportadas a `data/raw/telemetry_2026-10-10.csv` (13 líneas: cabecera `timestamp,event_type,tags` + 12 eventos con tags JSON). Fila en `job_runs`: status `completed`, `exported_rows=12`, `csv_path` correcto, `created_at` 2026-10-22 20:59:44 UTC. **Idempotencia verificada**: 2ª corrida → `noop_export`, exit 0. **Punto clave**: la rama **Postgres** del código (BIGSERIAL, `now()`, UNIQUE(job_name,target_date), CHECK status) quedó ejecutada contra Postgres real por primera vez. **Hallazgo menor**: `schema_migrations` queda count 0 en Postgres — `_ensure_schema_postgres` crea las tablas con DDL hardcodeado y NO inserta versiones (SQLite sí itera `_MIGRATIONS`). No bloquea; pendiente decidir documentarlo o corregirlo.
- **Pendiente**: instalar crontab en el entorno real (aún no instalado), decidir cómo tratar `schema_migrations` vacío en Postgres (hallazgo del humo), seguimiento post-deploy en `job_runs`. `npm run typecheck` pendiente de ejecutar (AGENTS.md). **NO commitear** (usuario sigue iterando).

### Telemetría: brechas de auditoría corregidas (2026-10-06)
- Privacidad de valores y formato temporal reforzados en ambas fronteras; expiración sin HMAC válido deja de perderse.
- Entrega de hechos obligatorios independiente del cliente: cola backend, lotes, reintentos y deduplicación de caducidad posterior a recepción confirmada; el stub no almacena eventos.
- 152 pruebas backend y 59 frontend pasan. Tipos focalizados y lint correctos; quedan cuatro errores globales ajenos y verificación integral de navegador pendiente. Detalle añadido al final del plan de telemetría.

### Telemetría: fase 1 completada (2026-10-06)
- Router receptor y modelo Pydantic cerrados, validación contra `docs/telemetry/event-schemas.json`, logs mínimos y ninguna escritura en base de datos.
- `TELEMETRY_ENDPOINT` leído al iniciar; catálogo empaquetado para Docker. 16 pruebas focalizadas pasan, incluidos los cinco contratos obligatorios y el montaje en la app real.
- No se implementaron servicio ni captura frontend. Validación ejecutada con un entorno Python temporal porque `uv` y `pytest` no estaban instalados en el contenedor.

### Telemetría: fase 2 implementada con dependencias pendientes (2026-10-06)
- Servicio frontend con API única `track()`, envelope automático, contratos compartidos, cola acotada, envío por lotes, beacon y tres reintentos. Integración de sesión sin instrumentación de eventos de negocio.
- Pendientes: configurar URL pública en el archivo local bloqueado y recibir seudónimo HMAC de autenticación. No se amplió el backend por decisión expresa del usuario.
- Diez pruebas focalizadas, las 46 pruebas del backoffice y tipos del servicio pasan. El typecheck global mantiene 11 errores ajenos al cambio y lint mantiene un aviso previo de AuthContext. Detalle al final del plan de telemetría.

### Telemetría: Fase 5 — Autenticación funcional para backoffice (2026-10-11)
- **Problema detectado**: TinyDB sin usuarios (`data/process/suppliers_db.json` en `.gitignore`, nunca ejecutado seed). API principal (`main.py`) no arranca por SQLModel + Python 3.14. Servidor standalone sin auth.
- **Seed de usuarios**: `services/telemetry/seed_auth_users.py` — script autónomo que crea `admin@healthcore.com` / `adminpass456` y `test@healthcore.com` / `securepassword123`.
- **Módulo auth standalone**: `services/telemetry/auth_standalone.py` — bcrypt, JWT (jose), consultas TinyDB. Sin dependencia de `services/api/`.
- **Endpoints en `server_standalone.py`**: `POST /auth/login` (login+JWT), `GET /auth/me` (perfil+rol+telemetry_user_id).
- **Cadena completa verificada**: Navegador → Next.js proxy → `localhost:8000/auth/*` → 200 OK.
- **Archivos**: `seed_auth_users.py` (creado), `auth_standalone.py` (creado), `server_standalone.py` (modificado), `services/api/.env` (modificado, JWT_SECRET_KEY).

### Telemetría: Fase 4 — Dashboard de telemetría en backoffice (2026-10-11)
- **Página creada**: `uis/backoffice/app/telemetry/page.tsx` — 5 paneles visuales (events_per_day, error_rate_by_type, latency_percentiles_by_route, event_type_distribution, auth_failure_rate).
- **Selector de fechas**: campos datetime-local que recargan el reporte vía `/api/telemetry/report`.
- **Proxy**: rewrite en `next.config.ts`; route handler bugado eliminado.
- **Navegación**: enlace "Telemetry" en BackofficeHeader.
- **Datos de prueba**: 100 eventos en Supabase (14 días, 5 tipos).

### Telemetría: Fase 3 — auth_failure_rate_by_day (2026-10-11)
- **Función creada**: `auth_failure_rate_by_day()` en `services/telemetry/analysis.py`.
- **SQL**: filtra `auth_login_failed` + `auth_login_succeeded`.
- **Pandas**: groupby día → pivot → tasa de fallo.
- **Integrada en `run_all()`**: servida automáticamente en `GET /telemetry/report`.
- **Auditoría 10/10**: todos los acceptance criteria cumplidos.

### Telemetría: control channel refactorizado y 422 corregido (2026-10-06)
- **Refactor del control channel**: `TelemetryService.control.ts` tenía fetch pipeline independiente a `/api/telemetry/control`, violando el principio de "única `track()`". Se refactorizó a `recordTelemetryControl()` que valida propiedades y llama a `track()`. Todos los eventos frontend van por `/api/telemetry/events`.
- **3 tests actualizados**: expectativas cambiadas de `"/api/telemetry/control"` a `"/api/telemetry/events"`. 2 de 3 correcciones pasan.
- **Bug 422 resuelto**: El backend de puerto 8000 (PID 42927) tenía código desactualizado desde las 18:01 — al reiniciarlo con `--reload` y recargar el backoffice, los eventos reales del navegador responden 200 OK.
- **Backend dual**: Se descubrió que había dos procesos FastAPI (puertos 8000 y 8400). Se mataron ambos y se reinició solo el puerto 8000 con el código correcto y `--reload`.
- **Verificado**: POST real a `/api/telemetry/events` vía proxy devuelve `{"received":1}` con 200.
- **Pendientes**: 1 test de reintentos (retries three times) sigue fallando — espera 4 llamadas de fetch pero recibe 12; requiere depuración adicional del mock de fetch.
- **Documentación**: `telemetry-plan.md` actualizado con el nuevo diseño del canal de control; `memory-bank` sincronizado con estos cambios.

### Completado
1. Hito web de HealthCore implementado en EN/ES:
- Landing con contenido corporativo, secciones requeridas y marcado Schema.org.
- Formulario de consulta con campos y validaciones alineadas al contexto.
- Mensajes de error y éxito visibles para usuario.

2. Fundamentos TypeScript implementados en src/:
- Modelado de entidades principales.
- Filtros, ordenamientos, busquedas lineal/binaria.
- Agregaciones de denegaciones y no-shows.
- Reportes CME y validaciones de dominio.

3. Talent Pipeline Tracker funcional en Next.js:
- Listado con filtros y búsqueda vía query params sin recarga completa.
- Detalle de candidatura por ID.
- Actualización de estado y etapa con PATCH.
- Gestión de notas (listar, crear, eliminar).
- Formularios de creación (POST) y edición (PUT).
- Autenticación JWT con login, registro, perfil, guard de rutas.

4. Salud técnica actual:
- npm run typecheck (raiz): OK.
- npm run typecheck (uis/talent-pipeline-tracker): OK.
- npm run typecheck y npm run lint (uis/backoffice): OK.
- npm run typecheck (uis/website): OK.
- **Tests unitarios (uis/backoffice)**: 11/11 pasan con `npx jest`.

5. Directorio de Proveedores (FastAPI + TinyDB + Pydantic):
- Modelos Pydantic con enums de status/categoría/país y coherencia moneda-país.
- Seeder idempotente con los 15 proveedores del CONTEXT (`uv run seed`).
- Endpoints POST/GET/GET id/PATCH rate/PATCH status/DELETE con 201/200/404/422 coherentes.
- DELETE es baja lógica: mantiene `status` en los dos valores del CONTEXT y marca `archived_at`.
- Página /suppliers en uis/backoffice con filtros sin recarga, alta validada en cliente, edición de tarifa inline y acciones Suspender/Activar y Eliminar por fila.
- Tres estados visuales diferenciados: Activo (verde), Suspendido (ámbar) y Eliminado (rojo, con fecha de baja).
- Auditoría ejecutada: 15/15 checks de backend y 11/11 de frontend renderizado; persistencia verificada reiniciando uvicorn.

6. Autenticación completa (API + backoffice + tracker):
- Login con JWT (Access token 30 min), registro con creación de perfil.
- Flujo completo de recuperación de contraseña: forgot-password con rate limiting (5 intentos/60 min), reset-password con token único de un solo uso, change-password con verificación de contraseña actual.
- Auditoría de eventos de restablecimiento en TinyDB.
- Envío de emails mediante Resend (simulado en consola local).
- Roles USER y ADMIN con protección de rutas.
- Tests automatizados: login, forgot/reset/change password, /me, security, user_service (9 archivos de test).

7. Sistema de Incidencias (API FastAPI independiente puerto 8010):
- CRUD completo de incidencias con filtros (categoría, origen, estado, clínica, fechas).
- Categorías: appointment, billing, clinical_equipment, compliance_breach, patient_experience.
- Orígenes: customer, staff, system, supplier.
- Tests funcionales en services/incidents-api/tests/.
- Frontend: 5 páginas (analyzer, list, register, summary, manager).
- Análisis de CSV legacy mediante incidents_analysis.py.

8. Módulo de Inventario (FastAPI + SQLModel + Supabase PostgreSQL + Frontend):
- 6 endpoints REST bajo /inventory con autenticación JWT.
- Modelos SQLModel: MedicalSupply, SupplyDelivery, SupplyConsumption.
- Stock siempre calculado como neto de entradas menos salidas.
- Rechazo de consumos con stock insuficiente (HTTP 400 con mensaje descriptivo).
- Seed data: 8 productos con stock calculado en Supabase.
- Frontend: 4 páginas protegidas (productos con colores, entrada, salida con stock reactivo, historial).
- Auditoría completada: 10/10 acceptance criteria cumplidos.
- Capa API dedicada (inventoryApi.ts) sin fetch directo en componentes.
- Proxy vía rewrites de Next.js (/api/inventory/* → localhost:8000).

9. Arquitectura dual de BD y APIs documentada en techContext.md:
- TinyDB para usuarios/auth/proveedores, Supabase PostgreSQL para inventario.
- Dos APIs separadas: principal (8000) e incidencias (8010).
- Dos estrategias de proxy: route handlers (auth/suppliers) y rewrites (inventario/incidencias).
- Capa API dedicada para inventario (inventoryApi.ts).
- Stock reactivo en frontend al seleccionar producto en formulario de salida.
- Comandos documentados para todos los servicios, builds y tests.

10. **Dockerización completa del monorepo para desarrollo**:
- `docker-compose.yml` en raíz con 3 servicios (uis, backend, incidents-backend) bajo red `healthcore-net`.
- `uis/Dockerfile` multi-etapa (Node 22 Alpine) para website + backoffice.
- `services/Dockerfile` (Python 3.12-slim + uv) para ambos backends FastAPI.
- `uis/start.sh` y `services/entrypoint.sh` como entrypoints dinámicos.
- `.dockerignore` en raíz, uis/ y services/ para optimizar contexto de build.
- Build exitoso verificado para las 3 imágenes.
- URLs actualizadas en route handlers, rewrites y `.env` para usar nombres Docker.
- Bug corregido: `INCIDENTS_API_URL` apuntaba a `backend:8010` → corregido a `backend:8000`.
- Dependencias faltantes añadidas a `services/api/requirements.txt` (sqlmodel, psycopg2-binary).
- `.gitignore` actualizado con `.env.local` y `.env.*.local`.

11. **Configuración de Jest y TypeScript para tests del backoffice**:
- `tsconfig.test.json` creado con `types: ["jest", "node"]`.
- `jest.config.ts` actualizado para usar `tsconfig.test.json`.
- `node_modules` instalados localmente en `uis/backoffice/`.
- `__tests__` excluido del `tsconfig.json` principal.
- 45 errores iniciales de TypeScript en `suppliersProxy.test.ts` resueltos.
- Tests ejecutándose correctamente: 11/11 passed (0.723s).

12. **Correcciones runtime (docker compose up)**:
- **Backend (8000) — Supabase graceful skip**: `DATABASE_URL` vacío provocaba crash en `init_supabase_schema()`. Solucionado con verificación `if not DATABASE_URL: logger.info(...); return`.
- **Backoffice (3001) — Module not found**: Turbopack no resuelve imports fuera del directorio del proyecto (`../../../src/...`). Solucionado montando `./src` dentro de `uis/backoffice/src` en docker-compose.yml y cambiando imports a `../src/...`.
- **Website (3000) — Imágenes rotas**: Next.js intenta optimizar imágenes descargándolas de Unsplash en el servidor, el contenedor no resuelve DNS externo. Solucionado con `images: { unoptimized: true }` en website/next.config.ts.
- **Verificación final**: los 4 servicios responden 200 OK (website:3000, backoffice:3001, backend:8000/docs, incidents-backend:8010). Imágenes visibles en website.

13. **Backend — Auditoría de serialización (completada)**:
- Auditoría de 38 endpoints (31 HealthCore API + 7 Incidents API), documentada en `docs/serialization-audit.md`.
- 8 nuevos schemas Pydantic creados: `ProfilePublic`, `MessageResponse`, `SupplierListItem`, `AnalysisResponse`, `AnalysisSummary`, `AnalysisPercentages`, `RootResponse` (x2).
- 14 endpoints actualizados con `response_model` explícito (auth, profiles, suppliers, root, analyze, summary).
- 180 tests pasan (113 API + 67 Incidents API) sin regresiones.
- Verificación via OpenAPI `/docs` de ambos servicios — todos los endpoints muestran schemas explícitos.
- Checklist de cumplimiento final: 7/7 ítems completados.

14. **Frontend — Auditoría Lighthouse y refactorización (completada)**:
- Auditoría con Lighthouse sobre website (EN/ES) y backoffice, documentada en `audit/AUDIT.md`.
- Correcciones aplicadas documentadas en `audit/REPORT.md`.
- Extracción de tipos/constantes de incidencias: eliminadas ~255 líneas duplicadas en 4 componentes.
- Consolidación de cliente HTTP: creado `lib/httpClient.ts`, eliminado `authHttpClient.ts`, ~195 líneas de HTTP duplicado eliminadas.
- Optimización JS: habilitado `optimizePackageImports` en website y backoffice.
- Optimización LCP: añadida prop `priority` a imagen hero en LandingPage.
- Abstracción de estados UI: creados `LoadingSpinner`, `ErrorMessage`, `EmptyState` (~90 líneas eliminadas en 5 componentes).
- Resultado Lighthouse final: Website EN 97→99, Website ES 83→99, Backoffice 80→81.

---

## Riesgos o brechas potenciales
- No hay pruebas automatizadas persistidas para la API de proveedores (la auditoría se ejecutó con scripts ad hoc).
- Falta verificar formalmente métricas de rendimiento (PageSpeed) en URL pública.
- README del tracker aun es plantilla genérica de Next.js, no documenta flujo de negocio/API.
- No se observan pruebas automatizadas visibles para UI ni utilidades TS en este barrido.
- **Inventario**: no hay tests automatizados para la API de inventario (solo se auditó manualmente contra 10 criterios).
- **Incidencias**: los tests de incidents-api existen pero no se sabe si están integrados en un pipeline CI.
- **Website público**: no se ha verificado su estado de build o despliegue.
- **Dependencia de Supabase**: la API de inventario depende de una conexión externa a Supabase. Si la conexión falla, todo el módulo de inventario queda inoperativo.
- **Variables de entorno**: authProxy.ts depende de SUPPLIERS_API_URL / INCIDENTS_API_URL que pueden no estar definidas (fallback a `http://backend:8000`).

15. **Optimización integral de caché (completada)**:
- Documentado exhaustivamente en `CACHING_REPORT.md` (679 líneas) con análisis, decisiones, trade-offs, bugs encontrados y glosario en lenguaje sencillo.
- **Frontend — useMemo**: 7 wrappers en `app/page.tsx` para valores derivados (denialRate, payerRates, locationNoShowRates, weeklyNoShowCost, sortedClaims, binaryIndex, linearClaim, cmeReport). Elimina ~7 operaciones O(n) + 1 O(n log n) por render.
- **Frontend — Lazy Loading (2 componentes)**: `AnalysisResultsPanel` y `IncidentFormPanel` extraídos a archivos independientes e importados con `next/dynamic`. Ahorro de ~25-35 KB en bundle inicial combinado.
- **Backend — MemoryCache**: Clase singleton con dict + `time.monotonic()` expiry, invalidación por prefijo. Implementada en ambas APIs (services/api/cache.py y services/incidents-api/cache.py).
- **Backend — HealthCore API**: `GET /products` cacheado TTL 30s, invalidación en 3 write endpoints (create_product, create_inbound_order, create_outbound_order).
- **Backend — Incidents API**: `GET /summary` cacheado TTL 60s, `GET / list` cacheado TTL 30s con clave por filtros. Invalidación en 4 write endpoints (create, update, update_status, delete).
- **Timing middleware**: implementado en ambas APIs (main.py) — loggea método, ruta, status y tiempo en ms para identificar cuellos de botella futuros.
- **Bugs corregidos**: (1) dead code en `get_summary()` — `cache.set()` después de `return` impedía cachear el resumen; (2) invalidación incompleta — `_invalidate_summary_cache()` no limpiaba prefijo `"incidents:list"`.
- **Verificación**: 82/82 tests pasan, 0 errores Python/TypeScript, documentación completa en CACHING_REPORT.md con analogías, tablas Antes/Después y glosario no-técnico.

---

16. **Pipeline de Reporting Mensual — Supply Performance (completado — Oct 2026)**:
- **Auth Standalone (`services/api/auth_standalone.py`)**: Servidor FastAPI ligero (puerto 8000) que provee `POST /auth/login` y `GET /auth/me` usando bcrypt + python-jose + TinyDB. No depende de SQLModel (evita crash Python 3.14). Token JWT 24h. Credenciales: `admin@healthcore.com` / `adminpass456`, `test@healthcore.com` / `securepassword123`.
- **Reporting API (`services/reporting/`)**: API FastAPI independiente (puerto 8001) con 3 endpoints JWT-protegidos para KPI mensuales, consulta de última ejecución y disparo manual del pipeline.
- **Pipeline de datos (`data/pipelines/`)**: Diseño Prefect 3.8.8 (extract → transform → load) con flows, runner y run_store.
- **Dashboard Reporting**: Página `uis/backoffice/app/reporting/page.tsx` con tabla de KPIs, protegida por JWT, proxy en next.config.ts.
- **Demo Data**: 10 filas insertadas en `reporting.monthly_clinic_supply_performance` (Oct 2026, 10 clínicas, $13,251.25 total).
- **Clinic Name Mapping**: Diccionario `CLINIC_NAMES` en reporting.py mapea `clinic-001` → `"Central — Austin Main Clinic"`...`clinic-010` → `"Atlanta Midtown"`. Mostrado en frontend como `{clinic.clinic_name || clinic.clinic_id}`.
- **Bugs corregidos en pipeline**:
  1. `transform.py`: int clinic_id crasheaba `.strip()` — añadido `str()` antes de .strip().
  2. `flows.py`: Prefect 3.x no soporta `.submit()` en `@flow` — cambiado a try/except direct call.
  3. `queries.py`: `DISTINCT ON` devolvía 1 fila — cambiado a subquery `WHERE month_start = (SELECT MAX(...))`.
  4. Supabase PgBouncer: prepared statement cache conflict — workaround con raw SQL.
- **Fix JWT Frontend**: `page.tsx` reemplazó `fetch(url)` por `request<T>(url)` (httpClient.ts) para incluir Bearer token.

17. **E2E Integration — Cadena completa verificada**:
   - Login → POST `/auth/login` → JWT token ✅
   - Token → GET `/auth/me` → perfil + rol ✅
   - Token → GET `/reporting/monthly-clinic-supply-performance` → 10 clinics, $13,251.25 ✅
   - Dashboard reporting → login → tabla con KPIs y nombres de clínica ✅
   - 38/38 backend tests passing ✅
   - 61/62 frontend tests passing (1 pre-existing telemetry timeout) ✅

## Riesgos o brechas potenciales
- No hay pruebas automatizadas persistidas para la API de proveedores (la auditoría se ejecutó con scripts ad hoc).
- Falta verificar formalmente métricas de rendimiento (PageSpeed) en URL pública.
- README del tracker aun es plantilla genérica de Next.js, no documenta flujo de negocio/API.
- No se observan pruebas automatizadas visibles para UI ni utilidades TS en este barrido.
- **Inventario**: no hay tests automatizados para la API de inventario (solo se auditó manualmente contra 10 criterios).
- **Incidencias**: los tests de incidents-api existen pero no se sabe si están integrados en un pipeline CI.
- **Website público**: no se ha verificado su estado de build o despliegue.
- **Dependencia de Supabase**: la API de inventario depende de una conexión externa a Supabase. Si la conexión falla, todo el módulo de inventario queda inoperativo.
- **Variables de entorno**: authProxy.ts depende de SUPPLIERS_API_URL / INCIDENTS_API_URL que pueden no estar definidas (fallback a `http://backend:8000`).
- **Caché en memoria**: Si la aplicación escala a múltiples workers, cada worker tendrá su propia caché en memoria sin compartir estado. Para multi-worker se debe migrar a Redis.
- **Python 3.14 + SQLModel 0.0.48**: `TypeError: issubclass()` impide que la API principal arranque. Solución temporal: servicios standalone (auth_standalone.py, reporting API, telemetry server). No hay solución compatible con SQLModel en Python 3.14.
- **Prefect 3.8.8**: `@flow` objects no tienen `.submit()`. Las flows deben llamarse directamente. Documentado en flows.py con try/except.
- **Supabase PgBouncer**: Prepared statement cache conflict en queries repetidas. Usar raw SQL en lugar de named parameters donde sea necesario.
- **Pronóstico de ventas**: el PSI de nivel es estructuralmente alto (6,03) por el crecimiento del negocio. Si alguien lo lee en aislamiento lo interpretará como un modelo roto; siempre hay que leerlo junto al PSI de crecimiento ajustado (0,2718).
- **Pronóstico de ventas**: la banda de ±1,96σ cubre 21/24 meses (87,5 %), por debajo del 95 % nominal. Con n=24 la estimación de σ es ruidosa; la banda es una guía de magnitud, no un intervalo de confianza formal.
- **Pronóstico de ventas**: el modelo no conoce variables exógenas (campañas, aperturas de clínica, cambios de tarifa). Su error explotará si el negocio cambia de régimen.
- **Pronóstico de ventas**: el pipeline se ejecuta como script, no hay endpoint ni dashboard; la reutilización desde otro servicio requeriría exponer `train_sales_model()` detrás de una API.

## Próximos pasos previstos
1. Documentar el tracker con README especifico de dominio (setup, variables de entorno, endpoints, flujo funcional).
2. Incorporar pruebas unitarias para utilidades de src/ y validaciones del tracker.
3. Persistir como suite de tests (pytest) la auditoría ad hoc de la API de proveedores.
4. Agregar pruebas de integracion básicas para operaciones críticas del tracker (listado, detalle, PATCH, notas).
5. Ejecutar auditoría de accesibilidad y rendimiento en despliegue público, con plan de mejora si la puntuacion < 80.
6. Continuar hitos siguientes del roadmap (telemetría, RAG y automatizaciones) reutilizando los tipos y patrones actuales.
7. **Probar `docker compose up` real** para verificar el funcionamiento en runtime de todos los servicios.
8. Extender tests de backend para cubrir casos borde de serialización (schemas de listado, análisis).
9. **Migrar a Redis** si el deployment escala a múltiples workers (la caché en memoria actual no comparte estado entre workers).
10. **Implementar stale-while-revalidate** en el frontend para peticiones GET al servidor.
11. **Evaluar SWR/TanStack Query** como sustituto de `useMemo` + fetch manual para caché de red con revalidación automática.
12. **Pronóstico de ventas — automatizar la reejecución**: encadenar `scripts/train_sales_forecast.py` al proceso nocturno o a un cron mensual para que la banda y las métricas se refresquen con los datos nuevos, y versionar `metrics.json` para detectar degradación entre ejecuciones.
13. **Pronóstico de ventas — incorporar variables exógenas**: altas de clínica, campañas de captación y cambios de tarifa explicarían parte del error residual que hoy queda en la banda.
14. **Pronóstico de ventas — comparar contra un baseline**: un modelo sencillo (media móvil o regresión lineal con estacionalidad) como referencia haría el informe defendible también en la dirección contraria ("¿de verdad necesitamos XGBoost?").
