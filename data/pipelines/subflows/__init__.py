"""Subflows del pipeline ``monthly_clinic_supply_performance``.

Vocabulario de dominio (alineado con CONTEXT.md):

- **supply_event_ingestion** → ingesta de eventos de insumos (resolución de
  periodo + extracción de eventos desde ``telemetry_events``).
- **supply_kpi_calculation** → cálculo de KPI de insumos (validación,
  deduplicación y agregación de los 4 KPI por clínica).
- **clinic_performance_publishing** → publicación de performance de clínicas
  (upsert idempotente, verificación y finalización de corrida).
- **clinic_kpi_snapshot** → snapshot opcional de KPI a JSON.
"""

from __future__ import annotations

from data.pipelines.subflows.supply_event_ingestion import subflow_supply_event_ingestion
from data.pipelines.subflows.supply_kpi_calculation import subflow_supply_kpi_calculation
from data.pipelines.subflows.clinic_performance_publishing import subflow_clinic_performance_publishing
from data.pipelines.subflows.clinic_kpi_snapshot import subflow_clinic_kpi_snapshot

__all__ = [
    "subflow_supply_event_ingestion",
    "subflow_supply_kpi_calculation",
    "subflow_clinic_performance_publishing",
    "subflow_clinic_kpi_snapshot",
]
