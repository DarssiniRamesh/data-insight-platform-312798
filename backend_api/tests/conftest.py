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
# FastAPI placeholder app factory (routes are ONLY for enabling tests)
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
    Creates a FastAPI app with placeholder routes that mimic the contract.

    IMPORTANT:
    - These are NOT the "real" implementation; they exist purely to support TDD of the contract.
    - Real implementation should live under backend_api/src and tests should then be updated to import it.
    """

    def _create_app() -> FastAPI:
        app = FastAPI(title="TDD Placeholder API", version="0.0.0-test")

        # Wire test doubles via app.state (acts as dependency overrides).
        app.state.db_conn = sqlite_conn
        app.state.audit_repo = audit_repo
        app.state.registration_repo = registration_repo
        app.state.policy_repo = policy_repo
        app.state.collibra_adapter = mock_collibra
        app.state.immuta_adapter = mock_immuta
        app.state.clock = fixed_clock

        @app.exception_handler(Exception)
        async def _unhandled_exception_handler(
            request: Request, exc: Exception
        ) -> JSONResponse:
            # For tests we let unhandled exceptions surface as 500 with audit.
            correlation_id = _audit(
                app,
                action="internal.error",
                outcome="failure",
                occurred_at_utc=app.state.clock(),
                error_code="InternalServerError",
                error_message=str(exc),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "InternalServerError",
                        "http_status": 500,
                        "message": "An unexpected error occurred.",
                        "correlation_id": correlation_id,
                        "occurred_at_utc": app.state.clock(),
                        "details": {"exception": str(exc)},
                    }
                },
            )

        # --- Registration (Drafts) ---
        # TODO (implementation): Replace with real service at POST /v2/drafts per OpenAPI V2.
        @app.post("/v2/drafts", status_code=201)
        async def create_draft(payload: Dict[str, Any]) -> JSONResponse:
            # Minimal "validation"
            required_fields = ["product_name", "classification", "schema_ref", "dataset_ref"]
            missing = [f for f in required_fields if f not in payload]
            if missing:
                msg = f"validation error: missing fields: {missing}"
                correlation_id = _audit(
                    app,
                    action="register",
                    outcome="failure",
                    occurred_at_utc=app.state.clock(),
                    error_code="InvalidInput",
                    error_message=msg,
                    details_json='{"validation_path":"body"}',
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "InvalidInput",
                            "http_status": 400,
                            "message": "Request payload is invalid.",
                            "correlation_id": correlation_id,
                            "occurred_at_utc": app.state.clock(),
                            "details": {"validation_path": "body", "missing": missing},
                        }
                    },
                )

            # Duplicate check
            try:
                draft_id = f"draft_{uuid4().hex[:8]}"
                created = {
                    "draft_id": draft_id,
                    "status": "DRAFT",
                    "product_name": payload["product_name"],
                    "classification": payload["classification"],
                    "created_at_utc": app.state.clock(),
                }
                # Save and detect duplicates
                app.state.registration_repo.create_draft(
                    {
                        "draft_id": draft_id,
                        "product_name": payload["product_name"],
                        "version": payload.get("version", "v1.0"),
                    }
                )
            except ValueError as e:
                if str(e) == "DuplicateResource":
                    correlation_id = _audit(
                        app,
                        action="register",
                        outcome="failure",
                        occurred_at_utc=app.state.clock(),
                        error_code="DuplicateResource",
                        error_message="Duplicate name/version.",
                        entity_id=None,
                    )
                    return JSONResponse(
                        status_code=409,
                        content={
                            "error": {
                                "code": "Conflict",
                                "http_status": 409,
                                "message": "Duplicate resource.",
                                "correlation_id": correlation_id,
                                "occurred_at_utc": app.state.clock(),
                                "details": {"error_code": "DuplicateResource"},
                            }
                        },
                    )
                raise

            correlation_id = _audit(
                app,
                action="register",
                outcome="success",
                occurred_at_utc=app.state.clock(),
                entity_id=draft_id,
            )
            created["correlation_id"] = correlation_id
            return JSONResponse(status_code=201, content=created)

        # --- Integration touchpoints (not in OpenAPI V2; required by user TDD request) ---
        # TODO (implementation): replace with real integration endpoints/services.
        @app.post("/v2/integrations/collibra/publish", status_code=200)
        async def publish_collibra(payload: Dict[str, Any]) -> JSONResponse:
            ok, details = app.state.collibra_adapter.publish_metadata(payload)
            if ok:
                correlation_id = _audit(
                    app,
                    action="integrate.collibra",
                    outcome="success",
                    occurred_at_utc=app.state.clock(),
                    entity_id=payload.get("draft_id"),
                )
                return JSONResponse(
                    status_code=200,
                    content={"status": "ok", "correlation_id": correlation_id},
                )

            correlation_id = _audit(
                app,
                action="integrate.collibra",
                outcome="failure",
                occurred_at_utc=app.state.clock(),
                entity_id=payload.get("draft_id"),
                error_code="CollibraValidationFailed",
                error_message=details.get("message", "Collibra validation failed."),
            )
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "GateComplianceFailed",
                        "http_status": 422,
                        "message": "Collibra integration gate failed.",
                        "correlation_id": correlation_id,
                        "occurred_at_utc": app.state.clock(),
                        "details": {"code": "CollibraValidationFailed"},
                    }
                },
            )

        @app.post("/v2/integrations/immuta/register", status_code=200)
        async def register_immuta(payload: Dict[str, Any]) -> JSONResponse:
            ok, details = app.state.immuta_adapter.register_dataset(payload)
            if ok:
                correlation_id = _audit(
                    app,
                    action="integrate.immuta",
                    outcome="success",
                    occurred_at_utc=app.state.clock(),
                    entity_id=payload.get("draft_id"),
                )
                return JSONResponse(status_code=200, content={"status": "ok", "correlation_id": correlation_id})

            correlation_id = _audit(
                app,
                action="integrate.immuta",
                outcome="failure",
                occurred_at_utc=app.state.clock(),
                entity_id=payload.get("draft_id"),
                error_code="PolicyDenied",
                error_message=details.get("message", "Denied by policy."),
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "Forbidden",
                        "http_status": 403,
                        "message": "Denied by policy.",
                        "correlation_id": correlation_id,
                        "occurred_at_utc": app.state.clock(),
                        "details": {"code": "PolicyDenied"},
                    }
                },
            )

        # --- Access policies (not in OpenAPI V2; required by user TDD request) ---
        @app.post("/v2/policies/grant", status_code=200)
        async def grant_policy(payload: Dict[str, Any]) -> JSONResponse:
            if "product_id" not in payload or "role" not in payload:
                correlation_id = _audit(
                    app,
                    action="policy.grant",
                    outcome="failure",
                    occurred_at_utc=app.state.clock(),
                    error_code="InvalidInput",
                    error_message="Missing product_id or role.",
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "InvalidInput",
                            "http_status": 400,
                            "message": "Request payload is invalid.",
                            "correlation_id": correlation_id,
                            "occurred_at_utc": app.state.clock(),
                            "details": {"validation_path": "body"},
                        }
                    },
                )

            try:
                app.state.policy_repo.grant(product_id=payload["product_id"], role=payload["role"])
            except ValueError as e:
                if str(e) == "PolicyConflict":
                    correlation_id = _audit(
                        app,
                        action="policy.grant",
                        outcome="failure",
                        occurred_at_utc=app.state.clock(),
                        error_code="PolicyConflict",
                        error_message="Policy already exists for this role.",
                        entity_id=payload["product_id"],
                    )
                    return JSONResponse(
                        status_code=409,
                        content={
                            "error": {
                                "code": "Conflict",
                                "http_status": 409,
                                "message": "Policy conflict.",
                                "correlation_id": correlation_id,
                                "occurred_at_utc": app.state.clock(),
                                "details": {"error_code": "PolicyConflict"},
                            }
                        },
                    )
                raise

            correlation_id = _audit(
                app,
                action="policy.grant",
                outcome="success",
                occurred_at_utc=app.state.clock(),
                entity_id=payload["product_id"],
            )
            return JSONResponse(status_code=200, content={"status": "ok", "correlation_id": correlation_id})

        @app.post("/v2/protected/operation", status_code=200)
        async def protected_operation(x_role: Optional[str] = Header(default=None)) -> JSONResponse:
            # deny-by-default enforcement (DPR-V2-FR-031)
            product_id = "product_protected_001"
            role = x_role or "anonymous"
            if not app.state.policy_repo.has_access(product_id=product_id, role=role):
                correlation_id = _audit(
                    app,
                    action="policy.enforce",
                    outcome="failure",
                    occurred_at_utc=app.state.clock(),
                    entity_id=product_id,
                    error_code="PolicyDenied",
                    error_message="Protected operation denied by policy.",
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "Forbidden",
                            "http_status": 403,
                            "message": "Forbidden.",
                            "correlation_id": correlation_id,
                            "occurred_at_utc": app.state.clock(),
                            "details": {"code": "PolicyDenied"},
                        }
                    },
                )

            correlation_id = _audit(
                app,
                action="policy.enforce",
                outcome="success",
                occurred_at_utc=app.state.clock(),
                entity_id=product_id,
            )
            return JSONResponse(status_code=200, content={"status": "ok", "correlation_id": correlation_id})

        # --- Gate evaluation negative (OpenAPI V2 path) ---
        @app.post("/v2/drafts/{draft_id}/gates/evaluate", status_code=200)
        async def evaluate_gates(draft_id: str, payload: Dict[str, Any]) -> JSONResponse:
            # Deterministic "negative scenario trigger" purely for tests.
            scenario = payload.get("scenario")
            stage = payload.get("stage", "validate")

            if scenario == "freshness_failed":
                correlation_id = _audit(
                    app,
                    action="gate.freshness",
                    outcome="failure",
                    occurred_at_utc=app.state.clock(),
                    entity_id=draft_id,
                    error_code="FreshnessCheckFailed",
                    error_message="Freshness gate failed.",
                    details_json='{"metric":{"expected":24,"observed":72}}',
                )
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "FreshnessCheckFailed",
                            "http_status": 422,
                            "message": "Freshness gate failed: latest record is older than max_age.",
                            "correlation_id": correlation_id,
                            "occurred_at_utc": app.state.clock(),
                            "details": {
                                "stage": stage,
                                "failing_gates": [
                                    {
                                        "gate_id": "freshness",
                                        "gate_name": "Freshness check against max_age SLO",
                                        "status": "FAIL",
                                        "severity": "BLOCK",
                                        "metric": {
                                            "name": "max_age_hours",
                                            "expected": 24,
                                            "observed": 72,
                                            "comparator": "<=",
                                        },
                                    }
                                ],
                                "evidence_refs": [{"artifact_type": "QualityReport", "artifact_id": "qr_test"}],
                            },
                        }
                    },
                )

            if scenario == "schema_failed":
                correlation_id = _audit(
                    app,
                    action="gate.schema",
                    outcome="failure",
                    occurred_at_utc=app.state.clock(),
                    entity_id=draft_id,
                    error_code="SchemaConformanceFailed",
                    error_message="Schema conformance gate failed.",
                )
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "GateComplianceFailed",
                            "http_status": 422,
                            "message": "One or more mandatory gates failed.",
                            "correlation_id": correlation_id,
                            "occurred_at_utc": app.state.clock(),
                            "details": {
                                "stage": stage,
                                "failing_gates": [
                                    {
                                        "gate_id": "schema",
                                        "gate_name": "Schema validation and conformance",
                                        "status": "FAIL",
                                        "severity": "BLOCK",
                                        "message": "Unknown field 'patient_zip' is not allowed in strict mode.",
                                    }
                                ],
                                "references": {"code": "SchemaConformanceFailed"},
                            },
                        }
                    },
                )

            if scenario == "gxp_baseline_failed":
                rule_pack_id = "GXP-RULEPACK-global-baseline-2b2a2f61-0f56-4c20-93a2-9b9cf2a1c0c1"
                correlation_id = _audit(
                    app,
                    action="gate.gxp",
                    outcome="failure",
                    occurred_at_utc=app.state.clock(),
                    entity_id=draft_id,
                    error_code="GateComplianceFailed",
                    error_message="GxP baseline gate failed.",
                    details_json=f'{{"rule_pack_id":"{rule_pack_id}"}}',
                )
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "GateComplianceFailed",
                            "http_status": 422,
                            "message": "One or more mandatory gates failed.",
                            "correlation_id": correlation_id,
                            "occurred_at_utc": app.state.clock(),
                            "details": {
                                "stage": stage,
                                "failing_gates": [
                                    {
                                        "gate_id": "schema",
                                        "gate_name": "Schema validation and conformance",
                                        "status": "FAIL",
                                        "severity": "BLOCK",
                                        "rule_ref": {"rule_pack_id": rule_pack_id, "rule_pack_version": "1.0.0"},
                                    }
                                ],
                                "references": [{"type": "rule_pack", "id": rule_pack_id}],
                            },
                        }
                    },
                )

            # Default success
            correlation_id = _audit(
                app,
                action="gate.evaluate",
                outcome="success",
                occurred_at_utc=app.state.clock(),
                entity_id=draft_id,
            )
            return JSONResponse(
                status_code=200,
                content={"stage": stage, "status": "PASS", "evaluated_gates": [], "correlation_id": correlation_id},
            )

        # Provide an audit listing endpoint (OpenAPI has /v2/audit-log)
        @app.get("/v2/audit-log", status_code=200)
        async def list_audit() -> Dict[str, Any]:
            return {"items": app.state.audit_repo.list_events()}

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
