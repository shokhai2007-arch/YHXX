import asyncio
import os
import subprocess
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from app.models import Event, Job, RiskScore, Video

# Test database URL (uses separate test database)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://cyberleek:changeme@localhost:5432/cyberleek_test"
)

# Test settings
test_settings = Settings(
    DATABASE_URL=TEST_DATABASE_URL,
    REDIS_URL="redis://localhost:6379/1",
    UPLOAD_DIR="/tmp/cyberleek_test_uploads",
    OUTPUT_DIR="/tmp/cyberleek_test_outputs",
    CAMERA_CONFIG_PATH="configs/camera.yaml",
    MAX_UPLOAD_SIZE_MB=100,
    MAX_DURATION_SEC=120,
    ALLOWED_MIME_TYPES=["video/mp4"],
    ENVIRONMENT="testing",
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_dirs():
    """Create test directories."""
    Path(test_settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(test_settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup after all tests
    import shutil
    shutil.rmtree(test_settings.UPLOAD_DIR, ignore_errors=True)
    shutil.rmtree(test_settings.OUTPUT_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with transaction rollback."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        # Begin transaction
        async with session.begin():
            yield session
        # Rollback happens automatically


@pytest.fixture(scope="function")
def override_get_db(db_session: AsyncSession):
    """Override get_db dependency."""
    async def _override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_client(override_get_db) -> TestClient:
    """Sync test client."""
    return TestClient(app)


@pytest.fixture(scope="function")
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session")
def sample_video_path() -> Path:
    """Generate a small test video using ffmpeg lavfi."""
    video_path = Path("/tmp/test_video_sample.mp4")
    if not video_path.exists():
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "testsrc=duration=5:size=1280x720:rate=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            pytest.skip(f"Could not create test video: {result.stderr}")
    return video_path


@pytest.fixture(scope="session")
def invalid_video_path() -> Path:
    """Create an invalid video file (text file with .mp4 extension)."""
    video_path = Path("/tmp/invalid_video.mp4")
    video_path.write_text("This is not a video file")
    return video_path


@pytest.fixture(scope="function")
async def clean_db(db_session: AsyncSession):
    """Clean all tables before test."""
    for table in [Event, Job, RiskScore, Video]:
        await db_session.execute(table.__table__.delete())
    await db_session.commit()


# Helper functions for tests
async def create_test_video(
    db: AsyncSession,
    video_id: str = None,
    filename: str = "test.mp4",
    status: str = "UPLOADED",
) -> Video:
    """Create a test video record."""
    if video_id is None:
        import uuid
        video_id = f"vid_{uuid.uuid4().hex[:8]}"

    video = Video(
        id=video_id,
        filename=filename,
        size_bytes=1024000,
        duration_sec=30.0,
        camera_id="cam_01",
        status=status,
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return video


async def create_test_job(
    db: AsyncSession,
    video_id: str,
    job_id: str = None,
    status: str = "PROCESSING",
    progress: int = 0,
) -> Job:
    """Create a test job record."""
    if job_id is None:
        import uuid
        job_id = f"job_{uuid.uuid4().hex[:8]}"

    job = Job(
        id=job_id,
        video_id=video_id,
        status=status,
        progress=progress,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def create_test_events(
    db: AsyncSession,
    video_id: str,
    job_id: str,
    events_data: list = None,
) -> list[Event]:
    """Create test event records."""
    if events_data is None:
        events_data = [
            {"start_sec": 10.0, "end_sec": 15.0, "label": "speeding", "track_id": 1, "confidence": 0.9},
            {"start_sec": 20.0, "end_sec": 25.0, "label": "illegal_parking", "track_id": 2, "confidence": 0.85},
        ]

    events = []
    for data in events_data:
        event = Event(
            video_id=video_id,
            job_id=job_id,
            **data,
        )
        db.add(event)
        events.append(event)

    await db.commit()
    for event in events:
        await db.refresh(event)
    return events


async def create_test_risk(
    db: AsyncSession,
    video_id: str,
    overall_risk: float = 0.5,
    by_category: dict = None,
) -> RiskScore:
    """Create a test risk score record."""
    if by_category is None:
        by_category = {
            "speeding": 0.8,
            "illegal_parking": 0.3,
            "illegal_uturn": 0.0,
            "wrong_way": 0.0,
            "stop_line_crossing": 0.0,
        }

    risk = RiskScore(
        video_id=video_id,
        overall_risk=overall_risk,
        by_category=by_category,
        high_risk_tracks=[1],
    )
    db.add(risk)
    await db.commit()
    await db.refresh(risk)
    return risk
