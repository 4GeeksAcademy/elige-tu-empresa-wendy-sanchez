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

### C02 — Token JWT almacenado en localStorage sin protección XSS

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/auth.ts` |
| **Líneas** | 52–56 |
| **Categoría** | 5 — FILTRACIÓN DE DATOS SENSIBLES |
| **Problema** | El JWT se almacena en `localStorage` sin `httpOnly` ni `Secure`. Cualquier script inyectado (XSS) puede robarlo. Esto permite suplantación de sesión completa. |
| **Corrección** | Migrar a cookies `httpOnly` + `Secure` + `SameSite=Strict` para tokens de acceso. O usar un patrón BFF (Next.js API route que maneje el token en servidor). |

### C03 — Sin `raise` después de `except` en `get_current_user` — token inválido tratado erróneamente

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/security.py` |
| **Líneas** | 67–70 |
| **Categoría** | 5 — FILTRACIÓN DE DATOS SENSIBLES |
| **Problema** | Al capturar `(JWTError, ValueError)` se lanza `raise unauthorized from None`, perdiendo la traza original. Aunque es intencional para evitar exponer detalles del token, el `from None` oculta información que podría ser útil para debugging. No es crítico por sí solo, pero en conjunto con el log de auditoría (que es limitado) impide rastrear ataques JWT. |
| **Corrección** | Hacer logging interno del error original antes del `raise unauthorized from None` para que los ataques queden registrados sin exponerse al cliente. |

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

### H02 — CATCH DEMASIADO AMPLIO en `main.py` de HealthCore API

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/main.py` |
| **Líneas** | 57–65 |
| **Categoría** | 2 — CATCH DEMASIADO AMPLIO |
| **Problema** | `analyze_incidents` y `analyze_sample_incidents` usan bloques `try/except ValueError` que envuelven toda la operación de análisis. Si ocurre cualquier otro tipo de error (KeyError, TypeError, etc.), la excepción se propaga sin control dando un `500 Internal Server Error` con stack trace al cliente. |
| **Corrección** | Acotar los try/except a las operaciones concretas que pueden lanzar ValueError (análisis CSV, parseo). Añadir un exception handler global en FastAPI para los errores no esperados. |

### H03 — FALLOS SILENCIOSOS en `AuthContext.tsx` — error de fetch del perfil silenciado

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/AuthContext.tsx` |
| **Líneas** | 47–49, 76–78 |
| **Categoría** | 3 — FALLOS SILENCIOSOS |
| **Problema** | Los bloques `catch` en `fetchUser()` y `login()` ponen `setUser(null)` pero no reportan el error al usuario ni lo registran. Si la API falla por razones de red (y el token es válido), el usuario se queda sin sesión aunque el token sea válido. |
| **Corrección** | Loggear el error usando `console.error` en desarrollo. En producción, si hay token pero falla el fetch, mantener al usuario como potencialmente autenticado e intentar de nuevo más tarde. |

### H04 — EXPOSICIÓN DE ERRORES EN CRUDO en `fetchFromApi` de `IncidentsManagerClient.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentsManagerClient.tsx` |
| **Líneas** | 118–120 |
| **Categoría** | 4 — EXPOSICIÓN DE ERRORES EN CRUDO |
| **Problema** | `fetchFromApi` hace `res.text()` y lo concatena directamente en el error: ``throw new Error(`API error ${res.status}: ${body}`)``. Si la API devuelve un stack trace HTML (por defecto FastAPI en dev), el mensaje de error viaja completo hasta el usuario. |
| **Corrección** | Limitar la longitud del body en el mensaje de error. Preferir `res.json()` con un fallback genérico. Sanitizar el contenido. |

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

### M02 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI en `IncidentsManagerClient.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentsManagerClient.tsx` |
| **Líneas** | 215–269 |
| **Categoría** | 6 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI |
| **Problema** | Los handlers `handleCreate`, `handleUpdate`, `handleDelete` usan `setFeedback()` para mostrar el error/success pero no hay casos de renderizado condicional para cuando `isSaving` es `true` durante la operación. El botón no se deshabilita durante la llamada `handleDelete` (falta `isSaving` o `isDeleting`). |
| **Corrección** | Deshabilitar el botón de submit/borrar mientras la operación asíncrona está en curso. Usar un estado `isDeleting` independiente. |

### M03 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO en `IncidentsAnalyzerClient.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentsAnalyzerClient.tsx` |
| **Líneas** | 89–93 |
| **Categoría** | 7 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO |
| **Problema** | Cuando el análisis falla (error de API, sample no disponible), el componente muestra el error en un recuadro rojo pero no ofrece un botón de reintentar. El usuario tiene que recargar la página manualmente. |
| **Corrección** | Añadir un botón "Reintentar" junto al mensaje de error que reinvoque la operación fallida. |

### M04 — SIN sys.exit EN FALLO DE SCRIPT en `seed_incidents.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `scripts/seed_incidents.py` |
| **Líneas** | 1 – final del script |
| **Categoría** | 8 — SIN sys.exit EN FALLO DE SCRIPT |
| **Problema** | El script `seed_incidents.py` no llama a `raise SystemExit` ni `sys.exit()` al final — solo tiene `def main(argv) -> int`. En `if __name__ == "__main__":` no hay nada que use el código de retorno. En caso de error crítico (CSV no encontrado), retorna 1 pero el script termina sin propagar el código de salida. |
| **Corrección** | Añadir `raise SystemExit(main(sys.argv))` en `if __name__ == "__main__":` (similar a `analyze.py`). |

### M05 — SIN sys.exit EN FALLO DE SCRIPT en `analyze.py` (menor — ya implementado pero inconsistente)

| Campo | Valor |
|-------|-------|
| **Archivo** | `scripts/analyze.py` |
| **Líneas** | 87 — `raise SystemExit(main(sys.argv))` |
| **Categoría** | 8 — SIN sys.exit EN FALLO DE SCRIPT |
| **Problema** | `analyze.py` implementa bien `SystemExit`, pero `seed_incidents.py` NO. Hay inconsistencia entre scripts del mismo directorio. Además, la lógica de `export_answer` dentro de `main` no está dentro de try/except — si `input()` lanza EOFError (entrada no interactiva), la función retorna 0 con éxito en lugar de fallar. |
| **Corrección** | Estandarizar todos los scripts con `raise SystemExit(main(sys.argv))`. Manejar EOFError en el input interactivo. |

### M06 — ESTADO DE CARGA AUSENTE en `SuppliersDirectoryClient.tsx` — filtros sin feedback

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/SuppliersDirectoryClient.tsx` |
| **Líneas** | 113–120 |
| **Categoría** | 6 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI |
| **Problema** | `loadSuppliers` tiene estado `isLoading` pero no hay renderizado condicional que muestre un spinner mientras se cargan los filtros. La tabla desaparece y no hay indicación visual de que está cargando. |
| **Corrección** | Renderizar un spinner de carga (o skeleton) cuando `isLoading` es `true`. |

### M07 — CATCH DEMASIADO AMPLIO en `authProxy.ts` y `suppliersProxy.ts`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/authProxy.ts` (líneas 12–16) y `uis/backoffice/lib/suppliersProxy.ts` (líneas 24–28) |
| **Categoría** | 2 — CATCH DEMASIADO AMPLIO |
| **Problema** | El `catch` sin tipo captura toda la llamada `fetch` y devuelve un mensaje genérico. Sin embargo, un error de red no discriminado (DNS failure, timeout, conexión rechazada) se trata igual que un error de protocolo. No hay diferenciación entre errores transitorios (retryables) y fatales. |
| **Corrección** | Clasificar errores: errores de conexión (TypeError, TypeError) vs errores HTTP. Considerar reintentar errores de red transitorios. |

---

## 🔵 BAJOS

### B01 — Exposición de ruta interna en `suppliersProxy.ts` y `authProxy.ts`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/authProxy.ts` (línea 3), `uis/backoffice/lib/suppliersProxy.ts` (línea 15) |
| **Categoría** | 5 — FILTRACIÓN DE DATOS SENSIBLES (bajo) |
| **Problema** | El mensaje de error del proxy dice textualmente: "¿Está levantada en el puerto 8000?" exponiendo información sobre el puerto de escucha del backend. |
| **Corrección** | Usar un mensaje genérico como "No se pudo contactar con la API. Inténtalo de nuevo más tarde." |

### B02 — FALLO SILENCIOSO en `rate_limiter.py` — fallo de TinyDB silenciado

| Campo | Valor |
|-------|-------|
| **Archivo** | `services/api/rate_limiter.py` |
| **Líneas** | 36–39 |
| **Categoría** | 3 — FALLOS SILENCIOSOS |
| **Problema** | La iteración `for doc in table:` y las operaciones `table.remove(doc_ids=...)` no están en try/except. Si la base de datos falla (disco lleno, permisos), el rate limiter fallará silenciosamente permitiendo abusos en el endpoint de reset de contraseña. |
| **Corrección** | Capturar excepciones de TinyDB. Si falla, permitir la operación (fail-open) pero loggear el error. |

### B03 — Estado de error en `forgot-password/page.tsx` sin acción de usuario

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/app/forgot-password/page.tsx` |
| **Líneas** | 57–61 |
| **Categoría** | 7 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO |
| **Problema** | Si el servidor devuelve error en el forgot-password, se muestra el error en un recuadro rojo, pero el usuario no tiene opción de reintentar directamente (tiene que editar el campo email de nuevo). |
| **Corrección** | Añadir un botón "Reintentar" que re-envíe la solicitud con los mismos datos. |

### B04 — Catch vacío funcional en `AuthContext.tsx`

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/lib/AuthContext.tsx` |
| **Líneas** | 47–49 |
| **Categoría** | 3 — FALLOS SILENCIOSOS |
| **Problema** | El `catch` bloque que hace `setUser(null)` no registra el error en consola. Si hay un error de red, no hay traza en los logs del navegador para debugging. |
| **Corrección** | Añadir `console.error("Auth fetch error:", error)` antes de `setUser(null)`. |

### B05 — SIN RETRY en `IncidentListPanel.tsx` — error de fetch sin reintentar

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/components/IncidentListPanel.tsx` |
| **Líneas** | 108–121 |
| **Categoría** | 7 — SIN LLAMADA A LA ACCIÓN PARA EL USUARIO |
| **Problema** | `fetchIncidents()` captura el error y muestra `fetchError`, pero no hay botón de reintentar en el componente para que el usuario recupere sin recargar. |
| **Corrección** | Añadir un botón "Reintentar" en el mensaje de error que llame a `fetchIncidents()`. |

### B06 — Estado de carga ausente en `LoginPage` (parcial)

| Campo | Valor |
|-------|-------|
| **Archivo** | `uis/backoffice/app/login/page.tsx` |
| **Líneas** | 99–103 |
| **Categoría** | 6 — ESTADOS DE CARGA/ERROR AUSENTES EN LA UI |
| **Problema** | El botón de submit se deshabilita durante el envío (correcto), pero si el estado es `submitting` la UI solo cambia el texto a "Iniciando sesión...". No hay skeleton loading ni indicación visual más allá del texto del botón. |
| **Corrección** | Añadir un spinner inline junto al texto del botón. |

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

## 🔥 OBSERVACIONES ADICIONALES

1. **Patrón general positivo:** El repositorio ya tiene varios buenos patrones — `extractErrorMessage` en `authHttpClient.ts`, handlers globales de excepción en `incidents-api/main.py`, y el uso de `audit_logger` para eventos de seguridad.

2. **Asimetría entre servicios:** La `incidents-api` tiene un handler global de excepciones (`global_exception_handler`) pero la `api` principal (HealthCore API) **no tiene ninguno**, por lo que cualquier excepción no capturada devuelve un error 500 con stack trace completo de FastAPI al cliente.

3. **Mejora recomendada prioritaria:** Implementar un exception handler global en `services/api/main.py` similar al de `services/incidents-api/main.py` para evitar que errores no esperados filtren stack traces.

4. **Falta de logging estructurado:** No hay uso de `logging` con niveles consistentes en el backend. `email_service.py` usa `logger` pero `security.py`, `user_service.py`, y las rutas no registran eventos de error interno. Esto dificulta la auditoría forense.