import asyncio
import json

from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    BaseModel,
    ExecutionConfig,
    MemoryRegistry,
    ServiceRegistration,
    ServiceRegistryConfig,
    build_service_runtime,
    fetch_registry_algorithm_catalogs,
)


class Req(BaseModel):
    value: int


class Resp(BaseModel):
    doubled: int


def mock_algo(req: Req) -> Resp:
    return Resp(doubled=req.value * 2)


def test_service_start_registers_and_publishes_catalog() -> None:
    algo_registry = AlgorithmRegistry()
    spec = AlgorithmSpec(
        name="test_algo",
        version="v1",
        algorithm_type=AlgorithmType.PLANNING,
        description="test",
        input_model=Req,
        output_model=Resp,
        execution=ExecutionConfig(),
        entrypoint=mock_algo,
        is_class=False,
    )
    algo_registry.register(spec)

    registry = MemoryRegistry()
    config = ServiceRegistryConfig(
        host="http://localhost:8500",
        enabled=True,
        service_name="algo-core-service",
        instance_id="algo-core-service-1",
        service_host="127.0.0.1",
        service_port=8000,
        health_check_interval=10,
        health_check_timeout=5,
    )

    bundle = build_service_runtime(
        registry=algo_registry,
        service_registry=registry,
        service_registry_config=config,
    )

    async def main() -> None:
        await bundle.runtime.provisioning()
        await bundle.runtime.ready()
        await bundle.runtime.running()

    asyncio.run(main())
    try:
        instances = registry.get_service(config.service_name)
        assert len(instances) == 1
        assert instances[0].service_id == "algo-core-service-1"
        assert instances[0].host == "127.0.0.1"
        assert instances[0].port == 8000

        catalogs, errors = fetch_registry_algorithm_catalogs(
            registry=registry,
            config=config,
        )
        assert errors == []
        assert len(catalogs) == 1
        assert catalogs[0]["service"] == "algo-core-service"
        assert any(
            algo["name"] == "test_algo"
            for algo in catalogs[0]["algorithms"]
        )
    finally:
        asyncio.run(bundle.runtime.shutdown())


def test_fetch_registry_catalogs_filters_unhealthy_instances() -> None:
    registry = MemoryRegistry()
    config = ServiceRegistryConfig(
        host="http://localhost:8500",
        enabled=True,
        service_name="svc-a",
        instance_id="svc-a-1",
        service_host="127.0.0.1",
        service_port=8000,
        health_check_interval=10,
        health_check_timeout=5,
    )
    registry.register(
        ServiceRegistration(
            service_name="svc-a",
            service_id="svc-a-1",
            host="127.0.0.1",
            port=8000,
        )
    )
    registry.set_kv(
        "algo_services/svc-a/svc-a-1/algorithms",
        json.dumps({"service": "svc-a", "algorithms": []}),
    )
    registry.set_kv(
        "algo_services/svc-b/svc-b-1/algorithms",
        json.dumps({"service": "svc-b", "algorithms": []}),
    )

    catalogs, errors = fetch_registry_algorithm_catalogs(
        registry=registry,
        config=config,
        healthy_only=True,
    )

    assert errors == []
    assert len(catalogs) == 1
    assert catalogs[0]["service"] == "svc-a"
