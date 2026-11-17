# HealthCore MCP Server

> **MCP Server** que expone el **Incidents Manager** y el **módulo de inventario** como herramientas MCP (Model Context Protocol), protegidas con **OAuth 2.1** vía **MCP Auth (mcpauth)** en modo **Resource Server**. No usa la capa OAuth integrada de FastMCP.

---

## Arquitectura

```
┌───────────────────────┐     OAuth 2.1 (Bearer JWT)        ┌──────────────────────────────────┐
│  MCP Clients          │ ──── scopes: incidents.*  ────▶  │  SelectiveBearerASGI             │
│  (Agente LangGraph)   │      inventory.read               │  ┌─ .well-known/ → público       │
│  (curl, Playground)   │                                   │  └─ /mcp → BearerAuthMiddleware  │
└───────────────────────┘                                   │       │                          │
                                                            │  ┌────▼─────────────────────┐    │
                                                            │  │  FastMCP (stateless_http)│    │
                                                            │  │  Streamable HTTP         │    │
                                                            │  │                          │    │
                                                            │  │  ┌─────────────────┐     │    │
                                                            │  │  │ get_incident    │     │    │
                                                            │  │  │ list_incidents  │─────┼────┼──▶ Incidents API :8010
                                                            │  │  │ create_incident │     │    │
                                                            │  │  │ update_status   │     │    │
                                                            │  │  │ get_summary     │     │    │
                                                            │  │  ├─────────────────┤     │    │
                                                            │  │  │ get_product     │─────┼────┼──▶ Inventory API :8000
                                                            │  │  │ list_products   │     │    │      (JWT Bearer)
                                                            │  │  └─────────────────┘     │    │
                                                            │  └──────────────────────────┘    │
                                                            └──────────────────────────────────┘
```

### Decisiones técnicas

| Decisión | Opción | Motivo |
|----------|--------|--------|
| **OAuth** | MCP Auth (mcpauth) modo Resource Server | Alineado con especificación MCP Auth; desacoplado de FastMCP; soporta cualquier proveedor OIDC; publica RFC 9728; scopes por tool |
| **Transporte** | Streamable HTTP (`stateless_http=True`) | Un solo endpoint HTTP; múltiples clientes simultáneos; sin estado de sesión en servidor |
| **Framework** | FastMCP v1 (`mcp>=1.24,<2`) | SDK oficial MCP; integración directa con `@mcp.tool()` |
| **Auth middleware** | mcpauth `bearer_auth_middleware()` | Implementación de referencia MCP Auth; valida JWT, issuer, scopes |
| **Público vs protegido** | `SelectiveBearerASGI` (wrapper ASGI) | Las rutas `/.well-known/` quedan fuera del bearer middleware; el lifespan del FastMCP se preserva al no anidar Starlettes |
| **Token dev** | `MCP_DEV_TOKEN` | Token fijo para desarrollo cuando no hay IDP; verificado por `_verify_dev_token()` |
| **Scopes** | Mínimo privilegio: `incidents.read`, `incidents.write`, `inventory.read`, `inventory.write` | Cada tool exige el scope mínimo necesario |
| **Adaptador LangGraph** | `langchain-mcp-adapters` | Convierte tools MCP a BaseTool de LangChain en `mcp_client.py`; integración nativa con LangGraph |
| **Rechazo escritura inventario** | Tools `create_product`, `update_product`, `delete_product` existen y devuelven error controlado | RETO 2 del ticket: "no basta con no implementar, el servidor debe rechazar explícitamente" |
| **DNS Rebinding / Tunnel** | `transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)` en FastMCP | FastMCP auto-activa protección anti-DNS rebinding para localhost, lo que rechaza Host headers de túneles (localtunnel). Se deshabilita explícitamente para permitir proxies reversos legítimos. |

---

## Setup

### Dependencias

```bash
uv add "mcp>=1.24.0,<2" "mcpauth>=0.1.0" "fastmcp>=1.0.0"
```

> **Nota**: `langchain-mcp-adapters` se usa en `services/agent/tools/mcp_client.py` para convertir las tools del MCP Server en objetos `BaseTool` de LangChain vía `load_mcp_tools()`, integrando el agente LangGraph de forma nativa con el ecosistema LangChain.

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Host de escucha |
| `MCP_PORT` | `9100` | Puerto |
| `MCP_TRANSPORT` | `streamable-http` | Transporte MCP |
| `MCP_PUBLIC_URL` | — | URL pública (ej. `https://<codespace>-9100.app.github.dev`) |
| `MCP_ISSUER` | `MCP_PUBLIC_URL` o `http://localhost:9100` | Issuer esperado en JWT |
| `MCP_JWKS_URI` | — | URI del JWKS endpoint del AS (para validación asimétrica en producción) |
| `MCP_SKIP_AUTH` | — | `1` para deshabilitar toda la capa OAuth (solo desarrollo local) |
| `MCP_DEV_TOKEN` | `hc_dev_token_no_usar_en_produccion` | Token fijo para desarrollo (usa `_verify_dev_token()`) |
| `MCP_REQUIRED_SCOPES` | `["incidents.read"]` | Scopes globales requeridos. Se calcula automáticamente: cuando `MCP_SKIP_AUTH=1` → vacío (sin scope mínimo); sin `MCP_SKIP_AUTH` → aplica el scope base para que un token sin ningún scope sea rechazado. **Bug corregido**: inicialmente la lógica estaba invertida (`if os.getenv("MCP_SKIP_AUTH")` en lugar de `if not`), lo que dejaba los scopes vacíos en modo producción y el middleware aceptaba cualquier request sin token. |
| `INCIDENTS_API_URL` | `http://incidents-backend:8010` | URL del Incidents Manager |
| `INVENTORY_API_URL` | `http://backend:8000` | URL del módulo de inventario |
| `AGENT_JWT_TOKEN` | — | JWT backend-a-backend que usa el MCP Server internamente para consultar inventario |

### Arranque local (sin auth)

```bash
MCP_SKIP_AUTH=1 uv run uvicorn mcps.server:app --host 0.0.0.0 --port 9100
```

### Arranque local (con auth — token fijo de desarrollo)

```bash
MCP_ISSUER="https://oidc.example.com" \
MCP_PUBLIC_URL="http://localhost:9100" \
uv run uvicorn mcps.server:app --host 0.0.0.0 --port 9100

# En otra terminal, probar con el token por defecto:
curl -X POST http://localhost:9100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer hc_dev_token_no_usar_en_produccion" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### Arranque producción (con JWKS)

```bash
MCP_PUBLIC_URL=https://mcp.healthcore.ai \
MCP_ISSUER=https://auth.healthcore.ai \
MCP_JWKS_URI=https://auth.healthcore.ai/.well-known/jwks.json \
uv run uvicorn mcps.server:app --host 0.0.0.0 --port 9100
```

> **⚠️ Importante**: `mcpauth.MCPAuth` valida que el `AuthServerConfig` incluya `response_types_supported=["code"]`, `grant_types_supported=["authorization_code"]` y `code_challenge_methods_supported=["S256"]`, incluso en modo Resource Server. Esto es requerido por la implementación de referencia (mcpauth v0.1.1). Ver `mcps/auth.py`.

---

## Tools expuestas

### Incidents (5 tools)

| Tool | Método HTTP interno | Scope requerido | Descripción |
|------|-------------------|----------------|-------------|
| `get_incident` | `GET /api/incidents/{id}` | `incidents.read` | Obtener incidente por ID |
| `list_incidents` | `GET /api/incidents` | `incidents.read` | Listar incidentes con filtros |
| `create_incident` | `POST /api/incidents` | `incidents.write` | Crear nuevo incidente |
| `update_incident_status` | **`PATCH /api/incidents/{id}/status`** | `incidents.write` | Cambiar estado vía endpoint de ciclo de vida |
| `get_incident_summary` | `GET /api/incidents/summary` | `incidents.read` | Resumen estadístico de incidentes |

> `update_incident_status` usa el **endpoint de ciclo de vida** específico (`PATCH /api/incidents/{id}/status`), no un PATCH genérico sobre el recurso.

#### `get_incident`

**Argumentos:**
```json
{
  "ticket_id": 123
}
```

**Respuesta:**
```json
{
  "success": true,
  "incident": {
    "id": 123,
    "title": "Patient not informed of reschedule",
    "status": "resolved",
    "category": "patient_experience",
    "origin": "customer",
    "branch": "london_west",
    "branch_label": "London — West",
    "description_preview": "Patient not informed of appointment reschedule by clinic",
    "created_at": "2024-01-17T00:00:00+00:00",
    "updated_at": "2026-09-10T14:43:15.712221+00:00"
  }
}
```

#### `list_incidents`

**Argumentos:**
```json
{
  "status": "open",
  "category": "clinical_equipment",
  "origin": "branch",
  "branch": "central",
  "limit": 50
}
```

Todos los filtros son opcionales.

**Respuesta:**
```json
{
  "success": true,
  "incidents": [...],
  "total": 5
}
```

#### `create_incident`

**Argumentos:**
```json
{
  "title": "Equipo de ultrasonido no funciona",
  "description": "El equipo de ultrasonido de la sala 3 no enciende",
  "category": "clinical_equipment",
  "origin": "branch",
  "branch": "central",
  "reported_by": "Dr. García"
}
```

**Respuesta:**
```json
{
  "success": true,
  "incident": {...}
}
```

#### `update_incident_status`

**Argumentos:**
```json
{
  "ticket_id": 123,
  "status": "resolved",
  "comment": "Se reparó el equipo"
}
```

**Transiciones válidas:** `open → in_progress`, `in_progress → resolved`, `in_progress → discarded`, `open → discarded`. Los estados `resolved` y `discarded` son finales.

**Respuesta:**
```json
{
  "success": true,
  "incident": {...}
}
```

#### `get_incident_summary`

**Argumentos:** ninguno.

**Respuesta:**
```json
{
  "success": true,
  "summary": {
    "total": 42,
    "by_status": {"open": 5, "in_progress": 3, "resolved": 30, "discarded": 4},
    "by_category": {"clinical_equipment": 10, ...},
    "by_origin": {"customer": 20, "branch": 15, "internal": 7}
  }
}
```

---

### Inventory (5 tools — 2 lectura + 3 rechazo explícito de escritura)

| Tool | Método HTTP interno | Scope requerido | Descripción |
|------|-------------------|----------------|-------------|
| `get_product` | `GET /inventory/products/{id}` | `inventory.read` | Obtener producto por ID |
| `list_products` | `GET /inventory/products` | `inventory.read` | Listar productos con filtros |
| `create_product` | — (rechazada) | `inventory.write` | **Rechazada.** Devuelve error controlado: inventario read-only |
| `update_product` | — (rechazada) | `inventory.write` | **Rechazada.** Devuelve error controlado: inventario read-only |
| `delete_product` | — (rechazada) | `inventory.write` | **Rechazada.** Devuelve error controlado: inventario read-only |

> ⚠️ **Rechazo explícito (RETO 2).** Las tools de escritura `create_product`, `update_product` y `delete_product` **existen y son descubribles** por el cliente MCP, pero devuelven un error controlado indicando que el inventario es solo lectura. Esto evita que el agente reciba un "tool not found" y reintente; en su lugar recibe un mensaje claro. No basta con "no implementar" la tool — el servidor debe rechazar explícitamente cualquier intento de modificación.

#### `get_product`

**Argumentos:**
```json
{
  "product_id": 456
}
```

**Respuesta:**
```json
{
  "success": true,
  "product": {
    "id": 456,
    "name": "Guantes quirúrgicos talla M",
    "sku": "GLOVE-M-001",
    "category": "supplies",
    "unit": "caja",
    "current_stock": 120,
    "expiry_date": "2026-12-31",
    "country": "US"
  }
}
```

#### `list_products`

**Argumentos:**
```json
{
  "category": "supplies",
  "name_search": "guantes"
}
```

**Respuesta:**
```json
{
  "success": true,
  "products": [...]
}
```

---

## OAuth Flow (MCP Auth — Resource Server)

### Arquitectura de autenticación

```
┌───────────────────────┐
│  Authorization Server │  ← Keycloak, Auth0, Cognito, etc.
│  (emite JWT)          │     (OIDC agnóstico)
└──────────┬────────────┘
           │ JWT signed (RS256)
           ▼
┌───────────────────────┐     Bearer JWT           ┌──────────────────────────┐
│  MCP Client           │ ───────────────────────▶ │  SelectiveBearerASGI     │
│  (agente, Playground) │                          │  ┌─ .well-known/ público │
└───────────────────────┘                          │  └─ /mcp → valida JWT    │
                                                   │     - issuer             │
                                                   │     - signature (JWKS)   │
                                                   │     - exp                │
                                                   │     - scopes             │
                                                   └──────────────────────────┘
```

### Protected Resource Metadata (RFC 9728)

El servidor publica metadata del recurso protegido en `/.well-known/oauth-protected-resource` **(público, sin autenticación)**:

```
GET /.well-known/oauth-protected-resource

HTTP/1.1 200 OK
Content-Type: application/json

{
  "resource": "https://mcp.healthcore.ai",
  "authorization_servers": ["https://auth.healthcore.ai"],
  "scopes_supported": ["incidents.read", "incidents.write", "inventory.read", "inventory.write"],
  "bearer_methods_supported": ["header"]
}
```

### Flujo típico

1. El **cliente MCP** descubre el AS consultando `/.well-known/oauth-protected-resource`.
2. El cliente obtiene un JWT del AS con los scopes necesarios.
3. En cada request MCP, el cliente envía `Authorization: Bearer <jwt>`.
4. El **middleware Bearer** (mcpauth) valida: firma contra JWKS, issuer, expiración, scopes.
5. Si el token es válido, la request pasa al FastMCP. Si no, responde 401/403.

### Modos de validación

| Modo | Configuración | Comportamiento |
|------|--------------|----------------|
| **JWKS** (producción) | `MCP_JWKS_URI` configurado | Valida JWT asimétricamente (RS256/ES256) contra el JWKS del AS. Scopes opcionales vía `MCP_REQUIRED_SCOPES` |
| **Token fijo** (desarrollo) | Sin `MCP_JWKS_URI` | Usa `MCP_DEV_TOKEN` (default `hc_dev_token_no_usar_en_produccion`) como secreto compartido. `show_error_details=True` para debug |
| **Skip** (desarrollo) | `MCP_SKIP_AUTH=1` | Sin validación. El servidor arranca sin middleware Bearer. Solo para tests locales |

### Códigos de error (Bearer Auth)

| Escenario | HTTP | `error` code | Descripción |
|-----------|------|-------------|-------------|
| Sin header `Authorization` | 401 | `missing_auth_header` | El cliente no envió token |
| Token inválido/malformado | 401 | `invalid_token` | Firma, issuer o formato incorrecto |
| Token sin scopes requeridos | 403 | `missing_required_scopes` | Token válido pero sin permisos |
| Error interno del AS | 500 | `server_error` | Error al validar contra el AS remoto |

---

## Implementación de la capa OAuth

### `mcps/auth.py`

El módulo `auth.py` contiene tres componentes clave:

1. **`build_auth_server_config()`** — Construye un `AuthServerConfig` con los campos que mcpauth requiere incluso en modo RS:
   ```python
   AuthorizationServerMetadata(
       issuer=issuer,
       authorization_endpoint="",
       token_endpoint="",
       jwks_uri=jwks_uri or None,
       response_types_supported=["code"],          # Requerido por mcpauth
       grant_types_supported=["authorization_code"], # Requerido por mcpauth
       code_challenge_methods_supported=["S256"],    # Requerido por mcpauth
       token_endpoint_auth_methods_supported=["client_secret_basic"],
       scope_supported=["incidents.read", ...],
   )
   ```

2. **`build_bearer_middleware(mcp_auth)`** — Crea el middleware Bearer vía `mcp_auth.bearer_auth_middleware()`:
   - Si `MCP_JWKS_URI` está configurado → modo `"jwt"` (validación asimétrica)
   - Si no → modo dev con `_verify_dev_token()` (token fijo)

3. **`SelectiveBearerASGI`** — Wrapper ASGI que aplica el middleware Bearer solo en rutas protegidas, dejando `/.well-known/` y `/health` públicas:
   ```python
   class SelectiveBearerASGI:
       EXCLUDED_PREFIXES = ("/.well-known/", "/health", "/openapi")
       async def __call__(self, scope, receive, send):
           if path.startswith(self.EXCLUDED_PREFIXES):
               await self._public_app(scope, receive, send)  # Sin auth
           else:
               await self._protected_app(scope, receive, send)  # Con auth
   ```

### `mcps/server.py` — Composición ASGI

```python
# 1. Obtener app Streamable HTTP de FastMCP (stateless_http=True)
mcp_app = mcp.streamable_http_app()

# 2. Agregar rutas públicas (Protected Resource Metadata)
for route in build_protected_resource_routes():
    mcp_app.add_route(path=route.path, route=route.endpoint, methods=route.methods)

# 3. Envolver con ASGI selectivo (público directo, protegido con Bearer)
app = SelectiveBearerASGI(
    mcp_asgi_app=mcp_app,
    bearer_mw_class=bearer_mw_class,
)
```

> **Importante**: No se usa `Starlette(routes=[...Mount(...)])` para anidar el FastMCP, porque eso rompe el lifespan del session manager. En su lugar, se usa `SelectiveBearerASGI` a nivel ASGI puro, preservando el ciclo de vida original.

### Logging por invocación de tool

Cada llamada a una tool registra un log estructurado vía `_serialize_result()`:

```python
logger.info("Tool OK | tool=%(label)s | success=true", {"label": label})
logger.warning("Tool ERROR | tool=%(label)s | success=false | error=%(error)s",
    {"label": label, "error": error_msg[:120]})
```

Ejemplo de salida:
```
Tool OK | tool=incidente creado | success=true
Tool ERROR | tool=productos | success=false | error=HTTP 401: Invalid token
```

---

## Migración del agente LangGraph

### Antes (HTTP directo)

```python
# services/agent/graph.py
from services.agent.tools.incidents import query_incident_by_id
from services.agent.tools.inventory import query_product_by_id

def node_query_incident(state):
    result = query_incident_by_id(ticket_id)  # HTTP directo sincrónico
    ...
```

### Después (MCP Client)

```python
# services/agent/graph.py
from services.agent.tools.mcp_client import (
    query_incident_by_id,
    query_products_list,
    ...
)

async def node_query_incident(state):
    result = await query_incident_by_id(ticket_id)  # MCP Client async
    ...
```

**Cambios necesarios:**

1. **Reemplazar imports**: `services.agent.tools.incidents` → `services.agent.tools.mcp_client`
2. **Convertir nodos a async**: `def` → `async def`, llamadas con `await`
3. **`run_agent` debe ser async**: usar `await agent_graph.ainvoke(...)` en lugar de `.invoke()`
4. **Endpoint FastAPI**: `def` → `async def` con `await run_agent(...)`
5. **Tests**: usar `@pytest.mark.asyncio` y `await` en tests que llamen `run_agent` o nodos tool

### MCP Client module (`services/agent/tools/mcp_client.py`)

El módulo usa **`langchain-mcp-adapters`** para cargar las tools del MCP Server como objetos `BaseTool` de LangChain:

```python
from langchain_mcp_adapters.tools import load_mcp_tools

async def _get_tool(tool_name: str) -> BaseTool | None:
    global _tools_cache
    if _tools_cache is None:
        session = await _ensure_session()
        lc_tools = await load_mcp_tools(session=session)
        _tools_cache = {tool.name: tool for tool in lc_tools}
    return _tools_cache.get(tool_name)
```

Cada función pública invoca la tool con `tool.ainvoke(arguments)` y normaliza el resultado al formato que esperan los nodos del grafo.

El módulo expone las mismas 6 funciones que las tools originales, pero asíncronas:

| Función | Tool MCP | Descripción |
|---------|----------|-------------|
| `query_incident_by_id(ticket_id)` | `get_incident` | Obtiene incidente por ID |
| `query_incidents_list(status, category, origin, branch)` | `list_incidents` | Lista incidentes |
| `create_incident(title, description, category, origin, branch)` | `create_incident` | Crea incidente |
| `update_incident_status(ticket_id, status, comment)` | `update_incident_status` | Cambia estado |
| `query_product_by_id(product_id)` | `get_product` | Obtiene producto |
| `query_products_list(category, name_search)` | `list_products` | Lista productos |

**Configuración vía entorno:**
- `MCP_SERVER_URL` — URL del MCP Server (default `http://mcp-server:9100`)
- `MCP_TRANSPORT` — Transporte (`streamable-http` o `stdio`)
- `MCP_AGENT_TOKEN` — Token Bearer JWT para autenticación contra el MCP Server

> **🧹 Archivos legacy**: `services/agent/tools/incidents.py` e `inventory.py` (las tools HTTP directas originales) están marcados como **DEPRECATED** con `DeprecationWarning` y docstring actualizado. El agente LangGraph ya no los importa. Se eliminarán en una limpieza futura. El `__init__.py` del paquete también se actualizó para reflejar la arquitectura MCP Client.

---

## Testing

### Tests del grafo migrado

```bash
uv run pytest tests/pipelines/test_agent_graph.py -v
```

Los tests parchean la referencia importada en el módulo del grafo (no el módulo original):

```python
with patch("services.agent.graph.query_incident_by_id", return_value=mock_data):
    result = await run_agent("¿Estado del ticket 2?", run_id=run_id)
```

### Tests del MCP Server

```bash
# 1. Arrancar servidor con auth en modo dev
MCP_SKIP_AUTH=0 MCP_JWKS_URI="" MCP_ISSUER="https://oidc.example.com" \
  MCP_PUBLIC_URL="http://localhost:9100" \
  uv run uvicorn mcps.server:app --host 0.0.0.0 --port 9100

# 2. Sin token → 401
curl -s -w "\nHTTP_CODE: %{http_code}\n" http://localhost:9100/mcp \
  -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 3. Con token válido → 200 + tools list
curl -s -w "\nHTTP_CODE: %{http_code}\n" http://localhost:9100/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer hc_dev_token_no_usar_en_produccion" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 4. Protected Resource Metadata (público)
curl -s http://localhost:9100/.well-known/oauth-protected-resource
```

Con `MCP_PUBLIC_URL` configurada, la metadata incluirá los `authorization_servers`.

### Probar tools individuales con Streamable HTTP

Streamable HTTP usa un protocolo específico con manejo de sesiones. Con `stateless_http=True`, cada request es independiente:

```bash
curl -X POST http://localhost:9100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_incident",
      "arguments": {"ticket_id": 2}
    }
  }'
```

### Diagnosticar logs

El servidor registra logs detallados a nivel INFO. Para ver logging de depuración:

```bash
uv run uvicorn mcps.server:app --host 0.0.0.0 --port 9100 --log-level debug
```

---

## Estructura del paquete

```
mcps/
  __init__.py       # Package init
  config.py         # Variables de entorno y constantes
  server.py         # FastMCP instance, tool definitions, CLI, composición ASGI
  tools.py          # Implementación HTTP de las 7 tools
  auth.py           # OAuth helpers: AuthServerConfig, bearer middleware,
                    # SelectiveBearerASGI, Protected Resource Metadata
```

---

## Notas de producción

- **Nunca** ejecutar con `MCP_SKIP_AUTH=1` en producción.
- **Nunca** usar el token fijo `hc_dev_token_no_usar_en_produccion` en producción. Configurar `MCP_JWKS_URI` con un AS real.
- El MCP Server debe estar detrás de un reverse proxy (nginx, Caddy) para TLS.
- El token `AGENT_JWT_TOKEN` (backend-to-backend) lo necesita el MCP Server internamente para consultar inventario. Es independiente del token Bearer que presenta el agente al MCP Server.
- `stateless_http=True` elimina la necesidad de sesiones persistentes. Cada request es autocontenida.
- La metadata `/.well-known/oauth-protected-resource` es **pública** (no requiere autenticación) para que los clientes MCP puedan descubrir el AS y los scopes antes de obtener un token.
- El `MCPAuth` de mcpauth requiere `response_types_supported=["code"]`, `grant_types_supported=["authorization_code"]` y `code_challenge_methods_supported=["S256"]` en el `AuthServerConfig`, incluso en modo Resource Server. Esto es una validación de la librería, no del estándar.

---

## Audit de aceptación (9 criterios)

| # | Criterio | Estado | Detalle |
|---|----------|--------|---------|
| 1 | Package `mcps/` existe | ✅ | `mcps/__init__.py`, `config.py`, `server.py`, `tools.py`, `auth.py`. Servidor levanta correctamente y expone tools vía `tools/list`. |
| 2 | Sin OAuth no se ejecutan tools | ✅ (REPARADO) | **ESTABA ROTO**: `config.py` tenía lógica inversa (`MCP_REQUIRED_SCOPES = ["incidents.read"] if os.getenv("MCP_SKIP_AUTH")`). Sin `MCP_SKIP_AUTH` los scopes quedaban vacíos → middleware no exigía token. Corregido a `if not os.getenv("MCP_SKIP_AUTH")`. Ahora: sin token → HTTP 401 `missing_auth_header`; con token válido → HTTP 200. |
| 3 | `update_incident_status` usa `PATCH /api/incidents/{id}/status` | ✅ | La tool `update_incident_status` en `tools.py` usa `PATCH /api/incidents/{id}/status` del Incidents Manager real. Create/get/list también contra el backend real. |
| 4 | Inventario solo lectura | ✅ | Tools de lectura (`get_product`, `list_products`) funcionan. **Además**: `create_product`, `update_product`, `delete_product` existen y devuelven error controlado `{"error": "read_only", "message": "..."}` (RETO 2 del ticket). El cliente MCP nunca recibe "tool not found". Scopes: `inventory.read` para lectura, `inventory.write` para las rejection tools. |
| 5 | Descripciones y schemas claros | ✅ | `@mcp.tool(description=…)` con descripciones semánticas en español. `inputSchema` con tipos anotados, valores válidos documentados, parámetros opcionales con `default`. Verificable via `tools/list`. |
| 6 | Errores diferenciados | ✅ | Sin token → `missing_auth_header` (401). Token inválido → `invalid_token` (401). Token sin scope → `missing_required_scopes` (403). Tool timeout → `"El servicio no respondió en Ns"`. Conexión fallida → `"No se pudo conectar"`. HTTP error → `"código NNN"`. Validación campo requerido → Pydantic `Field required` (422). |
| 7 | Log por invocación | ✅ | `_serialize_result()` registra `Tool OK | tool=<label> | success=true` o `Tool ERROR | tool=<label> | success=false | error=<msg>`. Un log por invocación con cliente, tool y resultado. |
| 8 | Agente usa MCP Client | ✅ | `graph.py` importa solo de `services.agent.tools.mcp_client`. El cliente usa **`langchain-mcp-adapters`** (`load_mcp_tools`) para convertir tools MCP a BaseTool de LangChain, cumpliendo RETO 4 del ticket. Archivos legacy `incidents.py` e `inventory.py` marcados como DEPRECATED con `DeprecationWarning`. 32 tests pasando. |
| 9 | MCP Playground / URL pública | ✅ | URL pública de Codespaces (`https://<codespace>-9100.app.github.dev/mcp`) configurada con visibilidad **Public**. CORS: `access-control-allow-origin: *`. **Fix transport_security**: se deshabilitó `enable_dns_rebinding_protection` en FastMCP vía `TransportSecuritySettings` para permitir proxies reversos. Verificado: `tools/list` → 10 tools, `tools/call` → write rejection `{"error": "read_only", "success": false}`. |

---

## Validación con MCP Playground

### Requisitos

- Servidor MCP corriendo con `MCP_SKIP_AUTH=1` (modo desarrollo sin OAuth)
- Puerto **públicamente accesible** desde Internet

### 1. Exponer el puerto en Codespaces

El puerto del servidor MCP (default `9100`) debe estar en **visibilidad pública** para que MCP Playground pueda conectarse:

```bash
# Cambiar visibilidad del puerto 9100 a public
gh codespace ports visibility 9100:public

# Verificar estado
gh codespace ports
```

La URL pública sigue el patrón:

```
https://<codespace-name>-<port>.app.github.dev/mcp
```

Por ejemplo:
```
https://congenial-pancake-gxq77rxwr56q3v7x4-9100.app.github.dev/mcp
```

> **⚠️ Nota**: Si el servidor no está corriendo, Codespaces devuelve **HTTP 502**. Verificar con `lsof -i :9100` antes de probar.

### 2. Conectar desde MCP Playground

1. Abrir https://www.mcpplayground.tech/playground
2. Ingresar la URL pública en el campo de conexión: `https://<codespace>-9100.app.github.dev/mcp`
3. Click **Connect**
4. El Playground listará las **10 tools** disponibles

### 3. Probar flujos completos

#### Tools de lectura (incidentes)

- `get_incident` → requiere `ticket_id` (entero)
- `list_incidents` → filtros opcionales: `status`, `category`, `origin`, `branch`, `limit`, `offset`
- `get_incident_summary` → sin argumentos

> En desarrollo sin los backends, estas tools devuelven error de conexión esperado.

#### Tools de escritura (incidentes)

- `create_incident` → requiere `title`, `description`, `category`, `origin`, `branch`
- `update_incident_status` → requiere `ticket_id`, `status`

#### Tools de inventario (solo lectura + rechazo explícito)

- `get_product` → requiere `product_id` (entero)
- `list_products` → filtros opcionales: `category`, `name_search`, `limit`, `offset`
- `create_product` → **✅ Devuelve error controlado**: `{"error": "read_only", "success": false}`
- `update_product` → **✅ Devuelve error controlado**: `{"error": "read_only", "success": false}`
- `delete_product` → **✅ Devuelve error controlado**: `{"error": "read_only", "success": false}`

### 4. Verificación con curl

```bash
# Probar servidor en local
curl -s -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' \
  http://127.0.0.1:9100/mcp

# Probar vía URL pública de Codespaces
PUBLIC_URL="https://<codespace>-9100.app.github.dev/mcp"
curl -s -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Origin: https://www.mcpplayground.tech" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' \
  "$PUBLIC_URL"

# Probar write rejection
curl -s -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"create_product","arguments":{"name":"Test","category":"supplies","unit":"unit"}}}' \
  "$PUBLIC_URL" | grep '"text"'
```

### 5. Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `HTTP 502` desde URL pública | Servidor MCP no está corriendo | `uvicorn mcps.server:app --host 0.0.0.0 --port 9100` |
| `HTTP 502` después de arrancar servidor | Proxy de Codespaces no actualizado | Esperar 10-30 segundos y reintentar |
| `401 Unauthorized` | `MCP_SKIP_AUTH` no está configurado | Usar `MCP_SKIP_AUTH=1` para desarrollo |
| Conexión fallida en Playground | Puerto no es público | `gh codespace ports visibility 9100:public` |
| Playground no lista tools | CORS bloqueado | Verificar cabecera `access-control-allow-origin: *` en respuesta OPTIONS |
| `Invalid Host header` | FastMCP DNS rebinding protection | Ya fixeado con `TransportSecuritySettings(enable_dns_rebinding_protection=False)` |

---

## Resumen de fixes aplicados

Durante la implementación se corrigieron los siguientes bugs / desviaciones del ticket:

| # | Bug / Desviación | Síntoma | Fix |
|---|------------------|---------|-----|
| 1 | **Auth invertido** — `MCP_REQUIRED_SCOPES` se llenaba con `MCP_SKIP_AUTH=1` y quedaba vacío sin ella | Sin `MCP_SKIP_AUTH` el middleware no exigía token → cualquiera podía llamar tools | Invertir condición: `if not os.getenv("MCP_SKIP_AUTH")` |
| 2 | **langchain-mcp-adapters listo en pyproject pero no importado** (RETO 4) | `mcp_client.py` usaba HTTP directo en vez de `load_mcp_tools` | Refactorizar `mcp_client.py` para usar `load_mcp_tools(session=session)` y `BaseTool.ainvoke()` |
| 3 | **Write rejection solo en comentarios** (RETO 2) | `create_product`, `update_product`, `delete_product` no existían como tools; el cliente recibiría "tool not found" | Implementar las 3 tools como rejection explícito con error controlado |
| 4 | **Invalid Host header con túneles** | localtunnel, Codespaces proxy y cualquier reverse proxy recibían HTTP 421 | Añadir `transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)` al constructor de FastMCP |
| 5 | **Puerto Codespaces en modo Private** | URL pública de Codespaces devolvía HTTP 502 porque el proxy no reenviaba al puerto | `gh codespace ports visibility 9100:public` |

---

*Documento generado como parte del criterio de aceptación del ticket de implementación MCP Server + OAuth.*
