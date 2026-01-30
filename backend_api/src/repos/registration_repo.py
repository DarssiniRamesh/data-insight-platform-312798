"""
Registration repository implementations.

This module provides a SQLModel-backed registration repository used by the FastAPI
app factory as a default implementation for non-test/runtime deployments.

The DraftsService expects the repository contract:
- create_draft(draft: dict) -> dict
  - raises ValueError("DuplicateResource") if product_name+version already exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from src.db import DEFAULT_ENGINE
from src.models import Draft


@dataclass
class SQLRegistrationRepo:
    """
    SQLite/SQLModel-backed draft registration repository.

    Persists Draft rows in the `draft` table. Duplicate detection is performed on
    (product_name, version) to match test expectations.
    """

    engine: Any = DEFAULT_ENGINE

    def create_draft(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a draft.

        Raises:
            ValueError("DuplicateResource"): If a draft already exists for the same
                product_name+version.
        """
        product_name = draft["product_name"]
        version = draft.get("version", "v1.0")

        with Session(self.engine) as session:
            existing: Optional[Draft] = session.exec(
                select(Draft).where(Draft.product_name == product_name, Draft.version == version)
            ).first()
            if existing is not None:
                # Match tests' contract used by DraftsService.
                raise ValueError("DuplicateResource")

            obj = Draft(
                draft_id=draft["draft_id"],
                product_name=product_name,
                version=version,
                # Persist minimal fields; response fields are assembled by service layer.
                classification=draft.get("classification", "Internal"),
                status=draft.get("status", "DRAFT"),
                created_at_utc=draft.get("created_at_utc", ""),
                updated_at_utc=draft.get("updated_at_utc"),
            )
            session.add(obj)
            session.commit()

        return draft


# PUBLIC_INTERFACE
def create_default_registration_repo() -> SQLRegistrationRepo:
    """Create the default registration repository used for runtime deployments."""
    return SQLRegistrationRepo()
