from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings
from app.db.database import init_db, AsyncSessionLocal
from app.api.v1.router import api_router

logger = structlog.get_logger()
settings = get_settings()


async def _seed_admin():
    """Create first admin account on first run if no users exist."""
    from sqlalchemy import select, func
    from app.models.models import User
    from app.core.security import hash_password

    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(User))
        if count == 0:
            admin = User(
                email=settings.first_admin_email,
                full_name=settings.first_admin_name,
                hashed_password=hash_password(settings.first_admin_password),
                role="admin",
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            await db.commit()
            logger.info("admin_seeded", email=settings.first_admin_email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", app=settings.app_name, version=settings.app_version)
    await init_db()
    await _seed_admin()
    import os
    os.makedirs(settings.upload_dir, exist_ok=True)
    yield
    logger.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Explainable Behaviour Analysis Platform for Human-Robot Interaction. "
        "JWT-authenticated, RBAC-protected. Research use only."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }
