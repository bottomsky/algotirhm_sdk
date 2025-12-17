from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, TypeVar, override

from .base_model_impl import BaseModel

TInput = TypeVar("TInput", bound=BaseModel, contravariant=True)
TOutput = TypeVar("TOutput", bound=BaseModel, covariant=True)


class AlgorithmLifecycle(Protocol[TInput, TOutput]):
    """Lifecycle contract for class-based algorithms."""

    def initialize(self) -> None:
        """
        Perform one-time setup before handling requests.

        Implementations can allocate resources such as model weights,
        connections, or caches. It should be safe to call when no requests
        have been served yet and should avoid consuming per-request state.
        """
        ...

    def run(self, req: TInput) -> TOutput:
        """
        Execute one unit of work for the algorithm.

        :param req: The input model for this invocation. It is guaranteed to
            be an instance of the request type parameter ``Req``.
        :return: A response model produced by the algorithm. It must be an
            instance of the response type parameter ``Resp``.

        Implementations should be side-effect free with respect to external
        systems unless explicitly designed otherwise, and should rely on
        :meth:`initialize` / :meth:`shutdown` for one-time setup/teardown and
        :meth:`after_run` for post-processing or cleanup after each call.
        """
        ...

    def after_run(self) -> None:
        """
        Perform post-processing after a call to :meth:`run`.

        This method is called after each successful invocation of
        :meth:`run`. Implementers can use it to perform per-request
        cleanup, logging, metrics collection, or other side effects that
        should occur after the main computation has finished.

        Implementations should not modify the response already returned by
        :meth:`run`, but may update internal state or external observers.
        """
        ...

    def shutdown(self) -> None:
        """
        Release resources and clean up the algorithm instance.

        This method is called when the algorithm is no longer needed, after
        the last call to :meth:`run` / :meth:`after_run`. Implementers should
        free resources acquired in :meth:`initialize`, such as closing files,
        network connections, or releasing memory held by large objects.

        Implementations should ensure that calling this method multiple times
        is safe (idempotent), as some runtimes may attempt repeated cleanup.
        """
        ...


class BaseAlgorithm(ABC, AlgorithmLifecycle[TInput, TOutput]):
    """
    Convenience base with no-op lifecycle hooks; subclasses must implement run.
    """

    @override
    def initialize(self) -> None:
        """Optional one-time setup; override if needed."""
        return None

    @abstractmethod
    @override
    def run(self, req: TInput) -> TOutput:
        """Core algorithm logic; subclasses must provide an implementation."""
        raise NotImplementedError

    @override
    def after_run(self) -> None:
        """Optional per-call hook after run completes; override if needed."""
        return None

    @override
    def shutdown(self) -> None:
        """Optional teardown hook; override if needed."""
        return None
