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

## Patrones de Docker

### 10) Comunicación por nombre Docker
- Los servicios se comunican usando nombres de servicio definidos en docker-compose.yml (`backend`, `incidents-backend`) en lugar de `localhost`.
- Las variables de entorno (`.env`) contienen URLs con nombres Docker: `SUPPLIERS_API_URL=http://backend:8000`, `INCIDENTS_API_URL=http://backend:8000`.
- Los route handlers y rewrites de Next.js (`next.config.ts`) usan estas variables de entorno.

### 11) Multi-etapa con Dev/Prod separados
- `uis/Dockerfile`: etapa `install` (dependencias) → `builder` (compilación) → `development` (dev con hot-reload via Turbopack). Sin `--only=production` para incluir devDependencies necesarias en runtime.
- `services/Dockerfile`: usa `uv` para instalar dependencias, entrypoint bash que selecciona entre api e incidents-api según variable `SERVICE_NAME`.

### 12) Bind mounts + volumes anónimos
- **Bind mounts** para hot-reload: `./uis:/workspace/uis` refleja cambios en vivo en website y backoffice.
- **Volumen especial**: `./src:/workspace/uis/backoffice/src` monta las utilidades compartidas dentro del proyecto backoffice, permitiendo que Turbopack resuelva imports como `../src/...`.
- **Volúmenes anónimos** para `node_modules` en cada proyecto Next.js, evitando que el bind mount sobreescriba `node_modules` del contenedor.

### 13) Graceful skip de dependencias externas
- `init_supabase_schema()` verifica si `DATABASE_URL` está configurada antes de conectar. Si está vacía, omite la inicialización gracefulmente con un log informativo. Esto permite desarrollo local sin Supabase sin necesidad de variables dummy.

### 14) Imágenes no optimizadas en contenedor
- `next.config.ts` del website usa `images: { unoptimized: true }` porque el contenedor no resuelve DNS externo, evitando errores `EAI_AGAIN` al intentar optimizar imágenes de terceros (Unsplash). La carga directa desde el navegador funciona sin problemas.

## Patrones de infraestructura y desarrollo

### 15) Proxy de API en el backoffice
- app/api/** reenvía al backend y traduce los errores 422 de FastAPI a mensajes legibles por campo.
- El navegador nunca habla directamente con FastAPI: evita CORS y oculta la URL interna del backend.

### 16) Docker multi-servicio para desarrollo
- Cada servicio tiene su propio `Dockerfile` y `.dockerignore` en su directorio.
- `docker-compose.yml` en raíz orquesta todos los servicios con red bridge explícita.
- Los contenedores se comunican por nombre de servicio Docker, no por localhost.
- Bind mounts del código fuente permiten hot-reload sin reconstruir imágenes.
- Volúmenes anónimos para `node_modules` evitan que el bind mount del host sobrescriba las dependencias instaladas en el contenedor.

### 17) Entrypoint dinámico
- `services/entrypoint.sh` selecciona el comando uvicorn según variable `SERVICE_NAME` (api→:8000, incidents-api→:8010).
- `uis/start.sh` lanza ambos Next.js en paralelo con manejo de señales SIGTERM/SIGINT.

### 18) Optimización de contexto Docker
- `.dockerignore` raíz excluye node_modules, .env, __pycache__, .next, .venv, .git del contexto de build (reduce ~987 kB → ~10.5 kB).
- Cada subdirectorio (uis/, services/) tiene su propio `.dockerignore` para filtros adicionales específicos.

### 19) Configuración dual de TypeScript para tests
- `tsconfig.json` principal: configuración estricta de producción, excluye `__tests__`.
- `tsconfig.test.json`: extiende el principal, añade `types: ["jest", "node"]`, incluye `__tests__`.
- `jest.config.ts` apunta al `tsconfig.test.json` para que Jest tenga los tipos correctos.
- Esto evita contaminar el ámbito de producción con tipos de test (@types/jest).
