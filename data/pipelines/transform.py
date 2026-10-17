"""Tasks de transformación — cálculo de los 4 KPI a partir de eventos extraídos.

Cada función recibe una lista de eventos (dicts) y devuelve agregados
por clínica y mes. Sigue el diseño de PIPELINE_DESIGN.md sección 3.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────


def _parse_cost(tags: dict) -> Decimal | None:
    """Extrae el coste monetario del evento ``inbound_order_created``.

    El campo ``cost`` es una extensión aditiva del payload (brecha
    identificada en el diseño). Si no está presente, se registra
    una advertencia y se devuelve ``None``.
    """
    cost_raw = tags.get("cost") or tags.get("total_cost")
    if cost_raw is None:
        return None
    try:
        return Decimal(str(cost_raw))
    except (ValueError, TypeError):
        logger.warning("Coste no convertible a Decimal: %r", cost_raw)
        return None


def _safe_int(val: Any) -> int:
    """Convierte a int de forma segura, devolviendo 0 si falla."""
    try:
        return int(val)
    except (ValueError, TypeError, OverflowError):
        return 0


# ── Validación de eventos ─────────────────────────────────────────────


def validate_event(event: dict) -> tuple[bool, str | None]:
    """Valida que un evento tenga los campos mínimos requeridos.

    Returns:
        (True, None) si es válido.
        (False, motivo) si es inválido.
    """
    tags = event.get("tags") or {}
    clinic_id = tags.get("clinic_id") or event.get("clinic_id")
    if not clinic_id:
        return False, "clinic_id es obligatorio"

    country = tags.get("country") or event.get("country")
    if not country:
        return False, "country es obligatorio"

    # Validar país conocido
    if country not in ("US", "UK"):
        return False, f"País desconocido: {country}"

    return True, None


def deduplicate_events(events: list[dict]) -> tuple[list[dict], int]:
    """Elimina duplicados por ``event_id``, conservando el primer ocurrencia.

    Returns:
        (lista deduplicada, número de duplicados eliminados).
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for ev in events:
        eid = ev.get("event_id")
        if eid in seen:
            continue
        seen.add(eid)
        unique.append(ev)
    return unique, len(events) - len(unique)


# ── Cálculo de KPI ────────────────────────────────────────────────────


def aggregate_kpis(
    events: list[dict],
    month_start: date,
) -> list[dict]:
    """Agrega los eventos en una fila de KPI por clínica y mes.

    Args:
        events: Eventos extraídos y validados.
        month_start: Primer día del mes (para la clave de agrupación).

    Returns:
        Lista de dicts, uno por clínica, con los 4 KPI calculados.
    """
    # Por si month_start viene como datetime
    if isinstance(month_start, datetime):
        month_start = month_start.date()

    # Agrupar por clinic_id
    kpis: dict[str, dict] = defaultdict(
        lambda: {
            "total_supply_cost": Decimal("0.00"),
            "supply_consumption_count": 0,
            "critical_stockout_count": 0,
            "expiry_risk_count": 0,
            "country": "US",  # se sobreescribe abajo
            "currency": "USD",
        }
    )

    for ev in events:
        tags = ev.get("tags") or {}
        clinic_id = (tags.get("clinic_id") or ev.get("clinic_id") or "unknown").strip()
        country = (tags.get("country") or ev.get("country") or "US").strip()
        event_type = ev.get("event_type", "")

        # Actualizar país y moneda (todos los eventos de una clínica deben
        # tener el mismo país; si no, se registra el del primer evento)
        if clinic_id not in kpis or kpis[clinic_id]["country"] == "US":
            kpis[clinic_id]["country"] = country
        kpis[clinic_id]["currency"] = "USD" if country == "US" else "GBP"

        if event_type == "inbound_order_created":
            cost = _parse_cost(tags)
            if cost is not None:
                kpis[clinic_id]["total_supply_cost"] += cost
            else:
                logger.warning(
                    "Evento %s sin coste válido — se omite del KPI de coste",
                    ev.get("event_id", "N/A"),
                )

        elif event_type == "outbound_order_created":
            kpis[clinic_id]["supply_consumption_count"] += 1

        elif event_type == "stock_threshold_triggered":
            kpis[clinic_id]["critical_stockout_count"] += 1

        elif event_type == "supply_expiry_flagged":
            kpis[clinic_id]["expiry_risk_count"] += 1

    # Convertir a lista plana
    result = []
    for clinic_id, values in kpis.items():
        result.append(
            {
                "clinic_id": clinic_id,
                "country": values["country"],
                "month_start": month_start,
                "total_supply_cost": values["total_supply_cost"],
                "supply_consumption_count": values["supply_consumption_count"],
                "critical_stockout_count": values["critical_stockout_count"],
                "expiry_risk_count": values["expiry_risk_count"],
                "currency": values["currency"],
            }
        )

    result.sort(key=lambda r: r["clinic_id"])
    logger.info("Agregados KPI para %d clínicas en %s", len(result), month_start)
    return result


# ── Validación de resultados ──────────────────────────────────────────


def verify_kpis(aggregated: list[dict]) -> list[str]:
    """Verifica que los KPI agregados sean coherentes.

    Returns:
        Lista de advertencias encontradas. Vacía si todo está bien.
    """
    warnings: list[str] = []
    for row in aggregated:
        if row["total_supply_cost"] < 0:
            warnings.append(
                f"Coste negativo para {row['clinic_id']}: {row['total_supply_cost']}"
            )
        if row["supply_consumption_count"] < 0:
            warnings.append(
                f"Consumo negativo para {row['clinic_id']}: {row['supply_consumption_count']}"
            )
        # Validar que la moneda sea coherente con el país
        if row["country"] == "US" and row["currency"] != "USD":
            warnings.append(
                f"Moneda incorrecta para clínica US {row['clinic_id']}: {row['currency']}"
            )
        elif row["country"] == "UK" and row["currency"] != "GBP":
            warnings.append(
                f"Moneda incorrecta para clínica UK {row['clinic_id']}: {row['currency']}"
            )
    return warnings