# DTO Boundary Strictness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce strict extra-field validation at algorithm request boundaries while keeping nested DTOs lenient for backward compatibility.

**Architecture:** Add a StrictCamelBaseModel with extra="forbid" and apply it to top-level request DTOs only. This keeps nested DTOs on CamelBaseModel to remain tolerant of extra fields. TDD flow follows @superpowers:test-driven-development.

**Tech Stack:** Python 3.11, Pydantic v2, pytest.

### Task 1: Enforce strictness on request DTOs

**Files:**
- Create: `tests/dto/test_dto_strictness.py`
- Modify: `src/algo_dto/base.py`
- Modify: `src/algo_dto/dto.py`

**Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError

from algo_dto.dto import PredictionRequest, PrepareRequest, ProgrammeRequest


def _prediction_payload() -> dict:
    return {
        "sat_states": {"sat_id": 1, "vvlh_rv": [0, 0, 0, 0, 0, 0]},
        "target_sats": [{"sat_id": 2, "vvlh_rv": [0, 0, 0, 0, 0, 0]}],
        "sim_time": [2025, 1, 1, 0, 0, 0],
        "duration_s": 10.0,
    }


def test_prediction_request_rejects_extra_fields() -> None:
    payload = _prediction_payload()
    payload["unexpected"] = "boom"
    with pytest.raises(ValidationError):
        PredictionRequest.model_validate(payload)


def test_request_models_forbid_extra_fields() -> None:
    for model in (PredictionRequest, PrepareRequest, ProgrammeRequest):
        assert model.model_config.get("extra") == "forbid"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/dto/test_dto_strictness.py -v`
Expected: FAIL because extra fields are accepted or `extra` config is missing.

**Step 3: Write minimal implementation**

```python
# src/algo_dto/base.py
class StrictCamelBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )
```

```python
# src/algo_dto/dto.py
class PredictionRequest(StrictCamelBaseModel):
    ...
class PrepareRequest(StrictCamelBaseModel):
    ...
class ProgrammeRequest(StrictCamelBaseModel):
    ...
```

Also add `StrictCamelBaseModel` to `__all__` in `src/algo_dto/base.py`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/dto/test_dto_strictness.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/dto/test_dto_strictness.py src/algo_dto/base.py src/algo_dto/dto.py
git commit -m "feat: forbid extra fields in request DTOs"
```
