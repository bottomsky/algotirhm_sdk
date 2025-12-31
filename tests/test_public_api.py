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
