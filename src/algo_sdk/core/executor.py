from __future__ import annotations

from typing import Protocol

from .metadata import AlgorithmSpec


class ExecutionResult:
    """Placeholder for execution result metadata."""

    def __init__(self, *, success: bool, error: str | None = None) -> None:
        self.success = success
        self.error = error


class Executor(Protocol):
    """Contract placeholder for executing registered algorithms."""

    def submit(self, spec: AlgorithmSpec, payload: object) -> ExecutionResult: ...
