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
        algorithm_type=AlgorithmType.PLANNING,
        description="test",
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


def test_readyz(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_list_algorithms(client):
    response = client.get("/algorithms")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert any(a["name"] == "test_algo" for a in data["data"])


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
        algorithm_type=AlgorithmType.PLANNING,
        description="test",
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
    registry = AlgorithmRegistry()

    def _fake_fetch_registry_algorithm_catalogs(
        *, kv_prefix: str, healthy_only: bool = False
    ):
        _ = (kv_prefix, healthy_only)
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
        assert len(data["catalogs"]) == 2
        assert len(data["algorithms"]) == 1
        assert data["algorithms"][0]["service"] == "svc-a"


def test_swagger_docs_disabled(monkeypatch):
    monkeypatch.setenv("SERVICE_SWAGGER_ENABLED", "false")
    app = create_app(AlgorithmRegistry())
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404


def test_swagger_open_on_startup(monkeypatch):
    monkeypatch.setenv("SERVICE_SWAGGER_ENABLED", "true")
    monkeypatch.setenv("SERVICE_SWAGGER_OPEN_ON_STARTUP", "true")
    monkeypatch.setenv("SERVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("SERVICE_PORT", "8000")

    opened = {}

    def fake_open(url):
        opened["url"] = url
        return True

    monkeypatch.setattr(
        http_server,
        "_open_swagger",
        fake_open,
    )

    app = create_app(AlgorithmRegistry())
    with TestClient(app):
        pass

    assert opened["url"] == "http://127.0.0.1:8000/docs"


def test_swagger_open_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("SERVICE_SWAGGER_ENABLED", "false")
    monkeypatch.setenv("SERVICE_SWAGGER_OPEN_ON_STARTUP", "true")

    opened = []

    def fake_open(url):
        opened.append(url)
        return True

    monkeypatch.setattr(
        http_server,
        "_open_swagger",
        fake_open,
    )

    app = create_app(AlgorithmRegistry())
    with TestClient(app):
        pass

    assert opened == []



def test_swagger_open_defaults_to_vscode(monkeypatch):
    monkeypatch.delenv("SERVICE_SWAGGER_OPEN_ON_STARTUP", raising=False)
    monkeypatch.setenv("SERVICE_SWAGGER_ENABLED", "true")
    monkeypatch.setenv("VSCODE_PID", "12345")
    monkeypatch.setenv("SERVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("SERVICE_PORT", "8000")

    opened = {}

    def fake_open(url):
        opened["url"] = url
        return True

    monkeypatch.setattr(
        http_server,
        "_open_swagger",
        fake_open,
    )

    app = create_app(AlgorithmRegistry())
    with TestClient(app):
        pass

    assert opened["url"] == "http://127.0.0.1:8000/docs"
