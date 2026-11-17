"""
services/agent/graph.py — Grafo LangGraph del agente de soporte HealthCore.

Parte 1 (base):
  - receive_question → retrieve_context → generate_answer / respond_no_info
  - Aristas condicionales, trazabilidad, checkpointing.

Parte 2 (tools externas):
  - classify_query: decide si la pregunta necesita RAG, tool (incidentes,
    inventario) o ambos, sin que el usuario lo especifique.
  - query_incident_tool: consulta el gestor de incidentes (GET /api/incidents).
  - query_inventory_tool: consulta el gestor de inventario (GET /inventory/products).
  - Todas las tools tienen timeout (5s) y ruta de fallback explícita.
  - El trace muestra si se usó RAG, tool, o ambos, y en qué orden.

Principios:
  - Estado mínimo y explícito.
  - Nodos con responsabilidad única.
  - Fallback honesto: si una tool falla, el agente no inventa datos.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

# Reutilizamos las funciones RAG existentes — sin duplicar lógica.
from data.pipelines.rag import generate_answer, retrieve

# Tools externas (Parte 2) — MCP Client
from services.agent.tools.mcp_client import (
    query_incident_by_id,
    query_incidents_list,
    query_product_by_id,
    query_products_list,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# 1.  Estado del grafo — mínimo, explícito, trazable
# ──────────────────────────────────────────────────────────────────────


def _accumulate_list(
    existing: list[Any], new: list[Any]
) -> list[Any]:
    """Reducer para acumular listas entre nodos en lugar de reemplazarlas."""
    return existing + new


class AgentState(TypedDict):
    """Estado que viaja entre nodos del grafo.

    Contiene solo la información mínima que cada nodo necesita para
    ejecutar su responsabilidad y decidir el siguiente paso.

    Atributos (Parte 1):
        question:         Pregunta original del usuario (validada).
        retrieved_chunks: Fragmentos recuperados de Qdrant.
        answer:           Respuesta final generada o mensaje de fallback.
        error:            Mensaje de error si un nodo falló (None si ok).
        trace_events:     Lista de eventos estructurados (reducer: add).
        routing_log:      Decisiones de enrutamiento (reducer: add).
        question_valid:   Booleano: True si la pregunta es válida.

    Atributos (Parte 2 — tools externas):
        routing_decision: Cómo enrutar la pregunta.
                          "rag" | "incident" | "inventory" |
                          "rag+incident" | "rag+inventory" | ""
        tool_results:     Resultados normalizados de las tools.
        tool_errors:      Errores de las tools (fallback).
    """

    question: str
    retrieved_chunks: list[dict[str, Any]]
    answer: str
    error: Optional[str]
    trace_events: Annotated[list[dict[str, Any]], _accumulate_list]
    routing_log: Annotated[list[str], _accumulate_list]
    question_valid: bool
    # Parte 2
    routing_decision: str
    tool_results: Annotated[list[dict[str, Any]], _accumulate_list]
    tool_errors: Annotated[list[str], _accumulate_list]


def build_initial_state(question: str) -> AgentState:
    """Construye el estado inicial para una nueva corrida del grafo."""
    return AgentState(
        question=question.strip(),
        retrieved_chunks=[],
        answer="",
        error=None,
        trace_events=[],
        routing_log=[],
        question_valid=True,
        routing_decision="",
        tool_results=[],
        tool_errors=[],
    )


# ──────────────────────────────────────────────────────────────────────
# 2.  Traza estructurada (funciona sin LangSmith)
# ──────────────────────────────────────────────────────────────────────

_TRACE_DIR = Path(__file__).resolve().parent / "traces"
_TRACE_DIR.mkdir(exist_ok=True)


def _make_trace_event(
    node: str,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea un evento de traza estructurado."""
    event: dict[str, Any] = {
        "node": node,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        event["metadata"] = metadata
    return event


def persist_trace(state: AgentState, run_id: str) -> Path:
    """Persiste la traza completa de una corrida en disco como JSON.

    El archivo se escribe en services/agent/traces/<run_id>.json.
    Es consultable después de la corrida — no solo impreso en consola.
    """
    trace = {
        "run_id": run_id,
        "question": state["question"],
        "answer": state["answer"],
        "error": state.get("error"),
        "routing_log": state.get("routing_log", []),
        "events": state.get("trace_events", []),
        "num_chunks_retrieved": len(state.get("retrieved_chunks", [])),
        "final_answer_length": len(state.get("answer", "")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    trace_path = _TRACE_DIR / f"{run_id}.json"
    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Trace persisted → %s", trace_path)
    return trace_path


# ──────────────────────────────────────────────────────────────────────
# 3.  Nodos — cada uno con una sola responsabilidad
# ──────────────────────────────────────────────────────────────────────


def node_receive_question(state: AgentState) -> dict[str, Any]:
    """Valida la pregunta del usuario.

    Responsabilidad: verificar que la pregunta no esté vacía ni sea
    demasiado corta.  Si es inválida, establece error y enruta al final.
    """
    question = state.get("question", "").strip()

    if not question:
        return {
            "error": "La pregunta no puede estar vacía.",
            "question_valid": False,
            "routing_log": ["receive_question → END (pregunta vacía)"],
            "trace_events": [_make_trace_event("receive_question", "error", {"reason": "empty"})],
        }

    if len(question) < 3:
        return {
            "error": "La pregunta es demasiado corta (mínimo 3 caracteres).",
            "question_valid": False,
            "routing_log": ["receive_question → END (pregunta demasiado corta)"],
            "trace_events": [_make_trace_event("receive_question", "error", {"reason": "too_short"})],
        }

    return {
        "question_valid": True,
        "routing_log": ["receive_question → classify_query (pregunta válida)"],
        "trace_events": [_make_trace_event("receive_question", "ok", {"question_length": len(question)})],
    }


def node_retrieve_context(state: AgentState) -> dict[str, Any]:
    """Ejecuta retrieve() sobre la base de conocimiento Qdrant.

    Reutiliza la función ``data.pipelines.rag.retrieve()`` sin duplicarla.
    El embed se hace internamente por retrieve() — no repetimos el embed aquí.
    """
    question = state["question"]
    try:
        chunks = retrieve(question, k=5, min_score=0.3)
    except RuntimeError as exc:
        return {
            "error": f"Error al recuperar información: {exc}",
            "retrieved_chunks": [],
            "routing_log": ["retrieve_context → error"],
            "trace_events": [_make_trace_event("retrieve_context", "error", {"error": str(exc)})],
        }

    if not chunks:
        return {
            "retrieved_chunks": [],
            "routing_log": [
                f"retrieve_context → respond_no_info (ningún fragmento "
                f"superó el umbral de {0.3})"
            ],
            "trace_events": [_make_trace_event("retrieve_context", "ok", {"num_chunks": 0})],
        }

    return {
        "retrieved_chunks": chunks,
        "routing_log": [
            f"retrieve_context → generate_answer ({len(chunks)} fragmentos recuperados)"
        ],
        "trace_events": [_make_trace_event("retrieve_context", "ok", {"num_chunks": len(chunks)})],
    }


def node_generate_answer(state: AgentState) -> dict[str, Any]:
    """Genera la respuesta final a partir del contexto ya recuperado.

    Reutiliza ``data.pipelines.rag.generate_answer(question, context)``
    con los chunks que el nodo retrieve_context ya produjo.
    NO ejecuta retrieve() internamente.
    """
    question = state["question"]
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {
            "answer": (
                "No encontré información relevante en la base de conocimiento "
                "para responder tu pregunta. Intenta reformularla o contacta a "
                "tu coordinador de pacientes."
            ),
            "routing_log": ["generate_answer → END (sin contexto, modo seguro)"],
            "trace_events": [_make_trace_event("generate_answer", "fallback", {"reason": "empty_context"})],
        }

    try:
        answer = generate_answer(question=question, context=chunks)
    except RuntimeError as exc:
        return {
            "error": f"Error al generar la respuesta: {exc}",
            "answer": "",
            "routing_log": ["generate_answer → error"],
            "trace_events": [_make_trace_event("generate_answer", "error", {"error": str(exc)})],
        }

    return {
        "answer": answer,
        "routing_log": ["generate_answer → END (respuesta generada)"],
        "trace_events": [_make_trace_event("generate_answer", "ok", {"answer_length": len(answer)})],
    }


def node_respond_no_info(state: AgentState) -> dict[str, Any]:
    """Responde con honestidad cuando no hay contexto suficiente.

    En lugar de forzar una generación sobre contexto vacío (que podría
    producir alucinaciones), devuelve un mensaje claro al usuario.
    """
    return {
        "answer": (
            "No tengo información suficiente en la base de conocimiento "
            "para responder esta pregunta. "
            "Si necesitas ayuda con políticas de HealthCore, "
            "intenta reformular tu pregunta o contacta a tu coordinador de pacientes."
        ),
        "routing_log": ["respond_no_info → END (sin información disponible)"],
        "trace_events": [_make_trace_event("respond_no_info", "ok")],
    }


def node_handle_error(state: AgentState) -> dict[str, Any]:
    """Maneja errores de nodos anteriores con un mensaje amigable.

    Nunca expone stack traces crudos al usuario.
    """
    error = state.get("error", "Error desconocido")

    return {
        "answer": (
            "Ocurrió un error al procesar tu solicitud. "
            "Por favor intenta de nuevo más tarde. "
            "Si el problema persiste, contacta a soporte técnico."
        ),
        "routing_log": [f"handle_error → END (error capturado: {error[:50]}...)"],
        "trace_events": [_make_trace_event("handle_error", "error", {"original_error": error})],
    }


# ══════════════════════════════════════════════════════════════════════
# P A R T E   2   —   N o d o s   d e   t o o l s   e x t e r n a s
# ══════════════════════════════════════════════════════════════════════
#
# El agente decide automáticamente si necesita RAG, una tool externa, o
# ambos, basándose en patrones léxicos de la pregunta.  No requiere que
# el usuario especifique la fuente.


def node_classify_query(state: AgentState) -> dict[str, Any]:
    """Clasifica la pregunta para decidir qué fuente(s) usar.

    Analiza la pregunta del usuario y determina si necesita:
      - "rag"             → solo base de conocimiento (políticas, procedimientos)
      - "incident"        → solo gestor de incidentes (tickets, estado)
      - "inventory"       → solo gestor de inventario (stock, productos)
      - "rag+incident"    → ambos (ej. "según la política X, ¿el ticket Y es válido?")
      - "rag+inventory"   → ambos

    El enrutamiento se basa en patrones léxicos específicos para cada
    dominio.  No se necesita un LLM para esta clasificación — la pregunta
    tiene señales suficientes.
    """
    question = state["question"].lower().strip()

    # ── Patrones para incidentes ──────────────────────────────────────
    incident_patterns = [
        r"\bticket\b", r"\bincidente\b", r"\bestado\s+del?\s+(ticket|incidente|caso)\b",
        r"\bincidentes?\b", r"\btickets?\b", r"\bticket\s+\d+\b",
        r"\bincidente\s+\d+\b", r"\bcaso\s+\d+\b", r"\bstatus\b",
        r"\bID\s+\d+\b", r"\bseguimiento\b", r"\bpendiente\b",
        r"\bcerrado\b", r"\ben\s+progreso\b", r"\bresuelto\b",
        r"\b#\d+\b", r"\bqué\s+pasó\b", r"\bproblema\s+reportado\b",
        r"\breporte\s+de\s+incidente\b", r"\bincidencias?\b",
    ]

    # ── Patrones para inventario ──────────────────────────────────────
    inventory_patterns = [
        r"\bstock\b", r"\binventario\b", r"\bproducto\b", r"\bsuministro\b",
        r"\btenemos\s+stock\b", r"\bcu[aá]nto\s+stock\b", r"\bdisponible\b",
        r"\bexistencia\b", r"\bhay\s+stock\b", r"\bsku\b",
        r"\bsupply\b", r"\bmaterial\b", r"\bmedicamento\b", r"\binsumo\b",
        r"\bproveedor\b", r"\borden\s+de\s+(compra|entrada|salida)\b",
    ]

    # ── Patrones para RAG (conocimiento) ──────────────────────────────
    rag_patterns = [
        r"\bpol[ií]tica\b", r"\bprocedimiento\b", r"\breglamento\b",
        r"\bcobertura\b", r"\bseguro\b", r"\bcargo\b", r"\bcobro\b",
        r"\bno-show\b", r"\bcancelaci[oó]n\b", r"\bmedicare\b",
        r"\bmedicaid\b", r"\bhipaa\b", r"\bprivacidad\b", r"\bconsentimiento\b",
        r"\bc[ií]tas?\b", r"\bagendamiento\b", r"\bhorario\b",
        r"\bdocumentaci[oó]n\b", r"\bpol[ií]ticas\b", r"\bnormativa\b",
        r"\bhealthcore\b", r"\bprograma\b", r"\bcategoria\b",
        r"\bconducta\b", r"\bc[oó]digo\b", r"\bdeberes\b",
    ]

    has_incident = any(re.search(p, question) for p in incident_patterns)
    has_inventory = any(re.search(p, question) for p in inventory_patterns)
    has_rag = any(re.search(p, question) for p in rag_patterns)

    # Si no hay señales claras de ningún dominio, asumir RAG (default)
    if not has_incident and not has_inventory and not has_rag:
        has_rag = True  # fallback a RAG

    # Construir routing_decision
    if has_incident and has_rag:
        decision = "rag+incident"
    elif has_inventory and has_rag:
        decision = "rag+inventory"
    elif has_incident:
        decision = "incident"
    elif has_inventory:
        decision = "inventory"
    else:
        decision = "rag"

    logger.info(
        "Clasificación: incident=%s inventory=%s rag=%s → decisión=%s",
        has_incident, has_inventory, has_rag, decision,
    )

    return {
        "routing_decision": decision,
        "routing_log": [f"classify_query → {decision}"],
        "trace_events": [_make_trace_event(
            "classify_query", "ok",
            {"decision": decision, "has_incident": has_incident,
             "has_inventory": has_inventory, "has_rag": has_rag},
        )],
    }


async def node_query_incident(state: AgentState) -> dict[str, Any]:
    """Consulta el gestor de incidentes vía MCP Client.

    Extrae el ID del ticket de la pregunta (si existe) o lista incidentes
    con filtros.  Timeout: configurado en el MCP Client (default 10s).

    Si el servicio no responde o el ticket no existe, registra un error
    controlado para que el grafo enrute a handle_error.
    """
    question = state["question"]

    # Intentar extraer un número de ticket (ej. "ticket 482", "#482", "482")
    ticket_id = _extract_ticket_id(question)

    if ticket_id is not None:
        result = await query_incident_by_id(ticket_id)
    else:
        # Sin ID específico: listar con filtros inferidos de la pregunta
        filters = _infer_incident_filters(question)
        result = await query_incidents_list(**filters)

    if isinstance(result, dict) and "error" in result:
        logger.warning("Fallo en query_incident: %s", result["error"])
        return {
            "tool_results": [],
            "tool_errors": [result["error"]],
            "routing_log": [f"query_incident → error: {result['error'][:60]}"],
            "trace_events": [_make_trace_event(
                "query_incident", "error", {"error": result["error"]},
            )],
        }

    # Si query_incidents_list devolvió lista, normalizamos cada item
    if isinstance(result, list):
        incidents = result
    else:
        incidents = [result]

    return {
        "tool_results": incidents,
        "tool_errors": [],
        "routing_log": [f"query_incident → {len(incidents)} resultado(s)"],
        "trace_events": [_make_trace_event(
            "query_incident", "ok", {"num_results": len(incidents)},
        )],
    }


async def node_query_inventory(state: AgentState) -> dict[str, Any]:
    """Consulta el gestor de inventario vía MCP Client.

    Extrae el ID del producto de la pregunta (si existe) o lista productos
    con filtros.  Timeout: configurado en el MCP Client (default 10s).
    """
    question = state["question"]

    # Intentar extraer un ID de producto
    product_id = _extract_product_id(question)
    name_search = _extract_product_name(question)

    if product_id is not None:
        result = await query_product_by_id(product_id)
    else:
        filters = {}
        category = _infer_product_category(question)
        if category:
            filters["category"] = category
        if name_search:
            filters["name_search"] = name_search
        result = await query_products_list(**filters)

    if isinstance(result, dict) and "error" in result:
        logger.warning("Fallo en query_inventory: %s", result["error"])
        return {
            "tool_results": [],
            "tool_errors": [result["error"]],
            "routing_log": [f"query_inventory → error: {result['error'][:60]}"],
            "trace_events": [_make_trace_event(
                "query_inventory", "error", {"error": result["error"]},
            )],
        }

    if isinstance(result, list):
        products = result
    else:
        products = [result]

    return {
        "tool_results": products,
        "tool_errors": [],
        "routing_log": [f"query_inventory → {len(products)} resultado(s)"],
        "trace_events": [_make_trace_event(
            "query_inventory", "ok", {"num_results": len(products)},
        )],
    }


def node_synthesize_tool_answer(state: AgentState) -> dict[str, Any]:
    """Sintetiza la respuesta final cuando se usaron tools externas.

    Construye un mensaje legible a partir de los resultados de la(s)
    tool(s).  Si hubo errores, responde con honestidad sin inventar datos.
    En modo combinado (rag+incident, rag+inventory) incluye la respuesta RAG
    aunque la tool haya fallado.
    """
    tool_results = state.get("tool_results", [])
    tool_errors = state.get("tool_errors", [])
    decision = state.get("routing_decision", "")
    rag_answer = state.get("answer", "")

    # Si todas las tools fallaron en modo combinado, incluir RAG + error
    if not tool_results and tool_errors:
        if decision in ("rag+incident", "rag+inventory") and rag_answer:
            error_msg = " ".join(tool_errors)
            answer = (
                f"{rag_answer}\n\n---\n\n"
                f"⚠️ No se pudo consultar el servicio externo: {error_msg}"
            )
            return {
                "answer": answer,
                "routing_log": [f"synthesize_tool_answer → respuesta RAG + error tool ({error_msg[:60]})"],
                "trace_events": [_make_trace_event(
                    "synthesize_tool_answer", "fallback",
                    {"errors": tool_errors, "rag_included": True},
                )],
            }
        # Modo tool-only: fallback honesto
        error_msg = " ".join(tool_errors)
        return {
            "answer": (
                f"No pude completar la consulta solicitada: {error_msg} "
                "Por favor verifica que los datos estén disponibles o "
                "intenta de nuevo más tarde."
            ),
            "routing_log": [f"synthesize_tool_answer → fallback por error: {error_msg[:60]}"],
            "trace_events": [_make_trace_event(
                "synthesize_tool_answer", "fallback",
                {"errors": tool_errors},
            )],
        }

    # Si hay resultados, construir respuesta
    rag_answer = state.get("answer", "")
    if decision == "incident":
        answer = _format_incident_response(tool_results)
    elif decision == "inventory":
        answer = _format_inventory_response(tool_results)
    elif decision == "rag+incident":
        # Combinar política (RAG) + incidente
        inc_answer = _format_incident_response(tool_results)
        answer = f"{inc_answer}\n\n---\n\n{rag_answer}" if rag_answer else inc_answer
    elif decision == "rag+inventory":
        # Combinar política (RAG) + inventario
        inv_answer = _format_inventory_response(tool_results)
        answer = f"{inv_answer}\n\n---\n\n{rag_answer}" if rag_answer else inv_answer
    else:
        # Fallback: si no hay decisión clara, volcar resultados
        items = []
        for r in tool_results:
            items.append(f"- {r}")
        answer = "Resultados de la consulta:\n" + "\n".join(items)

    return {
        "answer": answer,
        "routing_log": [f"synthesize_tool_answer → respuesta ({len(tool_results)} resultado(s))"],
        "trace_events": [_make_trace_event(
            "synthesize_tool_answer", "ok",
            {"decision": decision, "num_results": len(tool_results)},
        )],
    }


# ── Helpers para extraer IDs y filtros ──────────────────────────────


def _extract_ticket_id(question: str) -> int | None:
    """Extrae un ID numérico de ticket de la pregunta.

    Reconoce patrones como: "ticket 482", "#482", "482" cuando está
    cerca de palabras clave.
    """
    q = question.lower()
    # ticket 482, incidente 482, caso 482
    for pattern in [r"(?:ticket|incidente|caso|issue|#)\s*(\d{1,6})", r"\b(\d{1,6})\b"]:
        m = re.search(pattern, q)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 999999:
                return val
    return None


def _extract_product_id(question: str) -> int | None:
    """Extrae un ID numérico de producto de la pregunta."""
    q = question.lower()
    for pattern in [r"(?:producto|product|supply|sku|id)\s*[#:]?\s*(\d{1,6})", r"\b(\d{1,6})\b"]:
        m = re.search(pattern, q)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 999999:
                return val
    return None


def _extract_product_name(question: str) -> str | None:
    """Extrae un posible nombre de producto de la pregunta."""
    # Buscar frases como "stock de X", "hay X", "disponibilidad de X"
    q = question.lower()
    for pattern in [
        r"stock\s+(?:de\s+)?(\w+(?:\s+\w+){0,3})",
        r"(?:hay|tengo)\s+(?:stock\s+)?(?:de\s+)?(\w+(?:\s+\w+){0,3})",
        r"disponibilidad\s+(?:de\s+)?(\w+(?:\s+\w+){0,3})",
    ]:
        m = re.search(pattern, q)
        if m:
            candidate = m.group(1).strip()
            # Evitar palabras vacías
            if candidate and len(candidate) > 2:
                return candidate
    return None


def _infer_incident_filters(question: str) -> dict[str, str | None]:
    """Infierer filtros de incidentes desde el texto de la pregunta."""
    q = question.lower()
    filters: dict[str, str | None] = {}

    # Estado
    status_map = {
        "abierto": "open", "abiertos": "open", "open": "open",
        "en progreso": "in_progress", "progreso": "in_progress",
        "resuelto": "resolved", "resueltos": "resolved", "cerrado": "resolved",
        "descartado": "discarded", "descartados": "discarded",
    }
    for word, val in status_map.items():
        if word in q:
            filters["status"] = val
            break

    # Categoría
    category_map = {
        "equipo clínico": "clinical_equipment", "equipo": "clinical_equipment",
        "sistema": "it_system", "ti": "it_system",
        "facturación": "billing_error", "factura": "billing_error",
        "cumplimiento": "compliance_breach", "regulatorio": "compliance_breach",
        "paciente": "patient_experience", "experiencia": "patient_experience",
        "personal": "staff_issue", "staff": "staff_issue",
        "instalación": "facility_issue", "sucursal": "facility_issue",
        "referido": "referral_issue", "referencia": "referral_issue",
    }
    for word, val in category_map.items():
        if word in q:
            filters["category"] = val
            break

    return {k: v for k, v in filters.items() if v is not None}


def _infer_product_category(question: str) -> str | None:
    """Infierer categoría de producto desde la pregunta."""
    q = question.lower()
    category_map = {
        "equipo": "equipment", "equipment": "equipment",
        "medicamento": "medication", "medication": "medication",
        "insumo": "supply", "supply": "supply",
        "instrumental": "instrument", "instrument": "instrument",
    }
    for word, val in category_map.items():
        if word in q:
            return val
    return None


# ── Formateo de respuestas ──────────────────────────────────────────


def _format_incident_response(incidents: list[dict[str, Any]]) -> str:
    """Formatea uno o más incidentes en texto legible."""
    if len(incidents) == 1:
        inc = incidents[0]
        return (
            f"📋 **Ticket #{inc.get('id')}** — {inc.get('title', 'Sin título')}\n"
            f"- **Estado**: {inc.get('status', 'desconocido')}\n"
            f"- **Categoría**: {inc.get('category', 'N/A')}\n"
            f"- **Origen**: {inc.get('origin', 'N/A')}\n"
            f"- **Sucursal**: {inc.get('branch_label') or inc.get('branch', 'N/A')}\n"
            f"- **Creado**: {inc.get('created_at', 'N/A')}\n"
            f"- **Actualizado**: {inc.get('updated_at', 'N/A')}\n"
            f"- **Descripción**: {inc.get('description_preview', 'N/A')}"
        )

    lines = [f"Se encontraron **{len(incidents)}** incidentes:"]
    for inc in incidents:
        lines.append(
            f"- #{inc.get('id')} | {inc.get('status', '?')} | "
            f"{inc.get('category', '?')} | {inc.get('title', '?')[:60]}"
        )
    return "\n".join(lines)


def _format_inventory_response(products: list[dict[str, Any]]) -> str:
    """Formatea uno o más productos en texto legible."""
    if len(products) == 1:
        p = products[0]
        return (
            f"📦 **{p.get('name', 'Producto desconocido')}**\n"
            f"- **SKU**: {p.get('sku', 'N/A')}\n"
            f"- **Categoría**: {p.get('category', 'N/A')}\n"
            f"- **Stock actual**: {p.get('current_stock', 0)} {p.get('unit', 'unidades')}\n"
            f"- **País**: {p.get('country', 'N/A')}\n"
            f"- **Vencimiento**: {p.get('expiry_date', 'N/A')}"
        )

    lines = [f"Se encontraron **{len(products)}** productos:"]
    for p in products:
        lines.append(
            f"- {p.get('name', '?')} (SKU: {p.get('sku', '?')}) → "
            f"stock: {p.get('current_stock', 0)} {p.get('unit', '')}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# 4.  Aristas condicionales — decisiones de enrutamiento explícitas
# ──────────────────────────────────────────────────────────────────────


def route_after_receive(state: AgentState) -> Literal["classify_query", "__end__"]:
    """Decide el siguiente paso después de validar la pregunta.

    Ahora enruta a ``classify_query`` en lugar de directamente a
    ``retrieve_context``. La clasificación decide si toca RAG, tool, o ambos.
    """
    if state.get("error") or not state.get("question_valid", True):
        return "__end__"
    return "classify_query"


def route_after_classify(state: AgentState) -> str:
    """Decide qué nodos ejecutar según la clasificación de la pregunta.

    Retorna el nombre del siguiente nodo: puede ser RAG, una tool, o
    una combinación.  Si la decisión incluye multiple fuentes, el grafo
    ejecuta primero la tool (datos operativos) y luego el RAG
    (conocimiento).
    """
    decision = state.get("routing_decision", "rag")

    routing = {
        "rag": "retrieve_context",
        "incident": "query_incident",
        "inventory": "query_inventory",
        "rag+incident": "query_incident",
        "rag+inventory": "query_inventory",
    }

    node_name = routing.get(decision, "retrieve_context")
    logger.info("route_after_classify: decisión=%s → nodo=%s", decision, node_name)
    return node_name


def route_after_tool(state: AgentState) -> str:
    """Después de una tool, decide si necesita RAG adicional o sintetizar.

    Si la decisión original era combinada (rag+incident, rag+inventory),
    enruta a retrieve_context para obtener contexto adicional.
    Si no, va directo a sintetizar la respuesta de la tool.
    """
    decision = state.get("routing_decision", "")

    if decision in ("rag+incident", "rag+inventory"):
        return "retrieve_context"

    # Si solo era tool, vamos a sintetizar la respuesta
    return "synthesize_tool_answer"


def route_after_retrieve_v2(state: AgentState) -> str:
    """Versión extendida de route_after_retrieve que considera tools.

    Si hay contexto RAG, va a generate_answer aunque haya tools pendientes.
    Si no hay contexto RAG pero sí hay tools, va a synthesize_tool_answer.
    Si no hay nada, responde con honestidad o error.
    """
    has_tool_results = bool(state.get("tool_results"))
    has_rag_context = bool(state.get("retrieved_chunks"))
    decision = state.get("routing_decision", "")

    if state.get("error") and not has_tool_results:
        return "handle_error"

    # Dar prioridad a generate_answer con el contexto RAG recuperado
    if has_rag_context:
        return "generate_answer"

    # Sin RAG pero con tools: sintetizar directamente
    if has_tool_results:
        return "synthesize_tool_answer"

    # Sin nada
    return "respond_no_info"


def route_after_generate(state: AgentState) -> Literal["handle_error", "synthesize_tool_answer", "__end__"]:
    """Después de generar la respuesta RAG, verifica si hay tools pendientes.

    Si la decisión original incluía tools y hay tool_results o tool_errors,
    enruta a synthesize_tool_answer para combinar.  Si no, va a END.
    """
    if state.get("error"):
        return "handle_error"

    has_tool_results = bool(state.get("tool_results"))
    has_tool_errors = bool(state.get("tool_errors"))
    decision = state.get("routing_decision", "")

    if (has_tool_results or has_tool_errors) and decision in ("rag+incident", "rag+inventory"):
        return "synthesize_tool_answer"

    return "__end__"


# ──────────────────────────────────────────────────────────────────────
# 5.  Construcción y compilación del grafo
# ──────────────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    """Construye el grafo con todos los nodos y aristas (Parte 1 + Parte 2).

    Esta función es invocada una sola vez en tiempo de importación.
    Cualquier error estructural (nodo sin conectar, estado mal tipado)
    se detecta aquí, en tiempo de compilación.
    """
    workflow = StateGraph(AgentState)

    # Registrar nodos (Parte 1)
    workflow.add_node("receive_question", node_receive_question)
    workflow.add_node("retrieve_context", node_retrieve_context)
    workflow.add_node("generate_answer", node_generate_answer)
    workflow.add_node("respond_no_info", node_respond_no_info)
    workflow.add_node("handle_error", node_handle_error)

    # Registrar nodos (Parte 2 — tools externas)
    workflow.add_node("classify_query", node_classify_query)
    workflow.add_node("query_incident", node_query_incident)
    workflow.add_node("query_inventory", node_query_inventory)
    workflow.add_node("synthesize_tool_answer", node_synthesize_tool_answer)

    # Arista de entrada: el grafo arranca validando la pregunta
    workflow.set_entry_point("receive_question")

    # ── Aristas condicionales (Parte 1 adaptadas) ────────────────────
    workflow.add_conditional_edges(
        "receive_question",
        route_after_receive,
        {
            "classify_query": "classify_query",
            "__end__": END,
        },
    )

    # ── Aristas (Parte 2 — clasificación → herramientas) ─────────────
    # classify_query dirige a retrieve_context, query_incident o query_inventory
    workflow.add_conditional_edges(
        "classify_query",
        route_after_classify,
        {
            "retrieve_context": "retrieve_context",
            "query_incident": "query_incident",
            "query_inventory": "query_inventory",
        },
    )

    # Después de una tool: ¿necesita RAG adicional o sintetiza?
    workflow.add_conditional_edges(
        "query_incident",
        route_after_tool,
        {
            "retrieve_context": "retrieve_context",
            "synthesize_tool_answer": "synthesize_tool_answer",
        },
    )

    workflow.add_conditional_edges(
        "query_inventory",
        route_after_tool,
        {
            "retrieve_context": "retrieve_context",
            "synthesize_tool_answer": "synthesize_tool_answer",
        },
    )

    # Después de retrieve_context: versión que considera tools
    workflow.add_conditional_edges(
        "retrieve_context",
        route_after_retrieve_v2,
        {
            "generate_answer": "generate_answer",
            "respond_no_info": "respond_no_info",
            "handle_error": "handle_error",
            "synthesize_tool_answer": "synthesize_tool_answer",
        },
    )

    # Después de generate_answer: ¿tools pendientes o END?
    workflow.add_conditional_edges(
        "generate_answer",
        route_after_generate,
        {
            "handle_error": "handle_error",
            "synthesize_tool_answer": "synthesize_tool_answer",
            "__end__": END,
        },
    )

    # Nodos terminales
    workflow.add_edge("respond_no_info", END)
    workflow.add_edge("handle_error", END)
    workflow.add_edge("synthesize_tool_answer", END)

    return workflow


# ── Alias de compatibilidad hacia atrás ────────────────────────────
# Los tests de la Parte 1 importan route_after_retrieve por nombre.
# Mantenemos el alias para no romperlos.
route_after_retrieve = route_after_retrieve_v2


def _compile_graph() -> StateGraph:
    """Compila el grafo con checkpointing.

    El checkpointing (MemorySaver) permite inspeccionar o retomar
    cualquier corrida.  La compilación falla en tiempo de importación
    si hay errores estructurales.
    """
    workflow = _build_graph()
    # MemorySaver almacena checkpoints en memoria para cada transición.
    # En producción se reemplazaría por un saver persistente (Postgres, etc.).
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# ── Grafo compilado (singleton) ──────────────────────────────────────
# La compilación ocurre al importar este módulo.  Cualquier error
# estructural — nodo sin conectar, edge apuntando a un nodo inexistente,
# tipo de estado inconsistente — se detecta aquí y no en producción.
try:
    agent_graph = _compile_graph()
    logger.info(
        "Grafo LangGraph compilado correctamente con %d nodos.",
        len(agent_graph.nodes),
    )
except Exception as exc:
    logger.critical("Error al compilar el grafo LangGraph: %s", exc)
    raise


# ──────────────────────────────────────────────────────────────────────
# 6.  Función de ejecución pública
# ──────────────────────────────────────────────────────────────────────


async def run_agent(question: str, run_id: str | None = None) -> AgentState:
    """Ejecuta el agente completo para una pregunta (async).

    Llama al grafo compilado vía ainvoke, lo que permite que los nodos
    asíncronos (query_incident, query_inventory) funcionen correctamente.

    Args:
        question: Pregunta del usuario.
        run_id:   Identificador único para esta corrida (opcional).
                  Si no se proporciona, se genera uno automáticamente.

    Returns:
        El estado final del grafo, incluyendo answer, trace_events y
        routing_log.

    Raises:
        ValueError: Si la pregunta está vacía o es demasiado corta.
        RuntimeError: Si el grafo falla estructuralmente.
    """
    question = question.strip() if question else ""

    if not question:
        raise ValueError("La pregunta no puede estar vacía.")
    if len(question) < 3:
        raise ValueError(
            "La pregunta es demasiado corta (mínimo 3 caracteres)."
        )

    if run_id is None:
        import uuid
        run_id = str(uuid.uuid4())

    initial_state = build_initial_state(question)

    # Configuración de la corrida con thread_id para checkpointing
    config = {
        "configurable": {"thread_id": run_id},
    }

    logger.info("Ejecutando agente (run_id=%s): '%s'", run_id, question[:100])

    # Invocar el grafo compilado — ainvoke permite nodos async
    final_state: AgentState = await agent_graph.ainvoke(initial_state, config=config)

    # Persistir la traza
    persist_trace(final_state, run_id)

    return final_state


# ──────────────────────────────────────────────────────────────────────
# 7.  Consultar trazas (para debugging y evals)
# ──────────────────────────────────────────────────────────────────────


def get_trace(run_id: str) -> dict[str, Any] | None:
    """Recupera una traza persistida por su run_id.

    Args:
        run_id: Identificador único de la corrida.

    Returns:
        El dict de la traza, o None si no existe.
    """
    trace_path = _TRACE_DIR / f"{run_id}.json"
    if not trace_path.exists():
        return None
    return json.loads(trace_path.read_text(encoding="utf-8"))


def list_traces(limit: int = 20) -> list[dict[str, Any]]:
    """Lista las trazas más recientes.

    Args:
        limit: Número máximo de trazas a devolver.

    Returns:
        Lista de dicts con metadatos de cada traza (sin los events completos).
    """
    traces = sorted(_TRACE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for trace_path in traces[:limit]:
        data = json.loads(trace_path.read_text(encoding="utf-8"))
        # Resumen ligero sin los events completos
        result.append({
            "run_id": data.get("run_id"),
            "question": data.get("question"),
            "num_events": len(data.get("events", [])),
            "error": data.get("error"),
            "timestamp": data.get("timestamp"),
        })
    return result