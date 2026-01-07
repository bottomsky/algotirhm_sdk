import pytest

from algo_sdk import (
    AlgorithmMarker,
    AlgorithmType,
    AlgorithmValidationError,
    BaseAlgorithm,
    BaseModel,
    DefaultAlgorithmDecorator,
    ExecutionMode,
    HyperParams,
)


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


class _AlgoForRegistration(BaseAlgorithm[_Req, _Resp]):

    def initialize(self) -> None:
        self.ready = True

    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)

    def shutdown(self) -> None:
        self.ready = False


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


_DEFAULT_METADATA = {
    "created_time": "2026-01-06",
    "author": "qa",
    "category": "unit",
}


def test_function_registration_is_rejected() -> None:
    deco = DefaultAlgorithmDecorator()

    with pytest.raises(AlgorithmValidationError):

        @deco(
            name="fn_algo",
            version="v1",
            description="demo fn",
            algorithm_type=AlgorithmType.PREDICTION,
            **_DEFAULT_METADATA,
        )
        def fn(req: _Req) -> _Resp:
            return _Resp(doubled=req.value * 2)


def test_class_registration_marks_metadata() -> None:
    deco = DefaultAlgorithmDecorator()

    deco(
        name="cls_algo",
        version="v1",
        algorithm_type=AlgorithmType.PREDICTION,
        **_DEFAULT_METADATA,
        execution={
            "isolated_pool": True,
            "stateful": True,
            "execution_mode": ExecutionMode.PROCESS_POOL,
        },
    )(_AlgoForRegistration)

    meta = getattr(_AlgoForRegistration, "__algo_meta__")
    assert isinstance(meta, AlgorithmMarker)
    assert meta.name == "cls_algo"
    assert meta.execution["isolated_pool"] is True
    assert meta.execution["stateful"] is True
    assert meta.execution["execution_mode"] is ExecutionMode.PROCESS_POOL


def test_local_class_is_marked() -> None:
    deco = DefaultAlgorithmDecorator()

    class _LocalAlgo(BaseAlgorithm[_Req, _Resp]):

        def run(self, req: _Req) -> _Resp:  # type: ignore[override]
            return _Resp(doubled=req.value * 2)

    deco(
        name="local",
        version="v1",
        algorithm_type=AlgorithmType.PREDICTION,
        **_DEFAULT_METADATA,
    )(_LocalAlgo)

    meta = getattr(_LocalAlgo, "__algo_meta__")
    assert isinstance(meta, AlgorithmMarker)


def test_execution_mode_rejects_string() -> None:
    deco = DefaultAlgorithmDecorator()

    with pytest.raises(AlgorithmValidationError):
        deco(
            name="bad-mode",
            version="v1",
            algorithm_type=AlgorithmType.PREDICTION,
            **_DEFAULT_METADATA,
            execution={"execution_mode": "in_process"},
        )(_AlgoForRegistration)


def test_logging_config_is_recorded() -> None:
    deco = DefaultAlgorithmDecorator()

    deco(
        name="log-algo",
        version="v1",
        algorithm_type=AlgorithmType.PREDICTION,
        **_DEFAULT_METADATA,
        logging={
            "enabled": True,
            "log_input": True,
            "log_output": True,
            "max_length": 128,
            "redact_fields": ["secret"],
        },
    )(_AlgoForRegistration)

    meta = getattr(_AlgoForRegistration, "__algo_meta__")
    assert meta.logging["enabled"] is True
    assert meta.logging["log_input"] is True
    assert meta.logging["log_output"] is True
    assert meta.logging["max_length"] == 128
    assert meta.logging["redact_fields"] == ("secret",)


def test_hyperparams_requires_hyperparams_base() -> None:
    deco = DefaultAlgorithmDecorator()

    with pytest.raises(AlgorithmValidationError, match="HyperParams"):
        deco(
            name="bad-params",
            version="v1",
            algorithm_type=AlgorithmType.PREDICTION,
            **_DEFAULT_METADATA,
        )(_AlgoWithInvalidParams)

    deco(
        name="good-params",
        version="v1",
        algorithm_type=AlgorithmType.PREDICTION,
        **_DEFAULT_METADATA,
    )(_AlgoWithValidParams)

    meta = getattr(_AlgoWithValidParams, "__algo_meta__")
    assert meta.hyperparams_model is _ParamsValid


def test_algorithm_metadata_is_recorded() -> None:
    deco = DefaultAlgorithmDecorator()

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

    meta = getattr(_AlgoForRegistration, "__algo_meta__")
    assert meta.created_time == "2026-01-06"
    assert meta.author == "qa"
    assert meta.category == "unit"
    assert meta.application_scenarios == "demo"
    assert meta.extra == {"owner": "unit"}


def test_algorithm_metadata_rejects_invalid_values() -> None:
    deco = DefaultAlgorithmDecorator()

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
