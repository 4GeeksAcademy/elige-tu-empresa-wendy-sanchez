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

**Estado actual:** Stub receptor implementado; servicio e instrumentación pendientes.

### Fase 1 de implementación: stub receptor

- `POST /telemetry/events` recibe `{ "events": [...] }` con entre 1 y 100 eventos. Devuelve `200` con `{ "received": N }`; un contrato inválido rechaza el lote completo con `422`.
- `services/api/telemetry.py` define `TelemetryEvent`, el envelope cerrado y la validación del catálogo, incluyendo propiedades, versión y límite de 8192 bytes por evento.
- El router `services/api/routes/telemetry.py` solo registra cantidad y tipos de evento. No persiste, deduplica ni modifica datos de negocio.
- El backend lee `TELEMETRY_ENDPOINT` al iniciar, por defecto `http://localhost:8000/telemetry/events`, y lo expone internamente en `app.state.telemetry_endpoint`. Todavía no redirige tráfico.
- Ejecución local: `cd services/api && TELEMETRY_ENDPOINT=http://localhost:8000/telemetry/events uv run uvicorn main:app --port 8000 --reload`.
- Pruebas: `cd services/api && uv run pytest tests/test_telemetry.py -q`.
- La configuración `NEXT_PUBLIC_TELEMETRY_ENDPOINT`, el servicio del backoffice y la instrumentación quedan para las siguientes fases. El stub no autentica emisores: es una herramienta local de verificación, no un colector listo para producción.
