from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from .base_model_impl import BaseModel
from .lifecycle import AlgorithmLifecycleProtocol

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class ExecutionMode(Enum):
    PROCESS_POOL = "process_pool"
    IN_PROCESS = "in_process"


class AlgorithmType(str, Enum):
    PLANNING = "Planning"
    PREPARE = "Prepare"
    PRECITION = "Precition"


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Desired execution hints recorded with the algorithm."""

    execution_mode: ExecutionMode = ExecutionMode.PROCESS_POOL
    stateful: bool = False
    isolated_pool: bool = False
    max_workers: int | None = None
    timeout_s: int | None = None
    gpu: str | None = None


@dataclass(slots=True)
class AlgorithmSpec(Generic[TInput, TOutput]):
    """Metadata for an algorithm entry."""

    name: str
    version: str
    description: str | None
    input_model: type[TInput]
    output_model: type[TOutput]
    entrypoint: Callable[[TInput],
                         TOutput] | type[AlgorithmLifecycleProtocol[TInput,
                                                                    TOutput]]
    algorithm_type: AlgorithmType = AlgorithmType.PRECITION
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
