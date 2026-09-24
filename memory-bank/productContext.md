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
