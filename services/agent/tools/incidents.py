"""Tool para consultar el gestor de incidentes en tiempo real.

Contrato:
  - Entrada: ticket_id (int, opcional) o filtros de búsqueda.
  - Salida: estado, categoría, origen, fechas, branch — exactamente
    los campos que expone GET /api/incidents y GET /api/incidents/{id}.

Timeout: 5s. Fallback: si el servicio no responde o el ticket no existe,
el agente responde con honestidad.

Solo lectura: GET únicamente. Nunca crea, actualiza ni elimina tickets.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from services.agent.tools import _get_service_url

logger = logging.getLogger(__name__)

# ── Timeout explícito: si el servicio de incidentes no responde en 5s,
#    el grafo no se cuelga. 5s es suficiente para una consulta a TinyDB
#    local; en una configuración cloud podría necesitarse 10s.
_INCIDENTS_TIMEOUT_S = 5

# ── URL base del servicio de incidentes ───────────────────────────────
# Docker Compose expone el servicio en incidents-backend:8010.
# El valor se lee de entorno con fallback al nombre Docker.
_INCIDENTS_BASE_URL = _get_service_url(
    env_var="INCIDENTS_API_URL",
    default="http://incidents-backend:8010",
)


def query_incident_by_id(ticket_id: int) -> dict[str, Any]:
    """Obtiene un incidente por su ID.

    Args:
        ticket_id: Número de ticket (ID entero).

    Returns:
        Diccionario con los campos del incidente, o un dict con
        ``{"error": "…"}`` si falla o no existe.
    """
    url = f"{_INCIDENTS_BASE_URL}/api/incidents/{ticket_id}"
    logger.info("Consultando incidente %s → GET %s", ticket_id, url)

    try:
        with httpx.Client(timeout=_INCIDENTS_TIMEOUT_S) as client:
            resp = client.get(url)
    except httpx.TimeoutException:
        logger.warning("Timeout al consultar incidente %s (límite %ss)", ticket_id, _INCIDENTS_TIMEOUT_S)
        return {"error": f"El servicio de incidentes no respondió en {_INCIDENTS_TIMEOUT_S}s. Intenta de nuevo más tarde."}
    except httpx.RequestError as exc:
        logger.warning("Error de conexión al consultar incidente %s: %s", ticket_id, exc)
        return {"error": "No se pudo conectar con el servicio de incidentes. Verifica que esté disponible."}

    if resp.status_code == 404:
        logger.info("Incidente %s no encontrado", ticket_id)
        return {"error": f"No existe un ticket con ID {ticket_id}."}

    if resp.status_code != 200:
        logger.warning("Incidents API respondió %s para ticket %s", resp.status_code, ticket_id)
        return {"error": f"El servicio de incidentes respondió con código {resp.status_code}. Intenta de nuevo."}

    return _normalize_incident(resp.json())


def query_incidents_list(
    status: str | None = None,
    category: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Lista incidentes aplicando filtros opcionales.

    Args:
        status:   Filtrar por estado ("open", "in_progress", "resolved", "discarded").
        category: Filtrar por categoría.
        origin:   Filtrar por origen ("customer", "branch", "internal").
        branch:   Filtrar por sucursal.

    Returns:
        Lista de incidentes, o un dict con ``{"error": "…"}`` si falla.
    """
    params = {}
    if status:
        params["status"] = status
    if category:
        params["category"] = category
    if origin:
        params["origin"] = origin
    if branch:
        params["branch"] = branch

    url = f"{_INCIDENTS_BASE_URL}/api/incidents"
    logger.info("Listando incidentes con filtros %s → GET %s", params, url)

    try:
        with httpx.Client(timeout=_INCIDENTS_TIMEOUT_S) as client:
            resp = client.get(url, params=params)
    except httpx.TimeoutException:
        logger.warning("Timeout al listar incidentes (límite %ss)", _INCIDENTS_TIMEOUT_S)
        return {"error": f"El servicio de incidentes no respondió en {_INCIDENTS_TIMEOUT_S}s. Intenta de nuevo más tarde."}
    except httpx.RequestError as exc:
        logger.warning("Error de conexión al listar incidentes: %s", exc)
        return {"error": "No se pudo conectar con el servicio de incidentes."}

    if resp.status_code != 200:
        return {"error": f"El servicio de incidentes respondió con código {resp.status_code}."}

    incidents = resp.json()
    return [_normalize_incident(inc) for inc in incidents]


def _normalize_incident(inc: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un incidente a un formato plano para la respuesta del agente.

    Expone los campos más relevantes para soporte: ID, estado, categoría,
    origen, branch, fechas y título.
    """
    return {
        "id": inc.get("id"),
        "title": inc.get("title"),
        "status": inc.get("status"),
        "category": inc.get("category"),
        "origin": inc.get("origin"),
        "branch": inc.get("branch"),
        "branch_label": inc.get("branch_label", ""),
        "description_preview": (inc.get("description") or "")[:150],
        "created_at": inc.get("created_at"),
        "updated_at": inc.get("updated_at"),
    }