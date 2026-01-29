from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import FastAPI


@dataclass(frozen=True)
class AuditEventExpectation:
    """Represents the expected audit event fields for assertions."""

    action: str
    outcome: str
    error_code: Optional[str] = None
    entity_id: Optional[str] = None


# PUBLIC_INTERFACE
def fetch_audit_events(app: FastAPI) -> list[Dict[str, Any]]:
    """Fetch all audit events from the app's audit repository."""
    return app.state.audit_repo.list_events()


# PUBLIC_INTERFACE
def assert_audit_event(
    app: FastAPI,
    expected: AuditEventExpectation,
) -> Dict[str, Any]:
    """
    Assert the latest audit log entry matches expectations and includes required fields.

    Required fields (per user request):
    action, entity_id (if available), correlation_id, outcome, error_code, error_message, timestamp.
    """
    events = fetch_audit_events(app)
    assert events, "Expected at least one audit event to be created."
    last = events[-1]

    assert last["action"] == expected.action
    assert last["outcome"] == expected.outcome

    # Ensure mandatory fields exist and are non-empty
    assert last["correlation_id"], "correlation_id must be present"
    assert last["occurred_at_utc"], "timestamp (occurred_at_utc) must be present"

    # These fields must exist (nullable allowed in schema, but tests want presence as keys)
    assert "entity_id" in last
    assert "error_code" in last
    assert "error_message" in last

    if expected.entity_id is not None:
        assert last["entity_id"] == expected.entity_id

    if expected.error_code is not None:
        assert last["error_code"] == expected.error_code

    return last
