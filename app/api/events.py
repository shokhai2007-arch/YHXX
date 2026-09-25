from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Event, Video
from app.schemas import EventResponse, EventsListResponse

router = APIRouter(prefix="/api/v1/videos", tags=["events"])


@router.get("/{video_id}/events", response_model=EventsListResponse)
async def get_events(video_id: str, db: AsyncSession = Depends(get_db)):
    # Check video exists
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get events
    result = await db.execute(select(Event).where(Event.video_id == video_id).order_by(Event.start_sec))
    events = result.scalars().all()

    return EventsListResponse(
        video_id=video_id,
        events=[EventResponse.model_validate(e) for e in events],
        total_count=len(events)
    )
