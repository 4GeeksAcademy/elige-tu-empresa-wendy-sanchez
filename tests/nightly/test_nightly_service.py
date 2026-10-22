"""Tests de la orquestación completa del job nocturno.

Cubre ``services/nightly/nightly_service.py``:

- La máquina de estados completa del script (pending → processing →
  completed/failed) cuando se ejecuta end-to-end.
- Idempotencia: una segunda ejecución sobre el mismo día NO re-exporta
  (outcome noop_export) si el día ya está completed.
- Aborto silencioso: si una instancia está en processing, la segunda instancia
  devuelve outcome "aborted" (nunca falla, no escribe secundariamente).
- Importante: se usa SQLite en memoria para el ESTADO (job_runs) y un motor
  SQLite separado que emula ``telemetry_events`` (tabla creada inline) para
  probar el export real a CSV.
"""

from __future__ import annotations

import csv
import io
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text as sa_text

# Asegurar que la raíz del proyecto está en sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.job_runner import (
    JOB_NAME_NIGHTLY_EXPORT,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    build_engine,
    create_job_run,
    ensure_schema,
    find_job_run,
    mark_processing,
)
from services.nightly.nightly_service import (
    csv_path_for,
    default_export_dir,
    export_telemetry_events,
    run_nightly,
)

DAY = date(2026, 10, 20)


@pytest.fixture()
def job_engine():
    """Engine SQLite en memoria para job_runs (estado del job)."""
    eng = build_engine("sqlite+pysqlite:///:memory:")
    ensure_schema(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def events_engine():
    """Engine SQLite en memoria emulando telemetry_events con eventos de prueba."""
    eng = build_engine("sqlite+pysqlite:///:memory:")
    with eng.begin() as conn:
        conn.execute(sa_text("""
            CREATE TABLE telemetry_events (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMPTZ,
                event_type VARCHAR(64),
                tags TEXT
            )
        """))
        start = datetime(2026, 10, 20, tzinfo=timezone.utc)
        rows = [
            (start.replace(hour=1), "auth_login_succeeded", '{"page":"/login"}'),
            (start.replace(hour=2), "api_latency_recorded", '{"ms":120}'),
            (start.replace(hour=23), "auth_login_failed", '{}'),
        ]
        for ts, etype, tags in rows:
            conn.execute(
                sa_text("INSERT INTO telemetry_events (timestamp, event_type, tags) VALUES (:ts, :et, :tags)"),
                {"ts": ts, "et": etype, "tags": tags},
            )
    yield eng
    eng.dispose()


# ======================================================================
# Export CSV
# ======================================================================


def test_export_telemetry_events_writes_csv(events_engine, tmp_path):
    """Exporta solo los eventos del día, con headers timestamp/event_type/tags."""
    count, path = export_telemetry_events(events_engine, DAY, tmp_path)
    assert count == 3
    assert path.name == "telemetry_2026-10-20.csv"

    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["timestamp", "event_type", "tags"]
    assert len(rows) == 4  # header + 3
    assert rows[1][1] == "auth_login_succeeded"


def test_export_boundary_excludes_next_day(events_engine, tmp_path):
    """Eventos de OUTSIDE el día (día siguiente) NO se exportan."""
    with events_engine.begin() as conn:
        conn.execute(
            sa_text("INSERT INTO telemetry_events (timestamp, event_type, tags) VALUES (:ts, :et, '{}')"),
            {"ts": datetime(2026, 10, 21, tzinfo=timezone.utc), "et": "api_request_failed"},
        )
    count, _ = export_telemetry_events(events_engine, DAY, tmp_path)
    assert count == 3


def test_export_skips_when_csv_already_exists(events_engine, tmp_path):
    """Si el archivo telemetry_YYYY-MM-DD.csv YA EXISTE, no se re-exporta."""
    path = csv_path_for(DAY, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("*snapshot previo inmutable*\n", encoding="utf-8")

    count, returned = export_telemetry_events(events_engine, DAY, tmp_path)
    assert count == 0  # no se escribieron filas nuevas
    assert returned == path
    # El contenido original NO se sobrescribió (backup inmutable).
    assert path.read_text(encoding="utf-8") == "*snapshot previo inmutable*\n"


# ======================================================================
# run_nightly completo
# ======================================================================


def test_run_nightly_completed(job_engine, events_engine, tmp_path, monkeypatch):
    """El job completo termina en completed con CSV y rows exportadas."""
    # Redirigir la export para que lea de events_engine
    monkeypatch.setattr("services.nightly.nightly_service.export_telemetry_events",
                        _fake_export)  # see below

    result = run_nightly(
        engine=job_engine,
        target_date=DAY,
        export_dir=tmp_path,
        skip_pipeline=True,  # no lanzar runner en tests
    )
    assert result["outcome"] == "completed"
    assert result["status"] == STATUS_COMPLETED
    assert result["exported_rows"] == 3

    row = find_job_run(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_COMPLETED
    assert row["csv_path"]
    assert Path(row["csv_path"]).exists()


def _fake_export(*args, **kwargs):
    """Export de prueba: escribe un CSV real con 3 filas en el dir dado."""
    import json as _json

    path = csv_path_for(DAY, kwargs.get("export_dir"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "event_type", "tags"])
        for i in range(3):
            writer.writerow([f"2026-10-20T0{i}:00:00Z", "auth_login_succeeded", _json.dumps({})])
    return 3, path


def test_run_nightly_is_idempotent(job_engine, events_engine, tmp_path, monkeypatch):
    """Segunda ejecución sobre el mismo día completed → noop, sin re-exportar."""
    monkeypatch.setattr("services.nightly.nightly_service.export_telemetry_events",
                        _fake_export)
    first = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                        skip_pipeline=True)
    second = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                         skip_pipeline=True)
    assert first["outcome"] == "completed"
    assert second["outcome"] == "noop_export"
    assert second["status"] == STATUS_COMPLETED


def test_run_nightly_aborts_when_lock_taken(job_engine, tmp_path, monkeypatch):
    """Si otra instancia está en processing, la segunda aborta silenciosamente."""
    # Simular que otra instancia ya corrió y tomó el lock
    create_job_run(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert mark_processing(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is True

    result = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                         skip_pipeline=True)
    assert result["outcome"] == "aborted"
    assert result["status"] == STATUS_PROCESSING

    # El estado original sigue intacto (el lock NO se ha solapado).
    row = find_job_run(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_PROCESSING


def test_run_nightly_failed_marks_failed(job_engine, tmp_path, monkeypatch):
    """Excepción durante el trabajo → registro queda en failed, no processing."""

    def _boom(*args, **kwargs):
        raise RuntimeError("supabase timeout")

    monkeypatch.setattr("services.nightly.nightly_service.export_telemetry_events", _boom)
    result = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                         skip_pipeline=True)
    assert result["outcome"] == "failed"
    row = find_job_run(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_FAILED
    assert "RuntimeError" in row["error_message"]


def test_run_nightly_retries_after_failure(job_engine, tmp_path, monkeypatch):
    """Un día en failed puede reintentarse: vuelve a completed en la siguiente."""

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("services.nightly.nightly_service.export_telemetry_events", _boom)
    run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path, skip_pipeline=True)

    monkeypatch.setattr("services.nightly.nightly_service.export_telemetry_events", _fake_export)
    second = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                         skip_pipeline=True)
    assert second["outcome"] == "completed"
    assert find_job_run(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY)["status"] == STATUS_COMPLETED


# ======================================================================
# Observabilidad — logs INFO/ERROR con job + estado
# ======================================================================


def test_logs_info_on_start_finish_and_skip(job_engine, events_engine, tmp_path,
                                            monkeypatch, caplog):
    """Inicio, fin y omisión por duplicado emiten INFO normalizado (job+estado)."""
    monkeypatch.setattr("services.nightly.nightly_service.export_telemetry_events",
                        _fake_export)

    # Las líneas del job salen por el logger estable "healthcore.nightly".
    with caplog.at_level(logging.INFO, logger="healthcore.nightly"):
        first = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                            skip_pipeline=True)
        second = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                             skip_pipeline=True)

    assert first["outcome"] == "completed"
    assert second["outcome"] == "noop_export"

    records = caplog.records
    # Secuencia esperada: started (run1) → finished (run1) → skip_duplicate (run2)
    events = [r.getMessage() for r in records]
    joined = "\n".join(events)

    # Inicio con lock tomado: job + status=processing
    assert "event=started" in joined
    assert f"job={JOB_NAME_NIGHTLY_EXPORT}" in joined
    assert "status=processing" in joined
    # Fin con éxito: job + status=completed
    assert "event=finished" in joined
    assert "status=completed" in joined
    # Omisión por duplicado: job + status=completed
    assert "event=skip_duplicate" in joined
    assert "status=completed" in joined
    # Cada línea lleva timestamp (ts=).
    assert "ts=" in joined


def test_logs_error_on_failure(job_engine, tmp_path, monkeypatch, caplog):
    """Una excepción emite log ERROR con job + status=failed."""
    def _boom(*args, **kwargs):
        raise RuntimeError("supabase timeout")

    monkeypatch.setattr("services.nightly.nightly_service.export_telemetry_events", _boom)

    with caplog.at_level(logging.ERROR, logger="healthcore.nightly"):
        result = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                             skip_pipeline=True)

    assert result["outcome"] == "failed"

    failed_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert failed_records, "Debe existir al menos un registro ERROR"
    joined = "\n".join(r.getMessage() for r in failed_records)
    assert f"job={JOB_NAME_NIGHTLY_EXPORT}" in joined
    assert "status=failed" in joined
    # El propio log_error (log_result con exc_info) también emite ERROR.
    error_msgs = [r.getMessage() for r in failed_records if "event=failed" in r.getMessage()]
    assert error_msgs, "Debe existir una línea event=failed a nivel ERROR"


def test_logs_abort_when_lock_taken(job_engine, tmp_path, caplog):
    """Aborto por lock tomado → INFO con job + status=processing (no ERROR)."""
    create_job_run(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert mark_processing(job_engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is True

    with caplog.at_level(logging.INFO, logger="healthcore.nightly"):
        result = run_nightly(engine=job_engine, target_date=DAY, export_dir=tmp_path,
                             skip_pipeline=True)

    assert result["outcome"] == "aborted"
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "event=aborted" in joined or "event=aborted_lock" in joined
    assert f"job={JOB_NAME_NIGHTLY_EXPORT}" in joined
    assert "status=processing" in joined
    assert not any(r.levelno == logging.ERROR for r in caplog.records)