from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from algo_sdk.core.executor import ExecutorProtocol
from algo_sdk.core.registry import AlgorithmRegistry
from algo_sdk.http.impl.lifecycle_hooks import AlgorithmHttpServiceHook
from algo_sdk.http.impl.service import AlgorithmHttpService, ObservationHooks
from algo_sdk.observability import InMemoryMetrics, InMemoryTracer

from .impl.service_runtime import ServiceRuntime
from .protocol import ServiceLifecycleHookProtocol


@dataclass(slots=True)
class ServiceRuntimeBundle:
    runtime: ServiceRuntime
    service: AlgorithmHttpService
    metrics: InMemoryMetrics
    tracer: InMemoryTracer


def build_service_runtime(
    *,
    registry: AlgorithmRegistry,
    executor: ExecutorProtocol | None = None,
    hooks: Iterable[ServiceLifecycleHookProtocol] | None = None,
    service_hook_priority: int | None = None,
) -> ServiceRuntimeBundle:
    metrics = InMemoryMetrics()
    tracer = InMemoryTracer()

    observation = ObservationHooks(
        on_start=lambda req: (metrics.on_start(req), tracer.on_start(req)),
        on_complete=lambda req, res: (
            metrics.on_complete(req, res),
            tracer.on_complete(req, res),
        ),
        on_error=lambda req, res: (
            metrics.on_error(req, res),
            tracer.on_error(req, res),
        ),
    )

    service = AlgorithmHttpService(
        registry=registry, executor=executor, observation=observation
    )
    runtime_hooks: list[ServiceLifecycleHookProtocol] = [
        AlgorithmHttpServiceHook(
            service,
            priority=service_hook_priority,
        )
    ]
    if hooks:
        runtime_hooks.extend(hooks)

    runtime = ServiceRuntime(hooks=runtime_hooks)
    return ServiceRuntimeBundle(
        runtime=runtime,
        service=service,
        metrics=metrics,
        tracer=tracer,
    )
