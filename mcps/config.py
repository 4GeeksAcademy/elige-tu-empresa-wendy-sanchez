"""HealthCore MCP Server — configuration & bootstrap.

Arquitectura:
  - ``FastMCP`` (SDK oficial MCP v1) define las tools.
  - ``mcpauth.MCPAuth`` protege el servidor con OAuth 2.1: valida tokens
    Bearer JWT, aplica ``required_scopes`` (mínimo privilegio) y publica
    Protected Resource Metadata en ``/.well-known/oauth-protected-resource``.

Transporte por defecto: **Streamable HTTP** (un solo endpoint HTTP que
permite múltiples clientes remotos — el agente LangGraph, el MCP
Playground, clientes externos).  No usamos stdio (monocliente local).

Configuración vía variables de entorno:

  MCP_HOST              Host de escucha (default 0.0.0.0)
  MCP_PORT              Puerto (default 9100)
  MCP_TRANSPORT         "streamable-http" | "stdio" (default streamable-http)
  MCP_PUBLIC_URL        URL pública anunciada en la metadata de OAuth
                        (ej. https://<codespace>-9100.app.github.dev)
  MCP_ISSUER            Issuer esperado en los JWT (default MCP_PUBLIC_URL)
  INCIDENTS_API_URL     URL del Incidents Manager (default http://incidents-backend:8010)
  INVENTORY_API_URL     URL del módulo de inventario (default http://backend:8000)
  AGENT_JWT_TOKEN       JWT backend-a-backend para inventario (read-only)
  MCP_SKIP_AUTH=1       PARA PRUEBAS LOCALES únicamente; nunca en producción.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Directorios / rutas ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

# ── Configuración del transporte ─────────────────────────────────────
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "9100"))
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")

# ── OAuth / MCP Auth ─────────────────────────────────────────────────
MCP_PUBLIC_URL = os.getenv("MCP_PUBLIC_URL", "").rstrip("/")
MCP_ISSUER = os.getenv("MCP_ISSUER", MCP_PUBLIC_URL or f"http://localhost:{MCP_PORT}")
MCP_JWKS_URI = os.getenv(
    "MCP_JWKS_URI",
    ""
    or (f"{MCP_PUBLIC_URL}/.well-known/jwks.json" if MCP_PUBLIC_URL else ""),
)

# Scopes soportados — mínimo privilegio por dominio.
# Un token debe traer el scope exacto para poder llamar a la tool.
MCP_SCOPES_SUPPORTED = [
    "incidents.read",
    "incidents.write",
    "inventory.read",
]

# Scopes requeridos globalmente (todas las tools).  Se aplican además de
# los scopes específicos que cada tool exige.  Usamos uno "base" para que
# un token sin ningún scope sea rechazado incluso antes de llegar a la tool.
MCP_REQUIRED_SCOPES = ["incidents.read"] if os.getenv("MCP_SKIP_AUTH") else []

# ── Propiedades del servidor ─────────────────────────────────────────
SERVER_NAME = "healthcore-mcp"
SERVER_TITLE = "HealthCore MCP Server"
SERVER_VERSION = "1.0.0"
SERVER_DESCRIPTION = (
    "MCP Server de HealthCore que expone el Incidents Manager y el módulo "
    "de inventario como tools MCP. Protected con OAuth 2.1 via MCP Auth."
)