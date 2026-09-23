from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, REAL, TIMESTAMP, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("video.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("job.id"), nullable=False)
    start_sec: Mapped[float] = mapped_column(REAL, nullable=False)
    end_sec: Mapped[float] = mapped_column(REAL, nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(REAL, default=0.9)
    event_metadata: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

    video: Mapped["Video"] = relationship(back_populates="events")
    job: Mapped["Job"] = relationship(back_populates="events")


Index("idx_event_video_id", Event.video_id)
Index("idx_event_job_id", Event.job_id)