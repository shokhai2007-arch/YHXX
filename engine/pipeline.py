#!/usr/bin/env python3
"""
engine/pipeline.py — Traffic Processing Pipeline (Mock Implementation)

This is the SHARED ENGINE used by both:
1. Judge environment (solution.py → detect_events)
2. Website backend (FastAPI background job)

NO real AI — all mock/random responses for hackathon demo.
"""

import json
import random
import time
from pathlib import Path
from typing import Any
from dataclasses import dataclass


@dataclass
class CameraConfig:
    """Camera/scene configuration loaded from YAML."""
    lanes: list[list[list[float]]]          # Polygon points [[x,y], ...]
    stop_lines: list[list[list[float]]]     # Stop line polygons
    crosswalks: list[list[list[float]]]     # Crosswalk polygons
    roi: list[list[float]]                  # Region of interest polygon
    fps: float = 30.0
    width: int = 1280
    height: int = 720


class TrafficPipeline:
    """
    Main pipeline for traffic event detection.
    
    Mock implementation: returns deterministic pseudo-random events
    based on video filename hash for reproducibility.
    """
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self._seed = None
    
    def _load_config(self, config_path: str) -> CameraConfig:
        """Load camera configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            # Return default config if file missing
            return CameraConfig(
                lanes=[],
                stop_lines=[],
                crosswalks=[],
                roi=[[0, 0], [1280, 0], [1280, 720], [0, 720]],
            )
        
        # Try to load YAML, fallback to JSON, else default
        try:
            import yaml
            data = yaml.safe_load(path.read_text())
        except ImportError:
            # If PyYAML not installed, try JSON
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                data = {}
        
        return CameraConfig(
            lanes=data.get("lanes", []),
            stop_lines=data.get("stop_lines", []),
            crosswalks=data.get("crosswalks", []),
            roi=data.get("roi", [[0, 0], [1280, 0], [1280, 720], [0, 720]]),
            fps=data.get("fps", 30.0),
            width=data.get("width", 1280),
            height=data.get("height", 720),
        )
    
    def _get_video_seed(self, video_path: str) -> int:
        """Generate deterministic seed from video path for reproducible mock results."""
        import hashlib
        hash_obj = hashlib.md5(video_path.encode())
        return int(hash_obj.hexdigest()[:8], 16)
    
    def process_video(self, video_path: str) -> list[list]:
        """
        Process video and return detected events.
        
        Args:
            video_path: Path to video file
            
        Returns:
            List of [start_sec, end_sec, label] events
        """
        # Mock: simulate processing time
        time.sleep(0.1)
        
        # Deterministic seed from video path
        seed = self._get_video_seed(video_path)
        random.seed(seed)
        
        # Mock video duration (in real version, read from ffprobe)
        duration = self._get_mock_duration(video_path)
        
        # Generate mock events
        events = self._generate_mock_events(duration)
        
        return events
    
    def _get_mock_duration(self, video_path: str) -> float:
        """Get video duration (mock: based on filename)."""
        # In real implementation: use ffprobe
        # ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
        name = Path(video_path).stem.lower()
        if "sample" in name or "test" in name:
            return 45.0
        if "long" in name:
            return 120.0
        return 60.0  # default 1 minute
    
    def _generate_mock_events(self, duration: float) -> list[list]:
        """Generate deterministic mock events for given duration."""
        events = []
        num_events = random.randint(1, 5)
        
        labels = list(VALID_LABELS)
        
        for _ in range(num_events):
            start = round(random.uniform(0, max(0, duration - 5)), 1)
            end = round(random.uniform(start + 1, min(duration, start + 10)), 1)
            label = random.choice(labels)
            events.append([start, end, label])
        
        # Sort by start time
        events.sort(key=lambda x: x[0])
        return events


# Valid labels (shared with evaluate.py) — list for deterministic ordering
VALID_LABELS = [
    "speeding",
    "illegal_parking",
    "illegal_uturn",
    "wrong_way",
    "stop_line_crossing",
]


def main():
    """CLI for testing pipeline directly."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m engine.pipeline <video_path>")
        sys.exit(1)
    
    pipeline = TrafficPipeline("configs/camera.yaml")
    events = pipeline.process_video(sys.argv[1])
    print(json.dumps(events, indent=2))


if __name__ == "__main__":
    main()