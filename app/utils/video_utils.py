import subprocess
from pathlib import Path

import numpy as np


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return 60.0  # Default fallback
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        return 60.0


def create_thumbnail(video_path: str, output_path: str, timestamp: float = 10.0) -> bool:
    """Create thumbnail from video at given timestamp using ffmpeg."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    return result.returncode == 0


def create_annotated_video(
    video_path: str,
    events: list,
    output_path: str,
    config_path: str = "configs/camera.yaml"
) -> bool:
    """
    Create annotated video with bounding boxes for events.
    This is a mock implementation - draws simple overlays.
    """
    import cv2
    import yaml

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Load config for ROI
    roi = [[0, 0], [width, 0], [width, height], [0, height]]
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            if config and 'roi' in config:
                roi = config['roi']
    except Exception:
        pass

    # Video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = frame_idx / fps if fps > 0 else 0

        # Draw ROI
        if roi:
            pts = np.array(roi, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)

        # Draw events active at this time
        for event in events:
            start, end, label = event[0], event[1], event[2]
            if start <= current_time <= end:
                # Draw a mock bounding box (center of frame)
                cx, cy = width // 2, height // 2
                w, h = 200, 150
                cv2.rectangle(frame, (cx - w//2, cy - h//2), (cx + w//2, cy + h//2), (0, 0, 255), 2)
                cv2.putText(frame, label, (cx - w//2, cy - h//2 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.putText(frame, f"{start:.1f}s - {end:.1f}s", (cx - w//2, cy + h//2 + 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Draw timestamp
        cv2.putText(frame, f"Time: {current_time:.1f}s", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()
    return True
