"""
Audit endpoints per OpenAPI (subset).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_audit_repo

router = APIRouter(prefix="/v2", tags=["Audit"])


@router.get("/audit-log", status_code=200, summary="List audit log events (read-only)")
async def list_audit_events(audit_repo=Depends(get_audit_repo)):
    """Return audit events as an object with `items` list."""
    return {"items": audit_repo.list_events()}
