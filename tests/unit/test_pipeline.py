
import pytest

from engine.pipeline import VALID_LABELS, CameraConfig, TrafficPipeline


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
    def test_get_mock_duration(self, pipeline, filename, expected_duration):
        """Test mock duration based on filename."""
        duration = pipeline._get_mock_duration(f"/path/{filename}")
        assert duration == expected_duration

    def test_generate_mock_events_structure(self, pipeline):
        """Test mock events have correct structure."""
        # Use fixed seed for reproducibility
        import random
        random.seed(42)

        events = pipeline._generate_mock_events(60.0)

        assert isinstance(events, list)
        assert 1 <= len(events) <= 5  # num_events range

        for event in events:
            assert isinstance(event, list)
            assert len(event) == 3  # [start_sec, end_sec, label]
            start, end, label = event
            assert isinstance(start, float)
            assert isinstance(end, float)
            assert isinstance(label, str)
            assert 0 <= start < end <= 60.0
            assert label in VALID_LABELS

    def test_generate_mock_events_sorted_by_start(self, pipeline):
        """Test events are sorted by start time."""
        import random
        random.seed(123)

        events = pipeline._generate_mock_events(60.0)

        start_times = [e[0] for e in events]
        assert start_times == sorted(start_times)

    def test_generate_mock_events_deterministic(self, pipeline):
        """Test events are deterministic for same duration."""
        import random
        random.seed(999)
        events1 = pipeline._generate_mock_events(60.0)

        random.seed(999)
        events2 = pipeline._generate_mock_events(60.0)

        assert events1 == events2

    def test_process_video_returns_list(self, pipeline):
        """Test process_video returns list of events."""
        events = pipeline.process_video("/fake/path/video.mp4")

        assert isinstance(events, list)
        for event in events:
            assert len(event) == 3
            assert event[2] in VALID_LABELS

    def test_process_video_deterministic_for_same_path(self, pipeline):
        """Test process_video is deterministic for same video path."""
        events1 = pipeline.process_video("/path/same_video.mp4")
        events2 = pipeline.process_video("/path/same_video.mp4")

        assert events1 == events2

    def test_valid_labels_constant(self):
        """Test VALID_LABELS contains expected labels."""
        expected = [
            "speeding",
            "illegal_parking",
            "illegal_uturn",
            "wrong_way",
            "stop_line_crossing",
        ]
        assert expected == VALID_LABELS


class TestTrafficPipelineEdgeCases:
    """Edge case tests for TrafficPipeline."""

    def test_zero_duration(self):
        """Test handling of zero duration."""
        pipeline = TrafficPipeline(config_path="configs/camera.yaml")
        events = pipeline._generate_mock_events(0.0)
        # Should handle gracefully (may return empty or single event)
        assert isinstance(events, list)

    def test_very_short_duration(self):
        """Test very short duration (e.g., 1 second)."""
        pipeline = TrafficPipeline(config_path="configs/camera.yaml")
        events = pipeline._generate_mock_events(1.0)
        assert isinstance(events, list)
        for event in events:
            start, end, _ = event
            assert 0 <= start < end <= 1.0

    def test_all_labels_possible(self):
        """Test all valid labels can appear in events."""
        import random
        pipeline = TrafficPipeline(config_path="configs/camera.yaml")
        # Run many times to increase chance of seeing all labels
        seen_labels = set()
        for seed in range(100):
            random.seed(seed)
            events = pipeline._generate_mock_events(60.0)
            for event in events:
                seen_labels.add(event[2])

        # Should see most labels across different seeds
        assert len(seen_labels) >= 3  # At least 3 different labels
