"""Tests de la máquina de estados de job_runs (servicio job_runner, Hito 7).

Cubre la lógica de estados en ``services/job_runner.py`` sobre SQLite
en memoria:
- migración idempotente (ensure_schema)
- máquina de estados pending → processing → completed | failed
- lock vía estado: la segunda instancia no toma processing dos veces
- idempotencia por (job_name, target_date)
- helpers has_processing_lock / has_completed_for_date
- representación del CSV de export en ``nightly_service``
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

# Asegurar que la raíz del proyecto está en sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.job_runner import (
    JOB_NAME_NIGHTLY_EXPORT,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    VALID_STATUSES,
    build_engine,
    create_job_run,
    ensure_schema,
    find_job_run,
    has_completed_for_date,
    has_processing_lock,
    list_job_runs,
    mark_completed,
    mark_failed,
    mark_processing,
)
from services.nightly.nightly_service import csv_path_for, target_date_from_env

DAY = date(2026, 10, 20)


@pytest.fixture()
def engine():
    """Engine SQLite en memoria con el esquema job_runs aplicado."""
    eng = build_engine("sqlite+pysqlite:///:memory:")
    ensure_schema(eng)
    yield eng
    eng.dispose()


# ======================================================================
# 1. Migración idempotente
# ======================================================================


def test_ensure_schema_is_idempotent(engine):
    """Aplicar ensure_schema dos veces no rompe ni duplica nada."""
    ensure_schema(engine)  # segunda vez
    assert find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is None


def test_create_job_run_creates_pending(engine):
    """La fila se crea en pending ANTES de empezar."""
    row = create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_PENDING
    assert row["target_date"] == str(DAY)
    assert row["started_at"] is None
    assert row["finished_at"] is None


def test_create_job_run_is_unique_per_day(engine):
    """La unicidad (job_name, target_date) impide duplicar el mismo día."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    with pytest.raises(Exception):  # IntegrityError en SQLite/Postgres
        create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)


# ======================================================================
# 2. Máquina de estados: pending → processing → completed
# ======================================================================


def test_full_lifecycle_completed(engine):
    """pending → processing → completed, con sello temporal y resultado."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)

    assert mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is True
    row = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_PROCESSING
    assert row["started_at"] is not None
    assert row["finished_at"] is None

    assert mark_completed(
        engine, JOB_NAME_NIGHTLY_EXPORT, DAY, exported_rows=42, csv_path="x.csv"
    ) is True
    row = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_COMPLETED
    assert row["finished_at"] is not None
    assert row["exported_rows"] == 42
    assert row["csv_path"] == "x.csv"


def test_full_lifecycle_failed(engine):
    """pending → processing → failed (nunca se queda en processing)."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)

    assert mark_failed(engine, JOB_NAME_NIGHTLY_EXPORT, DAY,
                       error_message="ValueError: boom") is True
    row = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_FAILED
    assert row["finished_at"] is not None
    assert "boom" in row["error_message"]


def test_job_never_left_in_processing(engine):
    """Invariante: completing o failing SIEMPRE liberan el lock."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)

    finalized = mark_completed(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) or mark_failed(
        engine, JOB_NAME_NIGHTLY_EXPORT, DAY
    )
    assert finalized is True
    row = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] in (STATUS_COMPLETED, STATUS_FAILED)


# ======================================================================
# 3. Lock distribuido via estado: no dos processing
# ======================================================================


def test_lock_prevents_second_instance(engine):
    """El lock ES el estado: una fila en processing bloquea la segunda."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is True

    # Segunda instancia: el UPDATE ... WHERE status='pending' no afecta filas.
    assert mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is False

    # Y la fila sigue en processing (el estado original, no sobreescrito).
    row = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert row["status"] == STATUS_PROCESSING


def test_lock_only_blocks_pending(engine):
    """Una fila completed NO bloquea (se puede re-intentar si se fuerza)."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_completed(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)

    # Ya no hay pending → mark_processing no vuelve a fallar ni a tomar lock.
    assert mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is False


# ======================================================================
# 4. Consultas
# ======================================================================


def test_find_job_run_by_id_and_by_day(engine):
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    by_day = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert by_day is not None

    run_id = by_day["id"]
    by_id = find_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY, run_id=run_id)
    assert by_id["id"] == run_id


def test_list_job_runs_filters_by_job(engine):
    create_job_run(engine, "job_a", DAY)
    create_job_run(engine, "job_b", DAY + timedelta(days=1))
    runs = list_job_runs(engine, job_name="job_a")
    assert len(runs) == 1
    assert runs[0]["job_name"] == "job_a"


# ======================================================================
# 4b. Helpers has_processing_lock / has_completed_for_date
# ======================================================================


def test_has_processing_lock_false_when_none(engine):
    """Sin fila para el día → no hay lock."""
    assert has_processing_lock(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is False


def test_has_processing_lock_true_when_processing(engine):
    """Fila en processing → otra instancia tiene el lock (abortar)."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert has_processing_lock(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is True


def test_has_processing_lock_false_when_completed(engine):
    """Fila completed → el lock se liberó, no hay processing."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_completed(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert has_processing_lock(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is False


def test_has_processing_lock_is_scoped_by_job_and_date(engine):
    """El lock es por (job_name, target_date): otro job/día no lo ve."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert has_processing_lock(engine, "otro_job", DAY) is False
    assert has_processing_lock(engine, JOB_NAME_NIGHTLY_EXPORT, DAY + timedelta(days=1)) is False


def test_has_completed_for_date_false_when_pending_or_processing(engine):
    """pending/processing NO cuentan como completado (no idempotente)."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert has_completed_for_date(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is False
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert has_completed_for_date(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is False


def test_has_completed_for_date_true_after_completed(engine):
    """completed → idempotente: no volver a exportar."""
    create_job_run(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_processing(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    mark_completed(engine, JOB_NAME_NIGHTLY_EXPORT, DAY)
    assert has_completed_for_date(engine, JOB_NAME_NIGHTLY_EXPORT, DAY) is True


def test_has_completed_for_date_requires_same_job(engine):
    """Solo job_name + target_date basta; job_name sin día no es suficiente."""
    create_job_run(engine, "job_a", DAY)
    mark_processing(engine, "job_a", DAY)
    mark_completed(engine, "job_a", DAY)
    assert has_completed_for_date(engine, "job_a", DAY) is True
    # Mismo día pero OTRO job → NO completado.
    assert has_completed_for_date(engine, "job_b", DAY) is False


# ======================================================================
# 5. Fechas y convención de CSV
# ======================================================================


def test_target_date_from_env_monkeypatched(tmp_path, monkeypatch):
    """TARGET_DATE sobrescribe 'ayer' UTC para pruebas sin cambiar código."""
    monkeypatch.setenv("TARGET_DATE", "2026-10-20")
    assert target_date_from_env() == date(2026, 10, 20)


def test_csv_path_convention(tmp_path):
    """data/raw/telemetry_YYYY-MM-DD.csv."""
    path = csv_path_for(DAY, tmp_path)
    assert path.name == "telemetry_2026-10-20.csv"
    assert path.parent == tmp_path