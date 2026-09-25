# REPORTE DE CORRECCIONES APLICADAS

## Caso 1: Duplicación de tipos, constantes y mapeos en 4 componentes de Incidentes

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

### 🔮 Trabajo futuro (Caso 2)

El siguiente paso identificado en la auditoría es la **consolidación de clientes HTTP**: actualmente `IncidentListPanel` usa `fetch` directo, `IncidentsManagerClient` tiene un helper `fetchFromApi`, y el ecosistema tiene `authHttpClient`, `inventoryApi`, `suppliersApi`. Centralizar en un único `httpClient` compartido reduciría duplicación y mejoraría el manejo de errores.
