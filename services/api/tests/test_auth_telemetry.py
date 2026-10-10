from uuid import uuid4

import telemetry_delivery
from telemetry_delivery import TelemetryDelivery


def test_denials_tokens_resets_and_limits_are_instrumented(client, monkeypatch):
    delivery = TelemetryDelivery()
    monkeypatch.setattr(telemetry_delivery, "service", delivery)
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer token-canary"}).status_code == 401
    email = f"reset-{uuid4()}@example.com"
    for index in range(6):
        assert client.post("/auth/forgot-password", json={"email": email}).status_code == 200
    events = [item.event for item in delivery._queue]
    assert {"auth_authorization_denied", "auth_token_validation_failed", "auth_password_reset_requested", "auth_rate_limit_triggered"}.issubset({event.event_type for event in events})
    assert email not in str([event.model_dump() for event in events])
    assert "token-canary" not in str([event.model_dump() for event in events])