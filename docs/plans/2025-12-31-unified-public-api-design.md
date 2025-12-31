# Unified algo_sdk Public API Design

## Goal

Unify all public imports under `algo_sdk/__init__.py` for both algorithm authors and service builders.

## Architecture

- `algo_sdk/__init__.py` is the only supported public entry point.
- All internal modules remain but are treated as implementation details.
- All imports in `src/` and `tests/` are updated to `from algo_sdk import ...`.
- No backward compatibility for old import paths.

## Public Surface (Top-Level Exports)

Algorithm author surface:
- Algorithm decorator
- BaseModel
- AlgorithmContext
- AlgorithmRequest / AlgorithmResponse
- api_success / api_error

Service builder surface:
- AlgorithmRegistry / AlgorithmSpec / AlgorithmType
- ExecutionConfig / ExecutionMode
- ExecutorProtocol / ExecutionRequest / ExecutionResult / ExecutionError
- InProcessExecutor / ProcessPoolExecutor / IsolatedProcessPoolExecutor / DispatchingExecutor
- AlgorithmHttpService / ObservationHooks
- build_service_runtime

Runtime utilities:
- execution_context
- get_current_context / get_current_request_id / get_current_trace_id
- get_current_request_datetime
- set_response_code / set_response_message / set_response_context
- get_response_meta

## Migration Steps

1. Add module docstring and re-exports in `algo_sdk/__init__.py`.
2. Update imports across `src/` and `tests/` to use top-level API.
3. Keep subpackage `__init__.py` files minimal and mark as internal (optional note).
4. Verify no old paths remain with `rg`.

## Risks & Mitigations

- Circular imports from heavy re-exports.
  - Mitigation: keep `algo_sdk/__init__.py` as a thin re-export layer only.
  - If needed, use lazy `__getattr__` or re-export from leaf modules.

## Testing

- Run `pytest` after import migration.
- Ensure `rg "algo_sdk\.(core|protocol|runtime|decorators|algorithm_api|http|observability|service_registry)" src tests` returns no hits.

## Success Criteria

- All code imports from `algo_sdk` only.
- Test suite passes.
- Public API usage is unambiguous for both algorithm authors and service builders.
