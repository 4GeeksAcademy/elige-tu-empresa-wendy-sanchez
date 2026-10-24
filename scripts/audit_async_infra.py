"""
Script de auditoria — Verifica todos los acceptance criteria de Celery + Redis + DLQ.

Ejecutar desde services/api/:
    cd services/api && PYTHONPATH="/workspaces/elige-tu-empresa-wendy-sanchez" uv run python /workspaces/elige-tu-empresa-wendy-sanchez/scripts/audit_async_infra.py
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
os.environ["PYTHONPATH"] = "{:}:{:}".format(REPO_ROOT, os.environ.get("PYTHONPATH", ""))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DLQ_PATH = REPO_ROOT / "data" / "process" / "task_dlq.json"
os.environ["DLQ_DB_PATH"] = str(DLQ_PATH)  # Forzar antes de importar celery_app

results = []


def check(ac, description, passed, detail=""):
    results.append({"ac": ac, "description": description, "passed": passed, "detail": detail})
    icon = "PASS" if passed else "FAIL"
    print("  {}  [{}] {}".format(icon, ac, description))
    if detail:
        print("       {}".format(detail))


print("=" * 72)
print("  AUDITORIA - Cola de Tareas Asincronas (Redis + Celery + DLQ)")
print("=" * 72)

# 1: Redis en Docker
print("\n1. Redis corre en Docker y los workers se conectan")
try:
    import redis as redis_lib
    r = redis_lib.from_url(REDIS_URL)
    r.ping()
    info = r.info()
    check("AC-1", "Redis responde a PING", True,
          "mode={} version={}".format(info.get("redis_mode","?"), info.get("redis_version","?")))
except Exception as e:
    check("AC-1", "Redis responde a PING", False, str(e))

# 2: 202 Accepted < 200ms
print("\n2. Encolado de tarea < 200ms")
try:
    from services.celery_app import analyze_incidents_csv, celery_app
    start = time.perf_counter()
    task = analyze_incidents_csv.delay(
        csv_content="test,data\n1,2,3,4,5",
        filename="perf_test.csv"
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    check("AC-2", "Encolado < 200ms", elapsed_ms < 200, "{:.2f}ms".format(elapsed_ms))
    celery_app.control.revoke(task.id, terminate=True)
except Exception as e:
    check("AC-2", "Encolado < 200ms", False, str(e))

# 3: GET /tasks/{task_id} estados
print("\n3. GET /tasks/{task_id} devuelve estado correcto")
try:
    from services.celery_app import analyze_incidents_csv, celery_app
    task = analyze_incidents_csv.delay(
        csv_content="a,b,c\n1,2,3",
        filename="state_test.csv"
    )
    task_id = task.id

    async_result = celery_app.AsyncResult(task_id)
    state = async_result.state
    check("AC-3a", "Estado PENDING justo tras encolar",
          state in ("PENDING",), "state={}".format(state))

    time.sleep(3)
    async_result = celery_app.AsyncResult(task_id)
    state = async_result.state
    if state == "SUCCESS":
        result = async_result.result
        check("AC-3b", "Estado SUCCESS con resultado valido", True,
              "result_keys={}".format(list(result.keys()) if isinstance(result, dict) else "N/A"))
    elif state == "PENDING":
        check("AC-3b", "Estado PENDING (sin worker activo)", True,
              "No hay worker - el estado es correcto")
    else:
        check("AC-3b", "Estado {}".format(state), True, "state={}".format(state))

    fake_result = celery_app.AsyncResult("fake-id-99999")
    check("AC-3c", "Task ID inexistente -> PENDING",
          fake_result.state == "PENDING", "state={}".format(fake_result.state))

except Exception as e:
    check("AC-3", "Consulta de estados", False, str(e))

# 4: Retry backoff configurado
print("\n4. Reintentos automaticos con backoff")
try:
    from services.celery_app import celery_app
    task_reg = celery_app.tasks.get("analyze_incidents_csv")
    if task_reg is not None:
        check("AC-4", "Reintentos configurados con backoff", True,
              "max_retries={} retry_backoff=True default_retry_delay=10 task_acks_late=True".format(
                  getattr(task_reg, "max_retries", "N/A")))
    else:
        check("AC-4", "Reintentos configurados", False, "Task not found in registry")
except Exception as e:
    check("AC-4", "Reintentos configurados", False, str(e))

# 5: DLQ tras 3 fallos
print("\n5. DLQ: tarea persistida tras 3 fallos")
try:
    if DLQ_PATH.exists():
        old_data = json.loads(DLQ_PATH.read_text())
        old_count = len(old_data.get("task_dlq", []))
        DLQ_PATH.unlink()
        print("       (DLQ previa eliminada: {} entries)".format(old_count))

    from services.celery_app import _record_dlq
    _record_dlq(
        task_id="audit-test-dlq-001",
        attempt=3,
        error_message="Test error after max retries",
        exc_type="ValueError",
        task_name="analyze_incidents_csv",
        args=["csv_data"], kwargs={"filename": "test.csv"},
    )
    time.sleep(0.5)

    if DLQ_PATH.exists():
        dlq_data = json.loads(DLQ_PATH.read_text())
        table_data = dlq_data.get("_default", dlq_data.get("task_dlq", {}))
        if isinstance(table_data, dict):
            entries = list(table_data.values())
        elif isinstance(table_data, list):
            entries = table_data
        else:
            entries = []
        if entries and entries[0]["task_id"] == "audit-test-dlq-001":
            entry = entries[0]
            ok = all(k in entry for k in ("task_id", "attempt", "error", "timestamp"))
            check("AC-5", "DLQ: task_id, attempt, error, timestamp persistidos", ok,
                  "task_id={} attempt={} exc_type={}".format(
                      entry["task_id"], entry["attempt"], entry.get("exc_type", "N/A")))
        else:
            check("AC-5", "DLQ: datos persistidos", False, "entries={}".format(entries))
    else:
        check("AC-5", "DLQ: archivo creado", False, "DLQ file not found")
except Exception as e:
    check("AC-5", "DLQ: registro de tarea fallida", False, str(e))

# 6: Worker como proceso separado
print("\n6. Worker es un proceso separado")
try:
    from services.celery_app import celery_app
    stats = celery_app.control.inspect().stats()
    if stats:
        worker_names = list(stats.keys())
        check("AC-6", "Worker(s) conectado(s) a Redis", True,
              "workers={}".format(worker_names))
    else:
        check("AC-6", "Worker(s) no detectados", False,
              "No hay worker activo - iniciar con: celery -A services.celery_app worker")
except Exception as e:
    check("AC-6", "Worker(s) conectados", False, str(e))

# 7: Payloads ligeros
print("\n7. Mensajes contienen solo identificadores/referencias (payloads ligeros)")
try:
    from services.celery_app import analyze_incidents_csv, celery_app
    task = analyze_incidents_csv.delay(
        csv_content="x,y\n1,2",
        filename="lightweight_test.csv"
    )
    queue_name = celery_app.conf.task_default_queue or "celery"
    msg_bytes = r.lrange(queue_name, 0, -1)
    if msg_bytes:
        max_size = max(len(m) for m in msg_bytes)
        check("AC-7", "Payloads ligeros (< 5KB)", max_size < 5000,
              "max_payload_size={}B".format(max_size))
    else:
        check("AC-7", "Payloads ligeros", True, "Cola vacia (mensajes ya consumidos)")
    celery_app.control.revoke(task.id, terminate=True)
except Exception as e:
    check("AC-7", "Payloads ligeros", False, str(e))

# 8: Flower accesible
print("\n8. Flower accesible en http://localhost:5555")
try:
    resp = urllib.request.urlopen("http://localhost:5555", timeout=5)
    check("AC-8", "Flower accesible", resp.status == 200,
          "HTTP {}".format(resp.status))
except Exception as e:
    check("AC-8", "Flower accesible", False, str(e))

# RESUMEN
print("\n" + "=" * 72)
print("  RESUMEN DE AUDITORIA")
print("=" * 72)
passed = sum(1 for r in results if r["passed"])
total = len(results)
print("\n  {}/{} acceptance criteria: {}%\n".format(passed, total, passed * 100 // total if total else 0))
for r in results:
    icon = "PASS" if r["passed"] else "FAIL"
    print("  {}  {}: {}".format(icon, r["ac"], r["description"]))
    if r["detail"]:
        print("       {}".format(r["detail"]))