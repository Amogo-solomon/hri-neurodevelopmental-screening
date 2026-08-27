from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db
from app.schemas.schemas import HealthResponse
from app.services.vlm_service import OllamaVLMService
from app.core.config import get_settings

router   = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Overall platform health — used by frontend status indicator."""
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    vlm          = OllamaVLMService(settings.ollama_base_url, settings.vlm_model)
    ollama_ok    = await vlm.check_health()

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=settings.app_version,
        ollama_available=ollama_ok,
        ollama_model=settings.vlm_model,
        database_ok=db_ok,
    )


@router.get("/ollama")
async def ollama_detail():
    """
    Detailed Ollama status — called by frontend to show actionable guidance
    when VLM is not ready.
    """
    vlm      = OllamaVLMService(settings.ollama_base_url, settings.vlm_model)
    models   = await vlm.list_available_models()
    model_ok = await vlm.check_health()

    return {
        "reachable":        len(models) >= 0,   # list_available_models returns [] on error
        "configured_model": settings.vlm_model,
        "model_available":  model_ok,
        "available_models": models,
        "pull_command":     f"docker exec hri_ollama ollama pull {settings.vlm_model}",
        "guidance": (
            "Ready" if model_ok
            else f"Model not found. Run: docker exec hri_ollama ollama pull {settings.vlm_model}"
        ),
    }
