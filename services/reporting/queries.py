"""Consultas de reporting — funciones de datos para los endpoints.

Estas funciones son la interfaz estable entre la API y el pipeline.
Son importadas por los endpoints de ``services/reporting/routes/``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


def get_monthly_clinic_supply_performance(
    target_engine,
    month_start: date | str | None = None,
) -> list[dict]:
    """Consulta los KPI mensuales para el dashboard.

    Args:
        target_engine: Motor SQLAlchemy de la base de datos destino.
        month_start: Fecha del periodo (YYYY-MM-DD). Si es ``None``,
            devuelve el último periodo calculado disponible.

    Returns:
        Lista de filas con los KPI. Vacía si no hay datos.
    """
    if month_start is not None:
        if isinstance(month_start, str):
            month_start = datetime.strptime(month_start, "%Y-%m-%d").date()
        elif isinstance(month_start, datetime):
            month_start = month_start.date()

        stmt = sa_text("""
            SELECT clinic_id, country, month_start,
                   total_supply_cost, supply_consumption_count,
                   critical_stockout_count, expiry_risk_count,
                   currency, computed_at
            FROM reporting.monthly_clinic_supply_performance
            WHERE month_start = :month_start
            ORDER BY clinic_id
        """)
        params = {"month_start": month_start}
    else:
        stmt = sa_text("""
            SELECT DISTINCT ON (month_start)
                   clinic_id, country, month_start,
                   total_supply_cost, supply_consumption_count,
                   critical_stockout_count, expiry_risk_count,
                   currency, computed_at
            FROM reporting.monthly_clinic_supply_performance
            ORDER BY month_start DESC
        """)
        params = {}

    with target_engine.connect() as conn:
        rows = conn.execute(stmt, params).mappings().fetchall()

    result = []
    for row in rows:
        d = dict(row)
        # Convertir fechas a ISO string para serialización JSON
        for key in ("month_start", "computed_at"):
            if isinstance(d.get(key), (datetime, date)):
                d[key] = d[key].isoformat()
        # Decimal → float para JSON
        if "total_supply_cost" in d and hasattr(d["total_supply_cost"], "to_eng_string"):
            d["total_supply_cost"] = float(d["total_supply_cost"])
        result.append(d)

    logger.info("Consulta KPI: %s filas devueltas", len(result))
    return result