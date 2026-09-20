"""Pruebas para POST /auth/change-password.

Cubre: contraseña correcta, incorrecta, sin token, token inválido, bordes.
"""

from __future__ import annotations


class TestChangePasswordHappyPath:
    """Happy path: contraseña actual correcta + nueva válida → 200."""

    def test_change_password_success(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": seed_user["password"],
                "new_password": "newPassword789",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "Contraseña actualizada correctamente" in data["message"]

    def test_change_password_actually_updates(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        """Tras cambiarla, la nueva contraseña debe permitir login."""
        client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": seed_user["password"],
                "new_password": "newPassword789",
            },
        )
        # Login con nueva contraseña
        response = client.post("/auth/login", json={
            "email": seed_user["email"],
            "password": "newPassword789",
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_change_password_old_still_works_until_logout(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        """La contraseña anterior debe dejar de funcionar después del cambio."""
        client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": seed_user["password"],
                "new_password": "newPassword789",
            },
        )
        # Login con contraseña antigua → debe fallar
        response = client.post("/auth/login", json={
            "email": seed_user["email"],
            "password": seed_user["password"],
        })
        assert response.status_code == 401


class TestChangePasswordEdgeCases:
    """Casos límite del payload."""

    def test_change_password_same_password(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        """new_password = current_password → 200 (no hay validación que lo impida)."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": seed_user["password"],
                "new_password": seed_user["password"],
            },
        )
        assert response.status_code == 200

    def test_change_password_short_new_password(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        """Nueva contraseña < 8 caracteres → 422."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": seed_user["password"],
                "new_password": "short",
            },
        )
        assert response.status_code == 422

    def test_change_password_empty_new_password(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        """Nueva contraseña vacía → 422."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": seed_user["password"],
                "new_password": "",
            },
        )
        assert response.status_code == 422

    def test_change_password_current_empty(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        """Contraseña actual vacía → 400 (error de negocio)."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": "",
                "new_password": "validNewPass123",
            },
        )
        assert response.status_code == 400

    def test_change_password_missing_fields(
        self, client: object, access_token: str
    ) -> None:
        """Faltan campos → 422."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"new_password": "somepass"},
        )
        assert response.status_code == 422


class TestChangePasswordFailureModes:
    """Modos de fallo: contraseña incorrecta, sin autenticación, etc."""

    def test_change_password_wrong_current(
        self, client: object, access_token: str, seed_user: dict
    ) -> None:
        """Contraseña actual incorrecta → 400."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": "wrongCurrentPass",
                "new_password": "newPass1234",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "La contraseña actual no es correcta" in data["detail"]

    def test_change_password_no_token(self, client: object) -> None:
        """Sin autenticación → 401."""
        response = client.post(
            "/auth/change-password",
            json={
                "current_password": "somepass",
                "new_password": "newPass1234",
            },
        )
        assert response.status_code == 401

    def test_change_password_malformed_token(
        self, client: object
    ) -> None:
        """Token inválido → 401."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": "Bearer invalid-token"},
            json={
                "current_password": "somepass",
                "new_password": "newPass1234",
            },
        )
        assert response.status_code == 401

    def test_change_password_expired_token(
        self, client: object, expired_access_token: str
    ) -> None:
        """Token expirado → 401."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {expired_access_token}"},
            json={
                "current_password": "somepass",
                "new_password": "newPass1234",
            },
        )
        assert response.status_code == 401

    def test_change_password_wrong_auth_scheme(
        self, client: object, access_token: str
    ) -> None:
        """Authorization con esquema Basic en lugar de Bearer → 401."""
        response = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Basic {access_token}"},
            json={
                "current_password": "somepass",
                "new_password": "newPass1234",
            },
        )
        assert response.status_code == 401