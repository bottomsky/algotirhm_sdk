# Algorithm Response Meta + Request Context Access Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement request metadata access + optional response metadata (code/message/context) without exposing AlgorithmRequest in algorithm entrypoints.

**Architecture:** Use runtime contextvars to store request metadata and optional response metadata. Executors populate contextvars per request and capture response_meta for HTTP to build AlgorithmResponse with context omitted by default.

**Tech Stack:** Python 3.11 (venv), Pydantic v2, FastAPI, multiprocessing

### Task 1: Runtime context response meta + request datetime

**Files:**
- Create: `tests/runtime/test_context.py`
- Modify: `src/algo_sdk/runtime/context.py`
- Modify: `src/algo_sdk/runtime/__init__.py`

**Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from algo_sdk.protocol.models import AlgorithmContext
from algo_sdk.runtime import (
    execution_context,
    get_current_context,
    get_current_request_datetime,
    get_response_meta,
    set_response_code,
    set_response_context,
    set_response_message,
)


def test_response_meta_and_request_datetime_roundtrip() -> None:
    now = datetime.now(timezone.utc)
    ctx = AlgorithmContext(traceId="trace-ctx", tenantId="tenant-1")

    with execution_context(
        request_id="req-1",
        trace_id="trace-ctx",
        request_datetime=now,
        context=ctx,
    ):
        set_response_code(201)
        set_response_message("custom")
        set_response_context({"traceId": "resp-trace"})

        meta = get_response_meta()
        assert meta is not None
        assert meta.code == 201
        assert meta.message == "custom"
        assert meta.context is not None
        assert meta.context.traceId == "resp-trace"
        assert get_current_context() is not None
        assert get_current_request_datetime() == now
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_context.py::test_response_meta_and_request_datetime_roundtrip -v`
Expected: FAIL (missing symbols / request_datetime not supported)

**Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class ResponseMeta:
    code: int | None = None
    message: str | None = None
    context: AlgorithmContext | None = None
```

Add contextvars for `request_datetime` and `response_meta`, plus getters/setters:
- `get_current_request_datetime`
- `set_response_code`
- `set_response_message`
- `set_response_context`
- `get_response_meta`

Update `set_execution_context`/`reset_execution_context` to handle `request_datetime` and clear `response_meta` at start. Export new helpers from `runtime/__init__.py`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_context.py::test_response_meta_and_request_datetime_roundtrip -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/runtime/test_context.py src/algo_sdk/runtime/context.py src/algo_sdk/runtime/__init__.py
git commit -m "feat: add response meta + request datetime context"
```

### Task 2: Executor captures response meta + request datetime

**Files:**
- Modify: `src/algo_sdk/core/executor.py`
- Modify: `tests/core/test_executor.py`

**Step 1: Write the failing tests**

Add an algorithm that sets response metadata and echoes request datetime:

```python
from datetime import datetime, timezone
from algo_sdk.runtime import (
    get_current_request_datetime,
    set_response_code,
    set_response_context,
    set_response_message,
)

class _MetaReq(BaseModel):
    value: int

class _MetaResp(BaseModel):
    seen_datetime: datetime | None

class _MetaAlgo(BaseAlgorithm[_MetaReq, _MetaResp]):
    def run(self, _: _MetaReq) -> _MetaResp:  # type: ignore[override]
        set_response_code(202)
        set_response_message("accepted")
        set_response_context({"traceId": "resp-trace"})
        return _MetaResp(seen_datetime=get_current_request_datetime())
```

Tests:

```python
def test_in_process_captures_response_meta() -> None:
    spec = _build_meta_spec()
    executor = InProcessExecutor()
    try:
        req = ExecutionRequest(
            spec=spec,
            payload=_MetaReq(value=1),
            request_id="req-meta",
            request_datetime=datetime.now(timezone.utc),
        )
        result = executor.submit(req)
        assert result.success is True
        assert result.response_meta is not None
        assert result.response_meta.code == 202
        assert result.response_meta.message == "accepted"
        assert result.response_meta.context is not None
        assert result.response_meta.context.traceId == "resp-trace"
        assert result.data is not None
        assert result.data.seen_datetime == req.request_datetime
    finally:
        executor.shutdown()


def test_process_pool_captures_response_meta() -> None:
    spec = _build_meta_spec()
    executor = ProcessPoolExecutor(max_workers=1, queue_size=1)
    try:
        req = ExecutionRequest(
            spec=spec,
            payload=_MetaReq(value=1),
            request_id="req-meta-pool",
            request_datetime=datetime.now(timezone.utc),
        )
        result = executor.submit(req)
        assert result.success is True
        assert result.response_meta is not None
        assert result.response_meta.code == 202
        assert result.response_meta.message == "accepted"
        assert result.response_meta.context is not None
        assert result.response_meta.context.traceId == "resp-trace"
        assert result.data is not None
        assert result.data.seen_datetime == req.request_datetime
    finally:
        executor.shutdown()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_executor.py::test_in_process_captures_response_meta -v`
Expected: FAIL (ExecutionRequest missing request_datetime / response_meta)

**Step 3: Write minimal implementation**

- Add `request_datetime: datetime | None = None` to `ExecutionRequest`.
- Add `response_meta: ResponseMeta | None = None` to `ExecutionResult`.
- Extend `_WorkerPayload` with `request_datetime`.
- Extend `_WorkerResponse` with `response_meta` mapping.
- Update `set_execution_context` calls to include `request_datetime`.
- Capture `response_meta` after algorithm run (and on errors) and attach to results.
- Deserialize `response_meta` from worker response into `ResponseMeta`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_executor.py::test_in_process_captures_response_meta -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/algo_sdk/core/executor.py tests/core/test_executor.py
git commit -m "feat: capture response meta from executors"
```

### Task 3: HTTP service uses response meta and omits context by default

**Files:**
- Modify: `src/algo_sdk/http/impl/service.py`
- Modify: `src/algo_sdk/http/impl/server.py`
- Modify: `tests/http/test_service.py`

**Step 1: Write the failing tests**

Update existing success test to expect no context by default, and add response-meta override tests:

```python
class _MetaAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        set_response_code(201)
        set_response_message("created")
        set_response_context({"traceId": "resp-trace"})
        return _Resp(doubled=req.value * 2)

class _MetaFailAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, _: _Req) -> _Resp:  # type: ignore[override]
        set_response_code(418)
        set_response_message("teapot")
        set_response_context({"traceId": "resp-trace"})
        raise RuntimeError("boom")
```

Assertions:
- success: `response.context is None` when algorithm does not set it
- override: `response.code/message/context` reflect response_meta
- error override: `response.code/message/context` reflect response_meta even on failure

**Step 2: Run tests to verify they fail**

Run: `pytest tests/http/test_service.py -v`
Expected: FAIL (context still echoed from request; response_meta not wired)

**Step 3: Write minimal implementation**

- Include `request_datetime=request.datetime` in `ExecutionRequest`.
- Build AlgorithmResponse using `ExecutionResult.response_meta` overrides.
- Default `context=None` (omit) unless response_meta.context is set.
- Update server-level `api_error` responses to omit context unless explicitly set.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/http/test_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/algo_sdk/http/impl/service.py src/algo_sdk/http/impl/server.py tests/http/test_service.py
git commit -m "feat: build responses from response meta"
```

### Task 4: Full verification

**Step 1: Run full test suite**

Run: `pytest`
Expected: PASS

**Step 2: Commit (if needed)**

```bash
git status --short
```
Expected: clean

```

