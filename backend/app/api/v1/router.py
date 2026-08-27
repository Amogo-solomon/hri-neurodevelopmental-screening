from fastapi import APIRouter
from app.api.v1.endpoints import upload, analysis, health, auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(upload.router)
api_router.include_router(analysis.router)
api_router.include_router(health.router)
