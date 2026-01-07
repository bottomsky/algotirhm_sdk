from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    BaseModel,
    ExecutionConfig,
    create_app,
    http_server,
)


class Req(BaseModel):
    value: int


class Resp(BaseModel):
    doubled: int


def mock_algo(req: Req) -> Resp:
    return Resp(doubled=req.value * 2)


@pytest.fixture
def client():
    registry = AlgorithmRegistry()
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
        input_model=Req,
        output_model=Resp,
        execution=ExecutionConfig(),
        entrypoint=mock_algo,
        is_class=False,
    )
    registry.register(spec)
    app = create_app(registry)
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_healthz(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/healthz"


def test_readyz(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_list_algorithms(client):
    response = client.get("/algorithms")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    algo = next(a for a in data["data"] if a["name"] == "test_algo")
    assert algo["created_time"] == "2026-01-06"
    assert algo["author"] == "qa"
    assert algo["category"] == "unit"
    assert algo["application_scenarios"] == "demo"
    assert algo["extra"] == {"owner": "unit"}


def test_invoke_algorithm(client):
    req_body = {
        "requestId": "test-1",
        "datetime": datetime.now(timezone.utc).isoformat(),
        "context": {"traceId": "trace-1"},
        "data": {"value": 5},
    }
    response = client.post("/algorithms/test_algo/v1", json=req_body)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["doubled"] == 10


def test_schema_includes_metadata(client):
    response = client.get("/algorithms/test_algo/v1/schema")
    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    assert data["created_time"] == "2026-01-06"
    assert data["author"] == "qa"
    assert data["category"] == "unit"
    assert data["application_scenarios"] == "demo"
    assert data["extra"] == {"owner": "unit"}


def test_metrics(client):
    # First invoke to generate metrics
    test_invoke_algorithm(client)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "requests_total" in response.text


def test_service_info(monkeypatch):
    monkeypatch.setenv("SERVICE_NAME", "algo-core-service")
    monkeypatch.setenv("SERVICE_VERSION", "1.2.3")
    monkeypatch.setenv("SERVICE_INSTANCE_ID", "algo-core-service-abc123")
    monkeypatch.setenv("SERVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("SERVICE_PORT", "8000")

    registry = AlgorithmRegistry()
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
        input_model=Req,
        output_model=Resp,
        execution=ExecutionConfig(),
        entrypoint=mock_algo,
        is_class=False,
    )
    registry.register(spec)

    app = create_app(registry)
    with TestClient(app) as client:
        response = client.get("/service/info")
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        data = payload["data"]
        service = data["service"]
        assert service["name"] == "algo-core-service"
        assert service["version"] == "1.2.3"
        assert service["instance_id"] == "algo-core-service-abc123"
        assert service["host"] == "127.0.0.1"
        assert service["port"] == 8000
        assert any(
            algo["name"] == "test_algo" and algo["version"] == "v1"
            for algo in data["algorithms"]
        )


def test_list_registry_algorithms(monkeypatch):
    monkeypatch.setenv("SERVICE_REGISTRY_ENABLED", "true")
    registry = AlgorithmRegistry()
    captured = {}

    def _fake_fetch_registry_algorithm_catalogs(
        *, kv_prefix: str, healthy_only: bool = False
    ):
        captured["kv_prefix"] = kv_prefix
        captured["healthy_only"] = healthy_only
        return (
            [
                {
                    "service": "svc-a",
                    "algorithms": [
                        {
                            "name": "algo-1",
                            "version": "v1",
                            "description": "demo",
                        }
                    ],
                },
                {
                    "service": "svc-b",
                    "algorithms": [],
                },
            ],
            [],
        )

    monkeypatch.setattr(
        http_server,
        "fetch_registry_algorithm_catalogs",
        _fake_fetch_registry_algorithm_catalogs,
    )

    app = create_app(registry)
    with TestClient(app) as client:
        response = client.get("/registry/algorithms")
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        data = payload["data"]
        assert captured["healthy_only"] is True
        assert len(data["catalogs"]) == 2
        assert len(data["algorithms"]) == 1
        assert data["algorithms"][0]["service"] == "svc-a"


def test_list_registry_algorithms_disabled(monkeypatch):
    monkeypatch.setenv("SERVICE_REGISTRY_ENABLED", "false")
    registry = AlgorithmRegistry()

    def _should_not_call(*, kv_prefix: str, healthy_only: bool = False):
        raise AssertionError(
            "fetch_registry_algorithm_catalogs should not be called"
        )

    monkeypatch.setattr(
        http_server,
        "fetch_registry_algorithm_catalogs",
        _should_not_call,
    )

    app = create_app(registry)
    with TestClient(app) as client:
        response = client.get("/registry/algorithms")
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 503
        assert payload["message"] == "service registry disabled"


def test_swagger_docs_disabled(monkeypatch):
    monkeypatch.setenv("SERVICE_SWAGGER_ENABLED", "false")
    app = create_app(AlgorithmRegistry())
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404


def test_module_dir_loading(monkeypatch, tmp_path):
    package_dir = tmp_path / "demo_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        """
from algo_sdk import Algorithm, BaseAlgorithm, BaseModel, AlgorithmType


class Req(BaseModel):
    value: int


class Resp(BaseModel):
    doubled: int


@Algorithm(
    name="demo",
    version="v1",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-01-06",
    author="qa",
    category="unit",
)
class DemoAlgo(BaseAlgorithm[Req, Resp]):
    def run(self, req: Req) -> Resp:  # type: ignore[override]
        return Resp(doubled=req.value * 2)


__all__ = ["DemoAlgo"]
""".strip(),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")

    monkeypatch.setenv("ALGO_MODULE_DIR", str(tmp_path))
    monkeypatch.delenv("ALGO_MODULES", raising=False)

    registry = AlgorithmRegistry()
    monkeypatch.setattr(http_server, "get_registry", lambda: registry)
    monkeypatch.setattr(http_server.uvicorn, "run", lambda *args, **kwargs: None)

    http_server.run(env_path=env_path)

    spec = registry.get("demo", "v1")
    assert spec.algorithm_type is AlgorithmType.PREDICTION
