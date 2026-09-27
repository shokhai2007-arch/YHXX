from pathlib import Path

import pytest

from tests.conftest import create_test_events, create_test_job, create_test_risk


class TestJobStatus:
    """Tests for GET /api/v1/jobs/{id}."""

    @pytest.mark.asyncio
    async def test_get_job_success(self, async_client, db_session, clean_db):
        """Test getting job status."""
        job = await create_test_job(
            db_session,
            video_id="vid_job123",
            job_id="job_test123",
            status="PROCESSING",
            progress=50
        )

        response = await async_client.get("/api/v1/jobs/job_test123")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job_test123"
        assert data["video_id"] == "vid_job123"
        assert data["status"] == "PROCESSING"
        assert data["progress"] == 50

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, async_client):
        """Test getting non-existent job returns 404."""
        response = await async_client.get("/api/v1/jobs/job_nonexistent")

        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_job_completed(self, async_client, db_session, clean_db):
        """Test getting completed job."""
        job = await create_test_job(
            db_session,
            video_id="vid_job456",
            job_id="job_done123",
            status="COMPLETED",
            progress=100
        )

        response = await async_client.get("/api/v1/jobs/job_done123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["progress"] == 100
        assert data["completed_at"] is not None


class TestEvents:
    """Tests for GET /api/v1/videos/{id}/events."""

    @pytest.mark.asyncio
    async def test_get_events_success(self, async_client, db_session, clean_db):
        """Test getting events for video."""
        from tests.conftest import create_test_video

        video = await create_test_video(db_session, video_id="vid_evt123")
        events = await create_test_events(
            db_session,
            video_id="vid_evt123",
            job_id="job_evt123",
            events_data=[
                {"start_sec": 10.0, "end_sec": 15.0, "label": "speeding", "track_id": 1, "confidence": 0.9},
                {"start_sec": 20.0, "end_sec": 25.0, "label": "illegal_parking", "track_id": 2, "confidence": 0.85},
            ]
        )

        response = await async_client.get("/api/v1/videos/vid_evt123/events")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "vid_evt123"
        assert data["total_count"] == 2
        assert len(data["events"]) == 2

        event = data["events"][0]
        assert event["start_sec"] == 10.0
        assert event["end_sec"] == 15.0
        assert event["label"] == "speeding"
        assert event["track_id"] == 1
        assert event["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_get_events_empty(self, async_client, db_session, clean_db):
        """Test getting events when none exist."""
        from tests.conftest import create_test_video

        await create_test_video(db_session, video_id="vid_no_events")

        response = await async_client.get("/api/v1/videos/vid_no_events/events")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "vid_no_events"
        assert data["total_count"] == 0
        assert data["events"] == []

    @pytest.mark.asyncio
    async def test_get_events_video_not_found(self, async_client):
        """Test getting events for non-existent video."""
        response = await async_client.get("/api/v1/videos/vid_nonexistent/events")

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_events_sorted_by_start(self, async_client, db_session, clean_db):
        """Test events are sorted by start time."""
        from tests.conftest import create_test_video

        video = await create_test_video(db_session, video_id="vid_sort123")
        await create_test_events(
            db_session,
            video_id="vid_sort123",
            job_id="job_sort123",
            events_data=[
                {"start_sec": 30.0, "end_sec": 35.0, "label": "speeding", "track_id": 1, "confidence": 0.9},
                {"start_sec": 10.0, "end_sec": 15.0, "label": "illegal_parking", "track_id": 2, "confidence": 0.85},
                {"start_sec": 20.0, "end_sec": 25.0, "label": "wrong_way", "track_id": 3, "confidence": 0.8},
            ]
        )

        response = await async_client.get("/api/v1/videos/vid_sort123/events")

        assert response.status_code == 200
        data = response.json()

        start_times = [e["start_sec"] for e in data["events"]]
        assert start_times == [10.0, 20.0, 30.0]  # Sorted


class TestRisk:
    """Tests for GET /api/v1/videos/{id}/risk."""

    @pytest.mark.asyncio
    async def test_get_risk_success(self, async_client, db_session, clean_db):
        """Test getting risk scores."""
        from tests.conftest import create_test_video

        video = await create_test_video(db_session, video_id="vid_risk123")
        risk = await create_test_risk(
            db_session,
            video_id="vid_risk123",
            overall_risk=0.7,
            by_category={
                "speeding": 0.8,
                "illegal_parking": 0.4,
                "illegal_uturn": 0.0,
                "wrong_way": 0.0,
                "stop_line_crossing": 0.2,
            }
        )

        response = await async_client.get("/api/v1/videos/vid_risk123/risk")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "vid_risk123"
        assert data["overall_risk"] == 0.7
        assert data["by_category"]["speeding"] == 0.8
        assert data["by_category"]["illegal_parking"] == 0.4
        assert data["high_risk_tracks"] == [1]

    @pytest.mark.asyncio
    async def test_get_risk_video_not_found(self, async_client):
        """Test getting risk for non-existent video."""
        response = await async_client.get("/api/v1/videos/vid_nonexistent/risk")

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_risk_not_processed(self, async_client, db_session, clean_db):
        """Test getting risk for video not yet processed."""
        from tests.conftest import create_test_video

        await create_test_video(db_session, video_id="vid_norisk")

        response = await async_client.get("/api/v1/videos/vid_norisk/risk")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestResults:
    """Tests for GET /api/v1/videos/{id}/result."""

    @pytest.mark.asyncio
    async def test_get_result_success(self, async_client, db_session, clean_db):
        """Test getting result URLs."""
        from tests.conftest import create_test_video

        video = await create_test_video(
            db_session,
            video_id="vid_res123",
            status="COMPLETED"
        )

        # Create output directory and files
        from app.config import settings
        output_dir = Path(settings.OUTPUT_DIR) / "video_vid_res123"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "annotated.mp4").write_bytes(b"fake video")
        (output_dir / "thumbnail.jpg").write_bytes(b"fake thumb")
        (output_dir / "result.json").write_text('{"test": "data"}')

        response = await async_client.get("/api/v1/videos/vid_res123/result")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "vid_res123"
        assert "annotated_video_url" in data
        assert "thumbnail_url" in data
        assert "result_json_url" in data

        # Cleanup
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_get_result_video_not_found(self, async_client):
        """Test getting result for non-existent video."""
        response = await async_client.get("/api/v1/videos/vid_nonexistent/result")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_result_not_completed(self, async_client, db_session, clean_db):
        """Test getting result for video not completed."""
        from tests.conftest import create_test_video

        await create_test_video(db_session, video_id="vid_processing", status="PROCESSING")

        response = await async_client.get("/api/v1/videos/vid_processing/result")

        assert response.status_code == 400
        assert "not completed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_result_missing_files(self, async_client, db_session, clean_db):
        """Test getting result when output files missing."""
        from tests.conftest import create_test_video

        await create_test_video(db_session, video_id="vid_missing", status="COMPLETED")

        # Don't create output files
        response = await async_client.get("/api/v1/videos/vid_missing/result")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
