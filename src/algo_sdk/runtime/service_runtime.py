from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Iterable
from typing import Awaitable

from algo_sdk.core.service_lifecycle import (
    AlreadyInStateError,
    InvalidTransitionError,
    ServiceLifecycleContext,
    ServiceLifecycleHookProtocol,
    ServiceLifecyclePhase,
    ServiceLifecycleProtocol,
    ServiceState,
)

_LOGGER = logging.getLogger(__name__)

async def _maybe_await(result: Awaitable[None] | None) -> None:
    if result is None:
        return
    if inspect.isawaitable(result):
        await result


class ServiceRuntime(ServiceLifecycleProtocol):
    """
    Default implementation of ServiceLifecycleProtocol.

    - Executes lifecycle phases under a single async lock.
    - Runs hooks with descending priority for before, and reverse order for
      after.
    - If any before hook fails, blocks the transition.
    - After hook failures are logged and never block.
    """

    def __init__(
        self,
        *,
        hooks: Iterable[ServiceLifecycleHookProtocol] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        import asyncio

        self._lock = asyncio.Lock()
        self._state = ServiceState.CREATED
        self._hooks = list(hooks) if hooks is not None else []
        self._logger = logger or _LOGGER

    def add_hook(self, hook: ServiceLifecycleHookProtocol) -> None:
        self._hooks.append(hook)

    @property
    def state(self) -> ServiceState:
        return self._state

    @property
    def accepting_requests(self) -> bool:
        return self._state is ServiceState.RUNNING

    async def provisioning(self, *, reason: str | None = None) -> None:
        await self._transition(
            phase=ServiceLifecyclePhase.PROVISIONING,
            to_state=ServiceState.PROVISIONING,
            allowed_from=(ServiceState.CREATED,),
            reason=reason,
        )

    async def ready(self, *, reason: str | None = None) -> None:
        await self._transition(
            phase=ServiceLifecyclePhase.READY,
            to_state=ServiceState.READY,
            allowed_from=(ServiceState.PROVISIONING,),
            reason=reason,
        )

    async def running(self, *, reason: str | None = None) -> None:
        await self._transition(
            phase=ServiceLifecyclePhase.RUNNING,
            to_state=ServiceState.RUNNING,
            allowed_from=(ServiceState.READY, ServiceState.DEGRADED),
            reason=reason,
        )

    async def degraded(self, *, reason: str | None = None) -> None:
        await self._transition(
            phase=ServiceLifecyclePhase.DEGRADED,
            to_state=ServiceState.DEGRADED,
            allowed_from=(ServiceState.RUNNING,),
            reason=reason,
        )

    async def draining(self, *, reason: str | None = None) -> None:
        await self._transition(
            phase=ServiceLifecyclePhase.DRAINING,
            to_state=ServiceState.DRAINING,
            allowed_from=(ServiceState.RUNNING, ServiceState.DEGRADED),
            reason=reason,
        )

    async def shutdown(self, *, reason: str | None = None) -> None:
        await self._transition(
            phase=ServiceLifecyclePhase.SHUTDOWN,
            to_state=ServiceState.SHUTDOWN,
            allowed_from=(
                ServiceState.CREATED,
                ServiceState.PROVISIONING,
                ServiceState.READY,
                ServiceState.RUNNING,
                ServiceState.DEGRADED,
                ServiceState.DRAINING,
            ),
            reason=reason,
        )

    def _eligible_hooks(
        self, phase: ServiceLifecyclePhase
    ) -> list[ServiceLifecycleHookProtocol]:
        eligible: list[tuple[int, ServiceLifecycleHookProtocol]] = []
        for index, hook in enumerate(self._hooks):
            if hook.can_handle(phase):
                eligible.append((index, hook))

        eligible.sort(
            key=lambda item: (
                -int(getattr(item[1], "priority", 0)),
                item[0],
            )
        )
        return [hook for _, hook in eligible]

    async def _transition(
        self,
        *,
        phase: ServiceLifecyclePhase,
        to_state: ServiceState,
        allowed_from: tuple[ServiceState, ...],
        reason: str | None,
    ) -> None:
        async with self._lock:
            from_state = self._state
            if from_state is to_state:
                raise AlreadyInStateError(phase=phase, state=from_state)
            if allowed_from and from_state not in allowed_from:
                raise InvalidTransitionError(
                    phase=phase, state=from_state, allowed=allowed_from
                )

            ctx = ServiceLifecycleContext(
                phase=phase,
                from_state=from_state,
                to_state=to_state,
                reason=reason,
                started_at=time.monotonic(),
            )

            hooks = self._eligible_hooks(phase)
            ran_hooks: list[ServiceLifecycleHookProtocol] = []

            try:
                for hook in hooks:
                    try:
                        await _maybe_await(hook.before(ctx))
                        ran_hooks.append(hook)
                    except BaseException as exc:
                        ctx.exc_before = exc
                        raise

                self._state = to_state
            except BaseException as exc:
                if ctx.exc_before is None and ctx.exc_main is None:
                    ctx.exc_main = exc
                raise
            finally:
                ctx.ended_at = time.monotonic()
                for hook in reversed(ran_hooks):
                    try:
                        await _maybe_await(hook.after(ctx))
                    except BaseException as after_exc:
                        ctx.after_errors.append(after_exc)
                        self._logger.exception(
                            "Lifecycle after hook failed: phase=%s hook=%s",
                            phase.value,
                            hook.__class__.__name__,
                        )
