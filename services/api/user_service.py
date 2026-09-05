"""Capa de servicios para User y Profile (persistidos únicamente en TinyDB)."""

from __future__ import annotations

from tinydb import Query as TinyQuery

from database import get_profiles_table, get_users_table
from models import Profile, Role, User, utc_now

_UserQuery = TinyQuery()
_ProfileQuery = TinyQuery()


def _to_user(doc_id: int, record: dict) -> User:
    return User(id=doc_id, **record)


def _to_profile(doc_id: int, record: dict) -> Profile:
    return Profile(id=doc_id, **record)


def create_user(email: str, hashed_password: str, role: Role = Role.USER) -> User:
    table = get_users_table()
    record = {
        "email": email,
        "hashed_password": hashed_password,
        "is_active": True,
        "role": role.value,
        "created_at": utc_now().isoformat(),
    }
    doc_id = table.insert(record)
    return _to_user(doc_id, record)


def get_user_by_id(user_id: int) -> User | None:
    doc = get_users_table().get(doc_id=user_id)
    return _to_user(doc.doc_id, dict(doc)) if doc is not None else None


def get_user_by_email(email: str) -> User | None:
    doc = get_users_table().get(_UserQuery.email.test(lambda value: value.lower() == email.lower()))
    return _to_user(doc.doc_id, dict(doc)) if doc is not None else None


def list_users() -> list[User]:
    return [_to_user(doc.doc_id, dict(doc)) for doc in get_users_table().all()]


def update_user(user_id: int, changes: dict) -> User | None:
    table = get_users_table()
    if table.get(doc_id=user_id) is None:
        return None
    table.update(changes, doc_ids=[user_id])
    return get_user_by_id(user_id)


def delete_user(user_id: int) -> bool:
    table = get_users_table()
    if table.get(doc_id=user_id) is None:
        return False
    table.remove(doc_ids=[user_id])
    delete_profile_by_user_id(user_id)
    return True


def create_profile(user_id: int, name: str | None, phone: str | None, address: str | None) -> Profile:
    table = get_profiles_table()
    record = {"user_id": user_id, "name": name, "phone": phone, "address": address}
    doc_id = table.insert(record)
    return _to_profile(doc_id, record)


def get_profile_by_user_id(user_id: int) -> Profile | None:
    doc = get_profiles_table().get(_ProfileQuery.user_id == user_id)
    return _to_profile(doc.doc_id, dict(doc)) if doc is not None else None


def update_profile_by_user_id(user_id: int, changes: dict) -> Profile | None:
    table = get_profiles_table()
    doc = table.get(_ProfileQuery.user_id == user_id)
    if doc is None:
        return None
    table.update(changes, doc_ids=[doc.doc_id])
    return get_profile_by_user_id(user_id)


def delete_profile_by_user_id(user_id: int) -> bool:
    table = get_profiles_table()
    doc = table.get(_ProfileQuery.user_id == user_id)
    if doc is None:
        return False
    table.remove(doc_ids=[doc.doc_id])
    return True
