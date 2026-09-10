from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

import audit_logger
import database
import email_service
import rate_limiter
import user_service
from models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    ResetPasswordRequest,
    Token,
    User,
)
from security import (
    create_access_token,
    create_reset_token,
    create_reset_token_expiry,
    get_current_user,
    hash_password,
    invalidate_reset_token,
    validate_reset_token,
    verify_password,
)

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


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(payload: ForgotPasswordRequest, request: Request) -> dict[str, str]:
    """Solicita un enlace de restablecimiento para un email.

    Devuelve siempre 200 independientemente de si el email existe, para
    evitar la enumeración de usuarios.
    """
    ip_address = request.client.host if request.client else None
    email = payload.email

    # Rate limiting: prevenir abusos por dirección de email.
    if not rate_limiter.check_rate_limit(email):
        audit_logger.record_reset_event(
            event="rate_limit_exceeded",
            email=email,
            ip_address=ip_address,
            status="warning",
            metadata={"action": "forgot_password"},
        )
        # Devolvemos 200 aunque haya rate limit, para no filtrar información.
        return {"message": "Si esa dirección está registrada, recibirás un enlace en breve."}

    user = user_service.get_user_by_email(email)

    if user is not None and user.is_active:
        token = create_reset_token(user.id)
        # Persistimos el token para poder invalidarlo tras su uso.
        database.get_reset_tokens_table().insert(
            {"token": token, "user_id": user.id, "expires_at": create_reset_token_expiry().isoformat()}
        )
        email_service.send_password_reset_email(user.email, token)

        audit_logger.record_reset_event(
            event="forgot_password_requested",
            email=email,
            user_id=user.id,
            ip_address=ip_address,
            status="success",
            metadata={"action": "forgot_password"},
        )
    else:
        audit_logger.record_reset_event(
            event="forgot_password_requested",
            email=email,
            ip_address=ip_address,
            status="info",
            metadata={"action": "forgot_password", "reason": "user_not_found_or_inactive"},
        )

    return {"message": "Si esa dirección está registrada, recibirás un enlace en breve."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest, request: Request) -> dict[str, str]:
    """Restablece la contraseña usando un token de restablecimiento.

    Valida la firma y expiración del token, hashea la nueva contraseña,
    actualiza el usuario e invalida el token para que no pueda reutilizarse.
    """
    ip_address = request.client.host if request.client else None

    try:
        user_id = validate_reset_token(payload.token)
    except HTTPException:
        audit_logger.record_reset_event(
            event="reset_password_rejected",
            ip_address=ip_address,
            status="warning",
            metadata={"action": "reset_password", "reason": "invalid_or_expired_token"},
        )
        raise

    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        audit_logger.record_reset_event(
            event="reset_password_rejected",
            email=user.email if user else None,
            user_id=user_id,
            ip_address=ip_address,
            status="warning",
            metadata={"action": "reset_password", "reason": "user_not_found_or_inactive"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento no es válido o ha expirado.",
        )

    user_service.update_user(
        user_id,
        {"hashed_password": hash_password(payload.new_password)},
    )
    invalidate_reset_token(payload.token)

    audit_logger.record_reset_event(
        event="password_reset_completed",
        email=user.email,
        user_id=user_id,
        ip_address=ip_address,
        status="success",
        metadata={"action": "reset_password"},
    )

    return {"message": "Contraseña restablecida correctamente."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Cambia la contraseña del usuario autenticado.

    Verifica la contraseña actual antes de aplicar la nueva.
    """
    ip_address = request.client.host if request.client else None

    if not verify_password(payload.current_password, current_user.hashed_password):
        audit_logger.record_reset_event(
            event="change_password_failed",
            email=current_user.email,
            user_id=current_user.id,
            ip_address=ip_address,
            status="warning",
            metadata={"action": "change_password", "reason": "wrong_current_password"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta.",
        )

    user_service.update_user(
        current_user.id,
        {"hashed_password": hash_password(payload.new_password)},
    )

    audit_logger.record_reset_event(
        event="change_password_completed",
        email=current_user.email,
        user_id=current_user.id,
        ip_address=ip_address,
        status="success",
        metadata={"action": "change_password"},
    )

    return {"message": "Contraseña actualizada correctamente."}
