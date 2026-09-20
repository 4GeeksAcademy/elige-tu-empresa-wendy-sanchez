"""Pruebas para GET /auth/me.

Cubre: token válido, sin token, token malformado, expirado, usuario inexistente, etc.
"""

from __future__ import annotations


class TestMeHappyPath:
    """Happy path: token válido → 200 + MeResponse."""

    def test_me_returns_user_data(self, client: object, access_token: str, seed_user: dict) -> None:
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == seed_user["email"]
        assert data["role"] == "user"
        assert "profile" in data

    def test_me_returns_profile(self, client: object, access_token: str) -> None:
        """El perfil del usuario debe estar presente (no null)."""
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["profile"] is not None
        assert data["profile"]["name"] == "Test User"
        assert data["profile"]["phone"] == "+1-555-0100"

    def test_me_admin_role(self, client: object, admin_access_token: str, seed_admin: dict) -> None:
        """Usuario con rol admin."""
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_access_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == seed_admin["email"]
        assert data["role"] == "admin"


class TestMeEdgeCases:
    """Casos límite de GET /auth/me."""

    def test_me_without_profile(self, client: object) -> None:
        """Usuario sin perfil → profile debe ser null."""
        import user_service
        from models import Role
        from security import hash_password, create_access_token

        user = user_service.create_user(
            email="noprofile@test.com",
            hashed_password=hash_password("pass1234"),
            role=Role.USER,
        )
        token = create_access_token(subject=str(user.id))

        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["profile"] is None


class TestMeFailureModes:
    """Modos de fallo de GET /auth/me."""

    def test_me_no_token(self, client: object) -> None:
        """Sin cabecera Authorization → 401."""
        response = client.get("/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "detalle" in data.get("detail", "") or "credenciales" in str(data.get("detail", "")).lower()

    def test_me_malformed_token(self, client: object) -> None:
        """Token que no es un JWT → 401."""
        response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})
        assert response.status_code == 401

    def test_me_expired_token(self, client: object, expired_access_token: str) -> None:
        """Token expirado → 401."""
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_access_token}"})
        assert response.status_code == 401

    def test_me_wrong_scheme(self, client: object, access_token: str) -> None:
        """Bearer mal escrito (Basic, Digest...) → 401."""
        response = client.get("/auth/me", headers={"Authorization": f"Basic {access_token}"})
        assert response.status_code == 401

    def test_me_empty_bearer(self, client: object) -> None:
        """Bearer token vacío → 401."""
        response = client.get("/auth/me", headers={"Authorization": "Bearer "})
        assert response.status_code == 401

    def test_me_token_for_deleted_user(
        self, client: object, seed_user: dict
    ) -> None:
        """Token de usuario que luego se borró → 401."""
        from security import create_access_token
        import user_service

        token = create_access_token(subject=str(seed_user["id"]))
        user_service.delete_user(seed_user["id"])

        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_me_token_for_inactive_user(
        self, client: object, seed_inactive_user: dict
    ) -> None:
        """Token de usuario desactivado → 401."""
        from security import create_access_token
        token = create_access_token(subject=str(seed_inactive_user["id"]))
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401