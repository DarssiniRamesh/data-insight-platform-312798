"""
Integration orchestration.

Not part of the V2 OpenAPI spec, but required by current tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from src.errors import ForbiddenError, GateFailureDomainError


@dataclass
class IntegrationsService:
    """Service layer for external integration touchpoints."""

    collibra: Any
    immuta: Any

    # PUBLIC_INTERFACE
    def publish_collibra(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Publish metadata to Collibra."""
        return self.collibra.publish_metadata(payload)

    # PUBLIC_INTERFACE
    def register_immuta(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Register dataset/policy in Immuta."""
        return self.immuta.register_dataset(payload)

    # PUBLIC_INTERFACE
    def map_collibra_failure(self, message: str) -> GateFailureDomainError:
        """Map Collibra validation failures to a generic GateComplianceFailed error."""
        return GateFailureDomainError(
            code="GateComplianceFailed",
            message="Collibra integration gate failed.",
            details={"code": "CollibraValidationFailed", "message": message},
        )

    # PUBLIC_INTERFACE
    def map_immuta_denial(self, message: str) -> ForbiddenError:
        """Map Immuta denials to a Forbidden error used by tests."""
        return ForbiddenError(
            "Denied by policy.",
            details={"code": "PolicyDenied", "message": message},
        )
