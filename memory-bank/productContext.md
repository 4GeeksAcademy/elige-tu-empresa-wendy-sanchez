# Product Context

## Producto y alcance actual
El producto en este repositorio tiene las siguientes superficies:

1. Sitio público HealthCore
- Landing page corporativa EN/ES con servicios, ubicaciones y contacto.
- Formulario de consulta de pacientes (no reserva directa) con validaciones de negocio.

2. Talent Pipeline Tracker (Next.js)
- Listado de candidaturas con filtros por estado/etapa y búsqueda por nombre o email vía query params.
- Vista de detalle por candidato con actualización de estado y etapa.
- Gestión de notas (listar, agregar, eliminar).
- Formularios para crear y editar candidaturas.

3. Directorio de Proveedores (API + backoffice)
- Registro centralizado de proveedores clínicos, operacionales y tecnológicos, sustituyendo las hojas de cálculo separadas por departamento.
- Listado con filtros por país (USA/UK) y por categoría de producto.
- Alta de proveedores, actualización de tarifa mensual con sello temporal y cambio de estado.
- Baja de proveedores conservando el histórico y la fecha en que se dejó de trabajar con ellos.

4. Autenticación y gestión de usuarios (API + backoffice + tracker)
- Registro de usuarios con perfil (nombre, teléfono, dirección).
- Login con JWT y sesión persistente en localStorage.
- Recuperación de contraseña con flujo completo: forgot-password (email vía Resend), reset-password (token único), change-password.
- Perfil de usuario: consulta y actualización.
- Roles: USER y ADMIN, con permisos diferenciados.

5. Sistema de Incidencias (API independiente + backoffice)
- API FastAPI independiente (puerto 8010) para gestión de incidencias de pacientes.
- Registro, listado con filtros, detalle y actualización de incidencias.
- Análisis de CSV de incidencias del sistema legacy.
- Categorización por tipo (appointment, billing, clinical_equipment, compliance_breach, patient_experience).
- Clasificación por origen (customer, staff, system, supplier).

6. Módulo de Inventario de Suministros Médicos (API + backoffice)
- API de inventario con 6 endpoints bajo /inventory.
- Modelos SQLModel en Supabase PostgreSQL para suministros, entregas y consumos.
- Stock siempre calculado como neto de entradas menos salidas (no modificable directamente).
- 4 páginas en el backoffice: productos con código de color, registro de entradas, registro de salidas con stock reactivo, historial de órdenes.
- Datos semilla: 8 suministros con stock calculado, 12 clínicas.

7. **Cola de Tareas Asíncronas — Redis + Celery (Oct 2026)**
- **Sistema de cola de tareas asíncronas** que desacopla las operaciones pesadas de la API para que los endpoints respondan inmediatamente (HTTP 202 Accepted) mientras un worker independiente procesa la tarea en segundo plano.
- **Arquitectura Productor-Consumidor**: FastAPI (productor) encola tareas ligeras en Redis (broker), Celery Worker (consumidor) las procesa en un proceso separado, y TinyDB actúa como Dead Letter Queue (DLQ) para tareas que fallan tras 3 reintentos.
- **Endpoint asíncrono**: `POST /api/incidents/analyze` ahora responde 202 Accepted con `task_id` y header `Location: /tasks/{task_id}`. El análisis de CSV de incidencias se procesa en segundo plano.
- **Endpoint de consulta**: `GET /tasks/{task_id}` devuelve el estado (`pending | started | success | failure`), el resultado, y si falló, la entrada DLQ con detalles del error.
- **Reintentos automáticos**: backoff exponencial (10s, 20s, 40s) con jitter, `acks_late=True` para no perder tareas si el worker se cae, máximo 3 intentos antes de DLQ.
- **Dead Letter Queue**: persistencia en TinyDB (`data/process/task_dlq.json`) con todos los detalles del fallo. Consultable automáticamente por el endpoint de estado.
- **Monitoreo**: Flower disponible en `http://localhost:5555` para inspeccionar colas, workers y tareas en tiempo real.
- **Infraestructura Docker**: 3 nuevos servicios (`redis`, `flower`, `celery-worker`) añadidos a `docker-compose.yml` bajo la red `healthcore-net`.
- **Auditoría**: 10/10 criterios cumplidos — Redis responde, encolado en ~30ms, estados correctos, reintentos funcionales, DLQ operativa, worker conectado, payloads ligeros, Flower accesible.

8. **Telemetría — Pipeline de análisis y dashboard (servidor standalone + backoffice)**
- **Servidor standalone**: `services/telemetry/server_standalone.py` — FastAPI en puerto 8000 que evita SQLModel (incompatible Python 3.14). Sirve `GET /telemetry/report` (5 métricas consolidadas) con caché de 60s, `POST /auth/login`, `GET /auth/me`, `GET /health`.
- **Pipeline de análisis**: `services/telemetry/analysis.py` — 5 funciones pandas que leen Supabase PostgreSQL y producen métricas: `events_per_day()`, `error_rate_by_type()`, `latency_percentiles_by_route()`, `event_type_distribution()`, `auth_failure_rate_by_day()`. Orquestadas por `run_all()`.
- **Autenticación standalone**: `services/telemetry/auth_standalone.py` — bcrypt + JWT (jose) + consultas TinyDB. Sin dependencia de `services/api/models.py`.
- **Seed de usuarios**: `admin@healthcore.com` / `adminpass456` (admin) y `test@healthcore.com` / `securepassword123` (user) en TinyDB.
- **Dashboard**: `uis/backoffice/app/telemetry/page.tsx` — 5 paneles visuales protegidos por AuthGuard. Selector de fechas. Proxy via rewrite en `next.config.ts`.
- **Eventos de telemetría**: 41 eventos (5 obligatorios, 36 oportunidades) definidos en `docs/telemetry/event-schemas.json`.

9. **Reporting Mensual — Supply Performance Pipeline + Dashboard (Oct 2026)**
- **Auth Standalone (`services/api/auth_standalone.py`)**: Servidor FastAPI ligero (puerto 8000) para login JWT del backoffice. Evita SQLModel (crash Python 3.14). Usa bcrypt + TinyDB.
- **Reporting API (`services/reporting/`)**: API FastAPI independiente (puerto 8001) con 3 endpoints JWT-protegidos para KPIs mensuales de suministros por clínica.
- **Pipeline de datos (`data/pipelines/`)**: Orquestación Prefect 3.8.8 (extract → transform → load) para proceso ETL mensual de telemetry_events a tabla reporting.
- **Dashboard Reporting**: Página protegida `/reporting` en backoffice con tabla de KPIs, nombres reales de clínica (mapeo `clinic-001` → "Central — Austin Main Clinic"), consumo, stockouts y riesgo caducidad.
- **Demo Data**: 10 clínicas (5 US + 5 UK) con datos de Octubre 2026 insertados en Supabase PostgreSQL.
- **Cadena E2E verificada**: Login → JWT → Reporting API → Dashboard con datos y nombres de clínica.

## Usuarios clave
- Pacientes potenciales de HealthCore (especialmente mercado bilingue en EE. UU.).
- Equipo de recepción y experiencia del paciente.
- Equipo de People/HR para seguimiento de candidaturas.
- Diane Foster (VP of People): gestión del gasto y contratos con proveedores.
- Claire Whitfield (Chief Compliance Officer): verificación de acuerdos BAA/DPA y auditoría de cambios de coste, más auditoría de incidencias de datos de pacientes.
- James Osei (CTO): prioriza la API de inventario como base del panel de operaciones clínicas.
- Dra. Okonkwo (Dirección Ejecutiva): necesita visibilidad del stock en toda la red clínica.
- Personal clínico y administrativo de las 12 clínicas: registran consumos y recepciones de suministros.
- Stakeholders operativos y ejecutivos que necesitan datos consistentes.

## Necesidades que cubre
- Credibilidad digital y acceso bilingüe para pacientes.
- Estandarización de datos de entrada para contacto posterior.
- Flujo de reclutamiento con visibilidad de estado y etapa.
- Reducción de trabajo manual mediante validaciones y formularios estructurados.
- Autenticación segura con JWT y gestión de sesión en backoffice y tracker.
- Flujo completo de recuperación de contraseña (olvido, restablecimiento, cambio) con rate limiting y auditoría.
- Registro y gestión de incidencias de pacientes con categorización y filtros.
- Análisis de CSV de incidencias del sistema legacy.
- API de inventario como base para el panel de operaciones clínicas.
- Visibilidad centralizada del stock de suministros médicos en las 12 clínicas.
- Los niveles de stock no se pueden modificar directamente — solo mediante órdenes de entrada (entregas) y salida (consumos).
- Distinción visual del nivel de stock (crítico, bajo, saludable) en la interfaz.

## Reglas de negocio relevantes
- Campos de formulario de paciente definidos explícitamente en CONTEXT.md.
- Validaciones especificas: edad, teléfono con código de país, ventana de fecha preferida, reglas condicionales de seguro, regla pediátrica y consentimiento obligatorio.
- En tracker de talento, operaciones CRUD y PATCH para estado/etapa con feedback visual.
- Proveedores: moneda determinada por el país (USA->USD, UK->GBP), tarifa mensual estrictamente positiva y estado limitado a active/suspended.
- Proveedores: cada cambio de tarifa registra su timestamp; los proveedores no se borran, se suspenden o se archivan con fecha de baja.
- **Autenticación**: login con email+password, JWT con expiración de 30 minutos, las rutas protegidas requieren Bearer token.
- **Incidencias**: no deben almacenar datos identificativos de pacientes (solo ID interno opaco). El campo description debe mostrar advertencia sobre no incluir PHI.
- **Inventario**: `current_stock` siempre se calcula (nunca almacenado). No se puede registrar un consumo que resulte en stock negativo (HTTP 400). `consumption_type` solo acepta `"clinical_use"` o `"expiry_waste"`. Los datos de inventario son operativos, no PHI.
- **Arquitectura dual de base de datos**: usuarios/autenticación en TinyDB, datos de inventario en Supabase PostgreSQL con SQLModel. No hay tabla de usuarios en SQLModel — `user_uuid` referencia TinyDB.

## Criterios de experiencia de usuario
- Sin recargas completas para filtrar/buscar en tracker.
- Estados claros de carga, error y éxito en acciones asíncronas.
- Formularios con mensajes de validación accionables.
- Navegación simple entre listado y detalle.
- **Rendimiento de carga inicial**: la página principal debe cargar rápido incluso con bundles grandes. Los componentes pesados (AnalysisResultsPanel, IncidentFormPanel) se cargan bajo demanda (lazy loading) para no penalizar la primera impresión.
- **Consistencia de datos**: los valores derivados (denial rates, no-show costs) se calculan una sola vez por render (useMemo) y no cambian durante la vida de la página, incluso si hay re-renders parciales.
- **Frescura de datos en dashboards**: el resumen de incidencias y la lista de productos pueden tener hasta 30-60 segundos de desfase (caché). Esto es aceptable para dashboards operativos donde la inmediatez no es crítica.
