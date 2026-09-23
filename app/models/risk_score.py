from datetime import datetime
from typing import List
from sqlalchemy import String, ForeignKey, REAL, TIMESTAMP, JSON, Index, Integer
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RiskScore(Base):
    __tablename__ = "risk_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("video.id"), unique=True, nullable=False)
    overall_risk: Mapped[float] = mapped_column(REAL, nullable=False)
    by_category: Mapped[dict] = mapped_column(JSON, nullable=False)
    high_risk_tracks: Mapped[List[int]] = mapped_column(ARRAY(Integer), default=[])
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

    video: Mapped["Video"] = relationship(back_populates="risk_score")