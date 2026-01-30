"""
Audit logging service.

Tests assert that `app.state.audit_repo` exists and receives events with:
action, entity_id, correlation_id, outcome, error_code, error_message, occurred_at_utc, details_json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from uuid import uuid4


@dataclass
class AuditService:
    """Service responsible for writing audit events synchronously."""

    audit_repo: Any
    clock: Callable[[], str]

    # PUBLIC_INTERFACE
    def log(
        self,
        *,
        action: str,
        outcome: str,
        entity_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create an audit event and return its correlation_id."""
        correlation_id = str(uuid4())
        event = {
            "event_id": str(uuid4()),
            "action": action,
            "entity_id": entity_id,
            "correlation_id": correlation_id,
            "outcome": outcome,
            "error_code": error_code,
            "error_message": error_message,
            "occurred_at_utc": self.clock(),
            "details_json": json.dumps(details) if details is not None else None,
        }
        self.audit_repo.create_event(event)
        return correlation_id
