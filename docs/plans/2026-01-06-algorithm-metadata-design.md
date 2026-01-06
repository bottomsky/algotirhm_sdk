# Algorithm Metadata Design

## Goal
Add required and optional metadata fields to algorithm registration so external
systems can query consistent, typed metadata via HTTP endpoints and the service
registry catalog.

## Scope
- In: decorator registration, AlgorithmSpec, HTTP list/schema responses, service
  registry catalog.
- Out: request/response protocol changes and runtime execution behavior.

## Metadata Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| created_time | string | yes | Date string in `YYYY-MM-DD` format |
| author | string | yes | Non-empty |
| category | string | yes | Non-empty |
| application_scenarios | string | no | Optional, non-empty if provided |
| extra | dict[str, str] | no | Optional arbitrary key/value pairs |

## Decorator API
Add new keyword arguments to `@Algorithm(...)`:

```python
@Algorithm(
    name="Prediction",
    version="v1",
    description="...",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-01-06",
    author="Example Team",
    category="Orbital",
    application_scenarios="Test or demo",
    extra={"owner": "mission-a", "tier": "gold"},
)
```

## AlgorithmSpec Changes
Extend `AlgorithmSpec` with the metadata fields above. These are persisted in
the registry and used by API responses.

## Validation Rules
Decorator validates on registration:
- `author`, `category`, and `created_time` are required and must be non-empty.
- `created_time` must match `YYYY-MM-DD` and be a valid date.
- `application_scenarios` is optional but must be a non-empty string if set.
- `extra` is optional but must be a dict of string keys and string values.

Invalid values raise `AlgorithmValidationError` at import/registration time.

## API Exposure
Include the metadata fields in:
- `GET /algorithms` list entries.
- `GET /algorithms/{name}/{version}/schema` response payload.
- Service registry catalog entries (`build_algorithm_catalog`).

## Migration Plan
Update all algorithms under `src/algo_core_service/algorithms/` to provide the
required metadata fields in their `@Algorithm` decorators.

## Testing
- Unit tests for decorator validation (missing required fields, invalid date,
  invalid extra).
- Optional integration tests to assert metadata in `/algorithms` and
  `/schema` responses if HTTP test scaffolding exists.

## Risks
Existing algorithms without the new required metadata will fail registration
until updated.
