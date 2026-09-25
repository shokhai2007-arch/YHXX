from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import events, health, jobs, results, risk, videos
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    # Ensure directories exist
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown (if needed)


app = FastAPI(
    title="CyberLeek Traffic Detection API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for output access
app.mount("/api/v1/outputs", StaticFiles(directory=settings.OUTPUT_DIR), name="outputs")

# Include routers
app.include_router(health.router)
app.include_router(videos.router)
app.include_router(jobs.router)
app.include_router(events.router)
app.include_router(risk.router)
app.include_router(results.router)


@app.get("/")
async def root():
    return {"message": "CyberLeek Traffic Detection API", "version": "1.0.0", "docs": "/docs"}
