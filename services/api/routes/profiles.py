from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

import user_service
from models import Profile, ProfileUpdate, User
from security import get_current_user

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=Profile)
def get_my_profile(current_user: User = Depends(get_current_user)) -> Profile:
    profile = user_service.get_profile_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no encontrado")
    return profile


@router.put("/me", response_model=Profile)
def update_my_profile(
    payload: ProfileUpdate, current_user: User = Depends(get_current_user)
) -> Profile:
    profile = user_service.get_profile_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no encontrado")

    changes = payload.model_dump(exclude_unset=True)
    updated = user_service.update_profile_by_user_id(current_user.id, changes) if changes else profile
    return updated
