# Progress

## Estado actual del desarrollo

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

## Riesgos o brechas potenciales
- No hay pruebas automatizadas persistidas para la API de proveedores (la auditoría se ejecutó con scripts ad hoc).
- Falta verificar formalmente métricas de rendimiento (PageSpeed) en URL pública.
- README del tracker aun es plantilla genérica de Next.js, no documenta flujo de negocio/API.
- No se observan pruebas automatizadas visibles para UI ni utilidades TS en este barrido.
- **Inventario**: no hay tests automatizados para la API de inventario (solo se auditó manualmente contra 10 criterios).
- **Incidencias**: los tests de incidents-api existen pero no se sabe si están integrados en un pipeline CI.
- **Website público**: no se ha verificado su estado de build o despliegue.
- **Dependencia de Supabase**: la API de inventario depende de una conexión externa a Supabase. Si la conexión falla, todo el módulo de inventario queda inoperativo.
- **Variables de entorno**: authProxy.ts depende de SUPPLIERS_API_URL / INCIDENTS_API_URL que pueden no estar definidas (fallback a 127.0.0.1:8000).

## Próximos pasos previstos
1. Documentar el tracker con README especifico de dominio (setup, variables de entorno, endpoints, flujo funcional).
2. Incorporar pruebas unitarias para utilidades de src/ y validaciones del tracker.
3. Persistir como suite de tests (pytest) la auditoría ad hoc de la API de proveedores.
4. Agregar pruebas de integracion básicas para operaciones críticas del tracker (listado, detalle, PATCH, notas).
5. Ejecutar auditoría de accesibilidad y rendimiento en despliegue público, con plan de mejora si la puntuacion < 80.
6. Continuar hitos siguientes del roadmap (telemetría, RAG y automatizaciones) reutilizando los tipos y patrones actuales.
