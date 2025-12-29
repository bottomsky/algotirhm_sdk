from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from algo_sdk.core.base_model_impl import BaseModel
from algo_sdk.core.metadata import AlgorithmSpec, AlgorithmType, ExecutionConfig
from algo_sdk.core.registry import AlgorithmRegistry
from algo_sdk.http.server import create_app


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
