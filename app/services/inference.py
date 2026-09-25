import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import update

from app.config import settings
from app.database import async_session_maker
from app.models import Event, Job, RiskScore, Video
from app.utils.video_utils import create_annotated_video, create_thumbnail
from engine.pipeline import TrafficPipeline

VALID_LABELS = [
    "speeding",
    "illegal_parking",
    "illegal_uturn",
    "wrong_way",
    "stop_line_crossing",
]


async def update_job_progress(job_id: str, progress: int, status: str = None, error: str = None):
    """Update job progress in database."""
    async with async_session_maker() as db:
        stmt = update(Job).where(Job.id == job_id).values(progress=progress)
        if status:
            stmt = stmt.values(status=status)
        if error:
            stmt = stmt.values(error=error)
        if status == "COMPLETED":
            stmt = stmt.values(completed_at=datetime.utcnow())
        if status == "FAILED":
            stmt = stmt.values(completed_at=datetime.utcnow())
        await db.execute(stmt)
        await db.commit()


async def save_events(video_id: str, job_id: str, events: list):
    """Save events to database."""
    async with async_session_maker() as db:
        for event_data in events:
            event = Event(
                video_id=video_id,
                job_id=job_id,
                start_sec=event_data[0],
                end_sec=event_data[1],
                label=event_data[2],
                track_id=event_data[3] if len(event_data) > 3 else 1,
                confidence=event_data[4] if len(event_data) > 4 else 0.9,
                event_metadata={}
            )
            db.add(event)
        await db.commit()


async def calculate_and_save_risk(video_id: str, events: list):
    """Calculate risk scores and save to database."""
    # Mock risk calculation based on events
    risk_by_category = dict.fromkeys(VALID_LABELS, 0.0)
    track_ids = set()

    for event in events:
        label = event[2]
        track_id = event[3] if len(event) > 3 else 1
        if label in risk_by_category:
            risk_by_category[label] = min(risk_by_category[label] + 0.2, 1.0)
        track_ids.add(track_id)

    # Overall risk = max of category risks
    overall_risk = max(risk_by_category.values()) if risk_by_category else 0.0
    high_risk_tracks = list(track_ids)[:5]  # Top 5 tracks

    async with async_session_maker() as db:
        risk = RiskScore(
            video_id=video_id,
            overall_risk=overall_risk,
            by_category=risk_by_category,
            high_risk_tracks=high_risk_tracks,
        )
        db.add(risk)
        await db.commit()


async def write_result_json(video_id: str, events: list, risk_data: dict, processing_time: float):
    """Write result.json to output directory."""
    output_dir = Path(settings.OUTPUT_DIR) / f"video_{video_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "video_id": video_id,
        "duration_sec": 0,  # Will be filled by caller
        "events": [
            {
                "start_sec": e[0],
                "end_sec": e[1],
                "label": e[2],
                "track_id": e[3] if len(e) > 3 else 1,
                "confidence": e[4] if len(e) > 4 else 0.9,
            }
            for e in events
        ],
        "risk": risk_data,
        "processing_time_sec": processing_time,
        "engine_version": "1.0.0-mock"
    }

    result_path = output_dir / "result.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)


async def run_inference(job_id: str, video_id: str, video_path: str):
    """
    Background task to run inference on video.
    Updates job progress and saves results.
    """
    start_time = datetime.utcnow()

    try:
        # Progress: 10% - Starting
        await update_job_progress(job_id, 10, "PROCESSING")

        # Initialize pipeline
        pipeline = TrafficPipeline(config_path=settings.CAMERA_CONFIG_PATH)

        # Progress: 30% - Processing video
        await update_job_progress(job_id, 30)

        # Run pipeline (mock)
        events = pipeline.process_video(video_path)

        # Enrich events with track_id and confidence for Phase 2
        enriched_events = []
        for i, event in enumerate(events):
            enriched_events.append([
                event[0],  # start_sec
                event[1],  # end_sec
                event[2],  # label
                i + 1,     # track_id
                0.9        # confidence
            ])

        # Progress: 50% - Saving events
        await update_job_progress(job_id, 50)
        await save_events(video_id, job_id, enriched_events)

        # Progress: 70% - Calculating risk
        await update_job_progress(job_id, 70)
        await calculate_and_save_risk(video_id, enriched_events)

        # Progress: 80% - Creating annotated video
        await update_job_progress(job_id, 80)
        output_dir = Path(settings.OUTPUT_DIR) / f"video_{video_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        annotated_path = output_dir / "annotated.mp4"
        create_annotated_video(video_path, enriched_events, str(annotated_path), settings.CAMERA_CONFIG_PATH)

        # Progress: 90% - Creating thumbnail
        await update_job_progress(job_id, 90)
        thumbnail_path = output_dir / "thumbnail.jpg"
        from app.utils.video_utils import get_video_duration
        duration = get_video_duration(video_path)
        thumbnail_timestamp = min(10.0, max(1.0, duration / 2))
        create_thumbnail(video_path, str(thumbnail_path), timestamp=thumbnail_timestamp)

        # Progress: 95% - Writing result.json
        await update_job_progress(job_id, 95)

        risk_data = {
            "overall_risk": max([0.8 if e[2] == "speeding" else 0.5 for e in enriched_events], default=0.0),
            "by_category": {
                "speeding": 0.8,
                "illegal_parking": 0.5,
                "illegal_uturn": 0.0,
                "wrong_way": 0.0,
                "stop_line_crossing": 0.3
            },
            "high_risk_tracks": list(set(e[3] for e in enriched_events))
        }

        processing_time = (datetime.utcnow() - start_time).total_seconds()
        await write_result_json(video_id, enriched_events, risk_data, processing_time)

        # Update video status
        async with async_session_maker() as db:
            await db.execute(
                update(Video)
                .where(Video.id == video_id)
                .values(status="COMPLETED", processed_at=datetime.utcnow())
            )
            await db.commit()

        # Progress: 100% - Done
        await update_job_progress(job_id, 100, "COMPLETED")

    except Exception as e:
        await update_job_progress(job_id, 0, "FAILED", str(e))
        async with async_session_maker() as db:
            await db.execute(
                update(Video)
                .where(Video.id == video_id)
                .values(status="FAILED")
            )
            await db.commit()
        raise
