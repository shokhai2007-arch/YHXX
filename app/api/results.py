from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Video
from app.schemas import ResultResponse

router = APIRouter(prefix="/api/v1/videos", tags=["results"])


@router.get("/{video_id}/result", response_model=ResultResponse)
async def get_result(video_id: str, db: AsyncSession = Depends(get_db)):
    # Check video exists
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Video processing not completed")

    output_dir = Path(settings.OUTPUT_DIR) / f"video_{video_id}"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output files not found")

    return ResultResponse(
        video_id=video_id,
        annotated_video_url=f"/api/v1/outputs/video_{video_id}/annotated.mp4",
        thumbnail_url=f"/api/v1/outputs/video_{video_id}/thumbnail.jpg",
        result_json_url=f"/api/v1/outputs/video_{video_id}/result.json"
    )
