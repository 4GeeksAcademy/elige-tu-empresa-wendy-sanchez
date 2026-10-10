from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_db
from routes.telemetry import router


def event():
    return {
        "eventId": str(uuid4()), "timestamp": "2026-10-06T12:00:00Z",
        "sessionId": str(uuid4()), "userId": str(uuid4()),
        "requestId": str(uuid4()), "event_type": "auth_logout_completed",
        "schemaVersion": "1.0.0",
        "properties": {"application": "backoffice", "logout_reason": "user_action"},
    }


@pytest.fixture
def telemetry_client():
    # Lazy imports to avoid Python 3.14 / SQLModel compat issue at module level
    from sqlalchemy import text as sa_text
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    # Create telemetry_events table (raw SQL — not managed by SQLModel)
    with engine.connect() as conn:
        conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS telemetry_events (
                id              INTEGER  PRIMARY KEY AUTOINCREMENT,
                event_id        TEXT     NOT NULL UNIQUE,
                timestamp       TEXT     NOT NULL,
                session_id      TEXT     NOT NULL,
                user_id         TEXT     NOT NULL,
                event_type      TEXT     NOT NULL,
                schema_version  TEXT     NOT NULL,
                request_id      TEXT     NOT NULL,
                tags            TEXT,
                created_at      TEXT     NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """))
        conn.commit()
    app = FastAPI()
    app.include_router(router)

    def session_dependency():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = session_dependency
    return TestClient(app)


def test_batch_received(telemetry_client, caplog):
    with caplog.at_level("INFO", logger="api.telemetry"):
        response = telemetry_client.post("/telemetry/events", json={"events": [event(), event()]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 2
    assert data["stored"] == 2
    assert data["rejected"] == 0
    assert "auth_logout_completed" in caplog.text
    assert "userId" not in caplog.text


@pytest.mark.parametrize("change", [
    {"schemaVersion": "2.0.0"}, {"event_type": "unknown_event"},
    {"timestamp": "2026-10-06T12:00:00"}, {"timestamp": 123},
    {"eventId": "invalid"}, {"email": "private@example.com"},
    {"properties": {"application": "backoffice", "email": "private@example.com"}},
    {"properties": {"application": "backoffice", "logout_reason": "invalid"}},
])
def test_invalid_contract_rejected_individually(telemetry_client, change):
    """Single invalid event → 200 with rejected=1 (partial acceptance)."""
    invalid = deepcopy(event())
    invalid.update(change)
    response = telemetry_client.post("/telemetry/events", json={"events": [invalid]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["stored"] == 0
    assert data["rejected"] == 1


def test_invalid_batch_structure_rejected(telemetry_client):
    """Structural errors in the envelope itself still return 422."""
    response = telemetry_client.post("/telemetry/events", json={"events": [event()] * 101})
    assert response.status_code == 422

    response = telemetry_client.post("/telemetry/events", json={"events": "not_a_list"})
    assert response.status_code == 422


def test_mixed_batch_partial_acceptance(telemetry_client):
    """A mix of valid and invalid events → 200 with correct stored/rejected."""
    valid = event()
    invalid = deepcopy(event())
    invalid["event_type"] = "unknown_event"
    response = telemetry_client.post("/telemetry/events", json={"events": [valid, invalid]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 2
    assert data["stored"] == 1
    assert data["rejected"] == 1


@pytest.mark.parametrize("event_type,extra", [
    ("inbound_order_created", {"vendor_ref": "a" * 64}),
    ("outbound_order_created", {"department": "operations", "consumption_type": "clinical_use"}),
    ("stock_threshold_triggered", {"threshold_quantity": 20, "threshold_version": "1"}),
    ("direct_stock_edit_rejected", {"rejection_code": "direct_edit_not_allowed", "source_surface": "api"}),
    ("supply_expiry_flagged", {"days_to_expiry": 5, "expiry_window_days": 30}),
])
def test_mandatory_contracts(telemetry_client, event_type, extra):
    payload = event()
    payload["event_type"] = event_type
    payload["properties"] = {
        "clinic_id": 1, "country": "US", "product_id": 1,
        "product_category": "ppe", "quantity": 1, **extra,
    }
    response = telemetry_client.post("/telemetry/events", json={"events": [payload]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["stored"] == 1
    assert data["rejected"] == 0

    # Invalid property type → individual rejection, not 422
    payload["properties"]["quantity"] = True
    response = telemetry_client.post("/telemetry/events", json={"events": [payload]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["stored"] == 0
    assert data["rejected"] == 1


def test_router_has_events_endpoint():
    """The telemetry router includes POST /events and /control."""
    route_paths = [r.path for r in router.routes]
    assert "/telemetry/events" in route_paths
    assert "/telemetry/control" in route_paths


@pytest.mark.parametrize("timestamp", ["123", "20261006", "2026-10-06", "2026-10-06 12:00:00Z", "2026-02-31T12:00:00Z"])
def test_timestamp_must_be_iso_datetime(telemetry_client, timestamp):
    """Invalid timestamp → individual rejection, not 422."""
    payload = event()
    payload["timestamp"] = timestamp
    response = telemetry_client.post("/telemetry/events", json={"events": [payload]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["stored"] == 0
    assert data["rejected"] == 1


@pytest.mark.parametrize("field,value", [
    ("route_template", "/account/email-canary@example.com"),
    ("route_template", "/account/profile?password=private"),
    ("component", "JaneSmith"), ("app_version", "private-password"),
    ("error_code", "jane_smith"),
])
def test_pii_in_allowlisted_values_rejected(telemetry_client, field, value):
    """PII in allowlisted values → individual rejection, not 422."""
    payload = event()
    payload["event_type"] = "frontend_error_captured"
    payload["properties"] = {"application": "backoffice", "app_version": "0.1.0", "route_template": "/account/profile", "component": "window", "error_code": "uncaught_error", "error_class": "unknown"}
    payload["properties"][field] = value
    response = telemetry_client.post("/telemetry/events", json={"events": [payload]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["stored"] == 0
    assert data["rejected"] == 1


def test_diagnostic_event_reference_cannot_contain_arbitrary_names():
    from telemetry import validate_property_privacy
    with pytest.raises(ValueError):
        validate_property_privacy("event_type", "jane_smith")
    validate_property_privacy("event_type", "inbound_order_created")