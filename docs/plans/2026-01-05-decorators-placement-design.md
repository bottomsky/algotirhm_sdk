Title: Decorators Placement (Remove algorithm_api)

Status: Accepted
Date: 2026-01-05

Context
- The project is still in early development and does not need backward
  compatibility.
- The current decorator implementation lives under
  `src/algo_sdk/algorithm_api/`, which blurs module semantics.
- We want clear ownership: decorator code should live under `decorators/`.

Decision
- Remove the `algo_sdk.algorithm_api` package entirely.
- Place the decorator implementation in
  `src/algo_sdk/decorators/decorators.py`.
- Make `src/algo_sdk/decorators/__init__.py` the single subpackage export.
- Keep `src/algo_sdk/__init__.py` as the public API surface for imports.

Rationale
- Aligns directory semantics: decorators live in `decorators/`.
- Reduces indirection and avoids a redundant adapter layer.
- Keeps the public API simple and explicit via `algo_sdk/__init__.py`.

Scope
- Move `DefaultAlgorithmDecorator` and `Algorithm` into
  `algo_sdk.decorators`.
- Update imports in `algo_sdk/__init__.py`, tests, and any examples.
- Delete `src/algo_sdk/algorithm_api/` after dependencies are updated.

Non-goals
- Preserve compatibility with `algo_sdk.algorithm_api.*` imports.
- Refactor runtime behavior or validation logic.

Migration Steps
1) Move decorator implementation to `src/algo_sdk/decorators/`.
2) Update `src/algo_sdk/decorators/__init__.py` exports.
3) Update `src/algo_sdk/__init__.py` to import from `algo_sdk.decorators`.
4) Update tests to import from `algo_sdk` (preferred).
5) Remove the `algo_sdk/algorithm_api` package.

Risks
- Import cycles if `decorators` starts importing `algo_sdk.__init__`.
- Missing symbols if `algorithm_api/models.py` is deleted without relocating
  its contents (verify usage before removal).

Testing
- Run decorator unit tests: `tests/decorators/test_decorator.py`.
- Add a minimal import test for `from algo_sdk import Algorithm`.
