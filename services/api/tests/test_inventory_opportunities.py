from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from cache import cache
from database import get_db
from main import timing_middleware, validation_handler
from routes.inventory import router, get_current_user
import telemetry_delivery
from telemetry_delivery import TelemetryDelivery


def test_inventory_opportunities_are_real_and_match_contracts(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    delivery = TelemetryDelivery()
    monkeypatch.setattr(telemetry_delivery, "service", delivery)
    app = FastAPI()
    app.include_router(router)
    app.middleware("http")(timing_middleware)
    app.add_exception_handler(RequestValidationError, validation_handler)
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="admin")
    cache.invalidate("inventory")
    with TestClient(app) as client:
        product = client.post("/inventory/products", json={"name": "Test", "sku": "opportunity", "category": "ppe", "unit": "box", "country": "US"}).json()["id"]
        client.get("/inventory/products")
        client.get("/inventory/products")
        payload = {"supply_id": product, "clinic_id": 1, "quantity": 10, "vendor_name": "private vendor"}
        assert client.post("/inventory/orders/inbound", json=payload).status_code == 201
        assert client.post("/inventory/orders/inbound", json=payload).status_code == 201
        assert client.post("/inventory/snapshots").status_code == 200
        assert client.post(f"/inventory/products/{product}/reconcile", json={"clinic_id": 1, "counted_quantity": 19}).status_code == 200
        assert client.get("/inventory/orders/export").status_code == 200
        assert client.post("/inventory/orders/outbound", json={"quantity": -1}).status_code == 422
    types = {item.event.event_type for item in delivery._queue}
    assert {"inventory_cache_served", "inventory_cache_invalidated", "inventory_order_duplicate_suspected", "inventory_stock_snapshot_recorded", "inventory_stock_reconciliation_flagged", "inventory_order_history_exported", "inventory_order_validation_failed"}.issubset(types)
    assert "private vendor" not in str([item.event.model_dump() for item in delivery._queue])
    engine.dispose()