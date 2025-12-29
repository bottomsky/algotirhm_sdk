from __future__ import annotations

from algo_sdk.core.service_lifecycle import (
    ServiceLifecycleContext,
    ServiceLifecycleHookProtocol,
    ServiceLifecyclePhase,
)

from .service import AlgorithmHttpService


class AlgorithmHttpServiceHook(ServiceLifecycleHookProtocol):
    """Start and stop the HTTP-backed algorithm service via lifecycle hooks."""

    priority = 0

    def __init__(
        self,
        service: AlgorithmHttpService,
        *,
        priority: int | None = None,
    ) -> None:
        self._service = service
        if priority is not None:
            self.priority = priority

    def can_handle(self, phase: ServiceLifecyclePhase) -> bool:
        return phase in {
            ServiceLifecyclePhase.PROVISIONING,
            ServiceLifecyclePhase.SHUTDOWN,
        }

    def before(self, ctx: ServiceLifecycleContext) -> None:
        if ctx.phase is ServiceLifecyclePhase.PROVISIONING:
            self._service.start()
            return
        if ctx.phase is ServiceLifecyclePhase.SHUTDOWN:
            self._service.shutdown()

    def after(self, ctx: ServiceLifecycleContext) -> None:
        return None
