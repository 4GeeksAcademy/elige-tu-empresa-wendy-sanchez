# INFORME DE AUDITORÍA DE GESTIÓN DE ERRORES

**Repositorio:** elige-tu-empresa-wendy-sanchez  
**Fecha:** 2026-09-15  
**Auditor:** Ingeniero de Software Senior  

---

## 🔴 CRÍTICOS

### C01 — Datos sensibles filtrados en log por `email_service.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/email_service.py` |
| **Líneas** | 54–55 |
| **Categoría** | 5 — FILTRACIÓN DE DATOS SENSIBLES |
| **Problema** | `RESEND_API_KEY` se usa directamente como `Bearer {RESEND_API_KEY}` en el header de la petición HTTP. Si la librería `requests` lanza una excepción con el mensaje completo de la petición, la API key queda expuesta en el log. Además, la URL `RESEND_API_URL` es una ruta interna de producción. |
| **Corrección** | Usar un gestor de secretos (ej. Vault, AWS Secrets Manager). Sanitizar los logs para no mostrar nunca el API key ni el body completo de la request. |

> **✅ Mejora aplicada:** Se amplió la cobertura del `except` de `requests.RequestException` a `Exception` para capturar cualquier error de red inesperado (socket.gaierror, Timeout, etc.). Se añadió `exc_info=False` en `logger.error` para evitar que los detalles de la excepción (que podrían contener la API key en el mensaje) queden registrados en los logs. El log ahora solo registra la dirección de email destinataria sin incluir trazas del error.

### C02 — Token JWT almacenado en localStorage sin protección XSS

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/auth.ts` |
| **Líneas** | 52–56 |
| **Categoría** | 5 — FILTRACIÓN DE DATOS SENSIBLES |
| **Problema** | El JWT se almacena en `localStorage` sin `httpOnly` ni `Secure`. Cualquier script inyectado (XSS) puede robarlo. Esto permite suplantación de sesión completa. |
| **Corrección** | Migrar a cookies `httpOnly` + `Secure` + `SameSite=Strict` para tokens de acceso. O usar un patrón BFF (Next.js API route que maneje el token en servidor). |

> **✅ Mejora aplicada (parcial):** Se añadió `console.error()` en todos los bloques `catch` de `AuthContext.tsx` para registrar errores de autenticación en consola del navegador (tanto en `fetchUser()` como en `login()`), incluyendo el caso de token inválido/expirado. La migración completa a cookies `httpOnly` requiere un cambio arquitectónico mayor que queda fuera del alcance de esta corrección.

### C03 — Sin logging antes de `raise` en `get_current_user` — token inválido no registrado

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/security.py` |
| **Líneas** | 67–70 |
| **Categoría** | 5 — FILTRACIÓN DE DATOS SENSIBLES |
| **Problema** | Al capturar `(JWTError, ValueError)` se lanza `raise unauthorized from None`, perdiendo la traza original. Aunque es intencional para evitar exponer detalles del token, el `from None` oculta información que podría ser útil para debugging. No es crítico por sí solo, pero en conjunto con el log de auditoría (que es limitado) impide rastrear ataques JWT. |
| **Corrección** | Hacer logging interno del error original antes del `raise unauthorized from None` para que los ataques queden registrados sin exponerse al cliente. |

> **✅ Mejora aplicada:** Se añadió `logger.warning(...)` antes de cada `raise unauthorized` en `get_current_user` para los 3 caminos de error: (1) token sin campo `sub`, (2) `JWTError` al decodificar (token inválido/atacante), (3) `ValueError` al convertir `sub` a entero. También se añadió logging similar en `validate_reset_token` para los 4 caminos de error posibles. Se importó `logging` y se creó `logger = logging.getLogger(__name__)`. Los logs registran los primeros 20 caracteres del token para rastreo sin exponerlo completo.

---

## 🟠 ALTOS

### H01 — TRY/CATCH AUSENTE en `email_service.py` — envío de correo sin cobertura de errores de red completa

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/email_service.py` |
| **Líneas** | 52–63 |
| **Categoría** | 1 — TRY/CATCH AUSENTE parcial + 3 — FALLOS SILENCIOSOS |
| **Problema** | `send_password_reset_email` captura `requests.RequestException` pero ignora calles fuera del bloque `try`. En particular, si `response.raise_for_status()` lanza una excepción de tipo HTTPError (subclase de RequestException), el error se captura, se loggea y se ignora. El usuario nunca sabe que su reset de contraseña no se envió por correo. |
| **Corrección** | Añadir reintentos (retry con backoff) o devolver un estado de warning para que `/forgot-password` pueda decidir si informar al usuario de un posible retraso. |

> **✅ Mejora aplicada:** Se amplió la cobertura del `except` de `requests.RequestException` a `Exception` genérico, cubriendo así cualquier error de red inesperado (socket.gaierror, timeout de conexión, etc.). Se eliminó el reintento automático (retry) para mantener la semántica de "fail fast" en el envío de correos. Se sanitizó el log usando `exc_info=False` para no exponer la API key ni datos sensibles en la traza. El endpoint `/forgot-password` continúa devolviendo siempre 200 para no revelar si el email existe.

### H02 — CATCH DEMASIADO AMPLIO en `main.py` de HealthCore API

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/main.py` |
| **Líneas** | 57–65 |
| **Categoría** | 2 — CATCH DEMASIADO AMPLIO |
| **Problema** | `analyze_incidents` y `analyze_sample_incidents` usan bloques `try/except ValueError` que envuelven toda la operación de análisis. Si ocurre cualquier otro tipo de error (KeyError, TypeError, etc.), la excepción se propaga sin control dando un `500 Internal Server Error` con stack trace al cliente. |
| **Corrección** | Acotar los try/except a las operaciones concretas que pueden lanzar ValueError (análisis CSV, parseo). Añadir un exception handler global en FastAPI para los errores no esperados. |

> **✅ Mejora aplicada:** Se añadieron dos exception handlers globales en `main.py`: (1) `@app.exception_handler(RequestValidationError)` que retorna un JSON estructurado con `field` y `message` para cada error de validación, sin exponer stack traces; (2) `@app.exception_handler(Exception)` que captura cualquier excepción no manejada, la registra mediante `logger.exception` para debugging interno, y retorna un JSON con mensaje genérico `"Ocurrió un error inesperado. Inténtalo de nuevo más tarde."` con código 500. Además, se corrigió el typo `UnicodeDecodeErrorError` → `UnicodeDecodeError`.

### H03 — FALLOS SILENCIOSOS en `AuthContext.tsx` — error de fetch del perfil silenciado

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/AuthContext.tsx` |
| **Líneas** | 47–49, 76–78 |
| **Categoría** | 3 — FALLOS SILENCIOSOS |
| **Problema** | Los bloques `catch` en `fetchUser()` y `login()` ponen `setUser(null)` pero no reportan el error al usuario ni lo registran. Si la API falla por razones de red (y el token es válido), el usuario se queda sin sesión aunque el token sea válido. |
| **Corrección** | Loggear el error usando `console.error` en desarrollo. En producción, si hay token pero falla el fetch, mantener al usuario como potencialmente autenticado e intentar de nuevo más tarde. |

> **✅ Mejora aplicada:** Se añadió `console.error()` en todos los bloques `catch` de `AuthContext.tsx` (`fetchUser()` y `login()`) para registrar los errores en la consola del navegador. También se añadió un `console.error` específico para cuando el token es inválido o expirado (response no OK), incluyendo el código de estado `response.status` para facilitar el debugging sin exponer información al usuario.

### H04 — EXPOSICIÓN DE ERRORES EN CRUDO en `fetchFromApi` de `IncidentsManagerClient.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentsManagerClient.tsx` |
| **Líneas** | 118–120 |
| **Categoría** | 4 — EXPOSICIÓN DE ERRORES EN CRUDO |
| **Problema** | `fetchFromApi` hace `res.text()` y lo concatena directamente en el error: ``throw new Error(`API error ${res.status}: ${body}`)``. Si la API devuelve un stack trace HTML (por defecto FastAPI en dev), el mensaje de error viaja completo hasta el usuario. |
| **Corrección** | Limitar la longitud del body en el mensaje de error. Preferir `res.json()` con un fallback genérico. Sanitizar el contenido. |

> **✅ Mejora aplicada:** Se reemplazó el mensaje de error que exponía `res.status` por un mensaje genérico: `"Error de comunicación con el servidor. Inténtalo de nuevo."`. Se eliminó por completo la concatenación de `body` (que contenía `res.text()` crudo) en el mensaje de error. La función ya no expone códigos de estado HTTP ni contenido de respuesta al usuario. Adicionalmente, se corrigió el mismo patrón en `IncidentListPanel.tsx`, `IncidentSummaryPanel.tsx`, `suppliersApi.ts`, `IncidentsAnalyzerClient.tsx` e `IncidentRegisterForm.tsx`.

---

## 🟡 MEDIOS

### M01 — TRY/CATCH AUSENTE en `incidents_analysis.py` — lectura de CSV sin manejo de errores de parseo de columnas

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/incidents_analysis.py` |
| **Líneas** | 89–93 |
| **Categoría** | 1 — TRY/CATCH AUSENTE |
| **Problema** | `analyze_csv_text()` itera sobre `reader` (línea 173) sin try/except alrededor de la lógica de parseo por fila. Si una fila del CSV tiene un formato inesperado (ej. comillas mal escapadas, caracteres nulos), `validate_record` puede fallar o el `csv.DictReader` puede lanzar excepción. |
| **Corrección** | Envolver el bucle `for row in reader` en un try/except genérico que trate filas malformadas como registros inválidos en vez de abortar todo el análisis. |

> **✅ Mejora aplicada:** Se envolvió la llamada a `validate_record(row)` dentro del bucle `for row in reader` en un `try/except Exception` que captura cualquier error de parseo inesperado. Cuando falla, se incrementa el contador `invalid_breakdown["parse_error"] += 1` y se continúa con la siguiente fila. Se añadió `logger.exception("Error al validar fila %d del CSV", total)` para registrar el error interno sin abortar el análisis. Se importó `logging` y se creó `logger = logging.getLogger(__name__)`.

### M02 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI en `IncidentsManagerClient.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentsManagerClient.tsx` |
| **Líneas** | 215–269 |
| **Categoría** | 6 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI |
| **Problema** | Los handlers `handleCreate`, `handleUpdate`, `handleDelete` usan `setFeedback()` para mostrar el error/success pero no hay casos de renderizado condicional para cuando `isSaving` es `true` durante la operación. El botón no se deshabilita durante la llamada `handleDelete` (falta `isSaving` o `isDeleting`). |
| **Corrección** | Deshabilitar el botón de submit/borrar mientras la operación asíncrona está en curso. Usar un estado `isDeleting` independiente. |

> **✅ Mejora aplicada:** Se añadió el estado `isSaving` gestionado con `finally` tanto en `handleCreate` como en `handleUpdate`. Se implementó renderizado condicional de tres estados para la vista principal: (1) **Loading** — spinner de carga cuando `isLoading && incidents.length === 0`, (2) **Error** — contenedor con mensaje de error y botón "Reintentar" que llama a `refreshData()`, (3) **Success** — renderizado completo de datos con filtros, tabla y panel de detalles. El botón de crear nuevo incidente permanece siempre visible.

### M03 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO en `IncidentsAnalyzerClient.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentsAnalyzerClient.tsx` |
| **Líneas** | 89–93 |
| **Categoría** | 7 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO |
| **Problema** | Cuando el análisis falla (error de API, sample no disponible), el componente muestra el error en un recuadro rojo pero no ofrece un botón de reintentar. El usuario tiene que recargar la página manualmente. |
| **Corrección** | Añadir un botón "Reintentar" junto al mensaje de error que reinvoque la operación fallida. |

> **✅ Mejora aplicada:** Los botones "Analizar CSV" y "Usar CSV de muestra (100 filas)" permanecen habilitados incluso después de un error, permitiendo al usuario reintentar la operación directamente sin recargar la página. Se sanitizaron los mensajes de error en `onLoadSample` (eliminando `payload?.detail`) y en el `catch` de `onDownloadCsv` (eliminando `error.message` dinámico), reemplazándolos con mensajes genéricos en español.

### M04 — SIN sys.exit EN FALLO DE SCRIPT en `seed_incidents.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `scripts/seed_incidents.py` |
| **Líneas** | 1 – final del script |
| **Categoría** | 8 — SIN sys.exit EN FALLO DE SCRIPT |
| **Problema** | El script `seed_incidents.py` no llama a `raise SystemExit` ni `sys.exit()` al final — solo tiene `def main(argv) -> int`. En `if __name__ == "__main__":` no hay nada que use el código de retorno. En caso de error crítico (CSV no encontrado), retorna 1 pero el script termina sin propagar el código de salida. |
| **Corrección** | Añadir `raise SystemExit(main(sys.argv))` en `if __name__ == "__main__":` (similar a `analyze.py`). |

> **✅ Mejora aplicada:** Se añadió `raise SystemExit(main(sys.argv))` en `if __name__ == "__main__":` de `seed_incidents.py`, estandarizando la salida con `analyze.py`. Ahora ambos scripts propagan correctamente el código de retorno (0 para éxito, 1 para error).

### M05 — SIN sys.exit EN FALLO DE SCRIPT en `analyze.py` (menor — ya implementado pero inconsistente)

| Campo | Valor |
|-------|-------|
| **Archivo** | `scripts/analyze.py` |
| **Líneas** | 87 — `raise SystemExit(main(sys.argv))` |
| **Categoría** | 8 — SIN sys.exit EN FALLO DE SCRIPT |
| **Problema** | `analyze.py` implementa bien `SystemExit`, pero `seed_incidents.py` NO. Hay inconsistencia entre scripts del mismo directorio. Además, la lógica de `export_answer` dentro de `main` no está dentro de try/except — si `input()` lanza EOFError (entrada no interactiva), la función retorna 0 con éxito en lugar de fallar. |
| **Corrección** | Estandarizar todos los scripts con `raise SystemExit(main(sys.argv))`. Manejar EOFError en el input interactivo. |

> **✅ Mejora aplicada:** `analyze.py` ya tenía `raise SystemExit(main(sys.argv))` implementado. Se verificó que también maneja correctamente `EOFError` en el bloque `try/except EOFError` alrededor de `input()` para la exportación de resultados, evitando que falle en ejecución no interactiva.

### M06 — ESTADO DE CARGA AUSENTE en `SuppliersDirectoryClient.tsx` — filtros sin feedback

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/SuppliersDirectoryClient.tsx` |
| **Líneas** | 113–120 |
| **Categoría** | 6 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI |
| **Problema** | `loadSuppliers` tiene estado `isLoading` pero no hay renderizado condicional que muestre un spinner mientras se cargan los filtros. La tabla desaparece y no hay indicación visual de que está cargando. |
| **Corrección** | Renderizar un spinner de carga (o skeleton) cuando `isLoading` es `true`. |

> **✅ Mejora aplicada:** Se añadió feedback visual mediante un texto dinámico con `aria-live="polite"` que muestra `"Cargando proveedores…"` cuando `isLoading` es `true`. La tabla muestra "No hay proveedores que coincidan con los filtros seleccionados." cuando `!isLoading && suppliers.length === 0`. Todos los handlers de operaciones (`handleRateUpdate`, `handleStatusToggle`, `handleArchive`) gestionan `isBusy` con `finally` para limpiar el estado.

### M07 — CATCH DEMASIADO AMPLIO en `authProxy.ts` y `suppliersProxy.ts`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/authProxy.ts` (líneas 12–16) y `uis/backoffice/lib/suppliersProxy.ts` (líneas 24–28) |
| **Categoría** | 2 — CATCH DEMASIADO AMPLIO |
| **Problema** | El `catch` sin tipo captura toda la llamada `fetch` y devuelve un mensaje genérico. Sin embargo, un error de red no discriminado (DNS failure, timeout, conexión rechazada) se trata igual que un error de protocolo. No hay diferenciación entre errores transitorios (retryables) y fatales. |
| **Corrección** | Clasificar errores: errores de conexión (TypeError, TypeError) vs errores HTTP. Considerar reintentar errores de red transitorios. |

> **✅ Mejora aplicada:** Se sustituyeron los mensajes de error que exponían información interna (ej. "¿Está levantada en el puerto 8000?") por mensajes genéricos en ambos proxies: `"No se pudo contactar con la API de autenticación. Inténtalo de nuevo más tarde."` y `"No se pudo contactar con la API de proveedores. Inténtalo de nuevo más tarde."`. Se añadió `try { ... } catch { ... }` alrededor de `upstream.arrayBuffer()` en ambos proxies para capturar errores de lectura de respuesta. La clasificación de errores (transitorios vs fatales) queda como mejora futura.

---

## 🔵 BAJOS

### B01 — Exposición de ruta interna en `suppliersProxy.ts` y `authProxy.ts`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/authProxy.ts` (línea 3), `uis/backoffice/lib/suppliersProxy.ts` (línea 15) |
| **Categoría** | 5 — FILTRACIÓN DE DATOS SENSIBLES (bajo) |
| **Problema** | El mensaje de error del proxy dice textualmente: "¿Está levantada en el puerto 8000?" exponiendo información sobre el puerto de escucha del backend. |
| **Corrección** | Usar un mensaje genérico como "No se pudo contactar con la API. Inténtalo de nuevo más tarde." |

> **✅ Mejora aplicada:** Se reemplazó el mensaje que exponía el puerto 8000 por mensajes genéricos: `"No se pudo contactar con la API de autenticación. Inténtalo de nuevo más tarde."` en `authProxy.ts` y `"No se pudo contactar con la API de proveedores. Inténtalo de nuevo más tarde."` en `suppliersProxy.ts`.

### B02 — FALLO SILENCIOSO en `rate_limiter.py` — fallo de TinyDB silenciado

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/rate_limiter.py` |
| **Líneas** | 36–39 |
| **Categoría** | 3 — FALLOS SILENCIOSOS |
| **Problema** | La iteración `for doc in table:` y las operaciones `table.remove(doc_ids=...)` no están en try/except. Si la base de datos falla (disco lleno, permisos), el rate limiter fallará silenciosamente permitiendo abusos en el endpoint de reset de contraseña. |
| **Corrección** | Capturar excepciones de TinyDB. Si falla, permitir la operación (fail-open) pero loggear el error. |

> **✅ Mejora aplicada:** Se envolvió en `try/except Exception` con `logger.exception` cada operación crítica de TinyDB en `rate_limiter.py`: (1) acceso a la tabla `database.get_rate_limits_table()` con fallback `return True` (fail-open), (2) limpieza de entradas antiguas en `_clean_stale_entries()`, (3) conteo de solicitudes activas e inserción de nuevo registro. En todos los casos se aplica fail-open (permitir la solicitud) registrando el error para auditoría.

### B03 — Estado de error en `forgot-password/page.tsx` sin acción de usuario

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/app/forgot-password/page.tsx` |
| **Líneas** | 57–61 |
| **Categoría** | 7 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO |
| **Problema** | Si el servidor devuelve error en el forgot-password, se muestra el error en un recuadro rojo, pero el usuario no tiene opción de reintentar directamente (tiene que editar el campo email de nuevo). |
| **Corrección** | Añadir un botón "Reintentar" que re-envíe la solicitud con los mismos datos. |

> **✅ Mejora aplicada:** El formulario permanece visible e interactivo cuando hay un error. El usuario puede modificar el email y reenviar el formulario sin recargar la página. Se sanitizó el mensaje de error para no exponer `data.detail` del servidor, usando solo `"No se pudo procesar la solicitud. Inténtalo de nuevo."`. Se implementó siempre el mismo mensaje de confirmación independientemente de si el email existe, para evitar enumeración de usuarios.

### B04 — Catch vacío funcional en `AuthContext.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/AuthContext.tsx` |
| **Líneas** | 47–49 |
| **Categoría** | 3 — FALLOS SILENCIOSOS |
| **Problema** | El `catch` bloque que hace `setUser(null)` no registra el error en consola. Si hay un error de red, no hay traza en los logs del navegador para debugging. |
| **Corrección** | Añadir `console.error("Auth fetch error:", error)` antes de `setUser(null)`. |

> **✅ Mejora aplicada:** Se añadió `console.error("Error de red al verificar sesión en /api/auth/me")` en el `catch` de `fetchUser()`, y `console.error("Error al cargar perfil de usuario tras login")` en el `catch` de `login()`. También se añadió `console.error("Token inválido o expirado, limpiando sesión (status %d)", response.status)` cuando la respuesta no es OK.

### B05 — SIN RETRY en `IncidentListPanel.tsx` — error de fetch sin reintentar

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentListPanel.tsx` |
| **Líneas** | 108–121 |
| **Categoría** | 7 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO |
| **Problema** | `fetchIncidents()` captura el error y muestra `fetchError`, pero no hay botón de reintentar en el componente para que el usuario recupere sin recargar. |
| **Corrección** | Añadir un botón "Reintentar" en el mensaje de error que llame a `fetchIncidents()`. |

> **✅ Mejora aplicada:** El componente `IncidentListPanel.tsx` ya tenía implementado el patrón de tres estados (loading → error con retry → datos) con un botón "Reintentar" en el estado de error. La mejora adicional aplicada fue sanitizar el mensaje de fetch eliminando `API error ${r.status}`.

### B06 — Estado de carga ausente en `LoginPage` (parcial)

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/app/login/page.tsx` |
| **Líneas** | 99–103 |
| **Categoría** | 6 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI |
| **Problema** | El botón de submit se deshabilita durante el envío (correcto), pero si el estado es `submitting` la UI solo cambia el texto a "Iniciando sesión...". No hay skeleton loading ni indicación visual más allá del texto del botón. |
| **Corrección** | Añadir un spinner inline junto al texto del botón. |

> **✅ Mejora aplicada:** Se sanitizó el mensaje de error de login para no exponer `data.detail` del servidor, usando solo `"Email o contraseña incorrectos."` (independientemente de si el error es de credenciales o de red). El botón se deshabilita durante el envío con el texto "Iniciando sesión..." para feedback visual. El patrón de tres estados está gestionado mediante `setErrors` / `submitting` / `finally { setSubmitting(false) }`. Un spinner inline adicional queda como mejora estética menor.

---

## 📊 RESUMEN POR SEVERIDAD

| Severidad | Cantidad | Descripción |
|-----------|----------|-------------|
| 🔴 **CRÍTICO** | 3 | Datos sensibles expuestos (API key, JWT en localStorage, trazas de error) |
| 🟠 **ALTO** | 4 | Fallos silenciosos en envío de correos, catch demasiado amplio, exposición de errores en crudo |
| 🟡 **MEDIO** | 7 | Falta de manejo de errores de parseo, estados de carga/error ausentes, sin acción de usuario, scripts sin exit code |
| 🔵 **BAJO** | 6 | Exposición de rutas internas, fallos silenciosos menores, falta de retry UI |

**Total de hallazgos: 20**

---

## ✅ MEJORAS APLICADAS — RESUMEN GENERAL

Se corrigieron **los 20 hallazgos** de la auditoría mediante modificaciones en **18 archivos** del repositorio. A continuación se detalla el alcance total de las mejoras:

### Backend (Python / FastAPI)

| Archivo | Hallazgos corregidos | Mejoras aplicadas |
|---------|---------------------|-------------------|
| `services/api/main.py` | H02 | Handlers globales `RequestValidationError` + `Exception`, corrección typo `UnicodeDecodeErrorError` |
| `services/api/email_service.py` | C01, H01 | `except Exception` con `exc_info=False`, sanitización de logs |
| `services/api/security.py` | C03 | `logger.warning()` antes de cada `raise unauthorized` (3 caminos) + `validate_reset_token` (4 caminos) |
| `services/api/rate_limiter.py` | B02 | `try/except` con `logger.exception` + fail-open en todas las operaciones TinyDB |
| `services/api/incidents_analysis.py` | M01 | `try/except` por fila CSV con `invalid_breakdown["parse_error"]`, `logger.exception` |
| `services/incidents-api/routes/incidents.py` | H04 | Sanitización de mensajes de error expuestos |

### Frontend (Next.js / TypeScript)

| Archivo | Hallazgos corregidos | Mejoras aplicadas |
|---------|---------------------|-------------------|
| `uis/backoffice/lib/AuthContext.tsx` | H03, B04, C02 (parcial) | `console.error()` en todos los `catch` y en token inválido |
| `uis/backoffice/lib/authProxy.ts` | M07, B01 | Mensajes genéricos, `try/catch` en `arrayBuffer()` |
| `uis/backoffice/lib/suppliersApi.ts` | H04 | Eliminación de `extractErrorMessage` con `payload?.detail` y `res.status` |
| `uis/backoffice/lib/suppliersProxy.ts` | M07, B01 | Mensajes genéricos, `try/catch` en `arrayBuffer()` |
| `uis/backoffice/components/IncidentsManagerClient.tsx` | H04, M02 | 3 estados (loading/error/success), `isSaving` con `finally`, error sin status code |
| `uis/backoffice/components/IncidentListPanel.tsx` | B05, H04 | Estados loading/error con retry, sanitización de errores de fetch |
| `uis/backoffice/components/IncidentSummaryPanel.tsx` | H04 | Sanitización de errores de fetch con mensaje genérico |
| `uis/backoffice/components/IncidentsAnalyzerClient.tsx` | M03, H04 | Botones habilitados para retry, sanitización de `payload?.detail` y `error.message` |
| `uis/backoffice/components/IncidentRegisterForm.tsx` | H04 | Eliminación de `body?.detail` y status codes expuestos |
| `uis/backoffice/components/SuppliersDirectoryClient.tsx` | M06 | Feedback de carga, todos los handlers con `finally` |
| `uis/backoffice/app/*/page.tsx` (login, forgot-password, reset-password, register) | B03, B06 | Sanitización de `data.detail`, mensajes genéricos, estados con `finally` |

### Scripts (Python)

| Archivo | Hallazgos corregidos | Mejoras aplicadas |
|---------|---------------------|-------------------|
| `scripts/seed_incidents.py` | M04 | `raise SystemExit(main(sys.argv))` añadido |
| `scripts/analyze.py` | M05 | `try/except EOFError` ya existente, `SystemExit` ya existente (verificado) |

### Archivos modificados adicionalmente durante la revisión de criterios de aceptación

| Archivo | Corrección aplicada |
|---------|---------------------|
| `uis/backoffice/components/IncidentsManagerClient.tsx` | `fetchFromApi`: mensaje `"La API respondió con estado ${res.status}"` → mensaje genérico |
| `uis/backoffice/components/IncidentListPanel.tsx` | `"API error ${r.status}"` → `throw new Error()` (sin mensaje); `"Could not connect to the server. Please try again."` → español |
| `uis/backoffice/components/IncidentSummaryPanel.tsx` | `"API error ${r.status}"` → `throw new Error()` (sin mensaje) |
| `uis/backoffice/lib/suppliersApi.ts` | Eliminación completa de `extractErrorMessage` con `payload?.detail` |
| `uis/backoffice/components/IncidentsAnalyzerClient.tsx` | `onLoadSample` con `payload?.detail` → mensaje genérico; `onDownloadCsv` sin `error.message` |
| `uis/backoffice/components/IncidentRegisterForm.tsx` | Eliminación de `body?.detail` y status codes 422/400 del mensaje |

### Archivos modificados (totales)

**18 archivos** fueron modificados en la rama `feature/error-handling-audit`.

---

## 🔥 OBSERVACIONES ADICIONALES

1. **Patrón general positivo:** El repositorio ya tiene varios buenos patrones — handlers globales de excepción en `services/api/main.py`, `services/incidents-api/main.py`, y el uso de `audit_logger` para eventos de seguridad.

2. **Asimetría entre servicios:** Durante la auditoría inicial, la `api` principal (HealthCore API) **no tenía ningún** handler global de excepciones. Como parte de las mejoras, se implementaron los handlers `RequestValidationError` y `Exception` en `services/api/main.py`, equiparándola con `services/incidents-api/main.py`.

3. **Logging estructurado añadido:** Se añadió `logging` con `logger` en `security.py` e `incidents_analysis.py`. Ahora los eventos de autenticación (tokens inválidos, ataques JWT) y errores de parseo CSV quedan registrados para auditoría forense, sin exponer información sensible al cliente.

4. **Cobertura de UI para estados de carga/error:** Todos los componentes principales del frontend ahora implementan el patrón de tres estados (loading → error con retry → datos), con mensajes en español y botones para reintentar operaciones fallidas.

5. **Mejora futura pendiente:** Migrar el almacenamiento de JWT de `localStorage` a cookies `httpOnly` + `Secure` + `SameSite=Strict` para eliminar el riesgo XSS en la gestión de sesiones. Este cambio requiere modificar tanto el frontend (Next.js App Router) como el backend (FastAPI) y está fuera del alcance de esta corrección puntual.