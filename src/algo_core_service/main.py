from __future__ import annotations

from dataclasses import dataclass

from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmHttpService,
    InMemoryMetrics,
    InMemoryTracer,
    create_observation_hooks,
)


@dataclass(slots=True)
class ServiceRuntime:
    service: AlgorithmHttpService
    metrics: InMemoryMetrics
    tracer: InMemoryTracer


def create_service_runtime(registry: AlgorithmRegistry) -> ServiceRuntime:
    metrics = InMemoryMetrics()
    tracer = InMemoryTracer()
    hooks = create_observation_hooks(metrics, tracer)
    service = AlgorithmHttpService(registry, observation=hooks)
    return ServiceRuntime(service=service, metrics=metrics, tracer=tracer)


__all__ = ["ServiceRuntime", "create_service_runtime"]
