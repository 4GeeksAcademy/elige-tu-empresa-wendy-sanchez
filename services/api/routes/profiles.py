from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

import user_service
from models import Profile, ProfilePublic, ProfileUpdate, User
from security import get_current_user

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_profile_public(profile: Profile) -> ProfilePublic:
    """Convierte un Profile interno a su versión pública (sin user_id)."""
    return ProfilePublic(id=profile.id, name=profile.name, phone=profile.phone, address=profile.address)


@router.get("/me", response_model=ProfilePublic)
def get_my_profile(current_user: User = Depends(get_current_user)) -> ProfilePublic:
    profile = user_service.get_profile_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no encontrado")
    return _to_profile_public(profile)


@router.put("/me", response_model=ProfilePublic)
def update_my_profile(
    payload: ProfileUpdate, current_user: User = Depends(get_current_user)
) -> ProfilePublic:
    profile = user_service.get_profile_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no encontrado")

    changes = payload.model_dump(exclude_unset=True)
    updated = user_service.update_profile_by_user_id(current_user.id, changes) if changes else profile
    return _to_profile_public(updated)
