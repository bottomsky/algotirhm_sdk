# Module Structure and Assembly Design

## Goal

Provide a clean, protocol-first module structure that keeps implementations isolated and builds services through explicit assembly. This enables algorithm authors to depend on a minimal API (decorator + models) while service runtime uses pluggable components via hooks and factories.

## Design Principles

- Protocol-first: define Protocol interfaces before implementations.
- Shared logic lives in ABCs (Base classes) that inherit the Protocol.
- Concrete implementations live in separate impl/adapters folders.
- Cross-module imports should depend on Protocol/ABC only, not concrete implementations.
- Assembly is centralized in a factory/assembler module, never in __init__.py.
- No side effects at import time (avoid implicit startup in module scope).

## Proposed Package Layout

```
src/algo_sdk/
  algorithm_api/                 # Minimal API for algorithm authors
    protocol.py                  # Algorithm contracts (optional)
    decorators.py                # Algorithm decorator
    models.py                    # BaseModel wrapper, AlgorithmContext
    __init__.py                  # Export only minimal API

  core/                           # Domain types and registries
    base_model_impl.py
    metadata.py                   # AlgorithmSpec, ExecutionConfig, AlgorithmType
    registry.py                   # AlgorithmRegistry
    errors.py

  runtime/
    protocol.py                   # ServiceLifecycleProtocol, HookProtocol, State
    impl/
      service_runtime.py          # ServiceRuntime implementation
    factory.py                    # build_service_runtime(...) assembly
    __init__.py                   # Export Protocols + factory only

  http/
    protocol.py                   # Optional HTTP service protocol
    impl/
      service.py                  # AlgorithmHttpService implementation
      server.py                   # FastAPI wiring
    lifecycle_hooks.py            # HTTP lifecycle hooks
    __init__.py                   # Export protocol + factory hooks only

  observability/
    protocol.py                   # Metrics/Tracer protocols
    impl/
      metrics.py                  # InMemoryMetrics
      tracing.py                  # InMemoryTracer
    __init__.py

  service_registry/
    protocol.py                   # BaseServiceRegistry
    impl/
      consul_registry.py
      memory_registry.py
    catalog.py                    # Publish/fetch algorithm catalogs
    __init__.py
```

## Algorithm Author API (Minimal Dependency)

- Create a dedicated package (e.g., `algo_sdk/algorithm_api`) that exposes only:
  - `Algorithm` decorator
  - `BaseModel` (and optional `AlgorithmContext`)
  - Minimal metadata types if required (ExecutionConfig, AlgorithmType)
- Algorithm authors import from this minimal package:

```

from algo_sdk.algorithm_api import Algorithm, BaseModel

@Algorithm(name="demo", version="v1")
def run(req: MyReq) -> MyResp:
    ...
```

This avoids pulling in runtime/HTTP/executor dependencies when authoring algorithms.

## Runtime Assembly (Single Responsibility)

- `build_service_runtime(...)` is the single assembly point.
- It receives protocol-level dependencies (registry, executor, hooks).
- It constructs concrete implementations (AlgorithmHttpService, metrics/tracer) and wires them through lifecycle hooks.
- Service runtime remains clean and only knows about the lifecycle state machine and hooks.

## HTTP Server Integration

- `http/impl/server.py` should only:
  - call `build_service_runtime(...)`
  - set up FastAPI routes
  - gate readiness/draining based on ServiceLifecycleProtocol
- It should not construct implementations directly, and should not import impl classes except through factory output.

## Service Registry Aggregation

- Provide a registry-agnostic endpoint that queries algorithms from Consul via `BaseServiceRegistry`:
  - Example: `GET /registry/algorithms?prefix=services/`
- The endpoint should use `catalog.fetch_registry_algorithm_catalogs()` to avoid HTTP logic touching Consul directly.

## Suggested Migration Steps

1. Introduce protocol.py files and impl/ folders without moving code.
2. Move implementations into impl/ and update imports.
3. Route all assembly through runtime/factory.
4. Expose only protocol and factory from __init__.py.
5. Update algorithm author docs to use algorithm_api package.

## Notes on Naming

- Protocols end with `Protocol`.
- Abstract base classes start with `Base`.
- Concrete classes have no `Base` prefix.

## Detailed Migration Mapping

### algorithm_api (new)

- Create `src/algo_sdk/algorithm_api/` as the minimal author-facing surface.
- Move or re-export:
  - `algo_sdk/decorators/algorithm_decorator_impl.py` -> `algo_sdk/algorithm_api/decorators.py` (or keep impl and re-export from algorithm_api).
  - `algo_sdk/core/base_model_impl.py` -> re-export from `algorithm_api/models.py`.
  - `algo_sdk/protocol/models.py` -> re-export `AlgorithmContext` (optional).
- Example author import change:

```
# before
from algo_sdk.decorators import Algorithm
from algo_sdk.core.base_model_impl import BaseModel

# after
from algo_sdk.algorithm_api import Algorithm, BaseModel
```

### runtime

- Create protocol file: `src/algo_sdk/runtime/protocol.py` with:
  - `ServiceLifecycleProtocol`, `ServiceLifecycleHookProtocol`, `ServiceState`, `ServiceLifecyclePhase`, lifecycle errors.
- Move implementation:
  - `src/algo_sdk/runtime/service_runtime.py` -> `src/algo_sdk/runtime/impl/service_runtime.py`
- Keep assembly in:
  - `src/algo_sdk/runtime/factory.py`
- Update `src/algo_sdk/runtime/__init__.py` to export only protocols and factory (no impl imports).

### http

- Move implementations:
  - `src/algo_sdk/http/server.py` -> `src/algo_sdk/http/impl/server.py`
  - `src/algo_sdk/http/service.py` -> `src/algo_sdk/http/impl/service.py`
  - `src/algo_sdk/http/lifecycle_hooks.py` -> `src/algo_sdk/http/impl/lifecycle_hooks.py`
- Keep `src/algo_sdk/http/__init__.py` as re-exports of protocol + factory/hook entry points.

### observability

- Create protocol file: `src/algo_sdk/observability/protocol.py`.
- Move implementations:
  - `src/algo_sdk/observability/metrics.py` -> `src/algo_sdk/observability/impl/metrics.py`
  - `src/algo_sdk/observability/tracing.py` -> `src/algo_sdk/observability/impl/tracing.py`

### service_registry

- Keep protocol:
  - `src/algo_sdk/service_registry/protocol.py`
- Move implementations:
  - `src/algo_sdk/service_registry/consul_registry.py` -> `src/algo_sdk/service_registry/impl/consul_registry.py`
  - `src/algo_sdk/service_registry/memory_registry.py` -> `src/algo_sdk/service_registry/impl/memory_registry.py`
- Keep helpers:
  - `src/algo_sdk/service_registry/catalog.py` (or move to `helpers/` if desired)

### core (domain types)

- Keep `core/` as domain and registry types (`AlgorithmSpec`, `ExecutionConfig`, `AlgorithmRegistry`, errors).
- Avoid adding runtime or HTTP implementations here.

## Import/Dependency Rules (Enforced)

- `impl/*` may depend on `protocol` and `core`.
- `protocol/*` must not import from `impl/*`.
- `__init__.py` re-exports only protocol + factory symbols.
- Assembly happens only in `runtime/factory.py` (or `assembler.py`), not in `__init__.py`.

## Compatibility Plan

- Phase 1: add new paths and re-export legacy modules for compatibility.
- Phase 2: update internal imports to new protocol/impl paths.
- Phase 3: deprecate legacy imports (documented) and remove after a full release.

## File Migration List

- `src/algo_sdk/decorators/algorithm_decorator_impl.py` -> `src/algo_sdk/algorithm_api/decorators.py` (or re-export from algorithm_api)
- `src/algo_sdk/core/base_model_impl.py` -> `src/algo_sdk/algorithm_api/models.py` (re-export)
- `src/algo_sdk/protocol/models.py` -> `src/algo_sdk/algorithm_api/models.py` (AlgorithmContext re-export, optional)
- `src/algo_sdk/runtime/service_runtime.py` -> `src/algo_sdk/runtime/impl/service_runtime.py`
- `src/algo_sdk/runtime/factory.py` -> keep (assembly point)
- `src/algo_sdk/runtime/__init__.py` -> export protocol + factory only
- `src/algo_sdk/runtime/protocol.py` -> new
- `src/algo_sdk/http/server.py` -> `src/algo_sdk/http/impl/server.py`
- `src/algo_sdk/http/service.py` -> `src/algo_sdk/http/impl/service.py`
- `src/algo_sdk/http/lifecycle_hooks.py` -> `src/algo_sdk/http/impl/lifecycle_hooks.py`
- `src/algo_sdk/http/__init__.py` -> re-export protocol + factory/hook entry points only
- `src/algo_sdk/http/protocol.py` -> new (optional)
- `src/algo_sdk/observability/metrics.py` -> `src/algo_sdk/observability/impl/metrics.py`
- `src/algo_sdk/observability/tracing.py` -> `src/algo_sdk/observability/impl/tracing.py`
- `src/algo_sdk/observability/protocol.py` -> new
- `src/algo_sdk/service_registry/consul_registry.py` -> `src/algo_sdk/service_registry/impl/consul_registry.py`
- `src/algo_sdk/service_registry/memory_registry.py` -> `src/algo_sdk/service_registry/impl/memory_registry.py`
- `src/algo_sdk/service_registry/protocol.py` -> keep
- `src/algo_sdk/service_registry/catalog.py` -> keep (or move to helpers/)
- `src/algo_sdk/core/*` -> keep (domain types only)
