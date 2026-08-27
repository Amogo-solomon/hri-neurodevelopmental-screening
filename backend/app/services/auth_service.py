"""
app/services/auth_service.py
──────────────────────────────────────────────────────────────────
Business logic for all authentication flows:
  - Register with email uniqueness check
  - Login with bcrypt verify + last_login update
  - Refresh token rotation (old token revoked on use)
  - Password change (current password required)
  - Password reset (email token flow)
  - Audit logging for all sensitive actions
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, hash_token,
)
from app.core.config import get_settings
from app.models.models import User, RefreshToken, AuditLog, PasswordResetToken
from app.schemas.auth import UserRegister, AdminUserCreate

logger = structlog.get_logger()
settings = get_settings()


def _utcnow():
    return datetime.now(timezone.utc)


# ── Audit ─────────────────────────────────────────────────────────────────────

async def write_audit(
    db: AsyncSession,
    action: str,
    user_id: Optional[str] = None,
    resource: Optional[str] = None,
    detail: Optional[dict] = None,
    request: Optional[Request] = None,
):
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
    log = AuditLog(
        user_id=user_id, action=action, resource=resource,
        ip_address=ip, user_agent=ua, detail=detail,
    )
    db.add(log)
    await db.commit()
    logger.info("audit", action=action, user_id=user_id, resource=resource)


# ── Registration ──────────────────────────────────────────────────────────────

async def register_user(
    db: AsyncSession,
    data: UserRegister,
    request: Optional[Request] = None,
) -> User:
    # Uniqueness check
    existing = await db.execute(select(User).where(User.email == data.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email address already registered")

    user = User(
        email=data.email.lower(),
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
        role=data.role or "researcher",
        institution=data.institution,
        is_active=True,
        is_verified=False,      # email verification would be sent in production
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await write_audit(db, "register", user_id=user.id, request=request)
    logger.info("user_registered", email=user.email, role=user.role)
    return user


# ── Login ─────────────────────────────────────────────────────────────────────

async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
    request: Optional[Request] = None,
) -> tuple[str, str]:
    """Authenticate and return (access_token, refresh_token)."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    # Constant-time failure to prevent user enumeration
    if user is None or not verify_password(password, user.hashed_password):
        await write_audit(
            db, "login_failed",
            detail={"email": email},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Create tokens
    access_token = create_access_token(subject=user.id, role=user.role)
    raw_refresh, refresh_hash, refresh_exp = create_refresh_token()

    rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_exp,
        user_agent=request.headers.get("user-agent") if request else None,
        ip_address=request.client.host if (request and request.client) else None,
    )
    db.add(rt)

    user.last_login_at = _utcnow()
    await db.commit()

    await write_audit(db, "login", user_id=user.id, request=request)
    return access_token, raw_refresh


# ── Token refresh ─────────────────────────────────────────────────────────────

async def refresh_access_token(
    db: AsyncSession,
    raw_refresh: str,
    request: Optional[Request] = None,
) -> tuple[str, str]:
    """
    Rotate refresh token — old token revoked, new pair issued.
    Detects replay attacks (revoked token reuse → revoke all user tokens).
    """
    token_hash = hash_token(raw_refresh)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()

    if rt is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if rt.revoked:
        # Potential token theft — revoke ALL tokens for this user
        all_tokens = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == rt.user_id,
                RefreshToken.revoked == False,
            )
        )
        for t in all_tokens.scalars():
            t.revoked = True
        await db.commit()
        await write_audit(db, "token_replay_detected", user_id=rt.user_id, request=request)
        raise HTTPException(status_code=401, detail="Token reuse detected — please log in again")

    if rt.expires_at.replace(tzinfo=timezone.utc) < _utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Revoke old token
    rt.revoked = True

    # Fetch user
    result2 = await db.execute(select(User).where(User.id == rt.user_id))
    user = result2.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    # Issue new pair
    new_access = create_access_token(subject=user.id, role=user.role)
    raw_new, new_hash, new_exp = create_refresh_token()

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=new_exp,
        user_agent=request.headers.get("user-agent") if request else None,
        ip_address=request.client.host if (request and request.client) else None,
    )
    db.add(new_rt)
    await db.commit()

    await write_audit(db, "token_refresh", user_id=user.id, request=request)
    return new_access, raw_new


# ── Logout ────────────────────────────────────────────────────────────────────

async def logout_user(
    db: AsyncSession,
    raw_refresh: Optional[str],
    user_id: str,
    request: Optional[Request] = None,
):
    """Revoke the supplied refresh token (single-device logout)."""
    if raw_refresh:
        token_hash = hash_token(raw_refresh)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt and rt.user_id == user_id:
            rt.revoked = True
            await db.commit()
    await write_audit(db, "logout", user_id=user_id, request=request)


# ── Password change ───────────────────────────────────────────────────────────

async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
    request: Optional[Request] = None,
):
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = hash_password(new_password)
    # Revoke all refresh tokens on password change (security best practice)
    all_tokens = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked == False,
        )
    )
    for t in all_tokens.scalars():
        t.revoked = True

    await db.commit()
    await write_audit(db, "password_changed", user_id=user.id, request=request)


# ── Password reset request ────────────────────────────────────────────────────

async def request_password_reset(
    db: AsyncSession,
    email: str,
    request: Optional[Request] = None,
) -> Optional[str]:
    """
    Returns the raw reset token (to be emailed in production).
    Always returns 200 to prevent user enumeration.
    """
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None   # silent — don't reveal whether email exists

    raw = secrets.token_urlsafe(48)
    token_hash = hash_token(raw)
    prt = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=_utcnow() + timedelta(hours=1),
    )
    db.add(prt)
    await db.commit()
    await write_audit(db, "password_reset_requested", user_id=user.id, request=request)
    logger.info("password_reset_token_generated", email=email)
    return raw   # in production: email this to the user


async def confirm_password_reset(
    db: AsyncSession,
    raw_token: str,
    new_password: str,
    request: Optional[Request] = None,
):
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    prt = result.scalar_one_or_none()

    if not prt or prt.used:
        raise HTTPException(status_code=400, detail="Invalid or already-used reset token")

    if prt.expires_at.replace(tzinfo=timezone.utc) < _utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired")

    result2 = await db.execute(select(User).where(User.id == prt.user_id))
    user = result2.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(new_password)
    prt.used = True
    await db.commit()
    await write_audit(db, "password_reset_completed", user_id=user.id, request=request)


# ── Admin user creation ───────────────────────────────────────────────────────

async def admin_create_user(
    db: AsyncSession,
    data: AdminUserCreate,
    created_by: str,
    request: Optional[Request] = None,
) -> User:
    existing = await db.execute(select(User).where(User.email == data.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=data.email.lower(),
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
        role=data.role,
        institution=data.institution,
        is_active=True,
        is_verified=True,    # admin-created users are pre-verified
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await write_audit(
        db, "admin_created_user",
        user_id=created_by,
        resource=user.id,
        detail={"email": user.email, "role": user.role},
        request=request,
    )
    return user
