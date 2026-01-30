"""
Access policy endpoints (test-driven; not part of OpenAPI v2 YAML).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.deps import get_audit_repo, get_clock, get_policy_repo
from src.errors import ConflictError
from src.schemas import ApiError, GrantPolicyRequest
from src.services.audit_service import AuditService
from src.services.policies_service import PoliciesService

router = APIRouter(prefix="/v2", tags=["Policies"])


@router.post("/policies/grant", status_code=200, responses={400: {"model": ApiError}, 409: {"model": ApiError}})
async def grant_policy(
    payload: dict,
    audit_repo=Depends(get_audit_repo),
    clock=Depends(get_clock),
    policy_repo=Depends(get_policy_repo),
):
    """Grant a role-based policy for a product."""
    audit = AuditService(audit_repo=audit_repo, clock=clock)
    svc = PoliciesService(policy_repo=policy_repo)

    try:
        req = GrantPolicyRequest.model_validate(payload)
    except ValidationError:
        correlation_id = audit.log(
            action="policy.grant",
            outcome="failure",
            error_code="InvalidInput",
            error_message="Missing product_id or role.",
            details={"validation_path": "body"},
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "InvalidInput",
                    "http_status": 400,
                    "message": "Request payload is invalid.",
                    "correlation_id": correlation_id,
                    "occurred_at_utc": clock(),
                    "details": {"validation_path": "body"},
                }
            },
        )

    try:
        svc.grant(product_id=req.product_id, role=req.role)
    except ConflictError as ce:
        correlation_id = audit.log(
            action="policy.grant",
            outcome="failure",
            entity_id=req.product_id,
            error_code="PolicyConflict",
            error_message="Policy already exists for this role.",
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "Conflict",
                    "http_status": 409,
                    "message": "Policy conflict.",
                    "correlation_id": correlation_id,
                    "occurred_at_utc": clock(),
                    "details": ce.details or {"error_code": "PolicyConflict"},
                }
            },
        )

    correlation_id = audit.log(action="policy.grant", outcome="success", entity_id=req.product_id)
    return JSONResponse(status_code=200, content={"status": "ok", "correlation_id": correlation_id})


@router.post("/protected/operation", status_code=200, responses={403: {"model": ApiError}})
async def protected_operation(
    x_role: str | None = Header(default=None),
    audit_repo=Depends(get_audit_repo),
    clock=Depends(get_clock),
    policy_repo=Depends(get_policy_repo),
):
    """A deny-by-default protected operation used in tests."""
    audit = AuditService(audit_repo=audit_repo, clock=clock)
    svc = PoliciesService(policy_repo=policy_repo)

    product_id = "product_protected_001"
    role = x_role or "anonymous"

    if not svc.has_access(product_id=product_id, role=role):
        correlation_id = audit.log(
            action="policy.enforce",
            outcome="failure",
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
                    "occurred_at_utc": clock(),
                    "details": {"code": "PolicyDenied"},
                }
            },
        )

    correlation_id = audit.log(action="policy.enforce", outcome="success", entity_id=product_id)
    return JSONResponse(status_code=200, content={"status": "ok", "correlation_id": correlation_id})
