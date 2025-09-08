from fastapi import FastAPI
import os
from pathlib import Path

app = FastAPI(title="Persona Lab API")

def read_version() -> str:
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0-unknown"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {
        "service": "persona-lab",
        "version": read_version(),
        "host": os.getenv("APP_HOST", "0.0.0.0"),
        "port": int(os.getenv("APP_PORT", "8001")),
        "workers": int(os.getenv("WORKERS", "1")),
    }

@app.get("/")
def root():
    return {
        "message": "Persona Lab — Foundation & Portability",
        "docs": "/docs",
        "health": "/health",
        "version": "/version",
    }
