"""Tools MCP para el Incidents Manager y módulo de inventario.

Cada tool se comunica con el servicio correspondiente vía HTTP.
Los nombres de campos, IDs de entidad y valores de dominio coinciden
exactamente con las APIs de incidencias e inventario ya construidas.

Incidents (lectura + escritura):
  - create_incident
  - get_incident
  - list_incidents
  - update_incident_status   (usa el endpoint de ciclo de vida)
  - get_summary

Inventory (solo lectura — el servidor rechaza cualquier modificación):
  - get_product
  - list_products
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

# ── Timeout general ──────────────────────────────────────────────────
_REQUEST_TIMEOUT_S = 10

# ── URLs base ────────────────────────────────────────────────────────
_INCIDENTS_BASE_URL = os.getenv(
    "INCIDENTS_API_URL", "http://incidents-backend:8010"
)
_INVENTORY_BASE_URL = os.getenv(
    "INVENTORY_API_URL", "http://backend:8000"
)


# ═══════════════════════════════════════════════════════════════════════
#  Cliente HTTP compartido
# ═══════════════════════════════════════════════════════════════════════


def _get_http_client() -> httpx.Client:
    """Devuelve un cliente HTTP con timeout y headers básicos."""
    return httpx.Client(timeout=_REQUEST_TIMEOUT_S)


# ═══════════════════════════════════════════════════════════════════════
#  Incidents
# ═══════════════════════════════════════════════════════════════════════


def _call_incidents(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Wrapper para llamadas a la API de incidentes.

    Returns:
        Diccionario con ``success``, ``data``/``error``.
    """
    url = f"{_INCIDENTS_BASE_URL}{path}"
    try:
        with _get_http_client() as client:
            resp = client.request(method, url, **kwargs)
        if resp.status_code >= 400:
            body = resp.json() if resp.text else {}
            detail = body.get("detail") or body.get("error") or resp.text
            return {"success": False, "error": f"HTTP {resp.status_code}: {detail}"}
        data = resp.json()
        return {"success": True, "data": data}
    except httpx.TimeoutException:
        return {"success": False, "error": "El servicio de incidentes no respondió (timeout)."}
    except httpx.RequestError as exc:
        return {"success": False, "error": f"Error de conexión con incidentes: {exc}"}
    except Exception as exc:
        return {"success": False, "error": f"Error inesperado: {exc}"}


def create_incident(
    title: str,
    description: str,
    category: str,
    origin: str,
    branch: str,
    reported_by: str | None = None,
) -> dict[str, Any]:
    """Crea un nuevo incidente en el Incidents Manager.

    Args:
        title: Título corto del incidente.
        description: Descripción detallada.
        category: Categoría (clinical_equipment, it_system, billing_error,
                  compliance_breach, patient_experience, staff_issue,
                  facility_issue, referral_issue, other).
        origin: Origen (customer, branch, internal).
        branch: Sucursal (central, austin_north, dallas_uptown,
                houston_med_center, san_antonio_west, miami_brickell,
                miami_doral, orlando_east, tampa_bay, atlanta_midtown,
                savannah, london_city, london_west, manchester_central).
        reported_by: Quién reporta (opcional).

    Returns:
        El incidente creado con su ID asignado.
    """
    payload: dict[str, Any] = {
        "title": title,
        "description": description,
        "category": category,
        "origin": origin,
        "branch": branch,
    }
    if reported_by:
        payload["reported_by"] = reported_by

    result = _call_incidents("POST", "/api/incidents", json=payload)
    if result["success"]:
        return {"success": True, "incident": result["data"]}
    return {"success": False, "error": result["error"]}


def get_incident(ticket_id: int) -> dict[str, Any]:
    """Obtiene un incidente por su ID.

    Args:
        ticket_id: Número de ticket.

    Returns:
        Datos completos del incidente.
    """
    result = _call_incidents("GET", f"/api/incidents/{ticket_id}")
    if result["success"]:
        return {"success": True, "incident": result["data"]}
    return {"success": False, "error": result["error"]}


def list_incidents(
    status: str | None = None,
    category: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista incidentes con filtros opcionales.

    Args:
        status: Filtrar por estado (open, in_progress, resolved, discarded).
        category: Filtrar por categoría.
        origin: Filtrar por origen.
        branch: Filtrar por sucursal.
        limit: Máximo de resultados (default 20).
        offset: Desplazamiento (default 0).

    Returns:
        Lista de incidentes y metadatos de paginación.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    if category:
        params["category"] = category
    if origin:
        params["origin"] = origin
    if branch:
        params["branch"] = branch

    result = _call_incidents("GET", "/api/incidents", params=params)
    if result["success"]:
        data = result["data"]
        # La API puede devolver directamente una lista o un dict con items
        if isinstance(data, dict):
            items = data.get("items", data.get("incidents", []))
            total = data.get("total", len(items))
        else:
            items = data
            total = len(items)
        return {"success": True, "incidents": items, "total": total}
    return {"success": False, "error": result["error"]}


def update_incident_status(
    ticket_id: int,
    status: str,
    comment: str | None = None,
) -> dict[str, Any]:
    """Actualiza el estado de un incidente usando el endpoint de ciclo de vida.

    Transiciones válidas:
      open → in_progress | discarded
      in_progress → resolved | discarded
      resolved → (final)
      discarded → (final)

    Args:
        ticket_id: Número de ticket.
        status: Nuevo estado (in_progress, resolved, discarded).
        comment: Comentario opcional sobre el cambio.

    Returns:
        El incidente actualizado.
    """
    payload: dict[str, Any] = {"status": status}
    if comment:
        payload["comment"] = comment

    # Usamos el endpoint específico de ciclo de vida, NO un PATCH genérico.
    result = _call_incidents(
        "PATCH", f"/api/incidents/{ticket_id}/status", json=payload
    )
    if result["success"]:
        return {"success": True, "incident": result["data"]}
    return {"success": False, "error": result["error"]}


def get_summary() -> dict[str, Any]:
    """Obtiene un resumen estadístico de todos los incidentes.

    Returns:
        Conteos por estado, categoría, origen, sucursal.
    """
    result = _call_incidents("GET", "/api/incidents/summary")
    if result["success"]:
        return {"success": True, "summary": result["data"]}
    return {"success": False, "error": result["error"]}


# ═══════════════════════════════════════════════════════════════════════
#  Inventory  (S O L O   L E C T U R A)
# ═══════════════════════════════════════════════════════════════════════

_INVENTORY_TIMEOUT_S = 5


def _get_jwt_token() -> str:
    """Obtiene el JWT para autenticación backend-a-backend."""
    token = os.getenv("AGENT_JWT_TOKEN", "")
    if not token:
        logger.warning(
            "AGENT_JWT_TOKEN no configurado. El inventario rechazará la consulta."
        )
    return token


def _call_inventory(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Wrapper para llamadas a la API de inventario (requiere JWT)."""
    url = f"{_INVENTORY_BASE_URL}{path}"
    token = _get_jwt_token()
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with httpx.Client(timeout=_INVENTORY_TIMEOUT_S) as client:
            resp = client.request(method, url, headers=headers, **kwargs)
        if resp.status_code >= 400:
            body = resp.json() if resp.text else {}
            detail = body.get("detail") or body.get("error") or resp.text
            return {"success": False, "error": f"HTTP {resp.status_code}: {detail}"}
        data = resp.json()
        return {"success": True, "data": data}
    except httpx.TimeoutException:
        return {"success": False, "error": "El servicio de inventario no respondió (timeout)."}
    except httpx.RequestError as exc:
        return {"success": False, "error": f"Error de conexión con inventario: {exc}"}
    except Exception as exc:
        return {"success": False, "error": f"Error inesperado: {exc}"}


def get_product(product_id: int) -> dict[str, Any]:
    """Obtiene un producto del inventario por su ID.

    Args:
        product_id: ID del producto.

    Returns:
        Datos completos del producto (nombre, SKU, categoría, stock, unidad).
    """
    result = _call_inventory("GET", f"/inventory/products/{product_id}")
    if result["success"]:
        return {"success": True, "product": result["data"]}
    return {"success": False, "error": result["error"]}


def list_products(
    category: str | None = None,
    name_search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista productos del inventario con filtros opcionales.

    Args:
        category: Filtrar por categoría (equipment, medication, supply, instrument).
        name_search: Búsqueda por nombre parcial.
        limit: Máximo de resultados (default 20).
        offset: Desplazamiento (default 0).

    Returns:
        Lista de productos.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if category:
        params["category"] = category
    if name_search:
        params["name_search"] = name_search

    result = _call_inventory("GET", "/inventory/products", params=params)
    if result["success"]:
        data = result["data"]
        if isinstance(data, dict):
            items = data.get("items", data.get("products", []))
            total = data.get("total", len(items))
        else:
            items = data
            total = len(items)
        return {"success": True, "products": items, "total": total}
    return {"success": False, "error": result["error"]}


# ═══════════════════════════════════════════════════════════════════════
#  Inventory — Tools de escritura (rechazo explícito)
# ═══════════════════════════════════════════════════════════════════════
#
# Estas tools EXISTEN y son descubribles por el cliente MCP, pero
# devuelven un error controlado indicando que el inventario es solo
# lectura.  El ticket (RETO 2) exige explícitamente que "no basta con
# 'no implementar' el endpoint de escritura, el servidor debe rechazar
# explícitamente cualquier intento de modificación."
#
# Esto evita que el agente o el cliente MCP reciban un "tool not found"
# y sigan intentando.  En su lugar, reciben un mensaje claro de por qué
# la operación no está permitida.


def create_product(**kwargs: Any) -> dict[str, Any]:
    """Crea un nuevo producto en el inventario.

    IMPORTANTE: El inventario es SOLO LECTURA — esta tool rechaza
    explícitamente cualquier intento de crear un producto.

    Returns:
        Siempre ``{"success": False, "error": "read_only"}`` con un
        mensaje explícito.
    """
    logger.warning("Intento de crear producto rechazado (inventario read-only). Args: %s", kwargs)
    return {
        "success": False,
        "error": "read_only",
        "message": (
            "El módulo de inventario es solo lectura. "
            "No se pueden crear, modificar ni eliminar productos a través "
            "de este MCP Server.  Para cambios en el inventario, utiliza "
            "el sistema de gestión de inventario directamente."
        ),
    }


def update_product(product_id: int, **kwargs: Any) -> dict[str, Any]:
    """Actualiza un producto existente en el inventario.

    IMPORTANTE: El inventario es SOLO LECTURA — esta tool rechaza
    explícitamente cualquier intento de modificar un producto.

    Args:
        product_id: ID del producto a modificar.

    Returns:
        Siempre ``{"success": False, "error": "read_only"}`` con un
        mensaje explícito.
    """
    logger.warning(
        "Intento de actualizar producto %s rechazado (inventario read-only). Args: %s",
        product_id, kwargs,
    )
    return {
        "success": False,
        "error": "read_only",
        "message": (
            "El módulo de inventario es solo lectura. "
            "No se pueden crear, modificar ni eliminar productos a través "
            "de este MCP Server.  Para cambios en el inventario, utiliza "
            "el sistema de gestión de inventario directamente."
        ),
    }


def delete_product(product_id: int) -> dict[str, Any]:
    """Elimina un producto del inventario.

    IMPORTANTE: El inventario es SOLO LECTURA — esta tool rechaza
    explícitamente cualquier intento de eliminar un producto.

    Args:
        product_id: ID del producto a eliminar.

    Returns:
        Siempre ``{"success": False, "error": "read_only"}`` con un
        mensaje explícito.
    """
    logger.warning(
        "Intento de eliminar producto %s rechazado (inventario read-only).",
        product_id,
    )
    return {
        "success": False,
        "error": "read_only",
        "message": (
            "El módulo de inventario es solo lectura. "
            "No se pueden crear, modificar ni eliminar productos a través "
            "de este MCP Server.  Para cambios en el inventario, utiliza "
            "el sistema de gestión de inventario directamente."
        ),
    }