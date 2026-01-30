"""
Draft registration / submission services.

Current tests focus on draft creation and duplicate detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.errors import ConflictError
from src.schemas import CreateDraftRequest


@dataclass
class DraftsService:
    """Drafts service handling registration flows."""

    registration_repo: Any
    clock: Any

    # PUBLIC_INTERFACE
    def create_draft(self, req: CreateDraftRequest) -> dict:
        """Create a new draft and return response dict."""
        draft_id = f"draft_{uuid4().hex[:8]}"
        # Delegate duplicate check to repo contract used by tests.
        try:
            self.registration_repo.create_draft(
                {"draft_id": draft_id, "product_name": req.product_name, "version": req.version or "v1.0"}
            )
        except ValueError as e:
            if str(e) == "DuplicateResource":
                raise ConflictError(
                    "Duplicate resource.",
                    details={"error_code": "DuplicateResource"},
                )
            raise

        return {
            "draft_id": draft_id,
            "status": "DRAFT",
            "product_name": req.product_name,
            "classification": req.classification,
            "created_at_utc": self.clock(),
        }
