"""Pruebas para POST /auth/forgot-password.

Cubre: email registrado, no registrado, inactivo, rate limiting, email vacío.
"""

from __future__ import annotations

import os


class TestForgotPasswordHappyPath:
    """Happy path: email registrado → 200 + mensaje genérico."""

    def test_forgot_password_registered_user_returns_200(
        self, client: object, seed_user: dict
    ) -> None:
        response = client.post("/auth/forgot-password", json={
            "email": seed_user["email"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "Si esa dirección está registrada" in data["message"]

    def test_forgot_password_persists_token(
        self, client: object, seed_user: dict, reset_tokens_table: object
    ) -> None:
        """Tras la solicitud debe haber un token persistido en la BD."""
        client.post("/auth/forgot-password", json={
            "email": seed_user["email"],
        })
        # La tabla reset_tokens debe tener al menos 1 registro
        assert len(reset_tokens_table) >= 1


class TestForgotPasswordGenericResponse:
    """El mensaje debe ser idéntico siempre para no filtrar información."""

    def test_forgot_password_unregistered_email(
        self, client: object
    ) -> None:
        """Email no registrado → 200 con mismo mensaje."""
        response = client.post("/auth/forgot-password", json={
            "email": "noexiste@test.com",
        })
        assert response.status_code == 200
        data = response.json()
        assert "Si esa dirección está registrada" in data["message"]

    def test_forgot_password_inactive_user(
        self, client: object, seed_inactive_user: dict
    ) -> None:
        """Usuario inactivo → 200 con el mismo mensaje."""
        response = client.post("/auth/forgot-password", json={
            "email": seed_inactive_user["email"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "Si esa dirección está registrada" in data["message"]

    def test_forgot_password_response_identical(
        self, client: object, seed_user: dict
    ) -> None:
        """La respuesta debe ser idéntica para emails registrados y no registrados."""
        resp_registered = client.post("/auth/forgot-password", json={
            "email": seed_user["email"],
        })
        resp_unregistered = client.post("/auth/forgot-password", json={
            "email": "otro@test.com",
        })
        assert resp_registered.json() == resp_unregistered.json()


class TestForgotPasswordEdgeCases:
    """Casos límite del endpoint."""

    def test_forgot_password_empty_email(self, client: object) -> None:
        """Email vacío → 422."""
        response = client.post("/auth/forgot-password", json={
            "email": "",
        })
        assert response.status_code == 422

    def test_forgot_password_invalid_email_format(self, client: object) -> None:
        """Email con formato inválido → 422."""
        response = client.post("/auth/forgot-password", json={
            "email": "esto-no-es-email",
        })
        assert response.status_code == 422

    def test_forgot_password_empty_body(self, client: object) -> None:
        """Cuerpo vacío → 422."""
        response = client.post("/auth/forgot-password", json={})
        assert response.status_code == 422


class TestForgotPasswordRateLimit:
    """Rate limiting: después de N intentos, se deniega silenciosamente."""

    def test_rate_limit_exceeded_returns_200(
        self, client: object, seed_user: dict, rate_limits_table: object
    ) -> None:
        """Tras superar el límite (5 intentos), sigue devolviendo 200."""
        # Forzamos rate limit bajo para el test
        import os
        os.environ["RATE_LIMIT_MAX_REQUESTS"] = "2"
        os.environ["RATE_LIMIT_WINDOW_MINUTES"] = "60"

        # Recargamos rate_limiter para que lea los nuevos valores
        import importlib
        import rate_limiter
        importlib.reload(rate_limiter)

        # Forzamos 2 intentos para alcanzar el límite
        email = seed_user["email"]
        # Insertamos entradas manualmente en la tabla para simular intentos previos
        for i in range(2):
            rate_limits_table.insert({
                "email": email,
                "timestamp": "2026-09-16T10:00:00",
            })

        # Llamada que debería superar el rate limit
        response = client.post("/auth/forgot-password", json={
            "email": email,
        })
        assert response.status_code == 200
        data = response.json()
        assert "Si esa dirección está registrada" in data["message"]

    def test_rate_limit_within_limit_allows_request(
        self, client: object, seed_user: dict, rate_limits_table: object
    ) -> None:
        """Con menos intentos del límite, la solicitud se procesa."""
        import os
        os.environ["RATE_LIMIT_MAX_REQUESTS"] = "5"
        os.environ["RATE_LIMIT_WINDOW_MINUTES"] = "60"

        import importlib
        import rate_limiter
        importlib.reload(rate_limiter)

        response = client.post("/auth/forgot-password", json={
            "email": seed_user["email"],
        })
        assert response.status_code == 200