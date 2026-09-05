from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

import user_service
from models import LoginRequest, MeResponse, Token, User
from security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest) -> Token:
    user = user_service.get_user_by_email(payload.email)
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.get("/me", response_model=MeResponse)
def read_me(current_user: User = Depends(get_current_user)) -> MeResponse:
    profile = user_service.get_profile_by_user_id(current_user.id)
    return MeResponse(email=current_user.email, role=current_user.role, profile=profile)
