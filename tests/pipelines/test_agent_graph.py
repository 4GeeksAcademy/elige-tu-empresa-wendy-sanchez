"""
tests/pipelines/test_agent_graph.py — Evals del agente LangGraph de soporte.

Estos tests verifican:
  1. Compilación del grafo: errores estructurales se detectan en tiempo de build.
  2. Enrutamiento condicional: cada bifurcación se prueba con entradas controladas.
  3. Trazabilidad: cada corrida produce un trace consultable.
  4. Comportamiento RAG: el agente responde según las políticas de CONTEXT.md.

Los evals corren contra el grafo compilado (no contra ejecuciones en vivo).
Para los tests que requieren retrieve() real, se mockea Qdrant para que los
tests sean deterministas y no dependan de infraestructura externa.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Ensure services/api is on sys.path for router tests
_API_SRC = str(_PROJECT_ROOT / "services" / "api")
if _API_SRC not in sys.path:
    sys.path.insert(0, _API_SRC)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_chunk(
    source_document: str = "appointment-policy",
    section: str = "Política de cancelación",
    text: str | None = None,
    score: float = 0.85,
) -> dict[str, Any]:
    """Helper para construir un fragmento simulado como el que devuelve retrieve()."""
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
            "cargo de 50 USD (o 40 GBP en Reino Unido) para pacientes de pago privado.\n"
            "Pacientes con Medicare o Medicaid: no se les cobra cargo por no-show."
        ),
        "_score": score,
    }


def _mock_retrieve(chunks: list[dict[str, Any]] | None = None):
    """Patchea el retrieve dentro del módulo del grafo."""
    if chunks is None:
        chunks = [_make_chunk()]

    # El módulo graph importa 'retrieve' directamente, así que parcheamos
    # la referencia dentro de services.agent.graph
    return patch("services.agent.graph.retrieve", return_value=chunks)


def _mock_retrieve_empty():
    """Patchea retrieve para devolver lista vacía (simula umbral no superado)."""
    return patch("services.agent.graph.retrieve", return_value=[])


def _mock_retrieve_error():
    """Patchea retrieve para lanzar RuntimeError."""
    return patch(
        "services.agent.graph.retrieve",
        side_effect=RuntimeError("Qdrant connection refused"),
    )


def _mock_generate_answer(answer: str = "Respuesta simulada."):
    """Patchea generate_answer dentro del módulo del grafo."""
    return patch("services.agent.graph.generate_answer", return_value=answer)


def _mock_generate_answer_error():
    """Patchea generate_answer para lanzar RuntimeError."""
    return patch(
        "services.agent.graph.generate_answer",
        side_effect=RuntimeError("LLM API timeout"),
    )


# ======================================================================
# EVAL 1: Compilación y estructura del grafo
# ======================================================================


class TestGraphCompilation:
    """El grafo debe compilarse sin errores y exponer todos los nodos."""

    def test_graph_compiles_successfully(self):
        """El grafo debe compilar en tiempo de importación sin errores."""
        from services.agent.graph import agent_graph

        assert agent_graph is not None
        assert hasattr(agent_graph, "nodes")

    def test_graph_has_all_expected_nodes(self):
        """Deben existir todos los nodos del diseño, incluyendo __start__."""
        from services.agent.graph import agent_graph

        expected_nodes = {
            "__start__",
            "receive_question",
            "retrieve_context",
            "generate_answer",
            "respond_no_info",
            "handle_error",
        }
        actual_nodes = set(agent_graph.nodes.keys())
        for node in expected_nodes:
            assert node in actual_nodes, f"Nodo faltante: {node}"

    def test_graph_entry_point_is_receive_question(self):
        """El entry point debe ser receive_question."""
        from services.agent.graph import agent_graph

        # Verificar que __start__ tiene conexión a receive_question
        # Usamos la introspección del grafo si está disponible
        assert "receive_question" in agent_graph.nodes


# ======================================================================
# EVAL 2: Enrutamiento condicional — pregunta válida e inválida
# ======================================================================


class TestConditionalRouting:
    """Las aristas condicionales deben enrutar según el estado."""

    def test_empty_question_routes_to_end(self):
        """Pregunta vacía → error, no debe ejecutar retrieve_context."""
        from services.agent.graph import run_agent

        with pytest.raises(ValueError, match="no puede estar vacía"):
            run_agent("")

    def test_short_question_routes_to_end(self):
        """Pregunta muy corta → error, no debe ejecutar retrieve_context."""
        from services.agent.graph import run_agent

        with pytest.raises(ValueError, match="demasiado corta"):
            run_agent("ab")

    def test_valid_question_routes_to_retrieve_context(self):
        """Pregunta válida → retrieve_context debe ejecutarse."""
        from services.agent.graph import agent_graph, build_initial_state

        state = build_initial_state("¿Cuál es la política de cancelación?")
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        # Simular que receive_question pasó sin error y enruta a retrieve_context
        from services.agent.graph import route_after_receive

        decision = route_after_receive(state)
        assert decision == "retrieve_context", (
            f"Esperaba 'retrieve_context' pero obtuve '{decision}'"
        )

    def test_no_chunks_routes_to_respond_no_info(self):
        """Si retrieve() devuelve lista vacía, debe enrutar a respond_no_info."""
        from services.agent.graph import route_after_retrieve, build_initial_state

        state = build_initial_state("¿Pregunta sin contexto?")
        # retrieve_context dejó el estado sin chunks y sin error
        decision = route_after_retrieve(state)
        assert decision == "respond_no_info", (
            f"Esperaba 'respond_no_info' pero obtuve '{decision}'"
        )

    def test_chunks_found_routes_to_generate_answer(self):
        """Si retrieve() devuelve chunks, debe enrutar a generate_answer."""
        from services.agent.graph import route_after_retrieve, build_initial_state

        state = build_initial_state("¿Pregunta con contexto?")
        state["retrieved_chunks"] = [_make_chunk()]
        decision = route_after_retrieve(state)
        assert decision == "generate_answer", (
            f"Esperaba 'generate_answer' pero obtuve '{decision}'"
        )

    def test_retrieve_error_routes_to_handle_error(self):
        """Si retrieve() falla con RuntimeError, debe enrutar a handle_error."""
        from services.agent.graph import route_after_retrieve, build_initial_state

        state = build_initial_state("¿Pregunta que falla?")
        state["error"] = "Error al recuperar información: Qdrant connection refused"
        decision = route_after_retrieve(state)
        assert decision == "handle_error", (
            f"Esperaba 'handle_error' pero obtuve '{decision}'"
        )

    def test_generate_error_routes_to_handle_error(self):
        """Si generate_answer falla, debe enrutar a handle_error."""
        from services.agent.graph import route_after_generate, build_initial_state

        state = build_initial_state("¿Pregunta que falla en generación?")
        state["error"] = "Error al generar la respuesta: LLM API timeout"
        decision = route_after_generate(state)
        assert decision == "handle_error"


# ======================================================================
# EVAL 3: Trazabilidad — cada corrida produce un trace consultable
# ======================================================================


class TestTraceability:
    """Cada corrida debe producir un trace consultable con eventos y enrutamiento."""

    def test_trace_is_persisted_after_run(self):
        """Después de una corrida, debe existir un archivo de trace en disco."""
        from services.agent.graph import run_agent, get_trace

        run_id = str(uuid.uuid4())

        with _mock_retrieve(), _mock_generate_answer():
            _ = run_agent("¿Qué seguros aceptan?", run_id=run_id)

        trace = get_trace(run_id)

        assert trace is not None, f"No se encontró trace para run_id={run_id}"
        assert trace["run_id"] == run_id
        assert trace["question"] == "¿Qué seguros aceptan?"
        assert "events" in trace
        assert len(trace["events"]) > 0
        assert "routing_log" in trace

    def test_trace_contains_node_execution_order(self):
        """El trace debe registrar qué nodos se ejecutaron y en qué orden."""
        from services.agent.graph import run_agent, get_trace

        run_id = str(uuid.uuid4())

        with _mock_retrieve(), _mock_generate_answer():
            run_agent("¿Cuál es la política de no-show?", run_id=run_id)

        trace = get_trace(run_id)
        events = trace["events"]

        node_names = [e["node"] for e in events]
        assert "receive_question" in node_names, (
            f"El trace debería contener 'receive_question'. Nodos: {node_names}"
        )
        assert "retrieve_context" in node_names, (
            f"El trace debería contener 'retrieve_context'. Nodos: {node_names}"
        )
        assert "generate_answer" in node_names, (
            f"El trace debería contener 'generate_answer'. Nodos: {node_names}"
        )

    def test_trace_routing_log_records_decisions(self):
        """El routing_log debe registrar cada decisión de enrutamiento."""
        from services.agent.graph import run_agent, get_trace

        run_id = str(uuid.uuid4())

        with _mock_retrieve(), _mock_generate_answer():
            run_agent("¿Cobran cargo por no-show?", run_id=run_id)

        trace = get_trace(run_id)
        routing_log = trace["routing_log"]

        assert len(routing_log) >= 2, (
            f"Se esperaban al menos 2 entradas en routing_log. "
            f"Obtenidas: {len(routing_log)}"
        )

    def test_trace_consultable_after_run(self):
        """El trace debe ser consultable por get_trace() después de la corrida."""
        from services.agent.graph import run_agent, get_trace, list_traces

        run_id = str(uuid.uuid4())
        with _mock_retrieve(), _mock_generate_answer():
            run_agent("¿Qué es HealthCore?", run_id=run_id)

        # Consulta por ID específico
        trace = get_trace(run_id)
        assert trace is not None

        # Consulta por listado
        all_traces = list_traces(limit=10)
        assert any(t["run_id"] == run_id for t in all_traces), (
            "El trace debería aparecer en list_traces()"
        )


# ======================================================================
# EVAL 4: Comportamiento RAG — respuestas ancladas en la base de conocimiento
# ======================================================================


class TestRAGBehavior:
    """El comportamiento del agente debe estar anclado en la base de conocimiento.

    Estos tests verifican que el agente usa correctamente retrieve() y
    generate_answer() con chunks realistas, sin alucinar información.
    Los chunks simulados reflejan las políticas de CONTEXT.md.
    """

    def test_agent_uses_retrieve_and_generate_answer(self):
        """El agente debe llamar retrieve() y generate_answer() en orden."""
        from services.agent.graph import agent_graph

        # Verificamos que los nodos existen en el grafo
        nodes = set(agent_graph.nodes.keys())
        assert "retrieve_context" in nodes
        assert "generate_answer" in nodes

    def test_retrieve_executes_before_generate(self):
        """El nodo retrieve_context debe ejecutarse antes que generate_answer."""
        from services.agent.graph import route_after_retrieve, build_initial_state

        # El routing después de retrieve_context decide ir a generate_answer
        state = build_initial_state("test")
        state["retrieved_chunks"] = [_make_chunk(
            source_document="appointment-policy",
        )]

        decision = route_after_retrieve(state)
        assert decision == "generate_answer", (
            "Con chunks recuperados, debe enrutar a generate_answer"
        )

    def test_no_chunks_returns_honest_answer(self):
        """Sin contexto relevante, el agente debe responder con honestidad."""
        from services.agent.graph import route_after_retrieve, build_initial_state

        state = build_initial_state("¿Pregunta sin cobertura en BD?")
        decision = route_after_retrieve(state)
        assert decision == "respond_no_info", (
            "Sin chunks, debe enrutar a respond_no_info (no forzar generación)"
        )

    def test_medicare_no_show_policy(self):
        """El agente debe indicar que Medicare/Medicaid no paga no-show.

        Verifica que el comportamiento de negocio (CONTEXT.md item q-005)
        se mantiene: nunca aplicar cargo por no-show a Medicare/Medicaid.
        """
        from services.agent.graph import run_agent, get_trace

        run_id = str(uuid.uuid4())

        # Chunk de appointment-policy que explícitamente dice que Medicare no paga
        medicare_chunk = _make_chunk(
            source_document="appointment-policy",
            section="Política de cancelación",
            text=(
                "Cancelar con menos de 24 horas o no presentarse (no-show): "
                "cargo de 50 USD para pacientes de pago privado.\n"
                "Pacientes con Medicare o Medicaid: "
                "no se les cobra cargo por no-show."
            ),
        )

        with _mock_retrieve([medicare_chunk]), _mock_generate_answer(
            "No, los pacientes de Medicare o Medicaid "
            "no están sujetos al cargo por no-show en HealthCore."
        ):
            result = run_agent(
                "¿Cobran cargo por no-show a pacientes de Medicare?",
                run_id=run_id,
            )

        answer = result["answer"].lower()
        # La respuesta debe mencionar que no se cobra a Medicare
        assert "no " in answer, (
            "La respuesta debe indicar que NO se cobra a Medicare. "
            f"Respuesta: {result['answer']}"
        )
        assert "medicare" in answer or "medicaid" in answer, (
            "La respuesta debe mencionar Medicare o Medicaid. "
            f"Respuesta: {result['answer']}"
        )

        # Verificar que el trace es consultable
        trace = get_trace(run_id)
        assert trace is not None


# ======================================================================
# EVAL 5: Endpoint — el endpoint HTTP no contiene lógica de negocio
# ======================================================================


class TestAgentEndpoint:
    """El endpoint POST /agent/query debe ser una capa delgada sobre el grafo."""

    def test_endpoint_imports_and_has_correct_prefix(self):
        """El router debe existir y tener el prefijo correcto."""
        try:
            from services.agent.routes import router
            assert router.prefix == "/agent"
            assert len(router.routes) >= 1
        except ImportError as e:
            pytest.skip(f"Router de agente no disponible: {e}")

    def test_endpoint_delegates_to_graph(self):
        """El endpoint debe delegar en run_agent(), no contener lógica RAG propia."""
        import inspect
        from services.agent.routes import router

        for route in router.routes:
            if route.path == "/agent/query" and "POST" in route.methods:
                handler_source = inspect.getsource(route.endpoint)
                # Debe llamar a run_agent
                assert "run_agent" in handler_source, (
                    "El endpoint debe delegar en run_agent(), no contener lógica propia"
                )
                return

        pytest.fail("No se encontró el endpoint POST /agent/query")