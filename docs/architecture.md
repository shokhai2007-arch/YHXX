# Architecture / Arxitektura

## 🎯 Overview / Umumiy Ko'rinish
Bu hujjat **CyberLeek** jamoasi WUIT hackathoni uchun yaratilayotgan avtomobil yo'l harakati tahlil tizimi arxitekturasini tasvirlaydi. Asosiy talab: **real AI model yo'q**, barcha natijalar mock/namuna.

---

## ⚡ Dual-System Architecture (Muhim Qoida)

Tizim **ikki alohida tizimdan** iborat, ular **bitta `engine/`** kod bazasini ulashadi:

### 1. JUDGE ENVIRONMENT (Baholash Muhiti)
```bash
python run_submission.py
```
- **Kirish**: `solution.py` → `detect_events(video_path: str) -> list[list]`
- **Chiqish**: `predictions.json` fayli
- **Cheklovlar**: Hech qanday web framework, database, background job, WebSocket yo'q
- **Maqsad**: Tez, deterministik, avtomatik baholanishi mumkin

### 2. WEBSITE / DEMO (Ko'rsatish Muhiti)
```
Browser → Next.js (Frontend) → FastAPI (Backend) → Inference Engine → Events → Vizualizatsiya
```
- **Alahida deploy** (Vercel + Render/VDS)
- **Judge bilan bog'lanmaydi** — alohida microservice
- **Background jobs** bilan video qayta ishlash
- **Real-time polling** (1s) progres uchun

### 3. SHARED ENGINE (Ulashilgan Motor)
```
engine/
├── pipeline.py          # TrafficPipeline — asosiy entry point
├── detector.py          # Mock obyekt aniqlash (Phase 2)
├── tracker.py           # Mock obyekt kuzatish (Phase 2)
├── event_engine.py      # Voqealar logikasi (Phase 2)
├── risk_engine.py       # Risk hisoblash (Phase 2)
├── temporal.py          # Vaqtaviy tahlil (Phase 2)
```
- **Bitta kod bazasi** — ikkala tizim ham shu yerdan `import` qiladi
- **Config-driven**: `configs/camera.yaml` da lanelar, stop line, crosswalk polygonlari

---

## 🤖 Mock AI Strategy (Mock AI Strategiyasi)

| Komponent | Haqiqiy AI | Mock Versiya (MVP) |
|-----------|------------|-------------------|
| Object Detection | YOLOv8, RT-DETR | `random` bbox + class label |
| Tracking | ByteTrack, BoT-SORT | `track_id` = `frame_idx % 10` |
| Speed Estimation | Homography + Kalman | `speed = 40 + random(-10, 10)` |
| Event Detection | Rule-based on tracks | Hardcoded time intervals |
| Risk Scoring | ML model | `risk = min(speed/100, 1.0)` |

**Prinsip**: `engine/pipeline.py` ichida barcha "AI" funksiyalar `random` yoki `time.sleep` bilan simulyatsiya qilinadi. Keyin real model o'rniga o'tkazish oson bo'ladi.

---

## 🗺️ Roadmap / Yo'l Xaritasi

### Phase 1 — Core (Hozirgi vazifa)
- [ ] `solution.py` — judge entry point
- [ ] `run_submission.py` — video o'qib, `detect_events` chaqirib, `predictions.json` yozadi
- [ ] `evaluate.py` — prediction vs ground truth solishtiradi
- [ ] `engine/pipeline.py` — `TrafficPipeline` class (mock)
- [ ] `configs/camera.yaml` — sahna konfiguratsiyasi
- [ ] `requirements.txt` — Python dependencies
- [ ] CI: `.github/workflows/test.yml`

### Phase 2 — Backend
- [ ] FastAPI app (`app/main.py`)
- [ ] API routes: `/api/videos`, `/api/jobs`, `/api/videos/{id}/events|risk|result`
- [ ] DB: SQLite → Postgres (4 jadval: Video, Job, Event, RiskScore)
- [ ] BackgroundTasks video processing
- [ ] Validatsiya: MP4, ≤100MB, ≤2min, MIME, ffprobe decode test
- [ ] Output: `data/outputs/video_123/{result.json, annotated.mp4, thumbnail.jpg}`

### Phase 3 — Frontend
- [ ] Next.js + TypeScript + Tailwind
- [ ] Sahifalar: `/`, `/demo`, `/results/[id]`, `/about`, `/report`
- [ ] Komponentlar: VideoUploader, ProcessingProgress, VideoPlayer, EventTimeline, EventList, RiskChart, EventBadge, StatsCard, TrafficDashboard
- [ ] Video seek: `video.currentTime = start_sec`
- [ ] Sample demo mode: `website/public/samples/` + `predictions_samples.json` (inference yo'q)

---

## 🛠️ Tech Stack / Texnologiyalar

| Qavat | Texnologiya | Versiya |
|-------|-------------|---------|
| Backend | FastAPI | 0.110+ |
| Language | Python | 3.10+ |
| DB (Phase 2) | SQLAlchemy + SQLite | 2.0+ |
| Video I/O | OpenCV + FFmpeg | 4.8+ / 6.0+ |
| Frontend | Next.js + TypeScript | 14+ / 5.3+ |
| Styling | Tailwind CSS | 3.4+ |
| Charts | Recharts | 2.10+ |
| Video Player | HTML5 `<video>` | — |
| Deploy (Phase 2+) | Docker + Nginx | — |

---

## 📐 Data Flow / Ma'lumot Oqimi

### Judge Flow
```
video.mp4 → run_submission.py → solution.detect_events() → [[s, e, label], ...] → predictions.json
```

### Website Flow
```
POST /api/videos (multipart) → Video saqlanadi (UPLOADED)
    ↓
POST /api/videos/{id}/process → Job yaratiladi (PROCESSING)
    ↓
BackgroundTask: engine.pipeline.process_video() → events[]
    ↓
Job → COMPLETED, events DB ga yoziladi
    ↓
GET /api/videos/{id}/events → Frontend ko'rsatadi
    ↓
VideoPlayer da event click → video.currentTime = start_sec
```

---

## 🔒 Security / Xavfsizlik (MVP)
- **MVP da**: Hech qanday auth yo'q (hackathon demo)
- **Keyingi**: Vercel Auth (SSO) preview deployments uchun
- **Secrets**: `.env` fayllar, gitga yozilmaydi
- **File upload**: MIME + size + ffprobe validatsiya