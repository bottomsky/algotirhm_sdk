from __future__ import annotations

import importlib
import os
from typing import List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from ..core.executor import DispatchingExecutor
from ..core.registry import AlgorithmRegistry, get_registry
from ..observability.metrics import InMemoryMetrics
from ..observability.tracing import InMemoryTracer
from ..protocol.models import AlgorithmRequest, api_error, api_success
from .service import AlgorithmHttpService, ObservationHooks

# Initialize global metrics and tracer
_metrics = InMemoryMetrics()
_tracer = InMemoryTracer()


def load_modules(modules: List[str]) -> None:
    """Import modules to trigger algorithm registration."""
    for module_path in modules:
        if not module_path:
            continue
        try:
            importlib.import_module(module_path)
            print(f"Loaded module: {module_path}")
        except Exception as e:
            print(f"Failed to load module {module_path}: {e}")


def create_app(registry: Optional[AlgorithmRegistry] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    reg = registry or get_registry()

    # Configure hooks for metrics and tracing
    hooks = ObservationHooks(
        on_start=lambda req: (_metrics.on_start(req), _tracer.on_start(req)),
        on_complete=lambda req, res: (
            _metrics.on_complete(req, res),
            _tracer.on_complete(req, res),
        ),
        on_error=lambda req, res: (
            _metrics.on_error(req, res),
            _tracer.on_error(req, res),
        ),
    )

    # Initialize service
    service = AlgorithmHttpService(
        registry=reg, executor=DispatchingExecutor(), observation=hooks
    )
    service.start()

    app = FastAPI(title="Algorithm Service")

    @app.get("/healthz")
    async def healthz():
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        """Readiness probe."""
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return PlainTextResponse(_metrics.render_prometheus_text())

    @app.get("/algorithms")
    async def list_algorithms():
        """List all registered algorithms."""
        specs = reg.list()
        data = [
            {
                "name": s.name,
                "version": s.version,
                "description": s.description,
            }
            for s in specs
        ]
        return api_success(data=data)

    @app.get("/algorithms/{name}/{version}/schema")
    async def get_schema(name: str, version: str):
        """Get input/output schema for an algorithm."""
        try:
            spec = reg.get(name, version)
            return api_success(
                data={
                    "input": spec.input_schema(),
                    "output": spec.output_schema(),
                    "execution": spec.execution.model_dump(),
                }
            )
        except Exception as e:
            return api_error(code=404, message=str(e))

    @app.post("/algorithms/{name}/{version}")
    async def invoke_algorithm(
        name: str, version: str, request: AlgorithmRequest
    ):
        """Execute a specific algorithm."""
        try:
            response = service.invoke(name, version, request)
            return response
        except Exception as e:
            return api_error(code=500, message=str(e))

    @app.on_event("shutdown")
    def shutdown_event():
        service.shutdown()

    return app


class Server:
    @staticmethod
    def run():
        run()


def run():
    """Start uvicorn server with configuration from environment."""
    load_dotenv()

    host = os.getenv("SERVICE_HOST", "127.0.0.1")
    port = int(os.getenv("SERVICE_PORT", "8000"))

    # Load modules to register algorithms
    modules_str = os.getenv("ALGO_MODULES", "")
    if modules_str:
        load_modules([m.strip() for m in modules_str.split(",")])

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
