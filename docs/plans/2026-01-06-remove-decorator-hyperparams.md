# Remove Decorator Hyperparams Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove decorator-level hyperparams configuration and infer hyperparams only from `run` signatures, enforcing `HyperParams` inheritance at registration time.

**Architecture:** `DefaultAlgorithmDecorator` infers hyperparams from `run(self, req, params)` and rejects non-`HyperParams` types; explicit decorator `hyperparams` is removed; `AlgorithmSpec.hyperparams_model` records the inferred `HyperParams` subclass or stays `None`.

**Tech Stack:** Python 3.11, Pydantic v2.

### Task 1: Enforce HyperParams in decorator registration

**Files:**
- Modify: `tests/decorators/test_decorator.py`
- Modify: `src/algo_sdk/decorators/decorators.py`
- Modify: `src/algo_sdk/core/metadata.py`

**Step 1: Write the failing test**

```python
from algo_sdk.core.metadata import HyperParams

class _ParamsInvalid(BaseModel):
    value: int

class _ParamsValid(HyperParams):
    value: int

class _AlgoWithInvalidParams(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req, params: _ParamsInvalid) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)

class _AlgoWithValidParams(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req, params: _ParamsValid) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)


def test_hyperparams_requires_hyperparams_base() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    with pytest.raises(AlgorithmValidationError, match="HyperParams"):
        deco(
            name="bad-params",
            version="v1",
            algorithm_type=AlgorithmType.PREDICTION,
        )(_AlgoWithInvalidParams)

    deco(
        name="good-params",
        version="v1",
        algorithm_type=AlgorithmType.PREDICTION,
    )(_AlgoWithValidParams)

    spec = reg.get("good-params", "v1")
    assert spec.hyperparams_model is _ParamsValid
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/decorators/test_decorator.py::test_hyperparams_requires_hyperparams_base -v`
Expected: FAIL because non-`HyperParams` is currently accepted.

**Step 3: Write minimal implementation**

```python
from algo_sdk.core.metadata import HyperParams

# __call__ signature: remove hyperparams argument
# _build_class_spec/_build_function_spec: drop explicit hyperparams_model param
# _extract_io: require hyperparams to be a HyperParams subclass
if not (inspect.isclass(hyper_annotation) and issubclass(hyper_annotation, HyperParams)):
    raise AlgorithmValidationError("hyperparams must be a HyperParams subclass")

# AlgorithmSpec typing
hyperparams_model: type[HyperParams] | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/decorators/test_decorator.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/decorators/test_decorator.py src/algo_sdk/decorators/decorators.py src/algo_sdk/core/metadata.py
git commit -m "feat: enforce HyperParams in decorator registration"
```

### Task 2: Remove decorator hyperparams usage from sample algorithm

**Files:**
- Modify: `src/algo_core_service/algorithms/prepare.py`

**Step 1: Update the decorator usage**

```python
@Algorithm(
    name="Prepare",
    version="v1",
    description="Prepare algorithm sample implementation.",
    algorithm_type=AlgorithmType.PREPARE,
    logging=LoggingConfig(enabled=True, log_input=True, log_output=True),
)
class PrepareAlgorithm(BaseAlgorithm[PrepareRequest, PrepareResult]):
    def run(self, req: PrepareRequest, params: PrepareParams) -> PrepareResult:
        ...
```

**Step 2: Run test to verify no regressions**

Run: `pytest tests/decorators/test_decorator.py -v`
Expected: PASS.

**Step 3: Commit**

```bash
git add src/algo_core_service/algorithms/prepare.py
git commit -m "chore: drop hyperparams decorator usage"
```
