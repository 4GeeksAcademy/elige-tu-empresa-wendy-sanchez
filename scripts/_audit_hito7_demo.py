"""Demo de auditoría del proceso de segundo plano — concurrencia, idempotencia,
fallo, export CSV.

Lanza DOS instancias reales del script CLI (scripts/nightly_export.py) al
mismo tiempo contra la misma BD SQLite compartida, forzando la carrera del
lock. Luego demuestra: idempotencia por target_date, fallo → failed, y
contenido del CSV exportado.

USO (desde la raíz del repo):
    .venv-nightly/bin/python scripts/_audit_hito7_demo.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services.job_runner import build_engine, ensure_schema, find_job_run, list_job_runs  # noqa: E402
from services.nightly.nightly_service import csv_path_for, default_export_dir  # noqa: E402
from sqlalchemy import text as sa_text  # noqa: E402

AUDIT_DIR = Path("/tmp/h7audit")
DB_URL = f"sqlite+pysqlite:////{AUDIT_DIR}/db.sqlite3"
RAW_DIR = Path("/tmp/h7audit/raw")
DAY = date(2026, 10, 20)
ENV = {
    "DATABASE_URL": DB_URL,
    "TARGET_DATE": DAY.isoformat(),
}


def seed():
    """Crea job_runs + telemetry_events con 3 eventos el día 2026-10-20."""
    import json as _json

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # Limpiar de corridas previas: BD sqlite + CSV sintético en data/raw.
    # (El export real escribe en default_export_dir() = data/raw del repo.)
    for f in AUDIT_DIR.glob("*.sqlite3"):
        f.unlink()
    for f in RAW_DIR.glob("telemetry_2026-10-20.csv"):
        f.unlink()
    repo_csv = csv_path_for(DAY, default_export_dir())
    if repo_csv.exists():
        repo_csv.unlink()

    eng = build_engine(DB_URL)
    ensure_schema(eng)
    with eng.begin() as conn:
        conn.execute(sa_text(
            "CREATE TABLE telemetry_events ("
            "id INTEGER PRIMARY KEY, timestamp TIMESTAMPTZ, "
            "event_type VARCHAR(64), tags TEXT)"
        ))
        rows = [
            ("2026-10-20 01:00:00+00", "auth_login_succeeded", _json.dumps({"page": "/login"})),
            ("2026-10-20 02:30:00+00", "api_latency_recorded", _json.dumps({"ms": 120})),
            ("2026-10-20 23:59:00+00", "auth_login_failed", _json.dumps({})),
        ]
        for ts, etype, tags in rows:
            conn.execute(
                sa_text("INSERT INTO telemetry_events (timestamp, event_type, tags) "
                        "VALUES (:ts, :et, :tags)"),
                {"ts": ts, "et": etype, "tags": tags},
            )
    eng.dispose()
    print(f"[seed] BD {DB_URL} lista; 3 eventos el {DAY.isoformat()}")


def cli(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [str(_ROOT / ".venv-nightly/bin/python"), "scripts/nightly_export.py", *args]
    env = dict(ENV) if env_extra is None else {**ENV, **env_extra}
    return subprocess.run(cmd, cwd=str(_ROOT), env=env, capture_output=True, text=True)


def show_bd(label: str) -> None:
    eng = build_engine(DB_URL)
    rows = list_job_runs(eng, limit=10, job_name="nightly_export")
    eng.dispose()
    print(f"[bd:{label}] filas job_runs:")
    for r in rows:
        print(f"  id={r.get('id')} status={r.get('status'):<10} target_date={r.get('target_date')} "
              f"rows={r.get('exported_rows')} csv={r.get('csv_path')} err={r.get('error_message')}")

def main() -> int:
    seed()

    # ── C3: DOS instancias simultáneas (carrera del lock) ──────────────
    print("\n=== C3: lanzar 2 instancias del CLI al mismo tiempo ===")
    proc_a = subprocess.Popen(
        cli_parts("--skip-pipeline"), env=env_of(), cwd=str(_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    proc_b = subprocess.Popen(
        cli_parts("--skip-pipeline"), env=env_of(), cwd=str(_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    out_a, err_a = proc_a.communicate(timeout=120)
    out_b, err_b = proc_b.communicate(timeout=120)
    a = json_loads(out_a) or {"outcome": "??", "status": "??"}
    b = json_loads(out_b) or {"outcome": "??", "status": "??"}
    print(f"instancia A -> {a}")
    print(f"instancia B -> {b}")
    outcomes = {a["outcome"], b["outcome"]}
    show_bd("C3")

    # Demostración determinista del lock: el demo toma el lock (processing)
    # y LANZA una nueva instancia CLI → debe abortar silenciosamente.
    print("\n=== C3b: lock ya tomado (processing) -> nueva instancia ABORTA ===")
    eng = build_engine(DB_URL)
    from services.job_runner import create_job_run, mark_processing  # noqa: F401
    # Asegurar fila pending para OTRO día y tomar su lock manualmente
    DAY_LOCK = date(2026, 10, 22)
    create_job_run(eng, "nightly_export", DAY_LOCK)
    assert mark_processing(eng, "nightly_export", DAY_LOCK) is True
    eng.dispose()
    r = cli("--skip-pipeline", env_extra={"TARGET_DATE": DAY_LOCK.isoformat()})
    res3b = json_loads(r.stdout)
    print(f"instancia lanzada con lock tomado -> {res3b} (esperado aborted)")
    show_bd("C3b")

    # ── C4: idempotencia (2.ª ejecución del mismo día) ─────────────────
    print("\n=== C4: ejecutar de nuevo el MISMO día (idempotencia) ===")
    r = cli("--skip-pipeline")
    res4 = json_loads(r.stdout)
    print(f"segunda ejecucion -> {res4}")
    show_bd("C4")

    # ── C6: CSV generado en data/raw con nombre y contenido ────────────
    print("\n=== C6: CSV en data/raw (nombre + datos) ===")
    eng = build_engine(DB_URL)
    run = find_job_run(eng, "nightly_export", DAY)
    eng.dispose()
    csv_path = Path(run["csv_path"])
    print(f"csv_path registrado en job_runs: {csv_path}")
    print(f"existe: {csv_path.exists()}")
    print(f"en data/raw del repo: {csv_path.parent == default_export_dir()}")
    print("contenido CSV:")
    print(csv_path.read_text(encoding="utf-8"))

    # ── C5: fallo → failed (no processing) ─────────────────────────────
    print("\n=== C5: forzar fallo en una nueva fecha → failed ===")
    DAY_BAD = date(2026, 10, 21)
    eng = build_engine(DB_URL)
    with eng.begin() as conn:
        # corromper: borrar la tabla telemetry_events para que export falle
        conn.execute(sa_text("DROP TABLE telemetry_events"))
    eng.dispose()
    r = cli("--skip-pipeline", env_extra={"TARGET_DATE": DAY_BAD.isoformat()})
    res5 = json_loads(r.stdout)
    print(f"ejecucion fallida -> {res5}")
    show_bd("C5")

    # Verificación explícita: la fila del fallo quedó en failed (no processing),
    # y FAILED-ROW actualizada. La fila 2026-10-22 sigue processing porque la
    # demo C3b la retiene DELIBERADAMENTE (lock manual).
    eng = build_engine(DB_URL)
    rows = list_job_runs(eng, limit=10, job_name="nightly_export")
    eng.dispose()
    failed_row = next(r for r in rows if r["target_date"] == DAY_BAD.isoformat())
    failed_row_count = 1 if failed_row["status"] == "failed" else 0
    print(f"fila del fallo ({DAY_BAD}) status = {failed_row['status']} (esperado failed)")

    # Guardar los resultados en variables dedicadas para el resumen
    results = {
        "C3_race": (a["outcome"], b["outcome"]),
        "C3b_lock_abort": res3b["outcome"],
        "C4_idempotency": res4["outcome"],
        "C5_failed": res5["outcome"],
        "C6_csv_exists": csv_path.exists(),
        "failed_rows_after_C5": failed_row_count,
    }

    print("\n=== RESUMEN ===")
    print(f"C3 concurrencia (A,B): {results['C3_race']} (una completa; la otra aborted|noop_export)")
    print(f"C3b lock tomado -> aborta: {results['C3b_lock_abort']} (esperado aborted)")
    print(f"C4 idempotencia: {results['C4_idempotency']} (esperado noop_export)")
    print(f"C5 fallo -> failed: {results['C5_failed']} (esperado failed)")
    print(f"filas failed tras C5: {results['failed_rows_after_C5']} (esperado 1)")
    print(f"C6 CSV existe = {results['C6_csv_exists']} en {csv_path.parent}")

    return 0


def cli_parts(*args: str):
    return [str(_ROOT / ".venv-nightly/bin/python"), "scripts/nightly_export.py", *args]


def env_of():
    import os
    e = dict(ENV)
    e["PYTHONPATH"] = str(_ROOT)
    return e


def json_loads(s: str) -> dict | None:
    import json as _json
    try:
        return _json.loads(s)
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())