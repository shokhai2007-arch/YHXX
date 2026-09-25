#!/usr/bin/env python3
"""
engine/pipeline.py — Traffic Processing Pipeline (Rule-Based Mock Implementation)

This is the SHARED ENGINE used by both:
1. Judge environment (solution.py → detect_events)
2. Website backend (FastAPI background job)

Rule-based mock: generates deterministic mock tracks from video hash,
applies geometry rules from camera.yaml to produce events.
No real AI — deterministic pseudo-random for hackathon demo.
"""

import json
import random
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Any
from dataclasses import dataclass
import numpy as np


# 14 Official Event Classes (from WIUT Hackathon spec)
CLASSES = [
    "accident",
    "near_miss",
    "red_light",
    "wrong_way",
    "illegal_u_turn",
    "stopped_vehicle",
    "jaywalking",
    "failure_to_yield",
    "illegal_turn",
    "solid_line_crossing",
    "stop_line",
    "congestion",
    "road_obstacle",
    "fire_smoke",
]

# Alias for backward compatibility
VALID_LABELS = CLASSES


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


@dataclass
class MockTrack:
    """Mock track for rule-based event generation."""
    track_id: int
    class_name: str        # "vehicle" or "pedestrian"
    positions: list[tuple[float, float, float]]  # (frame_idx, x, y) centroid
    bbox: tuple[float, float, float, float]      # (x1, y1, x2, y2) at last frame
    start_frame: int
    end_frame: int
    lane_idx: int = -1     # Which lane polygon it's in (-1 = none)


class TrafficPipeline:
    """
    Main pipeline for traffic event detection.

    Rule-based mock implementation:
    - Generates deterministic mock tracks from video path hash
    - Applies geometry rules from camera.yaml to detect events
    - Returns [[start_sec, end_sec, label], ...]
    """

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self._video_seed = None

    def _load_config(self, config_path: str) -> CameraConfig:
        """Load camera configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            return CameraConfig(
                lanes=[],
                stop_lines=[],
                crosswalks=[],
                roi=[[0, 0], [1280, 0], [1280, 720], [0, 720]],
            )

        try:
            import yaml
            data = yaml.safe_load(path.read_text())
        except ImportError:
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
        hash_obj = hashlib.md5(video_path.encode())
        return int(hash_obj.hexdigest()[:8], 16)

    def _point_in_polygon(self, x: float, y: float, polygon: list[list[float]]) -> bool:
        """Check if point (x,y) is inside polygon using ray casting."""
        if not polygon:
            return False
        n = len(polygon)
        inside = False
        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
                inside = not inside
        return inside

    def _get_lane_for_point(self, x: float, y: float) -> int:
        """Return lane index (0,1,2) if point is in a lane polygon, else -1."""
        for idx, lane in enumerate(self.config.lanes):
            if self._point_in_polygon(x, y, lane):
                return idx
        return -1

    def _get_video_duration(self, video_path: str) -> float:
        """Get actual video duration using ffprobe."""
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
        # Fallback based on filename
        name = Path(video_path).stem.lower()
        if "sample" in name or "test" in name:
            return 45.0
        if "long" in name:
            return 120.0
        return 60.0

    def _generate_mock_tracks(self, duration: float, seed: int) -> list[MockTrack]:
        """Generate deterministic mock tracks for the video duration."""
        random.seed(seed)
        np.random.seed(seed % (2**32))

        fps = self.config.fps
        total_frames = int(duration * fps)
        sample_every = 2  # Process every 2nd frame (15 fps effective)
        sampled_frames = list(range(0, total_frames, sample_every))

        tracks = []
        num_tracks = random.randint(3, 8)

        for track_id in range(num_tracks):
            # Determine track type
            is_pedestrian = random.random() < 0.15
            class_name = "pedestrian" if is_pedestrian else "vehicle"

            # Start position: random lane at bottom or top
            lane_choices = list(range(len(self.config.lanes)))
            if not lane_choices:
                lane_choices = [0, 1, 2]

            start_lane = random.choice(lane_choices)
            lane_poly = self.config.lanes[start_lane] if start_lane < len(self.config.lanes) else self.config.lanes[0]

            # Get lane bounds
            xs = [p[0] for p in lane_poly]
            ys = [p[1] for p in lane_poly]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            # Direction: bottom-to-top (incoming) or top-to-bottom (wrong way)
            wrong_way = random.random() < 0.1  # 10% wrong way
            if wrong_way:
                start_y = y_min + random.uniform(0, 50)
                end_y = y_max - random.uniform(0, 50)
            else:
                start_y = y_max - random.uniform(0, 50)
                end_y = y_min + random.uniform(0, 50)

            start_x = random.uniform(x_min + 20, x_max - 20)
            end_x = start_x + random.uniform(-30, 30)  # Slight lateral movement

            # Generate positions over time
            start_frame = random.randint(0, max(0, len(sampled_frames) - 20))
            max_frames = min(len(sampled_frames) - start_frame, random.randint(15, 60))
            end_frame = start_frame + max_frames

            positions = []
            for i, frame_idx in enumerate(sampled_frames[start_frame:end_frame]):
                t = i / max(1, max_frames - 1)
                x = start_x + (end_x - start_x) * t
                # Add slight noise
                x += random.uniform(-2, 2)
                y = start_y + (end_y - start_y) * t
                positions.append((frame_idx * sample_every, x, y))

            # Bounding box (approximate)
            w, h = (60, 120) if not is_pedestrian else (30, 80)
            last_x, last_y = positions[-1][1], positions[-1][2]
            bbox = (last_x - w/2, last_y - h/2, last_x + w/2, last_y + h/2)

            track = MockTrack(
                track_id=track_id,
                class_name=class_name,
                positions=positions,
                bbox=bbox,
                start_frame=positions[0][0] if positions else 0,
                end_frame=positions[-1][0] if positions else 0,
                lane_idx=start_lane,
            )
            tracks.append(track)

        return tracks

    def _detect_events_from_tracks(self, tracks: list[MockTrack], duration: float) -> list[list]:
        """Apply geometry rules to tracks to detect events."""
        events = []
        fps = self.config.fps
        sample_every = 2

        def clamp_time(t: float) -> float:
            """Clamp time to [0, duration] and round to 1 decimal."""
            return round(max(0.0, min(duration, t)), 1)

        def add_event(start_sec: float, end_sec: float, label: str):
            """Add event with clamped times, only if valid."""
            s = clamp_time(start_sec)
            e = clamp_time(end_sec)
            if s < e:
                events.append([s, e, label])

        for track in tracks:
            if len(track.positions) < 3:
                continue

            lane_idx = track.lane_idx
            lane_poly = self.config.lanes[lane_idx] if 0 <= lane_idx < len(self.config.lanes) else None
            stop_line = self.config.stop_lines[0] if self.config.stop_lines else None
            crosswalk = self.config.crosswalks[0] if self.config.crosswalks else None

            # Compute speeds (px per frame)
            speeds = []
            for i in range(1, len(track.positions)):
                dx = track.positions[i][1] - track.positions[i-1][1]
                dy = track.positions[i][2] - track.positions[i-1][2]
                speeds.append((dx**2 + dy**2)**0.5)
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            max_speed = max(speeds) if speeds else 0

            # 1. WRONG_WAY: moving upward (decreasing y) in lane
            if lane_poly and not track.class_name == "pedestrian":
                y_start = track.positions[0][2]
                y_end = track.positions[-1][2]
                if y_end < y_start - 20:  # Significant upward movement
                    start_sec = track.positions[0][0] / fps
                    end_sec = track.positions[-1][0] / fps
                    add_event(start_sec, end_sec, "wrong_way")

            # 2. STOPPED_VEHICLE: centroid static for >10s (300 frames at 30fps = 150 sampled frames)
            if track.class_name == "vehicle" and len(track.positions) > 150:
                # Check if position variance is very low
                xs = [p[1] for p in track.positions]
                ys = [p[2] for p in track.positions]
                x_var = np.var(xs) if len(xs) > 1 else 0
                y_var = np.var(ys) if len(ys) > 1 else 0
                if x_var < 4 and y_var < 4:  # Very stationary
                    start_sec = track.positions[0][0] / fps
                    end_sec = track.positions[-1][0] / fps
                    if end_sec - start_sec >= 10:
                        add_event(start_sec, end_sec, "stopped_vehicle")

            # 3. SOLID_LINE_CROSSING: crossing lane boundaries (x=480 or x=800)
            lane_boundaries = [480, 800]  # Between lane 1-2 and 2-3
            for boundary_x in lane_boundaries:
                crossed = False
                cross_frame = None
                for i in range(1, len(track.positions)):
                    x1, x2 = track.positions[i-1][1], track.positions[i][1]
                    if (x1 < boundary_x and x2 > boundary_x) or (x1 > boundary_x and x2 < boundary_x):
                        crossed = True
                        cross_frame = track.positions[i][0]
                        break
                if crossed:
                    start_sec = max(0, cross_frame / fps - 1)
                    end_sec = min(duration, cross_frame / fps + 2)
                    add_event(start_sec, end_sec, "solid_line_crossing")

            # 4. STOP_LINE_CROSSING / RED_LIGHT / STOP_LINE: crossing stop line (y≈455)
            if stop_line:
                stop_y = stop_line[0][1]  # y-coordinate of stop line
                crossed = False
                cross_frame = None
                for i in range(1, len(track.positions)):
                    y1, y2 = track.positions[i-1][2], track.positions[i][2]
                    if (y1 > stop_y and y2 < stop_y) or (y1 < stop_y and y2 > stop_y):
                        crossed = True
                        cross_frame = track.positions[i][0]
                        break
                if crossed and track.class_name == "vehicle":
                    # Randomly assign: 40% red_light, 30% stop_line, 30% just crossing
                    r = random.random()
                    if r < 0.4:
                        label = "red_light"
                    elif r < 0.7:
                        label = "stop_line"
                    else:
                        label = "solid_line_crossing"  # Reuse for crossing
                    start_sec = max(0, cross_frame / fps - 1)
                    end_sec = min(duration, cross_frame / fps + 3)
                    add_event(start_sec, end_sec, label)

            # 5. ILLEGAL_U_TURN: sharp direction reversal with high curvature
            if track.class_name == "vehicle" and len(track.positions) >= 10:
                # Check for U-shape: y goes down then up (or vice versa)
                ys = [p[2] for p in track.positions]
                if len(ys) > 10:
                    mid = len(ys) // 2
                    first_half = ys[:mid]
                    second_half = ys[mid:]
                    if (first_half[0] > first_half[-1] and second_half[0] < second_half[-1]) or \
                       (first_half[0] < first_half[-1] and second_half[0] > second_half[-1]):
                        start_sec = track.positions[0][0] / fps
                        end_sec = track.positions[-1][0] / fps
                        add_event(start_sec, end_sec, "illegal_u_turn")

            # 6. CONGESTION: multiple vehicles with very low speed simultaneously
            # (Handled at video level after all tracks processed)

            # 7. ACCIDENT / NEAR_MISS: track overlap + sudden deceleration
            # Check pairwise with other tracks
            for other in tracks:
                if other.track_id <= track.track_id:
                    continue
                if track.class_name == "vehicle" and other.class_name == "vehicle":
                    # Check spatial overlap at same time
                    for i, (f1, x1, y1) in enumerate(track.positions):
                        for j, (f2, x2, y2) in enumerate(other.positions):
                            if abs(f1 - f2) < fps:  # Within 1 second
                                dist = ((x1 - x2)**2 + (y1 - y2)**2)**0.5
                                if dist < 80:  # Close proximity
                                    # Check speeds
                                    speed1 = speeds[i] if i < len(speeds) else 0
                                    other_speeds = []
                                    for k in range(1, len(other.positions)):
                                        dx = other.positions[k][1] - other.positions[k-1][1]
                                        dy = other.positions[k][2] - other.positions[k-1][2]
                                        other_speeds.append((dx**2 + dy**2)**0.5)
                                    speed2 = other_speeds[j] if j < len(other_speeds) else 0

                                    if speed1 < 5 and speed2 < 5 and dist < 50:
                                        # Accident: both stopped, very close
                                        start_sec = min(f1, f2) / fps
                                        end_sec = min(duration, start_sec + 5)
                                        add_event(start_sec, end_sec, "accident")
                                    elif (speed1 > 10 or speed2 > 10) and dist < 60:
                                        # Near miss: high speed, close pass
                                        start_sec = min(f1, f2) / fps
                                        end_sec = min(duration, start_sec + 3)
                                        add_event(start_sec, end_sec, "near_miss")

            # 8. JAYWALKING: pedestrian in lane polygon outside crosswalk
            if track.class_name == "pedestrian" and lane_poly:
                in_lane = False
                in_crosswalk = False
                for _, x, y in track.positions:
                    if self._point_in_polygon(x, y, lane_poly):
                        in_lane = True
                    if crosswalk and self._point_in_polygon(x, y, crosswalk):
                        in_crosswalk = True
                if in_lane and not in_crosswalk:
                    start_sec = track.positions[0][0] / fps
                    end_sec = track.positions[-1][0] / fps
                    add_event(start_sec, end_sec, "jaywalking")

            # 9. FAILURE_TO_YIELD: vehicle in crosswalk while pedestrian in crosswalk
            if track.class_name == "vehicle" and crosswalk:
                for other in tracks:
                    if other.class_name == "pedestrian":
                        # Check if both in crosswalk at same time
                        for f1, x1, y1 in track.positions:
                            for f2, x2, y2 in other.positions:
                                if abs(f1 - f2) < fps * 2:  # Within 2 seconds
                                    v_in = self._point_in_polygon(x1, y1, crosswalk)
                                    p_in = self._point_in_polygon(x2, y2, crosswalk)
                                    if v_in and p_in:
                                        start_sec = min(f1, f2) / fps
                                        end_sec = min(duration, start_sec + 4)
                                        add_event(start_sec, end_sec, "failure_to_yield")
                                        break

            # 10. ILLEGAL_TURN: vehicle exits lane at sharp angle
            if track.class_name == "vehicle" and lane_poly and len(track.positions) >= 5:
                # Check if track leaves lane polygon
                in_lane_count = sum(1 for _, x, y in track.positions if self._point_in_polygon(x, y, lane_poly))
                if in_lane_count < len(track.positions) * 0.5:  # Less than 50% in lane
                    start_sec = track.positions[0][0] / fps
                    end_sec = track.positions[-1][0] / fps
                    add_event(start_sec, end_sec, "illegal_turn")

            # 11. ROAD_OBSTACLE: static detection not matching vehicle/pedestrian
            # (Random low probability)
            if random.random() < 0.02:
                start_sec = random.uniform(0, max(0, duration - 5))
                end_sec = min(duration, start_sec + random.uniform(5, 15))
                add_event(start_sec, end_sec, "road_obstacle")

            # 12. FIRE_SMOKE: random very low probability
            if random.random() < 0.01:
                start_sec = random.uniform(0, max(0, duration - 10))
                end_sec = min(duration, start_sec + random.uniform(10, 30))
                add_event(start_sec, end_sec, "fire_smoke")

        # 13. CONGESTION: check globally for multiple slow vehicles
        vehicle_tracks = [t for t in tracks if t.class_name == "vehicle" and len(t.positions) > 20]
        if len(vehicle_tracks) >= 3:
            # Check if at least 3 vehicles are slow simultaneously
            slow_count = 0
            for track in vehicle_tracks:
                speeds = []
                for i in range(1, len(track.positions)):
                    dx = track.positions[i][1] - track.positions[i-1][1]
                    dy = track.positions[i][2] - track.positions[i-1][2]
                    speeds.append((dx**2 + dy**2)**0.5)
                avg_s = sum(speeds) / len(speeds) if speeds else 100
                if avg_s < 3:  # Very slow
                    slow_count += 1
            if slow_count >= 3:
                start_sec = 0
                end_sec = duration
                add_event(start_sec, end_sec, "congestion")

        # Merge overlapping events of same class
        events = self._merge_events(events)

        # Sort by start time
        events.sort(key=lambda x: x[0])

        return events

    def _merge_events(self, events: list[list]) -> list[list]:
        """Merge overlapping or adjacent events of the same class."""
        if not events:
            return []

        # Filter out invalid events (start >= end)
        valid_events = [ev for ev in events if ev[0] < ev[1]]
        if not valid_events:
            return []

        # Group by label
        by_label = {}
        for ev in valid_events:
            label = ev[2]
            if label not in by_label:
                by_label[label] = []
            by_label[label].append(ev)

        merged = []
        for label, evs in by_label.items():
            evs.sort(key=lambda x: x[0])
            current = evs[0]
            for ev in evs[1:]:
                if ev[0] <= current[1] + 1.0:  # Overlap or gap <= 1s
                    current[1] = max(current[1], ev[1])
                else:
                    merged.append(current)
                    current = ev
            merged.append(current)

        # Final validation: ensure start < end
        merged = [ev for ev in merged if ev[0] < ev[1]]

        return merged

    def process_video(self, video_path: str) -> list[list]:
        """
        Process video and return detected events.

        Args:
            video_path: Path to video file

        Returns:
            List of [start_sec, end_sec, label] events
        """
        # Deterministic seed from video path
        seed = self._get_video_seed(video_path)
        random.seed(seed)
        np.random.seed(seed % (2**32))

        # Get actual video duration
        duration = self._get_video_duration(video_path)

        # Generate mock tracks
        tracks = self._generate_mock_tracks(duration, seed)

        # Detect events from tracks using geometry rules
        events = self._detect_events_from_tracks(tracks, duration)

        return events


class RiskEstimator:
    """
    Part B: Accident anticipation (optional).
    Causal: step() sees frames in order and nothing else.

    TTC-based risk estimation from mock tracks.
    """

    def __init__(self):
        self.tracks = []
        self.fps = 30.0
        self.width = 1280
        self.height = 720
        self.current_frame = 0
        self._initialized = False

    def reset(self, meta: dict) -> None:
        """
        Initialize for new video.

        Args:
            meta: {"video_id", "fps", "width", "height", "n_frames"}
        """
        self.fps = meta.get("fps", 30.0)
        self.width = meta.get("width", 1280)
        self.height = meta.get("height", 720)
        self.current_frame = 0
        self._initialized = True

        # Generate mock tracks for this video (deterministic from video_id)
        video_id = meta.get("video_id", "unknown")
        seed = int(hashlib.md5(video_id.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        np.random.seed(seed % (2**32))

        n_frames = meta.get("n_frames", int(self.fps * 60))
        duration = n_frames / self.fps

        # Generate mock tracks (simplified version)
        self.tracks = []
        num_tracks = random.randint(3, 8)
        for track_id in range(num_tracks):
            is_pedestrian = random.random() < 0.15
            class_name = "pedestrian" if is_pedestrian else "vehicle"

            lane_choices = list(range(3))
            start_lane = random.choice(lane_choices)

            # Lane bounds (approximate)
            lane_x = [150, 480, 800][start_lane]
            lane_w = [350, 320, 300][start_lane]
            x_min, x_max = lane_x, lane_x + lane_w

            wrong_way = random.random() < 0.1
            if wrong_way:
                start_y, end_y = 200, 700
            else:
                start_y, end_y = 700, 200

            start_x = random.uniform(x_min + 20, x_max - 20)
            end_x = start_x + random.uniform(-30, 30)

            positions = []
            for frame_idx in range(n_frames):
                t = frame_idx / max(1, n_frames - 1)
                x = start_x + (end_x - start_x) * t + random.uniform(-1, 1)
                y = start_y + (end_y - start_y) * t
                positions.append((frame_idx, x, y))

            w, h = (60, 120) if not is_pedestrian else (30, 80)
            last_x, last_y = positions[-1][1], positions[-1][2]
            bbox = (last_x - w/2, last_y - h/2, last_x + w/2, last_y + h/2)

            self.tracks.append(MockTrack(
                track_id=track_id,
                class_name=class_name,
                positions=positions,
                bbox=bbox,
                start_frame=0,
                end_frame=n_frames - 1,
                lane_idx=start_lane,
            ))

    def step(self, frame: np.ndarray, t_sec: float) -> float:
        """
        Return P(accident starts within 5s) in [0, 1].

        TTC-based: for each vehicle pair, compute time-to-collision.
        Risk = max over pairs of max(0, 1 - TTC/5).
        """
        if not self._initialized:
            return 0.0

        self.current_frame = int(t_sec * self.fps)

        max_risk = 0.0
        horizon = 5.0  # 5 seconds

        # Compute TTC for each pair of vehicle tracks
        vehicle_tracks = [t for t in self.tracks if t.class_name == "vehicle"]

        for i, track1 in enumerate(vehicle_tracks):
            for track2 in vehicle_tracks[i+1:]:
                # Get positions at current frame
                pos1 = None
                pos2 = None
                for f, x, y in track1.positions:
                    if f == self.current_frame:
                        pos1 = (x, y)
                        break
                for f, x, y in track2.positions:
                    if f == self.current_frame:
                        pos2 = (x, y)
                        break

                if pos1 is None or pos2 is None:
                    continue

                # Distance between centroids
                dist = ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5

                # Estimate relative velocity from previous frame
                rel_vel = 10.0  # Default px/frame
                if self.current_frame > 0:
                    prev_pos1 = None
                    prev_pos2 = None
                    for f, x, y in track1.positions:
                        if f == self.current_frame - 1:
                            prev_pos1 = (x, y)
                            break
                    for f, x, y in track2.positions:
                        if f == self.current_frame - 1:
                            prev_pos2 = (x, y)
                            break
                    if prev_pos1 and prev_pos2:
                        prev_dist = ((prev_pos1[0] - prev_pos2[0])**2 + (prev_pos1[1] - prev_pos2[1])**2)**0.5
                        rel_vel = abs(prev_dist - dist)  # Simplified

                # Time to collision
                if rel_vel > 1.0:
                    ttc = dist / rel_vel / self.fps  # Convert to seconds
                    if ttc < horizon:
                        risk = max(0.0, 1.0 - ttc / horizon)
                        max_risk = max(max_risk, risk)

                # Also check for stopped vehicle ahead (rear-end risk)
                # If track1 is moving fast and track2 is slow/stopped ahead
                speed1 = 0
                speed2 = 0
                if self.current_frame > 0:
                    for f, x, y in track1.positions:
                        if f == self.current_frame:
                            pass
                    # Simplified: use distance and speed heuristic
                    if dist < 150 and track1.class_name == "vehicle" and track2.class_name == "vehicle":
                        # Risk increases as distance decreases
                        risk = max(0.0, 1.0 - dist / 150.0)
                        max_risk = max(max_risk, risk * 0.5)  # Lower weight

        return round(min(1.0, max_risk), 3)


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