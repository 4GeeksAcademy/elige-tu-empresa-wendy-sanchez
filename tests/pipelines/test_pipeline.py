"""Tests unitarios para las funciones de transformación del pipeline.

Verifica 6 funciones de ``data.pipelines.transform``:
- ``validate_event``
- ``deduplicate_events``
- ``aggregate_kpis``
- ``verify_kpis``
- ``_parse_cost``
- ``_safe_int``

Usa datos en memoria, sin dependencias externas ni base de datos.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

# Asegurar que el proyecto raíz está en sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data.pipelines.transform import (
    validate_event,
    deduplicate_events,
    aggregate_kpis,
    verify_kpis,
    _parse_cost,
    _safe_int,
)


# ======================================================================
# Tests para _parse_cost
# ======================================================================


class TestParseCost:
    """Cobertura: coste válido, ausente, nulo, no convertible."""

    def test_with_cost(self) -> None:
        """Debe extraer el coste como Decimal."""
        assert _parse_cost({"cost": "123.45"}) == Decimal("123.45")

    def test_with_total_cost(self) -> None:
        """Debe aceptar ``total_cost`` como alternativa."""
        assert _parse_cost({"total_cost": "99.99"}) == Decimal("99.99")

    def test_cost_is_number(self) -> None:
        """Debe convertir número directamente."""
        assert _parse_cost({"cost": 42}) == Decimal("42")

    def test_no_cost_key(self) -> None:
        """Debe devolver None si no hay clave de coste."""
        assert _parse_cost({"foo": "bar"}) is None

    def test_empty_tags(self) -> None:
        """Debe devolver None si tags está vacío."""
        assert _parse_cost({}) is None

    def test_invalid_cost(self) -> None:
        """Debe devolver None si el coste no es convertible."""
        assert _parse_cost({"cost": "not-a-number"}) is None

    def test_none_cost(self) -> None:
        """Debe devolver None si el coste es None."""
        assert _parse_cost({"cost": None}) is None


# ======================================================================
# Tests para _safe_int
# ======================================================================


class TestSafeInt:
    """Cobertura: entero, string, None, float, inválido."""

    def test_valid_int(self) -> None:
        assert _safe_int(42) == 42

    def test_valid_string(self) -> None:
        assert _safe_int("42") == 42

    def test_none(self) -> None:
        assert _safe_int(None) == 0

    def test_float_string(self) -> None:
        """String con decimal debe truncarse."""
        assert _safe_int("3.14") == 0  # int("3.14") lanza ValueError

    def test_non_numeric(self) -> None:
        assert _safe_int("abc") == 0

    def test_infinity_float(self) -> None:
        """float('inf') debe convertirse a 0."""
        assert _safe_int(float('inf')) == 0  # OverflowError


# ======================================================================
# Tests para validate_event
# ======================================================================


class TestValidateEvent:
    """Cobertura: válido, sin clinic_id, sin country, país desconocido, tags/root."""

    def test_valid_us_event(self) -> None:
        """Evento US con todos los campos."""
        event = {"event_id": "ev1", "clinic_id": "CLI-001", "country": "US", "tags": {}}
        valid, reason = validate_event(event)
        assert valid is True
        assert reason is None

    def test_valid_uk_event(self) -> None:
        """Evento UK válido."""
        event = {"event_id": "ev2", "clinic_id": "CLI-002", "country": "UK", "tags": {}}
        valid, reason = validate_event(event)
        assert valid is True
        assert reason is None

    def test_missing_clinic_id(self) -> None:
        """Debe rechazar si falta clinic_id."""
        event = {"event_id": "ev3", "country": "US", "tags": {}}
        valid, reason = validate_event(event)
        assert valid is False
        assert "clinic_id" in reason

    def test_missing_country(self) -> None:
        """Debe rechazar si falta country."""
        event = {"event_id": "ev4", "clinic_id": "CLI-001", "tags": {}}
        valid, reason = validate_event(event)
        assert valid is False
        assert "country" in reason

    def test_unknown_country(self) -> None:
        """Debe rechazar si el país no es US ni UK."""
        event = {"event_id": "ev5", "clinic_id": "CLI-001", "country": "AR", "tags": {}}
        valid, reason = validate_event(event)
        assert valid is False
        assert "desconocido" in reason or "unknown" in reason.lower()

    def test_clinic_id_in_tags(self) -> None:
        """Debe leer clinic_id desde tags si no está en root."""
        event = {"event_id": "ev6", "country": "US", "tags": {"clinic_id": "CLI-003"}}
        valid, reason = validate_event(event)
        assert valid is True
        assert reason is None

    def test_country_in_tags(self) -> None:
        """Debe leer country desde tags si no está en root."""
        event = {"event_id": "ev7", "clinic_id": "CLI-001", "tags": {"country": "UK"}}
        valid, reason = validate_event(event)
        assert valid is True
        assert reason is None


# ======================================================================
# Tests para deduplicate_events
# ======================================================================


class TestDeduplicateEvents:
    """Cobertura: sin duplicados, con duplicados, todos duplicados, vacío."""

    def test_no_duplicates(self) -> None:
        events = [
            {"event_id": "a", "data": 1},
            {"event_id": "b", "data": 2},
            {"event_id": "c", "data": 3},
        ]
        unique, removed = deduplicate_events(events)
        assert len(unique) == 3
        assert removed == 0

    def test_some_duplicates(self) -> None:
        events = [
            {"event_id": "a", "data": 1},
            {"event_id": "b", "data": 2},
            {"event_id": "a", "data": 100},  # duplicado, se conserva el primero
        ]
        unique, removed = deduplicate_events(events)
        assert len(unique) == 2
        assert removed == 1
        # El primer ocurrencia debe conservarse
        assert unique[0]["data"] == 1

    def test_all_duplicates(self) -> None:
        events = [
            {"event_id": "x", "data": "first"},
            {"event_id": "x", "data": "second"},
            {"event_id": "x", "data": "third"},
        ]
        unique, removed = deduplicate_events(events)
        assert len(unique) == 1
        assert removed == 2
        assert unique[0]["data"] == "first"

    def test_empty_list(self) -> None:
        unique, removed = deduplicate_events([])
        assert unique == []
        assert removed == 0

    def test_missing_event_id(self) -> None:
        """Evento sin event_id se conserva (no tiene clave de duplicado)."""
        events = [
            {"data": 1},
            {"data": 2},
        ]
        unique, removed = deduplicate_events(events)
        assert len(unique) == 2
        assert removed == 0


# ======================================================================
# Tests para aggregate_kpis (con cálculos manuales verificados)
# ======================================================================


class TestAggregateKpis:
    """Cobertura: todos los tipos de evento, múltiples clínicas,
    costes variados, eventos vacíos, sin coste."""

    @staticmethod
    def _make_event(
        event_id: str,
        event_type: str,
        clinic_id: str = "CLI-001",
        country: str = "US",
        cost: str | None = None,
    ) -> dict:
        """Helper para construir un evento de prueba."""
        tags = {"clinic_id": clinic_id, "country": country}
        if cost is not None:
            tags["cost"] = cost
        return {
            "event_id": event_id,
            "event_type": event_type,
            "clinic_id": clinic_id,
            "country": country,
            "tags": tags,
        }

    def test_all_event_types_one_clinic(self) -> None:
        """Calcula KPI manualmente para una clínica con todos los tipos."""
        month = date(2025, 1, 1)
        events = [
            self._make_event("e1", "inbound_order_created", cost="150.00"),
            self._make_event("e2", "outbound_order_created"),
            self._make_event("e3", "outbound_order_created"),
            self._make_event("e4", "stock_threshold_triggered"),
            self._make_event("e5", "supply_expiry_flagged"),
        ]
        result = aggregate_kpis(events, month)

        assert len(result) == 1
        row = result[0]
        assert row["clinic_id"] == "CLI-001"
        assert row["country"] == "US"
        assert row["currency"] == "USD"
        assert row["total_supply_cost"] == Decimal("150.00")
        assert row["supply_consumption_count"] == 2
        assert row["critical_stockout_count"] == 1
        assert row["expiry_risk_count"] == 1
        assert row["month_start"] == month

    def test_multiple_clinics(self) -> None:
        """Debe producir una fila por clínica."""
        month = date(2025, 1, 1)
        events = [
            self._make_event("e1", "inbound_order_created", "CLI-001", "US", cost="100"),
            self._make_event("e2", "outbound_order_created", "CLI-002", "UK"),
            self._make_event("e3", "outbound_order_created", "CLI-001", "US"),
        ]
        result = aggregate_kpis(events, month)

        assert len(result) == 2

        # Ordenado por clinic_id
        cli1 = result[0]
        assert cli1["clinic_id"] == "CLI-001"
        assert cli1["total_supply_cost"] == Decimal("100")
        assert cli1["supply_consumption_count"] == 1

        cli2 = result[1]
        assert cli2["clinic_id"] == "CLI-002"
        assert cli2["country"] == "UK"
        assert cli2["currency"] == "GBP"
        assert cli2["total_supply_cost"] == Decimal("0.00")
        assert cli2["supply_consumption_count"] == 1

    def test_hand_calculated_kpis(self) -> None:
        """Verificación manual de 4 eventos de distintos tipos para 2 clínicas.

        CLI-001 (US):
          - inbound_order_created, cost=200.50
          - outbound_order_created
          - supply_expiry_flagged
        Esperado: cost=200.50, consumption=1, stockout=0, expiry=1

        CLI-003 (UK):
          - inbound_order_created, cost=99.99
          - stock_threshold_triggered
          - stock_threshold_triggered
        Esperado: cost=99.99, consumption=0, stockout=2, expiry=0
        """
        month = date(2025, 3, 1)
        events = [
            self._make_event("e1", "inbound_order_created", "CLI-001", "US", cost="200.50"),
            self._make_event("e2", "outbound_order_created", "CLI-001", "US"),
            self._make_event("e3", "supply_expiry_flagged", "CLI-001", "US"),
            self._make_event("e4", "inbound_order_created", "CLI-003", "UK", cost="99.99"),
            self._make_event("e5", "stock_threshold_triggered", "CLI-003", "UK"),
            self._make_event("e6", "stock_threshold_triggered", "CLI-003", "UK"),
        ]
        result = aggregate_kpis(events, month)

        # Orden alfabético: CLI-001, CLI-003
        assert len(result) == 2

        r1 = result[0]
        assert r1["clinic_id"] == "CLI-001"
        assert r1["total_supply_cost"] == Decimal("200.50")
        assert r1["supply_consumption_count"] == 1
        assert r1["critical_stockout_count"] == 0
        assert r1["expiry_risk_count"] == 1
        assert r1["currency"] == "USD"

        r2 = result[1]
        assert r2["clinic_id"] == "CLI-003"
        assert r2["total_supply_cost"] == Decimal("99.99")
        assert r2["supply_consumption_count"] == 0
        assert r2["critical_stockout_count"] == 2
        assert r2["expiry_risk_count"] == 0
        assert r2["currency"] == "GBP"
        assert r2["country"] == "UK"

    def test_empty_events(self) -> None:
        """Caso extremo: lista vacía."""
        result = aggregate_kpis([], date(2025, 1, 1))
        assert result == []

    def test_missing_cost_in_inbound(self) -> None:
        """inbound sin coste no debe modificar total_supply_cost."""
        month = date(2025, 1, 1)
        events = [
            self._make_event("e1", "inbound_order_created", cost=None),
        ]
        result = aggregate_kpis(events, month)
        assert len(result) == 1
        assert result[0]["total_supply_cost"] == Decimal("0.00")

    def test_unknown_event_type(self) -> None:
        """Tipo de evento desconocido debe ignorarse."""
        month = date(2025, 1, 1)
        events = [
            {"event_id": "e1", "event_type": "unknown_type", "clinic_id": "CLI-001", "country": "US", "tags": {}},
        ]
        result = aggregate_kpis(events, month)
        assert len(result) == 1
        assert result[0]["total_supply_cost"] == Decimal("0.00")
        assert result[0]["supply_consumption_count"] == 0
        assert result[0]["critical_stockout_count"] == 0
        assert result[0]["expiry_risk_count"] == 0

    def test_clinic_id_from_tags(self) -> None:
        """Debe leer clinic_id desde tags si está presente."""
        month = date(2025, 1, 1)
        events = [
            {
                "event_id": "e1",
                "event_type": "outbound_order_created",
                "country": "US",
                "tags": {"clinic_id": "CLI-005", "country": "US"},
            }
        ]
        result = aggregate_kpis(events, month)
        assert len(result) == 1
        assert result[0]["clinic_id"] == "CLI-005"


# ======================================================================
# Tests para verify_kpis
# ======================================================================


class TestVerifyKpis:
    """Cobertura: sin advertencias, coste negativo, moneda incorrecta."""

    def test_no_warnings(self) -> None:
        """Datos correctos no deben generar advertencias."""
        rows = [
            {"clinic_id": "CLI-001", "country": "US", "currency": "USD",
             "total_supply_cost": Decimal("100"), "supply_consumption_count": 5,
             "critical_stockout_count": 0, "expiry_risk_count": 1},
        ]
        assert verify_kpis(rows) == []

    def test_negative_cost(self) -> None:
        """Coste negativo debe generar advertencia."""
        rows = [
            {"clinic_id": "CLI-001", "country": "US", "currency": "USD",
             "total_supply_cost": Decimal("-50"), "supply_consumption_count": 0,
             "critical_stockout_count": 0, "expiry_risk_count": 0},
        ]
        warnings = verify_kpis(rows)
        assert len(warnings) >= 1
        assert any("negativo" in w for w in warnings)

    def test_uk_with_usd(self) -> None:
        """Clínica UK con USD debe generar advertencia."""
        rows = [
            {"clinic_id": "CLI-002", "country": "UK", "currency": "USD",
             "total_supply_cost": Decimal("0"), "supply_consumption_count": 0,
             "critical_stockout_count": 0, "expiry_risk_count": 0},
        ]
        warnings = verify_kpis(rows)
        assert len(warnings) >= 1
        assert any("moneda" in w.lower() or "currency" in w.lower() for w in warnings)

    def test_us_with_gbp(self) -> None:
        """Clínica US con GBP debe generar advertencia."""
        rows = [
            {"clinic_id": "CLI-001", "country": "US", "currency": "GBP",
             "total_supply_cost": Decimal("0"), "supply_consumption_count": 0,
             "critical_stockout_count": 0, "expiry_risk_count": 0},
        ]
        warnings = verify_kpis(rows)
        assert len(warnings) >= 1

    def test_empty_list(self) -> None:
        """Lista vacía no debe generar advertencias."""
        assert verify_kpis([]) == []

    def test_negative_consumption(self) -> None:
        """Consumo negativo debe generar advertencia."""
        rows = [
            {"clinic_id": "CLI-001", "country": "US", "currency": "USD",
             "total_supply_cost": Decimal("0"), "supply_consumption_count": -1,
             "critical_stockout_count": 0, "expiry_risk_count": 0},
        ]
        warnings = verify_kpis(rows)
        assert len(warnings) >= 1
        assert any("negativo" in w for w in warnings)