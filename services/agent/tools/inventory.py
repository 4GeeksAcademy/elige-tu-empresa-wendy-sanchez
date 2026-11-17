"""⚠️  DEPRECATED — usar services.agent.tools.mcp_client en su lugar.

Este archivo se manteniene solo como referencia temporal.  Todo el código
nuevo debe importar las tools desde ``services.agent.tools.mcp_client``.

El agente LangGraph ya no usa este módulo.  Se eliminará en una limpieza
futura.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "services.agent.tools.inventory está DEPRECATED. "
    "Usa services.agent.tools.mcp_client en su lugar.",
    DeprecationWarning,
    stacklevel=2,
)

import logging
import os
from typing import Any

import httpx

from services.agent.tools import _get_service_url

logger = logging.getLogger(__name__)

# ── Timeout explícito ──────────────────────────────────────────────────
_INVENTORY_TIMEOUT_S = 5

# ── URL base ───────────────────────────────────────────────────────────
# Docker Compose expone el servicio en backend:8000.
_INVENTORY_BASE_URL = _get_service_url(
    env_var="INVENTORY_API_URL",
    default="http://backend:8000",
)


def _get_jwt_token() -> str:
    """Obtiene el JWT para autenticación backend-a-backend.

    Lee de variable de entorno AGENT_JWT_TOKEN. Si no está configurada,
    el servicio de inventario rechazará la consulta y la tool devolverá
    un error controlado.

    Nota: No se hardcodea ningún token. El operador o deployment debe
    proveerlo en el entorno.
    """
    token = os.getenv("AGENT_JWT_TOKEN")
    if not token:
        logger.warning(
            "AGENT_JWT_TOKEN no configurado. "
            "Las consultas a inventario fallarán con 401."
        )
    return token or ""


def _build_headers() -> dict[str, str]:
    """Construye headers HTTP incluyendo autenticación si está disponible."""
    token = _get_jwt_token()
    headers: dict[str, str] = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def query_product_by_id(product_id: int) -> dict[str, Any]:
    """Obtiene un producto de inventario por su ID.

    Args:
        product_id: ID del producto.

    Returns:
        Diccionario con datos del producto (nombre, SKU, categoría,
        stock actual, unidad), o un dict con ``{"error": "…"}`` si falla.
    """
    url = f"{_INVENTORY_BASE_URL}/inventory/products/{product_id}"
    logger.info("Consultando producto %s → GET %s", product_id, url)

    try:
        with httpx.Client(timeout=_INVENTORY_TIMEOUT_S) as client:
            resp = client.get(url, headers=_build_headers())
    except httpx.TimeoutException:
        logger.warning("Timeout al consultar producto %s (límite %ss)", product_id, _INVENTORY_TIMEOUT_S)
        return {"error": f"El servicio de inventario no respondió en {_INVENTORY_TIMEOUT_S}s. Intenta de nuevo más tarde."}
    except httpx.RequestError as exc:
        logger.warning("Error de conexión al consultar producto %s: %s", product_id, exc)
        return {"error": "No se pudo conectar con el servicio de inventario."}

    if resp.status_code == 401:
        return {"error": "Autenticación fallida: el token JWT no es válido o no está configurado."}

    if resp.status_code == 404:
        return {"error": f"No existe un producto con ID {product_id}."}

    if resp.status_code != 200:
        return {"error": f"El servicio de inventario respondió con código {resp.status_code}."}

    return _normalize_product(resp.json())


def query_products_list(
    category: str | None = None,
    name_search: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Lista productos con filtros opcionales.

    Args:
        category:    Filtrar por categoría.
        name_search: Buscar productos cuyo nombre contenga este texto.

    Returns:
        Lista de productos normalizados, o dict con ``{"error": "…"}``.
    """
    params = {}
    if category:
        params["category"] = category
    if name_search:
        params["name"] = name_search

    url = f"{_INVENTORY_BASE_URL}/inventory/products"
    logger.info("Listando productos con filtros %s → GET %s", params, url)

    try:
        with httpx.Client(timeout=_INVENTORY_TIMEOUT_S) as client:
            resp = client.get(url, params=params, headers=_build_headers())
    except httpx.TimeoutException:
        logger.warning("Timeout al listar productos (límite %ss)", _INVENTORY_TIMEOUT_S)
        return {"error": f"El servicio de inventario no respondió en {_INVENTORY_TIMEOUT_S}s."}
    except httpx.RequestError as exc:
        logger.warning("Error de conexión al listar productos: %s", exc)
        return {"error": "No se pudo conectar con el servicio de inventario."}

    if resp.status_code == 401:
        return {"error": "Autenticación fallida: el token JWT no es válido."}

    if resp.status_code != 200:
        return {"error": f"El servicio de inventario respondió con código {resp.status_code}."}

    products = resp.json()
    if not isinstance(products, list):
        return {"error": "El servicio devolvió un formato inesperado."}

    return [_normalize_product(p) for p in products]


def _normalize_product(prod: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un producto a un formato plano para la respuesta del agente."""
    return {
        "id": prod.get("id"),
        "name": prod.get("name"),
        "sku": prod.get("sku"),
        "category": prod.get("category"),
        "unit": prod.get("unit"),
        "current_stock": prod.get("current_stock"),
        "expiry_date": prod.get("expiry_date"),
        "country": prod.get("country"),
    }