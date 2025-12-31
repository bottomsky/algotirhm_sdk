import inspect

import pytest

from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmValidationError,
    AlgorithmLifecycleProtocol,
    BaseAlgorithm,
    BaseModel,
    DefaultAlgorithmDecorator,
    ExecutionMode,
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


def test_function_registration_is_rejected() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    with pytest.raises(AlgorithmValidationError):

        @deco(name="fn_algo", version="v1", description="demo fn")
        def fn(req: _Req) -> _Resp:
            return _Resp(doubled=req.value * 2)


def test_class_registration() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    deco(
        name="cls_algo",
        version="v1",
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
        deco(name="local", version="v1")(_LocalAlgo)


def test_execution_mode_rejects_string() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    with pytest.raises(AlgorithmValidationError):
        deco(
            name="bad-mode",
            version="v1",
            execution={"execution_mode": "in_process"},
        )(_AlgoForRegistration)
