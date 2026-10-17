"""Task de carga — upsert idempotente en ``reporting.monthly_clinic_supply_performance``.

La idempotencia se apoya en el constraint ``UNIQUE (clinic_id, month_start)``
de la tabla de destino. El upsert reemplaza completamente los valores
agregados del periodo; no suma incrementalmente.
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


def upsert_monthly_kpis(
    target_engine,
    kpi_rows: list[dict],
    month_start: date | datetime,
) -> tuple[int, int]:
    """Inserta o actualiza las filas de KPI para un periodo mensual.

    La operación es **idempotente**: ejecutarla N veces sobre el mismo
    ``month_start`` produce exactamente el mismo estado final en la tabla.

    Estrategia: ``INSERT ... ON CONFLICT (clinic_id, month_start) DO UPDATE``.
    En cada ejecución se reemplazan los valores agregados y se actualiza
    ``computed_at``. **No se suman** los valores nuevos a los existentes.

    Args:
        target_engine: Motor SQLAlchemy con permisos de escritura.
        kpi_rows: Lista de dicts con los KPI por clínica.
        month_start: Periodo al que pertenecen los datos.

    Returns:
        (rows_inserted, rows_updated).
    """
    if isinstance(month_start, datetime):
        month_start = month_start.date()

    rows_inserted = 0
    rows_updated = 0
    now = datetime.utcnow()

    upsert_stmt = sa_text("""
        INSERT INTO reporting.monthly_clinic_supply_performance
            (clinic_id, country, month_start,
             total_supply_cost, supply_consumption_count,
             critical_stockout_count, expiry_risk_count,
             currency, computed_at)
        VALUES
            (:clinic_id, :country, :month_start,
             :total_supply_cost, :supply_consumption_count,
             :critical_stockout_count, :expiry_risk_count,
             :currency, :computed_at)
        ON CONFLICT (clinic_id, month_start) DO UPDATE
        SET
            total_supply_cost       = EXCLUDED.total_supply_cost,
            supply_consumption_count = EXCLUDED.supply_consumption_count,
            critical_stockout_count = EXCLUDED.critical_stockout_count,
            expiry_risk_count       = EXCLUDED.expiry_risk_count,
            currency                = EXCLUDED.currency,
            computed_at             = EXCLUDED.computed_at
    """)

    with target_engine.begin() as conn:
        for row in kpi_rows:
            params = {
                "clinic_id": row["clinic_id"],
                "country": row["country"],
                "month_start": month_start,
                "total_supply_cost": float(row.get("total_supply_cost", 0)),
                "supply_consumption_count": int(row.get("supply_consumption_count", 0)),
                "critical_stockout_count": int(row.get("critical_stockout_count", 0)),
                "expiry_risk_count": int(row.get("expiry_risk_count", 0)),
                "currency": row.get("currency", "USD"),
                "computed_at": now,
            }
            result = conn.execute(upsert_stmt, params)
            if result.rowcount == 1:
                # PostgreSQL reporta 1 fila afectada para INSERT
                rows_inserted += 1
            elif result.rowcount == 2:
                # PostgreSQL reporta 2 filas para UPDATE en ON CONFLICT
                rows_updated += 1

    logger.info(
        "Upsert completado: %d insertadas, %d actualizadas para %s",
        rows_inserted,
        rows_updated,
        month_start,
    )
    return rows_inserted, rows_updated