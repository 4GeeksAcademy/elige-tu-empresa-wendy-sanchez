"""Tools externas para el agente de soporte LangGraph.

Este paquete permite al agente consultar datos operativos en tiempo real
a través del **MCP Server** (NO mediante HTTP directo a los servicios):

  - ``mcp_client`` → Cliente MCP que se comunica con el MCP Server vía
    Streamable HTTP, usando **langchain-mcp-adapters** para convertir
    tools MCP a objetos ``BaseTool`` de LangChain.
  - ``incidents``  → (DEPRECATED) Archivo legacy que será eliminado.
  - ``inventory``  → (DEPRECATED) Archivo legacy que será eliminado.

Toda interacción con Incidents Manager e Inventory pasa por el MCP
Server como cliente MCP, no por HTTP directo.
"""

from __future__ import annotations

import os


def _get_service_url(env_var: str, default: str) -> str:
    """Resuelve la URL base de un servicio desde variable de entorno.

    En Docker Compose la URL es el nombre del contenedor (ej. incidents-backend).
    En desarrollo local sin Docker la url sería localhost con el puerto mapeado.

    La variable de entorno permite sobreescribir sin modificar código,
    útil para tests que mockean el servicio.
    """
    return os.getenv(env_var, default)