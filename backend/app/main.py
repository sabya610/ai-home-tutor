"""FastAPI application entry point for the AI Home Tutor."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .config import get_settings
from .routers import dictation, health, homework, students, tutor

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(students.router)
app.include_router(dictation.router)
app.include_router(homework.router)
app.include_router(tutor.router)

# Create tables at import so both the server and TestClient are ready.
db.init_db()

class _NoCacheStatic(StaticFiles):
    """UI assets revalidate each load (ETag -> 304), so edits show on a normal
    refresh instead of needing a hard refresh."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Serve the child/parent web UI. Mounted last so /api/* wins.
_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
if _FRONTEND.is_dir():
    app.mount("/", _NoCacheStatic(directory=str(_FRONTEND), html=True), name="frontend")
