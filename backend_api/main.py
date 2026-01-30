"""
Uvicorn entrypoint used by the platform startCommand.

The platform starts this service with:

  python3 -m uvicorn main:app --host 0.0.0.0 --port 3001

The actual application code lives under `src/api/main.py`. This file bridges the
platform's expected module path (`main:app`) to the project's internal package
layout.

It intentionally performs no work other than importing the already-configured
FastAPI `app` so startup remains lightweight and `/healthz` can return quickly.
"""

from __future__ import annotations

from src.api.main import app

