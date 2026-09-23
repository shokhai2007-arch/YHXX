#!/usr/bin/env python3
"""
Judge Entry Point — WUIT Hackathon CyberLeek Traffic Detection

This file is the ONLY entry point for the judge environment.
It must implement detect_events(video_path) returning [[start_sec, end_sec, label], ...]
No web framework, no database, no background jobs — just pure function.
"""

import sys
import json
from pathlib import Path

# Add engine to path for import
sys.path.insert(0, str(Path(__file__).parent / "engine"))

from engine.pipeline import TrafficPipeline


def detect_events(video_path: str) -> list[list]:
    """
    Detect traffic events from video file.
    
    Args:
        video_path: Path to input video file (MP4)
        
    Returns:
        List of [start_sec, end_sec, label] where label is one of:
        - speeding
        - illegal_parking
        - illegal_uturn
        - wrong_way
        - stop_line_crossing
        
    Example:
        [[12.3, 15.8, "speeding"], [28.1, 32.0, "illegal_parking"]]
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