import random

import numpy as np
import pytest

from engine.pipeline import VALID_LABELS, CameraConfig, MockTrack, TrafficPipeline


class TestCameraConfig:
    """Tests for CameraConfig dataclass."""

    def test_default_config(self):
        """Test default config when file missing."""
        config = CameraConfig(
            lanes=[],
            stop_lines=[],
            crosswalks=[],
            roi=[[0, 0], [1280, 0], [1280, 720], [0, 720]],
        )
        assert config.fps == 30.0
        assert config.width == 1280
        assert config.height == 720


class TestTrafficPipeline:
    """Tests for TrafficPipeline class."""

    @pytest.fixture
    def pipeline(self):
        return TrafficPipeline(config_path="configs/camera.yaml")

    def test_init_loads_config(self, pipeline):
        """Test pipeline loads camera config."""
        assert isinstance(pipeline.config, CameraConfig)
        assert len(pipeline.config.lanes) == 3
        assert len(pipeline.config.stop_lines) == 1

    def test_init_missing_config_uses_default(self, tmp_path):
        """Test missing config file falls back to default CameraConfig."""
        pipeline = TrafficPipeline(config_path=str(tmp_path / "missing.yaml"))
        assert pipeline.config.lanes == []
        assert pipeline.config.stop_lines == []
        assert pipeline.config.fps == 30.0

    def test_get_video_seed_deterministic(self, pipeline):
        """Test seed generation is deterministic for same path."""
        path = "/path/to/video.mp4"
        seed1 = pipeline._get_video_seed(path)
        seed2 = pipeline._get_video_seed(path)
        assert seed1 == seed2
        assert isinstance(seed1, int)

    def test_different_paths_different_seeds(self, pipeline):
        """Test different paths produce different seeds."""
        seed1 = pipeline._get_video_seed("/path/video1.mp4")
        seed2 = pipeline._get_video_seed("/path/video2.mp4")
        assert seed1 != seed2

    @pytest.mark.parametrize("filename,expected_duration", [
        ("sample_video.mp4", 45.0),
        ("test_input.mp4", 45.0),
        ("long_video.mp4", 120.0),
        ("random_name.mp4", 60.0),
    ])
    def test_get_video_duration_filename_fallback(self, pipeline, filename, expected_duration):
        """Test duration fallback based on filename when ffprobe fails (file missing)."""
        duration = pipeline._get_video_duration(f"/nonexistent/{filename}")
        assert duration == expected_duration

    def test_process_video_returns_list(self, pipeline, sample_video_path):
        """Test process_video returns list of events."""
        events = pipeline.process_video(sample_video_path)

        assert isinstance(events, list)
        for event in events:
            assert len(event) == 3
            assert event[2] in VALID_LABELS

    def test_process_video_deterministic_for_same_path(self, pipeline, sample_video_path):
        """Test process_video is deterministic for same video path."""
        events1 = pipeline.process_video(sample_video_path)
        events2 = pipeline.process_video(sample_video_path)

        assert events1 == events2

    def test_process_video_events_within_duration(self, pipeline, sample_video_path):
        """Test all event times are clamped to [0, duration]."""
        duration = pipeline._get_video_duration(sample_video_path)
        events = pipeline.process_video(sample_video_path)

        for start, end, _label in events:
            assert 0 <= start < end <= duration

    def test_process_video_missing_file_raises(self, pipeline):
        """Test FileNotFoundError for non-existent video."""
        with pytest.raises(FileNotFoundError):
            pipeline.process_video("/nonexistent/video.mp4")

    def test_valid_labels_constant(self):
        """Test VALID_LABELS contains expected labels (14 official WIUT spec classes)."""
        expected = [
            "accident", "near_miss", "red_light", "wrong_way", "illegal_u_turn",
            "stopped_vehicle", "jaywalking", "failure_to_yield", "illegal_turn",
            "solid_line_crossing", "stop_line", "congestion", "road_obstacle", "fire_smoke",
        ]
        assert expected == VALID_LABELS


def _make_track(track_id: int, positions: list, class_name: str = "vehicle") -> MockTrack:
    """Helper: build a MockTrack from [(frame_idx, x, y), ...]."""
    last_x, last_y = positions[-1][1], positions[-1][2]
    w, h = (30, 80) if class_name == "pedestrian" else (60, 120)
    return MockTrack(
        track_id=track_id,
        class_name=class_name,
        positions=[tuple(p) for p in positions],
        bbox=(last_x - w / 2, last_y - h / 2, last_x + w / 2, last_y + h / 2),
        start_frame=positions[0][0],
        end_frame=positions[-1][0],
        lane_idx=0,
    )


class TestDetectEventsFromTracks:
    """Rule-based geometry tests with synthetic tracks (configs/camera.yaml)."""

    @pytest.fixture
    def pipeline(self):
        return TrafficPipeline(config_path="configs/camera.yaml")

    def test_wrong_way_upward_vehicle(self, pipeline):
        """Vehicle moving upward (decreasing y) in a lane -> wrong_way event."""
        # Lane 0: x ~150-500, y 450..720. Move from y=700 to y=460 (upward).
        positions = [(f, 300.0, 700.0 - f * 2.0) for f in range(0, 120, 2)]
        events = pipeline._detect_events_from_tracks([_make_track(1, positions)], 30.0)

        wrong_way = [e for e in events if e[2] == "wrong_way"]
        assert len(wrong_way) >= 1
        start, end, _ = wrong_way[0]
        assert 0 <= start < end <= 30.0

    def test_forward_vehicle_no_wrong_way(self, pipeline):
        """Vehicle moving downward (increasing y) must NOT trigger wrong_way."""
        positions = [(f, 300.0, 460.0 + f * 2.0) for f in range(0, 120, 2)]
        events = pipeline._detect_events_from_tracks([_make_track(1, positions)], 30.0)

        assert all(e[2] != "wrong_way" for e in events)

    def test_pedestrian_never_wrong_way(self, pipeline):
        """Pedestrians are excluded from wrong_way rule."""
        positions = [(f, 300.0, 700.0 - f * 2.0) for f in range(0, 120, 2)]
        track = _make_track(1, positions, class_name="pedestrian")
        events = pipeline._detect_events_from_tracks([track], 30.0)

        assert all(e[2] != "wrong_way" for e in events)

    def test_events_clamped_to_duration(self, pipeline):
        """add_event clamps times to [0, duration]."""
        positions = [(f, 300.0, 700.0 - f * 2.0) for f in range(0, 120, 2)]
        events = pipeline._detect_events_from_tracks([_make_track(1, positions)], 2.0)

        for start, end, _ in events:
            assert 0 <= start < end <= 2.0

    def test_short_track_skipped(self, pipeline):
        """Tracks with < 3 positions produce no events."""
        track = _make_track(1, [(0, 300.0, 700.0), (2, 300.0, 690.0)])
        events = pipeline._detect_events_from_tracks([track], 30.0)

        assert events == []


class TestMergeEvents:
    """Tests for _merge_events (pure function)."""

    @pytest.fixture
    def pipeline(self):
        return TrafficPipeline(config_path="configs/camera.yaml")

    def test_merges_overlapping_same_label(self, pipeline):
        events = [[0.0, 5.0, "wrong_way"], [4.0, 9.0, "wrong_way"]]
        merged = pipeline._merge_events(events)

        assert len(merged) == 1
        assert merged[0][0] == 0.0
        assert merged[0][1] == 9.0
        assert merged[0][2] == "wrong_way"

    def test_keeps_different_labels_separate(self, pipeline):
        events = [[0.0, 5.0, "wrong_way"], [0.0, 5.0, "jaywalking"]]
        merged = pipeline._merge_events(events)

        assert len(merged) == 2
        assert {e[2] for e in merged} == {"wrong_way", "jaywalking"}

    def test_filters_invalid_intervals(self, pipeline):
        events = [[5.0, 5.0, "wrong_way"], [7.0, 3.0, "stop_line"], [1.0, 2.0, "congestion"]]
        merged = pipeline._merge_events(events)

        assert merged == [[1.0, 2.0, "congestion"]]

    def test_empty_input(self, pipeline):
        assert pipeline._merge_events([]) == []

    def test_detect_level_result_sorted_by_start(self, pipeline):
        """_merge_events groups by label; _detect_events_from_tracks sorts by start."""
        positions = [(f, 300.0, 700.0 - f * 2.0) for f in range(0, 120, 2)]
        events = pipeline._detect_events_from_tracks([_make_track(1, positions)], 30.0)

        starts = [e[0] for e in events]
        assert starts == sorted(starts)


class TestGenerateMockTracks:
    """Tests for _generate_mock_tracks (deterministic mock track generation)."""

    @pytest.fixture
    def pipeline(self):
        return TrafficPipeline(config_path="configs/camera.yaml")

    def test_tracks_generated_for_duration(self, pipeline):
        random.seed(42)
        np.random.seed(42)
        tracks = pipeline._generate_mock_tracks(60.0, seed=42)

        assert isinstance(tracks, list)
        assert 3 <= len(tracks) <= 8  # num_tracks range from pipeline
        for track in tracks:
            assert track.class_name in ("vehicle", "pedestrian")
            assert len(track.positions) >= 2

    def test_tracks_deterministic_for_same_seed(self, pipeline):
        tracks1 = pipeline._generate_mock_tracks(60.0, seed=999)
        tracks2 = pipeline._generate_mock_tracks(60.0, seed=999)

        assert [(t.track_id, t.positions) for t in tracks1] == [
            (t.track_id, t.positions) for t in tracks2
        ]
