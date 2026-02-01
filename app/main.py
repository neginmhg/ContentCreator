"""FastAPI app entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.db import init_db
from app.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


app = FastAPI(title="Content Generator")

app.include_router(router, prefix="", tags=["content"])

@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    init_db()

@app.get("/health")
def health_check():
    """Health check endpoint for deployment platforms."""
    return {"status": "healthy", "message": "Content Generator is running"}

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
