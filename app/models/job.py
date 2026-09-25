from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Job(Base):
    __tablename__ = "job"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("video.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

    video: Mapped["Video"] = relationship(back_populates="jobs")
    events: Mapped[list["Event"]] = relationship(back_populates="job", cascade="all, delete-orphan")
