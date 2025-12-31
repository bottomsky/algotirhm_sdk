# Unified Public API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `algo_sdk/__init__.py` the single public entry point for algorithm authors and service builders, and migrate external imports to it.

**Architecture:** Add explicit top-level re-exports in `algo_sdk/__init__.py` and a small public API test. Update non-internal modules and all tests to import from `algo_sdk` instead of internal subpackages. Keep internal module imports that would cause circular dependencies.

**Tech Stack:** Python 3.11, pytest, FastAPI, Pydantic

### Task 1: Define top-level public API exports

**Files:**
- Create: `tests/test_public_api.py`
- Modify: `src/algo_sdk/__init__.py`

**Step 1: Write the failing test**

```python
from algo_sdk import (
    Algorithm,
    AlgorithmContext,
    AlgorithmRequest,
    AlgorithmResponse,
    BaseModel,
    api_error,
    api_success,
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    ExecutionConfig,
    ExecutionMode,
    ExecutionError,
    ExecutionRequest,
    ExecutionResult,
    ExecutorProtocol,
    InProcessExecutor,
    ProcessPoolExecutor,
    IsolatedProcessPoolExecutor,
    DispatchingExecutor,
    AlgorithmHttpService,
    ObservationHooks,
    build_service_runtime,
    execution_context,
    get_current_context,
    get_current_request_id,
    get_current_trace_id,
    get_current_request_datetime,
    set_response_code,
    set_response_message,
    set_response_context,
    get_response_meta,
)


def test_public_api_imports() -> None:
    assert Algorithm is not None
    assert BaseModel is not None
    assert AlgorithmRequest is not None
    assert AlgorithmResponse is not None
    assert AlgorithmRegistry is not None
    assert ExecutionRequest is not None
    assert AlgorithmHttpService is not None
    assert callable(api_success)
    assert callable(api_error)
    assert callable(execution_context)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_api.py::test_public_api_imports -v`
Expected: FAIL (missing top-level exports)

**Step 3: Write minimal implementation**

Update `src/algo_sdk/__init__.py`:

```python
"""Public API entry point for algo_sdk."""

from .algorithm_api.decorators import Algorithm
from .core import (
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    ExecutionError,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutorProtocol,
    InProcessExecutor,
    ProcessPoolExecutor,
    IsolatedProcessPoolExecutor,
    DispatchingExecutor,
    get_registry,
    AlgorithmLifecycleProtocol,
)
from .http import AlgorithmHttpService, ObservationHooks
from .protocol import (
    AlgorithmContext,
    AlgorithmRequest,
    AlgorithmResponse,
    api_error,
    api_success,
)
from .runtime import (
    build_service_runtime,
    execution_context,
    get_current_context,
    get_current_request_id,
    get_current_trace_id,
    get_current_request_datetime,
    set_response_code,
    set_response_message,
    set_response_context,
    get_response_meta,
)

__all__ = [
    "Algorithm",
    "BaseModel",
    "AlgorithmContext",
    "AlgorithmRequest",
    "AlgorithmResponse",
    "api_success",
    "api_error",
    "AlgorithmRegistry",
    "AlgorithmSpec",
    "AlgorithmType",
    "ExecutionConfig",
    "ExecutionMode",
    "ExecutionError",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutorProtocol",
    "InProcessExecutor",
    "ProcessPoolExecutor",
    "IsolatedProcessPoolExecutor",
    "DispatchingExecutor",
    "AlgorithmHttpService",
    "ObservationHooks",
    "build_service_runtime",
    "execution_context",
    "get_current_context",
    "get_current_request_id",
    "get_current_trace_id",
    "get_current_request_datetime",
    "set_response_code",
    "set_response_message",
    "set_response_context",
    "get_response_meta",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_public_api.py::test_public_api_imports -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_public_api.py src/algo_sdk/__init__.py
git commit -m "feat: define algo_sdk public api"
```

### Task 2: Migrate non-internal imports to top-level

**Files:**
- Modify: `src/algo_core_service/main.py`
- Modify: `tests/decorators/test_decorator.py`
- Modify: `tests/core/test_executor.py`
- Modify: `tests/core/test_executor_hard_timeout.py`
- Modify: `tests/core/test_lifecycle.py`
- Modify: `tests/core/test_registry.py`
- Modify: `tests/http/test_service.py`
- Modify: `tests/http/test_server.py`
- Modify: `tests/observability/test_observability.py`
- Modify: `tests/protocol/test_models.py`
- Modify: `tests/runtime/test_context.py`
- Modify: `tests/runtime/test_service_runtime.py`
- Modify: `tests/service_registry/test_registry_integration.py`
- Modify: `tests/service_registry/test_service_registry.py`

**Step 1: Write the failing test**

Update one test file to import from `algo_sdk` and confirm it fails before export changes (already done in Task 1). No additional new tests needed.

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_executor.py::test_in_process_propagates_context -v`
Expected: FAIL before import migration is complete.

**Step 3: Write minimal implementation**

Update imports to use top-level `algo_sdk`:

Example change:
```python
# before
from algo_sdk.core import AlgorithmRegistry, ExecutionConfig
from algo_sdk.protocol.models import AlgorithmContext

# after
from algo_sdk import AlgorithmRegistry, ExecutionConfig, AlgorithmContext
```

Keep internal imports inside `algo_sdk/*` modules unchanged if needed to avoid circular imports.

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_executor.py::test_in_process_propagates_context -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/algo_core_service/main.py tests
git commit -m "refactor: use algo_sdk public api"
```

### Task 3: Full verification and cleanup

**Step 1: Run full test suite**

Run: `pytest`
Expected: PASS

**Step 2: Confirm no legacy imports remain**

Run: `rg "algo_sdk\.(core|protocol|runtime|decorators|algorithm_api|http|observability|service_registry)" src tests`
Expected: no hits in `src/algo_core_service` and `tests`

**Step 3: Commit (if needed)**

```bash
git status --short
```
Expected: clean

