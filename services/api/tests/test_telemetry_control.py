from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import requests

import telemetry_delivery
from telemetry_delivery import TelemetryDelivery, record_drop, flush_control
from routes.telemetry import router
from tests.test_telemetry_delivery import event


def test_delivery_failures_use_independent_control_without_recursion(monkeypatch):
    telemetry_delivery.control_queue.clear()
    delivery = TelemetryDelivery("http://collector.test/events")
    monkeypatch.setattr(delivery._stop, "wait", lambda _: False)
    monkeypatch.setattr(telemetry_delivery.requests, "post", lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError()))
    delivery.track(event())
    assert not delivery.flush()
    record_drop("unregistered-private-name", "unknown_event")
    types = {event.event_type for event in telemetry_delivery.control_queue}
    assert {"telemetry_delivery_failed", "telemetry_event_dropped", "api_dependency_failed", "api_retry_exhausted"}.issubset(types)
    count = len(telemetry_delivery.control_queue)
    assert not flush_control()
    assert len(telemetry_delivery.control_queue) == count
    app = FastAPI(); app.include_router(router)
    receiver = TestClient(app)
    monkeypatch.setattr(telemetry_delivery.requests, "post", lambda url, **kwargs: receiver.post("/telemetry/control", json=kwargs["json"]))
    assert flush_control()
    assert not telemetry_delivery.control_queue


def test_readiness_failure_is_observed(client, monkeypatch):
    import database
    telemetry_delivery.control_queue.clear()
    monkeypatch.setattr(database, "get_sql_engine", lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")))
    assert client.get("/health/ready").status_code == 503
    assert any(event.event_type == "service_health_check_failed" for event in telemetry_delivery.control_queue)