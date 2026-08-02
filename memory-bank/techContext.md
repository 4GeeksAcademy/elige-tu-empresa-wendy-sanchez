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

## Decisiones de arquitectura tomadas
1. Mantener hito web y hito Next.js coexistiendo en el mismo repo para evaluación incremental.
2. Centralizar tipos de dominio del tracker en types/candidate.ts.
3. Encapsular llamadas API en un módulo único de servicios.
4. Implementar validación de formularios en librerías dedicadas (validation.js y lib/validation.ts).
5. Priorizar funciones puras para lógica de negocio en src/utils.

## Restricciones técnicas
- El contenido y campos deben seguir exactamente CONTEXT.md para cumplir evaluación.
- Bilingüismo obligatorio en la experiencia pública (EN/ES).
- API URL del tracker depende de variable de entorno NEXT_PUBLIC_API_URL.
- Validación de TypeScript exigida sin errores en raíz y en UI Next.js.
- El proyecto tiene estructura de plantilla; no todo el monorepo está operativo en runtime aún.

## Comandos útiles
- Preview estático en Codespaces: npx --yes serve . --listen 4173 --no-clipboard
- Typecheck raiz: npm run typecheck
- Tracker dev: cd uis/talent-pipeline-tracker && npm run dev
- Tracker typecheck: cd uis/talent-pipeline-tracker && npm run typecheck
