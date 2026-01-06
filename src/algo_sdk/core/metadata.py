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
    PROGRAMME = "Programme"
    PREPARE = "Prepare"
    PREDICTION = "Prediction"


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Desired execution hints recorded with the algorithm."""

    execution_mode: ExecutionMode = ExecutionMode.PROCESS_POOL
    stateful: bool = False
    isolated_pool: bool = False
    max_workers: int | None = None
    timeout_s: int | None = None
    gpu: str | None = None


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Logging configuration for algorithm payloads."""

    enabled: bool = False
    log_input: bool = False
    log_output: bool = False
    on_error_only: bool = False
    sample_rate: float = 1.0
    max_length: int = 2048
    redact_fields: tuple[str, ...] = field(default_factory=tuple)


class HyperParams(BaseModel):
    """Base model for algorithm hyper-parameters."""


def _extract_schema_type(schema: dict[str, Any]) -> str | None:
    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        return schema_type
    if isinstance(schema_type, list):
        return " | ".join(str(item) for item in schema_type)
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref
    if "anyOf" in schema:
        return "anyOf"
    if "oneOf" in schema:
        return "oneOf"
    if "allOf" in schema:
        return "allOf"
    return None


def _schema_to_fields(schema: dict[str, Any]) -> list[dict[str, Any]]:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return []
    required = schema.get("required", [])
    required_set = (
        set(required) if isinstance(required, list) else set()
    )
    fields: list[dict[str, Any]] = []
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        entry: dict[str, Any] = {
            "name": name,
            "required": name in required_set,
        }
        field_type = _extract_schema_type(prop)
        if field_type is not None:
            entry["type"] = field_type
        if "default" in prop:
            entry["default"] = prop["default"]
        if "description" in prop:
            entry["description"] = prop["description"]
        fields.append(entry)
    return fields


@dataclass(slots=True)
class AlgorithmSpec(Generic[TInput, TOutput]):
    """Metadata for an algorithm entry."""

    name: str
    version: str
    description: str | None
    input_model: type[TInput]
    output_model: type[TOutput]
    entrypoint: (
        Callable[[TInput], TOutput]
        | type[AlgorithmLifecycleProtocol[TInput, TOutput]]
    )
    algorithm_type: AlgorithmType
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    hyperparams_model: type[BaseModel] | None = None
    is_class: bool = False

    def key(self) -> tuple[str, str]:
        return self.name, self.version

    def input_schema(self) -> dict[str, Any]:
        """Return JSON schema for the input model."""
        return self.input_model.model_json_schema()

    def output_schema(self) -> dict[str, Any]:
        """Return JSON schema for the output model."""
        return self.output_model.model_json_schema()

    def hyperparams_schema(self) -> dict[str, Any] | None:
        """Return JSON schema for the hyper-parameter model."""
        if self.hyperparams_model is None:
            return None
        return self.hyperparams_model.model_json_schema()

    def hyperparams_fields(self) -> list[dict[str, Any]] | None:
        """Return flattened field metadata for hyper-parameters."""
        schema = self.hyperparams_schema()
        if schema is None:
            return None
        return _schema_to_fields(schema)
