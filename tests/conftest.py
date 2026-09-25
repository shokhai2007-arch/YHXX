import shutil
import subprocess
from pathlib import Path

import pytest


def _have_ffmpeg() -> bool:
    """Check ffmpeg and ffprobe are both available on PATH."""
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _generate_sample_video(video_path: Path) -> bool:
    """Generate a small test video with ffmpeg lavfi. Returns True on success."""
    if not _have_ffmpeg():
        return False
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "testsrc=duration=5:size=1280x720:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


@pytest.fixture(scope="session")
def sample_video_path() -> str:
    """Generate a small test video using ffmpeg lavfi. Skip all video-dependent tests if unavailable."""
    video_path = Path("/tmp/test_video_sample.mp4")
    if not video_path.exists():
        if not _generate_sample_video(video_path):
            pytest.skip(
                "ffmpeg unavailable or failed to generate test video; skipping video-dependent tests"
            )
    return str(video_path)
