"""
app/core/dependencies.py
──────────────────────────────────────────────────────────────────
FastAPI dependencies:
  - get_current_user  → verifies JWT, returns User ORM object
  - require_role      → RBAC factory (researcher | clinician | admin)
  - get_audit_logger  → audit trail helper
"""
from typing import Callable
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.models import User

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {"researcher": 0, "clinician": 1, "admin": 2}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT access token and return the authenticated User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: str) -> Callable:
    """
    RBAC factory.  Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    Roles: researcher | clinician | admin
    """
    async def checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access requires one of: {', '.join(roles)}",
            )
        return current_user
    return checker


# Shorthand dependency singletons
RequireResearcher = Depends(require_role("researcher", "clinician", "admin"))
RequireClinician  = Depends(require_role("clinician", "admin"))
RequireAdmin      = Depends(require_role("admin"))
