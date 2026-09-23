import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.inference import (
    calculate_and_save_risk,
    save_events,
    update_job_progress,
    write_result_json,
)
from app.services.inference import VALID_LABELS
from app.models import Event, RiskScore


@pytest.fixture
def sample_events():
    """Sample enriched events for testing."""
    return [
        [10.0, 15.0, "speeding", 1, 0.9],
        [20.0, 25.0, "illegal_parking", 2, 0.85],
        [30.0, 35.0, "speeding", 1, 0.95],
        [40.0, 45.0, "illegal_uturn", 3, 0.8],
    ]


@pytest.fixture
def empty_events():
    return []


class TestRiskCalculation:
    """Tests for risk calculation logic."""

    @pytest.mark.asyncio
    async def test_calculate_risk_by_category(self, sample_events):
        """Test risk is calculated per category."""
        # Mock the database session
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await calculate_and_save_risk("vid_test", sample_events)
            
            # Verify RiskScore was added
            mock_session.add.assert_called_once()
            added_obj = mock_session.add.call_args[0][0]
            assert isinstance(added_obj, RiskScore)
            
            # Check risk values
            assert added_obj.video_id == "vid_test"
            assert added_obj.overall_risk == 0.4  # max of speeding (0.4), illegal_parking (0.2), illegal_uturn (0.2)
            assert added_obj.by_category["speeding"] == 0.4  # 2 events * 0.2 capped at 1.0
            assert added_obj.by_category["illegal_parking"] == 0.2
            assert added_obj.by_category["illegal_uturn"] == 0.2
            assert added_obj.by_category["wrong_way"] == 0.0
            assert added_obj.by_category["stop_line_crossing"] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_risk_empty_events(self, empty_events):
        """Test risk calculation with empty events."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await calculate_and_save_risk("vid_test", empty_events)
            
            added_obj = mock_session.add.call_args[0][0]
            assert added_obj.overall_risk == 0.0
            assert all(v == 0.0 for v in added_obj.by_category.values())
            assert added_obj.high_risk_tracks == []

    @pytest.mark.asyncio
    async def test_calculate_risk_caps_at_1(self, sample_events):
        """Test risk caps at 1.0 per category."""
        # Create many speeding events
        many_speeding = [[10.0 + i, 12.0 + i, "speeding", 1, 0.9] for i in range(10)]
        
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await calculate_and_save_risk("vid_test", many_speeding)
            
            added_obj = mock_session.add.call_args[0][0]
            assert added_obj.by_category["speeding"] == 1.0  # Capped at 1.0
            assert added_obj.overall_risk == 1.0

    @pytest.mark.asyncio
    async def test_high_risk_tracks_unique(self, sample_events):
        """Test high_risk_tracks contains unique track IDs."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await calculate_and_save_risk("vid_test", sample_events)
            
            added_obj = mock_session.add.call_args[0][0]
            tracks = added_obj.high_risk_tracks
            assert len(tracks) == len(set(tracks))  # All unique
            assert set(tracks) == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_high_risk_tracks_limited_to_5(self):
        """Test high_risk_tracks limited to 5 tracks."""
        # Create events with 7 different track IDs
        many_tracks = [[10.0 + i, 12.0 + i, "speeding", i + 1, 0.9] for i in range(7)]
        
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await calculate_and_save_risk("vid_test", many_tracks)
            
            added_obj = mock_session.add.call_args[0][0]
            assert len(added_obj.high_risk_tracks) == 5

    def test_valid_labels_constant(self):
        """Test VALID_LABELS matches expected."""
        expected = [
            "speeding",
            "illegal_parking",
            "illegal_uturn",
            "wrong_way",
            "stop_line_crossing",
        ]
        assert VALID_LABELS == expected


class TestSaveEvents:
    """Tests for save_events function."""

    @pytest.mark.asyncio
    async def test_save_events_creates_records(self, sample_events):
        """Test events are saved to database."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await save_events("vid_test", "job_test", sample_events)
            
            # Should add 4 events
            assert mock_session.add.call_count == 4
            
            # Check first event
            first_event = mock_session.add.call_args_list[0][0][0]
            assert isinstance(first_event, Event)
            assert first_event.video_id == "vid_test"
            assert first_event.job_id == "job_test"
            assert first_event.start_sec == 10.0
            assert first_event.end_sec == 15.0
            assert first_event.label == "speeding"
            assert first_event.track_id == 1
            assert first_event.confidence == 0.9

    @pytest.mark.asyncio
    async def test_save_events_default_track_id_confidence(self):
        """Test default track_id and confidence when not provided."""
        events_minimal = [
            [10.0, 15.0, "speeding"],  # Only 3 elements
        ]
        
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await save_events("vid_test", "job_test", events_minimal)
            
            event = mock_session.add.call_args[0][0]
            assert event.track_id == 1  # Default
            assert event.confidence == 0.9  # Default


class TestUpdateJobProgress:
    """Tests for update_job_progress function."""

    @pytest.mark.asyncio
    async def test_update_progress_only(self):
        """Test updating only progress."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await update_job_progress("job_test", 50)
            
            # Verify update was called with progress=50
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_status(self):
        """Test updating progress and status."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await update_job_progress("job_test", 100, status="COMPLETED")
            
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_error(self):
        """Test updating with error."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await update_job_progress("job_test", 0, status="FAILED", error="Test error")
            
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_completed_sets_completed_at(self):
        """Test COMPLETED status sets completed_at."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await update_job_progress("job_test", 100, status="COMPLETED")
            
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_failed_sets_completed_at(self):
        """Test FAILED status sets completed_at."""
        with patch("app.services.inference.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            await update_job_progress("job_test", 0, status="FAILED")
            
            mock_session.execute.assert_called_once()


class TestWriteResultJson:
    """Tests for write_result_json function."""

    @pytest.mark.asyncio
    async def test_write_result_json_creates_file(self, sample_events, tmp_path):
        """Test result.json is written to output directory."""
        risk_data = {
            "overall_risk": 0.5,
            "by_category": {"speeding": 0.5},
            "high_risk_tracks": [1],
        }
        
        with patch("app.services.inference.settings") as mock_settings:
            mock_settings.OUTPUT_DIR = str(tmp_path)
            
            await write_result_json("vid_test", sample_events, risk_data, 5.0)
            
            result_file = tmp_path / "video_vid_test" / "result.json"
            assert result_file.exists()
            
            import json
            with open(result_file) as f:
                data = json.load(f)
            
            assert data["video_id"] == "vid_test"
            assert len(data["events"]) == 4
            assert data["risk"] == risk_data
            assert data["processing_time_sec"] == 5.0
            assert data["engine_version"] == "1.0.0-mock"

    @pytest.mark.asyncio
    async def test_write_result_json_event_structure(self, sample_events, tmp_path):
        """Test event structure in result.json."""
        risk_data = {"overall_risk": 0.5, "by_category": {}, "high_risk_tracks": []}
        
        with patch("app.services.inference.settings") as mock_settings:
            mock_settings.OUTPUT_DIR = str(tmp_path)
            
            await write_result_json("vid_test", sample_events, risk_data, 5.0)
            
            result_file = tmp_path / "video_vid_test" / "result.json"
            import json
            with open(result_file) as f:
                data = json.load(f)
            
            event = data["events"][0]
            assert "start_sec" in event
            assert "end_sec" in event
            assert "label" in event
            assert "track_id" in event
            assert "confidence" in event