"""
Database wiring for the backend_api service.

We use SQLite for persistence (file-based by default, but tests can override the engine/session).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.engine import Engine


def _default_sqlite_url() -> str:
    """
    Default SQLite URL for local dev.

    Tests typically override the engine/session using FastAPI dependency overrides.
    """
    return "sqlite:///./app.db"


# Module-level default engine (used for dev / normal runs).
DEFAULT_ENGINE: Engine = create_engine(
    _default_sqlite_url(),
    connect_args={"check_same_thread": False},
)


# PUBLIC_INTERFACE
def init_db(engine: Optional[Engine] = None) -> None:
    """Create all tables if they do not exist."""
    SQLModel.metadata.create_all(engine or DEFAULT_ENGINE)


# PUBLIC_INTERFACE
def get_session(engine: Optional[Engine] = None) -> Session:
    """Create a new SQLModel Session bound to the given engine (or the default engine)."""
    return Session(engine or DEFAULT_ENGINE)
