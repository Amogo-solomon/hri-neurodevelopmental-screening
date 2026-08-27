"""
app/schemas/auth.py — Pydantic v2 schemas for authentication flows
"""
import re
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional
from datetime import datetime


# ── Password validation ───────────────────────────────────────────────────────
PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_\-#])[A-Za-z\d@$!%*?&_\-#]{8,64}$"
)

def _validate_password(v: str) -> str:
    if not PASSWORD_RE.match(v):
        raise ValueError(
            "Password must be 8-64 characters and include uppercase, lowercase, "
            "a digit, and a special character (@$!%*?&_-#)"
        )
    return v


# ── Registration ──────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    institution: Optional[str] = None
    role: Optional[str] = "researcher"   # researcher|clinician (admin set manually)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ("researcher", "clinician"):
            raise ValueError("Self-registration role must be researcher or clinician")
        return v


# ── Login ─────────────────────────────────────────────────────────────────────
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ── Token responses ───────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # access token seconds


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ── User profile ──────────────────────────────────────────────────────────────
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    institution: Optional[str]
    created_at: datetime
    last_login_at: Optional[datetime]


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    institution: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


# ── Password reset ────────────────────────────────────────────────────────────
class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


# ── Admin user management ─────────────────────────────────────────────────────
class AdminUserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "researcher"
    institution: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ("researcher", "clinician", "admin"):
            raise ValueError("Role must be researcher, clinician, or admin")
        return v


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("researcher", "clinician", "admin"):
            raise ValueError("Role must be researcher, clinician, or admin")
        return v


# ── Audit log ─────────────────────────────────────────────────────────────────
class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Optional[str]
    action: str
    resource: Optional[str]
    ip_address: Optional[str]
    detail: Optional[dict]
    created_at: datetime
