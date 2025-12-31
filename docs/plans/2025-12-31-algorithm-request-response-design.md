# Algorithm Request/Response Boundary Design

## Goals

- Keep algorithm entrypoint signature as business-model only (`algo_dto`).
- HTTP accepts `AlgorithmRequest` and returns `AlgorithmResponse`.
- Executor passes `AlgorithmRequest.data` into algorithms.
- Algorithms can read request metadata (`requestId`, `datetime`, `context`, `traceId`) without receiving `AlgorithmRequest`.
- Algorithms can optionally set response fields (`code`, `message`, `context`), with response `context` omitted when not explicitly set.

## Non-Goals

- Do not embed transport semantics inside `algo_dto` models.
- Do not change algorithm entrypoint signatures to accept `AlgorithmRequest`.
- Do not automatically echo request context in responses.

## Data Flow

1. HTTP receives and validates `AlgorithmRequest`.
2. HTTP builds `ExecutionRequest` with payload=`request.data`, request_id, request_datetime, context, trace_id.
3. Executor sets per-request contextvars.
4. Algorithm runs with input model only; it may read request metadata and set response metadata via helpers.
5. Executor collects output + response metadata.
6. HTTP builds `AlgorithmResponse`.

## Contracts

- `ExecutionRequest` includes `request_datetime`, `request_id`, `context`, `trace_id`, and `payload`.
- `algo_sdk.runtime.context` provides:
  - getters for request metadata (context, request_id, trace_id, request_datetime)
  - response meta setters/getter (`set_response_code`, `set_response_message`, `set_response_context`, `get_response_meta`)
- `ExecutionResult` includes optional `response_meta`.
- Worker response messages carry serialized `response_meta` for process-pool executors.

## Response Rules

- Success: `AlgorithmResponse.data` is algorithm output; `code/message` default to 0/"success" unless explicitly set by algorithm; `context` only when explicitly set.
- Error: map `ExecutionError` kind to `api_error` defaults; if algorithm set response metadata before failing, its `code/message/context` override defaults.

## Testing

- Unit tests for contextvars getters/setters and response_meta validation.
- Executor tests (in-process + process pool) to ensure response_meta crosses process boundaries.
- HTTP integration tests:
  - request -> response happy path (context omitted by default)
  - algorithm sets context/message/code (reflected in response)
  - error path with response_meta override.
