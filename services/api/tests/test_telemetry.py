from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_batch_received(telemetry_client, caplog):
    with caplog.at_level("INFO", logger="api.telemetry"):
        response = telemetry_client.post("/telemetry/events", json={"events": [event(), event()]})
    assert response.status_code == 200
    assert response.json() == {"received": 2}
    assert "auth_logout_completed" in caplog.text
    assert "userId" not in caplog.text


@pytest.mark.parametrize("change", [
    {"schemaVersion": "2.0.0"}, {"event_type": "unknown_event"},
    {"timestamp": "2026-10-06T12:00:00"}, {"timestamp": 123},
    {"eventId": "invalid"}, {"email": "private@example.com"},
    {"properties": {"application": "backoffice", "email": "private@example.com"}},
    {"properties": {"application": "backoffice", "logout_reason": "invalid"}},
])
def test_invalid_contract_rejected(telemetry_client, change):
    invalid = deepcopy(event())
    invalid.update(change)
    assert telemetry_client.post("/telemetry/events", json={"events": [invalid]}).status_code == 422


def test_invalid_batch_rejected(telemetry_client):
    for body in ({"events": []}, {"events": [event()] * 101}, {"events": [event()], "extra": True}):
        assert telemetry_client.post("/telemetry/events", json=body).status_code == 422


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
    assert response.json() == {"received": 1}
    payload["properties"]["quantity"] = True
    assert telemetry_client.post("/telemetry/events", json={"events": [payload]}).status_code == 422


def test_router_registered_in_main(monkeypatch):
    import main

    monkeypatch.setattr(main, "init_supabase_schema", lambda: None)
    with TestClient(main.app) as client:
        response = client.post("/telemetry/events", json={"events": [event(), event()]})
    assert response.status_code == 200
    assert response.json() == {"received": 2}
    assert main.app.state.telemetry_endpoint