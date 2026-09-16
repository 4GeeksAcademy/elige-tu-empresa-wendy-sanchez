"""Pruebas unitarias de user_service: CRUD de usuarios y perfiles.

Se apoyan en la BD en memoria de conftest.py y no usan HTTP.
"""

from __future__ import annotations

import pytest

# ──────────────────────────────────────────────
# Creación de usuarios
# ──────────────────────────────────────────────


class TestCreateUser:
    def test_creates_user_with_all_fields(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="new@test.com",
            hashed_password=hash_password("pass1234"),
            role=Role.USER,
        )
        assert user.id is not None and user.id > 0
        assert user.email == "new@test.com"
        assert user.is_active is True
        assert user.role == Role.USER
        assert user.created_at is not None

    def test_creates_admin_user(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="admin@test.com",
            hashed_password=hash_password("adminpass"),
            role=Role.ADMIN,
        )
        assert user.role == Role.ADMIN

    def test_duplicate_email_not_prevented_by_service(self) -> None:
        """user_service.create_user NO verifica duplicados (eso es tarea del endpoint)."""
        import user_service
        from models import Role
        from security import hash_password

        u1 = user_service.create_user(
            email="dup@test.com",
            hashed_password=hash_password("pass1"),
            role=Role.USER,
        )
        u2 = user_service.create_user(
            email="dup@test.com",
            hashed_password=hash_password("pass2"),
            role=Role.USER,
        )
        # Se crean ambos porque TinyDB no tiene unique constraints
        assert u1.id != u2.id


# ──────────────────────────────────────────────
# Búsqueda de usuarios
# ──────────────────────────────────────────────


class TestGetUser:
    def test_get_by_id_exists(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        created = user_service.create_user(
            email="findme@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        found = user_service.get_user_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.email == created.email

    def test_get_by_id_not_found(self) -> None:
        import user_service
        assert user_service.get_user_by_id(99999) is None

    def test_get_by_email_case_insensitive(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user_service.create_user(
            email="Case@Test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        # Búsqueda con distinto casing (EmailStr normaliza el dominio a lowercase)
        found = user_service.get_user_by_email("case@test.com")
        assert found is not None
        assert found.email == "Case@test.com"

    def test_get_by_email_not_found(self) -> None:
        import user_service
        assert user_service.get_user_by_email("noexiste@test.com") is None

    def test_list_users_all(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user_service.create_user(
            email="a@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        user_service.create_user(
            email="b@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        users = user_service.list_users()
        assert len(users) == 2

    def test_list_users_empty(self) -> None:
        import user_service
        assert user_service.list_users() == []


# ──────────────────────────────────────────────
# Actualización de usuarios
# ──────────────────────────────────────────────


class TestUpdateUser:
    def test_update_existing_user(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="update@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        updated = user_service.update_user(user.id, {"email": "updated@test.com"})
        assert updated is not None
        assert updated.email == "updated@test.com"

    def test_update_nonexistent_user(self) -> None:
        import user_service
        result = user_service.update_user(99999, {"email": "x@test.com"})
        assert result is None

    def test_update_clears_is_active(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="active@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        updated = user_service.update_user(user.id, {"is_active": False})
        assert updated is not None
        assert updated.is_active is False


# ──────────────────────────────────────────────
# Eliminación de usuarios
# ──────────────────────────────────────────────


class TestDeleteUser:
    def test_delete_existing_user(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="delete@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        result = user_service.delete_user(user.id)
        assert result is True
        assert user_service.get_user_by_id(user.id) is None

    def test_delete_user_also_removes_profile(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="delprof@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        user_service.create_profile(user.id, "Name", "555", "Addr")
        user_service.delete_user(user.id)
        assert user_service.get_profile_by_user_id(user.id) is None

    def test_delete_nonexistent_user(self) -> None:
        import user_service
        result = user_service.delete_user(99999)
        assert result is False


# ──────────────────────────────────────────────
# Perfiles
# ──────────────────────────────────────────────


class TestProfile:
    def test_create_profile(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="prof@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        profile = user_service.create_profile(
            user_id=user.id,
            name="John",
            phone="+1-555-0000",
            address="Somewhere",
        )
        assert profile.user_id == user.id
        assert profile.name == "John"
        assert profile.phone == "+1-555-0000"
        assert profile.address == "Somewhere"

    def test_get_profile_by_user_id(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="getprof@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        user_service.create_profile(user.id, "Jane", "+2", "Addr")
        profile = user_service.get_profile_by_user_id(user.id)
        assert profile is not None
        assert profile.name == "Jane"

    def test_get_profile_not_found(self) -> None:
        import user_service
        assert user_service.get_profile_by_user_id(99999) is None

    def test_update_profile(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="updprof@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        user_service.create_profile(user.id, "Old", "1", "OldAddr")
        updated = user_service.update_profile_by_user_id(
            user.id, {"name": "New"}
        )
        assert updated is not None
        assert updated.name == "New"

    def test_update_nonexistent_profile(self) -> None:
        import user_service
        result = user_service.update_profile_by_user_id(99999, {"name": "X"})
        assert result is None

    def test_delete_profile(self) -> None:
        import user_service
        from models import Role
        from security import hash_password

        user = user_service.create_user(
            email="delprof2@test.com",
            hashed_password=hash_password("pass"),
            role=Role.USER,
        )
        user_service.create_profile(user.id, "Name", "555", "Addr")
        result = user_service.delete_profile_by_user_id(user.id)
        assert result is True
        assert user_service.get_profile_by_user_id(user.id) is None

    def test_delete_nonexistent_profile(self) -> None:
        import user_service
        result = user_service.delete_profile_by_user_id(99999)
        assert result is False