import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from cache import cache
from database import get_db
from routes.inventory import router
from security import get_current_user
from routes.telemetry import router as telemetry_router
from telemetry import TelemetryEvent
from uuid import uuid4


@pytest.fixture
def inventory_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(router)
    app.include_router(telemetry_router)
    def session_dependency():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = session_dependency
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    cache.invalidate("inventory")
    with TestClient(app) as client:
        yield client
    engine.dispose()


def events(response):
    return json.loads(response.headers.get("X-Telemetry-Events", "[]"))


def test_all_mandatory_events_and_real_clinic_stock(inventory_client):
    client = inventory_client
    product = client.post("/inventory/products", json={"name": "Gloves", "sku": "test", "category": "ppe", "unit": "box", "country": "US"})
    assert product.status_code == 201
    product_id = product.json()["id"]
    expiry = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
    assert client.put(f"/inventory/products/{product_id}/policy", json={"clinic_id": 1, "minimum_quantity": 5, "expiry_date": expiry}).status_code == 200
    inbound = client.post("/inventory/orders/inbound", json={"supply_id": product_id, "clinic_id": 1, "quantity": 10, "vendor_name": "Sensitive Vendor"})
    assert inbound.status_code == 201
    assert {item["event_type"] for item in events(inbound)} == {"inbound_order_created", "supply_expiry_flagged"}
    assert "Sensitive Vendor" not in inbound.headers["X-Telemetry-Events"]
    outbound_payload = {"supply_id": product_id, "clinic_id": 1, "quantity": 6, "consumption_type": "clinical_use", "department": "primary_care"}
    outbound = client.post("/inventory/orders/outbound", json=outbound_payload)
    assert outbound.status_code == 201
    assert {item["event_type"] for item in events(outbound)} == {"outbound_order_created", "stock_threshold_triggered"}
    assert client.get(f"/inventory/products/{product_id}?clinic_id=1").json()["current_stock"] == 4
    assert [item["event_type"] for item in events(client.get(f"/inventory/products/{product_id}"))] == ["supply_expiry_flagged"]
    outbound_payload["clinic_id"] = 2
    rejected = client.post("/inventory/orders/outbound", json=outbound_payload)
    assert rejected.status_code == 400
    assert [item["event_type"] for item in events(rejected)] == ["inventory_order_rejected"]
    direct = client.patch(f"/inventory/products/{product_id}/stock", json={"clinic_id": 1, "quantity": 10})
    assert direct.status_code == 403
    assert events(direct)[0]["event_type"] == "direct_stock_edit_rejected"
    assert client.get(f"/inventory/products/{product_id}?clinic_id=1").json()["current_stock"] == 4
    captured = events(inbound) + events(outbound) + events(direct)
    envelopes = [TelemetryEvent(
        eventId=item["eventId"], timestamp=item["timestamp"], event_type=item["event_type"],
        properties=item["properties"], schemaVersion="1.0.0", sessionId=str(uuid4()),
        userId="a" * 64, requestId=str(uuid4()),
    ).model_dump(mode="json") for item in captured]
    receipt = client.post("/telemetry/events", json={"events": envelopes})
    assert receipt.status_code == 200
    assert receipt.json() == {"received": 5}


def test_invalid_department_has_no_success_signal(inventory_client):
    response = inventory_client.post("/inventory/orders/outbound", json={"supply_id": 1, "clinic_id": 1, "quantity": 1, "consumption_type": "clinical_use", "department": "patient_name"})
    assert response.status_code == 422
    assert events(response) == []