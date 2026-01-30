"""
Domain errors and helpers to map them to OpenAPI-shaped responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class DomainError(Exception):
    """Base domain error."""

    code: str
    message: str
    http_status: int
    details: Optional[Dict[str, Any]] = None


@dataclass
class InvalidInputError(DomainError):
    """400 invalid input."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(code="InvalidInput", message=message, http_status=400, details=details)


@dataclass
class ConflictError(DomainError):
    """409 conflict."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(code="Conflict", message=message, http_status=409, details=details)


@dataclass
class ForbiddenError(DomainError):
    """403 forbidden (policy denied)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(code="Forbidden", message=message, http_status=403, details=details)


@dataclass
class GateFailureDomainError(DomainError):
    """422 gate failures."""

    def __init__(self, code: str, message: str, details: Dict[str, Any]):
        super().__init__(code=code, message=message, http_status=422, details=details)


@dataclass
class InternalServerError(DomainError):
    """500 internal error wrapper."""

    def __init__(self, message: str = "An unexpected error occurred.", details: Optional[Dict[str, Any]] = None):
        super().__init__(code="InternalServerError", message=message, http_status=500, details=details)
