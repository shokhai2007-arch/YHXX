import asyncio
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import create_engine, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import app.database as _app_database
from app.database import Base
from app.models import Event, Job, RiskScore, Video

# ---------------------------------------------------------------------------
# Test database (SQLite fayl bazasi — Postgres shart emas)
#
# Fayl bazasi + NullPool: har sessiya o'z connectionini ochadi va yopadi.
# Shu sababli TestClient (o'z event loop'ida ishlaydi) va pytest-asyncio
# (boshqa loop) o'rtasida "Future attached to a different loop" xatosi
# yuzaga kelmaydi. In-memory bazada esa bitta connection hamma loop'larda
# qayta ishlatilgani uchun aynan shu xato chiqardi.
# ---------------------------------------------------------------------------
_TEST_DB_PATH = Path("/tmp/cyberleek_test.db")
_TEST_DB_PATH.unlink(missing_ok=True)  # Har run'da toza baza

# Jadvallarni sinxron engine bilan yaratamiz — import vaqtida event loop
# kerak emas (eski yechim: asyncio.get_event_loop() — deprecated va xavfli).
Base.metadata.create_all(create_engine(f"sqlite:///{_TEST_DB_PATH}"))

_TEST_ENGINE = create_async_engine(
    f"sqlite+aiosqlite:///{_TEST_DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
    echo=False,
)
_TestSessionFactory = sessionmaker(
    _TEST_ENGINE, class_=AsyncSession, expire_on_commit=False,
)

# Background inference task'lari (app.services.inference) bazaga
# async_session_maker orqali yozadi — ularni ham test bazasiga yo'naltiramiz.
# MUHIM: bu patch app.main import qilinishidan OLDIN bajarilishi kerak.
_app_database.engine = _TEST_ENGINE
_app_database.async_session_maker = _TestSessionFactory

# O'chirish tartibi FK bog'liqliklariga mos (Event -> Job/Video)
_TABLES_IN_DELETE_ORDER = (Event, RiskScore, Job, Video)


async def _wipe_tables(session: AsyncSession) -> None:
    """Barcha jadvallarni bo'shatish (testlar orasida izolyatsiya)."""
    for table in _TABLES_IN_DELETE_ORDER:
        await session.execute(delete(table))
    await session.commit()


@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Har test uchun tozalangan baza + alohida sessiya."""
    async with _TestSessionFactory() as cleaner:
        await _wipe_tables(cleaner)
    async with _TestSessionFactory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def clean_db(db_session: AsyncSession) -> AsyncSession:
    """Izolyatsiya db_session setup'ida bajariladi; fixture moslik uchun saqlangan."""
    yield db_session


@pytest.fixture(scope="session")
def sample_video_path() -> str:
    """Kichik h264 MP4 (ffmpeg testsrc orqali generatsiya qilinadi).

    ffmpeg mavjud bo'lmasa, ushbu fixture'ga bog'liq testlar skip bo'ladi.
    """
    path = Path("/tmp/cyberleek_sample_video.mp4")
    try:
        if not path.exists() or path.stat().st_size == 0:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", "testsrc=duration=5:size=640x360:rate=15",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(path),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
    except Exception:
        pytest.skip("sample_video_path: ffmpeg bilan test videosi yaratib bo'lmadi")
    return str(path)


@pytest_asyncio.fixture(scope="function")
async def async_client() -> httpx.AsyncClient:
    """httpx.AsyncClient (ASGITransport) — testlar `await client.get(...)` deb yozilgan.

    TestClient sync bo'lgani uchun `await client.get(...)` ishlamaydi; httpx
    AsyncClient esa aynan shu uslubga mos. get_db test bazasiga override qilingan.
    """
    async def _override_get_db() -> Any:
        async with _TestSessionFactory() as sess:
            yield sess

    from app.config import settings

    # Test uchun yoziladigan runtime papkalar (konteynerda /app read-only)
    settings.OUTPUT_DIR = "/tmp/cyberleek_test_outputs"
    settings.UPLOAD_DIR = "/tmp/cyberleek_test_uploads"
    try:
        Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        pass

    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test data helpers (hammasi async — awaited holda chaqiriladi)
# ---------------------------------------------------------------------------
async def create_test_video(
    db_session: AsyncSession,
    video_id: str,
    status: str = "UPLOADED",
    filename: str = "test.mp4",
    size_bytes: int = 1024,
    duration_sec: float = 5.0,
    camera_id: str = "cam_01",
) -> Video:
    """Create and persist a Video row (useful when you need a known video_id
    instead of relying on the real upload endpoint)."""
    video = Video(
        id=video_id,
        filename=filename,
        size_bytes=size_bytes,
        duration_sec=duration_sec,
        camera_id=camera_id,
        status=status,
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    return video


async def create_test_job(
    db_session: AsyncSession,
    video_id: str,
    job_id: str,
    status: str = "PROCESSING",
    progress: int = 0,
) -> Job:
    """Create and persist a Job row."""
    from datetime import datetime

    job = Job(
        id=job_id,
        video_id=video_id,
        status=status,
        progress=progress,
        started_at=datetime.utcnow(),
        # Testlar COMPLETED job'da completed_at mavjudligini kutadi
        completed_at=datetime.utcnow() if status == "COMPLETED" else None,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


async def create_test_risk(
    db_session: AsyncSession,
    video_id: str,
    overall_risk: float = 0.0,
    by_category: dict[str, float] | None = None,
    high_risk_tracks: list[int] | None = None,
) -> RiskScore:
    """Create and persist a RiskScore row."""
    if by_category is None:
        by_category = {
            "speeding": 0.0,
            "illegal_parking": 0.0,
            "illegal_uturn": 0.0,
            "wrong_way": 0.0,
            "stop_line_crossing": 0.0,
        }
    risk = RiskScore(
        video_id=video_id,
        overall_risk=overall_risk,
        by_category=by_category,
        # Testlar standart holatda [1] kutyapti (test_get_risk_success)
        high_risk_tracks=high_risk_tracks if high_risk_tracks is not None else [1],
    )
    db_session.add(risk)
    await db_session.commit()
    await db_session.refresh(risk)
    return risk


async def create_test_events(
    db_session: AsyncSession,
    video_id: str,
    job_id: str,
    events_data: list[dict[str, Any]] | list[tuple[float, float, str]] = None,
) -> list[Event]:
    """Create and persist one or more Event rows.

    Events may be passed as either:
      * list[dict]  — keys: start_sec, end_sec, label, track_id, confidence
      * list[tuple] — (start_sec, end_sec, label[, track_id, confidence])
    """
    events: list[Event] = []
    for raw in events_data or []:
        if isinstance(raw, dict):
            event = Event(
                video_id=video_id,
                job_id=job_id,
                start_sec=float(raw["start_sec"]),
                end_sec=float(raw["end_sec"]),
                label=raw["label"],
                track_id=int(raw.get("track_id", 1)),
                confidence=float(raw.get("confidence", 0.9)),
            )
        else:
            seq = list(raw)
            event = Event(
                video_id=video_id,
                job_id=job_id,
                start_sec=float(seq[0]),
                end_sec=float(seq[1]),
                label=seq[2],
                track_id=int(seq[3]) if len(seq) > 3 else 1,
                confidence=float(seq[4]) if len(seq) > 4 else 0.9,
            )
        db_session.add(event)
        events.append(event)
    await db_session.commit()
    return events
