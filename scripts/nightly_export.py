"""Script nocturno de telemetría — export diario a CSV + lanzamiento del pipeline.

Proceso independiente de la API: corre vía cron/scheduler, en su propio hilo y
proceso. NO bloquea ningún endpoint de FastAPI.

Uso (ver background-processes.md para la expresión cron):
    python scripts/nightly_export.py                    # exporta "ayer" (UTC)
    TARGET_DATE=2026-10-20 python scripts/nightly_export.py   # pruebas
    python scripts/nightly_export.py --skip-pipeline    # solo export CSV
    python scripts/nightly_export.py --force            # re-ejecuta el día
    python scripts/nightly_export.py --dry-run          # no escribe nada

Criterios de aceptación que cumple:
  - Independiente de la API (proceso aparte, sin FastAPI).
  - Lock distribuido = el estado ``processing`` de job_runs: una segunda
    instancia aborta con código de salida 0.
  - Ningún registro queda en ``processing``: todo termina en completed/failed.
  - Idempotente por día: si se ejecuta dos veces sobre el mismo día, el
    resultado es el mismo (noop si ya estaba completed; el CSV es backup que
    solo se escribe si el archivo no existe).
  - Cada ejecución queda registrada con timestamp, estado y error_message.
  - Observabilidad (§6): logs INFO (inicio, fin, omisión por duplicado) y
    ERROR (excepciones); cada línea lleva timestamp, job y estado.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# ── Asegurar que la raíz del proyecto está en sys.path ────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.job_runner import (
    JOB_NAME_NIGHTLY_EXPORT,
    STATUS_COMPLETED,
    STATUS_FAILED,
    build_engine,
    ensure_schema,
    list_job_runs,
    log_result,
)
from services.nightly.nightly_service import (
    TARGET_DATE,
    default_export_dir,
    run_nightly,
    target_date_from_env,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nightly_export",
        description=(
            "Job nocturno de HealthCore: exporta telemetry_events de 'ayer' a "
            "CSV en data/raw/ y lanza el pipeline de datos como subprocess. "
            "Idempotente, con lock implicito (estado processing de job_runs)."
        ),
    )
    parser.add_argument("--skip-pipeline", action="store_true",
                        help="Solo exportar CSV, sin lanzar el pipeline.")
    parser.add_argument("--force", action="store_true",
                        help="Re-ejecutar aunque el día ya esté completed.")
    parser.add_argument("--target-date", type=str, default=None,
                        help="Día objetivo YYYY-MM-DD (equivale a TARGET_DATE).")
    parser.add_argument("--list", dest="list_runs", action="store_true",
                        help="Listar las últimas ejecuciones de job_runs.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostrar configuración y terminar sin ejecutar.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Si se pasa --target-date, reflejarlo en el entorno para el servicio.
    if args.target_date:
        os.environ[TARGET_DATE] = args.target_date

    target_date = target_date_from_env()
    engine = build_engine()
    ensure_schema(engine)

    if args.dry_run:
        print(json.dumps({
            "job_name": JOB_NAME_NIGHTLY_EXPORT,
            "target_date": str(target_date),
            "export_dir": str(default_export_dir()),
            "csv": f"telemetry_{target_date.isoformat()}.csv",
            "skip_pipeline": args.skip_pipeline,
            "force": args.force,
        }, indent=2))
        return 0

    if args.list_runs:
        for run in list_job_runs(engine, limit=20, job_name=JOB_NAME_NIGHTLY_EXPORT):
            print(json.dumps(run, ensure_ascii=False))
        return 0

    result = run_nightly(
        engine=engine,
        target_date=target_date,
        skip_pipeline=args.skip_pipeline,
        force=args.force,
    )

    # Log normalizado del resultado final del proceso (job + estado + ts).
    log_result(
        event="cli_finished",
        job=JOB_NAME_NIGHTLY_EXPORT,
        status=result["status"],
        outcome=result["outcome"],
        target_date=str(target_date),
        level=logging.ERROR if result["outcome"] == "failed" else logging.INFO,
        extra={"error": result.get("error_message", "")} if result["outcome"] == "failed" else None,
    )

    # Salida legible y JSON para pipelines/alertas.
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Un "aborted" es un éxito silencioso de coordinación (exit 0).
    if result["outcome"] in ("completed", "noop_export", "aborted"):
        return 0
    return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sys.exit(main())