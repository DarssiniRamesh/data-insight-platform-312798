"""
FastAPI dependencies.

Tests can override these dependencies using `app.dependency_overrides[...]`.
For compatibility with existing tests, we also fall back to `request.app.state.*` when available.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Request

from src.adapters import NoopCollibraAdapter, NoopImmutaAdapter


# PUBLIC_INTERFACE
def get_clock(request: Request) -> Callable[[], str]:
    """Get the app clock function (UTC ISO string)."""
    clock = getattr(request.app.state, "clock", None)
    if clock is None:
        # Default to an ISO-like string; tests override this.
        import datetime

        return lambda: datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    return clock


# PUBLIC_INTERFACE
def get_audit_repo(request: Request) -> Any:
    """Get the audit repository."""
    repo = getattr(request.app.state, "audit_repo", None)
    if repo is None:
        raise RuntimeError("audit_repo not configured on app.state")
    return repo


# PUBLIC_INTERFACE
def get_registration_repo(request: Request) -> Any:
    """Get registration repository (draft duplicate detection)."""
    repo = getattr(request.app.state, "registration_repo", None)
    if repo is None:
        raise RuntimeError("registration_repo not configured on app.state")
    return repo


# PUBLIC_INTERFACE
def get_policy_repo(request: Request) -> Any:
    """Get access policy repository."""
    repo = getattr(request.app.state, "policy_repo", None)
    if repo is None:
        raise RuntimeError("policy_repo not configured on app.state")
    return repo


# PUBLIC_INTERFACE
def get_collibra_adapter(request: Request) -> Any:
    """Get Collibra adapter."""
    adapter = getattr(request.app.state, "collibra_adapter", None)
    return adapter or NoopCollibraAdapter()


# PUBLIC_INTERFACE
def get_immuta_adapter(request: Request) -> Any:
    """Get Immuta adapter."""
    adapter = getattr(request.app.state, "immuta_adapter", None)
    return adapter or NoopImmutaAdapter()
