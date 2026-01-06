import pytest

from algo_sdk import (
    AlgorithmSpec,
    AlgorithmType,
    BaseModel,
    ExecutionConfig,
    ServiceRegistryConfig,
)
from algo_sdk.service_registry.catalog import (
    _build_catalog_kv_key,
    build_algorithm_catalog,
)


def test_build_catalog_kv_key_uses_fallback_service_id_when_instance_id_missing() -> (
    None
):
    config = ServiceRegistryConfig(
        host="http://localhost:8500",
        enabled=True,
        service_name="algo-service",
        instance_id=None,
        service_host="host.docker.internal",
        service_port=8000,
        service_protocol="http",
    )

    key = _build_catalog_kv_key(config, kv_key=None)

    assert (
        key
        == "algo_services/algo-service/algo-service-host.docker.internal-8000-http/algorithms"
    )


def test_build_algorithm_catalog_populates_service_id_when_instance_id_missing() -> (
    None
):
    config = ServiceRegistryConfig(
        host="http://localhost:8500",
        enabled=True,
        service_name="algo-service",
        instance_id=None,
        service_host="host.docker.internal",
        service_port=8000,
        service_protocol="http",
    )

    catalog = build_algorithm_catalog(config, algorithms=[])

    assert (
        catalog["service_id"] == "algo-service-host.docker.internal-8000-http"
    )


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


def _algo(req: _Req) -> _Resp:
    return _Resp(doubled=req.value * 2)


def test_build_algorithm_catalog_includes_metadata() -> None:
    config = ServiceRegistryConfig(
        host="http://localhost:8500",
        enabled=True,
        service_name="algo-service",
        instance_id="instance-1",
        service_host="host.docker.internal",
        service_port=8000,
        service_protocol="http",
    )

    spec = AlgorithmSpec(
        name="test_algo",
        version="v1",
        algorithm_type=AlgorithmType.PROGRAMME,
        description="test",
        created_time="2026-01-06",
        author="qa",
        category="unit",
        application_scenarios="demo",
        extra={"owner": "unit"},
        input_model=_Req,
        output_model=_Resp,
        execution=ExecutionConfig(),
        entrypoint=_algo,
        is_class=False,
    )

    catalog = build_algorithm_catalog(config, algorithms=[spec])
    entry = catalog["algorithms"][0]
    assert entry["created_time"] == "2026-01-06"
    assert entry["author"] == "qa"
    assert entry["category"] == "unit"
    assert entry["application_scenarios"] == "demo"
    assert entry["extra"] == {"owner": "unit"}
