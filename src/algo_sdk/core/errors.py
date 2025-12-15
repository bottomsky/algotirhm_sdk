from __future__ import annotations

from typing import Optional


class AlgorithmError(Exception):
    """Base exception for algorithm SDK errors."""

    def __init__(self, message: str, *, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code


class AlgorithmRegistrationError(AlgorithmError):
    """Raised when an algorithm fails to register or conflicts with an existing entry."""


class AlgorithmNotFoundError(AlgorithmError):
    """Raised when lookup for an algorithm name/version pair fails."""


class AlgorithmValidationError(AlgorithmError):
    """Raised when algorithm signature or schema validation fails."""
