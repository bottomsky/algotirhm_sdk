from __future__ import annotations

from types import ModuleType

from algo_sdk.core import (
    AlgorithmRegistry,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
)
from algo_sdk.decorators import Algorithm


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


@Algorithm(
    name="demo",
    version="v1",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-01-06",
    author="qa",
    category="unit",
)
class _Algo(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)


class _NotAlgo:
    pass


def test_register_from_module_uses_all() -> None:
    mod = ModuleType("demo_mod")
    mod.__all__ = ["Algo", "NotAlgo"]
    mod.Algo = _Algo
    mod.NotAlgo = _NotAlgo

    reg = AlgorithmRegistry()
    reg.register_from_module(mod)

    spec = reg.get("demo", "v1")
    assert spec.algorithm_type is AlgorithmType.PREDICTION


def test_non_basealgorithm_is_skipped(caplog):
    mod = ModuleType("bad_mod")
    mod.__all__ = ["NotAlgo"]
    mod.NotAlgo = _NotAlgo

    reg = AlgorithmRegistry()
    reg.register_from_module(mod)
    assert "NotAlgo" in caplog.text
