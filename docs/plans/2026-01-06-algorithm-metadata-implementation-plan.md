# Algorithm Metadata Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add required algorithm metadata fields with validation, then expose them in HTTP responses and the service registry catalog.

**Architecture:** Extend `AlgorithmSpec` to carry metadata fields, validate them in the `@Algorithm` decorator, and propagate them to `/algorithms`, `/schema`, and registry catalog outputs. Update sample algorithms and test fixtures to provide the required metadata.

**Tech Stack:** Python 3.11, FastAPI, dataclasses, pytest

### Task 1: Add metadata fields + decorator validation

**Files:**
- Modify: `src/algo_sdk/core/metadata.py`
- Modify: `src/algo_sdk/decorators/decorators.py`
- Modify: `tests/decorators/test_decorator.py`

**Step 1: Write the failing test**

Add these tests to `tests/decorators/test_decorator.py`:

```python
def test_algorithm_metadata_is_recorded() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    deco(
        name="meta-algo",
        version="v1",
        algorithm_type=AlgorithmType.PREDICTION,
        created_time="2026-01-06",
        author="qa",
        category="unit",
        application_scenarios="demo",
        extra={"owner": "unit"},
    )(_AlgoForRegistration)

    spec = reg.get("meta-algo", "v1")
    assert spec.created_time == "2026-01-06"
    assert spec.author == "qa"
    assert spec.category == "unit"
    assert spec.application_scenarios == "demo"
    assert spec.extra == {"owner": "unit"}


def test_algorithm_metadata_rejects_invalid_values() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    with pytest.raises(AlgorithmValidationError, match="created_time"):
        deco(
            name="bad-date",
            version="v1",
            algorithm_type=AlgorithmType.PREDICTION,
            created_time="2026-02-30",
            author="qa",
            category="unit",
        )(_AlgoForRegistration)

    with pytest.raises(AlgorithmValidationError, match="extra"):
        deco(
            name="bad-extra",
            version="v1",
            algorithm_type=AlgorithmType.PREDICTION,
            created_time="2026-01-06",
            author="qa",
            category="unit",
            extra={"ok": 1},
        )(_AlgoForRegistration)
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python -m pytest tests/decorators/test_decorator.py::test_algorithm_metadata_is_recorded -v`

Expected: FAIL with `unexpected keyword argument` for metadata fields.

**Step 3: Write minimal implementation**

Update `src/algo_sdk/core/metadata.py` to add metadata fields to `AlgorithmSpec`:

```python
@dataclass(slots=True)
class AlgorithmSpec(Generic[TInput, TOutput]):
    name: str
    version: str
    description: str | None
    created_time: str
    author: str
    category: str
    input_model: type[TInput]
    output_model: type[TOutput]
    entrypoint: (
        Callable[[TInput], TOutput]
        | type[AlgorithmLifecycleProtocol[TInput, TOutput]]
    )
    algorithm_type: AlgorithmType
    application_scenarios: str | None = None
    extra: dict[str, str] = field(default_factory=dict)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    hyperparams_model: type[HyperParams] | None = None
    is_class: bool = False
```

Update `src/algo_sdk/decorators/decorators.py` to accept and validate metadata:

```python
import re
from datetime import date

_DATE_RE = re.compile(r"^\\d{4}-\\d{2}-\\d{2}$")

    def __call__(
        self,
        *,
        name: str,
        version: str,
        algorithm_type: AlgorithmType | str,
        description: str | None = None,
        created_time: str | None = None,
        author: str | None = None,
        category: str | None = None,
        application_scenarios: str | None = None,
        extra: dict[str, str] | None = None,
        execution: dict[str, object] | None = None,
        logging: LoggingConfig | dict[str, object] | None = None,
    ) -> Callable[...]:
        ...
        meta = self._validate_metadata(
            created_time=created_time,
            author=author,
            category=category,
            application_scenarios=application_scenarios,
            extra=extra,
        )
        ...

    def _validate_metadata(
        self,
        *,
        created_time: str | None,
        author: str | None,
        category: str | None,
        application_scenarios: str | None,
        extra: dict[str, str] | None,
    ) -> tuple[str, str, str, str | None, dict[str, str]]:
        if not created_time or not created_time.strip():
            raise AlgorithmValidationError("created_time is required")
        created_time = created_time.strip()
        if not _DATE_RE.fullmatch(created_time):
            raise AlgorithmValidationError(
                "created_time must be in YYYY-MM-DD format"
            )
        try:
            date.fromisoformat(created_time)
        except ValueError as exc:
            raise AlgorithmValidationError(
                "created_time must be a valid date"
            ) from exc

        if not author or not author.strip():
            raise AlgorithmValidationError("author is required")
        author = author.strip()

        if not category or not category.strip():
            raise AlgorithmValidationError("category is required")
        category = category.strip()

        if application_scenarios is not None:
            if not application_scenarios.strip():
                raise AlgorithmValidationError(
                    "application_scenarios must be non-empty"
                )
            application_scenarios = application_scenarios.strip()

        if extra is None:
            extra = {}
        elif not isinstance(extra, dict):
            raise AlgorithmValidationError("extra must be a dict[str, str]")
        else:
            for key, value in extra.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise AlgorithmValidationError(
                        "extra must be a dict[str, str]"
                    )

        return (
            created_time,
            author,
            category,
            application_scenarios,
            extra,
        )
```

Use the returned metadata when creating `AlgorithmSpec` in `_build_class_spec`.

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python -m pytest tests/decorators/test_decorator.py::test_algorithm_metadata_is_recorded -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/decorators/test_decorator.py src/algo_sdk/core/metadata.py src/algo_sdk/decorators/decorators.py
git commit -m "feat: add algorithm metadata fields and validation"
```

### Task 2: Expose metadata in HTTP list + schema

**Files:**
- Modify: `src/algo_sdk/http/impl/server.py`
- Modify: `tests/http/test_server.py`

**Step 1: Write the failing test**

Update `tests/http/test_server.py` fixture `AlgorithmSpec(...)` to include metadata
and add a schema metadata assertion:

```python
spec = AlgorithmSpec(
    name="test_algo",
    version="v1",
    algorithm_type=AlgorithmType.PROGRAMME,
    description="test",
    created_time="2026-01-06",
    author="qa",
    category="unit",
    application_scenarios="demo",
    extra={"owner": "unit"},
    input_model=Req,
    output_model=Resp,
    execution=ExecutionConfig(),
    entrypoint=mock_algo,
    is_class=False,
)

def test_list_algorithms(client):
    response = client.get("/algorithms")
    ...
    algo = next(a for a in data["data"] if a["name"] == "test_algo")
    assert algo["created_time"] == "2026-01-06"
    assert algo["author"] == "qa"
    assert algo["category"] == "unit"
    assert algo["application_scenarios"] == "demo"
    assert algo["extra"] == {"owner": "unit"}


def test_schema_includes_metadata(client):
    response = client.get("/algorithms/test_algo/v1/schema")
    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    assert data["created_time"] == "2026-01-06"
    assert data["author"] == "qa"
    assert data["category"] == "unit"
    assert data["application_scenarios"] == "demo"
    assert data["extra"] == {"owner": "unit"}
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python -m pytest tests/http/test_server.py::test_list_algorithms -v`

Expected: FAIL because metadata fields are missing in responses.

**Step 3: Write minimal implementation**

Update `src/algo_sdk/http/impl/server.py` to include metadata in responses:

```python
    @app.get("/algorithms")
    async def list_algorithms():
        specs = reg.list()
        data = [
            {
                "name": s.name,
                "version": s.version,
                "description": s.description,
                "algorithm_type": s.algorithm_type.value,
                "created_time": s.created_time,
                "author": s.author,
                "category": s.category,
                "application_scenarios": s.application_scenarios,
                "extra": s.extra,
            }
            for s in specs
        ]
        return api_success(data=data)

    @app.get("/algorithms/{name}/{version}/schema")
    async def get_schema(name: str, version: str):
        ...
        return api_success(
            data={
                "input": spec.input_schema(),
                "output": spec.output_schema(),
                "execution": _execution_to_dict(spec.execution),
                "algorithm_type": spec.algorithm_type.value,
                "hyperparams": hyperparams,
                "created_time": spec.created_time,
                "author": spec.author,
                "category": spec.category,
                "application_scenarios": spec.application_scenarios,
                "extra": spec.extra,
            }
        )
```

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python -m pytest tests/http/test_server.py::test_list_algorithms -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/http/test_server.py src/algo_sdk/http/impl/server.py
git commit -m "feat: expose algorithm metadata in http responses"
```

### Task 3: Expose metadata in service registry catalog

**Files:**
- Modify: `src/algo_sdk/service_registry/catalog.py`
- Modify: `tests/service_registry/test_catalog.py`

**Step 1: Write the failing test**

Add a new test to `tests/service_registry/test_catalog.py`:

```python
from algo_sdk import AlgorithmSpec, AlgorithmType, BaseModel, ExecutionConfig

class _Req(BaseModel):
    value: int

class _Resp(BaseModel):
    doubled: int

def _algo(req: _Req) -> _Resp:
    return _Resp(doubled=req.value * 2)

def test_build_algorithm_catalog_includes_metadata() -> None:
    config = ServiceRegistryConfig(
        host="http://localhost:8500",
        enabled=True,
        service_name="algo-service",
        instance_id="instance-1",
        service_host="host.docker.internal",
        service_port=8000,
        service_protocol="http",
    )

    spec = AlgorithmSpec(
        name="test_algo",
        version="v1",
        algorithm_type=AlgorithmType.PROGRAMME,
        description="test",
        created_time="2026-01-06",
        author="qa",
        category="unit",
        application_scenarios="demo",
        extra={"owner": "unit"},
        input_model=_Req,
        output_model=_Resp,
        execution=ExecutionConfig(),
        entrypoint=_algo,
        is_class=False,
    )

    catalog = build_algorithm_catalog(config, algorithms=[spec])
    entry = catalog["algorithms"][0]
    assert entry["created_time"] == "2026-01-06"
    assert entry["author"] == "qa"
    assert entry["category"] == "unit"
    assert entry["application_scenarios"] == "demo"
    assert entry["extra"] == {"owner": "unit"}
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python -m pytest tests/service_registry/test_catalog.py::test_build_algorithm_catalog_includes_metadata -v`

Expected: FAIL because metadata fields are missing in catalog output.

**Step 3: Write minimal implementation**

Update `src/algo_sdk/service_registry/catalog.py` to include metadata:

```python
        items.append(
            {
                "name": spec.name,
                "version": spec.version,
                "description": spec.description,
                "algorithm_type": spec.algorithm_type.value,
                "route": route,
                "schema_url": schema_route,
                "absolute_route": f"{base_url}{route}",
                "absolute_schema_url": f"{base_url}{schema_route}",
                "input_schema": spec.input_schema(),
                "output_schema": spec.output_schema(),
                "hyperparams_schema": hyper_schema,
                "hyperparams_fields": hyper_fields or [],
                "created_time": spec.created_time,
                "author": spec.author,
                "category": spec.category,
                "application_scenarios": spec.application_scenarios,
                "extra": spec.extra,
            }
        )
```

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python -m pytest tests/service_registry/test_catalog.py::test_build_algorithm_catalog_includes_metadata -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/service_registry/test_catalog.py src/algo_sdk/service_registry/catalog.py
git commit -m "feat: include metadata in service registry catalog"
```

### Task 4: Update sample algorithms and all AlgorithmSpec instantiations

**Files:**
- Modify: `src/algo_core_service/algorithms/prediction.py`
- Modify: `src/algo_core_service/algorithms/prepare.py`
- Modify: `src/algo_core_service/algorithms/programme.py`
- Modify (AlgorithmSpec fixtures):  
  `tests/core/test_executor.py`  
  `tests/core/test_executor_hard_timeout.py`  
  `tests/core/test_lifecycle.py`  
  `tests/core/test_registry.py`  
  `tests/http/test_service.py`  
  `tests/observability/test_observability.py`  
  `tests/service_registry/test_registry_integration.py`  
  `tests/http/test_server.py` (if any remaining fixtures)

**Step 1: Update algorithm decorators with required metadata**

Example for each algorithm file:

```python
@Algorithm(
    name="Prediction",
    version="v1",
    description="Prediction algorithm sample implementation.",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-01-06",
    author="algo-team",
    category="prediction",
    application_scenarios="demo",
    extra={"owner": "core-service"},
    logging=LoggingConfig(enabled=True, log_input=True, log_output=True),
)
```

**Step 2: Update AlgorithmSpec instantiations**

Use a consistent metadata block for tests:

```python
spec = AlgorithmSpec(
    name="demo",
    version="v1",
    description=None,
    created_time="2026-01-06",
    author="qa",
    category="unit",
    application_scenarios="test",
    extra={"owner": "unit"},
    input_model=_Req,
    output_model=_Resp,
    algorithm_type=AlgorithmType.PREDICTION,
    execution=ExecutionConfig(),
    entrypoint=_DoubleAlgo,
    is_class=True,
)
```

**Step 3: Run full test suite**

Run: `.\.venv\Scripts\python -m pytest`

Expected: PASS

**Step 4: Commit**

```bash
git add src/algo_core_service/algorithms tests
git commit -m "chore: update algorithms and tests for metadata fields"
```
