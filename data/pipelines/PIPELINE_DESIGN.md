# HealthCore --- Diseño del pipeline de desempeño de insumos por clínica

## 1. Propósito del pipeline

Generar el **Reporte Mensual de Desempeño de Insumos por Clínica** para
que la junta directiva, la CEO Dra. Okonkwo y Claire, Chief Compliance
Officer, puedan revisar por clínica el coste de insumos, el consumo, los
quiebres críticos de stock y el riesgo de vencimiento, con el paquete
listo el primer día hábil de cada mes.

## 2. Current State y brecha de negocio

### Estado actual

HealthCore opera 12 clínicas en Estados Unidos (Texas, Florida y
Georgia) y Reino Unido (Londres y Manchester). La aplicación ya captura
eventos operativos y los persiste en PostgreSQL/Supabase, en la tabla
`telemetry_events`. La tabla incluye, entre otros, `event_id`,
`timestamp`, `event_type`, `schema_version`, `request_id` y `tags`
(`JSONB`). El productor coloca en `tags` las propiedades del evento.

El endpoint `GET /telemetry/report`, implementado en
`services/telemetry/server_standalone.py` mediante el módulo
`services/telemetry/analysis.py`, responde actualmente **cinco métricas
concretas de observabilidad técnica** orquestadas por `run_all()`:

| # | Métrica | Función en `analysis.py` | Qué responde |
|---|---|---|---|
| 1 | Volumen de eventos por día | `events_per_day()` | ¿Cuántos eventos genera el sistema cada día calendario? |
| 2 | Tasa de error por tipo de evento | `error_rate_by_type()` | ¿Qué tipos de evento concentran los fallos del sistema? |
| 3 | Percentiles de latencia por ruta | `latency_percentiles_by_route()` | ¿Qué rutas son las más lentas? (P50, P95, P99) |
| 4 | Distribución de tipos de evento | `event_type_distribution()` | ¿Qué tipos de evento dominan el tráfico del sistema? |
| 5 | Tasa de fallo de login por día | `auth_failure_rate_by_day()` | ¿Qué días concentran más fallos de autenticación? |

Estas cinco métricas son de **observabilidad técnica** — responden preguntas
de ingeniería sobre el comportamiento del sistema de telemetría (volumen,
errores, latencia). El reporte se sirve con una caché en memoria de 60 segundos
a través de `server_standalone.py` y acepta ventanas de fechas arbitrarias vía
query params `start_date` / `end_date`. Ninguna de estas métricas consolida
los KPI financiero-operativos que necesita la junta directiva.

### Brecha de negocio

El reporte técnico no consolida los cuatro KPI de negocio requeridos en
una fila por clínica y mes, no publica una tabla analítica propia para
el dashboard y no proporciona una API independiente para consultar los
KPI o conocer el estado de ejecución del pipeline. Además, aunque el
esquema de telemetría se ha extendido para aceptar `total_cost` y
`currency` como campos opcionales de `inbound_order_created`, el
productor del evento aún no envía estos datos. El KPI de gasto se
calculará cuando los eventos incluyan el coste; mientras tanto, el
pipeline lo procesa con advertencias y marca el KPI como incompleto.

### Límites de la solución

-   `services/telemetry/analysis.py` y `GET /telemetry/report`
    permanecen intactos.
-   El pipeline lee `telemetry_events` en modo de solo lectura.
-   El pipeline nunca escribe resultados en `telemetry_events`.
-   Los resultados de negocio se guardan en tablas nuevas bajo el
    esquema `reporting` y se exponen desde un módulo nuevo
    `services/reporting/`.
-   El payload de `inbound_order_created` ya se ha extendido de forma
    aditiva (total_cost, currency como opcionales); no se introdujo un
    nuevo tipo de evento para ese fin.
-   No se incluyen `direct_stock_edit_rejected` ni otros eventos
    técnicos en los KPI de esta versión.

### Preguntas y respuestas antes de diseñar el Pipeline 

**IDEMPOTENCIA**

**1.1.** *Duplicados en el origen*
- El campo `eventId` del envelope será la clave de deduplicación. En la ingesta, la tabla `telemetry_events` ya utiliza una restricción única sobre `event_id` y `ON CONFLICT (event_id) DO NOTHING`, por lo que dos solicitudes con el mismo identificador no deberían crear dos registros. En el pipeline de reporting, los eventos se deduplicarán por `event_id` antes de calcular los KPI. La tabla de resultados mensuales utilizará una clave única por `clinic_id` y `month_start`, de forma que cada clínica tenga un único registro por mes.

**1.2.** *Reintento después de un fallo*
- Si una ejecución falla después de cargar 847 de las 1.412 filas previstas, el pipeline debe poder volver a ejecutarse sin duplicar los resultados ya insertados. Para ello, se utilizará un `upsert` sobre la clave única de la partición de reporting. Como el informe de HealthCore tiene granularidad mensual, la partición será el periodo mensual y la clínica; si posteriormente se implementan agregados diarios, la clave deberá incluir la fecha del día.
- El pipeline volverá a calcular los valores desde los eventos de origen y sustituirá los resultados de la partición correspondiente, en lugar de sumar los nuevos valores a los existentes. Así, una ejecución repetida producirá el mismo resultado que una ejecución limpia, siempre que los datos de origen y las reglas de cálculo sean iguales.

**1.3.** *Eventos tardíos*
- Si un evento llega después de haberse publicado el informe del periodo al que pertenece, el pipeline deberá identificar el periodo afectado y recalcularlo a partir de los eventos de origen. El resultado anterior se actualizará mediante `upsert`, evitando incrementar los KPI de forma acumulativa.
- Cada recálculo tendrá un `run_id` propio y registrará el periodo recalculado, el motivo de la ejecución, su estado y las marcas temporales correspondientes. De esta forma, el resultado vigente se mantiene actualizado y el historial permite identificar qué ejecución volvió a calcular el periodo y cuándo lo hizo.

**OBSERVABILIDAD**

**2.1.** *Silencio vs. ausencia real*
- Un intervalo sin eventos no significa necesariamente que el negocio haya dejado de operar. Para distinguir una actividad realmente nula de un fallo de captura o de una ejecución ausente, se implementará un mecanismo de *heartbeat* que registre que el sistema de captura y el pipeline siguen funcionando.
- Se registrarán, como mínimo, la última actividad de captura, la hora del último heartbeat, el número de eventos recibidos por intervalo y el estado de la última ejecución del pipeline. Si no llegan eventos durante un intervalo superior al umbral definido y tampoco se recibe el heartbeat esperado, se generará una alerta de posible fallo de captura. Si el heartbeat sigue funcionando y no hay eventos, se podrá investigar si se trata de un periodo sin actividad real.

**2.2.** *Trazabilidad de la recolección*
- Para reconstruir el camino desde la recepción de un evento hasta el informe de negocio, se correlacionarán el `requestId` del envelope y el `run_id` de cada ejecución del pipeline. También se registrarán el `event_id`, el tipo de evento, su timestamp de origen, la hora de recepción y el periodo de reporting al que contribuye.
- Cada ejecución guardará las cantidades de eventos leídos, validados, descartados por duplicidad y agregados, junto con su estado y duración. Estos datos permitirán investigar picos repentinos, huecos de captura, procesamiento repetido de ventanas y desfases entre la hora del evento y la hora de su procesamiento.

**2.3.** *Crecimiento vs. pérdida de datos*
- El volumen de eventos se comparará por día, tipo de evento y clínica, teniendo en cuenta los patrones habituales de actividad. También se contrastará con indicadores independientes, como las sesiones activas o las clínicas que han reportado durante ese periodo, siempre que esos datos estén disponibles.
- Por ejemplo, una reducción de 12.000 eventos a 800 no se interpretará automáticamente como una caída del negocio: se comprobará si corresponde a un patrón esperado, como el menor volumen de actividad durante el domingo, o si existen errores en `POST /telemetry`, clínicas sin reportar, duplicados o periodos sin captura.
- El sistema registrará las diferencias relevantes y generará alertas ante desviaciones que superen los umbrales definidos. Las sesiones activas y los indicadores de clínicas que reportan son señales de contraste propuestas, no datos que debamos asumir que ya existen en el repositorio.

**RECUPERABILIDAD**

**3.1.** *Caída de la base de datos:*
- El pipeline utilizará la tabla `pipeline_runs` para persistir el estado de cada ejecución y la última fase completada. Se registrarán fases como extracción, validación, agregación, carga y verificación, junto con el `run_id`, el periodo procesado, el estado y el error, si lo hubiera.
- Si Pandas termina la agregación pero falla la inserción en Supabase, la ejecución se marcará como fallida y se podrá reanudar desde la fase de carga si los datos agregados siguen disponibles y son válidos. Si no se conservan esos datos intermedios, se repetirá la agregación desde el origen.
- La carga será idempotente mediante `upsert`, por lo que repetir la fase de inserción no debe duplicar resultados. Los checkpoints se actualizarán únicamente después de confirmar que la fase correspondiente terminó correctamente.

**3.2.** *Buffer en el frontend:*
- Sí, puede tener sentido mantener un buffer temporal en el navegador para conservar eventos cuando un operador pierde la conexión. Por ejemplo, los 45 eventos acumulados durante 20 minutos sin Wi-Fi podrían enviarse en un lote al recuperar la conexión.
- El buffer debe conservar el `eventId` original de cada evento y evitar generar identificadores nuevos durante los reintentos. El backend seguirá siendo responsable de validar los eventos, deduplicarlos y confirmar su persistencia. El envío por lotes deberá respetar el esquema y las restricciones de tamaño del endpoint.
- El almacenamiento local tiene riesgos: puede borrarse, quedar inaccesible o exponer datos en el dispositivo. Por eso, solo se conservarán los datos necesarios, sin información sanitaria identificable, y se eliminarán del buffer una vez recibida una confirmación satisfactoria del servidor. La persistencia y deduplicación del lado del servidor serán las garantías principales.

**3.3.** *Reintento de transmisión:*
- El cliente enviará cada evento con su `eventId` estable y, cuando se adopte formalmente el mecanismo, con una cabecera `Idempotency-Key` que corresponda al identificador del evento. Si se produce un timeout, el cliente repetirá la solicitud con la misma clave, nunca con una nueva.
- El backend comprobará si el evento ya existe mediante la restricción única de `event_id`. Si se almacenó en el primer intento, el reintento deberá responder con un estado de éxito, por ejemplo `200 OK`, indicando que el evento ya estaba registrado. Si se procesa por primera vez, responderá con el estado de éxito definido para la ingesta. Así, el cliente no necesita distinguir entre un almacenamiento nuevo y uno previamente confirmado para dejar de reintentar.
- Los errores temporales, como un timeout o un error transitorio del servidor, podrán reintentarse con espera progresiva. Los errores permanentes de validación no deben reintentarse indefinidamente. El contrato exacto de respuestas deberá definirse al implementar este comportamiento; no se debe asumir que el endpoint actual ya devuelve estos resultados diferenciados.

**ASPECTOS TRANSVERSALES**

*Corridas concurrentes:*
- Para evitar que la ejecución programada de las 02:00 y una activación manual a las 02:05 procesen simultáneamente el mismo periodo, se implementará un bloqueo por ventana de reporting, identificado por el pipeline y el periodo mensual. Cada ejecución tendrá un `run_id` único para distinguirla de las demás.
- Antes de iniciar el procesamiento, el sistema comprobará si ya existe una ejecución activa para esa ventana. Si existe, la nueva solicitud deberá esperar o devolver una respuesta que indique que el pipeline ya está ejecutándose. El bloqueo debe ser atómico y gestionarse en un mecanismo compartido, como la base de datos, para que también funcione entre distintos procesos.
- La tabla de resultados utilizará `upsert` y una clave única por clínica y mes, pero esto no sustituye al bloqueo: dos ejecuciones podrían calcular datos en momentos diferentes y sobrescribirse. Cada corrida registrará su estado, las fases completadas, los errores y los tiempos de ejecución. Si una falla, podrá reintentarse o recuperarse desde el último checkpoint válido sin duplicar los resultados.

## 3. Entregable, granularidad y KPI obligatorios

El entregable es una fila por `clinic_id` y mes calendario.
`month_start` es el primer día del mes en UTC. El periodo de un evento
se determina mediante su `timestamp`, no por `created_at` ni por el
momento en que se ejecuta el pipeline.

| KPI | Definición de negocio | Cálculo |
|---|---|---|
| `total_supply_cost` | Coste total de los insumos recibidos por la clínica durante el mes | Suma del coste total de cada `inbound_order_created` válido |
| `supply_consumption_count` | Número de eventos de salida/consumo de insumos de la clínica durante el mes | Conteo de `outbound_order_created` |
| `critical_stockout_count` | Número de eventos que indican que el stock cruzó por debajo del umbral mínimo | Conteo de `stock_threshold_triggered` |
| `expiry_risk_count` | Número de eventos que señalan riesgo de vencimiento de insumos | Conteo de `supply_expiry_flagged` |

`department` se valida y conserva en la transformación de los eventos de
consumo, pero la tabla de destino de la versión 1 tiene granularidad
clínica-mes y no ofrece un desglose por departamento.

### País y moneda

-   Clínicas `US`: moneda `USD`.
-   Clínicas `UK`: moneda `GBP`.
-   No se convierten monedas ni se suman importes de USD y GBP entre sí.
-   `clinic_id` se normaliza al tipo de la tabla de destino. El país
    debe ser coherente con el mapeo autoritativo de clínica. Si no lo
    es, la fila/evento se excluye del cálculo y se registra una
    incidencia; no se adivina el país.

## 4. Contrato y formato de extracción

### Tabla fuente y acceso

-   **Tabla:** `telemetry_events`.
-   **Columnas relacionales usadas:** `event_id`, `timestamp`,
    `event_type`, `schema_version`, `request_id`, `tags`.
-   **Formato de propiedades:** `tags` es JSONB y contiene las
    propiedades permitidas del evento.
-   **Acceso:** rol de base de datos de solo lectura para la fuente.
-   **Filtro temporal:** intervalo UTC semiabierto,
    `timestamp >= month_start AND timestamp < next_month_start`.
-   **Tipos de evento incluidos:** `inbound_order_created`,
    `outbound_order_created`, `stock_threshold_triggered` y
    `supply_expiry_flagged`.

### Payload requerido por evento

| Tipo de evento | Propiedades necesarias para la transformación |
|---|---|
| `inbound_order_created` | `clinic_id`, `country`, `product_id`, `product_category`, `quantity`, `vendor_ref` y coste válido |
| `outbound_order_created` | `clinic_id`, `country`, `product_id`, `product_category`, `quantity`, `department`, `consumption_type` |
| `stock_threshold_triggered` | `clinic_id`, `country`, `product_id`, `product_category`, `quantity`, `threshold_quantity`, `threshold_version` |
| `supply_expiry_flagged` | `clinic_id`, `country`, `product_id`, `product_category`, `quantity`, `days_to_expiry`, `expiry_window_days` |

Los campos concretos se validan contra el contrato versionado de
telemetría. `event_id` es la identidad del evento; `timestamp` define el
mes de negocio. `vendor_ref` es un pseudónimo del proveedor, no su
nombre real, y no se necesita para calcular los KPI.

### Brecha del coste y extensión aditiva

**Estado: resuelta (octubre 2026).** El contrato del evento
`inbound_order_created` ya incluye `total_cost` (numérico, no negativo)
y `currency` (`USD`/`GBP`) como propiedades opcionales en el esquema de
telemetría (`docs/telemetry/event-schemas.json`). La validación del
endpoint `POST /telemetry` permite estos campos desde la actualización
del fichero de esquemas, sin cambios en el código de validación.

El pipeline (`_parse_cost` en `data/pipelines/transform.py`) acepta
`total_cost` desde su implementación inicial. Si el campo no está
presente, el evento se procesa igual pero se registra una advertencia
y el KPI `total_supply_cost` no se considera completo para esa clínica.

Reglas de uso del coste:

-   Preferir `total_cost`, que representa el importe total de la
    entrega.
-   Si el negocio decide enviar solo `unit_cost`, calcular
    `quantity × unit_cost` y documentarlo como contrato alternativo.
-   Si ambos campos existen, `total_cost` será autoritativo; una
    discrepancia frente a `quantity × unit_cost` genera advertencia.
-   El importe debe ser numérico, no negativo. La moneda debe
    ser `USD` para `US` y `GBP` para `UK`.
-   Si falta un coste válido, no convertirlo silenciosamente en cero.
    Contabilizar la incidencia y marcar la ejecución con advertencias;
    el KPI de gasto no se considera completo mientras existan entradas
    sin coste.

No se debe cambiar el nombre ni la semántica de `inbound_order_created`,
ni crear un nuevo evento solo para el coste.

### Cadencia de actualización

El flujo programado se ejecuta mensualmente para calcular el mes
calendario anterior completo y publicar el reporte a tiempo para el
primer día hábil. Se permite disparo manual para un `month_start`
concreto y recálculo de meses históricos cuando lleguen eventos tardíos.
La zona horaria de los límites de cálculo es UTC; la hora exacta de
despliegue se configura en Prefect.

## 5. Flujo de datos ETL

``` mermaid
flowchart TD
    A["Extracción: telemetry_events<br/>event_id, timestamp, event_type, tags JSONB"] --> B["Validación y deduplicación<br/>contrato + event_id"]
    B --> C["Transformación: KPI por clinic_id y month_start<br/>coste, consumo, stock crítico, vencimiento"]
    C --> D["Carga transaccional: reporting.monthly_clinic_supply_performance<br/>UPSERT por (clinic_id, month_start)"]
    D --> E["Verificación y auditoría<br/>reporting.pipeline_runs"]
    E --> F["services/reporting/<br/>estado, disparo manual y KPI del dashboard"]
```

### Etapas

1.  **Extracción --- `extract_inventory_events`:** lee solo los cuatro
    tipos de evento de negocio y el periodo solicitado de
    `telemetry_events`. La consulta no modifica la tabla fuente.
2.  **Transformación --- `validate_and_deduplicate_events` y
    `aggregate_monthly_clinic_kpis`:** valida el contrato, normaliza
    tipos, elimina duplicados por `event_id`, determina país/moneda y
    agrega los cuatro KPI por clínica y mes.
3.  **Carga --- `upsert_monthly_results`:** persiste el conjunto
    calculado en `reporting.monthly_clinic_supply_performance` dentro de
    una transacción.
4.  **Verificación y auditoría --- `verify_monthly_results` y
    `finalize_run_log`:** comprueba integridad y registra el resultado
    final en `reporting.pipeline_runs`.

Las clínicas sin eventos solo podrán publicarse con KPI cero si se
dispone de un catálogo autoritativo de las 12 clínicas.
`telemetry_events` por sí sola no prueba que una clínica sin eventos en
el periodo deba aparecer como fila con ceros.

## 6. Esquema de destino

La tabla de KPI se crea mediante migración controlada en un esquema
separado:

``` sql
CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.monthly_clinic_supply_performance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id text NOT NULL,
  country text NOT NULL,
  month_start date NOT NULL,
  total_supply_cost numeric NOT NULL DEFAULT 0,
  supply_consumption_count integer NOT NULL DEFAULT 0,
  critical_stockout_count integer NOT NULL DEFAULT 0,
  expiry_risk_count integer NOT NULL DEFAULT 0,
  currency text NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (clinic_id, month_start)
);
```

La clave única `(clinic_id, month_start)` impide más de una fila de KPI
por clínica y mes. La tabla operativa de ejecuciones se mantiene
separada:

``` sql
CREATE TABLE IF NOT EXISTS reporting.pipeline_runs (
  run_id uuid PRIMARY KEY,
  flow_name text NOT NULL,
  status text NOT NULL,
  current_phase text,
  checkpoint text,
  trigger_source text NOT NULL DEFAULT 'scheduled',
  recalculation_reason text,
  invalidates_run_id uuid REFERENCES reporting.pipeline_runs(run_id),
  month_start date NOT NULL,
  month_end date NOT NULL,
  started_at timestamptz NOT NULL,
  finished_at timestamptz,
  events_read integer NOT NULL DEFAULT 0,
  events_valid integer NOT NULL DEFAULT 0,
  events_rejected integer NOT NULL DEFAULT 0,
  events_deduplicated integer NOT NULL DEFAULT 0,
  rows_inserted integer NOT NULL DEFAULT 0,
  rows_updated integer NOT NULL DEFAULT 0,
  warning_count integer NOT NULL DEFAULT 0,
  error_message text,
  prefect_flow_run_id text
);
```

La tabla `reporting.pipeline_runs` es una propuesta de diseño para la
auditoría operativa; no sustituye la tabla de KPI. `current_phase` y
`checkpoint` identifican la última fase confirmada. `trigger_source`
distingue una ejecución programada de una manual. En un recálculo por
eventos tardíos, `recalculation_reason` explica el motivo e
`invalidates_run_id` puede señalar la ejecución anterior cuyo resultado
se está sustituyendo. Estos campos forman parte del diseño futuro y
deberán añadirse mediante migración antes de implementar el pipeline.

## 7. Actualizaciones, idempotencia y recuperación

### Actualizaciones a registros existentes

La carga usa
`INSERT ... ON CONFLICT (clinic_id, month_start) DO UPDATE`. En cada
recálculo se reemplazan los valores agregados del periodo y se actualiza
`computed_at`; no se incrementan los KPI sumando el resultado nuevo al
antiguo. La agregación se calcula de nuevo desde los eventos de origen
válidos del mes.

### Segunda corrida después de un fallo de carga

-   **Si la transacción falla antes del `COMMIT`:** PostgreSQL revierte
    todos los cambios de esa transacción. La siguiente ejecución vuelve
    a extraer y calcular el periodo y hace el upsert completo.
-   **Si el `COMMIT` se completó pero el proceso falló antes de marcar
    la ejecución como exitosa:** la siguiente ejecución vuelve a
    calcular el mismo periodo y actualiza las mismas claves únicas. No
    crea filas duplicadas ni suma los KPI dos veces; `computed_at`
    refleja la última carga confirmada.
-   **Si la ejecución falla a mitad de la fase de carga:** todas las
    filas de un periodo deben escribirse en una única transacción para
    evitar publicar un conjunto parcial como completo. Si el volumen
    obligara a dividirla, se necesitaría un mecanismo de
    staging/publicación atómica definido antes de implementar.
-   **Deduplicación de eventos:** `event_id` identifica cada evento. La
    restricción única de origen y el `ON CONFLICT (event_id) DO NOTHING`
    de la ingesta existente ayudan a evitar duplicados en
    `telemetry_events`; el pipeline también deduplica por `event_id` al
    procesar.
-   **Concurrencia:** aplicar un bloqueo por periodo (por ejemplo,
    advisory lock de PostgreSQL) o exclusión equivalente. Una segunda
    ejecución del mismo `month_start` debe esperar o devolver un estado
    explícito de ejecución ya activa.
-   **Eventos tardíos:** asignarlos al mes de su `timestamp` original y
    volver a calcular el mes afectado. La carga reemplaza el resumen
    anterior mediante upsert. Se crea un nuevo `run_id`, se registra el
    motivo del recálculo y, si se conoce, se referencia en
    `invalidates_run_id` la ejecución cuyo resultado se está sustituyendo.
    El historial de corridas se conserva; no se borra la auditoría anterior.
-   **Checkpoint:** la unidad de reporting recuperable es el mes
    (`month_start`), pero la recuperación técnica registra también la
    fase confirmada en `current_phase` y `checkpoint`. Cada checkpoint
    se actualiza solo después de completar correctamente una fase. Si
    Pandas ya terminó la agregación y Supabase falla al insertar, se
    reintenta la fase de carga si el resultado agregado se conservó de
    forma fiable; de lo contrario, se repiten extracción y agregación.
    La carga se realiza en una transacción, y el upsert permite repetirla
    sin duplicar resultados.

No se declara éxito hasta que la transacción de carga y las
verificaciones hayan terminado. Los fallos y advertencias quedan en
`reporting.pipeline_runs`; los reintentos automáticos se reservan para
fallos transitorios, no para datos que incumplen el contrato.

## 8. Prefect: flow, tasks y estados

**Flow principal:**
`monthly_clinic_supply_performance_flow(month_start)`.

Tasks alineadas con las etapas ETL:

1.  `resolve_period` --- valida `month_start` y calcula los límites UTC.
2.  `extract_inventory_events` --- extrae eventos de `telemetry_events`.
3.  `validate_and_deduplicate_events` --- valida el payload y deduplica
    por `event_id`.
4.  `aggregate_monthly_clinic_kpis` --- calcula los KPI por clínica y
    mes.
5.  `upsert_monthly_results` --- carga el resumen mediante upsert
    transaccional.
6.  `verify_monthly_results` --- valida unicidad, moneda, valores y
    cantidad de filas.
7.  `finalize_run_log` --- guarda contadores, advertencias y estado
    final.

Se utilizarán los siguientes estados de ejecución de Prefect, que se
reflejan en el campo `status` de `reporting.pipeline_runs`:

| Estado Prefect | Cuándo se aplica | Se refleja en `pipeline_runs.status` como |
|---|---|---|
| `Scheduled` | El flow está en cola, esperando ejecutarse (programación mensual o trigger manual) | `running` (aún no empezó a procesar) |
| `Pending` | Las dependencias del flow están resolviéndose | `running` |
| `Running` | Una o más tasks están en ejecución activa | `running` |
| `Completed` | Todas las tasks finalizaron sin error | `completed` |
| `Failed` | Una task lanzó una excepción no recuperable | `failed` |

Un error de task debe propagarse al flow y quedar reflejado en el registro
persistente. Las credenciales se gestionan mediante secretos/bloques de Prefect
o variables de entorno protegidas; nunca se guardan en el repositorio ni en logs.

## 9. Registro de ejecución y auditoría

`reporting.pipeline_runs` debe persistir, como mínimo, estos campos:

| Campo | Tipo de dato | Justificación de auditoría |
|---|---|---|
| `run_id` | UUID | Identifica de forma única la ejecución y permite correlacionar logs y reintentos. |
| `flow_name` | TEXT | Identifica el flow y la versión lógica del proceso ejecutado. |
| `status` | TEXT | Distingue ejecución en curso, exitosa o fallida; permite detectar reportes no actualizados. |
| `current_phase` | TEXT nullable | Identifica la fase ETL que está ejecutándose o falló. |
| `checkpoint` | TEXT nullable | Registra la última fase confirmada para orientar la recuperación. |
| `trigger_source` | TEXT | Distingue ejecución programada de ejecución manual. |
| `recalculation_reason` | TEXT nullable | Explica por qué se recalculó un periodo, por ejemplo, por llegada tardía. |
| `invalidates_run_id` | UUID nullable | Referencia la corrida previa cuyo resultado se sustituye, cuando corresponda. |
| `month_start` | DATE | Identifica el mes de negocio que se está calculando. |
| `month_end` | DATE | Registra el límite superior del periodo procesado. |
| `started_at` | TIMESTAMPTZ | Permite medir duración y reconstruir la secuencia de ejecución. |
| `finished_at` | TIMESTAMPTZ nullable | Registra finalización; nulo indica que aún no terminó o que falta cierre tras un fallo. |
| `events_read` | INTEGER | Mide el volumen de origen y facilita detectar extracciones vacías o anómalas. |
| `events_valid` | INTEGER | Cuantifica los eventos aceptados para el cálculo. |
| `events_rejected` | INTEGER | Hace visible la pérdida de cobertura por datos inválidos. |
| `events_deduplicated` | INTEGER | Permite auditar cuántos duplicados se detectaron y excluyeron. |
| `rows_inserted` | INTEGER | Registra cuántas filas de KPI se crearon por primera vez. |
| `rows_updated` | INTEGER | Registra cuántas filas existentes se recalcularon. |
| `warning_count` | INTEGER | Señala incidencias no fatales, como eventos sin coste o inconsistencias de moneda. |
| `error_message` | TEXT nullable, sanitizado | Explica el fallo sin almacenar payloads completos, secretos ni datos sensibles. |
| `prefect_flow_run_id` | TEXT nullable | Vincula el registro de negocio con los detalles técnicos de Prefect. |

Los logs deben incluir `run_id` y periodo, pero no payloads completos.
Las métricas operativas incluyen duración, última ejecución exitosa,
antigüedad de `computed_at`, eventos rechazados, recepciones sin coste,
discrepancias de moneda y retraso frente al primer día hábil.

### Heartbeat y alerta de silencio

Se propone añadir un heartbeat periódico del componente de captura y
monitorizar su última recepción. Si no llegan eventos durante un
intervalo configurado, pero el heartbeat sigue llegando, se investigará
si la ausencia de actividad es real. Si tampoco llega el heartbeat, se
generará una alerta de posible fallo de captura o conectividad. El
pipeline tendrá su propia señal de ejecución y su última ejecución
exitosa, para distinguir un fallo de captura de un pipeline que no corrió.
Los umbrales y la frecuencia del heartbeat se definirán durante la
implementación; no se consideran funcionalidades existentes.

### Correlación y anomalías de volumen

Los logs de ingesta conservarán `request_id` y `event_id`; los logs del
pipeline añadirán `run_id`, periodo y fase. La correlación permitirá
seguir un evento desde su solicitud de entrada hasta la corrida que lo
procesa, sin registrar el payload completo. Se compararán los conteos
por tipo de evento, clínica e intervalo con periodos históricos y, si
existen fuentes fiables, con sesiones activas o clínicas que reportan.
Un cambio de volumen genera una señal para investigar, no una conclusión
automática de crecimiento o pérdida de datos. La disponibilidad de
sesiones activas o de un heartbeat de cada clínica queda como
dependencia pendiente de confirmar.

## 10. API nueva de `services/reporting/`

Los endpoints pertenecen a un módulo independiente. Las funciones
importadas desde `data/pipelines/` se diseñan como una interfaz estable
entre API y pipeline; sus implementaciones se desarrollarán en los
siguientes hitos.

### `GET /reporting/pipeline-runs/latest` --- consulta de estado

Devuelve la ejecución más reciente: `run_id`, `flow_name`, `status`,
periodo, timestamps, contadores, advertencias y mensaje sanitizado si
falló.

-   Función de datos importada:
    `data.pipelines.run_store.get_latest_pipeline_run()`.
-   No inicia una nueva ejecución ni recalcula KPI.

### `POST /reporting/pipeline-runs` --- disparo manual

Acepta opcionalmente `month_start` (`YYYY-MM-DD`, primer día del mes).
Devuelve el identificador y estado inicial de la ejecución; no debe
bloquear la petición esperando el informe completo. Debe evitar
ejecuciones simultáneas del mismo periodo. El cron y el disparo manual
compartirán el mismo mecanismo de bloqueo atómico por pipeline y periodo;
`run_id` será único por corrida. Si ya hay una corrida activa para esa
ventana, la API devolverá un estado explícito de ejecución existente o
permitirá esperar según el contrato que se defina.

-   Función de datos importada:
    `data.pipelines.runner.trigger_monthly_clinic_supply_performance(month_start)`.
-   La función delega la ejecución a Prefect y registra la ejecución
    solicitada.

### `GET /reporting/monthly-clinic-supply-performance` --- consulta de KPI para el dashboard

Acepta `month_start` opcional. Si se omite, devuelve el último periodo
calculado disponible. Devuelve todas las filas disponibles para ese mes
con `clinic_id`, `country`, `month_start`, los cuatro KPI, `currency` y
`computed_at`. Si no existe un periodo calculado, responde
explícitamente sin datos; no inventa resultados.

-   Función de datos importada:
    `data.pipelines.reporting_queries.get_monthly_clinic_supply_performance(month_start)`.

Las rutas no cambian `GET /telemetry/report` ni
`POST /telemetry/events`. El disparo manual deberá protegerse con
autenticación/autorización apropiada.

## 11. Telemetría offline y entrega tardía

El pipeline consume eventos ya persistidos en el servidor; no lee
directamente la cola local de los clientes. Para tolerar periodos
offline, se propone que el productor conserve temporalmente los eventos
pendientes y los reintente al recuperar conectividad. El mecanismo exacto
(por ejemplo, almacenamiento local del navegador) queda pendiente de
decisión según los requisitos del frontend y las políticas de seguridad:

-   El mismo evento conserva el mismo `event_id` en todos los
    reintentos. El cliente no genera un identificador nuevo por cada
    intento.
-   La cola local confirma la entrega solo tras recibir una respuesta
    satisfactoria del servidor.
-   Los reintentos usan espera incremental, un límite razonable y
    tratamiento distinto para errores temporales y errores permanentes
    de validación.
-   El buffer puede perderse o ser borrado, puede duplicar envíos y
    puede entregar eventos fuera de orden. Debe almacenar solo lo
    necesario y nunca datos de pacientes o PHI. La garantía final de
    deduplicación recae en el backend, no en el navegador.
-   Si se usa un envío por lotes, cada evento conserva su propio
    `event_id` y el servidor debe informar qué elementos se aceptaron
    o rechazaron; no se asumirá que un lote completo tuvo éxito si la
    respuesta no lo confirma.
-   Si un evento se almacena después del cierre mensual, su `timestamp`
    original determina el periodo y se vuelve a calcular ese mes,
    dejando registro de la corrida que realizó el recálculo.
-   Las señales de fallo de entrega no deben incluir propiedades
    sensibles.

### Contrato de reintentos de `POST /telemetry`

Se propone que el cliente envíe `Idempotency-Key` con el valor estable
de `eventId` (o que el servidor documente explícitamente `eventId` como
la clave idempotente equivalente). La restricción única sobre
`event_id` sigue siendo la garantía de persistencia contra duplicados.
Si el primer request se guardó pero la respuesta se perdió por timeout,
el reintento con la misma clave debe recibir una respuesta de éxito
(por ejemplo, `200 OK` con un resultado que indique que el evento ya
estaba registrado) y no insertar otra fila. Una inserción nueva puede
responder con el código de éxito definido por el contrato de la API.

Los errores transitorios de red o servidor pueden reintentarse con
espera incremental. Los errores permanentes de validación deben
devolver un error claro y no reintentarse indefinidamente. El endpoint
actual ya evita la duplicación en base de datos mediante
`ON CONFLICT (event_id) DO NOTHING`, pero el comportamiento exacto de
las respuestas HTTP y la cabecera `Idempotency-Key` quedan como cambios
propuestos para implementación y verificación.

## 12. Privacidad y seguridad

El pipeline procesa exclusivamente datos operativos de inventario. No
lee tablas de pacientes y no almacena nombres, identificadores de
pacientes, diagnósticos, detalles de atención ni PHI real o simulada. La
agregación se hace por clínica y mes; `department` se utiliza solo como
dimensión operativa permitida en el evento de consumo.

Los errores se sanitizan y los logs contienen metadatos y contadores, no
payloads completos. Las credenciales se mantienen fuera del código. Los
permisos deben permitir lectura de `telemetry_events` y escritura
únicamente en las tablas autorizadas del esquema `reporting`.

## 13. Decisiones pendientes para la implementación

1.  Confirmar el contrato definitivo del coste (`total_cost`
    recomendado) y cómo se deriva/valida la moneda en el productor de
    `inbound_order_created`.
2.  Confirmar el catálogo autoritativo de las 12 clínicas para decidir
    cómo generar filas con actividad cero.
3.  Acordar la ventana de gracia y política de recálculo para eventos
    tardíos.
4.  Confirmar versión y despliegue de Prefect.
5.  Definir autorización de los endpoints, especialmente el disparo
    manual.
6.  Definir si el estado de ejecución se inserta al inicio y se
    actualiza durante el flow, y cómo se reconcilia una caída abrupta
    del worker.
7.  Definir frecuencia y umbral del heartbeat, así como quién lo emite
    y cómo se entrega la alerta de silencio.
8.  Confirmar si existen métricas fiables de sesiones activas o clínicas
    que reportan para contrastar el volumen de eventos.
9.  Definir y probar el contrato HTTP de idempotencia para `POST /telemetry`,
    incluida la respuesta a duplicados y el uso de `Idempotency-Key`.
10. Confirmar el mecanismo de buffer offline y el envío por lotes, si
    corresponde, según las capacidades del frontend.

## 14. Frecuencia y ejecución del pipeline

### Frecuencia prevista

El pipeline se ejecuta **el primer día hábil de cada mes a las 07:00 UTC**,
de forma que la CEO y el equipo directivo dispongan del reporte mensual
consolidado desde la mañana del primer día laboral.

| Concepto | Valor |
|---|---|
| Cadencia | Mensual |
| Día de ejecución | Primer día hábil del mes |
| Hora objetivo | 07:00 UTC |
| Período procesado | Mes natural anterior completo |
| Trigger por defecto | `scheduled` |

### Mecanismo de disparo

El pipeline acepta tres orígenes de disparo (`--trigger`):

| Trigger | Uso previsto |
|---|---|
| `scheduled` | Ejecución automática programada (cron mensual) |
| `manual` | Disparo ad-hoc desde la API o CLI por un operador |
| `recalculation` | Recálculo solicitado tras ingreso de eventos tardíos del período |

Los eventos que lleguen después del cierre mensual conservan su `timestamp`
original y fuerzan un recálculo del mes correspondiente. La tabla de destino
es idempotente (`ON CONFLICT (clinic_id, month_start) DO UPDATE`), por lo que
repetir la ejecución para un mismo mes es seguro: los valores se reemplazan
con los nuevos cómputos, no se acumulan.

### Ejecución como CLI

El archivo ``data/pipelines/pipeline.py`` es el punto de entrada ejecutable:

```bash
# Procesar el mes anterior (por defecto)
python data/pipelines/pipeline.py

# Procesar un mes específico
python data/pipelines/pipeline.py --month 2026-07-01

# Especificar el origen del disparo
python data/pipelines/pipeline.py --month 2026-07-01 --trigger scheduled

# Inicializar esquema reporting antes de ejecutar
python data/pipelines/pipeline.py --init-schema

# Salida JSON (para integrar con wrappers)
python data/pipelines/pipeline.py --month 2026-07-01 --json
```

### Integración con cron (ejemplo)

```cron
# Todos los primeros días hábiles a las 07:00 UTC
# Ajustar según calendario de días festivos
0 7 1 * * cd /opt/healthcore && python data/pipelines/pipeline.py --trigger scheduled >> /var/log/healthcore/pipeline.log 2>&1
```

### Ejecución como librería

Desde código Python:

```python
from data.pipelines.runner import trigger_monthly_clinic_supply_performance

# Disparo programado
result = trigger_monthly_clinic_supply_performance(
    month_start="2026-07-01",
    trigger_source="scheduled",
)
```

Los endpoints de ``services/reporting/`` exponen el disparo vía
``POST /reporting/pipeline-runs`` y la consulta de resultados vía
``GET /reporting/monthly-clinic-supply-performance``.

### Dependencias de infraestructura

- **Base de datos:** PostgreSQL / Supabase con el esquema `reporting` creado.
  La inicialización automática se realiza al arrancar ``services/reporting/main.py``
  o manualmente con ``--init-schema``.
- **Prefect:** Se necesita una instancia del servidor Prefect para la
  orquestación de flows. Si no hay servidor externo, Prefect inicia uno
  efímero automáticamente (modo EPHEMERAL).
- **Variables de entorno:** ``DATABASE_URL`` debe estar configurada en
  ``services/api/.env``.

### Decisiones resueltas

Varias de las decisiones abiertas en la sección anterior (13) han sido
implementadas:

| # | Decisión | Resolución |
|---|---|---|
| 4 | Versión y despliegue de Prefect | Prefect 3.8.8 instalado vía pip en el entorno. Sin servidor persistente dedicado — el worker inicia servidor efímero automáticamente. |
| 5 | Autorización de endpoints | JWT Bearer token, validado con la misma `JWT_SECRET_KEY` y algoritmo HS256 que el API principal de services/api/. |
| 6 | Registro de ejecución | Sí: se inserta al inicio (`create_pipeline_run` en `run_store.py`) y se actualiza durante el flow. Una caída abrupta deja el registro con estado `failed` y checkpoint parcial. |
| 7 | Frecuencia y heartbeat | Frecuencia mensual definida aquí. No hay heartbeat interno del pipeline (la tarea dura minutos, no horas). |
| 8 | Duración esperada | < 5 minutos para 12 clínicas, < 15 minutos bajo carga máxima (estimado). |


## 15. Checklist de aceptación

-   [x] Existe una sección `Current State` y se explica la brecha del
    reporte de telemetría.
-   [x] Se especifican tablas, columnas, formato JSONB de propiedades y
    cadencia de extracción.
-   [x] El propósito nombra el entregable de negocio y los cuatro KPI
    concretos.
-   [x] Se preservan `services/telemetry/analysis.py` y
    `GET /telemetry/report`; no se escribe en `telemetry_events`.
-   [x] Los resultados viven en `reporting` y se exponen desde
    `services/reporting/`.
-   [x] El flujo ETL tiene extracción, transformación y carga con
    nombres reales.
-   [x] Se documentan upsert y recuperación explícita tras fallo
    antes/después del commit.
-   [x] El registro de ejecución define campos, tipos y justificación de
    auditoría.
-   [x] Prefect tiene un flow principal y tasks con nombres concretos.
-   [x] Se definen tres endpoints y las funciones de `data/pipelines/`
    que importan.
-   [x] Los eventos y KPI corresponden al contexto de HealthCore; el
    coste faltante queda declarado como brecha, no se inventa.
-   [x] La brecha del coste se cerró añadiendo `total_cost` y `currency` como
    propiedades opcionales de `inbound_order_created` en el esquema de
    telemetría. El pipeline ya lo acepta; falta el productor.



## 16. Mejora implementada: Bloqueo de concurrencia por periodo

### Problema de diseño

La sección 13 del presente documento identificó un problema de concurrencia en la línea 339:

> **Concurrencia:** aplicar un bloqueo por periodo (por ejemplo, advisory lock de PostgreSQL) o exclusión equivalente. Una segunda ejecución del mismo `month_start` debe esperar o devolver un estado explícito de ejecución ya activa.

El escenario concreto que se buscaba evitar es el siguiente:

1. El pipeline está programado para ejecutarse todos los días 1 a las 02:00 UTC vía cron (`trigger_source = "scheduled"`).
2. Un operador, sin saber que la ejecución automática está en curso, dispara manualmente el mismo pipeline a las 02:05 para el mismo `month_start`.
3. Ambas ejecuciones leen, transforman y publican los mismos datos simultáneamente.
4. Aunque la tabla destino usa `ON CONFLICT ... DO UPDATE` (upsert), las dos ejecuciones compiten por escribir, generando picos de carga innecesarios, duplicación de eventos leídos, y posible incoherencia en los registros de auditoría (`pipeline_runs`).

### Solución implementada

Se optó por un **bloqueo a nivel de aplicación, coordinado por base de datos**, que no requiere drivers adicionales ni permisos de superusuario. Consiste en dos piezas:

#### a) `has_active_run_for_period(target_engine, month_start) -> tuple[bool, str | None]`

- **Ubicación:** `data/pipelines/run_store.py`
- **Comportamiento:** Ejecuta `SELECT count(*) FROM reporting.pipeline_runs WHERE status = 'running' AND month_start = :month_start`. Si el conteo es mayor a cero, retorna `(True, run_id)`; si no, `(False, None)`.
- **Justificación:** La tabla `pipeline_runs` es el único punto de verdad compartido entre procesos. Consultar el estado directamente en ella evita introducir un mecanismo de coordinación separado (Redis, advisory locks, etc.) que añadiría latencia y complejidad operativa. La columna `status` se actualiza a `'completed'` o `'failed'` al finalizar, por lo que una ejecución activa siempre tendrá `status = 'running'`.

#### b) Integración en `trigger_monthly_clinic_supply_performance()`

- **Ubicación:** `data/pipelines/runner.py`
- **Flujo:**
  1. Se resuelve el período (`task_resolve_period`).
  2. Se obtiene el engine de destino (`get_target_engine()`).
  3. Se invoca `has_active_run_for_period(target_engine, month_start)`.
  4. Si hay una ejecución activa, la función retorna inmediatamente un diccionario con `{"status": "already_running", "run_id": <id>, "month_start": month_start, "message": "Ya existe una ejecución activa para este período"}`.
  5. Si no la hay, continúa con la creación del `run_id` y la ejecución normal.
- **Manejo de errores:** Si la consulta falla (base de datos caída, timeout), el bloque se captura con `try/except`, se registra una advertencia y se permite la ejecución de todas formas (fail-open). Esto evita que un problema de conectividad impida ejecutar el pipeline.

### Análisis de alternativas descartadas

| Alternativa | Motivo de descarte |
|---|---|
| **Advisory lock de PostgreSQL** (`pg_advisory_xact_lock`) | Es la solución más robusta, pues elimina cualquier ventana de competencia. Sin embargo, requiere permisos para llamar funciones del sistema y añade una dependencia directa del motor de base de datos. Se deja como mejora futura si la tasa de colisiones crece. |
| **Redis / lock distribuido** | Introduciría una nueva infraestructura (Redis) solo para este bloqueo, incrementando la complejidad operativa y el costo de mantenimiento. |
| **Archivo PID lock** (`/var/run/pipeline.lock`) | No funciona en entornos serverless o con múltiples workers. Tampoco es atómico entre contenedores. |
| **Esperar (sleep + reintento)** | Bloquea el worker sin garantía de liberación predecible. Aumenta la latencia sin resolver la competencia real. |

### Riesgo residual y mitigación

Existe una **ventana de competencia pequeña** entre el `SELECT` de `has_active_run_for_period()` y el `INSERT` del nuevo `pipeline_run`: dos procesos podrían ejecutar el SELECT simultáneamente, ambos obtener `count = 0`, y ambos crear un registro. Este riesgo se mitiga con:

- La restricción de unicidad en la base de datos (si se define un índice único sobre `(month_start, status)` filtrando por `status = 'running'`).
- La idempotencia del upsert en la tabla de KPI: aunque dos ejecuciones corran en paralelo, los datos finales son los mismos.
- La auditoría conserva ambos `run_id`; el equipo puede identificar ejecuciones solapadas.

Para eliminar esta ventana por completo, en una iteración futura se implementará un `pg_advisory_xact_lock(month_start_hash)` antes del SELECT, lo que serializaría las ejecuciones concurrentes para el mismo período.

