# HealthCore MCP Server

> **MCP Server** que expone el **Incidents Manager** y el **módulo de inventario** como herramientas MCP (Model Context Protocol), protegidas con **OAuth 2.1** vía MCP Auth (modo Resource Server).

---

## Arquitectura

```
┌─────────────────┐     OAuth 2.1 (Bearer JWT)        ┌──────────────────────┐
│  MCP Clients    │ ──── scopes: incidents.*  ────▶  │  MCP Server          │
│  (Agente, CLI)  │      inventory.read               │  puerto 9100         │
└─────────────────┘                                   │  Streamable HTTP     │
                                                      │                      │
                                                      │  ┌────────────────┐  │
                                                      │  │ get_incident   │  │
                                                      │  │ list_incidents │──┼──▶ Incidents API :8010
                                                      │  │ create_incident│  │
                                                      │  │ update_status  │  │
                                                      │  │ get_summary    │  │
                                                      │  ├────────────────┤  │
                                                      │  │ get_product    │──┼──▶ Inventory API :8000
                                                      │  │ list_products  │  │    (JWT Bearer)
                                                      │  └────────────────┘  │
                                                      └──────────────────────┘
```

### Decisiones técnicas

| Decisión | Opción | Motivo |
|----------|--------|--------|
| **OAuth** | MCP Auth (modo Resource Server) | Alineado con la especificación MCP Auth; desacoplado de FastMCP; soporta cualquier proveedor OIDC; publica RFC 9728 |
| **Transporte** | Streamable HTTP | Un solo endpoint HTTP; múltiples clientes simultáneos; sin limitación monocliente de stdio |
| **Framework** | FastMCP v1 (`mcp>=1.24,<2`) | SDK oficial MCP; integración directa con `@mcp.tool()` |
| **Auth token** | Bearer JWT vía `MCP_AGENT_TOKEN` | El agente presenta un token al MCP Server; el Server valida contra JWKS o token simétrico |
| **Scopes** | Mínimo privilegio: `incidents.read`, `incidents.write`, `inventory.read` | Cada tool exige el scope mínimo necesario |

---

## Setup

### Dependencias

```bash
uv add "mcp>=1.24.0,<2" "mcpauth>=0.1.0" "fastmcp>=1.0.0"
```

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Host de escucha |
| `MCP_PORT` | `9100` | Puerto |
| `MCP_TRANSPORT` | `streamable-http` | Transporte MCP |
| `MCP_PUBLIC_URL` | — | URL pública (ej. Codespaces) |
| `MCP_ISSUER` | `MCP_PUBLIC_URL` | Issuer esperado en JWT |
| `MCP_JWKS_URI` | — | URI del JWKS endpoint (para validación asimétrica) |
| `INCIDENTS_API_URL` | `http://incidents-backend:8010` | URL del Incidents Manager |
| `INVENTORY_API_URL` | `http://backend:8000` | URL del módulo de inventario |
| `AGENT_JWT_TOKEN` | — | JWT backend-a-backend para inventario (lo usa el propio MCP Server) |
| `MCP_AGENT_TOKEN` | — | Token que el agente LangGraph presenta al MCP Server |
| `MCP_SKIP_AUTH` | — | `1` para deshabilitar auth (solo desarrollo local) |

### Arranque local (sin auth)

```bash
MCP_SKIP_AUTH=1 uv run python -m mcps.server
```

### Arranque local (con auth)

```bash
# Generar un token para pruebas
MCP_AGENT_TOKEN="dev-token" MCP_SKIP_AUTH=1 uv run python -m mcps.server
```

> En producción: el cliente obtiene un JWT firmado del Authorization Server configurado y lo presenta vía header `Authorization: Bearer <token>`.

---

## Tools expuestas

### Incidents (5 tools)

| Tool | Método HTTP interno | Auth requerida | Descripción |
|------|-------------------|----------------|-------------|
| `get_incident` | `GET /api/incidents/{id}` | `incidents.read` | Obtener incidente por ID |
| `list_incidents` | `GET /api/incidents` | `incidents.read` | Listar incidentes con filtros |
| `create_incident` | `POST /api/incidents` | `incidents.write` | Crear nuevo incidente |
| `update_incident_status` | `PATCH /api/incidents/{id}/status` | `incidents.write` | Cambiar estado del incidente |
| `get_summary` | `GET /api/incidents/summary` | `incidents.read` | Resumen estadístico de incidentes |

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

**Transiciones válidas:** `open → in_progress`, `in_progress → resolved`, `in_progress → discarded`, `open → discarded`.

**Respuesta:**
```json
{
  "success": true,
  "incident": {...}
}
```

#### `get_summary`

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

### Inventory (2 tools, read-only)

| Tool | Método HTTP interno | Auth requerida | Descripción |
|------|-------------------|----------------|-------------|
| `get_product` | `GET /inventory/products/{id}` | `inventory.read` | Obtener producto por ID |
| `list_products` | `GET /inventory/products` | `inventory.read` | Listar productos con filtros |

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

## OAuth Flow

### Modo Resource Server (MCP Auth)

El servidor MCP actúa como **Resource Server** (RFC 9728). No emite tokens — solo los valida. La metadata del recurso protegido se publica en:

```
GET /.well-known/oauth-protected-resource
```

**Respuesta:**
```json
{
  "resource": "https://mcp.healthcore.ai/.well-known/oauth-protected-resource",
  "authorization_servers": ["https://auth.healthcore.ai"],
  "scopes_supported": ["incidents.read", "incidents.write", "inventory.read"],
  "bearer_methods_supported": ["header"]
}
```

### Flujo típico

1. Un **Authorization Server** (Keycloak, Auth0, Cognito, etc.) emite JWT con scopes.
2. El **cliente MCP** (agente LangGraph, curl, MCP Playground) obtiene un token.
3. En cada request MCP, el cliente envía `Authorization: Bearer <token>`.
4. El MCP Server valida el JWT (firma, issuer, exp, scopes) y ejecuta la tool solo si los scopes coinciden.

### Validación

| Modo | Configuración | Uso |
|------|--------------|-----|
| **JWKS** (producción) | `MCP_JWKS_URI` apuntando al JWKS endpoint del AS | Validación asimétrica (RS256, ES256) |
| **Simétrico** (dev) | Sin `MCP_JWKS_URI`, usa `MCP_AGENT_TOKEN` como secreto compartido | HMAC simple para desarrollo |
| **Skip** (dev) | `MCP_SKIP_AUTH=1` | Sin validación, solo para tests locales |

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
- `MCP_AGENT_TOKEN` — Token JWT para autenticación

---

## Testing

### Tests del grafo migrado

```bash
uv run pytest tests/pipelines/test_agent_graph.py -v
```

Los tests que parchean tools ahora parchean `services.agent.graph.query_incident_by_id` (la referencia importada en el módulo del grafo), no el módulo original de herramientas:

```python
with patch("services.agent.graph.query_incident_by_id", return_value=mock_data):
    result = await run_agent("¿Estado del ticket 2?", run_id=run_id)
```

### Probar el MCP Server directamente

```bash
# Sin auth
MCP_SKIP_AUTH=1 uv run python -m mcps.server --transport streamable-http

# En otra terminal:
curl -X POST http://localhost:9100/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Probar tools individuales

```bash
curl -X POST http://localhost:9100/mcp \
  -H "Content-Type: application/json" \
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

### Diagnosticar conexión

El MCP Server expone logs detallados. Para verlos:

```bash
MCP_DEBUG=1 uv run python -m mcps.server
```

---

## Estructura del paquete

```
mcps/
  __init__.py       # Package init
  config.py         # Variables de entorno y constantes
  server.py         # FastMCP instance, tool definitions, CLI
  tools.py          # Implementación HTTP de las 7 tools
  auth.py           # OAuth helpers: AuthServerConfig, bearer middleware, metadata routes
```

---

## Notas de producción

- **Nunca** ejecutar con `MCP_SKIP_AUTH=1` en producción.
- El MCP Server debe estar detrás de un reverse proxy (nginx, Caddy) para TLS.
- El token `AGENT_JWT_TOKEN` (backend-to-backend) lo necesita el MCP Server internamente para consultar inventario. Es independiente del token MCP que presenta el agente.
- El token `MCP_AGENT_TOKEN` lo presenta el agente LangGraph al MCP Server y debe tener los scopes necesarios para las tools que el agente invoque.