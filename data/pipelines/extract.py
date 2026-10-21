"""Tasks de extracción del pipeline — solo lectura sobre telemetry_events."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


# ── Eventos por periodo ───────────────────────────────────────────────


def extract_telemetry_events(
    source_engine,
    month_start: datetime,
    month_end: datetime,
) -> list[dict]:
    """Extrae todos los eventos de inventario del periodo desde ``telemetry_events``.

    Lee **solo los 4 tipos de evento** que necesita el pipeline:
    - ``inbound_order_created``
    - ``outbound_order_created``
    - ``stock_threshold_triggered``
    - ``supply_expiry_flagged``

    Cada fila devuelve las columnas relacionales más el JSONB ``tags``,
    que contiene las propiedades específicas del evento.

    Args:
        source_engine: Motor SQLAlchemy de solo lectura.
        month_start: Inicio del periodo (UTC, inclusivo).
        month_end: Fin del periodo (UTC, exclusivo).

    Returns:
        Lista de dicts con los eventos. Vacía si no hay eventos en el periodo.
    """
    query = sa_text("""
        SELECT
            event_id,
            timestamp,
            event_type,
            schema_version,
            request_id,
            tags
        FROM telemetry_events
        WHERE event_type IN (
              'inbound_order_created',
              'outbound_order_created',
              'stock_threshold_triggered',
              'supply_expiry_flagged'
        )
        AND timestamp >= :month_start
        AND timestamp <  :month_end
        ORDER BY timestamp ASC
    """)

    with source_engine.connect() as conn:
        rows = conn.execute(
            query,
            {
                "month_start": month_start,
                "month_end": month_end,
            },
        ).mappings().fetchall()

    # Convertir a dicts planos con tipos Python nativos
    result = []
    for row in rows:
        d = dict(row)
        # UUID → str
        if isinstance(d.get("event_id"), UUID):
            d["event_id"] = str(d["event_id"])
        # timestamp → ISO string
        if isinstance(d.get("timestamp"), datetime):
            d["timestamp"] = d["timestamp"].isoformat()
        result.append(d)

    logger.info(
        "Extraídos %d eventos de telemetry_events [%s, %s)",
        len(result),
        month_start.isoformat(),
        month_end.isoformat(),
    )
    return result


# ── Datos de contexto (clínicas) ──────────────────────────────────────


_CLINIC_COUNTRY_MAP: dict[str, str] = {
    # US clinics
    "us-tx-001": "US", "us-tx-002": "US",
    "us-tx-003": "US", "us-fl-001": "US",
    "us-fl-002": "US", "us-ga-001": "US",
    "us-tx-004": "US", "us-tx-005": "US",
    "us-tx-006": "US",
    # UK clinics
    "uk-lnd-001": "UK", "uk-lnd-002": "UK",
    "uk-mcr-001": "UK",
}

_CLINIC_CURRENCY_MAP: dict[str, str] = {
    "US": "USD",
    "UK": "GBP",
}


def get_country(clinic_id: str) -> str | None:
    """Resuelve el país de una clínica desde el mapeo autoritativo."""
    return _CLINIC_COUNTRY_MAP.get(clinic_id)


def get_currency(country: str) -> str:
    """Resuelve la moneda de un país."""
    return _CLINIC_CURRENCY_MAP.get(country, "USD")


def get_all_clinic_ids() -> list[str]:
    """Devuelve todos los IDs de clínica conocidos."""
    return list(_CLINIC_COUNTRY_MAP.keys())