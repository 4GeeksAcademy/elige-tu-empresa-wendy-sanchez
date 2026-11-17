"""
mcps/auth.py — Helpers de autenticación OAuth 2.1 para el MCP Server.

El MCP Server actúa como **Resource Server** (RS) de OAuth 2.1, NO como
Authorization Server (AS).  Sus responsabilidades son:

1. Publicar Protected Resource Metadata (RFC 9728) en
   ``/.well-known/oauth-protected-resource`` para que los clientes sepan
   qué AS pueden emitir tokens válidos y qué scopes se requieren.

2. Validar tokens Bearer JWT en cada request usando el middleware de
   mcpauth (Bearer Auth).  El middleware verifica issuer, audience,
   scopes y firma contra la JWKS del AS emisor.

Referencias de la especificación MCP Auth (modo Resource Server):
  https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/authorization/

Principios:
  - Sin acoplamiento a un proveedor OIDC específico (agnóstico).
  - Scopes de mínimo privilegio: incidents.read, incidents.write, inventory.read.
  - El servidor rechaza tokens sin los scopes requeridos (403).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mcpauth import AuthServerConfig, MCPAuth
from mcpauth.config import AuthorizationServerMetadata, AuthServerType
from mcpauth.types import AuthInfo

from mcps import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  Construcción del AuthServerConfig (para mcpauth)
# ═══════════════════════════════════════════════════════════════════════
#
# mcpauth necesita saber qué AS emitió el token para validar issuer y
# jwks_uri.  Esto NO significa que seamos el AS; es la configuración del
# AS remoto que los clientes deben usar para obtener tokens.


def build_auth_server_config() -> AuthServerConfig:
    """Construye la configuración del AS remoto para mcpauth.

    La metadata describe el AS que emite tokens para este RS.  El RS
    la necesita para saber dónde validar los JWT (jwks_uri).

    Returns:
        AuthServerConfig lista para pasar a ``MCPAuth(server=...)``.
    """
    issuer = config.MCP_ISSUER
    jwks_uri = config.MCP_JWKS_URI.strip()

    metadata = AuthorizationServerMetadata(
        issuer=issuer,
        authorization_endpoint="",
        token_endpoint="",
        jwks_uri=jwks_uri or None,
        response_types_supported=["token"],
        grant_types_supported=["client_credentials"],
        token_endpoint_auth_methods_supported=["client_secret_basic"],
        scopes_supported=config.MCP_SCOPES_SUPPORTED,
    )

    return AuthServerConfig(
        metadata=metadata,
        type=AuthServerType.OAUTH,
    )


# ═══════════════════════════════════════════════════════════════════════
#  Middleware Bearer Auth
# ═══════════════════════════════════════════════════════════════════════


def _verify_dev_token(token: str) -> AuthInfo:
    """Validador de desarrollo: acepta solo un token fijo configurado.

    Útil para integración temprana cuando no hay un IDP disponible.
    NUNCA usar en producción.
    """
    from mcpauth.exceptions import (
        MCPAuthTokenVerificationException,
        MCPAuthTokenVerificationExceptionCode,
    )

    dev_token = os.getenv("MCP_DEV_TOKEN", "hc_dev_token_no_usar_en_produccion")

    if token != dev_token:
        raise MCPAuthTokenVerificationException(
            MCPAuthTokenVerificationExceptionCode.INVALID_TOKEN,
            cause=ValueError("Token de desarrollo inválido"),
        )

    return AuthInfo(
        token=token,
        issuer=config.MCP_ISSUER,
        scopes=config.MCP_SCOPES_SUPPORTED,
        subject="dev-agent",
        audience=None,
        claims={"sub": "dev-agent", "iss": config.MCP_ISSUER},
    )


def build_bearer_middleware(mcp_auth: MCPAuth) -> type:
    """Crea el middleware Bearer Auth de mcpauth para este servidor.

    Si ``MCP_JWKS_URI`` está configurado, usa validación JWT contra
    JWKS remota.  Si no, usa un validador de desarrollo con token fijo.

    Args:
        mcp_auth: Instancia de MCPAuth ya configurada.

    Returns:
        Clase middleware Starlette (``BaseHTTPMiddleware``) lista para
        aplicar sobre la app.
    """
    required_scopes: list[str] | None = None
    if config.MCP_REQUIRED_SCOPES:
        required_scopes = config.MCP_REQUIRED_SCOPES

    jwks_uri = config.MCP_JWKS_URI.strip()

    if jwks_uri:
        # ── Producción: validar JWT contra JWKS remota ──────────────
        bearer_mw = mcp_auth.bearer_auth_middleware(
            mode_or_verify="jwt",
            required_scopes=required_scopes,
            show_error_details=False,
        )
        logger.info("Bearer Auth configurado con JWKS URI: %s", jwks_uri)
    else:
        # ── Desarrollo: token fijo ──────────────────────────────────
        bearer_mw = mcp_auth.bearer_auth_middleware(
            mode_or_verify=_verify_dev_token,
            required_scopes=required_scopes,
            show_error_details=True,
        )
        logger.info(
            "Bearer Auth en modo DEV (token estático). "
            "Configura MCP_JWKS_URI para producción."
        )

    return bearer_mw


# ═══════════════════════════════════════════════════════════════════════
#  Protected Resource Metadata (RFC 9728)
# ═══════════════════════════════════════════════════════════════════════
#
# Publicamos la metadata en /.well-known/oauth-protected-resource para
# que los clientes MCP puedan descubrir:
#   - La URL de este resource server (resource)
#   - Los AS autorizados para emitir tokens (authorization_servers)
#   - Los scopes soportados (scopes_supported)
#
# Esto es parte del flujo de autorización de MCP: el cliente obtiene esta
# metadata, descubre qué AS debe usar, solicita un token con los scopes
# adecuados, y luego lo presenta al MCP Server.


def build_protected_resource_routes() -> list:
    """Construye las rutas de Protected Resource Metadata (RFC 9728).

    Returns:
        Lista de rutas Starlette para agregar a la aplicación.

    Uso:
        app = Starlette(routes=[
            *build_protected_resource_routes(),
            Mount("/", app=mcp_app),
        ])
    """
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    # Si no hay public URL, esta metadata no tiene sentido
    public_url = config.MCP_PUBLIC_URL
    if not public_url:
        logger.warning(
            "MCP_PUBLIC_URL no está configurado. "
            "La Protected Resource Metadata no se publicará."
        )
        return []

    # La URL canónica de este resource server
    resource_url = public_url.rstrip("/")

    # Los AS que pueden emitir tokens para este RS
    authorization_servers: list[str] = []
    if config.MCP_JWKS_URI:
        # Si tenemos JWKS URI, inferimos el AS desde ahí
        # (en OIDC, el JWKS URI suele ser {issuer}/.well-known/jwks.json)
        authorization_servers.append(config.MCP_ISSUER)
    else:
        # Sin JWKS configurada, no podemos anunciar un AS.
        # En desarrollo con token fijo, esto es aceptable.
        logger.warning(
            "No hay authorization_servers configurados. "
            "La Protected Resource Metadata se publicará con lista vacía."
        )

    metadata_payload: dict[str, Any] = {
        "resource": resource_url,
        "authorization_servers": authorization_servers,
        "scopes_supported": config.MCP_SCOPES_SUPPORTED,
        "bearer_methods_supported": ["header"],
    }

    async def protected_resource_metadata(request):
        """Sirve la Protected Resource Metadata (RFC 9728)."""
        if request.method == "OPTIONS":
            from starlette.responses import Response

            return Response(status_code=204)

        return JSONResponse(
            content=metadata_payload,
            media_type="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )

    return [
        Route(
            "/.well-known/oauth-protected-resource",
            endpoint=protected_resource_metadata,
            methods=["GET", "OPTIONS"],
        ),
    ]