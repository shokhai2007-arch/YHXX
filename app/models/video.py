from datetime import datetime
from sqlalchemy import String, BigInteger, REAL, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Video(Base):
    __tablename__ = "video"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_sec: Mapped[float] = mapped_column(REAL, nullable=False)
    camera_id: Mapped[str] = mapped_column(String(64), default="cam_01")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    processed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)

    jobs: Mapped[list["Job"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    risk_score: Mapped["RiskScore"] = relationship(back_populates="video", uselist=False, cascade="all, delete-orphan")