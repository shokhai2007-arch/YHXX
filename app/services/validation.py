import subprocess
import os
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.config import Settings


async def validate_video_file(file: UploadFile, settings: Settings):
    # Check MIME type
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MIME type: {file.content_type}. Allowed: {settings.ALLOWED_MIME_TYPES}"
        )

    # Check file size by reading content
    file.file.seek(0, 2)  # Seek to end
    size_bytes = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size {size_bytes} bytes exceeds limit of {max_size_bytes} bytes ({settings.MAX_UPLOAD_SIZE_MB} MB)"
        )

    # We'll do ffprobe validation after saving the file
    return True


def validate_video_post_upload(file_path: str, settings: Settings) -> float:
    """
    Validate video after upload using ffprobe.
    Returns duration in seconds.
    Raises HTTPException if validation fails.
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Video file not found")

    # Run ffprobe to check codec and duration
    try:
        # Get codec
        codec_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            file_path
        ]
        codec_result = subprocess.run(codec_cmd, capture_output=True, text=True, timeout=30)
        if codec_result.returncode != 0:
            raise HTTPException(status_code=400, detail="Failed to probe video: invalid format")

        codec = codec_result.stdout.strip().lower()
        allowed_codecs = ["h264", "hevc", "h265"]
        if codec not in allowed_codecs:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported codec: {codec}. Allowed: {allowed_codecs}"
            )

        # Get duration
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=30)
        if duration_result.returncode != 0:
            raise HTTPException(status_code=400, detail="Failed to get video duration")

        duration_sec = float(duration_result.stdout.strip())
        if duration_sec > settings.MAX_DURATION_SEC:
            raise HTTPException(
                status_code=400,
                detail=f"Video duration {duration_sec:.1f}s exceeds limit of {settings.MAX_DURATION_SEC}s"
            )

        return duration_sec

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=400, detail="Video validation timed out")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid duration value")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Video validation error: {str(e)}")