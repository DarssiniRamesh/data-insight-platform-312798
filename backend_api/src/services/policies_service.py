"""
Access policy services.

Not in the V2 OpenAPI spec, but required by current tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.errors import ConflictError


@dataclass
class PoliciesService:
    """Access policies service (role-based grants)."""

    policy_repo: Any

    # PUBLIC_INTERFACE
    def grant(self, *, product_id: str, role: str) -> None:
        """Grant access for a role to a product_id."""
        try:
            self.policy_repo.grant(product_id=product_id, role=role)
        except ValueError as e:
            if str(e) == "PolicyConflict":
                raise ConflictError("Policy conflict.", details={"error_code": "PolicyConflict"})
            raise

    # PUBLIC_INTERFACE
    def has_access(self, *, product_id: str, role: str) -> bool:
        """Check if role has access to product_id."""
        return self.policy_repo.has_access(product_id=product_id, role=role)
