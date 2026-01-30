"""
Drafts router for V2 endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.deps import get_audit_repo, get_clock, get_registration_repo
from src.errors import ConflictError
from src.schemas import ApiError, CreateDraftRequest, DraftResponse
from src.services.audit_service import AuditService
from src.services.drafts_service import DraftsService

router = APIRouter(prefix="/v2", tags=["Drafts"])


@router.post(
    "/drafts",
    status_code=201,
    response_model=DraftResponse,
    responses={
        400: {"model": ApiError},
        409: {"model": ApiError},
        500: {"model": ApiError},
    },
    summary="Create a draft data product record (metadata + dataset reference)",
)
async def create_draft(
    payload: dict,
    audit_repo=Depends(get_audit_repo),
    clock=Depends(get_clock),
    registration_repo=Depends(get_registration_repo),
):
    """
    Create a draft record.

    Parameters:
      - payload: CreateDraftRequest JSON body

    Returns:
      - 201 DraftResponse on success
      - 400 ApiError (InvalidInput)
      - 409 ApiError (Conflict w/ DuplicateResource)
    """
    audit = AuditService(audit_repo=audit_repo, clock=clock)
    svc = DraftsService(registration_repo=registration_repo, clock=clock)

    try:
        req = CreateDraftRequest.model_validate(payload)
    except ValidationError as ve:
        msg = f"validation error: {ve.errors()}"
        correlation_id = audit.log(
            action="register",
            outcome="failure",
            error_code="InvalidInput",
            error_message=msg,
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
        created = svc.create_draft(req)
    except ConflictError as ce:
        # Tests expect error.code == Conflict and details.error_code == DuplicateResource
        correlation_id = audit.log(
            action="register",
            outcome="failure",
            error_code="DuplicateResource",
            error_message="Duplicate name/version.",
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "Conflict",
                    "http_status": 409,
                    "message": "Duplicate resource.",
                    "correlation_id": correlation_id,
                    "occurred_at_utc": clock(),
                    "details": ce.details or {"error_code": "DuplicateResource"},
                }
            },
        )

    correlation_id = audit.log(
        action="register",
        outcome="success",
        entity_id=created["draft_id"],
    )
    created["correlation_id"] = correlation_id
    return JSONResponse(status_code=201, content=created)
