"""Runner del pipeline — punto de entrada para la API y la línea de comandos.

Funciones:
- ``trigger_monthly_clinic_supply_performance(month_start)``: usada por
  ``POST /reporting/pipeline-runs`` para disparar el flow.
- ``main()``: CLI para ejecutar el pipeline desde la shell.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from typing import Any

from data.pipelines.database import get_target_engine
from data.pipelines.run_store import has_active_run_for_period

# Configurar logging ANTES de cualquier import del pipeline
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def trigger_monthly_clinic_supply_performance(
    month_start: str | date | datetime | None = None,
    trigger_source: str = "manual",
) -> dict[str, Any]:
    """Dispara el flow del pipeline y devuelve el resultado.

    Esta es la función que ``POST /reporting/pipeline-runs`` importa
    desde ``data.pipelines.runner``.

    Args:
        month_start: Primer día del mes (string ``YYYY-MM-DD``, ``date``
            o ``datetime``). Si es ``None`` se usa el mes anterior.
        trigger_source: ``scheduled``, ``manual`` o ``recalculation``.

    Returns:
        Dict con metadatos de la ejecución.
    """
    # Import tardío para evitar que Prefect se inicialice al cargar el módulo
    from data.pipelines.flows import monthly_clinic_supply_performance_flow

    logger.info(
        "Disparando pipeline: month_start=%s, trigger=%s",
        month_start,
        trigger_source,
    )

    # Verificar bloqueo de concurrencia: si ya hay una ejecución activa
    # para el mismo periodo, no iniciar una nueva.
    try:
        from data.pipelines.subflows.supply_event_ingestion import task_resolve_period
        resolved_start, resolved_end = task_resolve_period.fn(month_start)
        target_engine = get_target_engine()
        has_active, active_run_id = has_active_run_for_period(target_engine, resolved_start)
        if has_active:
            logger.warning(
                "Ejecución omitida por concurrencia: ya existe una ejecución activa "
                "(run_id=%s) para el periodo %s",
                active_run_id,
                resolved_start.date(),
            )
            return {
                "status": "already_running",
                "run_id": active_run_id,
                "month_start": resolved_start.isoformat(),
                "message": f"Ya existe una ejecución activa ({active_run_id}) para este periodo",
                "events_read": 0,
                "events_valid": 0,
                "events_rejected": 0,
                "events_deduplicated": 0,
                "rows_inserted": 0,
                "rows_updated": 0,
                "warning_count": 0,
                "error_message": None,
            }
    except Exception as exc:
        logger.warning("No se pudo verificar concurrencia (continuando): %s", exc)

    # El flow Prefect se ejecuta de forma síncrona aquí.
    # En producción, Prefect Server/Scheduler gestionaría esto.
    result = monthly_clinic_supply_performance_flow(
        month_start=month_start,
        trigger_source=trigger_source,
    )

    logger.info("Pipeline completado: %s", result.get("status"))
    return result


def main() -> None:
    """CLI del pipeline mensual de desempeño de insumos por clínica.

    Uso:
        python -m data.pipelines.runner --month 2025-01-01
        python -m data.pipelines.runner  # mes anterior
    """
    parser = argparse.ArgumentParser(
        description="HealthCore — Pipeline mensual de desempeño de insumos por clínica",
    )
    parser.add_argument(
        "--month",
        "-m",
        type=str,
        default=None,
        help="Primer día del mes a procesar (YYYY-MM-DD). Por defecto: mes anterior.",
    )
    parser.add_argument(
        "--trigger",
        "-t",
        type=str,
        default="manual",
        choices=["scheduled", "manual", "recalculation"],
        help="Origen del disparo. Por defecto: manual.",
    )
    parser.add_argument(
        "--init-schema",
        action="store_true",
        help="Inicializa el esquema reporting en la BD antes de ejecutar.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en formato JSON en lugar de texto plano.",
    )

    args = parser.parse_args()

    # Inicializar esquema si se solicita
    if args.init_schema:
        from data.pipelines.database import init_reporting_schema

        logger.info("Inicializando esquema reporting...")
        init_reporting_schema()

    # Ejecutar pipeline
    result = trigger_monthly_clinic_supply_performance(
        month_start=args.month,
        trigger_source=args.trigger,
    )

    if args.json:
        # Convertir tipos no serializables
        output = {}
        for k, v in result.items():
            if isinstance(v, datetime):
                output[k] = v.isoformat()
            elif isinstance(v, date):
                output[k] = v.isoformat()
            else:
                output[k] = v
        print(json.dumps(output, indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"Pipeline: monthly_clinic_supply_performance_flow")
        print(f"Estado:   {result.get('status')}")
        print(f"Mes:      {result.get('month_start')}")
        if result.get("error_message"):
            print(f"Error:    {result['error_message']}")
        print(f"\nContadores:")
        print(f"  Eventos leídos:         {result.get('events_read', 0)}")
        print(f"  Eventos válidos:        {result.get('events_valid', 0)}")
        print(f"  Eventos rechazados:     {result.get('events_rejected', 0)}")
        print(f"  Duplicados eliminados:  {result.get('events_deduplicated', 0)}")
        print(f"  Filas insertadas:       {result.get('rows_inserted', 0)}")
        print(f"  Filas actualizadas:     {result.get('rows_updated', 0)}")
        print(f"  Advertencias:           {result.get('warning_count', 0)}")
        print(f"  Run ID:                 {result.get('run_id')}")
        print(f"{'='*60}\n")

    # Código de salida según estado
    sys.exit(0 if result.get("status") == "completed" else 1)


if __name__ == "__main__":
    main()