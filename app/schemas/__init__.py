from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VideoBase(BaseModel):
    filename: str
    size_bytes: int
    duration_sec: float
    camera_id: str = "cam_01"


class VideoCreate(VideoBase):
    pass


class VideoResponse(VideoBase):
    id: str
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    video_id: str


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    id: str
    status: str
    progress: int
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EventBase(BaseModel):
    start_sec: float
    end_sec: float
    label: str
    track_id: int
    confidence: float = 0.9
    event_metadata: dict = {}


class EventResponse(EventBase):
    id: int
    video_id: str
    job_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class EventsListResponse(BaseModel):
    video_id: str
    events: List[EventResponse]
    total_count: int


class RiskCategory(BaseModel):
    speeding: float = 0.0
    illegal_parking: float = 0.0
    illegal_uturn: float = 0.0
    wrong_way: float = 0.0
    stop_line_crossing: float = 0.0


class RiskScoreBase(BaseModel):
    overall_risk: float
    by_category: RiskCategory
    high_risk_tracks: List[int] = []


class RiskScoreResponse(RiskScoreBase):
    video_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class ResultResponse(BaseModel):
    video_id: str
    annotated_video_url: str
    thumbnail_url: str
    result_json_url: str


class HealthResponse(BaseModel):
    status: str
    version: str