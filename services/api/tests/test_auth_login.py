"""Pruebas para POST /auth/login.

Cubre: credenciales correctas, incorrectas, campos vacíos, usuario inactivo.
"""

from __future__ import annotations


class TestLoginHappyPath:
    """Happy path: credenciales correctas → 200 + Token."""

    def test_login_success_returns_token(self, client: object, seed_user: dict) -> None:
        response = client.post("/auth/login", json={
            "email": seed_user["email"],
            "password": seed_user["password"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        assert data["token_type"] == "bearer"

    def test_login_success_different_user(self, client: object, seed_admin: dict) -> None:
        """Diferente usuario (admin) también puede hacer login."""
        response = client.post("/auth/login", json={
            "email": seed_admin["email"],
            "password": seed_admin["password"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestLoginEdgeCases:
    """Casos límite: campos vacíos, valores atípicos."""

    def test_login_empty_password(self, client: object, seed_user: dict) -> None:
        """Contraseña vacía → 401 (login fallido, no error de validación)."""
        response = client.post("/auth/login", json={
            "email": seed_user["email"],
            "password": "",
        })
        assert response.status_code == 401

    def test_login_empty_email(self, client: object) -> None:
        """Email vacío → 422 Validation Error."""
        response = client.post("/auth/login", json={
            "email": "",
            "password": "somepassword",
        })
        assert response.status_code == 422

    def test_login_missing_email_field(self, client: object) -> None:
        """Falta el campo email → 422."""
        response = client.post("/auth/login", json={
            "password": "somepassword",
        })
        assert response.status_code == 422

    def test_login_missing_password_field(self, client: object) -> None:
        """Falta el campo password → 422."""
        response = client.post("/auth/login", json={
            "email": "test@test.com",
        })
        assert response.status_code == 422

    def test_login_empty_body(self, client: object) -> None:
        """Cuerpo vacío → 422."""
        response = client.post("/auth/login", json={})
        assert response.status_code == 422

    def test_login_invalid_email_format(self, client: object) -> None:
        """Email con formato inválido (sin @) → 422."""
        response = client.post("/auth/login", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert response.status_code == 422


class TestLoginFailureModes:
    """Modos de fallo: credenciales inválidas, usuario inactivo, etc."""

    def test_login_wrong_password(self, client: object, seed_user: dict) -> None:
        """Contraseña incorrecta → 401."""
        response = client.post("/auth/login", json={
            "email": seed_user["email"],
            "password": "wrongpassword",
        })
        assert response.status_code == 401
        data = response.json()
        assert "Email o contraseña incorrectos" in data["detail"]

    def test_login_unregistered_email(self, client: object) -> None:
        """Email no registrado → 401."""
        response = client.post("/auth/login", json={
            "email": "noexiste@test.com",
            "password": "somepassword",
        })
        assert response.status_code == 401
        data = response.json()
        assert "Email o contraseña incorrectos" in data["detail"]

    def test_login_inactive_user(self, client: object, seed_inactive_user: dict) -> None:
        """Usuario inactivo → 401 (mismo mensaje genérico)."""
        response = client.post("/auth/login", json={
            "email": seed_inactive_user["email"],
            "password": seed_inactive_user["password"],
        })
        assert response.status_code == 401
        data = response.json()
        assert "Email o contraseña incorrectos" in data["detail"]

    def test_login_nonexistent_and_wrong_password_message_identical(
        self, client: object, seed_user: dict
    ) -> None:
        """El mensaje de error es idéntico para email no existe y password incorrecta."""
        resp1 = client.post("/auth/login", json={
            "email": "noexiste@test.com",
            "password": "anything",
        })
        resp2 = client.post("/auth/login", json={
            "email": seed_user["email"],
            "password": "wrongpassword",
        })
        assert resp1.json()["detail"] == resp2.json()["detail"]

    def test_login_non_string_types(self, client: object) -> None:
        """Tipos no string en campos → 422."""
        response = client.post("/auth/login", json={
            "email": 12345,
            "password": True,
        })
        assert response.status_code == 422