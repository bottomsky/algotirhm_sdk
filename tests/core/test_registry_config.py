from __future__ import annotations

from pathlib import Path

from algo_sdk.core import (
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    LoggingConfig,
)


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


class _Algo(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)


def _build_spec() -> AlgorithmSpec[_Req, _Resp]:
    return AlgorithmSpec(
        name="demo",
        version="v1",
        description="orig",
        created_time="2026-01-06",
        author="qa",
        category="unit",
        application_scenarios="demo",
        extra={"owner": "unit"},
        input_model=_Req,
        output_model=_Resp,
        algorithm_type=AlgorithmType.PREDICTION,
        execution=ExecutionConfig(timeout_s=10),
        logging=LoggingConfig(enabled=False, log_input=False, log_output=False),
        entrypoint=_Algo,
        is_class=True,
    )


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_load_config_overrides_existing(tmp_path: Path) -> None:
    reg = AlgorithmRegistry()
    reg.register(_build_spec())
    _write(
        tmp_path / "a.algometa.yaml",
        """
- name: demo
  version: v1
  category: unit
  algorithm_type: Prediction
  description: override
  created_time: "2026-02-01"
  author: "ml-team"
  application_scenarios: "offline"
  extra:
    owner: "override"
  logging:
    enabled: true
    log_output: true
  execution:
    timeout_s: 30
""".strip(),
    )

    reg.load_config(tmp_path)
    spec = reg.get("demo", "v1")
    assert spec.description == "override"
    assert spec.created_time == "2026-02-01"
    assert spec.author == "ml-team"
    assert spec.application_scenarios == "offline"
    assert spec.extra["owner"] == "override"
    assert spec.logging.enabled is True
    assert spec.logging.log_output is True
    assert spec.execution.timeout_s == 30


def test_load_config_before_register(tmp_path: Path) -> None:
    reg = AlgorithmRegistry()
    _write(
        tmp_path / "a.algometa.yaml",
        """
- name: demo
  version: v1
  category: unit
  algorithm_type: Prediction
  description: override
""".strip(),
    )
    reg.load_config(tmp_path)
    reg.register(_build_spec())
    spec = reg.get("demo", "v1")
    assert spec.description == "override"


def test_load_config_ordering(tmp_path: Path) -> None:
    reg = AlgorithmRegistry()
    reg.register(_build_spec())
    _write(
        tmp_path / "a.algometa.yaml",
        """
- name: demo
  version: v1
  category: unit
  algorithm_type: Prediction
  description: first
""".strip(),
    )
    _write(
        tmp_path / "b.algometa.yaml",
        """
- name: demo
  version: v1
  category: unit
  algorithm_type: Prediction
  description: second
""".strip(),
    )
    reg.load_config(tmp_path)
    spec = reg.get("demo", "v1")
    assert spec.description == "second"
