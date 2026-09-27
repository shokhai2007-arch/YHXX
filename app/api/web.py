"""Web UI sahifalari — Jinja2 (Django uslubidagi template sintaksisi).

Web pages router: renders Jinja2 templates (Django-style syntax: {{ }}, {% for %}).
API routerlardan alohida — faqat HTML sahifalarni serve qiladi.
"""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Event, Video

router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory="app/templates")

# (key, title, css-slug) — css slug: bg-event-<slug>
# 14 official event classes (engine/pipeline.py CLASSES — WIUT Hackathon spec)
EVENT_LABELS = [
    ("accident", "Accident", "accident"),
    ("near_miss", "Near Miss", "near-miss"),
    ("red_light", "Red Light", "red-light"),
    ("wrong_way", "Wrong Way", "wrong-way"),
    ("illegal_u_turn", "Illegal U-Turn", "illegal-u-turn"),
    ("stopped_vehicle", "Stopped Vehicle", "stopped-vehicle"),
    ("jaywalking", "Jaywalking", "jaywalking"),
    ("failure_to_yield", "Failure to Yield", "failure-to-yield"),
    ("illegal_turn", "Illegal Turn", "illegal-turn"),
    ("solid_line_crossing", "Solid Line Crossing", "solid-line-crossing"),
    ("stop_line", "Stop Line", "stop-line"),
    ("congestion", "Congestion", "congestion"),
    ("road_obstacle", "Road Obstacle", "road-obstacle"),
    ("fire_smoke", "Fire / Smoke", "fire-smoke"),
]

SAMPLES_STATIC_DIR = Path("app/static/samples")


def _load_samples_json() -> dict:
    """predictions_samples.json ni static dir dan o'qish / Load samples JSON."""
    path = SAMPLES_STATIC_DIR / "predictions_samples.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _label_title(key: str) -> str:
    return next((t for k, t, _ in EVENT_LABELS if k == key), key)


def _label_slug(key: str) -> str:
    return next((s for k, _, s in EVENT_LABELS if k == key), "wrong-way")


def _fmt_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def _build_demo_context() -> dict:
    """Demo sahifa konteksti / Demo page context."""
    data = _load_samples_json()
    samples = []
    for i in (1, 2, 3):
        sid = f"sample_{i}"
        v = data.get("videos", {}).get(sid, {})
        events = v.get("events", [])
        seen: list[str] = []
        for e in events:
            label = e[2] if isinstance(e, list) else e.get("label", "speeding")
            if label not in seen:
                seen.append(label)
        samples.append(
            {
                "id": sid,
                "duration_label": _fmt_duration(v.get("duration_sec", 0)),
                "event_count": len(events),
                "badge_labels": [
                    {"title": _label_title(k), "slug": _label_slug(k)} for k in seen[:3]
                ],
            }
        )
    steps = [
        {"title": "Upload", "icon": "cloud_upload"},
        {"title": "Decode", "icon": "decode"},
        {"title": "Detect", "icon": "search"},
        {"title": "Track", "icon": "timeline"},
        {"title": "Done", "icon": "task_alt"},
    ]
    return {"samples": samples, "steps": steps}


def _video_row(v: Video) -> dict:
    """Video qatori / Video row for list pages."""
    created = v.created_at
    created_label = (
        created.strftime("%Y-%m-%d %H:%M") if isinstance(created, datetime) else "—"
    )
    return {
        "id": v.id,
        "filename": v.filename,
        "camera_id": v.camera_id,
        "status": v.status,
        "size_mb": f"{v.size_bytes / (1024 * 1024):.1f}",
        "created_label": created_label,
    }


def _results_list_context(videos: list[Video]) -> dict:
    return {"videos": [_video_row(v) for v in videos]}


def _event_labels_context(data: dict, sample_id: str | None = None) -> list[dict]:
    """Timeline tracklari uchun label konteksti / Timeline track label context."""
    has_events = {k: False for k, _, _ in EVENT_LABELS}
    if sample_id:
        for e in data.get("videos", {}).get(sample_id, {}).get("events", []):
            key = e[2] if isinstance(e, list) else e.get("label")
            if key in has_events:
                has_events[key] = True
    return [
        {"key": k, "title": t, "slug": s, "has_events": has_events[k]}
        for k, t, s in EVENT_LABELS
    ]


async def _report_context(db: AsyncSession) -> dict:
    """Report sahifa konteksti / Report page context (videos + event counts)."""
    result = await db.execute(select(Video).order_by(Video.created_at.desc()))
    videos = result.scalars().all()
    counts_result = await db.execute(
        select(Event.video_id, func.count()).group_by(Event.video_id)
    )
    counts = dict(counts_result.all())
    rows = []
    for v in videos:
        row = _video_row(v)
        row["event_count"] = counts.get(v.id, 0)
        rows.append(row)
    return {
        "videos": rows,
        "selected_count": len(rows),
        "sections": [
            {
                "key": "summary",
                "title": "Umumiy ko'rinish",
                "desc": "Video metama'lumotlari va jami voqealar",
                "default": True,
            },
            {
                "key": "events",
                "title": "Voqealar ro'yxati",
                "desc": "Har bir qoidabuzarlik: vaqt, tur, ishonchlilik",
                "default": True,
            },
            {
                "key": "risk",
                "title": "Risk tahlili",
                "desc": "Umumiy risk va kategoriyalar bo'yicha taqsimot",
                "default": True,
            },
            {
                "key": "appendix",
                "title": "Ilova (Technical appendix)",
                "desc": "Konfiguratsiya, model versiyasi",
                "default": False,
            },
        ],
    }


# ==================
# Sahifalar / Pages
# ==================


@router.get("/")
async def landing(request: Request):
    features = [
        {"icon": "speed", "title": "Tezlik tahlili", "desc": "Har bir track uchun tezlikni kuzatish va speeding holatlarini aniqlash."},
        {"icon": "local_parking", "title": "Qoidabuzarlik klassifikatsiyasi", "desc": "5 xil violation class: speeding, parking, u-turn, wrong way, stop line."},
        {"icon": "crisis_alert", "title": "Risk baholash", "desc": "Umumiy va kategoriyalar bo'yicha xavf darajasi, high-risk tracklar."},
    ]
    labels = [
        {"title": t, "slug": s} for _, t, s in EVENT_LABELS
    ]
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"features": features, "labels": labels},
    )


@router.get("/demo")
async def demo_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="demo.html", context=_build_demo_context()
    )


@router.get("/results")
async def results_list_page(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).order_by(Video.created_at.desc()))
    videos = result.scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="results_list.html",
        context=_results_list_context(list(videos)),
    )


@router.get("/results/sample/{sample_id}")
async def sample_results_page(request: Request, sample_id: str):
    data = _load_samples_json()
    if sample_id not in data.get("videos", {}):
        raise HTTPException(status_code=404, detail="Sample topilmadi")
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "mode": "sample",
            "video_src": None,
            "title": f"{sample_id}.mp4",
            "ref_id": sample_id,
            "sample_id": sample_id,
            "camera_label": "Sample Demo Mode",
            "event_labels": _event_labels_context(data, sample_id),
        },
    )


@router.get("/results/{video_id}")
async def video_results_page(
    video_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "mode": "video",
            "video_src": f"/api/v1/videos/{video_id}/file",
            "title": video.filename,
            "ref_id": video.id,
            "sample_id": "",
            "camera_label": f"Kamera {video.camera_id}",
            "event_labels": _event_labels_context({}),
        },
    )


@router.get("/about")
async def about_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context={
            "tech_stack": [
                {"name": "FastAPI + Jinja2", "role": "Backend + server-rendered UI", "icon": "bolt"},
                {"name": "SQLAlchemy + Postgres", "role": "Async DB (4 jadval)", "icon": "storage"},
                {"name": "TrafficPipeline", "role": "Mock AI engine (engine/)", "icon": "precision_manufacturing"},
                {"name": "FFmpeg + OpenCV", "role": "Video decode/annotate", "icon": "movie"},
            ],
            "team": [
                {"name": "CyberLeek Member 1", "role": "CV / Detection", "bio": "Pipeline, detector va tracker modullari."},
                {"name": "CyberLeek Member 2", "role": "Backend / API", "bio": "FastAPI, DB sxemasi va background jobs."},
                {"name": "CyberLeek Member 3", "role": "Frontend / UI", "bio": "Stitch UI → Jinja2 templates, demo flow."},
            ],
        },
    )


@router.get("/report")
async def report_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = await _report_context(db)
    return templates.TemplateResponse(request=request, name="report.html", context=ctx)


async def not_found_page(request: Request, exc):
    """404 sahifa (web UI uchun) / Custom 404 page for web UI."""
    return templates.TemplateResponse(request=request, name="404.html", context={}, status_code=404)
