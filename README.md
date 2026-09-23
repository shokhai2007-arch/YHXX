# CyberLeek Traffic Detection

[![CI](https://github.com/your-org/YHXX/workflows/CI%20Pipeline/badge.svg)](https://github.com/your-org/YHXX/actions)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **WUIT Hackathon 2026** — CyberLeek Team  
> Video-based traffic violation detection system (Mock AI for demo)

## 🎯 Overview

CyberLeek analyzes traffic videos to detect violations:
- **Speeding** — exceeding speed limits
- **Illegal Parking** — unauthorized stopping
- **Illegal U-turn** — prohibited turnarounds
- **Wrong Way** — driving against traffic
- **Stop Line Crossing** — running red lights

**No real AI models** — all detection uses deterministic mock responses for hackathon demo. Engine is designed for easy model swap.

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  JUDGE ENVIRONMENT (Standalone)                                 │
│  python run_submission.py → solution.py → detect_events()      │
│  → predictions.json  ✅  No web/DB/framework                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                    SHARED ENGINE (engine/pipeline.py)
                              │
┌─────────────────────────────────────────────────────────────────┐
│  WEBSITE / DEMO (FastAPI + PostgreSQL + Redis)                 │
│  Browser → Next.js → FastAPI → BackgroundTasks → Events        │
│  → Visualization  ✅  Separate deploy, no judge coupling       │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/your-org/YHXX.git
cd YHXX
cp .env.example .env    # Edit POSTGRES_PASSWORD
docker compose up --build -d
```

**Services:**
- **API:** http://localhost:8000/docs (Swagger UI)
- **PostgreSQL:** localhost:5432 (internal only)
- **Redis:** localhost:6379 (internal only)

### Local Development

```bash
# Prerequisites: Python 3.10+, PostgreSQL 16+, Redis 7+, FFmpeg
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env  # Configure DATABASE_URL, REDIS_URL
alembic upgrade head

# Terminal 1: API
uvicorn app.main:app --reload --port 8000
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/videos` | Upload video (multipart) |
| `GET` | `/api/v1/videos/{id}` | Video info |
| `POST` | `/api/v1/videos/{id}/process` | Start processing (202) |
| `GET` | `/api/v1/jobs/{id}` | Job status (poll 1s) |
| `GET` | `/api/v1/videos/{id}/events` | Detected events |
| `GET` | `/api/v1/videos/{id}/risk` | Risk scores |
| `GET` | `/api/v1/videos/{id}/result` | Output file URLs |

[Full API Docs](docs/api-endpoints.md)

## 🎬 Example Flow

```bash
# 1. Upload video
curl -X POST "http://localhost:8000/api/v1/videos" \
  -F "file=@traffic.mp4;type=video/mp4" \
  -F "camera_id=cam_01"

# 2. Start processing
curl -X POST "http://localhost:8000/api/v1/videos/vid_abc123/process"

# 3. Poll job (every 1s)
curl "http://localhost:8000/api/v1/jobs/job_xyz789"

# 4. Get results
curl "http://localhost:8000/api/v1/videos/vid_abc123/events"
curl "http://localhost:8000/api/v1/videos/vid_abc123/risk"

# 5. Download annotated video
curl -o annotated.mp4 "http://localhost:8000/api/v1/outputs/video_vid_abc123/annotated.mp4"
```

## 🏁 Judge Environment

```bash
# No Docker, no DB, no web framework
python run_submission.py video.mp4
# or
python solution.py video.mp4
```

**Output:** `predictions.json`
```json
[[12.3, 15.8, "speeding"], [28.1, 32.0, "illegal_parking"]]
```

## 🛠 Development

### Make Commands

```bash
make help          # Show all commands
make dev           # Start dev stack
make dev-logs      # Follow logs
make test          # Run tests in container
make test-local    # Run tests locally
make lint          # Ruff + MyPy
make lint-fix      # Auto-fix
make migrate       # Run migrations
make migrate-new MSG='description'  # New migration
make shell         # Backend shell
make db-shell      # PostgreSQL shell
make redis-cli     # Redis CLI
make dev-clean     # Clean slate
```

### Testing

```bash
# Unit tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov=engine

# Lint
ruff check .
mypy app/ engine/
```

### Project Structure

```
YHXX/
├── app/                    # FastAPI Backend
│   ├── api/               # Endpoints (health, videos, jobs, events, risk, results)
│   ├── models/            # SQLAlchemy models (Video, Job, Event, RiskScore)
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic (validation, inference)
│   ├── utils/             # Video utilities (ffprobe, thumbnail, annotated)
│   ├── config.py          # Pydantic Settings
│   ├── database.py        # Async SQLAlchemy
│   └── main.py            # FastAPI app
├── engine/                # Shared Engine (Judge + Website)
│   └── pipeline.py        # TrafficPipeline (mock detection)
├── configs/
│   └── camera.yaml        # Scene geometry (lanes, stop lines, ROI)
├── data/
│   ├── uploads/           # Uploaded videos
│   └── outputs/           # Processed results (annotated.mp4, thumbnail.jpg, result.json)
├── postgres/              # DB init scripts
├── docs/                  # Documentation
├── tests/                 # Test suite (to be created)
├── .github/workflows/     # CI/CD
├── Dockerfile             # Production image
├── Dockerfile.dev         # Dev image (hot reload)
├── docker-compose.yml     # Dev stack (PostgreSQL + Redis + Backend)
├── pyproject.toml         # Package config
├── requirements.txt       # Dependencies
├── SETUP.md               # Detailed setup guide
├── Makefile               # Dev commands
├── solution.py            # Judge entry point
├── run_submission.py      # Judge runner
└── evaluate.py            # Evaluation script
```

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `changeme` | **Change in production!** |
| `DATABASE_URL` | `postgresql+asyncpg://cyberleek:changeme@postgres:5432/cyberleek` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `MAX_UPLOAD_SIZE_MB` | `100` | Max video size |
| `MAX_DURATION_SEC` | `120` | Max video duration |
| `UPLOAD_DIR` | `/app/data/uploads` | Upload directory |
| `OUTPUT_DIR` | `/app/data/outputs` | Output directory |

## 📦 Dependencies

**Core (Phase 1):**
- `opencv-python-headless` — Video processing
- `ffmpeg-python` — FFmpeg wrapper
- `PyYAML` — Config parsing

**Backend (Phase 2):**
- `fastapi`, `uvicorn` — Web framework
- `sqlalchemy`, `asyncpg` — Async ORM + PostgreSQL
- `pydantic`, `pydantic-settings` — Validation + Config
- `alembic` — Migrations
- `redis` — Redis client
- `python-multipart` — File upload
- `watchfiles` — Hot reload

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 👥 Team

**CyberLeek** — WUIT Hackathon 2026

---

*Built for demo purposes. Mock AI responses only. Replace `engine/pipeline.py` with real models for production.*