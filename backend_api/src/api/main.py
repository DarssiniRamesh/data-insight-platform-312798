"""
FastAPI entrypoint.

Exposes a module-level `app` for uvicorn and for `generate_openapi.py`.
"""

from __future__ import annotations

from src.api.app_factory import create_app

app = create_app()
