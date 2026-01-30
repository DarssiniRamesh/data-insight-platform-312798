"""
Pydantic schemas aligned with the OpenAPI V2 contract (subset required by current tests).

The tests focus on:
- POST /v2/drafts
- POST /v2/drafts/{draft_id}/gates/evaluate (negative scenarios)
- Integration endpoints (collibra/immuta) + access policies (not in OpenAPI, but required by tests)
- Audit logging shape
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class SchemaRef(BaseModel):
    schema_id: str = Field(..., description="Schema identifier")
    schema_version: str = Field(..., description="Schema semantic version")


class DatasetRef(BaseModel):
    uri: str = Field(..., description="Dataset location URI")
    format: Optional[str] = Field(None, description="Dataset format, e.g. csv")


class CreateDraftRequest(BaseModel):
    product_name: str = Field(..., description="Human name of the data product")
    classification: Literal["Public", "Internal", "Confidential", "Regulated"] = Field(
        ..., description="Data classification used by governance rules."
    )
    schema_ref: SchemaRef
    dataset_ref: DatasetRef
    update_frequency: Optional[str] = None
    max_age_hours: Optional[int] = Field(None, ge=0)
    lineage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    version: Optional[str] = Field(default="v1.0", description="Draft version string.")


class DraftResponse(BaseModel):
    draft_id: str
    status: str
    product_name: str
    classification: str
    created_at_utc: str
    correlation_id: str


class EvaluateGatesRequest(BaseModel):
    stage: Literal["validate", "approve", "publish"] = Field(...)
    # Test-only field used to deterministically trigger negative scenarios.
    scenario: Optional[str] = Field(
        default=None,
        description="Test-only scenario selector; not part of the public contract.",
    )


class GateMetric(BaseModel):
    name: str
    expected: Optional[Union[float, int, str, bool]] = None
    observed: Optional[Union[float, int, str, bool]] = None
    comparator: Optional[str] = None


class RuleRef(BaseModel):
    rule_pack_id: Optional[str] = None
    rule_pack_version: Optional[str] = None
    rule_id: Optional[str] = None


class QualityGate(BaseModel):
    gate_id: str
    gate_name: str
    status: Literal["PASS", "FAIL", "WARN"]
    severity: Literal["BLOCK", "WARN", "INFO"]
    message: Optional[str] = None
    metric: Optional[GateMetric] = None
    rule_ref: Optional[RuleRef] = None


class EvidenceRef(BaseModel):
    artifact_type: str
    artifact_id: str
    evidence_key: Optional[str] = None
    hash_sha256: Optional[str] = None
    uri: Optional[str] = None


class GateFailureDetails(BaseModel):
    stage: Literal["validate", "approve", "publish"]
    failing_gates: List[QualityGate]
    evidence_refs: Optional[List[EvidenceRef]] = None
    # Some tests use `references` (legacy/compat). Keep it permissive.
    references: Optional[Any] = None


class ErrorBody(BaseModel):
    code: str
    http_status: int
    message: str
    correlation_id: Optional[str] = None
    occurred_at_utc: str
    details: Optional[Dict[str, Any]] = None


class ApiError(BaseModel):
    error: ErrorBody


class GateFailureError(BaseModel):
    error: ErrorBody


class PublishCollibraRequest(BaseModel):
    draft_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class RegisterImmutaRequest(BaseModel):
    draft_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class GrantPolicyRequest(BaseModel):
    product_id: str
    role: str
