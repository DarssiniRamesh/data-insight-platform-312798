"""
Schema stubs for TDD.

These models exist solely so tests can use typed payload builders without importing
the (not-yet-implemented) real application models.

TODO (implementation): Replace usages with real schemas from backend_api/src.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SchemaRef(BaseModel):
    schema_id: str = Field(..., description="Schema identifier")
    schema_version: str = Field(..., description="Schema semantic version")


class DatasetRef(BaseModel):
    uri: str = Field(..., description="Dataset location URI")
    format: Optional[str] = Field(None, description="Dataset format, e.g. csv")


class CreateDraftRequest(BaseModel):
    # Aligns with OpenAPI CreateDraftRequest schema fields
    product_name: str = Field(..., description="Human name of the data product")
    classification: str = Field(..., description="Data classification")
    schema_ref: SchemaRef
    dataset_ref: DatasetRef
    update_frequency: Optional[str] = None
    max_age_hours: Optional[int] = None
    lineage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class PublishCollibraRequest(BaseModel):
    draft_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class RegisterImmutaRequest(BaseModel):
    draft_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class GrantPolicyRequest(BaseModel):
    product_id: str
    role: str
