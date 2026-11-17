"""MCP Client para el agente LangGraph de HealthCore.

Este módulo reemplaza las llamadas HTTP directas a los servicios de
incidentes e inventario por llamadas al MCP Server vía el protocolo MCP
(Streamable HTTP / client sesión), usando **langchain-mcp-adapters** como
capa de integración.

Cómo funciona:
  1. ``_ensure_session()`` crea/obtiene una sesión MCP (singleton).
  2. ``_load_tools()`` convierte todas las tools del MCP Server a
     objetos ``BaseTool`` de LangChain vía ``load_mcp_tools()``.
  3. Cada función pública (``query_incident_by_id``, ``list_products``,
     etc.) busca la tool en caché por nombre y la invoca con
     ``tool.ainvoke(arguments)``.
  4. El resultado normalizado vuelve al grafo con la misma firma que
     antes, para que los nodos del grafo no requieran cambios.

Ventajas de langchain-mcp-adapters:
  - Conversión automática de contenidos MCP (TextContent, ImageContent…).
  - Cadena de interceptores (tool_interceptors) para logging, validación.
  - Manejo de errores MCP (``isError=True``) como ``ToolMessage``.
  - Integración nativa con ecosistema LangChain/LangGraph.

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
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool
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

_tools_cache: dict[str, BaseTool] | None = None
"""Caché de tools LangChain convertidas vía langchain-mcp-adapters."""


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
        )
        await _session.initialize()
        _session_initialized = True

        # Al crear/renovar la sesión, invalidar la caché de tools
        global _tools_cache
        _tools_cache = None

        logger.info("Sesión MCP inicializada correctamente.")
        return _session

    except Exception as exc:
        logger.error("Error al crear sesión MCP: %s", exc)
        _session = None
        _session_initialized = False
        raise


# ═══════════════════════════════════════════════════════════════════════
#  Tools vía langchain-mcp-adapters — caché lazy
# ═══════════════════════════════════════════════════════════════════════


async def _get_tool(tool_name: str) -> BaseTool | None:
    """Obtiene una tool LangChain del MCP Server por nombre.

    Usa ``langchain_mcp_adapters.tools.load_mcp_tools`` para convertir
    todas las tools del servidor a objetos ``BaseTool`` de LangChain,
    y las cachea en ``_tools_cache``.

    Si la sesión se recrea, la caché se invalida automáticamente
    (ver ``_ensure_session``).
    """
    global _tools_cache

    if _tools_cache is None:
        session = await _ensure_session()
        lc_tools = await load_mcp_tools(session=session)
        _tools_cache = {tool.name: tool for tool in lc_tools}
        logger.info(
            "Tools LangChain cargadas vía langchain-mcp-adapters: %s",
            list(_tools_cache.keys()),
        )

    return _tools_cache.get(tool_name)


async def _call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Llama a una tool del MCP Server vía langchain-mcp-adapters.

    Obtiene la tool desde la caché (cargada con ``load_mcp_tools``)
    y la invoca con ``tool.ainvoke(arguments)``.

    Args:
        tool_name: Nombre de la tool (ej. ``get_incident``, ``list_products``).
        arguments: Argumentos de la tool.

    Returns:
        Diccionario normalizado con el resultado o ``{"error": "..."}``.
    """
    tool = await _get_tool(tool_name)
    if tool is None:
        logger.error("Tool MCP '%s' no encontrada en el servidor.", tool_name)
        return {"error": f"MCP tool '{tool_name}' no encontrada en el servidor."}

    try:
        # tool.ainvoke() devuelve (content, artifact)
        # donde content es str | list | ToolMessage | Command
        result = await tool.ainvoke(arguments or {})
    except Exception as exc:
        logger.warning("Error invocando tool MCP '%s' via langchain-mcp-adapters: %s", tool_name, exc)
        return {"error": f"Error en tool MCP '{tool_name}': {exc}"}

    # Normalizar el resultado al formato que esperan los nodos del grafo
    return _normalize_tool_result(tool_name, result)


def _normalize_tool_result(tool_name: str, result: Any) -> dict[str, Any]:
    """Convierte el resultado de una tool LangChain al formato interno.

    ``tool.ainvoke()`` puede devolver:
      - ``str``               → texto plano
      - ``list``              → lista de bloques de contenido MCP
      - ``ToolMessage``       → mensaje con status="error" si falló
      - ``Command``           → comando (no usado en este contexto)

    El formato interno espera un diccionario con:
      - ``{"success": True, "data": ...}`` o
      - ``{"error": "mensaje"}``

    También intenta parsear resultados JSON.
    """
    if isinstance(result, tuple):
        # tool.ainvoke() devuelve (content, artifact)
        result = result[0]

    # ToolMessage con error
    if hasattr(result, "status") and getattr(result, "status", None) == "error":
        error_msg = getattr(result, "content", str(result))
        return {"error": str(error_msg)}

    # Texto plano
    if isinstance(result, str):
        # Intentar parsear como JSON
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"data": result}

    # Lista de bloques de contenido
    if isinstance(result, list):
        texts = []
        for block in result:
            if hasattr(block, "text"):
                texts.append(block.text)
            elif isinstance(block, str):
                texts.append(block)
        combined = "\n".join(texts)
        try:
            parsed = json.loads(combined)
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"data": combined}

    # Cualquier otra cosa
    return {"data": result}


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