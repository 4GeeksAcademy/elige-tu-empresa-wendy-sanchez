# Plan de Pruebas — API de Autenticación y Lógica de Negocio

## Contexto de empresa con test y autenticación

Este proyecto corresponde a la cadena de clínicas HealthCore. Los médicos, pacientes y administrativos usan esta app. Una parte muy importante es la **autenticación**: es el sistema que permite a los usuarios iniciar sesión, cambiar su contraseña, o recuperarla si la olvidan.

El problema es que un día, sin querer, alguien podría romper el sistema de login sin darse cuenta. Los usuarios no podrían entrar a la app y eso sería un desastre.

Para evitarlo, se hacen pruebas automáticas (**tests**): Para eso escribimos código que se encarga de comprobar que todo funciona como esperamos. Así, si alguien toca algo y lo rompe, los tests saltan avisando antes de que llegue a producción.

## Cómo ejecutar las pruebas

### Python / FastAPI (pytest)

```bash
# 1. Instalar dependencias de testing (solo la primera vez)
cd services/api
uv add --dev pytest pytest-cov httpx

# 2. Ejecutar todos los tests
uv run pytest -v --tb=short

# 3. Con cobertura
uv run pytest -v --tb=short --cov=services/api --cov-report=term

# 4. Solo un fichero de tests
uv run pytest tests/test_security.py -v --tb=short
```

### TypeScript (Jest)

```bash
# 1. Instalar dependencias de testing (solo la primera vez)
npm install --save-dev jest @types/jest ts-jest

# 2. Ejecutar tests (desde la raíz del proyecto)
npx jest --coverage

# 3. Solo un fichero de tests
npx jest src/__tests__/auth.test.ts
```

---

## Estructura de archivos de prueba

```
services/api/tests/
├── __init__.py
├── conftest.py              # Fixtures compartidas: client, db, seed user
├── test_auth_login.py       # POST /auth/login
├── test_auth_me.py          # GET /auth/me
├── test_auth_forgot_password.py   # POST /auth/forgot-password
├── test_auth_reset_password.py    # POST /auth/reset-password
├── test_auth_change_password.py   # POST /auth/change-password
├── test_security.py         # hash_password, verify_password, tokens
├── test_user_service.py     # user_service CRUD

src/__tests__/
├── collections.test.ts      # filterClaims, sortClaimsById, groupClaimsBy, etc.
├── search.test.ts           # findClaimById, findClinicianById, binarySearchClaimById
├── transformations.test.ts  # calculateDenialRate, denialRateByPayer, noShowRate, etc.
├── validations.test.ts      # validateClaim, validateClinician, thresholds
├── auth.test.ts             # getToken, setToken, removeToken, getAuthHeaders
├── authHttpClient.test.ts   # request, requestAuth, handle401
├── authProxy.test.ts        # proxyToAuthApi, forwardJsonBody, forwardAuthorizationHeader
```

---
## Tipos de pruebas

🟢 **Happy path (camino feliz)**: Es la situación ideal, donde todo funciona como debería.

Ejemplo: "Usuario escribe su email y contraseña correctos → el sistema le deja entrar y le da un token"

🟡 **Caso límite (edge case)**: Son situaciones en el borde, raras pero posibles. Ahí suelen aparecer bugs.

Ejemplo: "¿Qué pasa si el usuario escribe una contraseña vacía?" (solo pulsa Enter sin escribir nada)
Ejemplo: "¿Qué pasa si la contraseña nueva tiene menos de 8 letras?" (porque en el registro exigen mínimo 8)

🔴 **Modo de fallo (failure mode)**: Qué debería pasar cuando algo va mal.

Ejemplo: "Usuario pone una contraseña incorrecta → el sistema debe rechazarlo con error 401 (no autorizado)"
Ejemplo: "El token ha caducado → el sistema debe pedir que inicie sesión de nuevo"

## Cobertura planeada: Python / FastAPI

### POST /auth/login — Iniciar sesión

| Categoría | Caso | Entrada | Comportamiento esperado |
|-----------|------|---------|------------------------|
| ✅ Happy path | Credenciales correctas | email + password válidos | 200, Token con access_token no vacío y token_type="bearer" |
| ⚠️ Límite | Contraseña vacía (campo vacío) | email válido, password="" | 422 Validation Error |
| ⚠️ Límite | Email vacío | email="", password válida | 422 Validation Error |
| ❌ Fallo | Email no registrado | email inexistente | 401 "Email o contraseña incorrectos" |
| ❌ Fallo | Contraseña incorrecta | email correcto, password errónea | 401 "Email o contraseña incorrectos" |
| ❌ Fallo | Usuario inactivo | usuario con is_active=False | 401 "Email o contraseña incorrectos" |
| ⚠️ Límite | Password con caracteres Unicode/atípicos | email válido, password con acentos | 401 si el hash no coincide |
| ⚠️ Límite | Múltiples intentos fallidos | credenciales incorrectas repetidas | Siempre 401, sin bloqueo (rate limit no aplica a login) |

#### Explicación de lógica:

1. **Happy path:** Email correcto + contraseña correcta → te doy un token (como un pase VIP).

2. **Casos límite:**

- ¿Email vacío? → El sistema dirá "eso no es válido" (error 422, que es como "mandaste datos incorrectos")
- ¿Contraseña vacía? → Igual, error 422
- ¿Contraseña con caracteres raros como ñ, acentos? → El sistema la procesa, y si es la correcta, funciona; si no, da error 401

3. **Fallos:**

- Email que no existe en el sistema → 401 "Email o contraseña incorrectos" (no decimos cuál de los dos falló, por seguridad)
- Contraseña equivocada → mismo mensaje 401
- Usuario desactivado (por ejemplo, un administrativo que ya no trabaja aquí) → 401, no puede entrar

### GET /auth/me — Ver mi perfil

| Categoría | Caso | Entrada | Comportamiento esperado |
|-----------|------|---------|------------------------|
| ✅ Happy path | Token JWT válido | Bearer token válido | 200, devuelve MeResponse con email, role y profile |
| ❌ Fallo | Sin token | Sin Authorization header | 401 "Credenciales inválidas o ausentes" |
| ❌ Fallo | Token expirado | JWT con exp pasado | 401 |
| ❌ Fallo | Token malformado | cadena aleatoria | 401 |
| ❌ Fallo | Token sin "sub" | JWT firmado sin claim sub | 401 |
| ❌ Fallo | Token con sub no entero | sub="abc" | 401 |
| ❌ Fallo | Token de acceso de otro tipo | token de reset usado en /me | 401 (el token de reset tiene sub, pero get_current_user no verifica type — lo maneja validate_reset_token) |
| ❌ Fallo | Usuario del token no existe en BD | token de usuario borrado | 401 |
| ❌ Fallo | Usuario del token está inactivo | token de usuario con is_active=False | 401 |
| ✅ Happy path | Usuario autenticado con perfil | token + perfil creado | profile no es null en la respuesta |
| ✅ Happy path | Usuario autenticado sin perfil | token sin perfil asociado | profile es null en la respuesta |

#### Explicación de lógica:

1. **Happy path:** Doy un token válido → el sistema me dice quién soy (email, rol, perfil).

2. **Fallos:**

- No doy token → 401
- Token inventado "abc123" → 401
- Token que ya expiró → 401
- Token de un usuario que borraron de la base de datos → 401
- Token de un usuario desactivado → 401

### POST /auth/forgot-password — Olvidé mi contraseña

| Categoría | Caso | Entrada | Comportamiento esperado |
|-----------|------|---------|------------------------|
| ✅ Happy path | Email registrado y activo | email existente | 200, "Si esa dirección está registrada...", token persistido, email "enviado" |
| ✅ Happy path | Email no registrado | email inexistente | 200, mismo mensaje (protección enumeración) |
| ✅ Happy path | Usuario inactivo | email de usuario inactivo | 200, mismo mensaje (no filtra información) |
| ⚠️ Límite | Email vacío | email="" | 422 Validation Error |
| ❌ Fallo | Rate limit excedido | mismo email 6+ veces en ventana | 200, mismo mensaje, pero audit_log registra rate_limit_exceeded |
| ⚠️ Límite | Formato email inválido | "no-es-un-email" | 422 Validation Error |

#### Explicación de lógica:

1. **Happy paths:**

- Email existe y está activo → 200, "Te enviaremos un enlace" (aunque en tests no se envía de verdad)
- Email no existe → 200, mismo mensaje. Esto es a propósito para que un atacante no pueda averiguar qué emails están registrados
- Usuario inactivo → 200, mismo mensaje. Por la misma razón

2. **Fallos:**

- Llamar muchas veces (más de 5 en una hora) → rate limit: el sistema deja de hacer caso, pero sigue diciendo "te enviaremos un enlace" para no dar pistas
- Email con formato inválido como "patata" → 422

### POST /auth/reset-password — Restablecer contraseña

| Categoría | Caso | Entrada | Comportamiento esperado |
|-----------|------|---------|------------------------|
| ✅ Happy path | Token válido + new_password válida | token de reset + password >= 8 chars | 200, "Contraseña restablecida correctamente", token invalidado |
| ❌ Fallo | Token inválido (no JWT) | cadena aleatoria | 400 "El enlace de restablecimiento no es válido o ha expirado" |
| ❌ Fallo | Token expirado | JWT con exp pasado | 400 |
| ❌ Fallo | Token de acceso JWT usado como reset | token de login (sin type="password_reset") | 400 |
| ❌ Fallo | Token reutilizado (ya invalidado) | token previamente usado | 400 |
| ❌ Fallo | Token con type incorrecto | type="other" | 400 |
| ❌ Fallo | Token sin sub | JWT firmado sin sub | 400 |
| ❌ Fallo | Usuario del token no existe | token para user_id inexistente | 400 |
| ❌ Fallo | Usuario del token inactivo | token para usuario inactivo | 400 |
| ⚠️ Límite | new_password demasiado corta | < 8 caracteres | 422 Validation Error |
| ⚠️ Límite | new_password demasiado larga | > 128 caracteres | 422 Validation Error |
| ⚠️ Límite | new_password vacía | "" | 422 Validation Error |
| ⚠️ Límite | Token vacío | token="" | 422 (Validation Error del modelo — token es str pero sin min_length explícito → FastAPI serializa como string vacío que jose rechaza → 400) |

#### Explicación de lógica:

1. **Happy path:** Token válido + contraseña nueva válida → se cambia la contraseña y el token se invalida (no se puede reusar).

2. **Fallos:**

- Token inventado → 400
- Token expirado → 400
- El mismo token usado dos veces → 400 (el token se invalida al primer uso)
- Token que es de acceso (de login) usado como token de reset → 400
- Token con formato correcto pero sin el campo "type" correcto → 400
- Usuario del token no existe o está inactivo → 400

3. **Casos límite:** Contraseña nueva demasiado corta (< 8), demasiado larga (> 128), vacía → 422

### POST /auth/change-password — Cambiar contraseña estando dentro

| Categoría | Caso | Entrada | Comportamiento esperado |
|-----------|------|---------|------------------------|
| ✅ Happy path | Contraseña actual correcta + new_password válida | payload + token válido | 200, "Contraseña actualizada correctamente" |
| ❌ Fallo | Contraseña actual incorrecta | current_password errónea | 400 "La contraseña actual no es correcta" |
| ❌ Fallo | Sin autenticación | Sin token | 401 |
| ❌ Fallo | Token expirado/inválido | Bearer inválido | 401 |
| ⚠️ Límite | new_password = current_password | ambas iguales | 200 (no hay validación que lo impida; se acepta) |
| ⚠️ Límite | new_password demasiado corta | < 8 caracteres | 422 Validation Error |
| ⚠️ Límite | current_password vacía | "" | 422 ó 400 (depende si Pydantic lo rechaza o llega a la lógica) |
| ⚠️ Límite | new_password vacía | "" | 422 Validation Error |

#### Explicación de lógica:

1. **Happy path:** Contraseña actual correcta + contraseña nueva válida → se actualiza.

2. **Fallos:**

- Contraseña actual incorrecta → 400 "La contraseña actual no es correcta"
- No estoy autenticado (sin token) → 401
- Token inválido → 401

3. **Caso límite interesante:** ¿Y si pongo la misma contraseña que ya tenía? → El sistema lo acepta (no hay código que lo prohíba expresamente). ¿Es correcto? Puede debatirse.

### security.py (unidad)

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | hash_password genera hash válido | bcrypt hash que verify_password acepta |
| ✅ Happy path | verify_password true para hash correcto | True |
| ❌ Fallo | verify_password false para contraseña diferente | False |
| ✅ Happy path | create_access_token genera JWT decodificable | payload.sub == subject, payload.exp futuro |
| ✅ Happy path | create_access_token con subject string | str(user_id) se codifica correctamente |
| ❌ Fallo | JWT_SECRET_KEY no configurada | RuntimeError |
| ✅ Happy path | create_reset_token incluye type="password_reset" | payload.type == "password_reset" |
| ✅ Happy path | validate_reset_token devuelve user_id | Número entero |
| ❌ Fallo | validate_reset_token con token de acceso | 400 por type incorrecto |
| ❌ Fallo | validate_reset_token con token expirado | 400 |
| ❌ Fallo | validate_reset_token con token ya invalidado | 400 |
| ✅ Happy path | invalidate_reset_token elimina el token de BD | Token ya no existe en reset_tokens |
| ⚠️ Límite | invalidate_reset_token con token inexistente | No falla (remove en TinyDB es seguro) |
| ✅ Happy path | ACCESS_TOKEN_EXPIRE_MINUTES=0 → creación rápida | Token expira inmediatamente |

### user_service.py (unidad)

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | create_user crea usuario con todos los campos | User con id asignado, role=USER, is_active=True, created_at set |
| ✅ Happy path | get_user_by_id devuelve usuario existente | User correcto |
| ❌ Fallo | get_user_by_id con ID inexistente | None |
| ✅ Happy path | get_user_by_email encuentra por email | Case insensitive |
| ❌ Fallo | get_user_by_email con email no registrado | None |
| ✅ Happy path | update_user actualiza campos | Devuelve User con cambios |
| ❌ Fallo | update_user con user_id inexistente | None |
| ✅ Happy path | delete_user elimina usuario y su perfil | True, BD limpia |
| ❌ Fallo | delete_user con ID inexistente | False |
| ✅ Happy path | create_profile crea perfil asociado | Profile con user_id correcto |
| ✅ Happy path | get_profile_by_user_id devuelve perfil | Profile o None |
| ⚠️ Límite | Actualizar perfil inexistente | None (update_profile_by_user_id devuelve None) |

---

## Cobertura planeada: TypeScript (src/utils/)

### collections.ts

| Categoría | Caso | Entrada | Comportamiento esperado |
|-----------|------|---------|------------------------|
| ✅ Happy path | filterClaims con múltiples filtros | claims + locationId + status | Claims filtrados |
| ⚠️ Límite | filterClaims con array vacío | [] | [] |
| ⚠️ Límite | filterClaims sin filtros (todos undefined) | claims + {} | Mismos claims |
| ✅ Happy path | filterAppointmentsByStatus | appointments + estados | Filtro correcto |
| ⚠️ Límite | filterAppointmentsByStatus array vacío | [] | [] |
| ✅ Happy path | sortClaimsById ascendente | claims desordenados | Orden CLM asc |
| ✅ Happy path | sortClaimsById descendente | claims desordenados | Orden CLM desc |
| ✅ Happy path | sortAppointmentsByDate asc | appointments desordenadas | Orden fecha asc |
| ✅ Happy path | groupClaimsBy con key válida | claims + "status" | Grupos correctos |
| ⚠️ Límite | groupClaimsBy con array vacío | [] + key | {} |

### search.ts

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | findClaimById encuentra existente | Claim |
| ❌ Fallo | findClaimById ID inexistente | null |
| ⚠️ Límite | findClaimById array vacío | null |
| ✅ Happy path | findClinicianById encuentra existente | Clinician |
| ❌ Fallo | findClinicianById ID inexistente | null |
| ✅ Happy path | binarySearchClaimById encuentra en medio | Índice correcto |
| ❌ Fallo | binarySearchClaimById no encontrado | -1 |
| ⚠️ Límite | binarySearchClaimById array vacío | -1 |

### transformations.ts

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | countByCategory cuenta correctamente | Record<string, number> |
| ⚠️ Límite | countByCategory array vacío | {} |
| ✅ Happy path | sumBy suma valores | Número |
| ⚠️ Límite | sumBy array vacío | 0 |
| ✅ Happy path | averageBy calcula media | Número redondeado a 2 decimales |
| ❌ Fallo | averageBy array vacío | null |
| ✅ Happy path | maxBy / minBy | Elemento extremo |
| ❌ Fallo | maxBy / minBy array vacío | null |
| ✅ Happy path | calculateDenialRate | Porcentaje |
| ❌ Fallo | calculateDenialRate array vacío | Error |
| ✅ Happy path | denialRateByPayer | Record por pagador |
| ✅ Happy path | denialRateByLocation | Record por ubicación |
| ✅ Happy path | flagHighDenialPayers threshold personalizado | Lista de pagadores |
| ✅ Happy path | calculateNoShowCost | Coste total |
| ❌ Fallo | calculateNoShowCost fecha inválida | Error |
| ✅ Happy path | noShowRateByLocation | Record por ubicación |
| ✅ Happy path | flagHighNoShowLocations | Lista de ubicaciones |

### validations.ts

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | validateClaim con claim válido | { valid: true, errors: [] } |
| ❌ Fallo | claimId malformado | Error |
| ❌ Fallo | patientId malformado | Error |
| ❌ Fallo | locationId no reconocida | Error |
| ❌ Fallo | claimAmount <= 0 | Error |
| ❌ Fallo | submissionDate futura | Error |
| ❌ Fallo | status denied sin denialReason | Error |
| ✅ Happy path | validateClinician válido | { valid: true, errors: [] } |
| ❌ Fallo | clinicianId malformado | Error |
| ❌ Fallo | role inválido | Error |
| ❌ Fallo | cmeHours negativo | Error |
| ❌ Fallo | licenceExpiryDate inválida | Error |
| ❌ Fallo | cmeYearStartDate inválida | Error |
| ✅ Happy path | isDenialRateAboveThreshold | true si rate > threshold |
| ⚠️ Límite | isDenialRateAboveThreshold justo en threshold | false (el umbral es estrictamente mayor) |
| ✅ Happy path | isNoShowRateAboveThreshold | true si rate > threshold |

### auth.ts (backoffice lib)

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | getToken con token en localStorage | string del token |
| ❌ Fallo | getToken sin token | null |
| ✅ Happy path | setToken almacena token | localStorage tiene el valor |
| ✅ Happy path | removeToken elimina token | localStorage vacío |
| ✅ Happy path | getAuthHeaders con token | { Authorization: "Bearer <token>" } |
| ⚠️ Límite | getAuthHeaders sin token | {} |

### authHttpClient.ts (backoffice lib)

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | request con 200 devuelve datos | T tipado |
| ⚠️ Límite | request con 204 | undefined |
| ❌ Fallo | request con 401 | Error + redirección a /login |
| ❌ Fallo | request con 422 + errores de validación | Error con mensaje parseado |
| ❌ Fallo | request con 500 | Error con mensaje estándar |

### authProxy.ts (backoffice lib)

| Categoría | Caso | Comportamiento esperado |
|-----------|------|------------------------|
| ✅ Happy path | proxyToAuthApi 200 con JSON | Response con body JSON |
| ❌ Fallo | proxyToAuthApi backend caído | 502 con mensaje |
| ❌ Fallo | proxyToAuthApi 204 | Response 204 sin body |
| ✅ Happy path | forwardJsonBody extrae body | RequestInit con body json y content-type |
| ✅ Happy path | forwardAuthorizationHeader | RequestInit con Authorization |
| ✅ Happy path | forwardAuthorizedJsonBody combina ambos | RequestInit completo |

---

## Principios de diseño de las pruebas

1. **No probar serialización HTTP**: No verificamos que FastAPI serializa correctamente
   un modelo Pydantic. Eso es responsabilidad del framework. Probamos que la
   **lógica de negocio** produce el resultado correcto.

2. **Aislar el estado**: Los tests de Python usan TinyDB en memoria (no el archivo
   real) mediante el patrón de reemplazar `get_db()` con una instancia limpia.
   Los tests de TypeScript usan datos mock, nunca dependen del DOM. → Los tests de Python usan una base de datos en memoria, no la real. Así no se contaminan entre sí y pueden ejecutarse muchas veces dando el mismo resultado.

3. **Cada endpoint tiene mínimo 3 tests**: happy path, caso límite, modo de fallo. → Es el mínimo para tener confianza.

4. **No dependencias externas**: Los tests de `email_service.py` y `rate_limiter.py`
   usan mocks para evitar llamadas reales a Resend o depender del reloj del sistema
   (se congela con `freezegun` en Python y `jest.useFakeTimers()` en TS). → Cuando probamos "olvidé mi contraseña", no enviamos un email de verdad. Simulamos (mock) esa parte.

5. **Determinismo**: Los tokens JWT se generan con secretos fijos en tests para
   poder predecir su estructura y expiración. → Congelamos el tiempo cuando sea necesario para que un token "que expira en 30 minutos" sepa exactamente cuándo expira, sin depender de la hora del ordenador.

---

## Configuración necesaria para tests

Para que los tests funcionen es necesario instalar las dependencias exactas que
se indican a continuación.

### Python / FastAPI

```bash
# Desde services/api/
cd services/api

# Las dependencias de test se añaden al grupo dev del pyproject.toml
uv add --dev pytest pytest-cov httpx

# Después, ejecutar tests con:
uv run pytest -v --tb=short
uv run pytest -v --tb=short --cov=services/api --cov-report=term
```

No es necesario crear un `pytest.ini` separado: `pytest` descubrirá los tests en
`services/api/tests/` automáticamente. Si se desea configurar opciones por defecto,
crear `services/api/pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
```

### TypeScript

```bash
# Desde la raíz del proyecto
npm install --save-dev jest @types/jest ts-jest

# Luego ejecutar tests con:
npx jest --coverage
```

Crear `jest.config.js` en la raíz con:

```js
/** @type {import('jest').Config} */
module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  roots: ["<rootDir>/src"],
  collectCoverageFrom: ["src/**/*.ts"],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
};
```