"""Tools externas para el agente de soporte LangGraph.

Este paquete contiene herramientas que permiten al agente consultar
datos operativos en tiempo real fuera de la base de conocimiento RAG:

  - ``incidents``  → Consulta el gestor de incidentes (GET /api/incidents).
  - ``inventory``  → Consulta el gestor de inventario (GET /inventory/products).

Ninguna tool escribe datos — solo lectura (GET).
Todas las tools tienen timeout explícito (5s) y ruta de fallback.
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