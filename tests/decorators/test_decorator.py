import inspect

import pytest

from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmType,
    AlgorithmValidationError,
    BaseAlgorithm,
    BaseModel,
    DefaultAlgorithmDecorator,
    ExecutionMode,
    HyperParams,
    LoggingConfig,
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
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

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


def test_class_registration() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

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

    spec = reg.get("cls_algo", "v1")
    assert inspect.isclass(spec.entrypoint)
    assert spec.is_class
    assert spec.execution.isolated_pool is True
    assert spec.execution.stateful is True
    assert spec.execution.execution_mode is ExecutionMode.PROCESS_POOL


def test_local_class_registration_is_rejected_for_pickle() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    class _LocalAlgo(BaseAlgorithm[_Req, _Resp]):

        def run(self, req: _Req) -> _Resp:  # type: ignore[override]
            return _Resp(doubled=req.value * 2)

    with pytest.raises(AlgorithmValidationError):
        deco(
            name="local",
            version="v1",
            algorithm_type=AlgorithmType.PREDICTION,
            **_DEFAULT_METADATA,
        )(_LocalAlgo)


def test_execution_mode_rejects_string() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    with pytest.raises(AlgorithmValidationError):
        deco(
            name="bad-mode",
            version="v1",
            algorithm_type=AlgorithmType.PREDICTION,
            **_DEFAULT_METADATA,
            execution={"execution_mode": "in_process"},
        )(_AlgoForRegistration)


def test_logging_config_is_recorded() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

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

    spec = reg.get("log-algo", "v1")
    assert isinstance(spec.logging, LoggingConfig)
    assert spec.logging.enabled is True
    assert spec.logging.log_input is True
    assert spec.logging.log_output is True
    assert spec.logging.max_length == 128
    assert spec.logging.redact_fields == ("secret",)


def test_hyperparams_requires_hyperparams_base() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

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

    spec = reg.get("good-params", "v1")
    assert spec.hyperparams_model is _ParamsValid


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
