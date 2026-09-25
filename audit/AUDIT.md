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