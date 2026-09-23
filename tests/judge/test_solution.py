import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.conftest import sample_video_path


class TestSolutionDetectEvents:
    """Tests for solution.py detect_events function."""

    @pytest.mark.asyncio
    async def test_detect_events_returns_list(self):
        """Test detect_events returns a list."""
        from solution import detect_events
        
        events = detect_events(str(sample_video_path))
        
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_detect_events_structure(self):
        """Test each event has [start_sec, end_sec, label] structure."""
        from solution import detect_events
        
        events = detect_events(str(sample_video_path))
        
        for event in events:
            assert isinstance(event, list)
            assert len(event) == 3
            assert isinstance(event[0], (int, float))  # start_sec
            assert isinstance(event[1], (int, float))  # end_sec
            assert isinstance(event[2], str)           # label
            assert event[0] < event[1]                 # start < end

    @pytest.mark.asyncio
    async def test_detect_events_valid_labels(self):
        """Test all labels are from valid set."""
        from solution import detect_events
        from engine.pipeline import VALID_LABELS
        
        events = detect_events(str(sample_video_path))
        
        for event in events:
            assert event[2] in VALID_LABELS

    @pytest.mark.asyncio
    async def test_detect_events_deterministic(self):
        """Test detect_events is deterministic for same input."""
        from solution import detect_events
        
        events1 = detect_events(str(sample_video_path))
        events2 = detect_events(str(sample_video_path))
        
        assert events1 == events2

    @pytest.mark.asyncio
    async def test_detect_events_empty_for_nonexistent(self):
        """Test behavior with non-existent file."""
        from solution import detect_events
        
        with pytest.raises(Exception):
            detect_events("/nonexistent/video.mp4")


class TestRunSubmission:
    """Tests for run_submission.py CLI."""

    def test_run_submission_help(self):
        """Test --help shows usage."""
        import subprocess
        result = subprocess.run(
            ["python", "run_submission.py", "--help"],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()

    def test_run_submission_output_file(self, tmp_path):
        """Test -o flag writes to custom output file."""
        import subprocess
        
        output_file = tmp_path / "custom_predictions.json"
        
        result = subprocess.run(
            ["python", "run_submission.py", str(sample_video_path), "-o", str(output_file)],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        
        assert result.returncode == 0
        assert output_file.exists()
        
        with open(output_file) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_run_submission_stdin(self, tmp_path):
        """Test reading video path from stdin."""
        import subprocess
        
        result = subprocess.run(
            ["python", "run_submission.py"],
            input=str(sample_video_path),
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        
        assert result.returncode == 0
        assert "Predictions written" in result.stderr

    def test_run_submission_no_args_exits(self):
        """Test exit with error when no args and no stdin."""
        import subprocess
        
        result = subprocess.run(
            ["python", "run_submission.py"],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        
        assert result.returncode != 0
        assert "required" in result.stderr.lower()

    def test_run_submission_invalid_file(self):
        """Test with non-existent file."""
        import subprocess
        
        result = subprocess.run(
            ["python", "run_submission.py", "/nonexistent/video.mp4"],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_run_submission_output_format(self):
        """Test output JSON format matches expected schema."""
        import subprocess
        
        result = subprocess.run(
            ["python", "run_submission.py", str(sample_video_path)],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        
        assert result.returncode == 0
        
        # Parse output (last line should be JSON)
        lines = result.stdout.strip().split('\n')
        predictions = json.loads(lines[-1])
        
        assert isinstance(predictions, list)
        for pred in predictions:
            assert isinstance(pred, list)
            assert len(pred) == 3
            assert isinstance(pred[0], (int, float))
            assert isinstance(pred[1], (int, float))
            assert isinstance(pred[2], str)
            assert pred[0] < pred[1]


class TestSolutionMain:
    """Tests for solution.py __main__ block."""

    def test_solution_main_help(self):
        """Test solution.py --help."""
        import subprocess
        result = subprocess.run(
            ["python", "solution.py", "--help"],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        assert result.returncode == 0

    def test_solution_main_with_video(self):
        """Test solution.py with video argument."""
        import subprocess
        result = subprocess.run(
            ["python", "solution.py", str(sample_video_path)],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        assert result.returncode == 0
        # Should print JSON
        predictions = json.loads(result.stdout.strip())
        assert isinstance(predictions, list)

    def test_solution_main_no_args(self):
        """Test solution.py without args shows usage."""
        import subprocess
        result = subprocess.run(
            ["python", "solution.py"],
            capture_output=True,
            text=True,
            cwd="/home/neo/Projects/YHXX"
        )
        assert result.returncode != 0
        assert "usage" in result.stderr.lower()


class TestJudgeOutputFormat:
    """Tests to ensure judge output format compliance."""

    @pytest.mark.asyncio
    async def test_output_matches_judge_schema(self, sample_video_path):
        """Test output matches judge expectations exactly."""
        from solution import detect_events
        
        events = detect_events(str(sample_video_path))
        
        # Judge expects: [[start_sec, end_sec, label], ...]
        # All values must be JSON serializable
        json_str = json.dumps(events)
        parsed = json.loads(json_str)
        
        assert parsed == events
        
        # Check types
        for event in events:
            assert isinstance(event[0], (int, float))
            assert isinstance(event[1], (int, float))
            assert isinstance(event[2], str)
            
            # Reasonable bounds
            assert 0 <= event[0] < event[1]
            assert event[1] <= 120  # Max duration from settings

    @pytest.mark.asyncio
    async def test_output_labels_valid(self, sample_video_path):
        """Test all labels are from expected set."""
        from solution import detect_events
        from engine.pipeline import VALID_LABELS
        
        events = detect_events(str(sample_video_path))
        
        for event in events:
            assert event[2] in VALID_LABELS

    @pytest.mark.asyncio
    async def test_deterministic_across_runs(self, sample_video_path):
        """Test multiple runs produce identical output."""
        from solution import detect_events
        
        events1 = detect_events(str(sample_video_path))
        events2 = detect_events(str(sample_video_path))
        events3 = detect_events(str(sample_video_path))
        
        assert events1 == events2 == events3