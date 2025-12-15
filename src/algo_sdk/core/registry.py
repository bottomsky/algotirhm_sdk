from __future__ import annotations

from threading import RLock
from typing import Dict, Iterable, Tuple

from .errors import AlgorithmNotFoundError, AlgorithmRegistrationError
from .metadata import AlgorithmSpec


class AlgorithmRegistry:
    """In-memory registry for algorithms."""

    def __init__(self) -> None:
        self._items: Dict[Tuple[str, str], AlgorithmSpec] = {}
        self._lock = RLock()

    def register(self, spec: AlgorithmSpec) -> None:
        key = spec.key()
        with self._lock:
            if key in self._items:
                raise AlgorithmRegistrationError(
                    f"algorithm already registered: {spec.name} ({spec.version})"
                )
            self._items[key] = spec

    def get(self, name: str, version: str) -> AlgorithmSpec:
        key = (name, version)
        with self._lock:
            try:
                return self._items[key]
            except KeyError as exc:
                raise AlgorithmNotFoundError(
                    f"algorithm not found: {name} ({version})"
                ) from exc

    def list(self) -> Iterable[AlgorithmSpec]:
        with self._lock:
            return tuple(self._items.values())


_default_registry = AlgorithmRegistry()


def get_registry() -> AlgorithmRegistry:
    return _default_registry
