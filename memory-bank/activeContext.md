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

## Estado operacional observado
- Typecheck de raiz sin errores.
- Typecheck de uis/talent-pipeline-tracker sin errores.
- Estructura del repo lista para continuar hitos posteriores (backend/telemetría/agentes/workflows).
