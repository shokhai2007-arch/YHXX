#!/usr/bin/env python3
"""
Judge Entry Point — WIUT Hackathon 2026 CV Track

This file is the ONLY entry point for the judge environment.
It must implement:
1. CLASSES — list of 14 official event labels
2. detect_events(video_path) -> list[list] — Part A
3. RiskEstimator class with reset(meta) and step(frame, t_sec) -> float — Part B

No web framework, no database, no background jobs — just pure functions.
"""

import json
import sys
from pathlib import Path

# Add engine to path for import
sys.path.insert(0, str(Path(__file__).parent / "engine"))

from engine.pipeline import CLASSES, RiskEstimator, TrafficPipeline

__all__ = ["CLASSES", "RiskEstimator", "detect_events"]


def detect_events(video_path: str) -> list[list]:
    """
    Detect traffic events from video file (Part A).

    Args:
        video_path: Path to input video file (MP4)

    Returns:
        List of [start_sec, end_sec, label] where label is one of CLASSES (14 classes).

    Example:
        [[12.3, 18.9, "accident"], [28.1, 32.0, "wrong_way"]]
    """
    config_path = Path(__file__).parent / "configs" / "camera.yaml"
    pipeline = TrafficPipeline(config_path=str(config_path))
    events = pipeline.process_video(video_path)
    return events


if __name__ == "__main__":
    # Allow direct execution for testing: python solution.py video.mp4
    if len(sys.argv) < 2:
        print("Usage: python solution.py <video_path>")
        sys.exit(1)

    video_path = sys.argv[1]
    events = detect_events(video_path)
    print(json.dumps(events, indent=2))
