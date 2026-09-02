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
- services/api.ts: cliente HTTP centralizado.
- types/candidate.ts y lib/validation.ts: contrato de datos y validación.

### 4) API Directorio de Proveedores (services/api)
- models.py: modelos Pydantic (Supplier, SupplierCreate, SupplierReplace, SupplierRateUpdate, SupplierStatusUpdate) con enums de país, moneda, categoría, estado y acuerdo de cumplimiento, más validador de coherencia moneda-país.
- database.py: inicialización de TinyDB (data/process/suppliers_db.json, override con HEALTHCORE_DB_PATH).
- routes/suppliers.py: listado con filtros, búsqueda por país y por categoría, alta, reemplazo, PATCH de tarifa (registra updated_at), PATCH de estado y DELETE como baja lógica (suspende y sella archived_at, no borra).
- seed.py: carga idempotente de los 15 proveedores del CONTEXT (`uv run seed` desde services/api).
- pyproject.toml: dependencias y script `seed`.

### 5) Directorio de proveedores en el backoffice (uis/backoffice)
- app/suppliers/page.tsx: Server Component que hace la carga inicial y enlaza desde el menú ("Supplier Directory").
- components/SuppliersDirectoryClient.tsx: tabla con filtros por país y categoría sin recarga, alta con validación en cliente, edición de tarifa inline y botones Suspender/Activar y Eliminar por fila.
- Tres estados visuales: Activo (verde), Suspendido (ámbar) y Eliminado (rojo, con fecha de baja).
- app/api/suppliers/**: route handlers que proxean a la API FastAPI (SUPPLIERS_API_URL, por defecto http://127.0.0.1:8000).
- lib/suppliersApi.ts, lib/suppliersProxy.ts y lib/suppliersServer.ts: cliente HTTP, proxy con formateo de errores 422 y carga server-side.
- types/supplier.ts: contrato de datos alineado con los modelos Pydantic.

## Decisiones de diseño vigentes
- El CONTEXT manda: `status` solo admite "active" y "suspended". No se añadió un tercer valor "deleted" pese a necesitarse el concepto de baja.
- El botón Eliminar ejecuta DELETE, que archiva el registro (`archived_at`) en lugar de borrarlo: una auditoría puede preguntar con qué proveedores se trabajó en un período.
- Suspender y Eliminar son acciones distintas: la primera es una pausa reversible sin fecha; la segunda cierra la relación dejando constancia del momento.

## Estado operacional observado
- Typecheck de raiz sin errores.
- Typecheck de uis/talent-pipeline-tracker sin errores.
- Typecheck y lint de uis/backoffice sin errores.
- API de proveedores auditada extremo a extremo: validaciones 422, 404, filtros, seeder idempotente y persistencia tras reiniciar uvicorn.
- Estructura del repo lista para continuar hitos posteriores (telemetría/agentes/workflows).
