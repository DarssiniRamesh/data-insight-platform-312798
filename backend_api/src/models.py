"""
SQLModel models used by the publishing workflow.

Only the subset required by the current test-suite is implemented (Drafts, Policies, AuditLog).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import SQLModel, Field


class Draft(SQLModel, table=True):
    """Draft record for a data product registration."""

    draft_id: str = Field(primary_key=True)
    product_name: str = Field(index=True)
    version: str = Field(default="v1.0", index=True)

    status: str = Field(default="DRAFT", index=True)
    classification: str

    created_at_utc: str
    updated_at_utc: Optional[str] = None

    # Minimal fields to align with CreateDraftRequest shape (not exhaustively persisted for tests)
    schema_id: Optional[str] = None
    schema_version: Optional[str] = None
    dataset_uri: Optional[str] = None
    dataset_format: Optional[str] = None
    max_age_hours: Optional[int] = None
    update_frequency: Optional[str] = None


class AccessPolicy(SQLModel, table=True):
    """Role-based access grant for a product id."""

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: str = Field(index=True)
    role: str = Field(index=True)


class AuditLogEvent(SQLModel, table=True):
    """
    Audit log events.

    Note: tests assert against app.state.audit_repo, but we also provide a SQL-backed repository to
    support real persistence in non-test runs.
    """

    event_id: str = Field(primary_key=True)
    action: str
    entity_id: Optional[str] = None
    correlation_id: str
    outcome: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    occurred_at_utc: str
    details_json: Optional[str] = None
