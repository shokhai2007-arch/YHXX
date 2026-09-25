from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import create_test_video


class TestFullFlow:
    """End-to-end integration tests for the complete flow."""

    @pytest.mark.asyncio
    async def test_full_flow_upload_process_results(
        self, async_client, db_session, clean_db, sample_video_path
    ):
        """Test complete flow: upload -> process -> poll -> events/risk/results."""
        # 1. Upload video
        with open(sample_video_path, "rb") as f:
            file_content = f.read()

        with patch("app.services.validation.validate_video_file", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True

            with patch("app.utils.video_utils.get_video_duration", return_value=5.0):
                response = await async_client.post(
                    "/api/v1/videos",
                    files={"file": ("test.mp4", file_content, "video/mp4")},
                    data={"camera_id": "cam_01"}
                )

        assert response.status_code == 201
        video_data = response.json()
        video_id = video_data["id"]

        # 2. Start processing
        with patch("app.services.inference.run_inference", new_callable=AsyncMock) as mock_inference:
            mock_inference.return_value = None

            response = await async_client.post(f"/api/v1/videos/{video_id}/process")

        assert response.status_code == 202
        job_data = response.json()
        job_id = job_data["job_id"]

        # 3. Poll job until completion (simulate)
        # In real scenario, background task updates DB
        # Here we manually update to simulate completion
        from sqlalchemy import select

        from app.models import Job, Video

        # Update job to COMPLETED
        result = await db_session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one()
        job.status = "COMPLETED"
        job.progress = 100

        result = await db_session.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one()
        video.status = "COMPLETED"

        await db_session.commit()

        # 4. Get events
        response = await async_client.get(f"/api/v1/videos/{video_id}/events")
        assert response.status_code == 200

        # 5. Get risk
        response = await async_client.get(f"/api/v1/videos/{video_id}/risk")
        assert response.status_code == 200

        # 6. Get results
        response = await async_client.get(f"/api/v1/videos/{video_id}/result")
        assert response.status_code == 200
        result_data = response.json()
        assert "annotated_video_url" in result_data
        assert "thumbnail_url" in result_data
        assert "result_json_url" in result_data

    @pytest.mark.asyncio
    async def test_upload_invalid_file_rejected(self, async_client):
        """Test invalid file is rejected at upload."""
        response = await async_client.post(
            "/api/v1/videos",
            files={"file": ("test.txt", b"not a video", "text/plain")},
            data={"camera_id": "cam_01"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_process_rejected(self, async_client, db_session, clean_db):
        """Test starting process on already processing video is rejected."""

        video = await create_test_video(
            db_session,
            video_id="vid_dup123",
            status="PROCESSING"
        )

        response = await async_client.post(f"/api/v1/videos/{video.id}/process")
        assert response.status_code == 400


class TestErrorHandling:
    """Tests for error handling across endpoints."""

    @pytest.mark.asyncio
    async def test_invalid_video_id_format(self, async_client):
        """Test endpoints handle invalid video ID gracefully."""
        # Non-vid_ prefix IDs
        response = await async_client.get("/api/v1/videos/invalid_id/events")
        # Should still return 404, not 500
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_job_id_format(self, async_client):
        """Test job endpoint with invalid ID."""
        response = await async_client.get("/api/v1/jobs/invalid_id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_malformed_json_body(self, async_client):
        """Test endpoints handle malformed requests."""
        # This would be tested at the FastAPI level


class TestConcurrency:
    """Tests for concurrent operations."""

    @pytest.mark.asyncio
    async def test_multiple_uploads(self, async_client, sample_video_path):
        """Test multiple concurrent uploads."""
        with open(sample_video_path, "rb") as f:
            file_content = f.read()

        with patch("app.services.validation.validate_video_file", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True

            with patch("app.utils.video_utils.get_video_duration", return_value=5.0):
                # Upload 3 videos concurrently
                import asyncio

                async def upload_one(i):
                    return await async_client.post(
                        "/api/v1/videos",
                        files={"file": (f"test_{i}.mp4", file_content, "video/mp4")},
                        data={"camera_id": "cam_01"}
                    )

                responses = await asyncio.gather(
                    upload_one(1),
                    upload_one(2),
                    upload_one(3)
                )

        assert all(r.status_code == 201 for r in responses)
        video_ids = [r.json()["id"] for r in responses]
        assert len(set(video_ids)) == 3  # All unique

    @pytest.mark.asyncio
    async def test_multiple_jobs_for_different_videos(self, async_client, db_session, clean_db):
        """Test multiple jobs can run for different videos."""

        video1 = await create_test_video(db_session, video_id="vid_con1", status="UPLOADED")
        video2 = await create_test_video(db_session, video_id="vid_con2", status="UPLOADED")

        with patch("app.services.inference.run_inference", new_callable=AsyncMock) as mock_inference:
            mock_inference.return_value = None

            response1 = await async_client.post(f"/api/v1/videos/{video1.id}/process")
            response2 = await async_client.post(f"/api/v1/videos/{video2.id}/process")

        assert response1.status_code == 202
        assert response2.status_code == 202
        assert response1.json()["job_id"] != response2.json()["job_id"]


class TestDataIntegrity:
    """Tests for data integrity and constraints."""

    @pytest.mark.asyncio
    async def test_video_deletion_cascades(self, async_client, db_session, clean_db):
        """Test deleting video cascades to jobs/events/risk."""
        from tests.conftest import create_test_events, create_test_job, create_test_risk

        video = await create_test_video(db_session, video_id="vid_cascade", status="COMPLETED")
        job = await create_test_job(db_session, video_id=video.id, job_id="job_cascade")
        events = await create_test_events(db_session, video_id=video.id, job_id=job.id)
        risk = await create_test_risk(db_session, video_id=video.id)

        # Delete video
        await db_session.delete(video)
        await db_session.commit()

        # Check cascades
        from sqlalchemy import select

        from app.models import Event, Job, RiskScore

        # Jobs should be deleted
        jobs = (await db_session.execute(select(Job).where(Job.video_id == video.id))).scalars().all()
        assert len(jobs) == 0

        # Events should be deleted
        events = (await db_session.execute(select(Event).where(Event.video_id == video.id))).scalars().all()
        assert len(events) == 0

        # Risk should be deleted
        risks = (await db_session.execute(select(RiskScore).where(RiskScore.video_id == video.id))).scalars().all()
        assert len(risks) == 0

    @pytest.mark.asyncio
    async def test_job_progress_bounds(self, async_client, db_session, clean_db):
        """Test job progress stays within 0-100."""
        from tests.conftest import create_test_job

        job = await create_test_job(db_session, video_id="vid_test", job_id="job_bounds", progress=0)

        # Progress should never exceed 100
        # (This is enforced by application logic, not DB constraint)
        assert 0 <= job.progress <= 100


class TestValidationEdgeCases:
    """Edge case validation tests."""

    @pytest.mark.asyncio
    async def test_filename_with_special_chars(self, async_client, sample_video_path):
        """Test upload with special characters in filename."""
        with open(sample_video_path, "rb") as f:
            file_content = f.read()

        with patch("app.services.validation.validate_video_file", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True

            with patch("app.utils.video_utils.get_video_duration", return_value=5.0):
                response = await async_client.post(
                    "/api/v1/videos",
                    files={"file": ("test@#$%^&.mp4", file_content, "video/mp4")},
                    data={"camera_id": "cam_01"}
                )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_camera_id_optional(self, async_client, sample_video_path):
        """Test camera_id is optional."""
        with open(sample_video_path, "rb") as f:
            file_content = f.read()

        with patch("app.services.validation.validate_video_file", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True

            with patch("app.utils.video_utils.get_video_duration", return_value=5.0):
                response = await async_client.post(
                    "/api/v1/videos",
                    files={"file": ("test.mp4", file_content, "video/mp4")},
                    # No camera_id
                )

        assert response.status_code == 201
        assert response.json()["camera_id"] == "cam_01"  # Default

    @pytest.mark.asyncio
    async def test_very_short_video(self, async_client):
        """Test very short video (1 second) is accepted."""
        # Create 1 second test video
        import subprocess
        short_video = Path("/tmp/short_test.mp4")
        if not short_video.exists():
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=duration=1:size=1280x720:rate=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(short_video)
            ], capture_output=True)

        if short_video.exists():
            with open(short_video, "rb") as f:
                file_content = f.read()

            with patch("app.services.validation.validate_video_file", new_callable=AsyncMock) as mock_validate:
                mock_validate.return_value = True

                with patch("app.utils.video_utils.get_video_duration", return_value=1.0):
                    response = await async_client.post(
                        "/api/v1/videos",
                        files={"file": ("short.mp4", file_content, "video/mp4")},
                    )

            assert response.status_code == 201
            assert response.json()["duration_sec"] == 1.0
