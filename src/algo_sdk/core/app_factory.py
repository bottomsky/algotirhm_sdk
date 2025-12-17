from __future__ import annotations

from typing import Protocol

from .registry import AlgorithmRegistry


class ApplicationFactoryProtocol(Protocol):
    """Contract for building a web app around registered algorithms."""

    def create_app(self, registry: AlgorithmRegistry):
        ...
