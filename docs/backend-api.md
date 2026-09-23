# Backend API / Backend API

## 🎯 Overview / Umumiy Ko'rinish
FastAPI asosida REST API. **Phase 2** da amalga oshiriladi. Judge environmentga tegmaydi.

---

## 📋 API Contract / API Kontrakti

### Base URL
```
/api/v1
```

### Endpoints

#### 1. Health Check
```http
GET /api/health
```
**Response 200:**
```json
{ "status": "ok", "version": "1.0.0" }
```

#### 2. Video Upload
```http
POST /api/videos
Content-Type: multipart/form-data
```
**Request:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | ✅ | Video fayli (MP4) |
| `camera_id` | string | ❌ | Kamera identifikatori (default: "cam_01") |

**Validatsiya (serverda):**
- MIME type: `video/mp4`
- Size: ≤ 100 MB
- Duration: ≤ 2 min (ffprobe orqali)
- Decode test: `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 input.mp4`

**Response 201:**
```json
{
  "id": "vid_abc123",
  "filename": "traffic.mp4",
  "size_bytes": 52428800,
  "duration_sec": 85.3,
  "status": "UPLOADED",
  "created_at": "2026-09-23T10:30:00Z"
}
```

**Response 400 (validatsiya xatosi):**
```json
{
  "detail": "Invalid video: duration 150s exceeds 120s limit"
}
```

#### 3. Video Info
```http
GET /api/videos/{video_id}
```
**Response 200:**
```json
{
  "id": "vid_abc123",
  "filename": "traffic.mp4",
  "size_bytes": 52428800,
  "duration_sec": 85.3,
  "status": "COMPLETED",
  "camera_id": "cam_01",
  "created_at": "2026-09-23T10:30:00Z",
  "processed_at": "2026-09-23T10:31:15Z"
}
```

#### 4. Start Processing
```http
POST /api/videos/{video_id}/process
```
**Response 202 (Accepted):**
```json
{
  "job_id": "job_xyz789",
  "status": "PROCESSING",
  "progress": 0
}
```
**Eslatma**: Inference **request ichida** emas, `BackgroundTasks` orqali fon rejimida amalga oshiriladi.

#### 5. Job Status (Polling — 1s)
```http
GET /api/jobs/{job_id}
```
**Response 200:**
```json
{
  "job_id": "job_xyz789",
  "video_id": "vid_abc123",
  "status": "PROCESSING",  // UPLOADED | PROCESSING | COMPLETED | FAILED
  "progress": 45,          // 0-100
  "error": null,
  "started_at": "2026-09-23T10:30:05Z",
  "completed_at": null
}
```

#### 6. Get Events
```http
GET /api/videos/{video_id}/events
```
**Response 200:**
```json
{
  "video_id": "vid_abc123",
  "events": [
    { "start_sec": 12.3, "end_sec": 15.8, "label": "speeding", "track_id": 3, "confidence": 0.92 },
    { "start_sec": 28.1, "end_sec": 32.0, "label": "illegal_parking", "track_id": 7, "confidence": 0.87 }
  ],
  "total_count": 2
}
```

#### 7. Get Risk Score
```http
GET /api/videos/{video_id}/risk
```
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
  "high_risk_tracks": [3, 7]
}
```

#### 8. Get Full Result (Annotated Video + Thumbnail)
```http
GET /api/videos/{video_id}/result
```
**Response 200:**
```json
{
  "video_id": "vid_abc123",
  "annotated_video_url": "/api/videos/vid_abc123/annotated.mp4",
  "thumbnail_url": "/api/videos/vid_abc123/thumbnail.jpg",
  "result_json_url": "/api/videos/vid_abc123/result.json"
}
```

---

## 🗄️ Database Schema / DB Sxemasi (4 Jadval)

### Video
```sql
CREATE TABLE video (
    id VARCHAR(32) PRIMARY KEY,           -- vid_abc123
    filename VARCHAR(255) NOT NULL,
    size_bytes BIGINT NOT NULL,
    duration_sec REAL NOT NULL,
    camera_id VARCHAR(64) DEFAULT 'cam_01',
    status VARCHAR(20) NOT NULL,          -- UPLOADED, PROCESSING, COMPLETED, FAILED
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP NULL
);
```

### Job
```sql
CREATE TABLE job (
    id VARCHAR(32) PRIMARY KEY,           -- job_xyz789
    video_id VARCHAR(32) REFERENCES video(id),
    status VARCHAR(20) NOT NULL,          -- UPLOADED, PROCESSING, COMPLETED, FAILED
    progress INTEGER DEFAULT 0,           -- 0-100
    error TEXT NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Event
```sql
CREATE TABLE event (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(32) REFERENCES video(id),
    job_id VARCHAR(32) REFERENCES job(id),
    start_sec REAL NOT NULL,
    end_sec REAL NOT NULL,
    label VARCHAR(32) NOT NULL,           -- speeding, illegal_parking, illegal_uturn, wrong_way, stop_line_crossing
    track_id INTEGER NOT NULL,
    confidence REAL DEFAULT 0.9,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### RiskScore
```sql
CREATE TABLE risk_score (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(32) REFERENCES video(id) UNIQUE,
    overall_risk REAL NOT NULL,
    by_category JSONB NOT NULL,           -- {"speeding": 0.8, ...}
    high_risk_tracks INTEGER[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## ⚙️ Background Jobs / Fon Vazifalar

### Implementation (FastAPI BackgroundTasks)
```python
from fastapi import BackgroundTasks

@router.post("/videos/{video_id}/process")
async def process_video(video_id: str, background_tasks: BackgroundTasks):
    job = create_job(video_id)
    background_tasks.add_task(run_inference, job.id, video_id)
    return {"job_id": job.id, "status": "PROCESSING", "progress": 0}

async def run_inference(job_id: str, video_id: str):
    update_job(job_id, progress=10, status="PROCESSING")
    # 1. Video ni o'qish
    update_job(job_id, progress=30)
    # 2. Engine orqali qayta ishlash
    events = TrafficPipeline(config_path="configs/camera.yaml").process_video(video_path)
    update_job(job_id, progress=70)
    # 3. Natijalarni DB ga yozish
    save_events(video_id, job_id, events)
    calc_and_save_risk(video_id, events)
    # 4. Annotated video + thumbnail yaratish
    create_annotated_video(video_path, events, output_path)
    create_thumbnail(video_path, thumbnail_path)
    update_job(job_id, progress=100, status="COMPLETED")
```

### Progress Updates (Mock)
```python
async def run_inference(job_id: str, video_id: str):
    for p in [10, 30, 50, 70, 90, 100]:
        await asyncio.sleep(0.5)  # Mock delay
        update_job(job_id, progress=p)
    # ... haqiqiy ish
```

---

## 📁 Output Structure / Chiquv Tuzilishi
```
data/
└── outputs/
    └── video_{video_id}/
        ├── result.json           # events + risk + metadata
        ├── annotated.mp4         # Bounding boxlar bilan video
        └── thumbnail.jpg         # 10-sondan frame (ffmpeg)
```

**result.json** misol:
```json
{
  "video_id": "vid_abc123",
  "duration_sec": 85.3,
  "events": [...],
  "risk": {...},
  "processing_time_sec": 12.4,
  "engine_version": "1.0.0-mock"
}
```

---

## ✅ Validatsiya Qoidalari / Validation Rules

| Tekshiruv | Limit | Xato Kodi |
|-----------|-------|-----------|
| MIME type | `video/mp4` | 400 |
| File size | ≤ 100 MB | 413 |
| Duration | ≤ 120 sec | 400 |
| Codec | H.264 / H.265 | 400 |
| Decode test | ffprobe success | 400 |

---

## 🧪 Testing / Testlash
```bash
# Unit tests
pytest tests/test_api.py -v

# Integration test (full flow)
python tests/integration_test.py

# Load test (locust)
locust -f tests/load_test.py --host=http://localhost:8000
```