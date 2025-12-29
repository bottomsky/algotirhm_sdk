import asyncio

import pytest

from algo_sdk.core import (
    AlreadyInStateError,
    InvalidTransitionError,
    ServiceLifecycleContext,
    ServiceLifecyclePhase,
    ServiceState,
)
from algo_sdk.runtime import ServiceRuntime


class _Hook:
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        priority: int,
        raise_in_before: bool = False,
        raise_in_after: bool = False,
        phases: set[ServiceLifecyclePhase] | None = None,
    ) -> None:
        self.priority = priority
        self._name = name
        self._events = events
        self._raise_in_before = raise_in_before
        self._raise_in_after = raise_in_after
        self._phases = phases

    def can_handle(self, phase: ServiceLifecyclePhase) -> bool:
        if self._phases is None:
            return True
        return phase in self._phases

    def before(self, ctx: ServiceLifecycleContext) -> None:
        self._events.append(f"before:{self._name}:{ctx.phase.value}")
        if self._raise_in_before:
            raise RuntimeError(f"before boom: {self._name}")

    def after(self, ctx: ServiceLifecycleContext) -> None:
        self._events.append(f"after:{self._name}:{ctx.phase.value}")
        if self._raise_in_after:
            raise RuntimeError(f"after boom: {self._name}")


def test_hook_ordering_priority_desc_and_after_reverse() -> None:
    events: list[str] = []
    hooks = [
        _Hook("low", events, priority=1),
        _Hook("high", events, priority=10),
    ]
    runtime = ServiceRuntime(hooks=hooks)

    async def main() -> None:
        await runtime.provisioning()

    asyncio.run(main())

    assert events == [
        "before:high:Provisioning",
        "before:low:Provisioning",
        "after:low:Provisioning",
        "after:high:Provisioning",
    ]


def test_phase_reentry_raises_already_in_state() -> None:
    runtime = ServiceRuntime()

    async def main() -> None:
        await runtime.provisioning()
        with pytest.raises(AlreadyInStateError):
            await runtime.provisioning()

    asyncio.run(main())


def test_before_hook_failure_blocks_transition_and_after_still_runs() -> None:
    events: list[str] = []
    hooks = [
        _Hook("first", events, priority=10),
        _Hook(
            "fail",
            events,
            priority=1,
            raise_in_before=True,
            phases={ServiceLifecyclePhase.READY},
        ),
    ]
    runtime = ServiceRuntime(hooks=hooks)

    async def main() -> None:
        await runtime.provisioning()
        with pytest.raises(RuntimeError):
            await runtime.ready()
        assert runtime.state is ServiceState.PROVISIONING

    asyncio.run(main())

    assert events == [
        "before:first:Provisioning",
        "after:first:Provisioning",
        "before:first:Ready",
        "before:fail:Ready",
        "after:first:Ready",
    ]


def test_after_hook_failure_is_logged_but_never_blocks() -> None:
    events: list[str] = []
    runtime = ServiceRuntime(
        hooks=[_Hook("bad_after", events, priority=1, raise_in_after=True)]
    )

    async def main() -> None:
        await runtime.provisioning()
        assert runtime.state is ServiceState.PROVISIONING

    asyncio.run(main())


def test_invalid_transition_raises() -> None:
    runtime = ServiceRuntime()

    async def main() -> None:
        with pytest.raises(InvalidTransitionError):
            await runtime.running()

    asyncio.run(main())
