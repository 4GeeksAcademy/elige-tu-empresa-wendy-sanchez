from types import SimpleNamespace
from uuid import uuid4

import pytest
import requests
from fastapi import Request, Response
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import telemetry_delivery
from models import InventoryAlertState
from telemetry import TelemetryEvent
from telemetry_delivery import TelemetryDelivery, capture_inventory_signals


def event(event_type="auth_logout_completed", properties=None):
    return TelemetryEvent(eventId=str(uuid4()), timestamp="2026-10-06T12:00:00Z", sessionId=str(uuid4()),
                          userId="a" * 64, requestId=str(uuid4()), schemaVersion="1.0.0", event_type=event_type,
                          properties=properties or {"application": "backoffice", "logout_reason": "user_action"})


def test_batch_delivery_retries_and_discards_without_changing_ids(monkeypatch):
    delivery = TelemetryDelivery("http://collector.test/events")
    recorded = []
    delays = []
    def unavailable(endpoint, **options):
        recorded.append(options["json"])
        raise requests.ConnectionError()
    monkeypatch.setattr(telemetry_delivery.requests, "post", unavailable)
    monkeypatch.setattr(delivery._stop, "wait", lambda delay: delays.append(delay) or False)
    delivery.track(event())
    delivery.track(event())
    assert delivery.flush() is False
    assert delays == [1, 2, 4]
    assert len(recorded) == 4
    assert all(payload == recorded[0] for payload in recorded)
    assert len(recorded[0]["events"]) == 2
    assert delivery.dropped == 2


def test_expiry_dedup_is_persisted_only_after_collector_receipt(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(telemetry_delivery, "get_sql_engine", lambda: engine)
    delivery = TelemetryDelivery("http://collector.test/events")
    key = "expiry:1:1:2026-10-16"
    captured = event("supply_expiry_flagged", {"clinic_id": 1, "country": "US", "product_id": 1, "product_category": "ppe", "quantity": 10, "days_to_expiry": 10, "expiry_window_days": 30})
    assert delivery.track(captured, key)
    assert not delivery.track(captured, key)
    with Session(engine) as session:
        assert session.get(InventoryAlertState, key) is None
    monkeypatch.setattr(telemetry_delivery.requests, "post", lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: {"received": 1}))
    assert delivery.flush()
    with Session(engine) as session:
        assert session.get(InventoryAlertState, key) is not None
    engine.dispose()


def test_queue_is_bounded_and_batches_never_exceed_twenty(monkeypatch):
    delivery = TelemetryDelivery()
    for index in range(220):
        delivery.track(event())
    assert delivery.queued_count == 200
    recorded = []
    def receipt(*args, **options):
        recorded.append(options["json"])
        return SimpleNamespace(status_code=200, json=lambda: {"received": len(options["json"]["events"])})
    monkeypatch.setattr(telemetry_delivery.requests, "post", receipt)
    assert delivery.flush()
    assert len(recorded[0]["events"]) == 20


def test_backend_enqueues_without_a_client_reading_headers(monkeypatch):
    import json
    delivery = TelemetryDelivery()
    monkeypatch.setattr(telemetry_delivery, "service", delivery)
    source = event()
    request = Request({"type": "http", "headers": []})
    request.state.telemetry_user_id = "b" * 64
    request.state.telemetry_request_id = str(uuid4())
    response = Response(headers={"X-Telemetry-Events": json.dumps([{"event_type": source.event_type, "properties": source.properties, "eventId": source.eventId, "timestamp": source.timestamp.isoformat()}])})
    capture_inventory_signals(request, response)
    assert delivery.queued_count == 1
    assert "X-Telemetry-Events" not in response.headers
    recorded = []
    def receipt(*args, **options):
        recorded.append(options["json"])
        return SimpleNamespace(status_code=200, json=lambda: {"received": 1})
    monkeypatch.setattr(telemetry_delivery.requests, "post", receipt)
    assert delivery.flush()
    assert recorded[0]["events"][0]["eventId"] == source.eventId
    assert recorded[0]["events"][0]["userId"] == "b" * 64


def test_wrong_receipt_does_not_acknowledge_expiry(monkeypatch):
    delivery = TelemetryDelivery()
    monkeypatch.setattr(delivery._stop, "wait", lambda _: False)
    monkeypatch.setattr(telemetry_delivery.requests, "post", lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: {"received": 0}))
    key = "expiry:1:1:2026-10-16"
    delivery.track(event(), key)
    assert not delivery.flush()
    assert delivery.track(event(), key)


def test_worker_uses_ten_second_window_and_twenty_event_trigger(monkeypatch):
    delivery = TelemetryDelivery()
    for index in range(19):
        delivery.track(event())
    assert not delivery._wake.is_set()
    delivery.track(event())
    assert delivery._wake.is_set()
    waits = []
    monkeypatch.setattr(delivery._wake, "wait", lambda duration: waits.append(duration))
    monkeypatch.setattr(delivery, "flush", lambda: delivery._stop.set())
    delivery._run()
    assert waits == [10]


def test_source_enqueues_before_response_is_consumed(monkeypatch):
    from inventory_telemetry import signal
    delivery = TelemetryDelivery()
    monkeypatch.setattr(telemetry_delivery, "service", delivery)
    request = Request({"type": "http", "headers": []})
    request.state.telemetry_user_id = "a" * 64
    request.state.telemetry_request_id = str(uuid4())
    token = telemetry_delivery.request_context.set(request)
    try:
        source = signal("auth_logout_completed", {"application": "backoffice", "logout_reason": "user_action"})
        assert source["_server_owned"]
        assert delivery.queued_count == 1
        import json
        response = Response(headers={"X-Telemetry-Events": json.dumps([source])})
        capture_inventory_signals(request, response)
        assert delivery.queued_count == 1
    finally:
        telemetry_delivery.request_context.reset(token)


def test_all_mandatory_events_reach_stub_without_frontend_processing(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from main import timing_middleware
    from routes.inventory import router as inventory_router, get_current_user as inventory_current_user
    from routes.telemetry import router as receiver_router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    delivery = TelemetryDelivery("http://collector.test/telemetry/events")
    monkeypatch.setattr(telemetry_delivery, "service", delivery)
    monkeypatch.setattr(telemetry_delivery, "get_sql_engine", lambda: engine)
    app = FastAPI()
    app.include_router(inventory_router)
    app.middleware("http")(timing_middleware)
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[inventory_current_user] = lambda: SimpleNamespace(id=1)
    receiver = FastAPI()
    receiver.include_router(receiver_router)
    sink = TestClient(receiver)
    recorded = []
    def post_to_stub(endpoint, **options):
        recorded.append(options["json"])
        return sink.post("/telemetry/events", json=options["json"])
    monkeypatch.setattr(telemetry_delivery.requests, "post", post_to_stub)

    with TestClient(app) as client:
        product = client.post("/inventory/products", json={"name": "Gloves", "sku": "end-to-end", "category": "ppe", "unit": "box", "country": "US"})
        assert product.status_code == 201
        product_id = product.json()["id"]
        expiry = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
        assert client.put(f"/inventory/products/{product_id}/policy", json={"clinic_id": 1, "minimum_quantity": 5, "expiry_date": expiry}).status_code == 200
        assert client.post("/inventory/orders/inbound", json={"supply_id": product_id, "clinic_id": 1, "quantity": 10, "vendor_name": "vendor-privacy-canary"}).status_code == 201
        assert client.post("/inventory/orders/outbound", json={"supply_id": product_id, "clinic_id": 1, "quantity": 6, "consumption_type": "clinical_use", "department": "primary_care"}).status_code == 201
        assert client.patch(f"/inventory/products/{product_id}/stock", json={"clinic_id": 1, "quantity": 4}).status_code == 403
        assert not recorded
        assert delivery.queued_count == 6
        key = f"expiry:{product_id}:1:{expiry}"
        with Session(engine) as session:
            assert session.get(InventoryAlertState, key) is None
        assert delivery.flush()
        emitted = recorded[0]["events"]
        assert len(emitted) == 6
        assert {"inbound_order_created", "outbound_order_created", "stock_threshold_triggered", "direct_stock_edit_rejected", "supply_expiry_flagged"}.issubset({item["event_type"] for item in emitted})
        assert all(len(item["userId"]) == 64 for item in emitted)
        assert "vendor-privacy-canary" not in str(emitted)
        assert all(set(item) == {"eventId", "timestamp", "sessionId", "userId", "event_type", "schemaVersion", "requestId", "properties"} for item in emitted)
        with Session(engine) as session:
            assert session.get(InventoryAlertState, key) is not None
        assert client.get(f"/inventory/products/{product_id}").status_code == 200
        assert delivery.queued_count == 0
    engine.dispose()