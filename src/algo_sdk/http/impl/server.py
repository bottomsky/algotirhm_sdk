from __future__ import annotations

import logging
import importlib
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from enum import Enum
from typing import List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse

from ...runtime import (
    AlreadyInStateError,
    InvalidTransitionError,
    ServiceLifecycleProtocol,
    ServiceState,
)
from ...core.executor import DispatchingExecutor
from ...core.registry import AlgorithmRegistry, get_registry
from ...protocol.models import AlgorithmRequest, api_error, api_success
from ...runtime.factory import build_service_runtime
from ...service_registry.catalog import fetch_registry_algorithm_catalogs
from ...service_registry.errors import ServiceRegistryError

_LOGGER = logging.getLogger(__name__)


def _get_env_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return int(raw)


def _get_env_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return float(raw)


def _get_env_bool(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    raw = raw.strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid bool env var {name}={raw!r}")


def _build_executor_from_env() -> DispatchingExecutor:
    global_max_workers = _get_env_int("EXECUTOR_GLOBAL_MAX_WORKERS")
    global_queue_size = _get_env_int("EXECUTOR_GLOBAL_QUEUE_SIZE")
    global_kill_tree = _get_env_bool("EXECUTOR_KILL_TREE")
    global_kill_grace_s = _get_env_float("EXECUTOR_KILL_GRACE_S")

    kwargs: dict[str, object] = {}
    if global_max_workers is not None:
        kwargs["global_max_workers"] = global_max_workers
    if global_queue_size is not None:
        kwargs["global_queue_size"] = global_queue_size
    if global_kill_tree is not None:
        kwargs["global_kill_tree"] = global_kill_tree
    if global_kill_grace_s is not None:
        kwargs["global_kill_grace_s"] = global_kill_grace_s

    return DispatchingExecutor(**kwargs)  # type: ignore[arg-type]


def _execution_to_dict(execution: object) -> dict[str, object]:
    payload: dict[str, object] = {}
    if hasattr(execution, "__dataclass_fields__"):
        payload = asdict(execution)  # type: ignore[arg-type]
    elif hasattr(execution, "__dict__"):
        payload = dict(execution.__dict__)  # type: ignore[attr-defined]

    for key, value in list(payload.items()):
        if isinstance(value, Enum):
            payload[key] = value.value
    return payload


def load_algorithm_modules(modules: List[str]) -> None:
    """Import modules to trigger algorithm registration."""
    for module_path in modules:
        if not module_path:
            continue
        try:
            importlib.import_module(module_path)
            _LOGGER.info("Loaded algorithm module: %s", module_path)
        except Exception:
            _LOGGER.exception("Failed to load module %s", module_path)


def create_app(registry: Optional[AlgorithmRegistry] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    reg = registry or get_registry()

    bundle = build_service_runtime(
        registry=reg,
        executor=_build_executor_from_env(),
    )
    service = bundle.service
    runtime = bundle.runtime
    metrics_store = bundle.metrics

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        try:
            await runtime.provisioning(reason="startup")
            await runtime.ready(reason="startup")
            await runtime.running(reason="startup")
            yield
        finally:
            try:
                await runtime.shutdown(reason="shutdown")
            except AlreadyInStateError:
                pass

    app = FastAPI(title="Algorithm Service", lifespan=lifespan)

    admin_enabled = _get_env_bool("SERVICE_ADMIN_ENABLED") or False

    @app.get("/healthz")
    async def healthz():
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        """Readiness probe."""
        service_runtime: ServiceLifecycleProtocol | None = getattr(
            app.state, "runtime", None
        )
        if service_runtime is None or not service_runtime.accepting_requests:
            state = (
                service_runtime.state.value if service_runtime else "Unknown"
            )
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "state": state},
            )
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return PlainTextResponse(metrics_store.render_prometheus_text())

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
                    "execution": _execution_to_dict(spec.execution),
                }
            )
        except Exception as e:
            return api_error(code=404, message=str(e))

    @app.get("/registry/algorithms")
    async def list_registry_algorithms(prefix: str = "services/"):
        """List algorithms registered in the service registry."""
        try:
            catalogs, errors = fetch_registry_algorithm_catalogs(
                kv_prefix=prefix
            )
        except ServiceRegistryError as exc:
            return api_error(code=502, message=str(exc))

        algorithms: list[dict[str, object]] = []
        for catalog in catalogs:
            service_name = catalog.get("service")
            items = catalog.get("algorithms", [])
            if not isinstance(items, list):
                continue
            for algo in items:
                if not isinstance(algo, dict):
                    continue
                entry = dict(algo)
                if service_name:
                    entry["service"] = service_name
                entry["kv_key"] = catalog.get("kv_key")
                algorithms.append(entry)

        return api_success(
            data={
                "catalogs": catalogs,
                "algorithms": algorithms,
                "errors": errors,
            }
        )

    @app.post("/algorithms/{name}/{version}")
    async def invoke_algorithm(
        name: str, version: str, request: AlgorithmRequest
    ):
        """Execute a specific algorithm."""
        service_runtime: ServiceLifecycleProtocol | None = getattr(
            app.state, "runtime", None
        )
        if (
            service_runtime is not None
            and not service_runtime.accepting_requests
        ):
            state = service_runtime.state
            status_code = 503
            if state is ServiceState.DRAINING:
                status_code = 429
            envelope = api_error(
                code=status_code,
                message=f"service not accepting requests: {state.value}",
                request_id=request.requestId,
                context=request.context,
            )
            return JSONResponse(
                status_code=status_code,
                content=envelope.model_dump(by_alias=True),
            )
        try:
            response = service.invoke(name, version, request)
            return response
        except Exception as e:
            return api_error(code=500, message=str(e))

    if admin_enabled:

        @app.get("/admin/lifecycle/state")
        async def lifecycle_state():
            service_runtime: ServiceLifecycleProtocol | None = getattr(
                app.state, "runtime", None
            )
            if service_runtime is None:
                return JSONResponse(
                    status_code=503,
                    content={"status": "not_ready", "state": "Unknown"},
                )
            return {
                "state": service_runtime.state.value,
                "accepting_requests": service_runtime.accepting_requests,
            }

        def _lifecycle_error(exc: Exception) -> JSONResponse:
            if isinstance(exc, (AlreadyInStateError, InvalidTransitionError)):
                return JSONResponse(
                    status_code=409,
                    content={"error": type(exc).__name__, "message": str(exc)},
                )
            return JSONResponse(
                status_code=500,
                content={"error": type(exc).__name__, "message": str(exc)},
            )

        @app.post("/admin/lifecycle/degraded")
        async def lifecycle_degraded():
            try:
                await runtime.degraded(reason="admin")
                return {"state": runtime.state.value}
            except Exception as exc:
                return _lifecycle_error(exc)

        @app.post("/admin/lifecycle/draining")
        async def lifecycle_draining():
            try:
                await runtime.draining(reason="admin")
                return {"state": runtime.state.value}
            except Exception as exc:
                return _lifecycle_error(exc)

        @app.post("/admin/lifecycle/running")
        async def lifecycle_running():
            try:
                await runtime.running(reason="admin")
                return {"state": runtime.state.value}
            except Exception as exc:
                return _lifecycle_error(exc)

        @app.post("/admin/lifecycle/shutdown")
        async def lifecycle_shutdown():
            try:
                await runtime.shutdown(reason="admin")
                return {"state": runtime.state.value}
            except Exception as exc:
                return _lifecycle_error(exc)

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
        load_algorithm_modules([m.strip() for m in modules_str.split(",")])

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
