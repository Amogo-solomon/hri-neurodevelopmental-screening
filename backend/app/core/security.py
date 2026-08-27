"""
app/core/security.py
──────────────────────────────────────────────────────────────────
JWT access/refresh token generation & verification
Password hashing (bcrypt, work factor 12)
Refresh-token rotation with secure hash storage
Rate-limiting helpers for brute-force protection
"""
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password hashing ─────────────────────────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────
ALGORITHM = "HS256"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Short-lived JWT access token (default 30 min)."""
    expire = _utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {
        "sub": subject,        # user id
        "role": role,
        "exp": expire,
        "iat": _utcnow(),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Generate an opaque refresh token.
    Returns (raw_token, sha256_hash, expires_at).
    Only the hash is stored in the DB.
    """
    raw = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = _utcnow() + timedelta(days=settings.refresh_token_expire_days)
    return raw, token_hash, expires_at


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token. Raises JWTError on failure."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        return payload
    except JWTError:
        raise
