# System Pattern

## Patrón general del repositorio
Monorepo de aprendizaje orientado a hitos, con separación por dominios:
- uis/: interfaces (HTML estático y app Next.js).
- src/: utilidades TypeScript de lógica de negocio (modelo, colecciones, búsqueda, transformaciones, validaciones).
- packages/, services/, data/, skills/, workflows/: estructura preparada para escalado en hitos posteriores.

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
