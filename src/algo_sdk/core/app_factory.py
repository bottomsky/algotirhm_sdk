from __future__ import annotations

from typing import Protocol

from .registry import AlgorithmRegistry


class ApplicationFactory(Protocol):
    """Contract for building a web application around the registered algorithms."""

    def create_app(self, registry: AlgorithmRegistry): ...
