# Product Context

## Producto y alcance actual
El producto en este repositorio tiene dos superficies principales:

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

## Usuarios clave
- Pacientes potenciales de HealthCore (especialmente mercado bilingue en EE. UU.).
- Equipo de recepción y experiencia del paciente.
- Equipo de People/HR para seguimiento de candidaturas.
- Diane Foster (VP of People): gestión del gasto y contratos con proveedores.
- Claire Whitfield (Chief Compliance Officer): verificación de acuerdos BAA/DPA y auditoría de cambios de coste.
- Stakeholders operativos y ejecutivos que necesitan datos consistentes.

## Necesidades que cubre
- Credibilidad digital y acceso bilingüe para pacientes.
- Estandarización de datos de entrada para contacto posterior.
- Flujo de reclutamiento con visibilidad de estado y etapa.
- Reducción de trabajo manual mediante validaciones y formularios estructurados.

## Reglas de negocio relevantes
- Campos de formulario de paciente definidos explícitamente en CONTEXT.md.
- Validaciones especificas: edad, teléfono con código de país, ventana de fecha preferida, reglas condicionales de seguro, regla pediátrica y consentimiento obligatorio.
- En tracker de talento, operaciones CRUD y PATCH para estado/etapa con feedback visual.
- Proveedores: moneda determinada por el país (USA->USD, UK->GBP), tarifa mensual estrictamente positiva y estado limitado a active/suspended.
- Proveedores: cada cambio de tarifa registra su timestamp; los proveedores no se borran, se suspenden o se archivan con fecha de baja.

## Criterios de experiencia de usuario
- Sin recargas completas para filtrar/buscar en tracker.
- Estados claros de carga, error y éxito en acciones asíncronas.
- Formularios con mensajes de validación accionables.
- Navegación simple entre listado y detalle.
