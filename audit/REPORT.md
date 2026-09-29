# REPORTE DE CORRECCIONES APLICADAS

## 1. Caso 1: Duplicación de tipos, constantes y mapeos en 4 componentes de Incidentes (Refactorización en AUDIT.md)

### 📋 Resumen

Se detectó que 4 componentes del módulo de incidentes (`IncidentListPanel`, `IncidentRegisterForm`, `IncidentSummaryPanel`, `IncidentsManagerClient`) definían **de forma independiente** los mismos tipos (`IncidentStatus`, `IncidentCategory`, `IncidentOrigin`) y constantes (`STATUS_LABELS`, `CATEGORY_LABELS`, `BRANCH_LABELS`, `API_BASE`, etc.), generando ~300 líneas de código duplicado.

Se aplicó la extracción hacia 2 archivos compartidos y se refactorizaron los 4 componentes para que importen desde ahí.

---

### 🏗️ Archivos creados

| Archivo | Propósito | Líneas |
|---|---|---|
| `uis/backoffice/types/incident.ts` | Tipos compartidos del dominio Incident | 30 |
| `uis/backoffice/lib/incidents.ts` | Constantes, labels, mapeos y valores por defecto | 100 |

---

### 🔧 Archivos modificados

| Archivo | Líneas eliminadas | Líneas de import agregadas |
|---|---|---|
| `IncidentListPanel.tsx` | ~70 (tipos + constantes) | 11 |
| `IncidentRegisterForm.tsx` | ~60 (tipos + constantes + form state) | 12 |
| `IncidentSummaryPanel.tsx` | ~45 (tipos + constantes) | 8 |
| `IncidentsManagerClient.tsx` | ~80 (tipos + constantes + form state) | 14 |

**Total de código duplicado eliminado: ~255 líneas**

---

### 📦 Constantes extraídas

| Constante | Descripción | Componentes que la usaban |
|---|---|---|
| `STATUS_LABELS` | Label por status | Todos (4) |
| `STATUS_COLORS` | Clases CSS por status | IncidentListPanel, IncidentsManagerClient |
| `STATUS_ORDER` | Orden de visualización | IncidentSummaryPanel |
| `STATUS_OPTIONS` | Transiciones permitidas | IncidentListPanel |
| `CATEGORY_LABELS` | Label por categoría | Todos (4) |
| `ORIGIN_LABELS` | Label por origen | IncidentRegisterForm, IncidentsManagerClient |
| `BRANCH_LABELS` | Label por sucursal | IncidentListPanel, IncidentSummaryPanel |
| `BRANCH_OPTIONS` | Array `{value, label}` para `<select>` | IncidentRegisterForm (como `BRANCHES`), IncidentsManagerClient (como `VALID_BRANCHES`) |
| `ALL_STATUSES` | Array de status | IncidentListPanel, IncidentRegisterForm |
| `ALL_CATEGORIES` | Array de categorías | IncidentListPanel, IncidentRegisterForm |
| `ALL_ORIGINS` | Array de orígenes | IncidentRegisterForm |
| `ALL_BRANCHES` | Array de keys de sucursales | IncidentListPanel |
| `API_BASE` | URL base de la API | Todos (4) |
| `EMPTY_FORM` | Estado inicial del formulario | IncidentRegisterForm, IncidentsManagerClient |

---

### 🔍 Hallazgos / Inconsistencias descubiertas

1. **`API_BASE` con valores por defecto distintos**: El ManagerClient usaba `""` (vacío) y luego concatenaba `/api/incidents`, mientras que los otros 3 componentes usaban `/api/incidents` como base. Se unificó con `/api/incidents` como valor por defecto y se corrigió el ManagerClient para no duplicar el path.

2. **`IncidentFormState` vs `FormState`**: El RegisterForm definía una interfaz `FormState` local idéntica a `IncidentFormState` del ManagerClient. Se consolidó como `IncidentFormState` compartido.

3. **Nombres distintos para el mismo concepto**: `BRANCHES` (RegisterForm) y `VALID_BRANCHES` (ManagerClient) contenían exactamente los mismos datos. Se unificó como `BRANCH_OPTIONS`.

4. **`STATUS_LABELS` como `Record<string, string>` en SummaryPanel**: El SummaryPanel declaraba los labels como `Record<string, string>` en vez de `Record<IncidentStatus, string>`, perdiendo type-safety. Se corrigió al importar la versión tipada.

5. **`BRANCH_LABELS` con traducciones inconsistentes**: El ManagerClient no usaba `BRANCH_LABELS` en ningún lado (solo `VALID_BRANCHES`), mientras que ListPanel y SummaryPanel recorrían `ALL_BRANCHES` y `BRANCH_LABELS` respectivamente — dos formas distintas de representar lo mismo.

> **📌 Nota:** Esta refactorización corresponde a la **Mejora 4** de `AUDIT.md` (*Extraer tipos y constantes compartidas de incidencias*). Lo que en AUDIT.md se listó como "Mejora 4 (P0)" se resolvió junto con el Caso 1 de la etapa de refactorización, quedando implementado en el mismo commit (`2cfd5dd`).

---

### ✅ Antes / Después

| Métrica | Antes | Después |
|---|---|---|
| Líneas de tipos duplicados | ~255 | 0 |
| Archivos con definiciones compartidas | 4 (cada uno lo suyo) | 2 compartidos |
| Definiciones de `IncidentStatus` | 4 | 1 |
| Definiciones de `IncidentCategory` | 4 | 1 |
| Definiciones de `IncidentOrigin` | 4 | 1 |
| Definiciones de `STATUS_LABELS` | 4 | 1 |
| Definiciones de `CATEGORY_LABELS` | 4 | 1 |
| Mantenibilidad | Si se agrega un status hay que modificar 4 archivos | Solo 1 archivo (`lib/incidents.ts`) |

**Resultado Lighthouse:** *(Imágenes /audit/after/ Caso 1)*
- Website en inglés → Performance aumentó de 97 a 98 
- Website en español → Performance aumentó de 83 a 98 
- Backoffice → Ningún cambio
---

## 2. Caso 2: Cliente HTTP autenticado implementado 3 veces con lógica casi idéntica (Refactorización en AUDIT.md)

### 📋 Resumen

Se detectó que el backoffice tenía **3 implementaciones distintas** del mismo patrón "fetch + JWT + error handling": `authHttpClient.ts`, `suppliersApi.ts` (con su propio `request<T>()`, `getAuthHeaders()`, `handle401()`) e `inventoryApi.ts` (con fetch directo, `getToken()` inline, `extractErrorMessage()`, `getAuthHeaders()` y `handle401()` duplicados). Cada implementación manejaba la autenticación, los errores 401 y la extracción de mensajes de error de forma ligeramente distinta.

Se consolidó todo en `lib/httpClient.ts` como el **único cliente HTTP del backoffice**, y se refactorizaron `suppliersApi.ts` e `inventoryApi.ts` para que deleguen la capa HTTP a este punto único.

---

### 🏗️ Archivos creados

| Archivo | Propósito | Líneas |
|---|---|---|
| `uis/backoffice/lib/httpClient.ts` | Cliente HTTP único con JWT, `extractErrorMessage`, `ApiError`, `request<T>()`, `jsonRequest()` | 125 |

---

### 🗑️ Archivos eliminados

| Archivo | Motivo | Líneas eliminadas |
|---|---|---|
| `uis/backoffice/lib/authHttpClient.ts` | Contenido consolidado en `httpClient.ts` | ~75 |

---

### 🔧 Archivos modificados

| Archivo | Cambio | Líneas eliminadas |
|---|---|---|
| `uis/backoffice/lib/suppliersApi.ts` | Eliminado `handle401()`, `getAuthHeaders()`, `request<T>()`, `jsonInit` (~50 líneas). Ahora importa `request` y `jsonRequest` desde `./httpClient` | ~50 |
| `uis/backoffice/lib/inventoryApi.ts` | Eliminado `getAuthHeaders()`, `handle401()`, `extractErrorMessage()`, `ValidationIssue`, `ApiError`, `request<T>()` (~70 líneas). Ahora importa `request` desde `./httpClient` y usa `requestInventory()` como wrapper para `apiPath()` | ~70 |
| `uis/backoffice/app/inventory/orders/inbound/page.tsx` | `ApiError` movido de `@/lib/inventoryApi` a `@/lib/httpClient` | 1 línea de import |
| `uis/backoffice/app/inventory/orders/outbound/page.tsx` | `ApiError` movido de `@/lib/inventoryApi` a `@/lib/httpClient` | 1 línea de import |

**Total de código duplicado eliminado: ~195 líneas** (75 del archivo eliminado + 50 de suppliersApi + 70 de inventoryApi)

---

### 📦 Lo que `httpClient.ts` exporta

| Exportación | Tipo | Descripción |
|---|---|---|
| `ValidationIssue` | `interface` | Formato de error de Pydantic v2 (`loc`, `msg`) |
| `ApiError` | `class extends Error` | Error con código de estado HTTP (`status`) |
| `extractErrorMessage()` | `function` | Extrae mensaje legible de respuestas FastAPI (soporta `detail` string o array Pydantic) |
| `request<T>()` | `function` | Request genérico autenticado: lee JWT, adjunta Bearer, maneja 401, extrae errores |
| `jsonRequest()` | `function` | Helper para POST/PUT/PATCH con `content-type: application/json` |
| `requestAuth()` | `function` | Alias de `request()` (deprecado) |

---

### 🧠 Detalle de la refactorización

#### suppliersApi.ts

**Antes:** Contenía su propio `handle401()`, `getAuthHeaders()`, `request<T>()` y `jsonInit` — exactamente el mismo patrón que `authHttpClient.ts` pero con mensaje de error genérico (`"Error de comunicación con el servidor"`) sin extracción del body.

**Después:** Importa `request` y `jsonRequest` desde `./httpClient`. Las funciones de negocio (`fetchSuppliers`, `createSupplier`, `updateSupplierRate`, `updateSupplierStatus`, `archiveSupplier`) quedan exactamente igual en su interfaz pública, pero internamente usan el cliente centralizado.

Empresa:
```typescript
// Antes (duplicado)
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = { ...init?.headers, ...getAuthHeaders() };
  const response = await fetch(url, { ...init, headers });
  if (response.status === 401) { handle401(); throw new Error("..."); }
  if (!response.ok) throw new Error("Error de comunicación...");
  ...
}

// Después (importado)
import { request, jsonRequest } from "./httpClient";
```

#### inventoryApi.ts

**Antes:** Tenía su propia implementación completa de `request<T>()` con `getAuthHeaders()`, `handle401()`, `extractErrorMessage()`, `ValidationIssue` y `ApiError` — además de lógica específica para el proxy de Next.js (`apiPath()`, `API_BASE_URL`).

**Después:** Mantiene solo la lógica específica de inventario: tipos (`MedicalSupply`, `OrderItem`, etc.), helpers de stock (`getStockLevel`, `getStockLevelLabel`, `getStockLevelColor`), y la resolución de rutas (`API_BASE_URL`, `apiPath()`). La capa HTTP se delega a `httpClient.ts` mediante un wrapper `requestInventory()` que llama a `request<T>()` con la ruta resuelta.

```typescript
// Antes: ~100 líneas de HTTP duplicado
function getAuthHeaders() { ... }
function handle401() { ... }
class ApiError extends Error { ... }
async function request<T>(...) { ... }
function extractErrorMessage(...) { ... }
interface ValidationIssue { ... }

// Después: wrapper de 3 líneas
async function requestInventory<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(apiPath(path), init);
}
```

#### Páginas de inventario (inbound/outbound)

`ApiError` se movió de `@/lib/inventoryApi` a `@/lib/httpClient`. Las páginas de órdenes de entrada y salida ahora importan `ApiError` desde `httpClient`.

---

### ✅ Validación con TypeScript

```bash
$ npx tsc --noEmit
# 0 errores nuevos introducidos por la refactorización
# (los errores preexistentes no están relacionados)
```

No se introdujeron errores nuevos de TypeScript. Los únicos errores reportados son preexistentes:
- `Cannot find module 'react'` — falta de tipos de React en `tsc` aislado (Next.js los resuelve en su propio build)
- `TS2345` en `suppliersApi.test.ts` — preexistente (inferencia de `as const` vs `SupplierCreatePayload`)

---

### 🔍 Hallazgos adicionales

1. **Mensajes de error inconsistentes**: `suppliersApi.ts` usaba un mensaje genérico `"Error de comunicación con el servidor. Inténtalo de nuevo."` que ocultaba el detalle real del servidor. `authHttpClient.ts` ya extraía el mensaje del body (`extractErrorMessage`). Con la consolidación, **todos los errores ahora incluyen el detalle real** devuelto por la API.

2. **`ApiError` con `status`**: La implementación de `inventoryApi.ts` tenía una clase `ApiError` con propiedad `status`, mientras que `authHttpClient.ts` lanzaba un `Error` genérico. Se adoptó `ApiError` como el error estándar, permitiendo a los componentes capturar `err instanceof ApiError` y acceder a `err.status`.

3. **`authHttpClient.ts` vs `httpClient.ts`**: Se creó `httpClient.ts` (nombre más simple) como el punto de consolidación, y se eliminó `authHttpClient.ts`. El contenido de `authHttpClient.ts` era el mejor punto de partida (ya tenía `extractErrorMessage` correcto), pero se mejoró añadiendo `ApiError` y `jsonRequest()`.

4. **`inventoryApi.ts` requiere `apiPath()`**: A diferencia de suppliers (que usa rutas directamente), inventory necesita un wrapper (`requestInventory`) porque sus endpoints pasan por el proxy de Next.js (`/api/inventory/*` → `http://backend:8000/inventory/*`). Este wrapper se simplificó de tener su propia implementación `request<T>()` a ser un mero re-exportador que resuelve la ruta.

> **📌 Nota:** Esta refactorización corresponde a la **Mejora 3** de `AUDIT.md` (*Consolidar el cliente HTTP autenticado en un único punto*). Lo que en AUDIT.md se listó como "Mejora 3 (P1)" se resolvió junto con el Caso 2 de la etapa de refactorización, quedando implementado en el mismo commit (`ae05931`).

---

### ✅ Antes / Después

| Métrica | Antes | Después |
|---|---|---|
| Implementaciones de `request<T>()` | 3 (authHttpClient, suppliersApi, inventoryApi) | 1 (`httpClient.ts`) |
| Implementaciones de `handle401()` | 3 | 1 |
| Implementaciones de `getAuthHeaders()` | 2 (suppliersApi, inventoryApi) | 0 (todo en `request()`) |
| Implementaciones de `extractErrorMessage()` | 2 (authHttpClient, inventoryApi) | 1 |
| Definiciones de `ApiError` | 1 (inventoryApi) | 1 (en `httpClient.ts`, única) |
| Definiciones de `ValidationIssue` | 2 (authHttpClient, inventoryApi) | 1 |
| Archivos con lógica HTTP duplicada | 3 | 0 |
| Líneas de HTTP boilerplate | ~195 | 0 (en `httpClient.ts` consolidadas) |
| Mantenibilidad | Para cambiar manejo de 401, modificar 3 archivos | 1 archivo (`lib/httpClient.ts`) |

**Resultado Lighthouse:** *(Imágenes /audit/after/ Caso 2)*
- Website en inglés → Performance se mantuvo en 98 
- Website en español → Performance se mantuvo en 98 
- Backoffice → Ningún cambio
---

## 3. Mejora 1: Reducción de JavaScript no utilizado en backoffice y website (Mejora 1 de AUDIT.md)

### 📋 Resumen

Se implementaron las optimizaciones propuestas en la **Mejora 1** de `AUDIT.md` para atacar el problema de JavaScript no utilizado que Lighthouse reportó en ambos frontends (544–560 KiB de JS sin usar). Las acciones concretas fueron:

1. **Habilitar `experimental.optimizePackageImports`** en los `next.config.ts` de website y backoffice
2. **Instalar `@next/bundle-analyzer`** como dependencia de desarrollo en ambos proyectos
3. **Agregar script `analyze`** para ejecutar el análisis visual de bundles
4. **Verificar la ausencia de imports barrel** y documentar el estado actual de las importaciones

---

### 🏗️ Archivos modificados

| Archivo | Cambio |
|---|---|
| `uis/website/next.config.ts` | Agregado `experimental.optimizePackageImports: ["@/components", "@/data"]` |
| `uis/backoffice/next.config.ts` | Agregado `experimental.optimizePackageImports: ["@/components", "@/lib", "@/types"]` |
| `uis/website/package.json` | Agregado script `"analyze": "ANALYZE=true next build"` + devDep `@next/bundle-analyzer` |
| `uis/backoffice/package.json` | Agregado script `"analyze": "ANALYZE=true next build"` + devDep `@next/bundle-analyzer` |

---

### 🔬 Detalle de cada optimización

#### 1. `experimental.optimizePackageImports`

Next.js 16 con Turbopack permite listar paquetes cuyas importaciones deben optimizarse durante el tree-shaking. Cuando se importa desde un directorio barrel (ej. `import { X } from "@/components"`), este flag hace que Next.js solo incluya en el bundle final los submódulos efectivamente usados, en lugar del archivo barrel completo.

```typescript
// uis/website/next.config.ts
experimental: {
  optimizePackageImports: ["@/components", "@/data"],
}

// uis/backoffice/next.config.ts
experimental: {
  externalDir: true,
  optimizePackageImports: ["@/components", "@/lib", "@/types"],
}
```

#### 2. `@next/bundle-analyzer` + script `analyze`

Se instaló `@next/bundle-analyzer` y se agregó el script personalizado:

```bash
npm run analyze
```

Que ejecuta `ANALYZE=true next build` y genera reportes visuales interactivos en `.next/analyze/` (`client.html`, `server.html`, `edge.html`). Esto permite inspeccionar:

- Módulos más pesados por ruta
- Módulos compartidos entre rutas
- Dependencias duplicadas
- Código legacy que puede eliminarse

#### 3. Verificación de imports barrel

Se revisaron todas las importaciones en ambos proyectos:

- **Website**: Todos los imports son directos a archivo (`@/components/SiteHeader`, `@/data/content`, etc.). No existe ningún barrel `index.ts` en `components/` ni `data/`.
- **Backoffice**: Todos los imports son directos a archivo (`@/components/IncidentListPanel`, `@/lib/httpClient`, etc.). No existe ningún barrel `index.ts` en `components/`, `lib/` ni `types/`.

---

### 🔍 Hallazgos adicionales

1. **No hay barrels activos**: A diferencia de lo que se sugería en AUDIT.md, **ningún componente** importa desde un barrel genérico. Todos los imports en website y backoffice son directos a archivo. Esto significa que el impacto inmediato de `optimizePackageImports` es principalmente **preventivo**: protege contra futuros barrels que pudieran crearse.

2. **Los 544–560 KiB de JS no usado** reportados por Lighthouse probablemente corresponden a:
   - Código incluido por defecto en el bundle de desarrollo (Lighthouse se midió en modo dev)
   - Código legacy del milestone anterior (`src/types/models.ts`, `src/utils/`) que se importa en `app/page.tsx` del backoffice
   - Runtime de Next.js y React, que es compartido entre todas las rutas

3. **El build del backoffice tiene un error preexistente**: El archivo `app/page.tsx` importa desde `../src/types/models` y `../src/utils/` usando rutas relativas que Turbopack en Next.js 16.2.11 no resuelve correctamente, a pesar de tener `externalDir: true`. Este error **no fue introducido por esta refactorización** — se verificó haciendo `git stash` y ejecutando `next build` sin los cambios, obteniendo el mismo error.

4. **El build del website compila correctamente** ✅ con la nueva configuración.

---

### ✅ Validación

```bash
# Website — build exitoso con nueva config
$ cd uis/website && npx next build
✓ Compiled successfully in 11.2s
✓ Generating static pages (6/6) in 218ms
# Experiments: optimizePackageImports (activo)

# Backoffice — error preexistente (Turbopack + externalDir)
$ cd uis/backoffice && npx next build
✗ Module not found: Can't resolve '../src/types/models'
# Error preexistente, no relacionado con los cambios de esta mejora
```

---

### 📊 Antes / Después

| Métrica | Antes | Después |
|---|---|---|
| `optimizePackageImports` en website | No configurado | `["@/components", "@/data"]` |
| `optimizePackageImports` en backoffice | No configurado | `["@/components", "@/lib", "@/types"]` |
| `@next/bundle-analyzer` instalado | No | Sí, en ambos proyectos |
| Script `analyze` disponible | No | `npm run analyze` en ambos |
| Build website | ✅ | ✅ |
| Build backoffice | ❌ (preexistente) | ❌ (mismo error preexistente) |

**Resultado Lighthouse:** *(Imágenes /audit/after/ Mejora 1)*
- Website en inglés → Performance se mantuvo en 98
- Website en español → Performance se mantuvo en 98 
- Backoffice → Ningún cambio 

---

## 4. Mejora 2: Optimización de LCP con `fetchpriority="high"` en la imagen hero (Mejora 2 de AUDIT.md)

### 📋 Resumen

Se implementó la **Mejora 2** de `AUDIT.md` para optimizar el Largest Contentful Paint (LCP) en el website corporativo. Lighthouse reportaba LCP de **2.5s** (inglés) y **4.7s** (español), con la recomendación explícita de aplicar `fetchpriority="high"` a la imagen hero y evitar `loading="lazy"` en el recurso LCP.

La acción concreta fue añadir la propiedad `priority` al componente `<Image>` de Next.js en `LandingPage.tsx`, que es el componente compartido por las 3 rutas del website (`/`, `/en`, `/es`).

---

### 🏗️ Archivo modificado

| Archivo | Cambio |
|---|---|
| `uis/website/components/LandingPage.tsx` | Añadida prop `priority` al `<Image>` de la imagen hero (línea 58) |

---

### 🔬 Detalle del cambio

**Antes:**
```tsx
<Image
  src="https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=1400&q=80"
  alt={content.heroImageAlt}
  className="h-72 w-full rounded-xl object-cover sm:h-80 lg:h-[26rem]"
  width={1400}
  height={832}
/>
```

**Después:**
```tsx
<Image
  priority
  src="https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=1400&q=80"
  alt={content.heroImageAlt}
  className="h-72 w-full rounded-xl object-cover sm:h-80 lg:h-[26rem]"
  width={1400}
  height={832}
/>
```

**¿Qué hace `priority` en Next.js `Image`?**

- Aplica `fetchpriority="high"` en el `<img>` renderizado, indicando al navegador que este recurso es prioritario frente a otros
- Elimina automáticamente `loading="lazy"` (que es el valor por defecto en Next.js Image), evitando que la imagen LCP se cargue con lazy loading
- Precarga el recurso añadiendo un `<link rel="preload" as="image">` en el `<head>`, lo que adelanta el descubrimiento de la imagen

---

### 🔍 Cobertura del cambio

El cambio beneficia a las **3 rutas del website** simultáneamente:

| Ruta | Idioma | Contenido | Componente hero | ¿Afectado? |
|------|--------|-----------|-----------------|------------|
| `/` | Inglés | `englishContent` | `LandingPage.tsx` | ✅ Sí |
| `/en` | Inglés | `englishContent` | `LandingPage.tsx` | ✅ Sí |
| `/es` | Español | `spanishContent` | `LandingPage.tsx` | ✅ Sí |

No fue necesario modificar nada adicional: el componente `LandingPage.tsx` es el mismo para todos los idiomas; solo cambia la prop `content` que recibe.

---

### ✅ Validación

```bash
$ cd uis/website && npx next build
✓ Compiled successfully in 10.8s
✓ Generating static pages (6/6) in 188ms

Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /application
├ ○ /en
└ ○ /es
```

El build de producción se completa sin errores, con las 6 rutas generadas correctamente como contenido estático.

---

### 📊 Antes / Después

| Métrica | Antes | Después |
|---|---|---|
| Prop `priority` en imagen hero | ❌ No presente | ✅ `priority` añadido |
| `fetchpriority="high"` en HTML | No generado | Generado automáticamente por Next.js |
| `loading="lazy"` en imagen hero | ✅ Sí (por defecto en Next.js Image) | ❌ Eliminado por `priority` |
| `<link rel="preload">` en `<head>` | No (solo si Next.js lo decide) | Generado para la imagen hero |
| Cobertura (rutas beneficiadas) | 0 | 3 (`/`, `/en`, `/es`) |
| Build producción | ✅ | ✅ |
| Líneas modificadas | 0 | 1 (adición de `priority`) |

**Resultado Lighthouse:** *(Imágenes /audit/after/ Mejora 2)*
- Website en inglés → Performance aumentó a 99
- Website en español → Performance se mantuvo en 98 
- Backoffice → Ningún cambio 

---

## 5. Mejora 6: Abstraer estados de carga, error y vacío en componentes reutilizables (Mejora 6 de AUDIT.md)

### 📋 Resumen

Se detectaron **3 patrones visuales repetidos** en componentes del backoffice que cargan datos desde API:

1. **Loading**: SVG spinner con mensaje de texto, envuelto en contenedor `main` con padding
2. **Error**: Bloque rojo con título, mensaje y botón "Reintentar", envuelto en contenedor `main`
3. **Vacío**: Mensaje centrado cuando `data.length === 0`

Cada componente implementaba estos patrones de forma manual, generando ~80 líneas duplicadas por componente. Se extrajeron a 3 componentes reutilizables en `components/ui/`.

---

### 🏗️ Archivos creados

| Archivo | Propósito | Líneas |
|---|---|---|
| `components/ui/LoadingSpinner.tsx` | Spinner animado con mensaje opcional | 39 |
| `components/ui/ErrorMessage.tsx` | Bloque de error con reintento y variantes | 74 |
| `components/ui/EmptyState.tsx` | Mensaje de lista vacía con icono y acción | 44 |
| `components/ui/index.ts` | Barrel export | 3 |

---

### 🔧 Archivos refactorizados

| Archivo | Loading Antes → Después | Error Antes → Después | Vacío Antes → Después |
|---|---|---|---|
| `IncidentListPanel.tsx` | 22 líneas inline → 1 línea `<LoadingSpinner>` | 18 líneas inline → 7 líneas `<ErrorMessage>` | — |
| `IncidentSummaryPanel.tsx` | 16 líneas inline → 1 línea `<LoadingSpinner>` | 18 líneas inline → 7 líneas `<ErrorMessage>` | — |
| `IncidentsManagerClient.tsx` | 4 líneas inline → 1 línea `<LoadingSpinner>` | 16 líneas inline → 7 líneas `<ErrorMessage>` | — |
| `app/inventory/products/page.tsx` | 10 líneas inline → 1 línea `<LoadingSpinner>` | 10 líneas inline → 5 líneas `<ErrorMessage>` | 5 líneas → 1 línea `<EmptyState>` |
| `app/inventory/orders/page.tsx` | 10 líneas inline → 1 línea `<LoadingSpinner>` | 10 líneas inline → 5 líneas `<ErrorMessage>` | 7 líneas → 1 línea `<EmptyState>` |

---

### 📦 Componentes creados

| Componente | Props | Variantes |
|---|---|---|
| `<LoadingSpinner>` | `message`, `fullPage`, `size` (sm/md/lg), `className` | `fullPage`: contenedor con padding; `!fullPage`: solo spinner+texto |
| `<ErrorMessage>` | `title`, `message`, `onRetry`, `retryLabel`, `variant` (error/warning/info), `fullPage`, `className` | 3 variantes de color (rojo, ámbar, azul) |
| `<EmptyState>` | `message`, `description`, `icon`, `action`, `fullPage`, `className` | Con/sin contenedor, con/sin acción |

---

### 📐 Patrón de uso

```tsx
// Antes — ~22 líneas repetitivas por componente
if (isLoading) {
  return (
    <main className="mx-auto ...">
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-600 border-t-transparent" />
        <p className="ml-3 text-sm text-slate-500">Cargando...</p>
      </div>
    </main>
  );
}

if (error) {
  return (
    <main className="mx-auto ...">
      <div className="rounded-xl border border-red-200 bg-red-50 p-4">
        <p className="text-sm font-medium text-red-800">Error</p>
        <p className="mt-1 text-sm text-red-600">{error}</p>
      </div>
    </main>
  );
}

// Después — 2 líneas
if (isLoading) return <LoadingSpinner message="Cargando..." />;
if (error) return <ErrorMessage title="Error" message={error} fullPage />;
```

---

### 🧩 Componentes NO refactorizados (intencionalmente)

| Componente | Razón |
|---|---|
| `SuppliersDirectoryClient.tsx` | Usa loading inline en tabla (`aria-live`), errores inline en `<div>` de feedback, vacío como fila de tabla — no aplica el patrón full-page |
| `IncidentsAnalyzerClient.tsx` | Solo tiene estados de formulario (submitting, download), no loading/error de listado |
| `InboundOrderPage.tsx` / `OutboundOrderPage.tsx` | Formularios: usan loading inline en `<select>` y errores inline como feedback post-submit |
| Páginas de auth (login, register, etc.) | Estados de formulario, no listados de datos |

---

### ✅ Validación

```bash
$ cd uis/backoffice && npx tsc --noEmit
# Solo errores pre-existentes (test types, ../src/ module resolution, string indexing)
# 0 errores nuevos introducidos por este cambio
```

**Build de producción backoffice:** No se ejecuta `next build` porque existe un error pre-existente de module resolution con `../src/` en Turbopack (`app/page.tsx`), no relacionado con este cambio.

El build del **website** se ejecuta sin errores:

```bash
$ cd uis/website && npx next build
✓ Compiled successfully
```

---

### 📊 Antes / Después

| Métrica | Antes | Después |
|---|---|---|
| Líneas de UI state duplicadas (5 componentes) | ~110 líneas inline | ~20 líneas de componentes reutilizables |
| Componentes reutilizables | 0 | 3 |
| Variantes de color en errores | Solo rojo | 3 (rojo, ámbar, azul) |
| Tamaño de spinner configurable | No | sm/md/lg |
| Icono/acción en estado vacío | No | Sí (props `icon`, `action`) |
| Cobertura (componentes refactorizados) | 0 | 5 |
| Líneas de código eliminadas | — | **~90 líneas** |

**Resultado Lighthouse:** *(Imágenes /audit/after/ Mejora 6)*
- Website en inglés → Performance se mantuvo en 99
- Website en español → Performance aumentó a 99
- Backoffice → Performance aumentó a 81 

---

### 🎯 Mejoras descartadas (proyecto personal — no aplican)

Las siguientes mejoras de AUDIT.md se evaluaron y se descartan por tratarse de un proyecto personal sin despliegue público actual:

| Mejora | Motivo |
|---|---|
| **Mejora 5** — Resolver bloqueo SEO (noindex) | El `noindex` es **correcto y deseable** en entornos de desarrollo/proyectos personales. Impide que Google indexe contenido no destinado a producción. No hay nada que resolver. |
| **Mejora 7** — Minificar/comprimir assets | Lighthouse reportaba ahorros en `next dev`, pero en producción (`next build`) Next.js ya minifica y comprime automáticamente con Turbopack. No requiere acción adicional. |

---

### ✅ Resumen final del ciclo de mejoras

| Mejora | Estado |
|---|---|
| Caso 1 — Duplicación | ✅ Implementada |
| Caso 2 — Cliente HTTP autenticado | ✅ Implementada |
| Mejora 1 — JS no utilizado | ✅ Implementada |
| Mejora 2 — Optimizar LCP | ✅ Implementada |
| Mejora 3 — Cliente HTTP | ✅ Ya implementada (Caso 2) |
| Mejora 4 — Tipos duplicados | ✅ Ya implementada (Caso 1) |
| Mejora 5 — SEO noindex | ❌ Descartada — proyecto personal |
| Mejora 6 — Estados UI reutilizables | ✅ Implementada |
| Mejora 7 — Minificar assets | ❌ Descartada — proyecto personal |

