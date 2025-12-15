import inspect

from algo_sdk.core import AlgorithmRegistry, BaseModel
from algo_sdk.decorators import DefaultAlgorithmDecorator


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


def test_function_registration() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    @deco(name="fn_algo", version="v1", description="demo fn")
    def fn(req: _Req) -> _Resp:
        return _Resp(doubled=req.value * 2)

    spec = reg.get("fn_algo", "v1")
    assert spec.entrypoint is fn
    assert spec.description == "demo fn"
    assert not spec.is_class


def test_class_registration() -> None:
    reg = AlgorithmRegistry()
    deco = DefaultAlgorithmDecorator(registry=reg)

    @deco(name="cls_algo", version="v1", execution={"isolated_pool": True})
    class Algo:
        def initialize(self) -> None:
            self.ready = True

        def run(self, req: _Req) -> _Resp:
            return _Resp(doubled=req.value * 2)

        def shutdown(self) -> None:
            self.ready = False

    spec = reg.get("cls_algo", "v1")
    assert inspect.isclass(spec.entrypoint)
    assert spec.is_class
    assert spec.execution.isolated_pool is True
