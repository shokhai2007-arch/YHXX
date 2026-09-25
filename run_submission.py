#!/usr/bin/env python3
"""
run_submission.py — Judge Environment Runner (WIUT Hackathon)

Reads video folder from command line, calls solution.detect_events() for each video,
streams frames through RiskEstimator, writes predictions.json with nested format:
{
  "team": "CyberLeek",
  "videos": {
    "test_001.mp4": {
      "events": [[start, end, label], ...],
      "risk": [[t_sec, score], ...]
    }
  }
}
"""

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

# Import solution module
sys.path.insert(0, str(Path(__file__).parent))
from solution import RiskEstimator, detect_events


class TimeoutError(Exception):
    """Custom timeout exception."""
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Processing timed out")


def get_video_duration(video_path: str) -> float:
    """Get video duration using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return 60.0  # Default fallback


def get_video_fps(video_path: str) -> float:
    """Get video FPS using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse fraction like "30000/1001"
            frac = result.stdout.strip()
            if '/' in frac:
                num, den = frac.split('/')
                return float(num) / float(den)
            return float(frac)
    except Exception:
        pass
    return 30.0


def get_video_info(video_path: str) -> dict:
    """Get video info: duration, fps, width, height, n_frames."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True, text=True, timeout=10
        )
        width, height, fps = 1280, 720, 30.0
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split()
            if len(parts) >= 3:
                width = int(parts[0])
                height = int(parts[1])
                frac = parts[2]
                if '/' in frac:
                    num, den = frac.split('/')
                    fps = float(num) / float(den)
                else:
                    fps = float(frac)
        duration = get_video_duration(video_path)
        n_frames = int(duration * fps)
        return {
            "duration": duration,
            "fps": fps,
            "width": width,
            "height": height,
            "n_frames": n_frames,
        }
    except Exception:
        return {
            "duration": 60.0,
            "fps": 30.0,
            "width": 1280,
            "height": 720,
            "n_frames": 1800,
        }


def stream_frames_for_risk(video_path: str, risk_estimator: RiskEstimator, meta: dict) -> list[list]:
    """
    Stream frames through RiskEstimator and collect risk scores.
    Returns list of [t_sec, score] pairs.
    """
    risk_scores = []

    try:
        # Use ffmpeg to decode frames and pipe to stdout
        # We'll sample every 2nd frame (15 fps effective) for speed
        fps = meta.get("fps", 30.0)
        width = meta.get("width", 1280)
        height = meta.get("height", 720)

        cmd = [
            "ffmpeg", "-v", "error",
            "-i", video_path,
            "-vf", f"fps={fps/2}",  # Sample at half fps
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-"
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        frame_size = width * height * 3  # BGR24
        frame_idx = 0

        while True:
            # Read one frame
            raw_frame = proc.stdout.read(frame_size)
            if len(raw_frame) != frame_size:
                break

            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
            t_sec = frame_idx * 2 / fps  # Since we sample every 2nd frame

            score = risk_estimator.step(frame, t_sec)
            risk_scores.append([round(t_sec, 3), round(score, 3)])

            frame_idx += 1

        proc.wait()

    except Exception as e:
        print(f"Warning: Risk estimation failed for {video_path}: {e}", file=sys.stderr)
        # Return zero risk as fallback
        duration = meta.get("duration", 60.0)
        fps = meta.get("fps", 30.0)
        for frame_idx in range(0, int(duration * fps), 2):
            t_sec = frame_idx / fps
            risk_scores.append([round(t_sec, 3), 0.0])

    return risk_scores


def process_video_with_timeout(video_path: str, time_budget_multiplier: float = 3.0) -> tuple[list, list]:
    """
    Process a single video with time budget enforcement.
    Returns (events, risk_scores).
    """
    # Get video metadata first
    meta = get_video_info(video_path)
    duration = meta["duration"]
    time_budget = duration * time_budget_multiplier

    # Set up timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(time_budget) + 5)  # Extra 5s buffer

    events = []
    risk_scores = []

    try:
        # Part A: Event detection
        events = detect_events(video_path)

        # Part B: Risk estimation
        risk_estimator = RiskEstimator()
        risk_estimator.reset({
            "video_id": Path(video_path).stem,
            "fps": meta["fps"],
            "width": meta["width"],
            "height": meta["height"],
            "n_frames": meta["n_frames"],
        })
        risk_scores = stream_frames_for_risk(video_path, risk_estimator, meta)

    except TimeoutError:
        print(f"Timeout: {video_path} exceeded {time_budget:.0f}s budget", file=sys.stderr)
        events = []
        risk_scores = []
    except Exception as e:
        print(f"Error processing {video_path}: {e}", file=sys.stderr)
        events = []
        risk_scores = []
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    return events, risk_scores


def main():
    parser = argparse.ArgumentParser(description="Run submission on video folder")
    parser.add_argument("--videos", required=True, help="Path to folder containing video files")
    parser.add_argument("-o", "--output", default="predictions.json", help="Output JSON file")
    parser.add_argument("--team", default="CyberLeek", help="Team name for submission")
    args = parser.parse_args()

    videos_path = Path(args.videos)
    if not videos_path.exists():
        print(f"Error: Videos folder not found: {videos_path}", file=sys.stderr)
        sys.exit(1)

    if not videos_path.is_dir():
        print(f"Error: --videos must be a directory: {videos_path}", file=sys.stderr)
        sys.exit(1)

    # Find all video files
    video_extensions = {".mp4", ".avi", ".mov", ".mkv"}
    video_files = sorted([
        f for f in videos_path.iterdir()
        if f.is_file() and f.suffix.lower() in video_extensions
    ])

    if not video_files:
        print(f"Error: No video files found in {videos_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(video_files)} video(s) to process", file=sys.stderr)

    # Process each video
    videos_output = {}
    for video_file in video_files:
        print(f"Processing: {video_file.name}", file=sys.stderr)
        start_time = time.time()

        events, risk_scores = process_video_with_timeout(str(video_file))

        elapsed = time.time() - start_time
        print(f"  Completed in {elapsed:.1f}s — Events: {len(events)}, Risk frames: {len(risk_scores)}", file=sys.stderr)

        videos_output[video_file.name] = {
            "events": events,
            "risk": risk_scores,
        }

    # Build final output
    output = {
        "team": args.team,
        "videos": videos_output,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"Predictions written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    # Need numpy for frame processing
    import numpy as np
    main()
