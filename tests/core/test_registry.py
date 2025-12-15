import pytest

from algo_sdk.core import AlgorithmRegistry, AlgorithmSpec, ExecutionConfig, BaseModel


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


def _fn(req: _Req) -> _Resp:
    return _Resp(doubled=req.value * 2)


def test_register_and_get_algorithm() -> None:
    reg = AlgorithmRegistry()
    spec = AlgorithmSpec(
        name="demo",
        version="v1",
        description=None,
        input_model=_Req,
        output_model=_Resp,
        execution=ExecutionConfig(),
        entrypoint=_fn,
        is_class=False,
    )
    reg.register(spec)
    fetched = reg.get("demo", "v1")
    assert fetched.entrypoint is _fn
    assert fetched.input_schema()["title"] == "_Req"
    assert fetched.output_schema()["title"] == "_Resp"


def test_register_duplicate_raises() -> None:
    reg = AlgorithmRegistry()
    spec = AlgorithmSpec(
        name="dup",
        version="v1",
        description=None,
        input_model=_Req,
        output_model=_Resp,
        execution=ExecutionConfig(),
        entrypoint=_fn,
        is_class=False,
    )
    reg.register(spec)
    with pytest.raises(Exception):
        reg.register(spec)
