from unittest.mock import AsyncMock, patch

import pytest


class TestVideoUpload:
    """Tests for POST /api/v1/videos."""

    @pytest.mark.asyncio
    async def test_upload_video_success(self, async_client, sample_video_path):
        """Test successful video upload."""
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
        data = response.json()
        assert data["filename"] == "test.mp4"
        assert data["size_bytes"] == len(file_content)
        assert data["duration_sec"] == 5.0
        assert data["camera_id"] == "cam_01"
        assert data["status"] == "UPLOADED"
        assert "id" in data
        assert data["id"].startswith("vid_")

    @pytest.mark.asyncio
    async def test_upload_video_invalid_mime(self, async_client):
        """Test upload with invalid MIME type."""
        file_content = b"not a video"

        response = await async_client.post(
            "/api/v1/videos",
            files={"file": ("test.avi", file_content, "video/avi")},
            data={"camera_id": "cam_01"}
        )

        assert response.status_code == 400
        assert "Invalid MIME type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_video_too_large(self, async_client):
        """Test upload with file exceeding size limit."""
        # Create 150MB content (limit is 100MB)
        large_content = b"x" * (150 * 1024 * 1024)

        with patch("app.services.validation.validate_video_file", new_callable=AsyncMock) as mock_validate:
            from fastapi import HTTPException
            mock_validate.side_effect = HTTPException(
                status_code=413,
                detail="File size exceeds limit"
            )

            response = await async_client.post(
                "/api/v1/videos",
                files={"file": ("large.mp4", large_content, "video/mp4")},
                data={"camera_id": "cam_01"}
            )

        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_video_missing_file(self, async_client):
        """Test upload without file."""
        response = await async_client.post(
            "/api/v1/videos",
            data={"camera_id": "cam_01"}
        )

        assert response.status_code == 422  # Validation error


class TestVideoGet:
    """Tests for GET /api/v1/videos/{id}."""

    @pytest.mark.asyncio
    async def test_get_video_success(self, async_client, db_session, clean_db):
        """Test getting existing video."""
        from tests.conftest import create_test_video

        video = await create_test_video(db_session, video_id="vid_test123")

        response = await async_client.get("/api/v1/videos/vid_test123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "vid_test123"
        assert data["filename"] == "test.mp4"
        assert data["status"] == "UPLOADED"

    @pytest.mark.asyncio
    async def test_get_video_not_found(self, async_client):
        """Test getting non-existent video returns 404."""
        response = await async_client.get("/api/v1/videos/vid_nonexistent")

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]


class TestVideoProcess:
    """Tests for POST /api/v1/videos/{id}/process."""

    @pytest.mark.asyncio
    async def test_process_video_success(self, async_client, db_session, clean_db):
        """Test starting video processing."""
        from tests.conftest import create_test_video

        video = await create_test_video(db_session, video_id="vid_proc123", status="UPLOADED")

        response = await async_client.post("/api/v1/videos/vid_proc123/process")

        assert response.status_code == 202
        data = response.json()
        assert data["video_id"] == "vid_proc123"
        assert data["status"] == "PROCESSING"
        assert data["progress"] == 0
        assert "job_id" in data
        assert data["job_id"].startswith("job_")

    @pytest.mark.asyncio
    async def test_process_video_not_found(self, async_client):
        """Test processing non-existent video returns 404."""
        response = await async_client.post("/api/v1/videos/vid_nonexistent/process")

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_process_video_already_processing(self, async_client, db_session, clean_db):
        """Test processing video that's already being processed."""
        from tests.conftest import create_test_video

        video = await create_test_video(db_session, video_id="vid_proc456", status="PROCESSING")

        response = await async_client.post("/api/v1/videos/vid_proc456/process")

        assert response.status_code == 400
        assert "already processing" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_process_video_already_completed(self, async_client, db_session, clean_db):
        """Test processing video that's already completed."""
        from tests.conftest import create_test_video

        video = await create_test_video(db_session, video_id="vid_proc789", status="COMPLETED")

        response = await async_client.post("/api/v1/videos/vid_proc789/process")

        assert response.status_code == 400
        assert "already completed" in response.json()["detail"].lower()
