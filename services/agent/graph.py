"""
services/agent/graph.py — Grafo LangGraph del agente de soporte HealthCore.

Define:
  - AgentState: estado mínimo y explícito que viaja entre nodos.
  - Nodos con responsabilidad única (recibir, recuperar, generar, fallback, error).
  - Aristas condicionales que deciden el flujo según resultados reales.
  - Grafo compilado con checkpointing para trazabilidad completa.

El grafo se compila al importar este módulo (falla en tiempo de build
si hay errores estructurales). No se necesita una ejecución para detectar
errores de tipado o conectividad entre nodos.
"""

from __future__ import annotations

import json
import logging
import operator
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

# Reutilizamos las funciones RAG existentes — sin duplicar lógica.
from data.pipelines.rag import generate_answer, retrieve

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
    ejecutar su responsabilidad y decidir el siguiente paso.  No incluye
    el historial completo de la conversación — eso vive en el checkpoint.

    Atributos:
        question:         Pregunta original del usuario (validada).
        retrieved_chunks: Fragmentos recuperados de Qdrant (lista de dicts).
        answer:           Respuesta final generada o mensaje de fallback.
        error:            Mensaje de error si un nodo falló (None si ok).
        trace_events:     Lista de eventos estructurados de la corrida.
                          Se acumula entre nodos (reducer: add).
        routing_log:      Decisión de enrutamiento en cada bifurcación.
                          Se acumula entre nodos (reducer: add).
        question_valid:   Booleano que indica si la pregunta es válida.
    """

    question: str
    retrieved_chunks: list[dict[str, Any]]
    answer: str
    error: Optional[str]
    trace_events: Annotated[list[dict[str, Any]], _accumulate_list]
    routing_log: Annotated[list[str], _accumulate_list]
    question_valid: bool


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
    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False))
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
        "routing_log": ["receive_question → retrieve_context (pregunta válida)"],
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


# ──────────────────────────────────────────────────────────────────────
# 4.  Aristas condicionales — decisiones de enrutamiento explícitas
# ──────────────────────────────────────────────────────────────────────


def route_after_receive(state: AgentState) -> Literal["retrieve_context", "__end__"]:
    """Decide el siguiente paso después de validar la pregunta.

    Condición: si la pregunta es inválida (vacía, muy corta) o hay error,
    enruta a END.  Si es válida, enruta a retrieve_context.
    """
    if state.get("error") or not state.get("question_valid", True):
        return "__end__"
    return "retrieve_context"


def route_after_retrieve(state: AgentState) -> Literal["generate_answer", "respond_no_info", "handle_error"]:
    """Decide el siguiente paso después de recuperar contexto.

    Condiciones:
      - Si hubo error → handle_error.
      - Si no se recuperaron fragmentos (vacío o bajo umbral) → respond_no_info.
      - Si hay fragmentos → generate_answer.
    """
    if state.get("error"):
        return "handle_error"
    if not state.get("retrieved_chunks"):
        return "respond_no_info"
    return "generate_answer"


def route_after_generate(state: AgentState) -> Literal["handle_error", "__end__"]:
    """Decide el siguiente paso después de generar la respuesta.

    Si hubo error durante la generación, enruta a handle_error.
    Si todo ok, enruta a END.
    """
    if state.get("error"):
        return "handle_error"
    return "__end__"


# ──────────────────────────────────────────────────────────────────────
# 5.  Construcción y compilación del grafo
# ──────────────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    """Construye el grafo con todos los nodos y aristas.

    Esta función es invocada una sola vez en tiempo de importación.
    Cualquier error estructural (nodo sin conectar, estado mal tipado)
    se detecta aquí, en tiempo de compilación.
    """
    workflow = StateGraph(AgentState)

    # Registrar nodos
    workflow.add_node("receive_question", node_receive_question)
    workflow.add_node("retrieve_context", node_retrieve_context)
    workflow.add_node("generate_answer", node_generate_answer)
    workflow.add_node("respond_no_info", node_respond_no_info)
    workflow.add_node("handle_error", node_handle_error)

    # Arista de entrada: el grafo siempre arranca validando la pregunta
    workflow.set_entry_point("receive_question")

    # Aristas condicionales
    workflow.add_conditional_edges(
        "receive_question",
        route_after_receive,
        {
            "retrieve_context": "retrieve_context",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "retrieve_context",
        route_after_retrieve,
        {
            "generate_answer": "generate_answer",
            "respond_no_info": "respond_no_info",
            "handle_error": "handle_error",
        },
    )

    workflow.add_conditional_edges(
        "generate_answer",
        route_after_generate,
        {
            "handle_error": "handle_error",
            "__end__": END,
        },
    )

    # Aristas directas a END para nodos terminales
    workflow.add_edge("respond_no_info", END)
    workflow.add_edge("handle_error", END)

    return workflow


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


def run_agent(question: str, run_id: str | None = None) -> AgentState:
    """Ejecuta el agente completo para una pregunta.

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

    # Invocar el grafo compilado
    final_state: AgentState = agent_graph.invoke(initial_state, config=config)

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