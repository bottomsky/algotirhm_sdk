import pytest

from algo_sdk import ServiceRegistryConfig
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
