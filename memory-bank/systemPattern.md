# System Pattern

## Patrón general del repositorio
Monorepo de aprendizaje orientado a hitos, con separación por dominios:
- uis/: interfaces (HTML estático y apps Next.js: website, backoffice, talent-pipeline-tracker).
- src/: utilidades TypeScript de lógica de negocio (modelo, colecciones, búsqueda, transformaciones, validaciones).
- services/api/: backend FastAPI (análisis de incidencias + directorio de proveedores).
- packages/, data/, skills/, workflows/: estructura preparada para escalado en hitos posteriores.

## Patrones de código observados

### 1) Separation of concerns
- Tipos y entidades en módulos dedicados.
- Utilidades puras separadas por responsabilidad (filtrado, búsqueda, agregaciones, validación).
- Componentes UI desacoplados de acceso a datos mediante services/api.ts.

### 2) Functional core
- Funciones de negocio mayormente puras en src/utils.
- Entradas y salidas tipadas con TypeScript estricto.
- Manejo explícito de casos borde: arrays vacíos, datos no encontrados, fechas inválidas.

### 3) Cliente API centralizado
- Wrapper request genérico en tracker para GET/POST/PUT/PATCH/DELETE.
- Normalización de errores HTTP a mensajes consumibles por UI.
- Construcción de query params desde estado de filtros.

### 4) Estado local por vista/componente
- Estado de red y formularios acotado en componentes cliente de Next.js.
- No prop drilling profundo; la lógica se concentra por pantalla.
- Feedback de operaciones asíncronas en el mismo contexto de uso.

### 5) UX y validación en tiempo real
- Formulario de paciente con validaciones realtime + submit guard.
- Uso de mensajes específicos por campo según reglas de negocio.
- Campos condicionales (insurance, patient_id) controlados por selecciones previas.

## Patrones de navegación
- Listado -> detalle con preservación de contexto de filtros vía query string.
- Operaciones del detalle (estado/etapa/notas/edición) sin salir de la página.

## Patrones del backend (services/api)

### 6) Capas por responsabilidad
- models.py: modelos Pydantic y enums de dominio.
- database.py: inicialización única de TinyDB y resolución de la ruta del fichero.
- routes/: un router por dominio, montado en main.py.
- seed.py: datos iniciales del CONTEXT, ejecutable como script.

### 7) Modelos de entrada y salida separados
- SupplierCreate / SupplierReplace para lo que envía el cliente.
- Supplier para la respuesta, con los campos que genera el sistema (id, updated_at, archived_at).
- Los campos generados por el sistema se ignoran si el cliente los envía.

### 8) Trazabilidad temporal
- updated_at sella exclusivamente los cambios de tarifa (auditorías de coste).
- archived_at sella la baja del proveedor. No se mezclan semánticas en un mismo campo.

### 9) Seeder idempotente
- Comprueba existencia por nombre antes de insertar y reporta insertados/omitidos/total por consola.

### 10) Proxy de API en el backoffice
- app/api/** reenvía al backend y traduce los errores 422 de FastAPI a mensajes legibles por campo.
- El navegador nunca habla directamente con FastAPI: evita CORS y oculta la URL interna del backend.
