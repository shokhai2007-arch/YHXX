# CyberLeek Traffic Detection API — Endpoints Documentation

**Base URL:** `http://localhost:8000/api/v1`  
**Content-Type:** `application/json` (except video upload: `multipart/form-data`)

---

## 1. Health Check

### GET `/health`

**Response 200:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## 2. Video Management

### POST `/videos` — Upload Video

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | ✅ | Video file (MP4) |
| `camera_id` | string | ❌ | Camera identifier (default: `"cam_01"`) |

**Validations (server-side):**
- MIME type: `video/mp4`
- Size: ≤ 100 MB
- Duration: ≤ 120 seconds (via ffprobe)
- Codec: H.264 / H.265

**Response 201:**
```json
{
  "id": "vid_abc123",
  "filename": "traffic.mp4",
  "size_bytes": 52428800,
  "duration_sec": 85.3,
  "camera_id": "cam_01",
  "status": "UPLOADED",
  "created_at": "2026-09-23T10:30:00Z",
  "processed_at": null
}
```

**Response 400 (validation error):**
```json
{
  "detail": "Invalid MIME type: application/octet-stream. Allowed: ['video/mp4']"
}
```

---

### GET `/videos/{video_id}` — Get Video Info

**Response 200:**
```json
{
  "id": "vid_abc123",
  "filename": "traffic.mp4",
  "size_bytes": 52428800,
  "duration_sec": 85.3,
  "camera_id": "cam_01",
  "status": "COMPLETED",
  "created_at": "2026-09-23T10:30:00Z",
  "processed_at": "2026-09-23T10:31:15Z"
}
```

**Status values:** `UPLOADED`, `PROCESSING`, `COMPLETED`, `FAILED`

---

### POST `/videos/{video_id}/process` — Start Processing

**Response 202 (Accepted):**
```json
{
  "job_id": "job_xyz789",
  "video_id": "vid_abc123",
  "status": "PROCESSING",
  "progress": 0,
  "error": null,
  "started_at": "2026-09-23T10:30:05Z",
  "completed_at": null,
  "created_at": "2026-09-23T10:30:05Z"
}
```

**Note:** Inference runs in background via FastAPI `BackgroundTasks`. Poll `/jobs/{job_id}` for progress.

---

## 3. Job Management

### GET `/jobs/{job_id}` — Get Job Status (Polling)

**Polling interval:** 1 second recommended

**Response 200:**
```json
{
  "job_id": "job_xyz789",
  "video_id": "vid_abc123",
  "status": "PROCESSING",
  "progress": 45,
  "error": null,
  "started_at": "2026-09-23T10:30:05Z",
  "completed_at": null,
  "created_at": "2026-09-23T10:30:05Z"
}
```

**Status progression:** `PROCESSING` (0→100) → `COMPLETED` or `FAILED`

---

## 4. Events

### GET `/videos/{video_id}/events` — Get Detected Events

**Response 200:**
```json
{
  "video_id": "vid_abc123",
  "events": [
    {
      "id": 1,
      "video_id": "vid_abc123",
      "job_id": "job_xyz789",
      "start_sec": 12.3,
      "end_sec": 15.8,
      "label": "speeding",
      "track_id": 3,
      "confidence": 0.92,
      "event_metadata": {},
      "created_at": "2026-09-23T10:31:00Z"
    },
    {
      "id": 2,
      "video_id": "vid_abc123",
      "job_id": "job_xyz789",
      "start_sec": 28.1,
      "end_sec": 32.0,
      "label": "illegal_parking",
      "track_id": 7,
      "confidence": 0.87,
      "event_metadata": {},
      "created_at": "2026-09-23T10:31:00Z"
    }
  ],
  "total_count": 2
}
```

**Valid labels:**
- `speeding`
- `illegal_parking`
- `illegal_uturn`
- `wrong_way`
- `stop_line_crossing`

---

## 5. Risk Score

### GET `/videos/{video_id}/risk` — Get Risk Scores

**Response 200:**
```json
{
  "video_id": "vid_abc123",
  "overall_risk": 0.67,
  "by_category": {
    "speeding": 0.8,
    "illegal_parking": 0.5,
    "illegal_uturn": 0.0,
    "wrong_way": 0.0,
    "stop_line_crossing": 0.3
  },
  "high_risk_tracks": [3, 7],
  "created_at": "2026-09-23T10:31:10Z"
}
```

**Risk interpretation:**
- `0.0` — no risk
- `0.0 - 0.3` — low
- `0.3 - 0.7` — medium
- `0.7 - 1.0` — high

---

## 6. Results

### GET `/videos/{video_id}/result` — Get Output Files

**Response 200:**
```json
{
  "video_id": "vid_abc123",
  "annotated_video_url": "/api/v1/outputs/video_vid_abc123/annotated.mp4",
  "thumbnail_url": "/api/v1/outputs/video_vid_abc123/thumbnail.jpg",
  "result_json_url": "/api/v1/outputs/video_vid_abc123/result.json"
}
```

### Static Files (Direct Access)

| File | URL Pattern |
|------|-------------|
| Annotated video | `/api/v1/outputs/video_{video_id}/annotated.mp4` |
| Thumbnail | `/api/v1/outputs/video_{video_id}/thumbnail.jpg` |
| Result JSON | `/api/v1/outputs/video_{video_id}/result.json` |

---

### Result JSON Structure (`result.json`)
```json
{
  "video_id": "vid_abc123",
  "duration_sec": 85.3,
  "events": [
    {
      "start_sec": 12.3,
      "end_sec": 15.8,
      "label": "speeding",
      "track_id": 3,
      "confidence": 0.92
    }
  ],
  "risk": {
    "overall_risk": 0.67,
    "by_category": {
      "speeding": 0.8,
      "illegal_parking": 0.5,
      "illegal_uturn": 0.0,
      "wrong_way": 0.0,
      "stop_line_crossing": 0.3
    },
    "high_risk_tracks": [3, 7]
  },
  "processing_time_sec": 12.4,
  "engine_version": "1.0.0-mock"
}
```

---

## 7. Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `BAD_REQUEST` | Validation error (MIME, size, duration, codec) |
| 404 | `NOT_FOUND` | Video/Job/Event/Risk not found |
| 413 | `PAYLOAD_TOO_LARGE` | File exceeds 100 MB |
| 422 | `UNPROCESSABLE_ENTITY` | Invalid request body |
| 500 | `INTERNAL_SERVER_ERROR` | Processing failed (check job error) |

---

## 8. cURL Examples

### Upload & Process Flow
```bash
# 1. Upload video
curl -X POST "http://localhost:8000/api/v1/videos" \
  -F "file=@traffic.mp4;type=video/mp4" \
  -F "camera_id=cam_01"

# Response: {"id": "vid_abc123", ...}

# 2. Start processing
curl -X POST "http://localhost:8000/api/v1/videos/vid_abc123/process"

# Response: {"job_id": "job_xyz789", "status": "PROCESSING", "progress": 0, ...}

# 3. Poll job status (every 1s)
curl "http://localhost:8000/api/v1/jobs/job_xyz789"

# Response: {"job_id": "job_xyz789", "status": "COMPLETED", "progress": 100, ...}

# 4. Get events
curl "http://localhost:8000/api/v1/videos/vid_abc123/events"

# 5. Get risk
curl "http://localhost:8000/api/v1/videos/vid_abc123/risk"

# 6. Get output files
curl "http://localhost:8000/api/v1/videos/vid_abc123/result"

# 7. Download annotated video
curl -o annotated.mp4 "http://localhost:8000/api/v1/outputs/video_vid_abc123/annotated.mp4"
```

---

## 9. Judge Environment (Separate)

The judge environment runs **outside Docker** and uses only:
```bash
python run_submission.py video.mp4
# or
python solution.py video.mp4
```

**Output:** `predictions.json` with format:
```json
[[start_sec, end_sec, "label"], ...]
```

**No database, no web framework, no background jobs.**

---

## 10. Architecture Notes

- **Dual-system**: Judge (standalone) + Website (FastAPI + PostgreSQL + Redis)
- **Shared engine**: `engine/pipeline.py` used by both
- **Mock AI**: All detection is deterministic pseudo-random (no real ML models)
- **Background processing**: FastAPI `BackgroundTasks` (not Celery in Phase 2)
- **Static files**: Served from `data/outputs/` at `/api/v1/outputs/`