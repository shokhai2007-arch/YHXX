import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from app.utils.video_utils import (
    get_video_duration,
    create_thumbnail,
    create_annotated_video,
)


class TestGetVideoDuration:
    """Tests for get_video_duration function."""

    @patch("subprocess.run")
    def test_valid_duration(self, mock_run):
        """Test valid duration returned."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="45.5\n"
        )
        
        duration = get_video_duration("/fake/video.mp4")
        assert duration == 45.5

    @patch("subprocess.run")
    def test_ffprobe_error_returns_default(self, mock_run):
        """Test ffprobe error returns default 60.0."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="error"
        )
        
        duration = get_video_duration("/fake/video.mp4")
        assert duration == 60.0

    @patch("subprocess.run")
    def test_invalid_output_returns_default(self, mock_run):
        """Test invalid ffprobe output returns default 60.0."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid\n"
        )
        
        duration = get_video_duration("/fake/video.mp4")
        assert duration == 60.0

    @patch("subprocess.run")
    def test_timeout_returns_default(self, mock_run):
        """Test subprocess timeout returns default 60.0."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 30)
        
        duration = get_video_duration("/fake/video.mp4")
        assert duration == 60.0


class TestCreateThumbnail:
    """Tests for create_thumbnail function."""

    @patch("subprocess.run")
    def test_create_thumbnail_success(self, mock_run, tmp_path):
        """Test thumbnail creation with valid timestamp."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "thumb.jpg")
        
        # Create dummy input file
        Path(video_path).write_bytes(b"fake video")
        
        mock_run.return_value = MagicMock(returncode=0)
        
        result = create_thumbnail(video_path, output_path, timestamp=10.0)
        
        assert result is True
        mock_run.assert_called_once()
        
        # Check ffmpeg command
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ffmpeg"
        assert "-ss" in call_args
        assert "10.0" in call_args
        assert "-frames:v" in call_args
        assert "1" in call_args

    @patch("subprocess.run")
    def test_create_thumbnail_ffmpeg_fails(self, mock_run, tmp_path):
        """Test thumbnail creation fails returns False."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "thumb.jpg")
        
        Path(video_path).write_bytes(b"fake video")
        
        mock_run.return_value = MagicMock(returncode=1)
        
        result = create_thumbnail(video_path, output_path)
        assert result is False

    @patch("subprocess.run")
    def test_create_thumbnail_creates_output_dir(self, mock_run, tmp_path):
        """Test output directory is created."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "subdir" / "thumb.jpg")
        
        Path(video_path).write_bytes(b"fake video")
        mock_run.return_value = MagicMock(returncode=0)
        
        result = create_thumbnail(video_path, output_path)
        
        assert result is True
        assert Path(output_path).parent.exists()


class TestCreateAnnotatedVideo:
    """Tests for create_annotated_video function."""

    @patch("cv2.VideoCapture")
    @patch("cv2.VideoWriter")
    @patch("cv2.VideoWriter_fourcc")
    def test_create_annotated_video_success(
        self, mock_fourcc, mock_writer_class, mock_cap_class, tmp_path
    ):
        """Test annotated video creation with events."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "annotated.mp4")
        
        # Mock VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            5: 30.0,   # CAP_PROP_FPS
            3: 1280,   # CAP_PROP_FRAME_WIDTH
            4: 720,    # CAP_PROP_FRAME_HEIGHT
            7: 150,    # CAP_PROP_FRAME_COUNT
        }.get(prop, 0)
        
        # Mock frames - return 3 frames then False
        frame = MagicMock()
        frame.shape = (720, 1280, 3)
        mock_cap.read.side_effect = [
            (True, frame), (True, frame), (True, frame), (False, None)
        ]
        mock_cap_class.return_value = mock_cap
        
        # Mock VideoWriter
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        mock_fourcc.return_value = 0x7634706d  # 'mp4v'
        
        # Mock yaml config
        with patch("yaml.safe_load", return_value={
            "roi": [[0, 200], [1280, 200], [1280, 720], [0, 720]]
        }):
            events = [
                [10.0, 15.0, "speeding"],
                [20.0, 25.0, "illegal_parking"],
            ]
            
            result = create_annotated_video(video_path, events, output_path)
            
            assert result is True
            mock_writer.write.assert_called()  # Frames written
            mock_writer.release.assert_called_once()
            mock_cap.release.assert_called_once()

    @patch("cv2.VideoCapture")
    def test_create_annotated_video_cannot_open(self, mock_cap_class, tmp_path):
        """Test returns False when video cannot be opened."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "annotated.mp4")
        
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap_class.return_value = mock_cap
        
        result = create_annotated_video(video_path, [], output_path)
        assert result is False

    @patch("cv2.VideoCapture")
    @patch("cv2.VideoWriter")
    @patch("cv2.VideoWriter_fourcc")
    def test_annotated_video_draws_roi(
        self, mock_fourcc, mock_writer_class, mock_cap_class, tmp_path
    ):
        """Test ROI is drawn on frames."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "annotated.mp4")
        
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            5: 30.0, 3: 1280, 4: 720, 7: 30
        }.get(prop, 0)
        
        frame = MagicMock()
        frame.shape = (720, 1280, 3)
        mock_cap.read.side_effect = [(True, frame), (False, None)]
        mock_cap_class.return_value = mock_cap
        
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        mock_fourcc.return_value = 0x7634706d
        
        with patch("yaml.safe_load", return_value={
            "roi": [[100, 100], [500, 100], [500, 500], [100, 500]]
        }):
            events = []
            result = create_annotated_video(video_path, events, output_path)
            
            assert result is True
            # Verify cv2.polylines was called on frame


class TestCreateAnnotatedVideoEdgeCases:
    """Edge case tests for annotated video."""

    @patch("cv2.VideoCapture")
    @patch("cv2.VideoWriter")
    @patch("cv2.VideoWriter_fourcc")
    def test_events_at_different_times(
        self, mock_fourcc, mock_writer_class, mock_cap_class, tmp_path
    ):
        """Test events at different timestamps are handled."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "annotated.mp4")
        
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 3: 1280, 4: 720, 7: 60}.get(prop, 0)
        
        frame = MagicMock()
        frame.shape = (720, 1280, 3)
        # 3 frames at different times: 0.033s, 0.066s, 0.1s
        mock_cap.read.side_effect = [
            (True, frame), (True, frame), (True, frame), (False, None)
        ]
        mock_cap_class.return_value = mock_cap
        
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        mock_fourcc.return_value = 0x7634706d
        
        events = [
            [0.0, 0.1, "speeding"],      # Active in first frames
            [5.0, 5.5, "illegal_parking"],  # Not in our 3 frames
        ]
        
        with patch("yaml.safe_load", return_value={"roi": [[0, 0], [1280, 0], [1280, 720], [0, 720]]}):
            result = create_annotated_video(video_path, events, output_path)
            assert result is True
            assert mock_writer.write.call_count == 3  # 3 frames written

    @patch("cv2.VideoCapture")
    @patch("cv2.VideoWriter")
    @patch("cv2.VideoWriter_fourcc")
    def test_no_config_file_uses_default_roi(
        self, mock_fourcc, mock_writer_class, mock_cap_class, tmp_path
    ):
        """Test default ROI when config file missing."""
        video_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "annotated.mp4")
        
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 3: 1280, 4: 720, 7: 30}.get(prop, 0)
        frame = MagicMock()
        frame.shape = (720, 1280, 3)
        mock_cap.read.side_effect = [(True, frame), (False, None)]
        mock_cap_class.return_value = mock_cap
        
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        mock_fourcc.return_value = 0x7634706d
        
        # No yaml.safe_load patch - will fail to load and use default
        with patch("builtins.open", side_effect=FileNotFoundError):
            events = []
            result = create_annotated_video(video_path, events, output_path)
            
            assert result is True