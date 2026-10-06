# Progress

## Estado actual del desarrollo

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
