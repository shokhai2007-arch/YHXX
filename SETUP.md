# CyberLeek Traffic Detection — Setup Guide

## Quick Start (Docker) — Recommended

```bash
git clone https://github.com/your-org/YHXX.git
cd YHXX
cp .env.example .env  # Edit POSTGRES_PASSWORD
docker compose up --build -d
# API: http://localhost:8000/docs
```

## Manual Installation (Local Development)

### Prerequisites
- Python 3.10+
- PostgreSQL 16+
- Redis 7+
- FFmpeg

### Install

```bash
# 1. Clone
git clone https://github.com/your-org/YHXX.git
cd YHXX

# 2. Create venv
python -m venv .venv
source .venv/bin/activate

# 3. Install package in editable mode
pip install -e ".[dev]"

# 4. Configure env
cp .env.example .env
# Edit DATABASE_URL, REDIS_URL

# 5. Run migrations
alembic upgrade head

# 6. Start services
# Terminal 1: API
uvicorn app.main:app --reload --port 8000

# Terminal 2: PostgreSQL & Redis (or use docker compose up -d postgres redis)
```

## Judge Environment (Standalone)

```bash
# No Docker, no DB, no web framework
python run_submission.py video.mp4
# Output: predictions.json
```

## Testing

```bash
# Unit tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov=engine

# Lint
ruff check .
mypy app/ engine/
```

## Docker Commands

```bash
# Build
docker compose build

# Up (dev with hot reload)
docker compose up -d

# Logs
docker compose logs -f backend

# Migrations
docker compose exec backend alembic upgrade head

# Shell
docker compose exec backend bash

# Down (keep volumes)
docker compose down

# Down (remove volumes - clean slate)
docker compose down -v
```

## Make Commands

```bash
make help          # Show all commands
make dev           # Start dev stack (docker compose up -d)
make dev-logs      # Follow backend logs
make dev-down      # Stop dev stack
make dev-clean     # Stop + remove volumes
make build         # Build docker images
make test          # Run tests in container
make test-local    # Run tests locally
make lint          # Run ruff + mypy
make migrate       # Run alembic migrations
make migrate-new   # Create new migration
make shell         # Shell into backend container
make db-shell      # PostgreSQL shell
make redis-cli     # Redis CLI
```