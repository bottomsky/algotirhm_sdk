# Decorators Placement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove `algo_sdk.algorithm_api` and place decorator implementation under `algo_sdk.decorators` with a single public import surface.

**Architecture:** Move the decorator implementation into the `decorators/` package, update `algo_sdk/__init__.py` to import from `decorators`, and delete the `algorithm_api` package. Add a test asserting the old package is gone.

**Tech Stack:** Python 3.11, pytest, standard library `importlib`.

### Task 1: Remove algorithm_api package and relocate decorators

**Files:**
- Create: `tests/decorators/test_public_imports.py`
- Create: `src/algo_sdk/decorators/decorators.py` (move from `src/algo_sdk/algorithm_api/decorators.py`)
- Modify: `src/algo_sdk/decorators/__init__.py`
- Modify: `src/algo_sdk/__init__.py`
- Delete: `src/algo_sdk/algorithm_api/__init__.py`
- Delete: `src/algo_sdk/algorithm_api/models.py`
- Delete: `src/algo_sdk/algorithm_api/decorators.py`

**Step 1: Write the failing test**

```python
import importlib
import pytest


def test_algorithm_api_package_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("algo_sdk.algorithm_api")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/decorators/test_public_imports.py::test_algorithm_api_package_removed -v`  
Expected: FAIL with "did not raise ModuleNotFoundError"

**Step 3: Implement the minimal code**

- Move the decorator implementation:
  - Command: `git mv src/algo_sdk/algorithm_api/decorators.py src/algo_sdk/decorators/decorators.py`
- Update `src/algo_sdk/decorators/__init__.py` to:

```python
"""Internal decorator exports. Prefer `algo_sdk` top-level imports."""

from .decorators import Algorithm, DefaultAlgorithmDecorator

__all__ = ["Algorithm", "DefaultAlgorithmDecorator"]
```

- Update the public import in `src/algo_sdk/__init__.py`:

```python
from .decorators import Algorithm, DefaultAlgorithmDecorator
```

- Remove the old package:
  - Commands:
    - `Remove-Item src/algo_sdk/algorithm_api/__init__.py`
    - `Remove-Item src/algo_sdk/algorithm_api/models.py`
    - `Remove-Item src/algo_sdk/algorithm_api` if empty
- Verify no remaining references:
  - Command: `rg -n "algorithm_api" -g "*.py"`

**Step 4: Run tests to verify they pass**

Run:
- `pytest tests/decorators/test_public_imports.py::test_algorithm_api_package_removed -v`
- `pytest tests/decorators/test_decorator.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/decorators/test_public_imports.py src/algo_sdk/decorators/__init__.py src/algo_sdk/decorators/decorators.py src/algo_sdk/__init__.py
git rm src/algo_sdk/algorithm_api/__init__.py src/algo_sdk/algorithm_api/models.py
git commit -m "refactor: remove algorithm_api package"
```
