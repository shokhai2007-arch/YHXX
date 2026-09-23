import pytest
from fastapi import UploadFile, HTTPException
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

from app.services.validation import validate_video_file, validate_video_post_upload
from app.config import Settings


class TestValidateVideoFile:
    """Tests for validate_video_file function."""

    @pytest.fixture
    def test_settings(self):
        return Settings(
            MAX_UPLOAD_SIZE_MB=100,
            MAX_DURATION_SEC=120,
            ALLOWED_MIME_TYPES=["video/mp4"],
        )

    @pytest.fixture
    def mock_upload_file(self):
        def _create(content_type: str, size_bytes: int):
            file = MagicMock(spec=UploadFile)
            file.content_type = content_type
            file.file = BytesIO(b"x" * size_bytes)
            file.file.seek = MagicMock()
            file.file.tell = MagicMock(return_value=size_bytes)
            return file
        return _create

    @pytest.mark.asyncio
    async def test_valid_mp4_file(self, test_settings, mock_upload_file):
        """Test valid MP4 file passes validation."""
        file = mock_upload_file("video/mp4", 1024 * 1024)  # 1MB
        result = await validate_video_file(file, test_settings)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_mime_type(self, test_settings, mock_upload_file):
        """Test invalid MIME type raises 400."""
        file = mock_upload_file("video/avi", 1024 * 1024)
        with pytest.raises(HTTPException) as exc_info:
            await validate_video_file(file, test_settings)
        assert exc_info.value.status_code == 400
        assert "Invalid MIME type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_file_too_large(self, test_settings, mock_upload_file):
        """Test file exceeding size limit raises 413."""
        file = mock_upload_file("video/mp4", 200 * 1024 * 1024)  # 200MB
        with pytest.raises(HTTPException) as exc_info:
            await validate_video_file(file, test_settings)
        assert exc_info.value.status_code == 413
        assert "exceeds limit" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_exact_size_limit(self, test_settings, mock_upload_file):
        """Test file at exact size limit passes."""
        file = mock_upload_file("video/mp4", 100 * 1024 * 1024)  # 100MB
        result = await validate_video_file(file, test_settings)
        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_allowed_mime_types(self, mock_upload_file):
        """Test custom allowed MIME types."""
        settings = Settings(
            MAX_UPLOAD_SIZE_MB=100,
            MAX_DURATION_SEC=120,
            ALLOWED_MIME_TYPES=["video/mp4", "video/quicktime"],
        )
        file = mock_upload_file("video/quicktime", 1024)
        result = await validate_video_file(file, settings)
        assert result is True


class TestValidateVideoPostUpload:
    """Tests for validate_video_post_upload function."""

    @pytest.fixture
    def test_settings(self):
        return Settings(
            MAX_UPLOAD_SIZE_MB=100,
            MAX_DURATION_SEC=120,
            ALLOWED_MIME_TYPES=["video/mp4"],
        )

    def test_file_not_found(self, test_settings):
        """Test non-existent file raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_video_post_upload("/nonexistent/video.mp4", test_settings)
        assert exc_info.value.status_code == 400
        assert "not found" in exc_info.value.detail

    @pytest.mark.parametrize("codec", ["h264", "hevc", "h265"])
    def test_allowed_codecs(self, codec, test_settings, sample_video_path):
        """Test allowed codecs pass validation."""
        # This test would need a real video file with specific codec
        # Skipped for unit test - requires integration test
        pytest.skip(f"Requires real video file with {codec} codec")

    def test_disallowed_codec(self, test_settings, sample_video_path):
        """Test disallowed codec raises 400."""
        # Would need a video with disallowed codec
        pytest.skip("Requires real video file with disallowed codec")

    def test_duration_exceeds_limit(self, test_settings):
        """Test video exceeding duration limit raises 400."""
        # Would need a long video file
        pytest.skip("Requires real long video file")


# Mock ffprobe for unit tests
@patch("subprocess.run")
class TestValidateVideoPostUploadMocked:
    """Tests with mocked ffprobe."""

    @pytest.fixture
    def test_settings(self):
        return Settings(
            MAX_UPLOAD_SIZE_MB=100,
            MAX_DURATION_SEC=120,
            ALLOWED_MIME_TYPES=["video/mp4"],
        )

    def test_valid_h264_duration_ok(self, mock_run, test_settings, tmp_path):
        """Test valid h264 codec and duration within limit."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        # Mock ffprobe calls: first for codec, second for duration
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="h264\n"),  # codec
            MagicMock(returncode=0, stdout="60.0\n"),  # duration
        ]

        duration = validate_video_post_upload(str(video_file), test_settings)
        assert duration == 60.0

    def test_codec_not_allowed(self, mock_run, test_settings, tmp_path):
        """Test disallowed codec raises 400."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        mock_run.return_value = MagicMock(returncode=0, stdout="vp9\n")

        with pytest.raises(HTTPException) as exc_info:
            validate_video_post_upload(str(video_file), test_settings)
        assert exc_info.value.status_code == 400
        assert "Unsupported codec" in exc_info.value.detail

    def test_ffprobe_fails(self, mock_run, test_settings, tmp_path):
        """Test ffprobe failure raises 400."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        with pytest.raises(HTTPException) as exc_info:
            validate_video_post_upload(str(video_file), test_settings)
        assert exc_info.value.status_code == 400

    def test_duration_exceeds_limit(self, mock_run, test_settings, tmp_path):
        """Test duration > 120s raises 400."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="h264\n"),
            MagicMock(returncode=0, stdout="150.0\n"),
        ]

        with pytest.raises(HTTPException) as exc_info:
            validate_video_post_upload(str(video_file), test_settings)
        assert exc_info.value.status_code == 400
        assert "exceeds limit" in exc_info.value.detail

    def test_ffprobe_timeout(self, mock_run, test_settings, tmp_path):
        """Test ffprobe timeout raises 400."""
        import subprocess
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 30)

        with pytest.raises(HTTPException) as exc_info:
            validate_video_post_upload(str(video_file), test_settings)
        assert exc_info.value.status_code == 400
        assert "timed out" in exc_info.value.detail

    def test_invalid_duration_value(self, mock_run, test_settings, tmp_path):
        """Test invalid duration output raises 400."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="h264\n"),
            MagicMock(returncode=0, stdout="invalid\n"),
        ]

        with pytest.raises(HTTPException) as exc_info:
            validate_video_post_upload(str(video_file), test_settings)
        assert exc_info.value.status_code == 400
        assert "Invalid duration" in exc_info.value.detail