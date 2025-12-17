from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeVar, cast
from threading import RLock

from .base_model_impl import BaseModel
from .errors import AlgorithmNotFoundError, AlgorithmRegistrationError
from .metadata import AlgorithmSpec

Req = TypeVar("Req", bound=BaseModel)
Resp = TypeVar("Resp", bound=BaseModel)
AnySpec = AlgorithmSpec[Any, Any]


class AlgorithmRegistry:
    """In-memory registry for algorithms."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], AnySpec] = {}
        self._lock = RLock()

    def register(self, spec: AlgorithmSpec[Req, Resp]) -> None:
        key = spec.key()
        with self._lock:
            if key in self._items:
                raise AlgorithmRegistrationError(
                    f"algorithm already registered: {spec.name} ({spec.version})"
                )
            # Cast to a common storage type since AlgorithmSpec is invariant.
            self._items[key] = cast(AnySpec, spec)

    def get(self, name: str, version: str) -> AnySpec:
        key = (name, version)
        with self._lock:
            try:
                return self._items[key]
            except KeyError as exc:
                raise AlgorithmNotFoundError(
                    f"algorithm not found: {name} ({version})") from exc

    def list(self) -> Iterable[AnySpec]:
        with self._lock:
            return tuple(self._items.values())


_default_registry = AlgorithmRegistry()


def get_registry() -> AlgorithmRegistry:
    return _default_registry
