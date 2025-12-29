from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Protocol, runtime_checkable


class ServiceState(str, Enum):
    """Coarse-grained lifecycle state for the whole service."""

    CREATED = "Created"
    PROVISIONING = "Provisioning"
    READY = "Ready"
    RUNNING = "Running"
    DEGRADED = "Degraded"
    DRAINING = "Draining"
    SHUTDOWN = "Shutdown"


class ServiceLifecyclePhase(str, Enum):
    """Lifecycle transition command executed against a service runtime."""

    PROVISIONING = "Provisioning"
    READY = "Ready"
    RUNNING = "Running"
    DEGRADED = "Degraded"
    DRAINING = "Draining"
    SHUTDOWN = "Shutdown"


class ServiceLifecycleError(Exception):
    """Base exception for service lifecycle transitions."""


class AlreadyInStateError(ServiceLifecycleError):
    """Raised when requesting a transition to the current state."""

    def __init__(self, *, phase: ServiceLifecyclePhase, state: ServiceState) -> None:
        super().__init__(f"already in state: {state.value}")
        self.phase = phase
        self.state = state


class InvalidTransitionError(ServiceLifecycleError):
    """Raised when a lifecycle command is invalid for the current state."""

    def __init__(
        self,
        *,
        phase: ServiceLifecyclePhase,
        state: ServiceState,
        allowed: tuple[ServiceState, ...],
    ) -> None:
        allowed_str = ", ".join(s.value for s in allowed) if allowed else "<none>"
        super().__init__(
            f"invalid transition {phase.value} from state={state.value}; "
            f"allowed={allowed_str}"
        )
        self.phase = phase
        self.state = state
        self.allowed = allowed


@dataclass(slots=True)
class ServiceLifecycleContext:
    """Context passed into lifecycle hooks for a single phase execution."""

    phase: ServiceLifecyclePhase
    from_state: ServiceState
    to_state: ServiceState
    reason: str | None = None

    exc_before: BaseException | None = None
    exc_main: BaseException | None = None
    after_errors: list[BaseException] = field(default_factory=list)

    started_at: float | None = None
    ended_at: float | None = None

    @property
    def success(self) -> bool:
        return self.exc_before is None and self.exc_main is None


@runtime_checkable
class ServiceLifecycleHookProtocol(Protocol):
    """
    Hook contract for service lifecycle transitions.

    Ordering:
    - before: higher priority runs first (descending)
    - after: reverse order of before (stack unwind)

    A hook can implement sync or async before/after; returning an awaitable is
    treated as async.
    """

    priority: int

    def can_handle(self, phase: ServiceLifecyclePhase) -> bool: ...

    def before(
        self, ctx: ServiceLifecycleContext
    ) -> Awaitable[None] | None: ...

    def after(
        self, ctx: ServiceLifecycleContext
    ) -> Awaitable[None] | None: ...


@runtime_checkable
class ServiceLifecycleProtocol(Protocol):
    """Lifecycle control surface for a service runtime."""

    @property
    def state(self) -> ServiceState: ...

    @property
    def accepting_requests(self) -> bool: ...

    async def provisioning(self, *, reason: str | None = None) -> None: ...

    async def ready(self, *, reason: str | None = None) -> None: ...

    async def running(self, *, reason: str | None = None) -> None: ...

    async def degraded(self, *, reason: str | None = None) -> None: ...

    async def draining(self, *, reason: str | None = None) -> None: ...

    async def shutdown(self, *, reason: str | None = None) -> None: ...
