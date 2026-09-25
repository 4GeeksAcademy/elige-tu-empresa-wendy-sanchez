# AUDITORÍA INICIAL DE HEALTHCORE

El proyecto de HealthCore se divide en 2 partes, los cuales actualmente corren mediante Docker, por ende primero me aseguré que ambos corrieran sin problemas antes de empezar la inspección con los Dev.Tools → Lighthouse 

| Aplicación | Puerto |   URL   | Estado |
|----------- | ------ | ------- | ------ |
| Website | 3000 | http://localhost:3000 | ✅ Corriendo |
| Backoffice | 3001 | http://localhost:3001 | ✅ Corriendo |

## WEBSITE - SITIO WEB CORPORATIVO

En el caso de la website pública se tienen 2 (una en español y otra en inglés), por lo tanto se hizo una medición por medio de Lighthouse de ambas, obteniendo los siguientes resultados:

### Website en inglés:
- Performance: 97
- Accessibility: 100
- Best practice: 77 
  - Uses third-party cookies - 2 cookies found
  - Issues were logged in the Issues panel in Chrome Devtools 
  - Missing source maps for large first-party JavaScript 
- SEO: 63 → Page is blocked from indexing

Adicional se tomaron en cuenta los siguientes **Core Web Vitals**:
- First Contentful Paint (FCP): 1.1 s
- Largest Contentful Paint (LCP): 2.5 s
- Total Blocking Time (TBT): 60 ms
- Cumulative Layout Shift (CLS): 0
- Speed Index: 1.1 s 
- Interaction to Next Paint (INP): 30 ms

**LCP request discovery:**
Optimize LCP by making the LCP image discoverable from the HTML immediately, and avoiding lazy-loading
- fetchpriority=high should be applied
- Request is discoverable in initial document
- LCP resources should not use loading=lazy

**Network dependency tree:**
Avoid chaining critical requests by reducing the length of chains, reducing the download size of resources, or deferring the download of unnecessary resources to improve page load.

Maximum critical path latency: 1,401 ms

**Others:**
- Minify CSS - Est savings of 8 KiB
- Minify JavaScript - Est savings of 182 KiB
- Reduce unused CSS - Est savings of 19 KiB
- Reduce unused JavaScript Est savings of 544 KiB 

---
### Website en español:
- Performance: 83
- Accessibility: 100
- Best practice: 77 
  - Uses third-party cookies - 2 cookies found
  - Issues were logged in the Issues panel in Chrome Devtools 
  - Missing source maps for large first-party JavaScript 
- SEO: 63 → Page is blocked from indexing

Adicional se tomaron en cuenta los siguientes **Core Web Vitals**:
- First Contentful Paint (FCP): 1.1 s
- Largest Contentful Paint (LCP): 4.7 s
- Total Blocking Time (TBT): 50 ms
- Cumulative Layout Shift (CLS): 0
- Speed Index: 1.3 s 
- Interaction to Next Paint (INP): 30 ms

**LCP request discovery:**
Optimize LCP by making the LCP image discoverable from the HTML immediately, and avoiding lazy-loading 
- fetchpriority=high should be applied
- Request is discoverable in initial document
- LCP resources should not use loading=lazy

**Network dependency tree:**
Avoid chaining critical requests by reducing the length of chains, reducing the download size of resources, or deferring the download of unnecessary resources to improve page load.

Maximum critical path latency: 2,110 ms

**Render-blocking requests**

**Legacy JavaScript - Est savings of 8 KiB**

**Others:**
- Minify JavaScript - Est savings of 165 KiB
- Reduce unused JavaScript - Est savings of 472 KiB
- Minify CSS - Est savings of 8 KiB
- Reduce unused CSS - Est savings of 19 KiB

## BACKOFFICE
- Performance: 80
- Accessibility: 96 → Background and foreground colors do not have a sufficient contrast ratio.
- Best practice: 100
- SEO: 60 → Page is blocked from indexing

Adicional se tomaron en cuenta los siguientes **Core Web Vitals**:
- First Contentful Paint (FCP): 0.9 s
- Largest Contentful Paint (LCP): 5.3 s
- Total Blocking Time (TBT): 70 ms
- Cumulative Layout Shift (CLS): 0
- Speed Index: 0.9 s 
- Interaction to Next Paint (INP): 40 ms

**Network dependency tree:**
Avoid chaining critical requests by reducing the length of chains, reducing the download size of resources, or deferring the download of unnecessary resources to improve page load.

Maximum critical path latency: 1,858 ms

**Render-blocking requests**

**Legacy JavaScript - Est savings of 8 KiB**

**Others:**
- Minify JavaScript - Est savings of 182 KiB
- Reduce unused JavaScript - Est savings of 560 KiB
- Minify CSS - Est savings of 8 KiB
- Reduce unused CSS - Est savings of 19 KiB

---

## ANÁLISIS DE DUPLICACIÓN Y REFACTORIZACIÓN

### Caso 1 — Tipos, constantes y mapeos de incidencias duplicados en 4 componentes

**Dónde aparece:**

| Archivo | Líneas duplicadas |
|---------|------------------|
| `uis/backoffice/components/IncidentListPanel.tsx` | Types `IncidentStatus`, `IncidentCategory`, `IncidentOrigin` + `STATUS_LABELS`, `STATUS_COLORS`, `CATEGORY_LABELS`, `BRANCH_LABELS`, `ALL_STATUSES`, `ALL_CATEGORIES`, `ALL_BRANCHES`, `STATUS_OPTIONS` (~70 líneas) |
| `uis/backoffice/components/IncidentRegisterForm.tsx` | Mismos types + `ORIGIN_LABELS`, `STATUS_LABELS`, `CATEGORY_LABELS`, `BRANCHES`, `ALL_CATEGORIES`, `ALL_ORIGINS`, `ALL_STATUSES` (~60 líneas) |
| `uis/backoffice/components/IncidentSummaryPanel.tsx` | `STATUS_LABELS`, `STATUS_ORDER`, `CATEGORY_LABELS`, `BRANCH_LABELS` (~45 líneas) |
| `uis/backoffice/components/IncidentsManagerClient.tsx` | Todos los types (`Incident`, `IncidentSummary`, `IncidentStatus`, `IncidentCategory`, `IncidentOrigin`) + `STATUS_LABELS`, `STATUS_COLORS`, `CATEGORY_LABELS`, `ORIGIN_LABELS`, `VALID_BRANCHES`, `IncidentFormState` (~80 líneas) |

**Por qué es candidato a refactorización:**

- **Violación DRY**: El mismo contrato de datos (tipos, enums, labels, colores) está definido 4 veces de forma casi idéntica. Cualquier cambio en una categoría, sucursal o label requiere modificar 4 archivos.
- **Riesgo de inconsistencia**: Si se añade una nueva categoría ("pharmacy" por ejemplo) y no se actualizan los 4 archivos, algunos componentes mostrarán labels indefinidos o faltantes.
- **Código inflado**: Se pierden ~250 líneas en definiciones redundantes.
- **Sin capa de datos compartida**: A diferencia de `inventoryApi.ts` que sí centraliza sus tipos y helpers, los componentes de incidencias no tienen un archivo `incidents.ts` común.

**Cómo quedaría la abstracción compartida:**

Crear un archivo `uis/backoffice/lib/incidents.ts` (o `/types/incident.ts`) que exporte:

```typescript
// ── Tipos ─────────────────────────────────────────────────────────────
export type IncidentStatus = "open" | "in_progress" | "resolved" | "discarded";
export type IncidentCategory =
  | "clinical_equipment" | "it_system" | "billing_error"
  | "compliance_breach" | "patient_experience" | "staff_issue"
  | "facility_issue" | "referral_issue" | "other";
export type IncidentOrigin = "customer" | "branch" | "internal";

export interface Incident {
  id: number;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: string;
  branch_label: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentFormState {
  title: string;
  description: string;
  category: IncidentCategory | "";
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: string;
}

export interface IncidentSummary {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  by_branch: Record<string, number>;
  by_origin: Record<string, number>;
}

// ── Constantes ─────────────────────────────────────────────────────────
export const STATUS_LABELS: Record<IncidentStatus, string> = { /* ... */ };
export const STATUS_COLORS: Record<IncidentStatus, string> = { /* ... */ };
export const CATEGORY_LABELS: Record<IncidentCategory, string> = { /* ... */ };
export const ORIGIN_LABELS: Record<IncidentOrigin, string> = { /* ... */ };
export const BRANCH_LABELS: Record<string, string> = { /* ... */ };
export const STATUS_OPTIONS = [ /* ... */ ];
export const ALL_STATUSES: IncidentStatus[] = [ /* ... */ ];
export const ALL_CATEGORIES: IncidentCategory[] = [ /* ... */ ];
export const ALL_BRANCHES = Object.keys(BRANCH_LABELS);
```

Cada componente importaría desde `@/lib/incidents` en lugar de redefinir. El `API_BASE` también podría ir ahí.

---

### Caso 2 — Cliente HTTP autenticado implementado 3 veces con lógica casi idéntica

**Dónde aparece:**

| Archivo | Rol | Lógica duplicada |
|---------|-----|-----------------|
| `uis/backoffice/lib/authHttpClient.ts` | Cliente HTTP genérico con JWT, extractErrorMessage, handle401 | ~75 líneas |
| `uis/backoffice/lib/suppliersApi.ts` | Cliente específico de suppliers con su propio `request<T>()`, `getAuthHeaders()`, `handle401()` | ~50 líneas |
| `uis/backoffice/lib/inventoryApi.ts` | Cliente de inventario con fetch inline y `getToken()` repetido | Lectura manual de token y manejo de errores inline |

**Por qué es candidato a refactorización:**

- **Misma responsabilidad**: Los tres módulos necesitan: (1) leer token de localStorage, (2) adjuntar `Authorization: Bearer`, (3) manejar 401 con redirección a `/login`, (4) extraer mensajes de error del cuerpo de la respuesta.
- **Patrón divergente**: `authHttpClient.ts` expone `request<T>()` genérico con tipado estricto y `extractErrorMessage()`. `suppliersApi.ts` reinventa el mismo `request<T>()` pero sin `extractErrorMessage`. `inventoryApi.ts` no usa ninguno de los dos y hace fetch directo con su propio `getToken()`.
- **Mantenibilidad**: Para cambiar la lógica de renovación de token, manejo de 401 o formato de errores, hay que modificar 3 implementaciones distintas.
- **No hay un único punto de entrada HTTP** para el backoffice; cada módulo de features (suppliers, inventory, incidents) tiene su propia estrategia.

**Cómo quedaría la abstracción compartida:**

Consolidar todo en `authHttpClient.ts` como el único cliente HTTP del backoffice, y hacer que los módulos específicos lo extiendan sin reimplementar:

```typescript
// lib/httpClient.ts — Único cliente HTTP del backoffice
import { getToken, removeToken } from "./auth";

export interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

export function extractErrorMessage(payload: unknown, fallback: string): string {
  // ... implementación única ...
}

function handle401() {
  if (typeof window !== "undefined") {
    removeToken();
    window.location.href = "/login";
  }
}

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const response = await fetch(url, { ...init, headers });

  if (response.status === 401) {
    handle401();
    throw new Error("Sesión expirada. Redirigiendo al inicio de sesión...");
  }

  if (!response.ok) {
    let payload: unknown = null;
    try { payload = await response.json(); } catch { /* ignore */ }
    throw new Error(extractErrorMessage(payload, `Error ${response.status}`));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// helpers para métodos HTTP comunes
export const jsonRequest = <T>(method: string, url: string, body: unknown): Promise<T> =>
  request<T>(url, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
```

Luego `suppliersApi.ts` e `inventoryApi.ts` importarían desde `@/lib/httpClient`:

```typescript
// suppliersApi.ts — Solo lógica de negocio, sin reimplementar HTTP
import { request, jsonRequest } from "./httpClient";
import type { Supplier, SupplierCreatePayload, SupplierFilters, SupplierStatus } from "../types/supplier";

export function fetchSuppliers(filters: SupplierFilters = {}): Promise<Supplier[]> {
  const params = new URLSearchParams();
  if (filters.country) params.set("country", filters.country);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  return request<Supplier[]>(`/api/suppliers${query ? `?${query}` : ""}`);
}

export function createSupplier(payload: SupplierCreatePayload): Promise<Supplier> {
  return jsonRequest<Supplier>("POST", "/api/suppliers", payload);
}
```

Para `inventoryApi.ts` se eliminaría el fetch manual y se usaría `request<T>()` del cliente centralizado, manteniendo solo los tipos específicos y helpers de stock.

---

## EJECUCIÓN DE SKILLS DE CALIDAD WEB

A continuación se aplican los marcos de análisis de las 3 skills disponibles (`core-web-vitals`, `performance`, `web-perf`) sobre los resultados de Lighthouse ya capturados en las secciones anteriores. Dado que no se dispone de Chrome DevTools MCP en el entorno actual, el análisis se realiza sobre las trazas y métricas de laboratorio disponibles.

### Skill: core-web-vitals

Aplicando el marco de análisis de Core Web Vitals sobre las 3 páginas medidas:

| Página | LCP | INP | CLS | Diagnóstico CWV |
|--------|-----|-----|-----|-----------------|
| Website (EN) | 2.5 s ✅ | 30 ms ✅ | 0 ✅ | **Good** — LCP en el límite justo de 2.5s |
| Website (ES) | 4.7 s ❌ | 30 ms ✅ | 0 ✅ | **Poor** — LCP supera 4s, categoría "poor" |
| Backoffice | 5.3 s ❌ | 40 ms ✅ | 0 ✅ | **Poor** — LCP muy por encima de 4s |

**Análisis detallado de cada métrica:**

**LCP — Website inglés (2.5s):**
- En el límite exacto del umbral "good" (≤ 2.5s). Cualquier regresión lo empeoraría.
- La traza de Lighthouse indica que el LCP *request discovery* está presente: la imagen hero es descubrible en el documento inicial, pero no tiene `fetchpriority="high"`.
- Cadena crítica máxima: 1,401 ms. Hay 1.4s de latencia en la cadena de dependencias de red.
- La imagen hero proviene de Unsplash (CDN externo), lo que añade latencia de conexión.

**LCP — Website español (4.7s):**
- Supera ampliamente el umbral "poor" (> 4s). Es la métrica más crítica del sitio.
- Misma estructura que la versión EN, pero carga una imagen Unsplash diferente y tiene cadenas de requests más largas (2,110 ms de latencia crítica máxima).
- La diferencia respecto a EN (4.7s vs 2.5s) sugiere que el tamaño/bytes de la imagen hero en español es mayor o que la conexión a Unsplash es más lenta en esa ruta.
- Render-blocking requests detectados: recursos que bloquean el primer pintado.

**LCP — Backoffice (5.3s):**
- Es el peor LCP de los 3. 5.3s es más del doble del umbral "good".
- Hay render-blocking requests y cadenas de dependencias críticas de 1,858 ms.
- Legacy JavaScript con 8 KiB de ahorro estimado: hay scripts antiguos que se pueden diferir.
- JavaScript sin usar: 560 KiB — casi medio mega de JS que se descarga y parsea sin necesidad.

**INP — Todos (30-40ms):**
- Todos los frontends están muy por debajo del umbral "good" (≤ 200ms). La interactividad no es un problema en estos momentos.

**CLS — Todos (0):**
- No hay desplazamiento acumulativo de layout. Las imágenes tienen dimensiones explícitas (`width`/`height` en Next.js Image). Sin problemas de estabilidad visual.

---

### Skill: performance

Aplicando el marco de optimización de rendimiento sobre los resultados existentes:

**Presupuesto de rendimiento estimado vs. real:**

| Recurso | Presupuesto sugerido | Website (estimado) | Backoffice (estimado) | Diagnóstico |
|---------|---------------------|-------------------|---------------------|-------------|
| Peso total página | < 1.5 MB | Supera (por JS no usado) | Supera (por JS no usado) | ❌ |
| JavaScript (comprimido) | < 300 KB | ~544 KB sin usar | ~560 KB sin usar | ❌ |
| CSS (comprimido) | < 100 KB | ~19 KB sin usar | ~19 KB sin usar | ⚠️ Borde |
| Imágenes (above-fold) | < 500 KB | LCP image de Unsplash | N/A | ⚠️ |
| Fuentes | < 100 KB | No detectado | No detectado | ✅ |
| Terceros | < 200 KB | Unsplash CDN | No detectado | ⚠️ |

**Hallazgos de rendimiento clave:**

1. **JavaScript no utilizado** (544-560 KiB de ahorro estimado): Es el problema dominante en los 3 frontends. Next.js 16 con Turbopack genera bundles grandes que incluyen código de componentes no renderizados en la ruta actual. Habilitar `experimental.optimizePackageImports` y revisar importaciones barrel puede reducirlo.

2. **Minificación**: Hay ahorros significativos (165-182 KiB en JS, 8 KiB en CSS). Aunque Turbopack ya minifica en producción, en desarrollo no lo hace. Estos valores pueden corresponder a la medición en modo dev.

3. **Cadenas de requests críticas**: 1,401ms (EN), 2,110ms (ES) y 1,858ms (backoffice) de latencia máxima en la ruta crítica. Implica que recursos necesarios para el primer pintado dependen de otros recursos que se cargan secuencialmente.

4. **Render-blocking resources**: Presentes en website (ES) y backoffice. Archivos CSS/JS que bloquean el primer renderizado.

5. **Legacy JavaScript**: 8 KiB de ahorro estimado en ambas versiones del website y backoffice. Scripts que pueden diferirse o eliminarse.

6. **Third-party cookies (website)**: 2 cookies de terceros detectadas. Impactan best practices y pueden añadir latencia.

---

### Skill: web-perf Auditoría Integral

Aplicando el flujo de trabajo y guías de referencia de web-perf sobre los datos disponibles:

**Resumen de señales por frontend:**

| Señal | Website EN | Website ES | Backoffice |
|-------|-----------|-----------|------------|
| **Lighthouse Performance** | 97 ✅ | 83 ⚠️ | 80 ⚠️ |
| **Lighthouse Accessibility** | 100 ✅ | 100 ✅ | 96 ⚠️ |
| **Lighthouse Best Practices** | 77 ❌ | 77 ❌ | 100 ✅ |
| **Lighthouse SEO** | 63 ❌ | 63 ❌ | 60 ❌ |
| **FCP** | 1.1s | 1.1s | 0.9s |
| **LCP** | 2.5s ⚠️ | 4.7s ❌ | 5.3s ❌ |
| **TBT** | 60ms | 50ms | 70ms |
| **CLS** | 0 ✅ | 0 ✅ | 0 ✅ |
| **Speed Index** | 1.1s | 1.3s | 0.9s |
| **Max critical path latency** | 1,401ms | 2,110ms ❌ | 1,858ms ⚠️ |

**Diagnóstico por categoría Lighthouse:**

**Best Practices (77/100 — website):**
- Uso de cookies de terceros: 2 encontradas. Probablemente rastro de herramientas de análisis o CDN.
- Source maps ausentes para JavaScript first-party grande: impide depurar en producción.
- Issues en consola de Chrome DevTools.

**SEO (60-63/100 — ambos):**
- **Page blocked from indexing**: Es la causa principal de la puntuación baja. Los metadatos `noindex` están bloqueando la indexación en motores de búsqueda. Esto puede ser intencional (entorno de desarrollo) o accidental.
- Las páginas tienen meta descriptions y datos estructurados JSON-LD correctos, lo cual es positivo.

**Accessibility (96/100 — backoffice):**
- Contraste de color insuficiente entre foreground y background: el diseño dark del backoffice (bg-slate-950, text-slate-50) parece tener algún elemento donde el contraste no alcanza la relación 4.5:1 requerida por WCAG AA.

---

## PROPUESTAS DE MEJORA

### Mejora 1 — Reducir JavaScript no utilizado en backoffice y website

**Problema:** Lighthouse reporta entre 472 KiB y 560 KiB de JavaScript no utilizado en todas las páginas. Next.js 16 con Turbopack genera bundles que incluyen código de rutas no visitadas y componentes no utilizados.

**Causa raíz:** Importaciones tipo "barrel" (`import { ... } from "@/components"`), falta de `experimental.optimizePackageImports` en `next.config.ts`, y posiblemente código legacy del milestone anterior que sigue en el árbol de dependencias.

**Propuesta de mejora:**
1. Habilitar en `next.config.ts` de ambos proyectos:
   ```typescript
   experimental: {
     optimizePackageImports: ["@/components", "@/lib"],
   }
   ```
2. Revisar las importaciones en las páginas del backoffice para eliminar imports de componentes no utilizados (tree-shaking manual).
3. Configurar el análisis de bundles con `next build --analyze` (requiere `@next/bundle-analyzer`) para identificar los módulos más pesados.
4. Migrar las importaciones barrel a imports directos de archivo donde sea viable.

**Resultado esperado:**
- Reducción del JS no utilizado de ~550 KiB a < 200 KiB.
- LCP debería mejorar significativamente (especialmente en backoffice, donde 5.3s está muy afectado por el tiempo de parseo de JS).
- Ahorro estimado: 300-350 KiB en transferencia y parseo.

---

### Mejora 2 — Optimizar LCP con fetchpriority y precarga de imagen hero

**Problema:** La imagen LCP (hero de Unsplash en website, y posible contenido principal en backoffice) no está priorizada. El tiempo de LCP en website español (4.7s) y backoffice (5.3s) excede los umbrales aceptables.

**Causa raíz:** Las imágenes hero no llevan `fetchpriority="high"` y en algunos casos pueden estar compitiendo con otros recursos por ancho de banda. El componente `<Image>` de Next.js tiene `loading="lazy"` por defecto, que retrasa la carga del LCP.

**Propuesta de mejora:**
1. En `uis/website/components/LandingPage.tsx`, añadir `priority` a la imagen hero (Next.js Image):
   ```tsx
   <Image
     priority
     src="https://images.unsplash.com/photo-1584515933487-779824d29309"
     alt={content.heroImageAlt}
     className="h-72 w-full rounded-xl object-cover sm:h-80 lg:h-[26rem]"
     width={1400}
     height={832}
   />
   ```
   La prop `priority` en Next.js equivale a `fetchpriority="high"` + elimina `loading=lazy`.
2. Verificar que la imagen hero de la versión en español también tenga `priority`.
3. Evaluar si el Unsplash CDN es necesario en hero o si conviene servir la imagen desde el propio dominio (self-hosting) para evitar latencia de conexión a terceros.

**Resultado esperado:**
- LCP en website español debería bajar de 4.7s a ~2-3s.
- LCP en website inglés debería mejorar de 2.5s a ~1.5s.
- Impacto directo en Lighthouse Performance score (+5-10 puntos).

---

### Mejora 3 — Consolidar el cliente HTTP autenticado en un único punto

**Problema:** El backoffice tiene 3 implementaciones distintas del patrón "fetch + JWT + error handling" (authHttpClient, suppliersApi, inventoryApi). Mantenerlas por separado incrementa el riesgo de bugs, duplica ~150 líneas de código y dificulta cambios como la renovación silenciosa de tokens.

**Causa raíz:** Desarrollo orgánico por features sin una capa de infraestructura compartida. Cada módulo implementó su propio cliente porque no existía un HTTP client estándar al inicio.

**Propuesta de mejora:**
1. Crear (o reforzar) `uis/backoffice/lib/httpClient.ts` como el ÚNICO cliente HTTP del backoffice, exportando `request<T>()`, `extractErrorMessage()` y helpers `jsonRequest`, `formRequest`.
2. Refactorizar `suppliersApi.ts` para que use `request<T>()` y `jsonRequest` de `httpClient.ts` en lugar de su propio `request<T>()`, eliminando `getAuthHeaders()` y `handle401()` internos.
3. Refactorizar `inventoryApi.ts` para que use `request<T>()` de `httpClient.ts` en lugar de fetch directo con `getToken()`, manteniendo solo los tipos (MedicalSupply, OrderItem, etc.) y helpers de clasificación de stock (`getStockLevel()`, `getStockLevelColor()`).
4. Eliminar la función `handle401()` duplicada en suppliersApi.

**Resultado esperado:**
- Reducción de ~150 líneas de código duplicado.
- Un único mantenedor para la lógica de autenticación HTTP.
- Consistencia en el manejo de errores 401 y extracción de mensajes de error.

---

### Mejora 4 — Extraer tipos y constantes compartidas de incidencias

**Problema:** Los tipos `IncidentStatus`, `IncidentCategory`, `IncidentOrigin` y todos los mapeos de labels, colores y sucursales están definidos literalmente en 4 componentes de incidencias (IncidentListPanel, IncidentRegisterForm, IncidentSummaryPanel, IncidentsManagerClient).

**Causa raíz:** No existe un archivo compartido para el dominio "incident". A diferencia de suppliers e inventory, el módulo de incidencias no tiene un `types/incident.ts` ni `lib/incidents.ts`.

**Propuesta de mejora:**
1. Crear `uis/backoffice/types/incident.ts` con las interfaces y tipos del dominio.
2. Crear `uis/backoffice/lib/incidents.ts` con las constantes y mapeos (STATUS_LABELS, CATEGORY_LABELS, BRANCH_LABELS, etc.), incluyendo tipos derivados como `ALL_STATUSES`, `ALL_CATEGORIES`.
3. Eliminar todas las declaraciones duplicadas de los 4 componentes y reemplazarlas por imports desde `@/types/incident` y `@/lib/incidents`.
4. Centralizar `API_BASE` en `lib/incidents.ts` para que no haya 4 constantes iguales.

**Resultado esperado:**
- Eliminación de ~200 líneas de código duplicado.
- Cambios futuros (nueva categoría, sucursal, estado) en un solo archivo.
- Consistencia garantizada entre listado, formulario, resumen y gestor.

---

### Mejora 5 — Resolver el bloqueo de indexación SEO (noindex)

**Problema:** Lighthouse reporta SEO 60-63/100 con "Page is blocked from indexing". Las páginas tienen una directiva `noindex` que impide que Google las indexe.

**Causa raíz:** Revisar el layout raíz (`app/layout.tsx`) y la configuración de Next.js. Es posible que exista un `meta[name="robots"] content="noindex"` o una cabecera `X-Robots-Tag: noindex`. En Next.js, si no se define `metadata.robots` explícitamente, el framework puede inyectar `noindex` en desarrollo.

**Propuesta de mejora:**
1. En `uis/website/app/layout.tsx` y `uis/backoffice/app/layout.tsx`, verificar y establecer explícitamente:
   ```typescript
   export const metadata: Metadata = {
     robots: { index: true, follow: true },
     // ... resto de metadatos
   };
   ```
2. Si el entorno es development, Next.js añade `noindex` automáticamente. Confirmar que la medición de Lighthouse se hizo en producción (`next build && next start`).
3. Si se desea mantener `noindex` en desarrollo, documentarlo y medir solo sobre build de producción.

**Resultado esperado:**
- SEO score pasaría de 63 a 90+.
- El sitio sería indexable por motores de búsqueda, requisito fundamental para un sitio corporativo.

---

### Mejora 6 — Abstraer estados de carga, error y vacío en componentes reutilizables

**Problema:** Múltiples componentes en el backoffice implementan manualmente spinners de carga, mensajes de error y estados vacíos con el mismo patrón Tailwind, duplicando ~20-30 líneas de JSX cada uno.

**Causa raíz:** No existe un sistema de componentes de UI atómico. Cada desarrollador escribe sus propios estados visuales.

**Propuesta de mejora:**
1. Crear componentes UI base compartidos:
   - `components/ui/LoadingSpinner.tsx` — spinner animado reutilizable con texto opcional.
   - `components/ui/ErrorMessage.tsx` — banner de error con icono, mensaje y botón de reintento.
   - `components/ui/EmptyState.tsx` — estado vacío con icono, título y mensaje.
2. Refactorizar IncidentListPanel, IncidentSummaryPanel, products, inbound/outbound para usar estos componentes.

**Resultado esperado:**
- Reducción de ~100-150 líneas de JSX duplicado.
- Consistencia visual en todos los estados de carga, error y vacío.
- Cambios de diseño (colores, animaciones) en un solo lugar.

---

### Mejora 7 — Minificar y comprimir assets en producción

**Problema:** Lighthouse reporta ahorros de 182 KiB en JS, 8 KiB en CSS por minificación no aplicada. También hay 8 KiB de Legacy JavaScript.

**Causa raíz:** Mediciones posiblemente hechas en modo `next dev`, que no aplica minificación ni compresión. En producción (`next build && next start`), Next.js ya minifica automáticamente con Turbopack.

**Propuesta de mejora:**
1. Verificar que las mediciones de Lighthouse se realicen sobre una build de producción (`npm run build && npm run start`), no sobre `next dev`.
2. Si se confirma que es en desarrollo, documentar que los ahorros de minificación se resuelven automáticamente con el build de producción.
3. Habilitar compresión Brotli en el servidor (Nginx/reverse proxy o CDN) para reducir tamaño en transferencia.

**Resultado esperado:**
- Los ahorros de minificación reportados (182 KiB JS, 8 KiB CSS) se resuelven con solo usar producción.
- Compresión Brotli adicional del 15-20% sobre Gzip.