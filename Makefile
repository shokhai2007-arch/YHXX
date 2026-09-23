# CyberLeek Traffic Detection — Make Commands
# Usage: make <command>

.PHONY: help dev dev-logs dev-down dev-clean build test test-local lint lint-fix migrate migrate-new shell db-shell redis-cli clean

# Default target
help:
	@echo "CyberLeek Traffic Detection — Available Commands:"
	@echo ""
	@echo "  Development (Docker):"
	@echo "    make dev           Start dev stack (postgres + redis + backend)"
	@echo "    make dev-logs      Follow backend logs"
	@echo "    make dev-down      Stop dev stack (keep volumes)"
	@echo "    make dev-clean     Stop + remove volumes (clean slate)"
	@echo ""
	@echo "  Building:"
	@echo "    make build         Build docker images"
	@echo ""
	@echo "  Testing:"
	@echo "    make test          Run tests in container"
	@echo "    make test-local    Run tests locally (requires .venv)"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint          Run ruff + mypy"
	@echo "    make lint-fix      Auto-fix ruff issues"
	@echo ""
	@echo "  Database (Alembic):"
	@echo "    make migrate       Run alembic upgrade head"
	@echo "    make migrate-new   Create new migration (usage: make migrate-new MSG='description')"
	@echo ""
	@echo "  Shell Access:"
	@echo "    make shell         Shell into backend container"
	@echo "    make db-shell      PostgreSQL shell"
	@echo "    make redis-cli     Redis CLI"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean         Remove __pycache__, .pytest_cache, *.pyc"

# Docker Compose shortcuts
COMPOSE = docker compose
COMPOSE_DEV = docker compose -f docker-compose.yml

# Development stack
dev:
	$(COMPOSE_DEV) up --build -d

dev-logs:
	$(COMPOSE_DEV) logs -f backend

dev-down:
	$(COMPOSE_DEV) down

dev-clean:
	$(COMPOSE_DEV) down -v

# Build
build:
	$(COMPOSE_DEV) build

# Testing
test:
	$(COMPOSE_DEV) exec backend pytest tests/ -v

test-local:
	@if [ ! -d ".venv" ]; then echo "Run 'python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]' first"; exit 1; fi
	.venv/bin/pytest tests/ -v

# Linting
lint:
	$(COMPOSE_DEV) exec backend ruff check app/ engine/
	$(COMPOSE_DEV) exec backend mypy app/ engine/

lint-fix:
	$(COMPOSE_DEV) exec backend ruff check --fix app/ engine/

# Database migrations
migrate:
	$(COMPOSE_DEV) exec backend alembic upgrade head

migrate-new:
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-new MSG='description'"; exit 1; fi
	$(COMPOSE_DEV) exec backend alembic revision --autogenerate -m "$(MSG)"

# Shell access
shell:
	$(COMPOSE_DEV) exec backend bash

db-shell:
	$(COMPOSE_DEV) exec postgres psql -U cyberleek -d cyberleek

redis-cli:
	$(COMPOSE_DEV) exec redis redis-cli

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov 2>/dev/null || true

# Install package locally (for development)
install-dev:
	pip install -e ".[dev]"

# Judge environment test
test-judge:
	python run_submission.py data/uploads/test_video.mp4