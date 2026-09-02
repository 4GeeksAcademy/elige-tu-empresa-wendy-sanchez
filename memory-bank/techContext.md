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

### UI Talent Pipeline Tracker
- Next.js (App Router), React 19, TypeScript.
- Tailwind CSS 4 para estilos.
- ESLint configurado en app de UI.
- Cliente fetch nativo para integración con API externa (NEXT_PUBLIC_API_URL).

### API HealthCore (services/api)
- Python 3.12 gestionado con uv (pyproject.toml en services/api, entorno en .venv local).
- FastAPI + Uvicorn; Pydantic v2 para modelado y validación; TinyDB como almacenamiento en JSON.
- Script de carga inicial expuesto como `uv run seed` vía [project.scripts].
- Ruta de la base de datos: data/process/suppliers_db.json, sobreescribible con HEALTHCORE_DB_PATH.

### UI Backoffice (uis/backoffice)
- Next.js 16 (App Router), React 19, Tailwind CSS 4.
- Route handlers en app/api/** que actúan de proxy hacia FastAPI (SUPPLIERS_API_URL, por defecto http://127.0.0.1:8000).
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

## Restricciones técnicas
- El contenido y campos deben seguir exactamente CONTEXT.md para cumplir evaluación.
- Bilingüismo obligatorio en la experiencia pública (EN/ES).
- API URL del tracker depende de variable de entorno NEXT_PUBLIC_API_URL.
- Validación de TypeScript exigida sin errores en raíz y en UI Next.js.
- `status` de proveedor limitado a "active" y "suspended": no ampliar el enum aunque el negocio pida más estados.
- data/process/suppliers_db.json y services/api/.venv están en .gitignore: son artefactos regenerables.
- El proyecto tiene estructura de plantilla; no todo el monorepo está operativo en runtime aún.

## Comandos útiles
- Preview estático en Codespaces: npx --yes serve . --listen 4173 --no-clipboard
- Typecheck raiz: npm run typecheck
- Tracker dev: cd uis/talent-pipeline-tracker && npm run dev
- Tracker typecheck: cd uis/talent-pipeline-tracker && npm run typecheck
- Seed de proveedores: cd services/api && uv run seed (falla desde la raíz: el pyproject vive en services/api)
- API dev: cd services/api && uv run uvicorn main:app --port 8000 --reload
- Backoffice dev: cd uis/backoffice && npm run dev (http://localhost:3000/suppliers)
- Backoffice checks: cd uis/backoffice && npm run typecheck && npm run lint
