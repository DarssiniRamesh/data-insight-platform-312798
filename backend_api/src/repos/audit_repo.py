"""
Audit repository implementations.

This module provides a SQLModel-backed audit repository used by the FastAPI app factory
as a default implementation for non-test/runtime deployments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from src.db import DEFAULT_ENGINE
from src.models import AuditLogEvent


@dataclass
class SQLAuditLogRepo:
    """
    SQLite/SQLModel-backed audit log repository.

    This repository stores audit events in the `auditlogevent` table (derived from the
    SQLModel `AuditLogEvent` model) and supports the minimal interface expected by the app:
    - create_event(event: dict) -> None
    - list_events() -> list[dict]
    """

    engine: Any = DEFAULT_ENGINE

    def create_event(self, event: Dict[str, Any]) -> None:
        """Persist a single audit log event."""
        obj = AuditLogEvent(
            event_id=event["event_id"],
            action=event["action"],
            entity_id=event.get("entity_id"),
            correlation_id=event["correlation_id"],
            outcome=event["outcome"],
            error_code=event.get("error_code"),
            error_message=event.get("error_message"),
            occurred_at_utc=event["occurred_at_utc"],
            details_json=event.get("details_json"),
        )
        with Session(self.engine) as session:
            session.add(obj)
            session.commit()

    def list_events(self) -> List[Dict[str, Any]]:
        """Return all persisted events ordered by insertion."""
        with Session(self.engine) as session:
            events: List[AuditLogEvent] = list(session.exec(select(AuditLogEvent)))

        # Shape matches what tests/assertions expect from audit_repo.list_events()
        return [
            {
                "event_id": e.event_id,
                "action": e.action,
                "entity_id": e.entity_id,
                "correlation_id": e.correlation_id,
                "outcome": e.outcome,
                "error_code": e.error_code,
                "error_message": e.error_message,
                "occurred_at_utc": e.occurred_at_utc,
                "details_json": e.details_json,
            }
            for e in events
        ]


# PUBLIC_INTERFACE
def create_default_audit_repo() -> SQLAuditLogRepo:
    """Create the default audit repository used for runtime deployments."""
    return SQLAuditLogRepo()
