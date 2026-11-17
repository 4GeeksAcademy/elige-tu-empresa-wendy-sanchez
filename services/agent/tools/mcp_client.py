"""MCP Client para el agente LangGraph de HealthCore.

Este módulo reemplaza las llamadas HTTP directas a los servicios de
incidentes e inventario por llamadas al MCP Server vía el protocolo MCP
(Streamable HTTP / client sesión).

Ventajas:
  - Centraliza la lógica de conexión, auth y error handling.
  - Las tools están declaradas en un solo sitio (el MCP Server).
  - El agente no necesita saber URLs, JWT tokens ni detalles de cada API.
  - OAuth: el cliente obtiene y refresca tokens automáticamente.

Las funciones expuestas mantienen las mismas firmas que las tools
originales (``services/agent/tools/incidents.py`` e ``inventory.py``)
para que los nodos del grafo no requieran cambios.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)

# ── Configuración ────────────────────────────────────────────────────
_MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://mcp-server:9100",  # Docker Compose service name
)

_MCP_TRANSPORT = os.getenv(
    "MCP_TRANSPORT",
    "streamable-http",
)

# Token JWT que el agente presenta al MCP Server para OAuth.
# Debe tener los scopes: incidents.read, incidents.write, inventory.read.
_MCP_AUTH_TOKEN = os.getenv("MCP_AGENT_TOKEN", "")

# Timeout para cada llamada a tool.
_MCP_TOOL_TIMEOUT_S = 10


# ═══════════════════════════════════════════════════════════════════════
#  Sesión MCP (singleton per process)
# ═══════════════════════════════════════════════════════════════════════

_session: ClientSession | None = None
"""Sesión MCP compartida (inicializada lazy)."""

_session_initialized: bool = False


async def _ensure_session() -> ClientSession:
    """Obtiene o crea la sesión MCP compartida.

    La sesión se crea una vez por proceso y se reusa para todas las
    llamadas a tools.  Si la sesión se cierra, se recrea automáticamente.
    """
    global _session, _session_initialized

    if _session is not None and _session_initialized:
        return _session

    # Cerrar sesión anterior si existe pero no está inicializada
    if _session is not None:
        try:
            await _session.close()
        except Exception:
            pass
        _session = None
        _session_initialized = False

    # Headers de autenticación
    headers: dict[str, str] = {}
    if _MCP_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {_MCP_AUTH_TOKEN}"
        logger.info("MCP Client autenticado con token OAuth.")

    try:
        if _MCP_TRANSPORT in ("streamable-http", "http"):
            logger.info("Conectando al MCP Server via Streamable HTTP: %s", _MCP_SERVER_URL)
            # Crear un cliente HTTP con los headers de autenticación
            http_client = httpx.AsyncClient(headers=headers)
            streams = await streamable_http_client(
                url=_MCP_SERVER_URL,
                http_client=http_client,
            )
        else:
            # Fallback a stdio (para desarrollo local)
            logger.info("Conectando al MCP Server via stdio")
            server_params = StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "mcps.server", "--transport", "stdio"],
            )
            streams = await stdio_client(server_params)

        _session = ClientSession(
            streams[0],
            streams[1],
            # No ponemos logging_callback para no contaminar logs del agente
        )
        await _session.initialize()
        _session_initialized = True
        logger.info("Sesión MCP inicializada correctamente.")
        return _session

    except Exception as exc:
        logger.error("Error al crear sesión MCP: %s", exc)
        _session = None
        _session_initialized = False
        raise


# ═══════════════════════════════════════════════════════════════════════
#  Llamada a tools MCP
# ═══════════════════════════════════════════════════════════════════════


async def _call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Llama a una tool del MCP Server y devuelve el resultado parseado.

    Args:
        tool_name: Nombre de la tool (ej. "get_incident", "list_products").
        arguments: Argumentos de la tool.

    Returns:
        Diccionario con el resultado.  Si la tool devuelve un JSON
        válido, lo parsea automáticamente.  Si falla la conexión o la
        tool devuelve error, retorna ``{"error": "..."}``.
    """
    try:
        session = await _ensure_session()
    except Exception as exc:
        logger.error("No se pudo conectar al MCP Server: %s", exc)
        return {"error": f"No se pudo conectar al MCP Server: {exc}"}

    try:
        result = await session.call_tool(
            tool_name,
            arguments=arguments or {},
        )

        # Extraer el contenido textual de la respuesta MCP
        if result.content and len(result.content) > 0:
            text_content = result.content[0].text
            # Intentar parsear como JSON
            try:
                parsed = json.loads(text_content)
                return parsed
            except (json.JSONDecodeError, TypeError):
                return {"data": text_content}
        else:
            return {"error": "MCP tool returned no content"}

    except Exception as exc:
        logger.warning("Error llamando a tool MCP '%s': %s", tool_name, exc)
        return {"error": f"Error en tool MCP '{tool_name}': {exc}"}


# ═══════════════════════════════════════════════════════════════════════
#  Incidents — firmas idénticas a services/agent/tools/incidents.py
# ═══════════════════════════════════════════════════════════════════════


async def query_incident_by_id(ticket_id: int) -> dict[str, Any]:
    """Obtiene un incidente por su ID.

    Args:
        ticket_id: Número de ticket.

    Returns:
        Diccionario con los campos del incidente, o ``{"error": "…"}``.
    """
    result = await _call_tool("get_incident", {"ticket_id": ticket_id})

    if "error" in result:
        return result

    # Normalizar: la tool devuelve {"success": true, "incident": {...}}
    if result.get("success") and "incident" in result:
        return result["incident"]

    return result


async def query_incidents_list(
    status: str | None = None,
    category: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
) -> list[dict[str, Any]]:
    """Lista incidentes con filtros opcionales.

    Args:
        status: Filtrar por estado.
        category: Filtrar por categoría.
        origin: Filtrar por origen.
        branch: Filtrar por sucursal.

    Returns:
        Lista de incidentes, o lista vacía si error.
    """
    args: dict[str, Any] = {}
    if status:
        args["status"] = status
    if category:
        args["category"] = category
    if origin:
        args["origin"] = origin
    if branch:
        args["branch"] = branch
    args["limit"] = 50  # Suficiente para el agente

    result = await _call_tool("list_incidents", args)

    if "error" in result:
        logger.warning("Error en query_incidents_list: %s", result["error"])
        return []

    if result.get("success") and "incidents" in result:
        return result["incidents"]

    return []


async def create_incident(
    title: str,
    description: str,
    category: str,
    origin: str,
    branch: str,
    reported_by: str | None = None,
) -> dict[str, Any]:
    """Crea un nuevo incidente.

    NO era parte de las tools originales (eran solo lectura), pero ya que
    el MCP Server expone escritura, el agente puede crear incidentes.

    Args:
        title: Título del incidente.
        description: Descripción.
        category: Categoría.
        origin: Origen.
        branch: Sucursal.
        reported_by: Quién reporta.

    Returns:
        El incidente creado o ``{"error": "..."}``.
    """
    args: dict[str, Any] = {
        "title": title,
        "description": description,
        "category": category,
        "origin": origin,
        "branch": branch,
    }
    if reported_by:
        args["reported_by"] = reported_by

    result = await _call_tool("create_incident", args)

    if "error" in result:
        return result

    if result.get("success") and "incident" in result:
        return result["incident"]

    return result


async def update_incident_status(
    ticket_id: int,
    status: str,
    comment: str | None = None,
) -> dict[str, Any]:
    """Actualiza el estado de un incidente (usa endpoint de ciclo de vida).

    Args:
        ticket_id: Número de ticket.
        status: Nuevo estado (in_progress, resolved, discarded).
        comment: Comentario opcional.

    Returns:
        Incidente actualizado o ``{"error": "..."}``.
    """
    args: dict[str, Any] = {
        "ticket_id": ticket_id,
        "status": status,
    }
    if comment:
        args["comment"] = comment

    result = await _call_tool("update_incident_status", args)

    if "error" in result:
        return result

    if result.get("success") and "incident" in result:
        return result["incident"]

    return result


# ═══════════════════════════════════════════════════════════════════════
#  Inventory — firmas idénticas a services/agent/tools/inventory.py
# ═══════════════════════════════════════════════════════════════════════


async def query_product_by_id(product_id: int) -> dict[str, Any]:
    """Obtiene un producto del inventario por su ID.

    Args:
        product_id: ID del producto.

    Returns:
        Datos del producto o ``{"error": "..."}``.
    """
    result = await _call_tool("get_product", {"product_id": product_id})

    if "error" in result:
        return result

    if result.get("success") and "product" in result:
        return result["product"]

    return result


async def query_products_list(
    category: str | None = None,
    name_search: str | None = None,
) -> list[dict[str, Any]]:
    """Lista productos del inventario con filtros opcionales.

    Args:
        category: Filtrar por categoría.
        name_search: Búsqueda por nombre.

    Returns:
        Lista de productos, o lista vacía si error.
    """
    args: dict[str, Any] = {}
    if category:
        args["category"] = category
    if name_search:
        args["name_search"] = name_search
    args["limit"] = 50

    result = await _call_tool("list_products", args)

    if "error" in result:
        logger.warning("Error en query_products_list: %s", result["error"])
        return []

    if result.get("success") and "products" in result:
        return result["products"]

    return []