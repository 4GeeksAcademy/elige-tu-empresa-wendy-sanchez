"""Regenera trazas reales del agente LangGraph usando servicios reales.

Cada corrida produce un archivo JSON en services/agent/traces/<run_id>.json
con timestamps reales (no sub-ms), routing_log verificable y eventos ordenados.

A diferencia de la versión anterior, NO se mockea ningún servicio:
  - retrieve() consulta Qdrant real (http://localhost:6333)
  - generate_answer() invoca el LLM real (https://llm.4geeks.ai)
  - query_incident_by_id() consulta la Incidents API real (http://localhost:8010)

Requisitos:
  - Docker services corriendo: qdrant, incidents-backend
  - .env con API_KEY, HOST, QDRANT_URL configurados

Los timestamps reflejan latencias reales de red, Qdrant y LLM.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Cargar .env primero (API_KEY, HOST) ────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── Sobrescribir URLs Docker-internas con localhost ────────────────
# Desde fuera de Docker, los contenedores son reachables por localhost
# gracias al mapeo de puertos en docker-compose.yml.
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["INCIDENTS_API_URL"] = "http://localhost:8010"

from services.agent.graph import run_agent, get_trace, list_traces


# ── Helpers ──────────────────────────────────────────────────────────

def _compute_duration_ms(trace: dict) -> str:
    """Calcula la duración real de la corrida desde los timestamps de eventos."""
    timestamps = [
        e.get("timestamp", "") for e in trace.get("events", [])
        if e.get("timestamp")
    ]
    if len(timestamps) >= 2:
        try:
            t0 = datetime.fromisoformat(timestamps[0])
            t1 = datetime.fromisoformat(timestamps[-1])
            ms = (t1 - t0).total_seconds() * 1000
            return f" | ⏱ {ms:.0f}ms"
        except (ValueError, TypeError):
            pass
    return ""


async def run_scenario(question: str, scenario_name: str) -> tuple[str, dict]:
    """Ejecuta el agente real (sin mocks) y retorna el run_id.

    Los servicios reales son:
      - Qdrant para retrieve (embed + vector search)
      - LLM para generate_answer
      - Incidents API para query_incident_by_id
    """
    run_id = str(uuid.uuid4())
    result = await run_agent(question, run_id=run_id)
    trace = get_trace(run_id)
    if trace:
        events = trace.get("events", [])
        routing = trace.get("routing_log", [])
        duration = _compute_duration_ms(trace)
        print(f"✅ {scenario_name}")
        print(f"   run_id={run_id[:8]}... | {len(events)} eventos | "
              f"routing: {' → '.join(routing)}{duration}")
    else:
        print(f"❌ {scenario_name} → no se generó trace")
    return run_id, result


async def main():
    # ── Limpiar trazas anteriores ────────────────────────────────────────
    traces_dir = _PROJECT_ROOT / "services" / "agent" / "traces"
    cleaned = 0
    for f in sorted(traces_dir.glob("*.json")):
        f.unlink()
        cleaned += 1
    print(f"🧹 {cleaned} traces anteriores eliminados.\n")

    # ── Escenario 1: RAG puro ────────────────────────────────────────────
    await run_scenario(
        "¿Cobran cargo por no-show a pacientes de Medicare?",
        "RAG puro — Medicare no-show",
    )

    # ── Escenario 2: Incidente puro ──────────────────────────────────────
    await run_scenario(
        "¿En qué estado está el ticket 2?",
        "Incidente puro — ticket 2",
    )

    # ── Escenario 3: Rag+Incidente combinado (caso que fallaba) ──────────
    await run_scenario(
        "Según la política de cancelación, ¿el ticket 2 debería tener cargo?",
        "RAG+Incidente combinado",
    )

    # ── Escenario 4: Fallo de tool en modo combinado ────────────────────
    await run_scenario(
        "Según la política de cancelación, ¿el ticket 999 debería tener cargo?",
        "RAG+Incidente con fallo de tool",
    )

    # ── Escenario 5: Pregunta inválida ──────────────────────────────────
    try:
        await run_agent("ab")
    except ValueError as e:
        print(f"✅ Pregunta inválida → ValueError: {e}")

    # ── Resumen ──────────────────────────────────────────────────────────
    all_traces = list_traces(limit=10)
    print(f"\n📊 Total trazas generadas: {len(all_traces)}")
    for t in all_traces:
        dur = _compute_duration_ms(t)
        print(f"  • {t['run_id'][:8]}... | {t['question'][:50]} | "
              f"{t['num_events']} eventos{dur}")


if __name__ == "__main__":
    asyncio.run(main())