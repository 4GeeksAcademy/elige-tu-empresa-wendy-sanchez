"""Pruebas para POST /auth/reset-password.

Cubre: token válido, expirado, inválido, reutilizado, type incorrecto,
usuario inexistente/inactivo, contraseña inválida.
"""

from __future__ import annotations


class TestResetPasswordHappyPath:
    """Happy path: token válido + contraseña válida → 200."""

    def test_reset_password_success(
        self, client: object, reset_token: str
    ) -> None:
        response = client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": "newSecurePass789",
        })
        assert response.status_code == 200
        data = response.json()
        assert "Contraseña restablecida correctamente" in data["message"]

    def test_reset_password_updates_password(
        self, client: object, reset_token: str, seed_user: dict
    ) -> None:
        """La nueva contraseña debe permitir hacer login."""
        client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": "newSecurePass789",
        })
        # Verificar que podemos loguearnos con la nueva contraseña
        response = client.post("/auth/login", json={
            "email": seed_user["email"],
            "password": "newSecurePass789",
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_reset_password_invalidates_token(
        self, client: object, reset_token: str, reset_tokens_table: object
    ) -> None:
        """El token debe eliminarse de la BD tras usarse."""
        client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": "newPass456",
        })
        from tinydb import Query as TinyQuery
        assert not reset_tokens_table.contains(TinyQuery()["token"] == reset_token)


class TestResetPasswordEdgeCases:
    """Casos límite del payload."""

    def test_reset_password_short_password(
        self, client: object, reset_token: str
    ) -> None:
        """Contraseña nueva menor de 8 caracteres → 422."""
        response = client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": "short",
        })
        assert response.status_code == 422

    def test_reset_password_long_password(
        self, client: object, reset_token: str
    ) -> None:
        """Contraseña nueva > 128 caracteres → 422."""
        long_pw = "a" * 129
        response = client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": long_pw,
        })
        assert response.status_code == 422

    def test_reset_password_empty_new_password(
        self, client: object, reset_token: str
    ) -> None:
        """Contraseña nueva vacía → 422."""
        response = client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": "",
        })
        assert response.status_code == 422

    def test_reset_password_empty_token(
        self, client: object
    ) -> None:
        """Token vacío → 422 o 400 (depende de si llega a validación)."""
        response = client.post("/auth/reset-password", json={
            "token": "",
            "new_password": "validPass123",
        })
        assert response.status_code in (400, 422)

    def test_reset_password_missing_fields(self, client: object) -> None:
        """Cuerpo vacío → 422."""
        response = client.post("/auth/reset-password", json={})
        assert response.status_code == 422


class TestResetPasswordFailureModes:
    """Modos de fallo: token inválido, expirado, reutilizado, etc."""

    def test_reset_password_invalid_token(self, client: object) -> None:
        """Token que no es un JWT → 400."""
        response = client.post("/auth/reset-password", json={
            "token": "token-invalido",
            "new_password": "newPass1234",
        })
        assert response.status_code == 400
        data = response.json()
        assert "El enlace de restablecimiento no es válido" in data["detail"]

    def test_reset_password_expired_token(
        self, client: object, expired_reset_token: str
    ) -> None:
        """Token expirado → 400."""
        response = client.post("/auth/reset-password", json={
            "token": expired_reset_token,
            "new_password": "newPass1234",
        })
        assert response.status_code == 400
        data = response.json()
        assert "El enlace de restablecimiento no es válido" in data["detail"]

    def test_reset_password_reused_token(
        self, client: object, reset_token: str
    ) -> None:
        """Mismo token usado dos veces → primero 200, luego 400."""
        # Primer uso
        resp1 = client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": "newPass789",
        })
        assert resp1.status_code == 200

        # Segundo uso (token ya invalidado)
        resp2 = client.post("/auth/reset-password", json={
            "token": reset_token,
            "new_password": "anotherPass456",
        })
        assert resp2.status_code == 400
        assert "El enlace de restablecimiento no es válido" in resp2.json()["detail"]

    def test_reset_password_access_token_as_reset(
        self, client: object, access_token: str
    ) -> None:
        """Un token de acceso JWT no debe funcionar como token de reset."""
        response = client.post("/auth/reset-password", json={
            "token": access_token,
            "new_password": "newPass1234",
        })
        assert response.status_code == 400

    def test_reset_password_nonexistent_user(
        self, client: object, seed_user: dict
    ) -> None:
        """Token para usuario que fue borrado → 400."""
        from security import create_reset_token, create_reset_token_expiry
        import user_service
        import database

        # Creamos token antes de borrar el usuario
        token = create_reset_token(user_id=seed_user["id"])
        database.get_reset_tokens_table().insert({
            "token": token,
            "user_id": seed_user["id"],
            "expires_at": create_reset_token_expiry().isoformat(),
        })

        # Borramos el usuario
        user_service.delete_user(seed_user["id"])

        response = client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "newPass1234",
        })
        assert response.status_code == 400