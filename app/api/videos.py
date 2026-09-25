import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Job, Video
from app.schemas import JobResponse, VideoResponse
from app.services.inference import run_inference
from app.services.validation import validate_video_file

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", response_model=VideoResponse, status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    camera_id: str = "cam_01",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    # Validate file
    await validate_video_file(file, settings)

    # Generate unique ID
    video_id = f"vid_{uuid.uuid4().hex[:8]}"
    filename = file.filename or "video.mp4"

    # Save file
    upload_path = Path(settings.UPLOAD_DIR) / f"{video_id}.mp4"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Get file size
    size_bytes = upload_path.stat().st_size

    # Get duration via ffprobe
    from app.utils.video_utils import get_video_duration
    duration_sec = get_video_duration(str(upload_path))

    # Create video record
    video = Video(
        id=video_id,
        filename=filename,
        size_bytes=size_bytes,
        duration_sec=duration_sec,
        camera_id=camera_id,
        status="UPLOADED",
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    return VideoResponse.model_validate(video)


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoResponse.model_validate(video)


@router.post("/{video_id}/process", response_model=JobResponse, status_code=202)
async def process_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.status in ["PROCESSING", "COMPLETED"]:
        raise HTTPException(status_code=400, detail=f"Video already {video.status.lower()}")

    # Create job
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    job = Job(
        id=job_id,
        video_id=video_id,
        status="PROCESSING",
        progress=0,
        started_at=datetime.utcnow(),
    )
    video.status = "PROCESSING"
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Add background task
    video_path = str(Path(settings.UPLOAD_DIR) / f"{video_id}.mp4")
    background_tasks.add_task(run_inference, job_id, video_id, video_path)

    return JobResponse.model_validate(job)
