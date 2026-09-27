from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


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
    processed_at: datetime | None = None

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    video_id: str


class JobCreate(JobBase):
    pass


class JobResponse(BaseModel):
    """API'da job `job_id` nomi bilan tanilgan (docs/frontend shartnomasi).

    Modelda esa PK `id` — validator ikkala nomni qabul qiladi,
    serijalizatsiya har doim `job_id` beradi.
    """

    job_id: str = Field(validation_alias="id", serialization_alias="job_id")
    video_id: str
    status: str
    progress: int
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class EventBase(BaseModel):
    start_sec: float
    end_sec: float
    label: str
    track_id: int
    confidence: float = 0.9
    event_metadata: dict = Field(default_factory=dict)

    # JSON bo'lmagan bazalarda JSONB o'rniga dict emas, string bo'lishi mumkin;
    # shuningdek None bo'sh lug'atga aylanadi (response contract barqaror bo'lishi uchun).
    @field_validator("event_metadata", mode="before")
    @classmethod
    def _coerce_event_metadata(cls, v: Any) -> dict:
        if v is None:
            return {}
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return v


class EventResponse(EventBase):
    id: int
    video_id: str
    job_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class EventsListResponse(BaseModel):
    video_id: str
    events: list[EventResponse]
    total_count: int


class RiskCategory(BaseModel):
    """by_category — ochiq lug'at (engine CLASSES kalitlari) / Open dict keyed by event label."""

    model_config = {"extra": "allow"}

    accident: float = 0.0
    near_miss: float = 0.0
    red_light: float = 0.0
    wrong_way: float = 0.0
    illegal_u_turn: float = 0.0
    stopped_vehicle: float = 0.0
    jaywalking: float = 0.0
    failure_to_yield: float = 0.0
    illegal_turn: float = 0.0
    solid_line_crossing: float = 0.0
    stop_line: float = 0.0
    congestion: float = 0.0
    road_obstacle: float = 0.0
    fire_smoke: float = 0.0


class RiskScoreBase(BaseModel):
    overall_risk: float
    by_category: RiskCategory
    high_risk_tracks: list[int] = Field(default_factory=list)

    @field_validator("high_risk_tracks", mode="before")
    @classmethod
    def _coerce_high_risk_tracks(cls, v: Any) -> list:
        # Bazada JSON string sifatida saqlangan bo'lishi mumkin; None -> []
        if v is None:
            return []
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v


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
