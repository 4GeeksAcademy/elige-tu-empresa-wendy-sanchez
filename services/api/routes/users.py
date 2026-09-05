from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

import user_service
from models import Role, User, UserCreate, UserOut, UserUpdate
from security import get_current_user, hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, is_active=user.is_active, role=user.role, created_at=user.created_at)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate) -> UserOut:
    if user_service.get_user_by_email(payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario registrado con el email '{payload.email}'",
        )

    user = user_service.create_user(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=Role.USER,
    )
    user_service.create_profile(
        user_id=user.id, name=payload.name, phone=payload.phone, address=payload.address
    )
    return _to_user_out(user)


@router.get("", response_model=list[UserOut])
def list_all_users(current_user: User = Depends(get_current_user)) -> list[UserOut]:
    return [_to_user_out(user) for user in user_service.list_users()]


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, current_user: User = Depends(get_current_user)) -> UserOut:
    user = user_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return _to_user_out(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: UserUpdate, current_user: User = Depends(get_current_user)
) -> UserOut:
    target = user_service.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    is_self = current_user.id == user_id
    is_admin = current_user.role is Role.ADMIN
    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar este usuario",
        )

    changes: dict[str, object] = {}
    if payload.email is not None:
        existing = user_service.get_user_by_email(payload.email)
        if existing is not None and existing.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un usuario registrado con el email '{payload.email}'",
            )
        changes["email"] = payload.email
    if payload.role is not None:
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sólo un administrador puede cambiar el rol de un usuario",
            )
        changes["role"] = payload.role.value

    updated = user_service.update_user(user_id, changes) if changes else target
    return _to_user_out(updated)


@router.delete("/{user_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, current_user: User = Depends(get_current_user)) -> None:
    target = user_service.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    is_self = current_user.id == user_id
    is_admin = current_user.role is Role.ADMIN
    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este usuario",
        )

    user_service.delete_user(user_id)
