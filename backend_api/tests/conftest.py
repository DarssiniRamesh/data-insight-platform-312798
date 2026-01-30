import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generator, Optional
from uuid import uuid4

import pytest
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from tests.mocks.mock_collibra import MockCollibraAdapter
from tests.mocks.mock_immuta import MockImmutaAdapter
from tests.utils.audit_helpers import (
    AuditEventExpectation,
    assert_audit_event,
    fetch_audit_events,
)

# ----------------------------
# Dependency "keys" for overrides
# ----------------------------
# NOTE: These are placeholders to allow TDD without any application code yet.
# In the real implementation, the app should expose dependencies (e.g., in src/api/deps.py)
# and tests should override those. For now we use request.app.state.* for deterministic wiring.

APP_STATE_DB_CONN_KEY = "db_conn"
APP_STATE_AUDIT_REPO_KEY = "audit_repo"
APP_STATE_REGISTRATION_REPO_KEY = "registration_repo"
APP_STATE_POLICY_REPO_KEY = "policy_repo"
APP_STATE_COLLIBRA_KEY = "collibra_adapter"
APP_STATE_IMMUTA_KEY = "immuta_adapter"


# ----------------------------
# Minimal in-memory repositories (test doubles)
# ----------------------------
@dataclass
class InMemoryRegistrationRepo:
    """Test-double repository for draft registration with duplicate detection."""

    existing: Dict[str, Dict[str, Any]]

    def create_draft(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        key = f"{draft['product_name']}::{draft.get('version', 'v1.0')}"
        if key in self.existing:
            raise ValueError("DuplicateResource")
        self.existing[key] = draft
        return draft


@dataclass
class InMemoryPolicyRepo:
    """Test-double policy repository for grant/enforce operations."""

    grants: Dict[str, Dict[str, Any]]

    def grant(self, product_id: str, role: str) -> None:
        if product_id in self.grants and self.grants[product_id].get("role") == role:
            raise ValueError("PolicyConflict")
        self.grants[product_id] = {"role": role}

    def has_access(self, product_id: str, role: str) -> bool:
        return self.grants.get(product_id, {}).get("role") == role


@dataclass
class SQLiteAuditLogRepo:
    """SQLite-backed audit repo used by tests to assert audit logging behavior."""

    conn: sqlite3.Connection

    def create_event(self, event: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_log (
                event_id,
                action,
                entity_id,
                correlation_id,
                outcome,
                error_code,
                error_message,
                occurred_at_utc,
                details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["action"],
                event.get("entity_id"),
                event["correlation_id"],
                event["outcome"],
                event.get("error_code"),
                event.get("error_message"),
                event["occurred_at_utc"],
                event.get("details_json"),
            ),
        )
        self.conn.commit()

    def list_events(self) -> list[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
                event_id,
                action,
                entity_id,
                correlation_id,
                outcome,
                error_code,
                error_message,
                occurred_at_utc,
                details_json
            FROM audit_log
            ORDER BY rowid ASC
            """
        ).fetchall()
        return [
            {
                "event_id": r[0],
                "action": r[1],
                "entity_id": r[2],
                "correlation_id": r[3],
                "outcome": r[4],
                "error_code": r[5],
                "error_message": r[6],
                "occurred_at_utc": r[7],
                "details_json": r[8],
            }
            for r in rows
        ]


# ----------------------------
# SQLite fixture (in-memory)
# ----------------------------
@pytest.fixture()
def sqlite_conn() -> Generator[sqlite3.Connection, None, None]:
    """Provides an in-memory SQLite connection with the audit_log table created."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            event_id TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            entity_id TEXT NULL,
            correlation_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            error_code TEXT NULL,
            error_message TEXT NULL,
            occurred_at_utc TEXT NOT NULL,
            details_json TEXT NULL
        )
        """
    )
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture()
def audit_repo(sqlite_conn: sqlite3.Connection) -> SQLiteAuditLogRepo:
    """SQLite audit repository fixture."""
    return SQLiteAuditLogRepo(conn=sqlite_conn)


@pytest.fixture()
def registration_repo() -> InMemoryRegistrationRepo:
    """In-memory registration repository with deterministic duplicate behavior."""
    return InMemoryRegistrationRepo(existing={})


@pytest.fixture()
def policy_repo() -> InMemoryPolicyRepo:
    """In-memory policy repository with deterministic conflict behavior."""
    return InMemoryPolicyRepo(grants={})


@pytest.fixture()
def mock_collibra() -> MockCollibraAdapter:
    """Mock Collibra adapter."""
    return MockCollibraAdapter()


@pytest.fixture()
def mock_immuta() -> MockImmutaAdapter:
    """Mock Immuta adapter."""
    return MockImmutaAdapter()


@pytest.fixture()
def fixed_clock() -> Callable[[], str]:
    """Deterministic clock fixture to avoid time.now in tests."""
    return lambda: "2026-01-29T12:34:56Z"


def _audit(
    app: FastAPI,
    *,
    action: str,
    outcome: str,
    occurred_at_utc: str,
    entity_id: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    details_json: Optional[str] = None,
) -> str:
    correlation_id = str(uuid4())
    event = {
        "event_id": str(uuid4()),
        "action": action,
        "entity_id": entity_id,
        "correlation_id": correlation_id,
        "outcome": outcome,
        "error_code": error_code,
        "error_message": error_message,
        "occurred_at_utc": occurred_at_utc,
        "details_json": details_json,
    }
    app.state.audit_repo.create_event(event)
    return correlation_id


# ----------------------------
# FastAPI app factory (real implementation under src/)
# ----------------------------
@pytest.fixture()
def app_factory(
    sqlite_conn: sqlite3.Connection,
    audit_repo: SQLiteAuditLogRepo,
    registration_repo: InMemoryRegistrationRepo,
    policy_repo: InMemoryPolicyRepo,
    mock_collibra: MockCollibraAdapter,
    mock_immuta: MockImmutaAdapter,
    fixed_clock: Callable[[], str],
) -> Callable[[], FastAPI]:
    """
    Creates a FastAPI app using the real application factory and wires test doubles via app.state.

    The app's dependencies read from request.app.state.* (see src/api/deps.py), so tests can inject
    deterministic repositories/adapters and a fixed clock.
    """
    from src.api.app_factory import create_app

    def _create_app() -> FastAPI:
        app = create_app(init_sqlite=False)

        # Wire test doubles via app.state (acts as dependency overrides).
        app.state.db_conn = sqlite_conn
        app.state.audit_repo = audit_repo
        app.state.registration_repo = registration_repo
        app.state.policy_repo = policy_repo
        app.state.collibra_adapter = mock_collibra
        app.state.immuta_adapter = mock_immuta
        app.state.clock = fixed_clock

        return app

    return _create_app


@pytest.fixture()
def app(app_factory: Callable[[], FastAPI]) -> FastAPI:
    """FastAPI app fixture."""
    return app_factory()


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture()
def audit_events(app: FastAPI) -> Callable[[], list[Dict[str, Any]]]:
    """Convenience accessor for audit events."""
    return lambda: fetch_audit_events(app)
