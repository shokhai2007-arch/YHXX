import pytest
from pathlib import Path
import subprocess


@pytest.fixture(scope="session")
def sample_video_path() -> str:
    """Generate a small test video using ffmpeg lavfi."""
    video_path = "/tmp/test_video_sample.mp4"
    if not Path(video_path).exists():
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