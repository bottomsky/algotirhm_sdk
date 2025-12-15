from __future__ import annotations

from typing import Protocol, TypeVar

from .base_model_impl import BaseModel

Req = TypeVar("Req", bound=BaseModel)
Resp = TypeVar("Resp", bound=BaseModel)


class AlgorithmLifecycle(Protocol[Req, Resp]):
    """Lifecycle contract for class-based algorithms."""

    def initialize(self) -> None: ...

    def run(self, req: Req) -> Resp: ...

    def after_run(self) -> None: ...

    def shutdown(self) -> None: ...
