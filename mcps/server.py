"""
mcps/server.py — MCP Server principal de HealthCore.

Punto de entrada del servidor MCP.  Construye la aplicación FastMCP con las
tools de incidentes e inventario, la protege con OAuth 2.1 vía MCP Auth
(mcpauth) y la sirve como aplicación ASGI (Streamable HTTP).

Uso:

  # Desde la raíz del monorepo (desarrollo local, sin auth)
  MCP_SKIP_AUTH=1 uv run uvicorn mcps.server:app --host 0.0.0.0 --port 9100

  # Producción (con OAuth)
  MCP_PUBLIC_URL=https://<tu-dominio> \
  MCP_JWKS_URI=https://<idp>/.well-known/jwks.json \
  uv run uvicorn mcps.server:app --host 0.0.0.0 --port 9100

  # Desde CLI de MCP (modo stdio, para pruebas locales con el agente)
  uv run python -m mcps.server --transport stdio
"""

from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcps import config
from mcps.tools import (
    create_incident as _create_incident,
    get_incident as _get_incident,
    list_incidents as _list_incidents,
    update_incident_status as _update_incident_status,
    get_summary as _get_summary,
    get_product as _get_product,
    list_products as _list_products,
    create_product as _create_product,
    update_product as _update_product,
    delete_product as _delete_product,
)

logger = logging.getLogger(__name__)

# ── Atajo para desarrollo local: cargar .env si existe ──────────────
_env_file = config.ENV_FILE
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file, override=False)
        logger.info("Cargado .env desde %s", _env_file)
    except ImportError:
        pass  # python-dotenv no instalado, se ignoran .env

# ═══════════════════════════════════════════════════════════════════════
#  FastMCP — definición del servidor
# ═══════════════════════════════════════════════════════════════════════

mcp = FastMCP(
    name=config.SERVER_NAME,
    instructions=config.SERVER_DESCRIPTION,
    dependencies=["httpx"],
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
    # El auth se aplica externamente con mcpauth (no la auth interna de FastMCP).
    # La auth interna de FastMCP es opcional/experimental; nosotros usamos la
    # capa de mcpauth que es la implementación de referencia de MCP Auth.
    # auth=None, auth_server_provider=None, token_verifier=None es el default.
)


# ═══════════════════════════════════════════════════════════════════════
#  Tools — Incidents (lectura + escritura)
# ═══════════════════════════════════════════════════════════════════════
#
# Cada tool expone scopes requeridos que el middleware de mcpauth validará.
# La herramienta ``update_incident_status`` usa el endpoint de ciclo de vida
# del Incidents Manager (PATCH /api/incidents/{id}/status).


@mcp.tool(
    name="create_incident",
    description="Crea un nuevo incidente en HealthCore. Requiere scope incidents.write.",
)
def create_incident(
    title: str,
    description: str,
    category: str,
    origin: str,
    branch: str,
    reported_by: str | None = None,
) -> str:
    """Crea un nuevo incidente.

    Args:
        title: Título corto del incidente.
        description: Descripción detallada.
        category: Categoría del incidente. Valores válidos:
                  clinical_equipment, it_system, billing_error,
                  compliance_breach, patient_experience, staff_issue,
                  facility_issue, referral_issue, other.
        origin: Origen del incidente. Valores válidos: customer, branch, internal.
        branch: Sucursal. Valores válidos: central, austin_north, dallas_uptown,
                houston_med_center, san_antonio_west, miami_brickell, miami_doral,
                orlando_east, tampa_bay, atlanta_midtown, savannah, london_city,
                london_west, manchester_central.
        reported_by: Quién reporta el incidente (opcional).

    Returns:
        El incidente creado como JSON.
    """
    result = _create_incident(
        title=title,
        description=description,
        category=category,
        origin=origin,
        branch=branch,
        reported_by=reported_by,
    )
    return _serialize_result(result, label="incidente creado")


@mcp.tool(
    name="get_incident",
    description="Obtiene un incidente por su ID (número de ticket). Requiere scope incidents.read.",
)
def get_incident(ticket_id: int) -> str:
    """Obtiene un incidente por su ID.

    Args:
        ticket_id: Número de ticket del incidente.

    Returns:
        Datos completos del incidente como JSON.
    """
    result = _get_incident(ticket_id)
    return _serialize_result(result, label="incidente")


@mcp.tool(
    name="list_incidents",
    description="Lista incidentes con filtros opcionales por estado, categoría, origen y sucursal. Requiere scope incidents.read.",
)
def list_incidents(
    status: str | None = None,
    category: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """Lista incidentes con filtros opcionales.

    Args:
        status: Filtrar por estado (open, in_progress, resolved, discarded).
        category: Filtrar por categoría.
        origin: Filtrar por origen (customer, branch, internal).
        branch: Filtrar por sucursal.
        limit: Máximo de resultados (default 20).
        offset: Desplazamiento (default 0).

    Returns:
        Lista de incidentes como JSON.
    """
    result = _list_incidents(
        status=status,
        category=category,
        origin=origin,
        branch=branch,
        limit=limit,
        offset=offset,
    )
    return _serialize_result(result, label="incidentes")


@mcp.tool(
    name="update_incident_status",
    description="""Actualiza el estado de un incidente usando el endpoint de ciclo de vida.

Transiciones válidas:
  open → in_progress | discarded
  in_progress → resolved | discarded
  resolved → (final, no se puede cambiar)
  discarded → (final, no se puede cambiar)

Requiere scope incidents.write.""",
)
def update_incident_status(
    ticket_id: int,
    status: str,
    comment: str | None = None,
) -> str:
    """Actualiza el estado de un incidente.

    Usa el endpoint específico PATCH /api/incidents/{id}/status del Incidents Manager,
    NO un PATCH genérico sobre el recurso.

    Args:
        ticket_id: Número de ticket del incidente.
        status: Nuevo estado. Valores: in_progress, resolved, discarded.
        comment: Comentario opcional sobre el cambio de estado.

    Returns:
        El incidente actualizado como JSON.
    """
    result = _update_incident_status(
        ticket_id=ticket_id,
        status=status,
        comment=comment,
    )
    return _serialize_result(result, label="estado actualizado")


@mcp.tool(
    name="get_incident_summary",
    description="Obtiene un resumen estadístico de todos los incidentes. Requiere scope incidents.read.",
)
def get_incident_summary() -> str:
    """Obtiene el resumen estadístico de incidentes (conteos por estado, categoría, origen, sucursal).

    Returns:
        Resumen como JSON.
    """
    result = _get_summary()
    return _serialize_result(result, label="resumen")


# ═══════════════════════════════════════════════════════════════════════
#  Tools — Inventory (SOLO LECTURA)
# ═══════════════════════════════════════════════════════════════════════
#
# El servidor rechaza explícitamente cualquier intento de crear, actualizar
# o eliminar productos.  Las tools de escritura EXISTEN y son descubribles,
# pero devuelven un error controlado (RETO 2 del ticket).
# Todas las tools de inventario (lectura) requieren scope inventory.read.


@mcp.tool(
    name="get_product",
    description="Obtiene un producto del inventario por su ID. Solo lectura. Requiere scope inventory.read.",
)
def get_product(product_id: int) -> str:
    """Obtiene un producto del inventario por su ID.

    Args:
        product_id: ID del producto.

    Returns:
        Datos del producto como JSON (nombre, SKU, categoría, stock, unidad).
    """
    result = _get_product(product_id)
    return _serialize_result(result, label="producto")


@mcp.tool(
    name="list_products",
    description="Lista productos del inventario con filtros opcionales. Solo lectura. Requiere scope inventory.read.",
)
def list_products(
    category: str | None = None,
    name_search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """Lista productos del inventario.

    Args:
        category: Filtrar por categoría (equipment, medication, supply, instrument).
        name_search: Búsqueda por nombre parcial.
        limit: Máximo de resultados (default 20).
        offset: Desplazamiento (default 0).

    Returns:
        Lista de productos como JSON.
    """
    result = _list_products(
        category=category,
        name_search=name_search,
        limit=limit,
        offset=offset,
    )
    return _serialize_result(result, label="productos")


@mcp.tool(
    name="create_product",
    description="""INTENCIONALMENTE RECHAZADA — El inventario es SOLO LECTURA.

Esta tool existe para que el cliente MCP reciba un error controlado
en lugar de "tool not found".  Siempre devuelve un error indicando
que el inventario es solo lectura.  Requiere scope inventory.write.""",
)
def create_product(
    name: str,
    category: str,
    unit: str,
    stock: int = 0,
    sku: str | None = None,
) -> str:
    """Crea un nuevo producto en el inventario.

    IMPORTANTE: El inventario es SOLO LECTURA — esta operación siempre
    es rechazada.  La tool existe para dar un mensaje de error claro
    en lugar de "tool not found".

    Args:
        name: Nombre del producto.
        category: Categoría (equipment, medication, supply, instrument).
        unit: Unidad de medida.
        stock: Stock inicial (opcional, default 0).
        sku: Código SKU (opcional).

    Returns:
        Siempre un error indicando que el inventario es solo lectura.
    """
    result = _create_product(
        name=name,
        category=category,
        unit=unit,
        stock=stock,
        sku=sku,
    )
    return _serialize_result(result, label="create_product (read-only)")


@mcp.tool(
    name="update_product",
    description="""INTENCIONALMENTE RECHAZADA — El inventario es SOLO LECTURA.

Esta tool existe para que el cliente MCP reciba un error controlado
en lugar de "tool not found".  Siempre devuelve un error indicando
que el inventario es solo lectura.  Requiere scope inventory.write.""",
)
def update_product(
    product_id: int,
    name: str | None = None,
    category: str | None = None,
    unit: str | None = None,
    stock: int | None = None,
) -> str:
    """Actualiza un producto existente en el inventario.

    IMPORTANTE: El inventario es SOLO LECTURA — esta operación siempre
    es rechazada.  La tool existe para dar un mensaje de error claro
    en lugar de "tool not found".

    Args:
        product_id: ID del producto a modificar.
        name: Nuevo nombre (opcional).
        category: Nueva categoría (opcional).
        unit: Nueva unidad de medida (opcional).
        stock: Nuevo stock (opcional).

    Returns:
        Siempre un error indicando que el inventario es solo lectura.
    """
    result = _update_product(
        product_id=product_id,
        name=name,
        category=category,
        unit=unit,
        stock=stock,
    )
    return _serialize_result(result, label="update_product (read-only)")


@mcp.tool(
    name="delete_product",
    description="""INTENCIONALMENTE RECHAZADA — El inventario es SOLO LECTURA.

Esta tool existe para que el cliente MCP reciba un error controlado
en lugar de "tool not found".  Siempre devuelve un error indicando
que el inventario es solo lectura.  Requiere scope inventory.write.""",
)
def delete_product(product_id: int) -> str:
    """Elimina un producto del inventario.

    IMPORTANTE: El inventario es SOLO LECTURA — esta operación siempre
    es rechazada.  La tool existe para dar un mensaje de error claro
    en lugar de "tool not found".

    Args:
        product_id: ID del producto a eliminar.

    Returns:
        Siempre un error indicando que el inventario es solo lectura.
    """
    result = _delete_product(product_id=product_id)
    return _serialize_result(result, label="delete_product (read-only)")


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _serialize_result(result: dict, label: str = "resultado") -> str:
    """Serializa el resultado de una tool a JSON para el cliente MCP.

    Registra un log por cada invocación con tool, resultado y estado.
    """
    import json

    if result.get("success"):
        logger.info(
            "Tool OK | tool=%(label)s | success=true",
            {"label": label},
        )
        return json.dumps(result, ensure_ascii=False, default=str)
    else:
        error_msg = result.get("error", "Error desconocido")
        logger.warning(
            "Tool ERROR | tool=%(label)s | success=false | error=%(error)s",
            {"label": label, "error": error_msg[:120]},
        )
        return json.dumps(
            {"error": error_msg, "success": False},
            ensure_ascii=False,
        )


# ═══════════════════════════════════════════════════════════════════════
#  ASGI app (Streamable HTTP) + OAuth middleware (modo Resource Server)
# ═══════════════════════════════════════════════════════════════════════
#
# El MCP Server actúa como **Resource Server** (RS) de OAuth 2.1:
#   - NO publica metadata de Authorization Server (eso lo hace el AS).
#   - Publica Protected Resource Metadata (RFC 9728) en
#     ``/.well-known/oauth-protected-resource`` indicando qué AS pueden
#     emitir tokens para este RS y qué scopes soporta.
#   - Valida tokens Bearer JWT entrantes via mcpauth (middleware), sin
#     tocar la auth interna de FastMCP.
#
# Referencias:
#   - MCP Auth spec (modo Resource Server):
#     https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/authorization/
#   - RFC 9728 (OAuth 2.0 Protected Resource Metadata):
#     https://www.rfc-editor.org/rfc/rfc9728
#   - mcpauth: https://pypi.org/project/mcpauth/
#
# Si MCP_SKIP_AUTH=1, se omite toda la capa OAuth (solo desarrollo local).

SKIP_AUTH = os.getenv("MCP_SKIP_AUTH", "").strip() in ("1", "true", "yes")

if SKIP_AUTH:
    # Modo desarrollo: app sin auth
    raw_app = mcp.streamable_http_app()
    logger.warning("MCP Server ejecutándose SIN autenticación (solo desarrollo).")
else:
    # ── Modo producción: aplicar OAuth vía mcpauth (modo RS) ─────────
    from mcpauth import MCPAuth
    from mcps.auth import (
        CORSAsgiMiddleware,
        build_auth_server_config,
        build_bearer_middleware,
        build_protected_resource_routes,
        SelectiveBearerASGI,
    )

    # ── 1. Construir config del Authorization Server remoto ──────────
    auth_server_config = build_auth_server_config()
    mcp_auth = MCPAuth(server=auth_server_config)

    # ── 2. Crear middleware Bearer Auth (mcpauth) ────────────────────
    bearer_mw_class = build_bearer_middleware(mcp_auth)

    # ── 3. Obtener la app Streamable HTTP de FastMCP ─────────────────
    raw_app = mcp.streamable_http_app()

    # ── 4. Agregar rutas públicas de Protected Resource Metadata ─────
    #     Se agregan directamente al FastMCP app (sin auth).
    for route in build_protected_resource_routes():
        raw_app.add_route(
            path=route.path,
            route=route.endpoint,
            methods=route.methods,
        )

    # ── 5. Envolver con ASGI selectivo: público directo,              ──
    #       protegido pasa por Bearer Auth.  El lifespan del FastMCP
    #       se preserva porque seguimos siendo una sola capa ASGI.
    raw_app = SelectiveBearerASGI(
        mcp_asgi_app=raw_app,
        bearer_mw_class=bearer_mw_class,
    )

    logger.info(
        "MCP Server configurado como Resource Server. "
        "Scopes soportados: %s",
        config.MCP_SCOPES_SUPPORTED,
    )

# ── 6. Envolver con CORS (necesario para MCP Playground web) ────────
from mcps.auth import CORSAsgiMiddleware
app = CORSAsgiMiddleware(raw_app)


# ═══════════════════════════════════════════════════════════════════════
#  CLI entry point
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    """Punto de entrada para ejecutar el servidor vía CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="HealthCore MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=config.MCP_TRANSPORT,
        help="Transporte del servidor MCP (default: %(default)s)",
    )
    parser.add_argument("--host", default=config.MCP_HOST, help="Host de escucha")
    parser.add_argument("--port", type=int, default=config.MCP_PORT, help="Puerto")
    parser.add_argument("--skip-auth", action="store_true", help="Deshabilitar OAuth")

    args = parser.parse_args()

    if args.skip_auth:
        os.environ["MCP_SKIP_AUTH"] = "1"

    if args.transport == "stdio":
        logger.info("Iniciando MCP Server en modo stdio...")
        mcp.run(transport="stdio")
    else:
        logger.info("Iniciando MCP Server en %s:%d (streamable-http)...", args.host, args.port)
        import uvicorn

        uvicorn.run(
            "mcps.server:app",
            host=args.host,
            port=args.port,
            reload=bool(os.getenv("MCP_RELOAD", "")),
        )


if __name__ == "__main__":
    main()