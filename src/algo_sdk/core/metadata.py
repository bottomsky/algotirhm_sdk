from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type, TypeVar

from .base_model_impl import BaseModel
from .lifecycle import AlgorithmLifecycle

Req = TypeVar("Req", bound=BaseModel)
Resp = TypeVar("Resp", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Desired execution hints recorded with the algorithm."""

    isolated_pool: bool = False
    max_workers: Optional[int] = None
    timeout_s: Optional[int] = None
    gpu: Optional[str] = None


@dataclass(slots=True)
class AlgorithmSpec:
    """Metadata for an algorithm entry."""

    name: str
    version: str
    description: Optional[str]
    input_model: Type[Req]
    output_model: Type[Resp]
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    entrypoint: Callable[[Req], Resp] | Type[AlgorithmLifecycle[Req, Resp]]
    is_class: bool = False

    def key(self) -> tuple[str, str]:
        return self.name, self.version
