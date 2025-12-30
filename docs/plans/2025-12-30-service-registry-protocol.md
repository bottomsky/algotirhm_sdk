# Service Registry Protocol Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a `ServiceRegistryProtocol` interface and update callers to type against it for clearer decoupling.

**Architecture:** Add a `typing.Protocol` in `src/algo_sdk/service_registry/protocol.py` alongside the shared dataclasses and enums. Keep `BaseServiceRegistry` as an ABC that structurally satisfies the protocol. Update callers (e.g., catalog) to annotate against the protocol and re-export it from `src/algo_sdk/service_registry/__init__.py`.

**Tech Stack:** Python 3.11/3.13, typing.Protocol, pytest

### Task 1: Add ServiceRegistryProtocol and a runtime check test

**Files:**
- Modify: `src/algo_sdk/service_registry/protocol.py`
- Modify: `src/algo_sdk/service_registry/__init__.py`
- Test: `tests/service_registry/test_service_registry.py`

**Step 1: Write the failing test**

```python
from algo_sdk.service_registry import MemoryRegistry, ServiceRegistryProtocol

def test_memory_registry_implements_protocol() -> None:
    registry = MemoryRegistry()
    assert isinstance(registry, ServiceRegistryProtocol)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service_registry/test_service_registry.py::test_memory_registry_implements_protocol -v`
Expected: FAIL with ImportError for `ServiceRegistryProtocol` or Protocol not runtime-checkable.

**Step 3: Write minimal implementation**

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ServiceRegistryProtocol(Protocol):
    def register(self, registration: ServiceRegistration) -> None: ...
    def deregister(self, service_id: str) -> None: ...
    def get_service(self, service_name: str) -> list[ServiceInstance]: ...
    def get_healthy_service(self, service_name: str) -> list[ServiceInstance]: ...
    def set_kv(self, key: str, value: str) -> None: ...
    def get_kv(self, key: str) -> str | None: ...
    def list_kv_prefix(self, prefix: str) -> dict[str, str]: ...
    def delete_kv(self, key: str) -> None: ...
    def is_healthy(self) -> bool: ...

class BaseServiceRegistry(ABC, ServiceRegistryProtocol):
    ...
```

Also re-export in `__init__.py` and add to `__all__`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/service_registry/test_service_registry.py::test_memory_registry_implements_protocol -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/algo_sdk/service_registry/protocol.py src/algo_sdk/service_registry/__init__.py tests/service_registry/test_service_registry.py
git commit -m "feat: add service registry protocol"
```

### Task 2: Type consumers against the protocol

**Files:**
- Modify: `src/algo_sdk/service_registry/catalog.py`

**Step 1: Update type hints/imports**

```python
from .protocol import ServiceRegistryProtocol

def publish_algorithm_catalog(
    *,
    registry: ServiceRegistryProtocol | None = None,
    ...
) -> None:
    ...
```

**Step 2: Run tests to ensure no regressions**

Run: `uv run pytest tests/service_registry/test_service_registry.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/algo_sdk/service_registry/catalog.py
git commit -m "refactor: type catalog against protocol"
```
