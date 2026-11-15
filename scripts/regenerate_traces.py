"""Regenera trazas reales del agente LangGraph con los servicios mockeados.

Cada corrida produce un archivo JSON en services/agent/traces/<run_id>.json
con timestamps reales (no sub-ms), routing_log verificable y eventos ordenados.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from unittest.mock import patch
from services.agent.graph import run_agent, get_trace, list_traces

# ── Helpers ──────────────────────────────────────────────────────────

def _make_chunk(source_document="appointment-policy", section="Política de cancelación",
                text=None, score=0.85):
    return {
        "company": "healthcore",
        "source_document": source_document,
        "section": section,
        "language": "es",
        "chunk_index": 0,
        "text": text or (
            "Política de cancelación:\n"
            "Cancelar con más de 24 horas de anticipación: sin cargo.\n"
            "Cancelar con menos de 24 horas o no presentarse (no-show): "
            "cargo de 50 USD para pacientes de pago privado.\n"
            "Pacientes con Medicare o Medicaid: no se les cobra cargo por no-show."
        ),
        "_score": score,
    }

def _fake_generate_answer_grounded(question, context):
    if not context:
        return "No tengo información en los documentos disponibles..."
    texts = [chunk.get("text", "") for chunk in context]
    question_lower = question.lower()
    keywords = question_lower.split()
    best_text, best_score = "", 0
    for text in texts:
        text_lower = text.lower()
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_text = text
    if best_text:
        return f"Según la documentación de HealthCore:\n{best_text.strip()}"
    return "No encontré información relevante..."

def run_scenario(question, scenario_name, chunks=None, incident_result=None,
                 inventory_result=None, generate_answer=None):
    """Ejecuta el agente con los mocks correspondientes y retorna el run_id."""
    run_id = str(uuid.uuid4())

    patches_list = []

    # Mock retrieve
    if chunks is not None:
        patches_list.append(patch("services.agent.graph.retrieve", return_value=chunks))
    else:
        patches_list.append(patch("services.agent.graph.retrieve",
                                  return_value=[_make_chunk()]))

    # Mock generate_answer
    if generate_answer is not None:
        patches_list.append(patch("services.agent.graph.generate_answer",
                                  side_effect=generate_answer or _fake_generate_answer_grounded))
    else:
        patches_list.append(patch("services.agent.graph.generate_answer",
                                  side_effect=_fake_generate_answer_grounded))

    # Mock incident tool
    if incident_result is not None:
        patches_list.append(patch("services.agent.graph.query_incident_by_id",
                                  return_value=incident_result))

    # Mock inventory tool
    if inventory_result is not None:
        patches_list.append(patch("services.agent.graph.query_products_list",
                                  return_value=inventory_result))

    with patches_list[0]:
        with patches_list[1]:
            for p in patches_list[2:]:
                p.start()
            try:
                result = run_agent(question, run_id=run_id)
            finally:
                for p in patches_list[2:]:
                    p.stop()

    trace = get_trace(run_id)
    if trace:
        print(f"✅ {scenario_name} → {run_id[:8]}... ({len(trace['events'])} eventos, "
              f"routing: {' | '.join(trace['routing_log'])})")
    else:
        print(f"❌ {scenario_name} → no trace generated")
    return run_id, result

# ── Limpiar trazas anteriores ────────────────────────────────────────
traces_dir = _PROJECT_ROOT / "services" / "agent" / "traces"
for f in traces_dir.glob("*.json"):
    f.unlink()
print("🧹 Traces cleaned.\n")

# ── Escenario 1: RAG puro ────────────────────────────────────────────
run_scenario(
    "¿Cobran cargo por no-show a pacientes de Medicare?",
    "RAG puro — Medicare no-show",
    chunks=[_make_chunk(
        text="Cancelar con menos de 24 horas: cargo de 50 USD. Pacientes con Medicare: no se les cobra."
    )],
)

# ── Escenario 2: Incidente puro ──────────────────────────────────────
run_scenario(
    "¿En qué estado está el ticket 2?",
    "Incidente puro — ticket 2",
    incident_result={
        "id": 2, "title": "Patient not informed of appointment reschedule by clinic",
        "status": "resolved", "category": "patient_experience",
        "origin": "customer", "branch": "london_west",
        "branch_label": "London — West",
        "created_at": "2024-01-17T00:00:00+00:00",
        "updated_at": "2026-09-10T14:43:15.712221+00:00",
        "description_preview": "Patient not informed of appointment reschedule by clinic",
    },
)

# ── Escenario 3: Rag+Incidente combinado (caso que fallaba) ──────────
run_scenario(
    "Según la política de cancelación, ¿el ticket 2 debería tener cargo?",
    "RAG+Incidente combinado",
    chunks=[_make_chunk(
        text="Cancelar con menos de 24 horas: cargo de 50 USD. Pacientes con Medicare: no se les cobra."
    )],
    incident_result={
        "id": 2, "title": "Patient not informed of appointment reschedule by clinic",
        "status": "resolved", "category": "patient_experience",
        "origin": "customer",
        "branch": "london_west", "branch_label": "London — West",
        "created_at": "2024-01-17T00:00:00+00:00",
        "updated_at": "2026-09-10T14:43:15.712221+00:00",
        "description_preview": "Patient not informed of appointment reschedule by clinic",
    },
)

# ── Escenario 4: Fallo de tool en modo combinado ────────────────────
run_scenario(
    "Según la política de cancelación, ¿el ticket 999 debería tener cargo?",
    "RAG+Incidente con fallo de tool",
    chunks=[_make_chunk(
        text="Cancelar con menos de 24 horas: cargo de 50 USD."
    )],
    incident_result={"error": "No se pudo conectar con el servicio de incidentes."},
)

# ── Escenario 5: Pregunta inválida ──────────────────────────────────
try:
    run_agent("ab")
except ValueError as e:
    print(f"✅ Pregunta inválida → ValueError: {e}")

# ── Resumen ──────────────────────────────────────────────────────────
all_traces = list_traces(limit=10)
print(f"\n📊 Total trazas generadas: {len(all_traces)}")
for t in all_traces:
    print(f"  • {t['run_id'][:8]}... | {t['question'][:50]} | {t['num_events']} eventos")