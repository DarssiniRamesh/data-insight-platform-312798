"""
Policy repository implementations.

This module provides a SQLModel-backed policy repository used by the FastAPI app factory
as a default implementation for non-test/runtime deployments.

The PoliciesService expects the repository contract:
- grant(product_id: str, role: str) -> None
  - raises ValueError("PolicyConflict") if the same product_id+role already exists.
- has_access(product_id: str, role: str) -> bool
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session, select

from src.db import DEFAULT_ENGINE
from src.models import AccessPolicy


@dataclass
class SQLPolicyRepo:
    """SQLite/SQLModel-backed access policy repository."""

    engine: Any = DEFAULT_ENGINE

    def grant(self, product_id: str, role: str) -> None:
        """Grant access for a role to a product_id."""
        with Session(self.engine) as session:
            existing: Optional[AccessPolicy] = session.exec(
                select(AccessPolicy).where(AccessPolicy.product_id == product_id, AccessPolicy.role == role)
            ).first()
            if existing is not None:
                raise ValueError("PolicyConflict")

            obj = AccessPolicy(product_id=product_id, role=role)
            session.add(obj)
            session.commit()

    def has_access(self, product_id: str, role: str) -> bool:
        """Return True if role has access to product_id."""
        with Session(self.engine) as session:
            existing: Optional[AccessPolicy] = session.exec(
                select(AccessPolicy).where(AccessPolicy.product_id == product_id, AccessPolicy.role == role)
            ).first()
            return existing is not None


# PUBLIC_INTERFACE
def create_default_policy_repo() -> SQLPolicyRepo:
    """Create the default policy repository used for runtime deployments."""
    return SQLPolicyRepo()
