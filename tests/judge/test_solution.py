"""Judge environment tests: solution.py + run_submission.py CLI contract."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Repo ildizi (hardcoded absolute path emas — CI/local ikkalasida ham ishlaydi)
REPO_ROOT = str(Path(__file__).resolve().parents[2])


def _run_cli(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a repo CLI script with repo root on PYTHONPATH (host va konteynerda ham ishlaydi).

    Izoh: import qismi `engine.pipeline` sifatida yozilgan, shuning uchun repo ildizi
    PYTHONPATHda turishi kerak (cwd yetarli emas, chunki subprocess izolyatsiyasi).
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        **kwargs,
    )


class TestSolutionDetectEvents:
    """Tests for solution.py detect_events function."""

    def test_detect_events_returns_list(self, sample_video_path):
        """Test detect_events returns a list."""
        from solution import detect_events

        events = detect_events(sample_video_path)

        assert isinstance(events, list)

    def test_detect_events_structure(self, sample_video_path):
        """Test each event has [start_sec, end_sec, label] structure."""
        from solution import detect_events

        events = detect_events(sample_video_path)

        for event in events:
            assert isinstance(event, list)
            assert len(event) == 3
            assert isinstance(event[0], (int, float))  # start_sec
            assert isinstance(event[1], (int, float))  # end_sec
            assert isinstance(event[2], str)           # label
            assert event[0] < event[1]                 # start < end

    def test_detect_events_valid_labels(self, sample_video_path):
        """Test all labels are from valid set."""
        from engine.pipeline import VALID_LABELS
        from solution import detect_events

        events = detect_events(sample_video_path)

        for event in events:
            assert event[2] in VALID_LABELS

    def test_detect_events_deterministic(self, sample_video_path):
        """Test detect_events is deterministic for same input."""
        from solution import detect_events

        events1 = detect_events(sample_video_path)
        events2 = detect_events(sample_video_path)

        assert events1 == events2

    def test_detect_events_empty_for_nonexistent(self):
        """Test behavior with non-existent file."""
        from solution import detect_events

        with pytest.raises(FileNotFoundError):
            detect_events("/nonexistent/video.mp4")


class TestRunSubmission:
    """Tests for run_submission.py CLI (--videos folder-based contract)."""

    def test_run_submission_help(self):
        """Test --help shows usage."""
        result = _run_cli(["run_submission.py", "--help"])
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()

    def test_run_submission_output_file(self, tmp_path, sample_video_path):
        """Test --videos folder + -o flag writes to custom output file."""
        videos_dir = tmp_path / "videos"
        videos_dir.mkdir()
        shutil.copy(sample_video_path, videos_dir / "test_video.mp4")
        output_file = tmp_path / "custom_predictions.json"

        result = _run_cli(
            ["run_submission.py", "--videos", str(videos_dir), "-o", str(output_file)]
        )

        assert result.returncode == 0, result.stderr
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "team" in data
        assert "videos" in data

    def test_run_submission_no_args_exits(self):
        """Test exit with error when no args and no stdin."""
        result = _run_cli(["run_submission.py"])

        assert result.returncode != 0
        assert "required" in result.stderr.lower()

    def test_run_submission_invalid_folder(self):
        """Test with non-existent videos folder."""
        result = _run_cli(["run_submission.py", "--videos", "/nonexistent/folder"])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_run_submission_empty_folder(self, tmp_path):
        """Test empty videos folder exits with error."""
        videos_dir = tmp_path / "empty"
        videos_dir.mkdir()

        result = _run_cli(["run_submission.py", "--videos", str(videos_dir)])

        assert result.returncode != 0
        assert "no video files" in result.stderr.lower()

    def test_run_submission_output_format(self, tmp_path, sample_video_path):
        """Test output JSON matches judge schema."""
        videos_dir = tmp_path / "videos"
        videos_dir.mkdir()
        shutil.copy(sample_video_path, videos_dir / "test_video.mp4")
        output_file = tmp_path / "predictions.json"

        result = _run_cli(
            ["run_submission.py", "--videos", str(videos_dir), "-o", str(output_file)]
        )

        assert result.returncode == 0, result.stderr
        assert "Predictions written" in result.stderr

        data = json.loads(output_file.read_text())

        assert "team" in data
        assert "videos" in data
        for _vid, vdata in data["videos"].items():
            assert "events" in vdata
            assert "risk" in vdata
            for item in vdata["events"]:
                assert isinstance(item, list)
                assert len(item) == 3
                assert isinstance(item[0], (int, float))
                assert isinstance(item[1], (int, float))
                assert isinstance(item[2], str)
                assert item[0] < item[1]


class TestSolutionMain:
    """Tests for solution.py __main__ block."""

    def test_solution_main_help(self):
        """Test solution.py --help exits 0 with usage."""
        result = _run_cli(["solution.py", "--help"])
        assert result.returncode == 0
        assert "usage" in (result.stdout + result.stderr).lower()

    def test_solution_main_with_video(self, sample_video_path):
        """Test solution.py with video argument prints JSON."""
        result = _run_cli(["solution.py", sample_video_path])
        assert result.returncode == 0, result.stderr
        predictions = json.loads(result.stdout.strip())
        assert isinstance(predictions, list)

    def test_solution_main_no_args(self):
        """Test solution.py without args shows usage and exits non-zero."""
        result = _run_cli(["solution.py"])
        assert result.returncode != 0
        assert "usage" in (result.stdout + result.stderr).lower()


class TestJudgeOutputFormat:
    """Tests to ensure judge output format compliance."""

    def test_output_matches_judge_schema(self, sample_video_path):
        """Test output matches judge expectations exactly."""
        from solution import detect_events

        events = detect_events(sample_video_path)

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

    def test_output_labels_valid(self, sample_video_path):
        """Test all labels are from expected set."""
        from engine.pipeline import VALID_LABELS
        from solution import detect_events

        events = detect_events(sample_video_path)

        for event in events:
            assert event[2] in VALID_LABELS

    def test_deterministic_across_runs(self, sample_video_path):
        """Test multiple runs produce identical output."""
        from solution import detect_events

        events1 = detect_events(sample_video_path)
        events2 = detect_events(sample_video_path)
        events3 = detect_events(sample_video_path)

        assert events1 == events2 == events3
