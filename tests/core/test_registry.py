import pytest

from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
)


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


class _DoubleAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)


def test_register_and_get_algorithm() -> None:
    reg = AlgorithmRegistry()
    spec = AlgorithmSpec(
        name="demo",
        version="v1",
        description=None,
        created_time="2026-01-06",
        author="qa",
        category="unit",
        application_scenarios="test",
        extra={"owner": "unit"},
        input_model=_Req,
        output_model=_Resp,
        algorithm_type=AlgorithmType.PREDICTION,
        execution=ExecutionConfig(),
        entrypoint=_DoubleAlgo,
        is_class=True,
    )
    reg.register(spec)
    fetched = reg.get("demo", "v1")
    assert fetched.entrypoint is _DoubleAlgo
    assert fetched.input_schema()["title"] == "_Req"
    assert fetched.output_schema()["title"] == "_Resp"


def test_register_duplicate_raises() -> None:
    reg = AlgorithmRegistry()
    spec = AlgorithmSpec(
        name="dup",
        version="v1",
        description=None,
        created_time="2026-01-06",
        author="qa",
        category="unit",
        application_scenarios="test",
        extra={"owner": "unit"},
        input_model=_Req,
        output_model=_Resp,
        algorithm_type=AlgorithmType.PREDICTION,
        execution=ExecutionConfig(),
        entrypoint=_DoubleAlgo,
        is_class=True,
    )
    reg.register(spec)
    with pytest.raises(Exception):
        reg.register(spec)
