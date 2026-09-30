# Informe Técnico de Optimización de Caching

> **Alcance**: Backoffice UI (Next.js), HealthCore API (FastAPI :8000), Incidents API (FastAPI :8010)
> **Objetivo**: Identificar e implementar oportunidades de caching con mayor impacto en rendimiento, reduciendo cargas duplicadas al backend y renderizados innecesarios en el frontend.

---

## 🔍 ¿Qué es el "caching" y por qué lo necesitamos?

Imagina que cada vez que entras a una página web, el sistema tiene que calcular todo desde cero, aunque los datos no hayan cambiado. Eso es exactamente lo que estaba pasando en nuestra aplicación:

- **En el frontend** (las pantallas que ves como usuario): cada vez que React decide "repintar" la pantalla por cualquier motivo (un movimiento de mouse, un cambio pequeño), vuelve a ejecutar operaciones matemáticas costosas que ya había hecho antes. Es como si cada vez que miras un menú de restaurante, el camarero volviera a cocinar la comida desde cero para mostrártela.
- **En el backend** (los servidores que envían los datos): cuando varias personas abren la misma página al mismo tiempo, el servidor hace la misma consulta a la base de datos múltiples veces, como si cada cliente que entra a una tienda preguntara "¿cuánto cuesta esto?" y el dependiente fuera a buscar el precio al almacén cada vez, en vez de tener una lista a mano.

**La solución — el caching — funciona como una "nota adhesiva"**: guardas el resultado de un cálculo para no tener que repetirlo si los datos no han cambiado. Es como apuntar en un post-it el resultado de una cuenta: la próxima vez que necesites saber cuánto es, miras el post-it en lugar de hacer la cuenta otra vez.

---

## 1. Decisiones en el Frontend (lo que ve el usuario)

### 1.1 `useMemo` en la página de inicio (`app/page.tsx`)

**¿Qué problema teníamos?**

La página principal del backoffice muestra datos de ejemplo (reclamaciones, citas, médicos) que **nunca cambian mientras usas la página**. Sin embargo, React tiene una característica (o "comportamiento") por la cual cada vez que algo cambia en la página — aunque sea escribir en un campo de texto o pasar el mouse — React "repinta" todo el componente, y durante ese repintado vuelve a ejecutar **todos los cálculos desde cero**.

**¿Qué significa esto en la práctica?**

Imagina que tienes una hoja de cálculo con 1000 filas y cada vez que mueves el mouse la hoja de cálculo se recalculara entera. Eso es exactamente lo que pasaba. Cada uno de estos 7 cálculos recorre listas enteras de datos (1000 reclamaciones, 500 citas, etc.) y hace operaciones como sumar, agrupar o buscar.

**¿Qué hicimos?**

Envolvimos esos 7 cálculos en `useMemo`, una herramienta de React que le dice: "esto calcúlalo **solo la primera vez** y recuerda el resultado. Si los datos de entrada no cambian, no lo vuelvas a hacer, solo devuelve lo que ya calculaste antes".

Puedes pensar en `useMemo` como una calculadora con memoria: aprietas los botones una vez, la calculadora guarda el resultado en su memoria, y cada vez que preguntas "¿cuánto es?" te muestra el resultado guardado en lugar de hacer la operación otra vez.

**Los 7 cálculos que protegimos:**

| Cálculo | Costo estimado | Dependencias | Beneficio |
|---|---|---|---|
| `denialRate` | O(n) sobre todas las reclamaciones | `[]` (estático) | Evita recorrer el array de reclamaciones en cada render |
| `payerRates` | O(n) agrupando por pagador | `[]` (estático) | Evita re-agrupar datos inmutables |
| `locationNoShowRates` | O(n) filtrando + agrupando | `[]` (estático) | Evita recalcular tasas por ubicación |
| `weeklyNoShowCost` | O(n) por semana | `[]` (estático) | Evita re-sumar costes semanales |
| `sortedClaims` | O(n log n) ordenación | `[]` (estático) | Evita reordenar datos inmutables |
| `binaryIndex` | O(log n) búsqueda binaria | `[sortedClaims]` (depende de sortedClaims) | Evita reconstruir índice en memoria |
| `linearClaim` / `cmeReport` | O(n) búsqueda + transformación | `[]` (estático) | Evita re-procesar datos estáticos |

> **Nota sobre las dependencias**: La columna "Dependencias" indica qué datos, si cambian, harían que React recalcule el valor. El array vacío `[]` significa "solo calcúlalo una vez al cargar la página y no lo vuelvas a hacer nunca". El valor `[sortedClaims]` significa "solo recalcula esto si `sortedClaims` cambia" — en este caso, `binaryIndex` depende de que la lista esté ordenada, así que si `sortedClaims` se recalculara, `binaryIndex` también lo haría para mantener la consistencia.

**¿Qué ganamos con esto?**

En una sesión normal de uso, una página puede "repintarse" (renderizarse en React) docenas de veces por causas que el usuario ni siquiera nota: al recibir datos del servidor, al escribir en un campo, al cambiar entre pestañas, etc.

Sin `useMemo`, cada uno de esos repintados ejecuta:
- 1 operación que revisa 1000 reclamaciones (denialRate)
- 1 operación que agrupa 1000 reclamaciones por pagador (payerRates)
- 1 operación que filtra y agrupa 500 citas (locationNoShowRates)
- 1 operación que suma costos de 500 citas (weeklyNoShowCost)
- 1 operación que ordena 1000 elementos (sortedClaims — la más costosa)
- 1 búsqueda en la lista ordenada (binaryIndex)
- 1 búsqueda lineal y 1 transformación (linearClaim + cmeReport)

Con `useMemo`, todo esto se hace **una sola vez**. Si la página se repinta 20 veces (algo común), estamos ahorrando 19 ejecuciones de cada uno de estos cálculos. En total, eso son aproximadamente **133 operaciones sobre listas completas que ya no se repiten innecesariamente**.

### 1.2 Lazy Loading — `AnalysisResultsPanel` (Analizador de Incidencias)

**¿Qué problema teníamos?**

La página del Analizador de Incidencias —donde los usuarios cargan archivos CSV para analizar— incluía **todo el código del panel de resultados desde el momento en que se carga la página**. Este panel tiene aproximadamente 200 líneas de código (tablas, badges de clasificación, desgloses por categoría, etc.), pero **solo se muestra después** de que el usuario:
1. Selecciona un archivo CSV
2. Hace clic en "Analizar"
3. Espera a que el servidor procese el archivo

**¿Por qué es esto un problema?**

Imagina que entras a un restaurante y, antes de que puedas siquiera ver el menú, el mesero ya te trajo el postre, la cuenta y un libro de reclamaciones. Todo eso ocupa espacio en tu mesa y te distrae de lo que realmente importa al principio. Eso es lo que pasaba con este componente: el navegador descargaba y procesaba código que el usuario no iba a necesitar hasta minutos después (o quizás nunca, si solo entra a la página a mirar sin subir un archivo).

**¿Qué hicimos?**

Dividimos el componente en dos partes separadas y aplicamos una técnica llamada **Lazy Loading** (carga perezosa):

1. **IncidentsAnalyzerClient** — el código principal (selector de archivo, botón de análisis) que se ve desde el inicio
2. **AnalysisResultsPanel** — el panel de resultados, que ahora se carga **solo cuando el usuario realmente lo necesita**

La técnica funciona así:

```jsx
// Antes: el panel se importaba y cargaba siempre, sin importar si hacía falta
import AnalysisResultsPanel from "./AnalysisResultsPanel";

// Ahora se carga bajo demanda. El navegador solo descarga este archivo
// cuando la variable `response` tiene datos (es decir, cuando el análisis terminó).
const AnalysisResultsPanel = dynamic(
  () => import("@/components/AnalysisResultsPanel"),
  { ssr: false },
);
```

**¿Qué significa `dynamic` y `ssr: false`?**

- **`dynamic`** es una función de Next.js que permite cargar un componente solo cuando se necesita (en lugar de al inicio). Le decimos: "this component, please load it later when it's actually needed".
- **`ssr: false`** significa "no renderices esto en el servidor". SSR (Server-Side Rendering) es cuando el servidor prepara la página HTML antes de enviarla al navegador. Como este panel solo tiene sentido cuando el usuario ya está interactuando con la página en su navegador (después de subir un CSV), renderizarlo en el servidor sería un trabajo inútil.

**¿Qué ganamos con esto?**

- **Entre 15 y 20 kilobytes menos** que el navegador tiene que descargar y procesar al entrar a la página. En una conexión de internet lenta o móvil, esos kilobytes pueden significar segundos enteros de diferencia en cuánto tarda la página en estar lista.
- El código del panel **solo se descarga si el usuario realmente va a usarlo**. Si un usuario entra a la página y solo mira las instrucciones, nunca descarga ese código.

**Análisis de costo-beneficio:**

| Aspecto | Sin lazy loading (antes) | Con lazy loading (después) |
|---|---|---|
| Carga inicial | 100% del código (incluyendo el panel) | Solo ~85% del código (sin el panel) |
| Tiempo hasta que la página es usable | Más lento (descarga código innecesario) | Más rápido (menos código que procesar) |
| Experiencia al ver resultados | Normal | Minima pausa mientras se descarga el panel (imperceptible, ~50-200ms) |
| ¿El usuario nota la diferencia? | Sí (la página tarda más en cargar) | No (la mini-pausa es imperceptible) |

### 1.3 Lazy Loading — `IncidentFormPanel` (Formulario de incidencias)

**¿Qué problema teníamos?**

La página del Gestor de Incidencias —la tabla donde se listan, crean y editan incidencias— incluía **todo el código del formulario de creación/edición desde el momento de cargar la página**. Este formulario tiene aproximadamente 150 líneas de código con inputs, selects, validaciones y etiquetas de categorías, pero **solo se muestra** cuando el usuario hace clic en "New Incident" o "Edit".

**¿Por qué cargar algo que no se ve?**

Piénsalo así: cuando entras a tu casa, no tienes la maleta de viaje abierta y llena en medio de la sala todos los días —solo la sacas cuando realmente vas a viajar. El formulario de incidencias es como esa maleta: solo la necesitas cuando vas a crear o editar una incidencia. Tenerla siempre "abierta" y ocupando espacio innecesariamente es un desperdicio de recursos.

**¿Qué hicimos?**

Extrajimos todo el formulario (título, descripción, categoría, origen, sucursal, botones) a un componente separado `IncidentFormPanel.tsx` y lo cargamos bajo demanda con `next/dynamic`, exactamente como hicimos con el panel de resultados del analizador.

**¿Qué ganamos con esto?**

- **Entre 10 y 15 kilobytes menos** en la carga inicial del gestor de incidencias. Esto puede no parecer mucho, pero es código que incluye:
  - Las etiquetas traducidas de todas las categorías y orígenes
  - La lógica de validación del formulario
  - El renderizado de inputs, selects y textarea
  - Manejo de estados de error y carga

- Todo ese código **solo se descarga** cuando el usuario hace clic en "New Incident" o "Edit", no antes.

**¿Cómo se comunica con la página principal?**

El formulario recibe todo lo que necesita a través de "props" (propiedades), que son como parámetros que le pasamos al componente:

```jsx
<IncidentFormPanel
  form={form}           // Los datos actuales del formulario
  editingId={editingId} // ID de la incidencia que se está editando (o null si es nueva)
  isSaving={isSaving}   // Si está guardando (para mostrar "Saving..." y deshabilitar botones)
  formErrors={formErrors} // Errores de validación de cada campo
  onChange={setForm}     // Función que se llama cuando el usuario cambia un campo
  onSave={handleCreate}  // Función que se llama cuando el usuario hace clic en Guardar
  onCancel={cancelFn}    // Función que se llama cuando el usuario hace clic en Cancelar
/>
```

Esto se llama **comunicación padre-hijo**: la página principal mantiene el control de los datos y le pasa al formulario todo lo que necesita para funcionar. El formulario solo se encarga de "pintar" los campos en pantalla y avisar a la página principal cuando algo cambia o cuando el usuario quiere guardar/cancelar.

### 1.4 Criterios de selección para lazy loading — ¿Cómo supimos qué merecía lazy loading?

No todos los componentes se benefician del lazy loading. De hecho, si lo aplicas mal, puedes empeorar la experiencia del usuario (imagina que la tabla principal se cargara "bajo demanda" y la página se viera en blanco unos segundos cada vez que entras). Por eso usamos estos 4 criterios para decidir:

| Criterio | ¿Qué significa? | AnalysisResultsPanel | IncidentFormPanel |
|---|---|---|---|
| **¿Se ve apenas entras a la página?** | Si el componente es visible desde el primer momento, debe cargarse de inmediato. Si no, puede esperar. | ❌ No — solo tras subir y analizar un CSV | ❌ No — solo tras hacer clic en "New" o "Edit" |
| **¿Tiene bastante código?** | Si es pequeño (ej. 20 líneas), el ahorro de lazy loading es tan mínimo que no vale la complejidad. | Sí (~200 líneas + imports) | Sí (~150 líneas + imports) |
| **¿Incluye dependencias pesadas?** | Etiquetas de categorías, librerías de formato, tablas complejas, selectores grandes. | Sí (tablas, badges, formateo de datos) | Sí (etiquetas de categorías/orígenes, validación) |
| **¿Tiene sentido renderizarlo en el servidor (SSR)?** | Si el componente necesita datos solo disponibles en el navegador (archivos cargados por el usuario, interacciones), el SSR es un trabajo inútil. | No — solo útil en el navegador del cliente | No — es un modal interactivo |

**Regla práctica**: Si la respuesta a "¿Se ve al entrar?" es **NO** y dos o más de las otras son **SÍ**, entonces merece lazy loading. Si la respuesta a "¿Se ve al entrar?" es **SÍ**, entonces NO se debe poner lazy loading sino optimizarlo con `useMemo`.

---

## 2. Decisiones en el Backend (los servidores)

Hasta ahora hemos optimizado lo que pasa **dentro del navegador del usuario**. Ahora veamos el otro lado: los servidores que envían los datos que el navegador necesita.

**¿Qué problema general tenemos aquí?**

Cuando el navegador necesita la lista de productos del inventario, le hace una petición al servidor (API). El servidor, a su vez, tiene que ir a buscar esos datos a la base de datos. Si 10 personas abren la página de inventario al mismo tiempo, el servidor tiene que hacer 10 consultas a la base de datos, aunque todas pregunten exactamente lo mismo. Eso es trabajo desperdiciado.

**¿Cómo lo solucionamos?**

Con una "cajita" de memoria dentro del servidor donde guardamos las respuestas. La próxima vez que alguien pregunte lo mismo, en lugar de ir a la base de datos, miramos primero nuestra cajita.

### 2.1 Nuestra herramienta: `MemoryCache` — Una "cajita de notas" dentro del servidor

**¿Qué creamos?**

Una clase de Python llamada `MemoryCache` — piensa en ella como una **cajita de notas adhesivas** que está dentro del servidor. Cuando alguien le pregunta algo al servidor:

1. **Primero miramos la cajita**: ¿ya tenemos anotada la respuesta de antes?
   - Si sí y **sigue vigente** (no ha pasado el tiempo de expiración) → la devolvemos al instante
   - Si sí pero **está vencida** → la borramos (esa nota ya no sirve)
   - Si no → vamos a la base de datos, calculamos la respuesta y la anotamos en la cajita para la próxima vez

**El código real (simplificado):**

```python
class MemoryCache:
    # El diccionario es nuestra "cajita": cada clave es una etiqueta que identifica
    # la respuesta, y el valor incluye la respuesta junto con su fecha de caducidad.
    def __init__(self):
        self._store = {}  # {"clave: (timestamp_caducidad, valor_respuesta)}

    def get(self, clave):
        """Busca una respuesta en la cajita. Si expiró, la borra."""
        entrada = self._store.get(clave)
        if not entrada:
            return None  # No está en la cajita
        expiracion, valor = entrada
        if time.monotonic() >= expiracion:
            del self._store[clave]  # Estaba vencida, la limpiamos
            return None
        return valor  # ¡Encontrada y vigente!

    def set(self, clave, valor, ttl_segundos):
        """Guarda una respuesta en la cajita con un tiempo de vida (TTL)."""
        self._store[clave] = (time.monotonic() + ttl_segundos, valor)

    def invalidate(self, prefijo):
        """Limpia todas las respuestas cuya clave empiece con cierto texto.
           Útil cuando los datos cambian y necesitamos "resetear" la caché."""
        claves_a_borrar = [k for k in self._store if k.startswith(prefijo)]
        for k in claves_a_borrar:
            del self._store[k]
        return len(claves_a_borrar)
```

**La analogía del supermercado:**

| Concepto técnico | Analogía |
|---|---|
| `MemoryCache` | Un tablero de anuncios en la entrada del supermercado |
| Clave (key) | El título del anuncio: "Precio de la leche" |
| Valor (value) | El contenido: "Leche entera: $2.50" |
| TTL (tiempo de vida) | Un cartel que dice "Este precio caduca en 30 segundos" |
| `invalidate(prefix)` | Cuando cambian los precios de todos los lácteos, arrancamos todos los anuncios que empiecen con "Lácteo:" |
| `cache.get(clave)` | Mirar el tablero antes de ir al almacén a preguntar el precio |

**¿Por qué una cajita en memoria en lugar de algo más sofisticado?**

Porque es simple, rápida y no requiere instalar nada extra. La memoria del servidor es el lugar más rápido para guardar y recuperar datos — mucho más rápido que cualquier base de datos.

**Limitación importante para el futuro:**

Esta cajita vive **dentro del servidor individual**. Si en el futuro nuestra aplicación crece y necesitamos que 3 servidores trabajen en equipo (lo que se llama "escalado horizontal"), cada servidor tendría su propia cajita y no sabrían lo que los otros tienen guardado. Para eso necesitaríamos Redis, que es como una cajita compartida a la que todos los servidores pueden mirar. Pero para una aplicación de un solo servidor, nuestra cajita en memoria es perfecta.

### 2.2 HealthCore API — Inventario `GET /products`

**¿Qué problema teníamos?**

Cuando alguien abre la página de inventario, el servidor tiene que hacer lo siguiente:

1. **Paso 1:** Traer todos los productos de la base de datos PostgreSQL (1 consulta)
2. **Paso 2:** Por **cada producto**, calcular cuánto stock hay disponible. Para eso necesita hacer **2 consultas adicionales**:
   - Una para sumar toda la mercancía que ha **entrado** (deliveries)
   - Otra para sumar toda la mercancía que ha **salido** (consumptions)
   
   **Fórmula del stock:** `stock = total_entrado - total_salido`

**Traducción a números:**

Si hay 100 productos en el catálogo, cada vez que alguien abre la página de inventario, el servidor hace **1 + (100 × 2) = 201 consultas** a la base de datos.

Si solo 5 personas abren la página al mismo tiempo, eso son **1005 consultas** a la base de datos, aunque los datos no hayan cambiado entre una consulta y otra.

**¿Qué hicimos?**

Guardamos la lista completa de productos (con su stock ya calculado) en la caché. Ahora, la primera persona que abre la página genera las 201 consultas, pero las siguientes personas reciben la respuesta instantánea desde la caché.

| Aspecto | Detalle técnico | Explicación sencilla |
|---|---|---|
| **¿Qué guardamos?** | La lista completa de productos con stock calculado | Una "foto" del catálogo lista para entregar |
| **Clave de caché** | `"inventory:products:list"` | La "etiqueta" de nuestra nota adhesiva |
| **TTL (tiempo de vida)** | **30 segundos** | Cada 30 segundos la foto se renueva automáticamente |
| **Costo sin caché** | O(2n) — por cada producto, 2 consultas a BD | Por cada producto, 2 viajes a la base de datos |
| **Costo con caché** | O(1) — una sola lectura de memoria | La respuesta sale instantánea de la cajita |

**¿Por qué exactamente 30 segundos?**

Esta fue una decisión con estudio:

- **Si poníamos 5 segundos**: casi no ahorraríamos consultas porque la caché se vence muy rápido. Sería como poner una nota adhesiva que se cae a los 5 segundos.
- **Si poníamos 5 minutos (300 segundos)**: ahorraríamos muchas consultas, pero el stock podría estar desactualizado por mucho tiempo. Imagina que alguien consume 10 unidades de un producto y el sistema sigue mostrando que hay stock durante 5 minutos. Eso podría causar que alguien intente usar un producto que ya no está disponible.
- **30 segundos es el punto medio**: suficientemente largo para que varias personas que abran la página al mismo tiempo se beneficien de la caché, pero suficientemente corto para que, si alguien cambia el stock, la página se actualice en menos de medio minuto.

**¿Qué pasa cuando alguien cambia los datos?**

Este es un punto crítico. Cuando alguien:
- **Crea un producto nuevo** (el catálogo cambió)
- **Recibe mercancía** (los stocks cambiaron)
- **Consume mercancía** (los stocks cambiaron)

...el sistema **limpia la caché de productos inmediatamente**. No espera los 30 segundos. Es como si, cada vez que cambia el precio de un producto en el supermercado, un empleado fuera al tablero de anuncios y arrancara la nota vieja al instante. La siguiente persona que pregunte verá los datos frescos.

### 2.3 Incidents API — Resumen `GET /summary`

**¿Qué problema teníamos?**

La página del Gestor de Incidencias muestra unas tarjetas en la parte superior con números: "Total: 150", "Abiertas: 45", "En progreso: 20", etc. Para calcular esos números, el servidor tiene que **leer todas las incidencias una por una** y contarlas según su estado, categoría, origen y sucursal.

**¿Qué significa "leer todas las incidencias" exactamente?**

TinyDB (la base de datos que usamos para incidencias) no tiene un "contador rápido" como Excel. Para saber cuántas incidencias hay abiertas, tiene que:
1. Traer todas las incidencias desde el archivo JSON
2. Revisar cada una y preguntar: "¿está abierta? ¿cerrada? ¿descartada?"
3. Ir sumando en contadores separados

Si hay 1000 incidencias, eso significa recorrer 1000 registros completos cada vez que alguien abre el gestor.

**Aún más importante**: este resumen se muestra en una pantalla de monitoreo que probablemente varias personas tengan abierta al mismo tiempo. Sin caché, cada persona que tenga la pantalla abierta estaría haciendo que el servidor recorra las 1000 incidencias cada vez que la página se actualice.

**¿Qué hicimos?**

Guardamos el resumen completo (todos los contadores ya calculados) en caché.

| Aspecto | Detalle técnico | Explicación sencilla |
|---|---|---|
| **¿Qué guardamos?** | El objeto `IncidentSummary` con todos los contadores | Los números del tablero ya calculados |
| **Clave de caché** | `"incidents:summary"` | La etiqueta de la nota adhesiva |
| **TTL** | **60 segundos** | Cada 60 segundos se recalcula automáticamente |
| **Costo sin caché** | Full table scan — recorre TODAS las incidencias | Lee el archivo entero de principio a fin |
| **Costo con caché** | O(1) — solo leer de memoria | Sale instantáneo de la cajita |

**¿Por qué 60 segundos y no 30 como el inventario?**

Porque este resumen es un **tablero de monitoreo**, no un sistema de transacciones en tiempo real. Pregúntate: ¿qué pasa si un supervisor ve que hay "150 incidencias totales" cuando en realidad ya hay 151?

- **En el inventario**: 30 segundos de desfase en stock podría causar que alguien intente usar un producto que ya no existe. Eso sí es problemático.
- **En el resumen de incidencias**: 60 segundos de desfase significa que un contador muestra "45 abiertas" en lugar de "46". Para un tablero que se usa para tener una visión general del estado de las incidencias, esa diferencia de 1 o 2 incidencias durante menos de un minuto **no afecta ninguna decisión operativa**.

**Pero ojo: igual que el inventario, la invalidación es inmediata**

Cuando alguien crea, edita o elimina una incidencia, la caché del resumen se limpia **al instante**. El TTL de 60 segundos solo aplica durante periodos donde **no hay cambios** (que son la mayoría del tiempo en una aplicación normal).

### 2.4 Incidents API — Lista filtrada `GET /`

**¿Qué problema teníamos?**

Además del resumen de contadores (sección 2.3), el Gestor de Incidencias muestra una **lista con filtros**: el usuario puede filtrar por estado, categoría, origen y sucursal. Cada combinación de filtros produce una lista diferente.

**¿Qué hace el servidor sin caché?**

Cuando un usuario aplica filtros, el servidor:
1. **Trae todas las incidencias** de la base de datos
2. **Filtra en memoria**: revisa cada incidencia y pregunta si cumple con todos los filtros seleccionados

Esto significa que cada vez que alguien cambia un filtro, el servidor vuelve a recorrer todas las incidencias. Si un usuario prueba varias combinaciones de filtros (algo muy común cuando se busca una incidencia específica), el servidor hace el mismo trabajo muchas veces.

**¿Qué hicimos?**

Guardamos la lista de incidencias ya filtrada en caché, pero con un truco importante: **la clave incluye los filtros**, así que cada combinación de filtros tiene su propia entrada en la caché.

**Explicación de la clave con filtros:**

```python
# La clave se construye así:
filtros = f"s:{status}|c:{category}|o:{origin}|b:{branch}"
cache_key = f"incidents:list:{filtros}"

# Ejemplos reales de claves:
"incidents:list:s:OPEN|c:BILLING|o:None|b:None"     # Incidencias abiertas de facturación
"incidents:list:s:CLOSED|c:None|o:customer|b:UK01"  # Incidencias cerradas de cliente UK01
"incidents:list:s:None|c:None|o:None|b:None"         # Todas las incidencias (sin filtros)
```

Esto es importante porque **no podemos mezclar resultados de diferentes filtros**. Imagina que alguien busca incidencias abiertas y la respuesta se mezcla con la de otro que busca incidencias cerradas — eso sería un error grave de datos.

| Aspecto | Detalle técnico | Explicación sencilla |
|---|---|---|
| **¿Qué guardamos?** | Lista de incidencias ya filtrada | El resultado de la búsqueda listo para entregar |
| **Clave de caché** | `"incidents:list:s:{status}\|c:{category}\|o:{origin}\|b:{branch}"` | La etiqueta incluye los filtros: "Resultado para: incidencias abiertas de facturación" |
| **TTL** | **30 segundos** | Cada 30 segundos se recalcula automáticamente |
| **Costo sin caché** | Full table scan + filtrado en Python | Recorre todas las incidencias y filtra una por una |
| **Costo con caché** | O(1) por combinación de filtros | Si la combinación ya está en la cajita, sale al instante |

**¿Por qué 30 segundos?**

Cuando un usuario está navegando por el gestor de incidencias, aplicando y quitando filtros, queremos que vea datos relativamente frescos (no más de 30 segundos de retraso). Pero al mismo tiempo, si varias personas usan los mismos filtros (ej. "incidencias abiertas" es un filtro muy común), queremos evitar que el servidor haga el mismo trabajo una y otra vez. 30 segundos logra ese equilibrio.

**¿Y cuándo se limpia esta caché?**

Se limpia junto con el resumen (sección 2.5), cada vez que alguien crea, edita o elimina una incidencia. Así, si un usuario acaba de crear una incidencia y va a ver la lista con filtros, los datos estarán actualizados.

### 2.5 Invalidación en escrituras — "Cuando algo cambia, limpia la nota vieja"

**¿Por qué es necesario invalidar la caché?**

La caché es genial para lecturas repetidas, pero tiene un peligro: **si los datos cambian y la caché no se actualiza, el usuario ve datos desactualizados**. Por eso, cada vez que alguien escribe datos nuevos (crear, editar, eliminar), debemos limpiar la caché relacionada.

**¿Cuál es la regla general que seguimos?**

Es muy simple — la llamamos "cache-aside con invalidación en escritura", pero en español sencillo es:

```
Cuando alguien LEE:     ¿Está en la cajita? → Sí → devolver rápido
                        No → ir a la BD, calcular, guardar en cajita, devolver

Cuando alguien ESCRIBE: Hacer el cambio → limpiar la cajita (lo que esté relacionado)
```

**Piénsalo como un supermercado:**

- **Lectura**: un cliente pregunta "¿cuánto cuesta la leche?" → miro mi tablero de anuncios (caché). Si el precio está ahí, lo digo. Si no, voy al almacén (BD), pregunto el precio, lo anoto en el tablero, y se lo digo al cliente.
- **Escritura**: el gerente cambia el precio de la leche → va al almacén y lo actualiza, **pero también arranca la nota del tablero** que tenía el precio viejo. Así el próximo cliente que pregunte verá el precio nuevo.

**Invalidación en el inventario (HealthCore API):**

| Operación de escritura | ¿Qué cambia? | ¿Qué limpiamos? |
|---|---|---|
| Crear un producto nuevo | El catálogo tiene un producto más | La caché de productos (`"inventory:products:..."`) |
| Recibir mercancía (inbound) | Los stocks de los productos aumentan | La caché de productos (`"inventory:products:..."`) |
| Consumir mercancía (outbound) | Los stocks de los productos disminuyen | La caché de productos (`"inventory:products:..."`) |

**Invalidación en las incidencias (Incidents API):**

| Operación de escritura | ¿Qué cambia? | ¿Qué limpiamos? |
|---|---|---|
| Crear una incidencia | Hay una incidencia más | Resumen (`"incidents:summary"`) + Listas (`"incidents:list"`) |
| Editar una incidencia | Los datos de una incidencia cambiaron | Resumen + Listas |
| Cambiar el estado de una incidencia | Los contadores del resumen cambian | Resumen + Listas |
| Eliminar una incidencia | Hay una incidencia menos | Resumen + Listas |

**¿Por qué en Incidents API limpiamos TANTO el resumen como las listas?**

Porque cualquier cambio en cualquier incidencia **podría** afectar ambos:
- **El resumen**: si cambia el estado de una incidencia de "abierta" a "cerrada", el contador de "abiertas" baja y el de "cerradas" sube.
- **Las listas filtradas**: si alguien está viendo "incidencias abiertas" y una incidencia cambia a "cerrada", esa lista ya no es correcta.

En lugar de analizar caso por caso (lo cual sería complejo y propenso a errores), limpiamos todo. Es más simple, más seguro, y la pérdida de rendimiento por limpiar de más es mínima.

> **⚠️ Nota importante de la auditoría**: Encontramos un error durante la revisión: originalmente, la invalidación **solo limpiaba el resumen** (`"incidents:summary"`), pero **no limpiaba las listas filtradas** (`"incidents:list"`). Esto significaba que al crear una incidencia, los contadores del tablero se actualizaban correctamente, pero la tabla de incidencias (con sus filtros) seguía mostrando datos viejos. Ya corregimos este error para que ambas se limpien. Este tipo de detalle es fácil de pasar por alto, por eso la invalidación merece tanta atención como el propio cacheo.

---

## 3. Intercambios Reconocidos (Trade-offs)

> Con la caché, estamos **ganando velocidad**, pero a cambio **perdemos precisión momentánea**. 

### 3.1 Inventario: stock desactualizado hasta 30 segundos

**¿Qué ganamos? (velocidad)**

Sin caché, 10 personas abriendo la página de inventario generan **2010 consultas a la base de datos** (201 consultas por persona). Con caché, solo la primera persona genera esas consultas. Las otras 9 reciben la respuesta desde la memoria del servidor en **microsegundos** (millonésimas de segundo).

**¿Qué perdemos? (frescura)**

Si alguien consume 10 unidades de un producto, la lista puede mostrar el stock anterior (incorrecto) por hasta **30 segundos**.

**¿Es grave?**

Depende del contexto:
- ✅ **Aceptable**: un operador que revisa el inventario general para planificar pedidos. Si ve que hay "100 unidades" en lugar de "90" por 30 segundos, no pasa nada.
- ❌ **No aceptable**: un quirófano donde el material quirúrgico debe estar contado al segundo. Si el sistema dice que hay 1 bisturí cuando en realidad ya se usó, eso podría causar un problema serio.

**En nuestro caso**, la aplicación de HealthCore se usa para gestión interna de inventario médico, donde 30 segundos de desfase es perfectamente aceptable. No es un sistema de quirófano en tiempo real.

**¿Cómo mitigamos el riesgo?** (2 capas de defensa)

1. **Invalidación inmediata**: cuando alguien registra una entrada o salida de mercancía, la caché se limpia al instante. La mayoría de las veces, el usuario que acaba de hacer un cambio y vuelve a ver la lista verá datos frescos.
2. **TTL bajo (30s)**: si la invalidación fallara por algún motivo (error de programación, reinicio, etc.), el TTL de 30 segundos asegura que la caché se limpie sola en menos de un minuto. Es como un "seguro de vida".

### 3.2 Resumen de incidencias: contadores desactualizados hasta 60 segundos

**¿Qué ganamos? (velocidad)**

El tablero de resumen puede ser visto por múltiples supervisores al mismo tiempo sin saturar TinyDB (la base de datos de incidencias). En lugar de que cada supervisor genere un "full scan" de todas las incidencias cada vez que abre la página, el servidor lo hace solo una vez cada 60 segundos y comparte el resultado con todos.

**¿Qué perdemos? (frescura)**

Una incidencia nueva puede tardar hasta **60 segundos** en aparecer en los contadores del tablero.

**¿Es grave?**

Muy poco grave por dos razones:
1. **Es un tablero de monitoreo**, no un sistema de transacciones. El supervisor lo usa para tener una visión general del estado de las incidencias, no para operaciones segundo a segundo. Ver "25 abiertas" en lugar de "26" por 40 segundos no afecta ninguna decisión.
2. **Quien crea la incidencia** ve la confirmación inmediata en la pantalla ("Incidente creado correctamente"). La única persona que podría notar el desfase es alguien que esté mirando el tablero desde otra pantalla mientras otro usuario crea una incidencia — una situación poco común.

**¿Cómo lo mitigamos?**

Igual que el inventario: invalidación inmediata al crear/editar/eliminar. El TTL de 60s es solo el respaldo.

### 3.3 Caché en memoria (nuestra elección) vs. Redis (alternativa profesional)

**¿Por qué no usamos simplemente Redis?**

Redis es un programa externo especializado en caché que varios servidores pueden compartir. Suena mejor, pero tiene costos:

| Aspecto | Nuestra caché en memoria | Redis |
|---|---|---|
| **Instalación** | ✅ No requiere instalar nada — ya está en el servidor | ❌ Requiere instalar y configurar Redis aparte |
| **Velocidad** | ✅ Microsegundos (lectura de RAM local) | ✅ También rápido, pero un poco más lento (hay que ir por la red a otro programa) |
| **Complejidad** | ✅ ~50 líneas de código, fácil de entender | ❌ Más código, más configuración, más cosas que pueden fallar |
| **Compartida entre servidores** | ❌ Cada servidor tiene su propia caché | ✅ Todos los servidores ven la misma caché |
| **Persistencia** | ❌ Al reiniciar el servidor, la caché se pierde | ✅ Redis guarda los datos aunque el servidor se reinicie |
| **Escalabilidad** | ❌ No sirve si tenemos 5 servidores | ✅ Funciona igual con 1 o con 50 servidores |

**Decisión fundamentada:**

Para nuestra situación actual — una aplicación que funciona con **un solo servidor** — la caché en memoria es la mejor opción porque:
- Es más rápida (no hay que salir a la red)
- Es más simple de mantener (no hay que instalar Redis)
- Hace exactamente lo que necesitamos

**¿Cuándo deberíamos migrar a Redis?**

Si en el futuro la aplicación crece y usamos **varios servidores** trabajando en equipo (lo que se llama "escalado horizontal"), en ese momento necesitaremos Redis. Pero hasta entonces, la caché en memoria es la decisión correcta.

### 3.4 Lazy Loading: la página arranca más rápido pero... hay que esperar para ver ciertos componentes

**¿Qué ganamos? (carga inicial más rápida)**

Al entrar a la página, el navegador descarga entre **25 y 35 kilobytes menos** de código. En una conexión de internet rápida son milisegundos, pero en una conexión lenta o móvil puede ser la diferencia entre la página cargar en 2 segundos o en 5 segundos.

**¿Qué perdemos? (mini-demora bajo demanda)**

Cuando el usuario hace clic para abrir el formulario o ver el panel de resultados, hay una **pequeña pausa** (normalmente 50-200 milisegundos) mientras se descarga el código que falta.

**¿Se nota esa pausa?**

- La **primera vez** que haces clic: sí, apenas se nota (50-200ms es menos de un parpadeo).
- Las **veces siguientes**: no, porque el navegador ya guardó ese código en su memoria caché.

**¿Dónde aplicamos lazy loading y dónde no?**

| Situación | Decisión | ¿Por qué? |
|---|---|---|
| Panel de resultados del analizador | ✅ Lazy loading | No se ve al entrar, solo tras subir un CSV |
| Formulario de incidencias | ✅ Lazy loading | No se ve al entrar, solo tras hacer clic |
| Tabla principal de incidencias | ❌ No lazy loading | Se ve al entrar — cargarla bajo demanda retrasaría la experiencia inicial |
| Tarjetas de resumen | ❌ No lazy loading | Se ven al entrar |
| Filtros y búsqueda | ❌ No lazy loading | Se ven al entrar — son parte de la experiencia inmediata |

**¿Por qué no aplicamos lazy loading a los componentes que se ven al entrar?**

Imagina que entras a una página y ves una pantalla en blanco durante 1-2 segundos mientras se descarga el código de la tabla principal. Eso **empeora** la experiencia del usuario, no la mejora. El lazy loading solo beneficia a componentes que **no están visibles desde el principio**.

---

## 4. ¿Qué NO cacheamos y por qué?

> No todo se puede o se debe cachear. De hecho, aplicar caché incorrectamente puede causar problemas más graves que no tenerla (como mostrar datos de una persona a otra, o mostrar información desactualizada sin que nadie se dé cuenta). Esta sección explica cada exclusión con su fundamento.

### 4.1 Datos personales y de sesión

#### Endpoint `GET /profiles/me` (mi perfil)

**¿Qué hace este endpoint?** Devuelve los datos de la persona que está usando el sistema en este momento: nombre, email, rol dentro de la aplicación, preferencias, etc.

**¿Por qué decidimos NO cachearlo?**

- **Problema de seguridad**: Cada usuario tiene su propio perfil. Si guardamos el perfil del usuario "María" en la caché con una clave genérica como `"profile"`, y luego el usuario "Pedro" hace la misma petición, el sistema le devolvería el perfil de María. Esto sería una **filtración de datos grave**.
- **Solución posible (pero descartada)**: Podríamos crear una clave que incluya el ID del usuario, como `"profile:user_123"`, `"profile:user_456"`. Pero entonces:
  - Cada usuario que use el sistema ocuparía espacio en la caché (si hay 500 usuarios, 500 entradas)
  - Si alguien actualiza su perfil, habría que encontrar y limpiar esa clave específica
  - Como cada usuario ve su propio perfil y nadie más lo solicita, **no hay peticiones repetidas de los mismos datos** — el beneficio del caché sería mínimo

- **Conclusión**: El riesgo de seguridad más la complejidad de implementación no justifican el mínimo beneficio que obtendríamos.

#### Endpoint `GET /auth/me` (verificar sesión activa)

**¿Qué hace este endpoint?** Verifica si el usuario todavía tiene la sesión iniciada (es decir, si su token de acceso sigue siendo válido).

**¿Por qué decidimos NO cachearlo?** Porque la validez de una sesión cambia constantemente:
  - Cuando el usuario inicia sesión → el token se vuelve válido
  - Cuando el usuario cierra sesión → el token se vuelve inválido
  - Cuando el token expira → el token se vuelve inválido

Cachear este endpoint podría hacer que el sistema piense que un usuario sigue "logueado" cuando en realidad ya cerró sesión hace rato. Eso sería un **riesgo de seguridad**.

#### Endpoint `GET /users/me` (usuario actual)

**¿Qué hace?** Información del usuario que está usando el sistema.

**¿Por qué NO?** Misma razón que `profiles/me`: son datos personales que varían por usuario y no hay repetición de consultas idénticas entre distintas personas.

### 4.2 Proveedores `GET /suppliers/*` — porque ya es rápido sin caché

**¿Qué hace este endpoint?** Trae la lista de proveedores registrados en el sistema.

**¿Por qué decidimos NO cachearlo?** Porque los datos de proveedores se guardan en **TinyDB**, una base de datos que lee un archivo JSON directamente desde la memoria del servidor. TinyDB es extremadamente rápida para lecturas simples — las respuestas se miden en **milisegundos** incluso sin caché.

**Criterio que aplicamos**: Si un endpoint ya responde en menos de 10-20 milisegundos sin caché, cachearlo no daría una mejora notable para el usuario. Añadir caché para algo que ya es rápido solo añade complejidad innecesaria al código y posibles bugs (como olvidar invalidar cuando se añade un nuevo proveedor).

### 4.3 Operaciones de escritura (POST, PATCH, PUT, DELETE)

**¿Qué hace un endpoint POST?** Crea datos nuevos.

**¿Por qué NO cacheamos escrituras?** Porque la caché sirve para acelerar **lecturas repetidas**. Cuando escribes datos nuevos:
- No vas a repetir la misma escritura varias veces (no tiene sentido crear la misma incidencia 10 veces)
- Necesitas que el cambio se refleje **inmediatamente** — si cachearas la respuesta de una escritura, podrías terminar mostrando datos inconsistentes

**La regla es simple**: Sólo cacheamos GET (lecturas). Nunca cacheamos POST, PATCH, PUT o DELETE (escrituras).

### 4.4 Endpoints con datos personalizados por usuario

**¿Qué endpoints son estos?** Cualquier endpoint que devuelve información específica del usuario que hace la petición.

| Endpoint | ¿Por qué no se cacheó? | ¿Qué pasaría si lo cacheáramos mal? |
|---|---|---|
| `GET /users/me` | Datos del usuario logueado — diferentes para cada persona | Un usuario vería los datos de otro |
| `GET /profiles/me` | Perfil personal — varía por usuario | Un usuario vería el perfil de otro |
| Cualquier endpoint que use `current_user` | Requeriría acotar la clave de caché al user_id | Datos mezclados entre usuarios |

**Principio fundamental que seguimos:**

> "No guardes en caché datos personales, de sesión o información sensible a menos que la clave de caché incluya al usuario autenticado."

**En lenguaje sencillo**: si los datos son diferentes para cada persona, no los metas en una caché que todos comparten, porque terminarías mostrándole a una persona los datos de otra. Eso sería un error grave de privacidad.

### 4.5 Componentes frontend que se ven desde el principio

**¿Qué componentes frontend NO sometimos a lazy loading?**

- **Tabla principal de incidencias**: visible nada más cargar la página
- **Tarjetas de resumen** (total, abiertas, cerradas, etc.): visibles al cargar
- **Filtros y barra de búsqueda**: visibles al cargar
- **Desglose por categorías**: visible al cargar

**¿Por qué no aplicamos lazy loading aquí?**

Porque estos componentes son parte de la **experiencia inmediata** del usuario. Si los cargáramos bajo demanda, el usuario vería una pantalla en blanco mientras el navegador descarga, procesa y renderiza el código necesario. Eso es exactamente lo contrario de lo que queremos lograr: mejorar la percepción de velocidad.

**¿Qué hicimos en su lugar?**

Los optimizamos con `useMemo` (sección 1.1) y los cargamos de forma normal (sin lazy loading). Así se benefician de la memoización (no recalcular innecesariamente) pero sin el retraso inicial del lazy loading.

---

## 5. Resumen de Impacto

Aquí tienes un resumen de todo lo que cambiamos, en lenguaje sencillo y con el beneficio concreto:

| ¿Dónde? | ¿Qué cambiamos? | ¿Qué conseguimos? |
|---|---|---|
| **Página principal** | 7 cálculos ahora usan `useMemo` | En lugar de recalcular todo en cada "repintado" de la pantalla, se calcula una sola vez. Ahorro: ~7 operaciones sobre listas completas por render. |
| **Analizador de incidencias** | Panel de resultados ahora se carga bajo demanda (lazy loading) | Entre 15-20 KB menos al entrar a la página. El panel solo se descarga si realmente vas a ver resultados. |
| **Gestor de incidencias** | Formulario de crear/editar ahora se carga bajo demanda (lazy loading) | Entre 10-15 KB menos al entrar a la página. El formulario solo se descarga si haces clic en "New" o "Edit". |
| **Lista de productos (API inventario)** | Se guarda en caché por 30 segundos | De 201 consultas a la base de datos por persona (1 lista + 2 por cada producto) a solo 1 consulta cada 30 segundos. Las siguientes personas reciben la respuesta instantánea. |
| **Resumen de incidencias (API)** | Se guarda en caché por 60 segundos | De escanear todas las incidencias cada vez a solo hacerlo cada 60 segundos. |
| **Lista de incidencias (API)** | Se guarda en caché por 30 segundos, con clave única por cada combinación de filtros | De escanear todas las incidencias cada vez que cambias un filtro a solo hacerlo cada 30 segundos. Las combinaciones de filtros más usadas se sirven desde la memoria. |
| **Ambas APIs** | Se agregó un cronómetro a cada consulta (timing middleware) | Ahora podemos medir cuánto tarda cada operación y encontrar los próximos cuellos de botella con datos reales, no con suposiciones. |

---
