"""
External integration adapter interfaces.

Tests override these adapters using FastAPI dependency overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, Tuple


class CollibraAdapter(Protocol):
    """Protocol for Collibra integration touchpoints."""

    def publish_metadata(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Publish metadata to Collibra; return (ok, details)."""


class ImmutaAdapter(Protocol):
    """Protocol for Immuta integration touchpoints."""

    def register_dataset(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Register a dataset/policy in Immuta; return (ok, details)."""


@dataclass
class NoopCollibraAdapter:
    """Default adapter used outside tests."""

    calls: List[Dict[str, Any]] = field(default_factory=list)

    def publish_metadata(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        self.calls.append({"method": "publish_metadata", "payload": payload})
        return True, {"message": "ok"}


@dataclass
class NoopImmutaAdapter:
    """Default adapter used outside tests."""

    calls: List[Dict[str, Any]] = field(default_factory=list)

    def register_dataset(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        self.calls.append({"method": "register_dataset", "payload": payload})
        return True, {"message": "ok"}
