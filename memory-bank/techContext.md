# Tech Context

## Stack técnologico

### Raíz del repositorio
- TypeScript 5.x
- Configuración estricta en tsconfig.json (strict, noImplicitAny, noUnusedLocals, noUnusedParameters).
- Script de validación: npm run typecheck.

### Sitio estático (hito web)
- HTML semántico (index/application en EN y ES).
- Tailwind CSS via CDN para estilos utilitarios.
- JavaScript vanilla en validation.js para validación del formulario.
- Datos estructurados Schema.org (MedicalOrganization + MedicalClinic) en landing.

### UI Talent Pipeline Tracker (uis/talent-pipeline-tracker)
- Next.js (App Router), React 19, TypeScript.
- Tailwind CSS 4 para estilos.
- ESLint configurado.
- Cliente fetch nativo para integración con API externa (NEXT_PUBLIC_API_URL).
- Autenticación JWT con localStorage.

### API HealthCore — Principal (services/api)
- Python 3.12, gestionado con uv (pyproject.toml en services/api, .venv local).
- **FastAPI + Uvicorn** para servir la API.
- **Pydantic v2** para modelado y validación de datos.
- **TinyDB** como almacenamiento en JSON para usuarios, proveedores y autenticación.
- **SQLModel 0.0.42** (SQLAlchemy 2.0.54) como ORM para inventario en Supabase PostgreSQL.
- **psycopg2-binary 2.9.13** como driver de PostgreSQL.
- **python-jose** para JWT (emisión y validación de tokens).
- **passlib + bcrypt** para hash de contraseñas.
- **Resend API** para envío de emails transaccionales.
- **requests** para llamadas HTTP externas (Resend).
- **dotenv** para configuración de variables de entorno.
- **pytest** para tests (9 archivos de test en services/api/tests/).
- **Cobertura**: `.coverage` en services/incidents-api.
- Scripts: `uv run seed` (carga inicial), `uv run uvicorn main:app --port 8000 --reload`.
- Ruta de TinyDB de proveedores: data/process/suppliers_db.json, sobreescribible con HEALTHCARE_DB_PATH.
- Ruta de TinyDB de usuarios/auth: services/api/db.json (creado automáticamente).
- Variables de entorno requeridas: JWT_SECRET_KEY, y opcionalmente RESEND_API_KEY, SUPABASE_URL, SUPABASE_KEY, HEALTHCORE_DB_PATH, RATE_LIMIT_MAX_REQUESTS, ACCESS_TOKEN_EXPIRE_MINUTES, etc.

### API de Incidencias (services/incidents-api)
- FastAPI independiente, puerto 8010.
- TinyDB como almacenamiento.
- pytest con tests funcionales (conftest.py, helpers.py, test_incidents.py).
- Análisis de CSV: `incidents_analysis.py` en services/api/.

### UI Backoffice (uis/backoffice)
- **Next.js 16** (App Router), **React 19**, **Tailwind CSS 4**.
- **TypeScript** estricto.
- ESLint configurado (eslint.config.mjs).
- Route handlers en `app/api/**` que actúan de proxy hacia FastAPI (SUPPLIERS_API_URL, por defecto http://127.0.0.1:8000). Útiles para auth (login, me, forgot-password, change-password, reset-password), profiles (me), users y suppliers.
- Rewrites en `next.config.ts`:
  - `/api/inventory/*` → `http://127.0.0.1:8000/inventory/*` (inventario, puerto 8000)
  - `/api/incidents/*` → `http://127.0.0.1:8010/api/incidents/*` (incidencias, puerto 8010)
- **Auth**: React Context (AuthProvider) + AuthGuard + localStorage (clave `healthcore_token`).
- **Capas de cliente HTTP**:
  - `lib/inventoryApi.ts` — cliente centralizado de inventario (con ApiError, extractErrorMessage, helpers de stock)
  - `lib/suppliersApi.ts` + `lib/suppliersProxy.ts` + `lib/suppliersServer.ts` — tres capas para proveedores
  - `lib/auth.ts` — utilidades de token (getToken, setToken, removeToken)
  - `lib/authHttpClient.ts` — cliente HTTP genérico con Bearer token y manejo 401
  - `lib/AuthContext.tsx` — React Context de autenticación
  - `lib/authProxy.ts` — proxy server-side de auth para route handlers
- **Componentes**: AuthGuard, BackofficeHeader (con links de inventario), SuppliersDirectoryClient, y 5 componentes de incidencias (IncidentListPanel, IncidentRegisterForm, IncidentSummaryPanel, IncidentsAnalyzerClient, IncidentsManagerClient).
- **Páginas protegidas**: /suppliers, /inventory/* (4), /incidents/* (5), /incidents-manager, /account/profile, /account/change-password.
- **Páginas públicas**: /login, /register, /forgot-password, /reset-password.

### UI Website público (uis/website)
- Next.js (App Router), React, TypeScript.
- Tailwind CSS 4.
- ESLint configurado.
- Sin autenticación — sitio público corporativo de HealthCore.
- Carga inicial en Server Component; refetch client-side solo desde event handlers.

## Decisiones de arquitectura tomadas
1. Mantener hito web y hito Next.js coexistiendo en el mismo repo para evaluación incremental.
2. Centralizar tipos de dominio del tracker en types/candidate.ts.
3. Encapsular llamadas API en un módulo único de servicios.
4. Implementar validación de formularios en librerías dedicadas (validation.js y lib/validation.ts).
5. Priorizar funciones puras para lógica de negocio en src/utils.
6. Validar en el borde con Pydantic: las reglas de negocio del CONTEXT (moneda por país, tarifa positiva, enums de estado y categoría) se rechazan con 422 antes de tocar TinyDB.
7. Baja lógica en el directorio de proveedores: DELETE no borra, marca `archived_at`. `status` conserva únicamente los valores del CONTEXT.
8. No cargar datos en useEffect en el backoffice: la carga inicial es server-side y evita la regla react-hooks/set-state-in-effect.
9. **Arquitectura dual de BD**: TinyDB para usuarios/auth/proveedores, Supabase PostgreSQL para inventario. El modelo User NO existe en SQLModel.
10. **Dos APIs separadas**: API principal (puerto 8000) para proveedores, auth, inventario. API de incidencias (puerto 8010) independiente.
11. **Dos estrategias de proxy**: route handlers de Next.js para auth/suppliers (permiten lógica server-side como forwardHeaders), rewrites de next.config.ts para inventario/incidencias (más simples, sin lógica intermedia).
12. **Capa API dedicada para inventario**: inventoryApi.ts centraliza todas las llamadas. Ningún componente de inventario hace fetch directo. Esto contrasta con el patrón anterior donde algunos componentes podían tener fetch inline.
13. **Stock reactivo en frontend**: al seleccionar un producto en el formulario de salida, se dispara fetchProduct() para obtener el stock fresco de la API. No confía solo en el listado inicial.
14. **Dockerización para desarrollo**: contenedores separados por servicio, comunicación por nombre Docker, bind mounts para hot-reload.
15. **Configuración dual de tsconfig**: `tsconfig.json` principal para producción (excluye `__tests__`), `tsconfig.test.json` para Jest (con `types: ["jest", "node"]`).

## Docker y orquestación

### docker-compose.yml (raíz)
- **Red**: `healthcore-net` (bridge explícito).
- **Servicios**: `uis` (Node.js), `backend` (Python), `incidents-backend` (Python).
- **Contexto de build**: siempre `.` (raíz), con `.dockerignore` para filtrar.
- **Montajes**: bind mounts de código fuente + volúmenes anónimos para `node_modules`.
- **Variables de entorno**: via `env_file: .env`.
- **Comunicación**: por nombre de servicio Docker (`http://backend:8000`, `http://incidents-backend:8010`).

### uis/Dockerfile
- **Imagen base**: `node:22-alpine`.
- **3 etapas**: base, deps-website, deps-backoffice, runner.
- **Puertos**: 3000 (website) y 3001 (backoffice).
- **Entrypoint**: `start.sh` que lanza ambos Next.js en paralelo con `npm run dev`.

### services/Dockerfile
- **Imagen base**: `python:3.12-slim`.
- **Instalación**: `pip install uv` → `uv pip install --system` desde ambos `requirements.txt`.
- **Puertos**: 8000 (api) y 8010 (incidents-api).
- **Entrypoint**: `entrypoint.sh` que selecciona `uvicorn` según `SERVICE_NAME`.

### Variables de entorno para Docker (.env)
- `SUPPLIERS_API_URL=http://backend:8000`
- `INCIDENTS_API_URL=http://backend:8000` (¡no backend:8010!)
- `NEXT_PUBLIC_INVENTORY_API_URL=http://backend:8000`
- `NEXT_PUBLIC_INCIDENTS_API_URL=/api/incidents`
- `JWT_SECRET_KEY=dev-secret-not-for-production`
- `RESEND_API_KEY=` (vacío, simulación en consola)

## Tests y TypeScript

### Jest (uis/backoffice)
- `jest.config.ts` configurado con `ts-jest` y `tsconfig.test.json`.
- `tsconfig.test.json`: extiende `tsconfig.json`, añade `types: ["jest", "node"]`, incluye `__tests__`.
- 11 tests pasando (0.723s): suppliers proxy, auth, suppliers API.
- Ejecución: `npx jest` desde `uis/backoffice/`.

### TypeScript
- `__tests__` excluido del `tsconfig.json` principal para evitar conflictos de tipos.
- Recarga de ventana VS Code necesaria después de cambios en tsconfig (TypeScript cachea el proyecto).

## Restricciones técnicas
- El contenido y campos deben seguir exactamente CONTEXT.md para cumplir evaluación.
- Bilingüismo obligatorio en la experiencia pública (EN/ES).
- API URL del tracker depende de variable de entorno NEXT_PUBLIC_API_URL.
- Validación de TypeScript exigida sin errores en raíz y en UI Next.js.
- `status` de proveedor limitado a "active" y "suspended": no ampliar el enum aunque el negocio pida más estados.
- data/process/suppliers_db.json y services/api/.venv están en .gitignore: son artefactos regenerables.
- **Inventario**: `current_stock` no se almacena ni se modifica directamente. Solo se cambia mediante órdenes.
- **Inventario**: `consumption_type` validado en schema Pydantic, solo `"clinical_use"` y `"expiry_waste"`.
- **Inventario**: stock insuficiente → HTTP 400 antes de escribir en BD.
- **Inventario**: los datos de inventario son operativos, no PHI (confirmado por Claire Whitfield).
- El proyecto tiene estructura de plantilla; no todo el monorepo está operativo en runtime aún.

## Comandos útiles
- Preview estático en Codespaces: npx --yes serve . --listen 4173 --no-clipboard
- Typecheck raiz: npm run typecheck
- Tracker dev: cd uis/talent-pipeline-tracker && npm run dev
- Tracker typecheck: cd uis/talent-pipeline-tracker && npm run typecheck
- Seed de proveedores: cd services/api && uv run seed (falla desde la raíz: el pyproject vive en services/api)
- Seed de inventario: el mismo `uv run seed` incluye seed_inventory()
- API dev (principal): cd services/api && uv run uvicorn main:app --port 8000 --reload
- API dev (incidencias): cd services/incidents-api && uv run uvicorn main:app --port 8010 --reload
- Backoffice dev: cd uis/backoffice && npm run dev (http://localhost:3000)
- Backoffice build: cd uis/backoffice && npm run build
- Backoffice checks: cd uis/backoffice && npm run typecheck && npm run lint
- Tests API principal: cd services/api && uv run pytest
- Tests API incidencias: cd services/incidents-api && uv run pytest
- Website dev: cd uis/website && npm run dev
- Login test admin: admin@healthcore.com / Admin123! (creado vía API)
