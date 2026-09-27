from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import events, health, jobs, results, risk, videos, web
from app.config import settings
from app.database import init_db


def ensure_runtime_directories() -> None:
    """Create runtime directories needed by the application."""
    try:
        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # In test environments or restricted containers, directories may not be writable.
        # StaticFiles will fail later with a clearer error if directories don't exist.
        pass


# StaticFiles checks that its directory exists during construction.
# This must run before app.mount().
ensure_runtime_directories()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    # Ensure directories exist (redundant but safe)
    ensure_runtime_directories()
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

# Web UI (Jinja2 templates — Django uslubidagi sintaksis) / Web pages
app.include_router(web.router)

# Static files: web UI assets + sample data / Statik fayllar
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Custom 404 handler: API -> JSON, Web -> HTML
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"detail": exc.detail if hasattr(exc, "detail") else "Not found"},
        )
    return await web.not_found_page(request, exc)


@app.get("/")
async def root():
    return {"message": "CyberLeek Traffic Detection API", "version": "1.0.0", "docs": "/docs"}
