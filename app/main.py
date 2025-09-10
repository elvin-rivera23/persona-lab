import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

app = FastAPI(title="Persona Lab API")


def read_version() -> str:
    """Read version string from repo root VERSION file."""
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0-unknown"


def iso_now() -> str:
    """UTC timestamp ISO8601."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/health")
def health():
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.get("/version")
def version():
    """Expose service version and runtime settings (non-sensitive)."""
    return {
        "service": "persona-lab",
        "version": read_version(),
        "host": os.getenv("APP_HOST", "0.0.0.0"),
        "port": int(os.getenv("APP_PORT", "8001")),
        "workers": int(os.getenv("WORKERS", "1")),
    }


@app.get("/__meta")
def meta():
    """
    Build & runtime metadata for portability/debug.
    Data sources:
      - VERSION file
      - Build args promoted to env: GIT_SHA, GIT_BRANCH, BUILD_DATE
      - Runtime: python, uvicorn, platform
    """
    return {
        "service": "persona-lab",
        "version": read_version(),
        "git": {
            "sha": os.getenv("GIT_SHA", "unknown"),
            "branch": os.getenv("GIT_BRANCH", "unknown"),
        },
        "build": {
            "date": os.getenv("BUILD_DATE", "unknown"),
            "image_labels": {
                "org.opencontainers.image.revision": os.getenv("GIT_SHA", "unknown"),
                "org.opencontainers.image.created": os.getenv("BUILD_DATE", "unknown"),
            },
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            "started_at": iso_now(),
        },
        "endpoints": {
            "root": "/",
            "docs": "/docs",
            "health": "/health",
            "version": "/version",
            "meta": "/__meta",
        },
    }


@app.get("/")
def root():
    """Landing endpoint with pointers."""
    return {
        "message": "Persona Lab — Foundation & Portability",
        "docs": "/docs",
        "health": "/health",
        "version": "/version",
        "meta": "/__meta",
    }
