from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from .base_model_impl import BaseModel
from .lifecycle import AlgorithmLifecycle

Req = TypeVar("Req", bound=BaseModel)
Resp = TypeVar("Resp", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Desired execution hints recorded with the algorithm."""

    isolated_pool: bool = False
    max_workers: int | None = None
    timeout_s: int | None = None
    gpu: str | None = None


@dataclass(slots=True)
class AlgorithmSpec(Generic[Req, Resp]):
    """Metadata for an algorithm entry."""

    name: str
    version: str
    description: str | None
    input_model: type[Req]
    output_model: type[Resp]
    entrypoint: Callable[[Req], Resp] | type[AlgorithmLifecycle[Req, Resp]]
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    is_class: bool = False

    def key(self) -> tuple[str, str]:
        return self.name, self.version

    def input_schema(self) -> dict[str, Any]:
        """Return JSON schema for the input model."""
        return self.input_model.model_json_schema()

    def output_schema(self) -> dict[str, Any]:
        """Return JSON schema for the output model."""
        return self.output_model.model_json_schema()
