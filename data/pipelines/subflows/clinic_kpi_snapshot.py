"""Subflow de snapshot de KPI por cl\u00ednica \u2014 exporta a JSON (opcional, no cr\u00edtico).

Este subflow se invoca con ``return_state=True`` desde el flujo principal
para que un fallo (p. ej. permisos de disco) no interrumpa el pipeline.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from prefect import flow, task
from prefect.logging import get_run_logger

logger = logging.getLogger(__name__)


# ── Task ─────────────────────────────────────────────────────────────


@task(
    name="snapshot_kpi_export",
)
def task_snapshot_kpi_export(
    kpi_rows: list[dict],
    month_start_dt: datetime,
) -> str:
    """Exporta un snapshot de los KPI de insumos a JSON en ``data/eval/``.

    Task **no cr\u00edtica**: si falla (permisos, espacio), el flujo principal
    contin\u00faa sin impacto.

    Returns:
        Ruta al archivo generado.
    """
    run_logger = get_run_logger()

    month_str = (
        month_start_dt.strftime("%Y-%m")
        if isinstance(month_start_dt, datetime)
        else str(month_start_dt)
    )
    eval_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    filename = f"kpi_snapshot_{month_str}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
    filepath = eval_dir / filename

    serializable = []
    for row in kpi_rows:
        r = dict(row)
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
        serializable.append(r)

    with open(filepath, "w") as f:
        json.dump(serializable, f, indent=2, default=str)

    run_logger.info("Snapshot exportado a %s", filepath)
    return str(filepath)


# ── Subflow ──────────────────────────────────────────────────────────


@flow(
    name="subflow_clinic_kpi_snapshot",
    log_prints=True,
)
def subflow_clinic_kpi_snapshot(
    kpi_rows: list[dict],
    month_start_dt: datetime,
) -> dict[str, Any]:
    """Subflow opcional: exporta snapshot de KPI de insumos a JSON.

    Se invoca con ``return_state=True`` desde el flujo principal.

    Args:
        kpi_rows: Filas de KPI agregadas.
        month_start_dt: L\u00edmite UTC del periodo.

    Returns:
        Diccionario con ``snapshot_path`` si se gener\u00f3, o ``skipped``.
    """
    run_logger = get_run_logger()

    if not kpi_rows:
        run_logger.info("Snapshot omitido: no hay filas de KPI.")
        return {"snapshot_path": None, "skipped": True}

    try:
        filepath = task_snapshot_kpi_export(kpi_rows, month_start_dt)
        return {"snapshot_path": filepath, "skipped": False}
    except Exception as exc:
        run_logger.warning("Snapshot fall\u00f3 (no cr\u00edtico): %s", exc)
        return {"snapshot_path": None, "skipped": True, "error": str(exc)}
