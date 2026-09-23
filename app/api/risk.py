from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Video, RiskScore
from app.schemas import RiskScoreResponse

router = APIRouter(prefix="/api/v1/videos", tags=["risk"])


@router.get("/{video_id}/risk", response_model=RiskScoreResponse)
async def get_risk(video_id: str, db: AsyncSession = Depends(get_db)):
    # Check video exists
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get risk score
    result = await db.execute(select(RiskScore).where(RiskScore.video_id == video_id))
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk score not found. Process video first.")

    return RiskScoreResponse.model_validate(risk)