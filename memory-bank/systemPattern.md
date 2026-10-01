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

### 20) Schemas de serialización: entrada y salida separados (backend)
- **Modelos Pydantic de entrada** (`*Create`, `*Update`, `*Replace`): definen exactamente lo que el cliente debe enviar, sin campos generados por el sistema.
- **Modelos de salida para listado** (`*ListItem`, `*Public`): más ligeros que los de detalle, excluyen campos pesados o claves foráneas internas.
- **Modelos de salida para detalle/escritura** (`Supplier`, `IncidentResponse`): incluyen todos los campos que el consumidor necesita tras una operación.
- **Modelos de mensaje genérico** (`MessageResponse`): para flujos donde solo se devuelve un texto (auth no autenticado).
- **Modelos de respuesta compuesta** (`AnalysisResponse` con `AnalysisSummary` y `AnalysisPercentages` anidados): estructuras complejas completamente tipadas.
- **RootResponse**: schema explícito para endpoints de descubrimiento, eliminando `response_model=dict`.

### 21) Patrón de refactorización frontend: capa de datos compartida
- **Tipos de dominio en `types/`**: cada módulo de negocio (incident, supplier) tiene su archivo de tipos compartido.
- **Constantes y mapeos en `lib/`**: labels, colores, opciones de select, API_BASE — todo centralizado para evitar duplicación entre componentes.
- **Clientes HTTP en `lib/`**: un único `httpClient.ts` para todo el backoffice, con `request<T>()`, `extractErrorMessage()`, `ApiError`. Los módulos específicos importan desde ahí.

### 22) Patrón de componentes UI reutilizables
- **`LoadingSpinner`**: spinner animado con props `message`, `fullPage`, `size` (sm/md/lg).
- **`ErrorMessage`**: bloque de error con props `title`, `message`, `onRetry`, `variant` (error/warning/info).
- **`EmptyState`**: estado de lista vacía con props `message`, `description`, `icon`, `action`.
- Todos en `components/ui/` con barrel export desde `index.ts`.

### 23) Patrón de caché — Cache-Aside (backend)
- **Estrategia cache-aside**: el código pregunta primero a la caché (`cache.get(key)`); si existe el valor, lo devuelve sin tocar la base de datos. Si no existe, ejecuta la operación (consulta DB, cálculo), almacena el resultado en caché con `cache.set(key, value, ttl)`, y lo devuelve.
- **Clave única por combinación de parámetros**: en endpoints con filtros (GET /incidents), la clave incluye todos los parámetros de consulta serializados para que cada combinación de filtros tenga su propia entrada en caché.
- **Invalidación por prefijo de clave**: en lugar de rastrear claves individuales, se invalida un prefijo completo (`\"incidents:list\"` → elimina todas las claves que empiecen por `\"incidents:list:\"`). Es más simple y seguro que la invalidación selectiva.
- **TTL cortos (30-60s)**: se prioriza la frescura de datos sobre el ahorro máximo de consultas. Suficiente para reducir carga repetitiva sin riesgos de obsolescencia.

### 24) Patrón de Lazy Loading (frontend)
- **`next/dynamic` con `ssr: false`**: los componentes pesados que no se ven en carga inicial se importan dinámicamente. `ssr: false` evita que el servidor los procese, dejando la descarga al navegador bajo demanda.
- **Extracción a archivo independiente**: para poder usar `next/dynamic`, el componente debe estar en un archivo separado con `export default`. No funciona con exportaciones nombradas inline.

### 25) Patrón de `useMemo` con dependencias explícitas (frontend)
- Cada `useMemo` declara exactamente las variables de las que depende en su array de dependencias. Si el valor usa `sortedClaims`, la dependencia es `[sortedClaims]` — no la lista original.
- Esto evita recálculos en cadena: si cambia una variable que no afecta a cierto cómputo, ese cómputo no se repite.
- Los valores computados (derivados de otros `useMemo`) se encadenan correctamente respetando el grafo de dependencias.

### 26) Patrón de Timing Middleware (backend)
- Middleware FastAPI que captura el tiempo de inicio antes de procesar la request y calcula la diferencia después de enviar la respuesta.
- Loggea al formato: `METODO /ruta → CODIGO (X.XXms)` para permitir identificación de cuellos de botella sin herramientas externas de APM.
- No interfiere con el flujo de la request ni añade latencia medible.
