"""
app/api/v1/endpoints/auth.py
──────────────────────────────────────────────────────────────────
All authentication and user-management endpoints:

  POST /auth/register          — self-registration
  POST /auth/login             — login → access + refresh tokens
  POST /auth/refresh           — refresh token rotation
  POST /auth/logout            — revoke refresh token
  GET  /auth/me                — current user profile
  PUT  /auth/me                — update profile
  POST /auth/me/change-password
  POST /auth/password-reset/request
  POST /auth/password-reset/confirm

  GET  /auth/admin/users       — list all users (admin)
  POST /auth/admin/users       — create user (admin)
  PUT  /auth/admin/users/{id}  — update role/status (admin)
  DELETE /auth/admin/users/{id}
  GET  /auth/admin/audit-log   — audit trail (admin)
"""
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.config import get_settings
from app.models.models import User, AuditLog
from app.schemas.auth import (
    UserRegister, UserLogin, UserResponse, UserUpdate,
    TokenResponse, AccessTokenResponse, RefreshRequest,
    PasswordChange, PasswordResetRequest, PasswordResetConfirm,
    AdminUserCreate, AdminUserUpdate, AuditLogResponse,
)
from app.services.auth_service import (
    register_user, login_user, refresh_access_token,
    logout_user, change_password, request_password_reset,
    confirm_password_reset, admin_create_user, write_audit,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Self-registration for researcher/clinician accounts."""
    user = await register_user(db, data, request)
    return UserResponse.model_validate(user)


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and receive access + refresh tokens."""
    access, refresh = await login_user(db, data.email, data.password, request)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── Refresh ───────────────────────────────────────────────────────────────────
@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token — returns new access + refresh token pair."""
    access, new_refresh = await refresh_access_token(db, data.refresh_token, request)
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── Logout ────────────────────────────────────────────────────────────────────
@router.post("/logout", status_code=204)
async def logout(
    data: RefreshRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the supplied refresh token."""
    await logout_user(db, data.refresh_token, current_user.id, request)


# ── My profile ────────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name.strip()
    if data.institution is not None:
        current_user.institution = data.institution
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ── Change password ───────────────────────────────────────────────────────────
@router.post("/me/change-password", status_code=204)
async def change_my_password(
    data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await change_password(db, current_user, data.current_password, data.new_password, request)


# ── Password reset flow ───────────────────────────────────────────────────────
@router.post("/password-reset/request", status_code=202)
async def password_reset_request(
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset token.
    In production this emails the token to the user.
    During development the token is returned in the response body.
    """
    raw_token = await request_password_reset(db, data.email, request)
    if settings.environment == "development" and raw_token:
        return {"message": "Reset token generated (dev mode)", "reset_token": raw_token}
    return {"message": "If that email is registered you will receive a reset link"}


@router.post("/password-reset/confirm", status_code=204)
async def password_reset_confirm(
    data: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await confirm_password_reset(db, data.token, data.new_password, request)


# ── Admin: list users ─────────────────────────────────────────────────────────
@router.get("/admin/users", response_model=list[UserResponse])
async def admin_list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    return [UserResponse.model_validate(u) for u in result.scalars()]


# ── Admin: create user ────────────────────────────────────────────────────────
@router.post("/admin/users", response_model=UserResponse, status_code=201)
async def admin_create(
    data: AdminUserCreate,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user = await admin_create_user(db, data, current_user.id, request)
    return UserResponse.model_validate(user)


# ── Admin: update user ────────────────────────────────────────────────────────
@router.put("/admin/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: str,
    data: AdminUserUpdate,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.is_verified is not None:
        user.is_verified = data.is_verified

    await db.commit()
    await db.refresh(user)
    await write_audit(
        db, "admin_updated_user", user_id=current_user.id,
        resource=user_id, detail=data.model_dump(exclude_none=True), request=request,
    )
    return UserResponse.model_validate(user)


# ── Admin: delete user ────────────────────────────────────────────────────────
@router.delete("/admin/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await write_audit(
        db, "admin_deleted_user", user_id=current_user.id,
        resource=user_id, detail={"email": user.email}, request=request,
    )
    await db.delete(user)
    await db.commit()


# ── Admin: audit log ──────────────────────────────────────────────────────────
@router.get("/admin/audit-log", response_model=list[AuditLogResponse])
async def admin_audit_log(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .offset(skip).limit(limit)
    )
    return [AuditLogResponse.model_validate(log) for log in result.scalars()]
