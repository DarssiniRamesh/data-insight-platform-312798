"""
Integration endpoints.

These are test-driven endpoints (not present in the OpenAPI v2 YAML) to verify that integration
adapters are DI-replaceable and audited.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.deps import get_audit_repo, get_clock, get_collibra_adapter, get_immuta_adapter
from src.errors import ForbiddenError, GateFailureDomainError
from src.schemas import ApiError, PublishCollibraRequest, RegisterImmutaRequest
from src.services.audit_service import AuditService
from src.services.integrations_service import IntegrationsService

router = APIRouter(prefix="/v2", tags=["Integrations"])


@router.post("/integrations/collibra/publish", status_code=200, responses={422: {"model": ApiError}, 400: {"model": ApiError}})
async def publish_collibra(
    payload: dict,
    audit_repo=Depends(get_audit_repo),
    clock=Depends(get_clock),
    collibra=Depends(get_collibra_adapter),
):
    """Publish metadata to Collibra (mockable)."""
    audit = AuditService(audit_repo=audit_repo, clock=clock)
    svc = IntegrationsService(collibra=collibra, immuta=None)

    try:
        req = PublishCollibraRequest.model_validate(payload)
    except ValidationError as ve:
        correlation_id = audit.log(
            action="integrate.collibra",
            outcome="failure",
            error_code="InvalidInput",
            error_message=f"validation error: {ve.errors()}",
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

    ok, details = svc.publish_collibra(req.model_dump())
    if ok:
        correlation_id = audit.log(
            action="integrate.collibra",
            outcome="success",
            entity_id=req.draft_id,
        )
        return JSONResponse(status_code=200, content={"status": "ok", "correlation_id": correlation_id})

    err: GateFailureDomainError = svc.map_collibra_failure(details.get("message", "Collibra validation failed."))
    correlation_id = audit.log(
        action="integrate.collibra",
        outcome="failure",
        entity_id=req.draft_id,
        error_code="CollibraValidationFailed",
        error_message=details.get("message", "Collibra validation failed."),
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": err.code,
                "http_status": 422,
                "message": err.message,
                "correlation_id": correlation_id,
                "occurred_at_utc": clock(),
                "details": {"code": "CollibraValidationFailed"},
            }
        },
    )


@router.post("/integrations/immuta/register", status_code=200, responses={403: {"model": ApiError}, 400: {"model": ApiError}})
async def register_immuta(
    payload: dict,
    audit_repo=Depends(get_audit_repo),
    clock=Depends(get_clock),
    immuta=Depends(get_immuta_adapter),
):
    """Register dataset/policy in Immuta (mockable)."""
    audit = AuditService(audit_repo=audit_repo, clock=clock)
    svc = IntegrationsService(collibra=None, immuta=immuta)

    try:
        req = RegisterImmutaRequest.model_validate(payload)
    except ValidationError as ve:
        correlation_id = audit.log(
            action="integrate.immuta",
            outcome="failure",
            error_code="InvalidInput",
            error_message=f"validation error: {ve.errors()}",
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

    ok, details = svc.register_immuta(req.model_dump())
    if ok:
        correlation_id = audit.log(action="integrate.immuta", outcome="success", entity_id=req.draft_id)
        return JSONResponse(status_code=200, content={"status": "ok", "correlation_id": correlation_id})

    err: ForbiddenError = svc.map_immuta_denial(details.get("message", "Denied by policy."))
    correlation_id = audit.log(
        action="integrate.immuta",
        outcome="failure",
        entity_id=req.draft_id,
        error_code="PolicyDenied",
        error_message=details.get("message", "Denied by policy."),
    )
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": err.code,
                "http_status": 403,
                "message": err.message,
                "correlation_id": correlation_id,
                "occurred_at_utc": clock(),
                "details": {"code": "PolicyDenied"},
            }
        },
    )
