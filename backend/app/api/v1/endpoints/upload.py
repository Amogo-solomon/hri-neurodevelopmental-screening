import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.models import VideoUpload
from app.schemas.schemas import VideoUploadResponse
from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.models.models import User
from app.services.video_processor import VideoProcessor
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/upload", tags=["upload"])
settings = get_settings()


@router.post("/video", response_model=VideoUploadResponse)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a video file (up to 8GB) for HRI behavioural analysis.
    Validates file type, streams to disk, computes integrity checksum.
    """
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.allowed_video_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(settings.allowed_video_extensions)}",
        )

    # Validate content-type
    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video.")

    # Generate safe unique filename
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}{ext}"
    upload_path = os.path.join(settings.upload_dir, safe_filename)

    # Stream file to disk in chunks (handles 2GB without RAM overflow)
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB chunks

    os.makedirs(settings.upload_dir, exist_ok=True)

    try:
        async with aiofiles.open(upload_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_size_bytes:
                    await f.close()
                    os.remove(upload_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {settings.max_upload_size_mb}MB",
                    )
                await f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(upload_path):
            os.remove(upload_path)
        logger.error("upload_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Compute checksum and extract video metadata
    processor = VideoProcessor(settings.upload_dir)

    checksum = processor.compute_sha256(upload_path)

    try:
        meta = processor.validate_video(upload_path)
    except Exception as e:
        os.remove(upload_path)
        raise HTTPException(status_code=422, detail=f"Invalid video file: {str(e)}")

    # Persist to DB
    video = VideoUpload(
        id=file_id,
        filename=safe_filename,
        original_filename=file.filename or safe_filename,
        file_size=total_bytes,
        duration_seconds=meta.get("duration_seconds"),
        fps=meta.get("fps"),
        width=meta.get("width"),
        height=meta.get("height"),
        mime_type=file.content_type or f"video/{ext[1:]}",
        upload_path=upload_path,
        checksum_sha256=checksum,
        status="uploaded",
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    logger.info(
        "video_uploaded",
        video_id=file_id,
        filename=file.filename,
        size_mb=round(total_bytes / 1024 / 1024, 2),
        duration=meta.get("duration_seconds"),
    )

    return VideoUploadResponse.model_validate(video)


@router.get("/videos", response_model=list[VideoUploadResponse])
async def list_videos(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(VideoUpload).order_by(VideoUpload.created_at.desc()).limit(50)
    )
    return [VideoUploadResponse.model_validate(v) for v in result.scalars().all()]


@router.get("/videos/{video_id}", response_model=VideoUploadResponse)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(VideoUpload).where(VideoUpload.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoUploadResponse.model_validate(video)


@router.delete("/videos/{video_id}")
async def delete_video(video_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete video and associated data (right to erasure - UK GDPR Article 17)."""
    result = await db.execute(select(VideoUpload).where(VideoUpload.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Remove file from disk
    if os.path.exists(video.upload_path):
        os.remove(video.upload_path)

    await db.delete(video)
    await db.commit()
    return {"message": "Video and all associated data deleted", "video_id": video_id}
