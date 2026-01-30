"""
FastAPI application factory for the backend_api service.

Tests should construct the app using this factory and then inject/override:
- app.state.audit_repo
- app.state.registration_repo
- app.state.policy_repo
- app.state.collibra_adapter
- app.state.immuta_adapter
- app.state.clock
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import audit as audit_router
from src.api.routers import drafts as drafts_router
from src.api.routers import gates as gates_router
from src.api.routers import integrations as integrations_router
from src.api.routers import policies as policies_router
from src.db import init_db
from src.errors import DomainError, InternalServerError
from src.repos.audit_repo import create_default_audit_repo
from src.repos.policy_repo import create_default_policy_repo
from src.repos.registration_repo import create_default_registration_repo


def _default_clock() -> str:
    """
    Return current UTC time in ISO 8601 format.

    Uses datetime.timezone.utc (instead of datetime.UTC) for compatibility across
    Python versions used in different preview/CI environments.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# PUBLIC_INTERFACE
def create_app(
    *,
    init_sqlite: bool = True,
    audit_repo: Optional[Any] = None,
    registration_repo: Optional[Any] = None,
    policy_repo: Optional[Any] = None,
    collibra_adapter: Optional[Any] = None,
    immuta_adapter: Optional[Any] = None,
    clock: Optional[Callable[[], str]] = None,
) -> FastAPI:
    """
    Create and configure the FastAPI app.

    Parameters:
      - init_sqlite: if True, create tables on startup (safe for SQLite).
      - audit_repo/registration_repo/policy_repo/collibra_adapter/immuta_adapter/clock:
        optional initial wiring for app.state (tests commonly override these).

    Returns:
      - Configured FastAPI application.
    """
    app = FastAPI(
        title="Data Product Publishing Workflow API (V2)",
        version="2.0.0",
        description="Minimal implementation to satisfy V2 tests and align with the OpenAPI contract.",
        openapi_tags=[
            {"name": "Drafts", "description": "Submission and draft lifecycle."},
            {"name": "Gating", "description": "Evaluate gate compliance and gate decisions (blocking failures)."},
            {"name": "Audit", "description": "Audit trail access (append-only conceptually)."},
            {"name": "Integrations", "description": "Mockable integration touchpoints (test-driven)."},
            {"name": "Policies", "description": "Access policies (test-driven)."},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Persist init flag on app.state so the startup hook can reference it.
    app.state.init_sqlite = init_sqlite

    def _ensure_default_wiring() -> None:
        """
        Ensure all required app.state dependencies exist.

        Important: This function never overwrites already-configured values on app.state,
        so tests can safely set app.state.* after create_app() returns (before startup runs).
        """
        if audit_repo is not None and getattr(app.state, "audit_repo", None) is None:
            app.state.audit_repo = audit_repo
        if getattr(app.state, "audit_repo", None) is None:
            # Safe default so endpoints depending on get_audit_repo don't 500 at runtime.
            app.state.audit_repo = create_default_audit_repo()

        if registration_repo is not None and getattr(app.state, "registration_repo", None) is None:
            app.state.registration_repo = registration_repo
        if getattr(app.state, "registration_repo", None) is None:
            app.state.registration_repo = create_default_registration_repo()

        if policy_repo is not None and getattr(app.state, "policy_repo", None) is None:
            app.state.policy_repo = policy_repo
        if getattr(app.state, "policy_repo", None) is None:
            app.state.policy_repo = create_default_policy_repo()

        if collibra_adapter is not None and getattr(app.state, "collibra_adapter", None) is None:
            app.state.collibra_adapter = collibra_adapter
        if immuta_adapter is not None and getattr(app.state, "immuta_adapter", None) is None:
            app.state.immuta_adapter = immuta_adapter

        if clock is not None and getattr(app.state, "clock", None) is None:
            app.state.clock = clock
        if getattr(app.state, "clock", None) is None:
            app.state.clock = _default_clock

    # Ensure defaults are present immediately (so app.state exists for error handlers, etc.)
    _ensure_default_wiring()

    @app.on_event("startup")
    async def _startup_init() -> None:
        """
        Initialize persistence + confirm default wiring at service startup.

        This makes preview readiness more robust by ensuring:
        - tables exist before any request hits DB-backed repos
        - required repos are available even if a caller forgets to wire them
        """
        if getattr(app.state, "init_sqlite", False):
            init_db()
        _ensure_default_wiring()

    # Include routers
    app.include_router(drafts_router.router)
    app.include_router(gates_router.router)
    app.include_router(audit_router.router)
    app.include_router(integrations_router.router)
    app.include_router(policies_router.router)

    @app.get("/", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return {"message": "Healthy"}

    @app.get("/healthz", tags=["Health"])
    async def healthz():
        """Readiness/liveness probe endpoint used by the preview healthcheck."""
        return {"status": "ok"}

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        """Return OpenAPI-shaped error payload for domain errors."""
        correlation_id = None
        occurred_at = app.state.clock()
        try:
            audit_repo_local = getattr(app.state, "audit_repo", None)
            if audit_repo_local is not None:
                from src.services.audit_service import AuditService

                audit = AuditService(audit_repo=audit_repo_local, clock=app.state.clock)
                correlation_id = audit.log(
                    action="domain.error",
                    outcome="failure",
                    error_code=exc.code,
                    error_message=exc.message,
                    details=exc.details,
                )
        except Exception:
            correlation_id = correlation_id or None

        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.code,
                    "http_status": exc.http_status,
                    "message": exc.message,
                    "correlation_id": correlation_id,
                    "occurred_at_utc": occurred_at,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Catch-all exception handler returning InternalServerError and auditing."""
        err = InternalServerError(details={"exception": str(exc)})
        occurred_at = app.state.clock()

        correlation_id = None
        try:
            audit_repo_local = getattr(app.state, "audit_repo", None)
            if audit_repo_local is not None:
                from src.services.audit_service import AuditService

                audit = AuditService(audit_repo=audit_repo_local, clock=app.state.clock)
                correlation_id = audit.log(
                    action="internal.error",
                    outcome="failure",
                    error_code=err.code,
                    error_message=str(exc),
                    details=err.details,
                )
        except Exception:
            correlation_id = None

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "InternalServerError",
                    "http_status": 500,
                    "message": "An unexpected error occurred.",
                    "correlation_id": correlation_id,
                    "occurred_at_utc": occurred_at,
                    "details": {"exception": str(exc)},
                }
            },
        )

    return app
