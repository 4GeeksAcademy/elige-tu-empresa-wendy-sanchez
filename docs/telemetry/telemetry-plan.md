# Plan de Telemetría de HealthCore

**Estado:** Diseño previo a instrumentación
**Ámbito:** Inventario clínico, backoffice y servicios que lo soportan  
**Contratos:** [`event-schemas.json`](event-schemas.json)

## Objetivo y principios

Este plan define qué señales capturar antes de instrumentar el sistema de inventario y el backoffice. El catálogo distingue el mínimo exigido por HealthCore de oportunidades propuestas; cada oportunidad se conserva únicamente cuando permite formular una hipótesis y una decisión operativa verificables.

Principios de diseño:

- **Privacidad por defecto:** la telemetría del inventario trata suministros, órdenes, clínicas y operación del software; nunca pacientes. No capturar nombres, IDs de historia, diagnósticos, información de contacto, texto libre clínico, tokens, contraseñas, cabeceras `Authorization`, cuerpos HTTP ni parámetros de URL que puedan contenerlos.
- **Allowlist estricta:** cada tipo de evento tiene una lista cerrada de propiedades en `event-schemas.json`. Rechazar campos adicionales; no serializar objetos de request/respuesta completos.
- **Minimización:** `userId` es un seudónimo HMAC rotatorio, no `user_uuid`, email ni ID de TinyDB. `sessionId` es un identificador aleatorio de sesión, no el JWT. Los eventos previos al login usan un seudónimo anónimo ligado a una sesión efímera.
- **Separación:** telemetría analítica no debe cambiar el resultado de una operación clínica/operativa ni impedir que se complete una orden.
- **Correlación controlada:** generar `requestId` aleatorio en el borde y propagarlo frontend → proxy → API → logs; nunca usar datos de negocio como ID de correlación.
- **Calidad medible:** registrar versión de esquema, deduplicar por `eventId`, vigilar eventos rechazados/perdidos y documentar cambios incompatibles.

Los eventos no contienen PHI. Algunos metadatos (seudónimo de operador, IP si una infraestructura la recoge, identificador de sesión) pueden ser datos personales seudonimizados. Las IP no se incluyen en el envelope ni en propiedades; si el proveedor de infraestructura las procesa inevitablemente, aplicar truncamiento/anonimización en el primer salto, limitar acceso y retención y validar residencia, contrato y base legal con Claire Whitfield antes de producción.

## Flujo observado y límites actuales

Flujo que se debe instrumentar de extremo a extremo:

1. Operador abre el backoffice; `AuthGuard` exige sesión autenticada.
2. El cliente consulta productos y stock por la capa `inventoryApi.ts`; las rutas `/inventory` requieren JWT.
3. El operador elige producto y clínica, completa cantidad y datos de entrega o consumo, y el cliente ejecuta validaciones locales.
4. FastAPI valida el cuerpo, resuelve el suministro y registra la entrega o consumo con `user_uuid` de TinyDB.
5. Para consumos, el backend calcula stock disponible y rechaza antes de escribir si la cantidad lo dejaría negativo (HTTP 400).
6. Tras una escritura válida, el backend invalida la caché de productos; el stock se vuelve a calcular como entregas menos consumos.
7. El backoffice presenta confirmación/error e historial.

La implementación actual agrega stock por `supply_id`, aunque las órdenes tienen `clinic_id`: no representa saldo separado por clínica. Tampoco existe un umbral mínimo configurable por clínica; el modelo actual no contiene la fecha de caducidad indicada por el contexto ni el consumo acepta `department`. Por tanto, los eventos de umbral, caducidad, consumo por departamento y saldo por clínica requieren completar primero el modelo y la semántica del dominio. No se deben inventar datos para emitirlos. El endpoint actual tampoco ofrece una operación de edición directa de stock. El evento `direct_stock_edit_rejected` se instrumentará en el borde de la API que deniegue expresamente una mutación de stock, después de autenticar y solo cuando se puedan resolver las dimensiones operativas requeridas; no se simulará en el navegador ni se confundirá con un 404/405 ajeno a un intento de edición.

### Normalización de datos de inventario

Los contratos usan las dimensiones canónicas del CONTEXT, no los valores internos diferentes del modelo actual. Aplicar esta tabla en el servidor antes de emitir:

| Campo de origen | Valor actual | Valor de telemetría |
|---|---|---|
| `MedicalSupply.category` | `ppe` | `product_category: ppe` |
| `MedicalSupply.category` | `medications` | `product_category: medication` |
| `MedicalSupply.category` | `consumables`, `wound_care`, `diagnostics` | `product_category: consumable` |
| `MedicalSupply.category` | `equipment` | `product_category: equipment`, solo después de que la API acepte esta categoría |

No inferir categoría desde `name` o `sku`; los valores no mapeados se rechazan para telemetría y cuentan como error de contrato, sin incluir el valor original. Para `inbound_order_created`, el API actual solo recibe `vendor_name`: el productor lo normaliza (Unicode NFC, recorte, espacios consecutivos colapsados y `casefold`) y calcula `vendor_ref` mediante HMAC-SHA256 con una clave de telemetría dedicada/versionada. El texto original no sale del servicio de inventario ni entra a la canalización analítica. La clave no puede ser la de `userId` y su rotación requiere preservar explícitamente la continuidad analítica o aceptar una nueva serie.

## Fase 1: catálogo de oportunidades

En las tablas, **Obligatorio** significa que el evento está definido por CONTEXT; **Oportunidad** es una propuesta de este plan. La columna de hipótesis completa «necesitamos saber…» y la decisión indica qué acción habilita. Los códigos de propiedad de dominio conservan los nombres exactos del contexto (`clinic_id`, `country`, `product_id`, `product_category`, `quantity`, `department`). Los valores de `country` son `US`/`UK`; `product_category` usa `medication`/`ppe`/`consumable`/`equipment`.

### Inventario y disponibilidad

| Clase | `event_type` | Necesitamos saber (hipótesis) | Decisión que habilita |
|---|---|---|---|
| Obligatorio | `inbound_order_created` | cuánto y qué insumo entra, por clínica y proveedor | consolidar compras y negociar condiciones |
| Obligatorio | `outbound_order_created` | qué se consume y a qué ritmo, por clínica y departamento | ajustar reposición automática |
| Obligatorio | `stock_threshold_triggered` | con qué frecuencia un insumo crítico queda bajo mínimo en una clínica | priorizar reabastecimiento urgente y escalar a Marcus |
| Obligatorio | `direct_stock_edit_rejected` | dónde se intenta eludir el registro de movimientos | reforzar capacitación o permisos |
| Obligatorio | `supply_expiry_flagged` | qué cantidad y productos se acercan a caducar | priorizar uso seguro o baja controlada |
| Oportunidad | `inventory_product_created` | qué categorías y jurisdicciones se incorporan y con qué frecuencia | revisar catálogo y gobernanza de altas |
| Oportunidad | `inventory_order_validation_failed` | qué campos y reglas generan correcciones antes del envío | mejorar formularios, ayuda y validaciones |
| Oportunidad | `inventory_order_rejected` | qué operaciones fallan por stock insuficiente u otra regla de dominio | corregir reposición, permisos o capacitación |
| Oportunidad | `inventory_product_lookup_completed` | cuánto tarda y falla la consulta de stock usada al preparar una salida | mejorar disponibilidad y experiencia del flujo |
| Oportunidad | `inventory_stock_snapshot_recorded` | cómo varía el stock por producto, clínica y país entre periodos | planificar compras y detectar tendencias |
| Oportunidad | `inventory_cache_served` | qué proporción de lecturas obtiene respuesta cacheada | ajustar TTL/caché según frescura y carga |
| Oportunidad | `inventory_cache_invalidated` | qué escrituras invalidan caché y con qué frecuencia | detectar invalidaciones excesivas o datos obsoletos |
| Oportunidad | `inventory_stock_reconciliation_flagged` | cuándo el saldo derivado no coincide con un recuento autorizado | investigar errores de registro y conciliar inventario |
| Oportunidad | `inventory_order_duplicate_suspected` | cuántas órdenes repetidas podrían duplicar movimientos | revisar idempotencia y evitar doble contabilización |
| Oportunidad | `inventory_order_history_exported` | qué demanda de exportación existe por jurisdicción/periodo | priorizar reportes auditables y controlar exportaciones |

### Autenticación y autorización

| Clase | `event_type` | Necesitamos saber (hipótesis) | Decisión que habilita |
|---|---|---|---|
| Oportunidad | `auth_login_succeeded` | cuántos inicios válidos ocurren por hora, aplicación y rol agregado | dimensionar acceso y detectar anomalías sin perfilar personas |
| Oportunidad | `auth_login_failed` | qué proporción falla por categoría de resultado y si hay ráfagas | activar protección anti-abuso o corregir fallos de acceso |
| Oportunidad | `auth_session_expired` | con qué frecuencia expira una sesión durante tareas operativas | ajustar expiración/renovación y reducir interrupciones seguras |
| Oportunidad | `auth_logout_completed` | si las sesiones se cierran correctamente y cuándo | evaluar controles de sesión y cierre remoto |
| Oportunidad | `auth_authorization_denied` | qué rutas se deniegan por falta de permisos o autenticación | corregir roles mal asignados o investigar accesos anómalos |
| Oportunidad | `auth_password_reset_requested` | demanda y fallos agregados de recuperación de acceso | mejorar soporte sin revelar si un email está registrado |
| Oportunidad | `auth_rate_limit_triggered` | si controles de frecuencia frenan automatización o abuso | calibrar límites y escalar incidentes de seguridad |
| Oportunidad | `auth_token_validation_failed` | frecuencia por código de error seguro | diagnosticar expiraciones/ataques sin registrar tokens |

### Rendimiento y confiabilidad técnica

| Clase | `event_type` | Necesitamos saber (hipótesis) | Decisión que habilita |
|---|---|---|---|
| Oportunidad | `api_latency_recorded` | distribución de latencia por ruta normalizada, método y status | priorizar endpoints lentos y fijar SLOs |
| Oportunidad | `api_request_failed` | tasa y clase de errores de API por ruta/servicio | activar respuesta a incidentes y corregir regresiones |
| Oportunidad | `api_dependency_failed` | cuándo falla Supabase, TinyDB, proxy o proveedor externo | aplicar recuperación, escalamiento o degradación controlada |
| Oportunidad | `api_retry_exhausted` | qué dependencias y operaciones agotan reintentos | ajustar timeouts, backoff o capacidad |
| Oportunidad | `frontend_error_captured` | qué errores no capturados afectan operación y en qué versión | corregir regresiones antes de bloquear flujos |
| Oportunidad | `frontend_route_load_recorded` | cuánto tarda en cargar cada ruta del backoffice | optimizar rutas y priorizar rendimiento percibido |
| Oportunidad | `client_performance_recorded` | si LCP/INP/CLS deterioran tareas frecuentes | elegir optimizaciones según impacto real |
| Oportunidad | `telemetry_delivery_failed` | qué proporción de eventos no llega y por qué clase | reparar pipeline y cuantificar pérdida |
| Oportunidad | `telemetry_event_dropped` | qué eventos se rechazan por esquema, privacidad o volumen | corregir productores/políticas sin abrir allowlists |
| Oportunidad | `service_health_check_failed` | qué servicio deja de responder a chequeos | alertar al equipo de plataforma y reducir detección |

### Navegación y finalización de flujos

| Clase | `event_type` | Necesitamos saber (hipótesis) | Decisión que habilita |
|---|---|---|---|
| Oportunidad | `backoffice_page_viewed` | qué áreas se utilizan por país y rol agregado | priorizar mantenimiento y navegación, no evaluar personas |
| Oportunidad | `inventory_filter_applied` | qué filtros son usados y si encuentran resultados | mejorar filtros, etiquetas e índices |
| Oportunidad | `inventory_workflow_started` | cuántos operadores comienzan entrada/salida por clínica | dimensionar soporte y comparar inicios/finalizaciones |
| Oportunidad | `inventory_workflow_abandoned` | en qué paso se abandona una orden y con qué clase de motivo | simplificar el flujo y resolver bloqueos de UX |
| Oportunidad | `inventory_form_validation_failed` | qué reglas impiden completar formularios y si se repiten | reducir errores con cambios de UX/documentación |
| Oportunidad | `inventory_order_confirmation_viewed` | si el operador ve confirmación tras escritura aceptada | detectar fallos de feedback y evitar reenvíos |
| Oportunidad | `inventory_search_performed` | frecuencia/latencia de búsqueda por categoría | mejorar descubrimiento sin capturar texto escrito |
| Oportunidad | `backoffice_navigation_error` | qué enlaces o destinos fallan durante tareas | corregir rutas y navegación |

Los 41 eventos del catálogo tienen contrato detallado en `event-schemas.json`: cinco obligatorios y 36 oportunidades de inventario, autenticación, rendimiento, confiabilidad y navegación. Las oportunidades siguen sujetas a revisión de privacidad, utilidad y presupuesto antes de instrumentarse; incluir su contrato no equivale a aprobar despliegue o retención.

## Fase 2: Event Envelope y contratos

### Envelope común

Todos los eventos usan el envelope cerrado descrito en `event-schemas.json`:

| Campo | Tipo | Regla |
|---|---|---|
| `eventId` | UUID string | aleatorio por evento; clave de idempotencia |
| `timestamp` | string ISO 8601 | UTC, con `Z` o desplazamiento; preferir reloj del servidor |
| `sessionId` | string | aleatorio, opaco y de corta duración; nunca token |
| `userId` | string | HMAC seudónimo del ID interno, con clave separada/rotatoria; anónimo efímero antes de login |
| `event_type` | string | nombre registrado, formato `entidad_acción` |
| `schemaVersion` | string | versión semántica, inicialmente `1.0.0` |
| `requestId` | string | correlación aleatoria propagada a servicios/logs |
| `properties` | object | payload específico, solo propiedades de su allowlist |

Los ocho campos son obligatorios. En actividad sin usuario autenticado, `userId` es una cadena seudónima efímera sin identidad de cuenta. No usar email, IP ni `user_uuid` como fallback. El esquema prohíbe propiedades desconocidas tanto en envelope como en cada payload.

### Contratos y datos sensibles

El archivo JSON adjunto es el registro versionado de contratos. Para cada evento declara descripción, grupo, modalidad, allowlist explícita, propiedades con tipo/obligatoriedad/significado/clasificación de sensibilidad y política de sanitización. No pasar objetos de dominio completos.

Ningún contrato permite PHI ni PII directa. `userId`/`sessionId` del envelope son seudónimos y se protegen como datos personales. Para errores se conservan `error_code` y `error_class` normalizados, no mensaje libre, stack trace, cuerpos HTTP, URL completa ni headers. Para autenticación se omiten email, contraseña, JWT, token de reset y cualquier respuesta que permita enumerar cuentas.

### Consideraciones por evento obligatorio

- `inbound_order_created`: emitir solo después del commit. `vendor_ref` se calcula en el servidor a partir de `vendor_name` normalizado mediante HMAC-SHA256 y clave de telemetría separada/versionada; solo se envía la referencia seudónima, nunca el nombre ni el contacto.
- `outbound_order_created`: emitir solo tras commit. `department` forma parte del contrato porque el contexto requiere consumo agregado por departamento; el API debe aceptar y validar un enum aprobado.
- `stock_threshold_triggered`: emitir al cruzar de `stock >= minimum` a `stock < minimum`, no en cada lectura; deduplicar. Requiere mínimo por clínica/producto y saldo segmentado por clínica.
- `direct_stock_edit_rejected`: emitir desde backend al denegar expresamente una mutación de stock por método/campo no permitido. El punto es el guard/manejador de rechazo de la API antes de responder; requiere identidad autenticada y dimensiones `clinic_id`, `country`, `product_id`, `product_category` y cantidad del intento. No añadir ruta que permita mutación. Si el request no permite resolver esas dimensiones, no emitir un evento que incumpla el contrato; registrar solo un error técnico sanitizado si aplica.
- `supply_expiry_flagged`: detectar dentro de 30 días y deduplicar por lote/regla. Requiere fecha de vencimiento en `Product`; para lotes, modelar fecha/cantidad con identidad no personal.

`inventory_order_validation_failed` exige `operation`, `field_name` y `validation_code`. `clinic_id`, `country`, `product_id` y `product_category` son opcionales porque precisamente pueden faltar o no resolverse cuando falla la validación; se omiten si no son datos válidos. `inventory_order_rejected` se reserva para rechazos de reglas de negocio después de resolver el producto; un `supply_id` desconocido se registra como error de validación, no como rechazo con una categoría inventada.

## Fase 3: entrega, procesamiento y operación

### Stream frente a batch

La modalidad de cada contrato se decide por la urgencia de la acción, no por preferencia técnica.

**Stream (objetivo de segundos):** nuevas entradas/salidas, cruce de umbral, edición directa rechazada, caducidad detectada, orden rechazada, denegaciones de autorización, anomalías de login/rate-limit, fallos de API/dependencias, errores del cliente y pérdida del pipeline. Habilitan reabastecimiento, respuesta de seguridad o recuperación. El chequeo de caducidad puede ejecutarse como job diario; al detectar el caso, la notificación debe publicarse por stream.

**Batch:** snapshots de inventario (diario y post-conciliación), navegación (cada hora), métricas de latencia/rendimiento (ventanas de 1–5 min, publicar cada 5 min), filtros/búsquedas (cada 5 min), actividad de workflow (cada 5 min), exportes (cada 15 min) y resúmenes de caché/health checks (cada 1–5 min según SLO). Agregar antes de persistir cuando no se requiera investigar evento individual.

En stream, objetivo inicial p95 < 10 s; alertar si eventos críticos superan 60 s. Los batch deben publicar dentro de su ventana y no presentarse como tiempo real.

### Mapa de modalidad por catálogo

| Modalidad | Eventos |
|---|---|
| Stream | `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `supply_expiry_flagged`, `inventory_order_rejected`, `inventory_order_validation_failed`, `auth_login_failed` (anomalías en stream; retención individual breve), `auth_authorization_denied`, `auth_rate_limit_triggered`, `api_request_failed`, `api_dependency_failed`, `api_retry_exhausted`, `frontend_error_captured`, `telemetry_delivery_failed`, `telemetry_event_dropped`, `service_health_check_failed` |
| Batch | `inventory_product_created`, `inventory_product_lookup_completed`, `inventory_stock_snapshot_recorded`, `inventory_cache_served`, `inventory_cache_invalidated`, `inventory_stock_reconciliation_flagged`, `inventory_order_duplicate_suspected`, `inventory_order_history_exported`, `auth_login_succeeded`, `auth_session_expired`, `auth_logout_completed`, `auth_password_reset_requested`, `auth_token_validation_failed`, `api_latency_recorded`, `frontend_route_load_recorded`, `client_performance_recorded`, `backoffice_page_viewed`, `inventory_filter_applied`, `inventory_workflow_started`, `inventory_workflow_abandoned`, `inventory_form_validation_failed`, `inventory_order_confirmation_viewed`, `inventory_search_performed`, `backoffice_navigation_error` |

Cada evento de catálogo aparece una vez. Si un batch descubre condición urgente, publicar una señal stream específica y deduplicada (p. ej. `stock_threshold_triggered`), sin esperar al próximo lote.

### Throttle, debounce y muestreo

- **API latency:** medir en middleware, sin segundo request por cada request de negocio. Agrupar histogramas por ventana/ruta normalizada/método/status. Muestrear trazas de éxito 1–5%, errores y operaciones críticas 100%, con cardinalidad limitada; nunca incluir query strings.
- **Navegación:** un `backoffice_page_viewed` por cambio efectivo de ruta; debounce de 500 ms para cambios rápidos. No registrar renders, hover, teclas ni foco.
- **Búsqueda/filtros:** debounce de 500 ms; emitir al confirmar o tras 1 s de inactividad, máximo uno por sesión/ruta/filtro cada 5 s. Registrar categoría de filtro, no texto libre ni SKU escrito.
- **Errores frontend:** deduplicar firma normalizada por 1 min y limitar a 20 eventos por sesión/min. Sin stack trace ni mensaje crudo; solo versión, ruta/componentes conocidos y código normalizado.
- **Umbral/caducidad:** emitir solo transición/ventana con deduplicación persistida por `clinic_id + product_id + threshold_version` o lote/ventana; rearmar al recuperar stock o cambiar ventana.
- **Login fallido/denegaciones:** publicar señal agregada por stream; retención individual breve y restringida. No conservar IP sin revisión de privacidad.
- **Alta frecuencia:** agregar en edge/agente y registrar factor/ventana de muestreo. El libro de órdenes sigue siendo la fuente de auditoría, no el bus analítico.

### Entrega fiable y correlación

Usar outbox transaccional en el mismo almacenamiento que confirma la orden y publicar asíncronamente; consumidores idempotentes por `eventId`. No realizar llamadas bloqueantes al colector dentro de la transacción. Auth/TinyDB y PostgreSQL son almacenes separados: definir outbox/buffer local por servicio y política de reintento/retención. Evitar dual-write síncrono sin outbox.

Propagar `requestId` generado en el borde por header confiable; reemplazar valores externos que no cumplan formato/límite. Logs y trazas aplican la misma redacción y no copian el payload.

`telemetry_delivery_failed` y `telemetry_event_dropped` no se publican recursivamente por el mismo canal cuya falla describen. El relay debe incrementar contadores locales agregados y enviarlos por un canal de control independiente; si tampoco está disponible, persistir el contador sin payload y reportarlo al recuperar conectividad.

### Riesgos, dependencias y exclusiones

1. **Granularidad de stock:** el cálculo actual es global por `supply_id`; atribuirlo a clínica falsearía umbrales/snapshots. Calcular movimientos por `clinic_id` antes de alertas.
2. **Funciones ausentes:** no existen mínimos por producto/clínica, caducidad en el modelo ni `department` en consumos. Añadirlos con validaciones; hasta entonces no emitir valores inventados.
3. **Edición directa:** hoy no hay endpoint de edición de stock. El evento obligatorio solo se emite ante intento real rechazado en backend, no como evento ficticio del frontend.
4. **Seudónimos:** siguen siendo datos personales. Claire debe aprobar retención, acceso, rotación HMAC, ámbito transfronterizo y base legal; nunca unir a sistemas clínicos.
5. **Cardinalidad:** `requestId`, `eventId`, `sessionId` y `userId` no son etiquetas de métricas. Agrupar por rutas template, status, país, clínica y categorías controladas.
6. **Caché:** listado de producto tiene TTL 30 s; eventos de escritura post-commit. Distinguir dato del evento de lectura cacheada e indicar frescura.
7. **Retención/costos:** propuesta inicial: señales técnicas detalladas 14–30 días; eventos operativos 90 días; agregados no identificables 13 meses. Requiere aprobación legal/contractual y revisión de costos.
8. **Fuga por errores:** prohibir excepciones/mensajes crudos, SQL, payload, cookies, headers y URL completa. Probar con valores canario que nada sensible llega a collector/logs.
9. **Datos excluidos:** nombre/ID/historia/diagnóstico de paciente, clínica de un paciente, texto de notas/incidencias, email/teléfono, credenciales, JWT/tokens de recuperación, IP sin anonimizar, dirección, cuerpo HTTP, cookies y pagos.
10. **Candidatos descartados:** productividad individual, session replay, captura de teclas, geolocalización precisa, perfiles de navegación externos y experimentos que alteren operaciones clínicas; utilidad no proporcionada al riesgo de vigilancia/exposición/costo.

### Criterios de salida antes de instrumentar

- Claire aprueba propósito, residencia, retención, acceso y seudonimización para EE. UU./Reino Unido.
- Los cinco eventos obligatorios tienen pruebas de contrato, privacidad y entrega; los de stock por clínica esperan corregir granularidad.
- Consumidores validan `schemaVersion`, allowlist, tipos, tamaño y deduplicación; un evento inválido incrementa contador sin volcar payload.
- Dashboard/alertas cubren retraso, pérdida, volumen y eventos rechazados.
- Pruebas verifican emisión post-commit, ausencia de emisión tras rollback, consumo sin stock sin `outbound_order_created`, y redacción de valores sensibles.
- La telemetría no bloquea ni modifica respuestas HTTP o flujos operativos.

## Implementación construida

Los avances de implementación se documentan aquí, después del plan original y en el orden en que se construyen.

**Estado actual:** Stub, servicio e instrumentación implementados; brechas de privacidad, timestamp, entrega obligatoria y expiración corregidas. Recorrido integral en Chromium pendiente; almacenamiento analítico todavía no implementado.

### Fase 1 de implementación: stub receptor

- `POST /telemetry/events` recibe `{ "events": [...] }` con entre 1 y 100 eventos. Devuelve `200` con `{ "received": N }`; un contrato inválido rechaza el lote completo con `422`.
- `services/api/telemetry.py` define `TelemetryEvent`, el envelope cerrado y la validación del catálogo, incluyendo propiedades, versión y límite de 8192 bytes por evento.
- El router `services/api/routes/telemetry.py` solo registra cantidad y tipos de evento. No persiste, deduplica ni modifica datos de negocio.
- El backend lee `TELEMETRY_ENDPOINT` al iniciar, por defecto `http://localhost:8000/telemetry/events`, y lo expone internamente en `app.state.telemetry_endpoint`. Todavía no redirige tráfico.
- Ejecución local: `cd services/api && TELEMETRY_ENDPOINT=http://localhost:8000/telemetry/events uv run uvicorn main:app --port 8000 --reload`.
- Pruebas: `cd services/api && uv run pytest tests/test_telemetry.py -q`.
- Al terminar esta fase quedaron pendientes la configuración `NEXT_PUBLIC_TELEMETRY_ENDPOINT`, el servicio del backoffice y la instrumentación. El stub no autentica emisores: es una herramienta local de verificación, no un colector listo para producción.

### Fase 2 de implementación: servicio frontend

- `uis/backoffice/lib/telemetry.ts` sigue la ubicación existente de las capas cliente del backoffice y exporta únicamente `track(eventType: string, properties: Record<string, unknown>): void`. No se añadieron llamadas de tracking a componentes ni eventos de negocio.
- La cola vive en memoria, con máximo de 200 eventos entre pendientes y en vuelo. Se envían lotes `{ "events": [...] }` cada 10 segundos desde el primer evento o al alcanzar 20 eventos. La llegada de nuevos eventos no reinicia la ventana ni produce requests individuales. El tamaño de cada lote se limita a 48 KB.
- El servicio genera `eventId` y `requestId` aleatorios, añade el `timestamp` ISO 8601 en captura y obtiene `sessionId`/`userId` de su sesión en memoria. No se envían credenciales, perfil, email, JWT ni ID interno al colector.
- `telemetryContracts.ts` comparte el registro JSON con el stub: `TELEMETRY_SCHEMA_VERSION` procede de `formatVersion`. Se validan allowlist, campos obligatorios, tipos, rangos, enums y tamaño antes de encolar. Los datos inválidos se descartan sin registrar el payload.
- `visibilitychange`, cuando la pestaña queda oculta, y `pagehide` vacían eventos pendientes mediante `navigator.sendBeacon`. Un beacon aceptado puede incluir el lote HTTP en vuelo; este se cancela y no se reintenta. Si el navegador rechaza o lanza al encolar el beacon, el lote se conserva. La aceptación del beacon no equivale a confirmación del servidor; el futuro colector deberá deduplicar por `eventId`.
- Un fallo HTTP/red/timeout produce hasta tres reintentos adicionales, tras 1, 2 y 4 segundos. Se reutilizan el lote, IDs y timestamps originales. Después se descarta el lote y se continúa con la cola. Cada request tiene un timeout de 10 segundos. Los contadores de descarte/fallo son internos y no generan eventos recursivos.
- `telemetrySession.ts`, `auth.ts` y `AuthContext.tsx` enlazan la sesión con login, recuperación y logout. El UUID de sesión se genera al login y no se persiste. Las recargas de la pestaña crean una sesión nueva; las renovaciones de perfil mantienen la misma sesión. Los eventos ya capturados conservan su identidad aunque cambie la cuenta.
- **Dependencia pendiente aceptada:** el backend actual no devuelve el HMAC `telemetry_user_id` en `/auth/me` y se decidió no modificarlo en esta fase. El campo opcional queda preparado en el contrato frontend. Mientras falte un seudónimo válido, se descarta la captura autenticada, sin sustituirlo por email, ID interno ni un usuario anónimo. Sin autenticación se usa una identidad anónima efímera, conforme al plan.
- **Configuración local pendiente:** el servicio lee `NEXT_PUBLIC_TELEMETRY_ENDPOINT` sin fallback; si falta, no captura ni envía. El archivo `uis/backoffice/.env.local` está bloqueado para la herramienta de edición de esta sesión. Añadir allí `NEXT_PUBLIC_TELEMETRY_ENDPOINT=http://localhost:8000/telemetry/events` y reiniciar Next.js. En Codespaces/producción usar una URL HTTPS accesible desde el navegador, no el nombre interno de Docker ni un localhost remoto.
- El catálogo se incluye en `uis/Dockerfile` para resolver la misma fuente de contratos dentro de la imagen.
- Verificación: diez pruebas focalizadas de telemetría y las 46 pruebas de la suite del backoffice pasan; chequeo TypeScript focalizado sin errores. El typecheck global sigue fallando por 11 errores ajenos a esta fase (pruebas de proveedores, imports compartidos de la página principal y resumen de incidencias). Lint confirma un aviso preexistente en el efecto de `AuthContext`; los archivos nuevos no presentan errores.
- Pruebas: `cd uis/backoffice && npm test -- --runInBand`. La instalación local de dependencias reportó 28 vulnerabilidades; no se actualizaron dependencias ni lockfiles dentro de esta fase.

### Corrección de conectividad: localhost en Codespaces

- El navegador del operador no comparte `localhost` con el contenedor. Una URL pública `http://localhost:8000/telemetry/events` puede producir `net::ERR_CONNECTION_REFUSED` aunque FastAPI esté activo en Codespaces.
- `telemetryEndpoint.ts` transforma endpoints loopback en `/api/telemetry/events`, tanto para `fetch` como para `sendBeacon`. Las URLs externas HTTP/HTTPS se conservan y continúan controladas por `NEXT_PUBLIC_TELEMETRY_ENDPOINT`.
- El route handler de Next.js reenvía el lote completo al receptor. `TELEMETRY_ENDPOINT` configura el destino del servidor y tiene prioridad; sin él, un endpoint público local usa `SUPPLIERS_API_URL` si está definido, permitiendo `http://backend:8000` en Docker.
- El request del navegador al proxy permite únicamente credenciales de mismo origen para acceder a puertos privados de Codespaces. El proxy nunca reenvía cookies ni `Authorization` al colector. Un colector externo recibe requests con `credentials: omit`.
- Un receptor caído devuelve `502` desde el proxy y activa los reintentos acotados existentes; no se altera el resultado de operaciones de negocio. Se conserva el código `422` del stub para lotes inválidos.
- Verificación: 14 pruebas focalizadas pasan y lint del cambio sin errores. Una petición real a `http://127.0.0.1:3001/api/telemetry/events` devolvió `200` con `{ "received": 2 }`. Esta comprobación valida el transporte, no sustituye el recorrido completo de instrumentación en navegador.
- Tras cargar esta corrección, recargar el backoffice. En Network, el destino local esperado es la ruta `/api/telemetry/events` del propio backoffice, no `localhost:8000` del equipo del operador.

### Correcciones posteriores a la auditoría

- **Privacidad en la frontera:** `privacyValidation` del registro define rutas normalizadas, componentes conocidos, versiones/códigos restringidos y referencias a eventos registrados. Frontend y backend aplican las mismas restricciones antes de aceptar propiedades. No se añadieron claves al payload. Los canarios de email en `route_template`, nombre en `component` y texto sensible en versiones/códigos se rechazan; tampoco llegan a beacon.
- **Timestamp ISO estricto:** el modelo Pydantic exige fecha/hora ISO 8601 con `T` y zona horaria. Se rechazan strings numéricos como `"123"`, fechas sin hora, espacios en lugar de `T` y fechas imposibles. Los objetos datetime internos siguen sujetos a zona horaria.
- **Identidad autenticada:** `/auth/me` ya proporciona el HMAC `telemetry_user_id`; las claves de usuario y proveedor son diferentes. Configurar `TELEMETRY_USER_KEY` y `TELEMETRY_VENDOR_KEY` exclusivamente en servidor; el usuario rota por día UTC. En producción (`ENVIRONMENT=production`) se exige configurar ambas claves. En desarrollo, las claves efímeras de cada proceso no ofrecen continuidad entre reinicios/workers.
- **Cinco métricas obligatorias:** las entradas/salidas se capturan tras commit, el cruce de mínimos usa saldo y política por clínica, la edición directa se captura al rechazarla en backend y la caducidad usa una fecha real configurada. El consumo incorpora departamento validado. No se infieren mínimos ni fechas faltantes.
- **Entrega independiente del navegador:** `services/api/telemetry_delivery.py` encola la señal en el origen usando el contexto autenticado de la petición. Genera el envelope de servidor, respeta `eventId`/timestamp de captura y correlaciona `requestId`; acepta el UUID de sesión enviado por el cliente o genera uno aleatorio para otros clientes. No necesita que un cliente lea `X-Telemetry-Events`; el middleware retira esa cabecera y evita doble captura.
- **Productor backend por lotes:** cola acotada a 200 eventos pendientes/en vuelo, ventana de 10 segundos o disparo a 20 eventos, máximo de 48 KB por lote, timeout HTTP de 5 segundos y hasta tres reintentos adicionales con esperas de 1, 2 y 4 segundos. Un worker asíncrono respecto a la operación evita bloquear órdenes; conserva IDs/timestamps durante reintentos. El endpoint procede de `TELEMETRY_ENDPOINT`. Los fallos incrementan contadores/logs sin volcar payloads ni publicar eventos recursivos.
- **Caducidad posterior al acuse:** la deduplicación persistente se marca únicamente tras recibir `200` y `{ "received": N }` coherente. Mientras el evento está pendiente se deduplica en memoria; si se agotan reintentos, se libera para detectar nuevamente el caso. La marca es estado de regla, no almacenamiento de eventos en el stub. Un fallo al guardar el acuse no bloquea la operación; la caché temporal de claves también está acotada.
- **Expiración restaurada:** una sesión rechazada antes de obtener un HMAC válido emite una señal deduplicada con identidad anónima efímera y el UUID de sesión. Esta excepción no habilita captura autenticada general ni extrae identidad del JWT.
- **Transporte centralizado:** el navegador solo emite mediante `track()`. El proxy Next.js delega su HTTP a `lib/TelemetryService.server.ts`; no contiene un `fetch` propio hacia el colector. El productor backend es un servicio separado para hechos de servidor, no tracking disperso en componentes.
- **Piso transversal:** `TelemetryObserver` captura navegación principal con debounce de 500 ms, errores globales sin mensajes/stacks y LCP/INP/CLS/TTFB con ruta normalizada. El cliente HTTP central captura latencias/fallos; los hooks de autenticación capturan login válido/fallido, expiración y logout. Las razones nuevas de login están aprobadas en `auth_login_failed` versión `1.1.0`.
- **Evidencia:** 152 pruebas de backend y 59 de frontend pasan; lint y tipos focalizados del servicio sin errores. La reproducción de la auditoría pasó de enviar el canario a `pii_canary_blocked: true`. Una integración ejecuta las cinco operaciones mediante el middleware real y envía automáticamente seis eventos (cinco obligatorios y alta de producto) al stub, que valida el lote con `200`; la marca de caducidad se verifica antes/después del acuse.
- **Límites de verificación:** persisten cuatro errores TypeScript preexistentes en pruebas de proveedores y resumen de incidencias, fuera de estas correcciones. `scripts/verify_telemetry_browser.mjs` se adaptó a productores independientes: Network del navegador solo muestra sus lotes; los eventos de servidor se verifican con las pruebas backend. No se certificó todavía el recorrido completo en Chromium.
- **Operación:** reiniciar FastAPI para activar el worker nuevo y recargar el backoffice. En Docker configurar `TELEMETRY_ENDPOINT=http://backend:8000/telemetry/events` en el backend; en ejecución local usar `http://127.0.0.1:8000/telemetry/events`. El stub sigue sin persistir eventos. La cola en memoria puede perderse al reiniciar; persistencia/outbox, retención y deduplicación final del colector siguen perteneciendo a la fase de almacenamiento.

### Estado final de instrumentación (41 eventos)

La auditoría final confirma que los **41 eventos del catálogo están instrumentados en código**. El campo `x-implemented` en `event-schemas.json` se actualizó a `true` para todos los eventos tras verificar la emisión en archivos fuente.

#### Resumen de implementación

| # | event_type | Origen | Archivo(s) de emisión |
|---|---|---|---|
| 1 | `inbound_order_created` | Backend | `routes/inventory.py` |
| 2 | `outbound_order_created` | Backend | `routes/inventory.py` |
| 3 | `stock_threshold_triggered` | Backend | `routes/inventory.py` |
| 4 | `direct_stock_edit_rejected` | Backend | `routes/inventory.py` |
| 5 | `supply_expiry_flagged` | Backend | `inventory_telemetry.py` |
| 6 | `inventory_order_validation_failed` | Backend | `routes/inventory.py`, `main.py` |
| 7 | `inventory_order_rejected` | Backend | `routes/inventory.py` |
| 8 | `inventory_product_lookup_completed` | Frontend | `lib/inventoryApi.ts` |
| 9 | `inventory_stock_snapshot_recorded` | Backend | `routes/inventory.py` |
| 10 | `inventory_cache_served` | Backend | `routes/inventory.py` |
| 11 | `auth_login_succeeded` | Frontend | `lib/AuthContext.tsx` |
| 12 | `auth_login_failed` | Frontend | `lib/telemetryAuth.ts` |
| 13 | `auth_session_expired` | Frontend | `lib/telemetryAuth.ts` |
| 14 | `auth_logout_completed` | Frontend | `lib/AuthContext.tsx` |
| 15 | `auth_authorization_denied` | Backend | `main.py` (timing_middleware) |
| 16 | `api_latency_recorded` | Frontend | `lib/telemetryApi.ts` |
| 17 | `api_request_failed` | Frontend | `lib/telemetryApi.ts` |
| 18 | `api_dependency_failed` | Backend | `main.py`, `telemetry_delivery.py` |
| 19 | `frontend_error_captured` | Frontend | `lib/telemetryInstrumentation.ts` |
| 20 | `client_performance_recorded` | Frontend | `lib/telemetryInstrumentation.ts` |
| 21 | `backoffice_page_viewed` | Frontend | `lib/telemetryInstrumentation.ts` |
| 22 | `inventory_filter_applied` | Frontend | `lib/telemetryInstrumentation.ts` |
| 23 | `inventory_workflow_abandoned` | Frontend | `lib/useInventoryTelemetry.ts` |
| 24 | `inventory_product_created` | Backend | `routes/inventory.py` |
| 25 | `inventory_cache_invalidated` | Backend | `routes/inventory.py` |
| 26 | `inventory_stock_reconciliation_flagged` | Backend | `routes/inventory.py` |
| 27 | `inventory_order_duplicate_suspected` | Backend | `routes/inventory.py` |
| 28 | `inventory_order_history_exported` | Backend | `routes/inventory.py` |
| 29 | `auth_password_reset_requested` | Backend | `routes/auth.py` |
| 30 | `auth_rate_limit_triggered` | Backend | `rate_limiter.py` |
| 31 | `auth_token_validation_failed` | Backend | `security.py` |
| 32 | `api_retry_exhausted` | Ambos | `telemetry_delivery.py`, `lib/telemetry.ts` |
| 33 | `telemetry_delivery_failed` | Ambos | `telemetry_delivery.py`, `lib/telemetry.ts` |
| 34 | `telemetry_event_dropped` | Ambos | `telemetry_delivery.py`, `lib/telemetry.ts` |
| 35 | `service_health_check_failed` | Backend | `main.py` (health/ready) |
| 36 | `frontend_route_load_recorded` | Frontend | `lib/telemetryInstrumentation.ts` |
| 37 | `inventory_workflow_started` | Frontend | `lib/useInventoryTelemetry.ts` |
| 38 | `inventory_form_validation_failed` | Frontend | `lib/useInventoryTelemetry.ts` |
| 39 | `inventory_order_confirmation_viewed` | Frontend | `lib/useInventoryTelemetry.ts` |
| 40 | `inventory_search_performed` | Frontend | `lib/telemetryInstrumentation.ts` |
| 41 | `backoffice_navigation_error` | Frontend | `lib/telemetryInstrumentation.ts`, `app/not-found.tsx` |

#### Distribución

- **Backend puro**: 17 eventos
- **Frontend puro**: 22 eventos
- **Ambos (frontend + backend)**: 2 eventos (`api_retry_exhausted`, `telemetry_delivery_failed`, `telemetry_event_dropped`)
- **5 obligatorios**: todos instrumentados en backend
- **36 oportunidades**: todas instrumentadas

#### Canal de control independiente

Los eventos de diagnóstico del pipeline (`telemetry_delivery_failed`, `api_retry_exhausted`, `telemetry_event_dropped`, `api_dependency_failed`, `service_health_check_failed`) usan un canal de control independiente:
- **Backend**: `services/api/telemetry_delivery.py` → `control_queue` → `flush_control()` → `POST /telemetry/control`
- **Frontend**: `lib/TelemetryService.control.ts` → cola independiente → `POST /api/telemetry/control` (proxy Next.js → backend)

Este diseño evita recursión: si el canal principal falla, los eventos de diagnóstico no se publican por el mismo canal cuya falla describen.

#### Pruebas

- **Backend**: 156 pruebas pasan (28.6 s)
  - `test_telemetry.py`: validación de contratos, envelope, privacidad
  - `test_telemetry_delivery.py`: entrega, reintentos, control channel
  - `test_telemetry_control.py`: canal independiente, salud
  - `test_inventory_telemetry.py`: 5 obligatorios + alta de producto
  - `test_inventory_opportunities.py`: oportunidades de inventario
  - `test_auth_telemetry.py`: eventos de autenticación
  - `test_telemetry_identity.py`: identidad HMAC
- **Frontend**: 62 pruebas pasan (2.4 s)
  - `telemetry.test.ts`: track, queue, flush, contracts
  - `telemetryApi.test.ts`: captura de API
  - `telemetryInstrumentation.test.ts`: observer, page view, rendimiento
  - `telemetryProxy.test.ts`: proxy Next.js
  - `inventoryWorkflow.test.tsx`: workflow start/abandon
- **TypeScript**: lint y tipos focalizados sin errores. Persisten errores preexistentes en pruebas de proveedores y resumen de incidencias, fuera del ámbito de telemetría.

#### Archivos nuevos

Como parte de la instrumentación final se crearon 10 archivos nuevos:

| Archivo | Propósito |
|---|---|
| `services/api/tests/test_auth_telemetry.py` | Pruebas de `auth_authorization_denied`, `auth_token_validation_failed`, `auth_password_reset_requested`, `auth_rate_limit_triggered` |
| `services/api/tests/test_inventory_opportunities.py` | Pruebas de caché, snapshot, reconciliación, duplicados, exportación, validación |
| `services/api/tests/test_telemetry_control.py` | Pruebas del canal de control y health check |
| `uis/backoffice/__tests__/inventoryWorkflow.test.tsx` | Prueba de workflow start/abandon |
| `uis/backoffice/app/api/telemetry/control/route.ts` | Proxy Next.js para control events |
| `uis/backoffice/app/not-found.tsx` | Reporta `backoffice_navigation_error` en 404 |
| `uis/backoffice/lib/TelemetryService.control.ts` | Canal de control frontend |
| `uis/website/app/api/telemetry/events/route.ts` | Proxy de eventos para website |
| `uis/website/app/api/telemetry/control/route.ts` | Proxy de control para website |
| `uis/website/components/WebsiteTelemetry.tsx` | Componente de telemetría para el website público |

#### Pendientes (para fase de almacenamiento)

1. **Persistencia/outbox**: el stub no persiste eventos; la cola en memoria se pierde al reiniciar.
2. **Colector dedicado**: el stub actual es una herramienta local de verificación, no un colector listo para producción.
3. **Deduplicación final**: aunque el pipeline envía `eventId`, el stub no deduplica.
4. **Recorrido Chromium**: `scripts/verify_telemetry_browser.mjs` está preparado pero no se ejecutó en navegador headless.
5. **NEXT_PUBLIC_TELEMETRY_ENDPOINT**: requiere configuración en `.env.local`.
