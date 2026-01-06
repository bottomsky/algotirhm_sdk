from __future__ import annotations

import hashlib
import importlib
import importlib.util
import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles

from ...core.executor import DispatchingExecutor
from ...core.registry import AlgorithmRegistry, get_registry
from ...logging import configure_logging as configure_sdk_logging
from ...logging import get_event_logger
from ...protocol.models import AlgorithmRequest, api_error, api_success
from ...runtime import (
    AlreadyInStateError,
    InvalidTransitionError,
    ServiceLifecycleProtocol,
    ServiceState,
)
from ...runtime.factory import build_service_runtime
from ...service_registry.catalog import (
    build_algorithm_catalog,
    fetch_registry_algorithm_catalogs,
)
from ...service_registry.config import load_config as load_registry_config
from ...service_registry.errors import ServiceRegistryError

_LOGGER = logging.getLogger(__name__)
_EVENT_LOGGER = get_event_logger()


class _AccessLogExcludePathsFilter(logging.Filter):
    def __init__(self, excluded_paths: set[str]):
        super().__init__()
        self._excluded_paths = excluded_paths

    def filter(self, record: logging.LogRecord) -> bool:
        request_line = getattr(record, "request_line", None)
        if isinstance(request_line, str) and request_line:
            parts = request_line.split()
            if len(parts) >= 2:
                path = parts[1]
                if path in self._excluded_paths:
                    return False

        message = record.getMessage()
        for path in self._excluded_paths:
            if f" {path} " in message or f'"GET {path} ' in message:
                return False
        return True


def _install_uvicorn_access_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")

    excluded = {"/healthz"}
    marker = "_algo_sdk_access_filter_installed"
    if getattr(logger, marker, False):
        return
    logger.addFilter(_AccessLogExcludePathsFilter(excluded))
    setattr(logger, marker, True)


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


def _get_env_bool_default(name: str, default: bool) -> bool:
    value = _get_env_bool(name)
    return default if value is None else value


def _get_env_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_path(path: str | None, fallback: str) -> str:
    if not path or not path.strip():
        return fallback
    path = path.strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def _get_env_path(name: str) -> Path | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _resolve_swagger_static_dir() -> Path:
    env_path = _get_env_path("SERVICE_SWAGGER_STATIC_DIR")
    if env_path is not None:
        return env_path
    return Path.cwd() / "assets" / "swagger-ui"


def _resolve_env_path(env_path: str | os.PathLike[str] | None) -> Path | None:
    if env_path is not None:
        env_text = str(env_path).strip()
        if env_text:
            return Path(env_text).expanduser()
        return None
    env_text = os.getenv("SERVICE_ENV_PATH", "").strip()
    if env_text:
        return Path(env_text).expanduser()
    return Path.cwd() / ".env"


def _load_env_file(env_path: str | os.PathLike[str] | None) -> None:
    resolved = _resolve_env_path(env_path)
    if resolved is None:
        load_dotenv()
        return
    if resolved.exists():
        load_dotenv(resolved)
        return
    load_dotenv()


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


def _split_module_spec(module_spec: str) -> tuple[str, str | None]:
    if ":" not in module_spec:
        return module_spec, None
    if (
        len(module_spec) > 2
        and module_spec[1] == ":"
        and module_spec[2:3] in {"\\", "/"}
    ):
        last_colon = module_spec.rfind(":")
        if last_colon == 1:
            return module_spec, None
        module_path = module_spec[:last_colon].strip()
        index: int = last_colon + 1
        attr = module_spec[index:].strip()
        return module_path, attr or None
    module_path, attr = module_spec.rsplit(":", 1)
    module_path = module_path.strip()
    attr = attr.strip()
    return module_path, attr or None


def _is_filesystem_path(module_path: str) -> bool:
    path = Path(module_path)
    if path.is_absolute() or path.exists():
        return True
    if path.suffix == ".py":
        return True
    return "\\" in module_path or "/" in module_path


def _make_module_name(path: Path) -> str:
    stem = re.sub(r"\W+", "_", path.stem)
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    return f"algo_dynamic_{stem}_{digest}"


def _load_module_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        _make_module_name(path), path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from path: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_algorithm_modules(modules: List[str]) -> None:
    """Import modules or file paths to trigger algorithm registration."""
    for module_spec in modules:
        if not module_spec:
            continue
        try:
            module_path, attr = _split_module_spec(module_spec)
            module: ModuleType
            if _is_filesystem_path(module_path):
                path = Path(module_path)
                if not path.is_absolute():
                    path = (Path.cwd() / path).resolve()
                if path.is_dir():
                    path = path / "__init__.py"
                if not path.exists():
                    raise FileNotFoundError(f"No module at {path}")
                module = _load_module_from_path(path)
            else:
                module = importlib.import_module(module_path)
            if attr:
                getattr(module, attr)
            _EVENT_LOGGER.info(
                "Loaded algorithm module: %s",
                module_spec,
                logger=_LOGGER,
            )
        except Exception:
            _EVENT_LOGGER.exception(
                "Failed to load module %s",
                module_spec,
                logger=_LOGGER,
            )


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
    swagger_enabled = _get_env_bool_default("SERVICE_SWAGGER_ENABLED", True)
    swagger_docs_path = _normalize_path(
        os.getenv("SERVICE_SWAGGER_PATH", "/docs"),
        "/docs",
    )
    swagger_offline_enabled = _get_env_bool_default(
        "SERVICE_SWAGGER_OFFLINE", False
    )
    docs_url = swagger_docs_path if swagger_enabled else None
    openapi_url = "/openapi.json" if swagger_enabled else None
    redoc_url = "/redoc" if swagger_enabled else None
    swagger_static_dir: Path | None = None
    use_offline_swagger = False
    if swagger_enabled and swagger_offline_enabled:
        swagger_static_dir = _resolve_swagger_static_dir()
        if swagger_static_dir.exists():
            docs_url = None
            redoc_url = None
            use_offline_swagger = True
        else:
            docs_url = None
            redoc_url = None
            _LOGGER.warning(
                "Swagger offline enabled but static dir missing: %s",
                swagger_static_dir,
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        try:
            _install_uvicorn_access_log_filter()
            await runtime.provisioning(reason="startup")
            await runtime.ready(reason="startup")
            await runtime.running(reason="startup")
            yield
        finally:
            try:
                await runtime.shutdown(reason="shutdown")
            except AlreadyInStateError:
                pass

    app = FastAPI(
        title="Algorithm Service",
        lifespan=lifespan,
        docs_url=docs_url,
        openapi_url=openapi_url,
        redoc_url=redoc_url,
    )

    if use_offline_swagger and swagger_static_dir is not None:
        app.mount(
            "/swagger-ui",
            StaticFiles(directory=str(swagger_static_dir)),
            name="swagger-ui",
        )

        @app.get(swagger_docs_path, include_in_schema=False)
        async def swagger_ui_html():
            openapi = openapi_url or "/openapi.json"
            html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{app.title} - Swagger UI</title>
    <link rel="stylesheet" href="/swagger-ui/swagger-ui.css" />
    <link rel="icon" href="/swagger-ui/favicon.png" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="/swagger-ui/swagger-ui-bundle.js"></script>
    <script src="/swagger-ui/swagger-ui-standalone-preset.js"></script>
    <script>
      window.onload = () => {{
        const ui = SwaggerUIBundle({{
          url: "{openapi}",
          dom_id: "#swagger-ui",
          presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
          layout: "BaseLayout"
        }});
        window.ui = ui;
      }};
    </script>
  </body>
</html>
"""
            return HTMLResponse(html)

    if _get_env_bool_default("CORS_ENABLED", False):
        allow_origins = _get_env_list("CORS_ALLOW_ORIGINS")
        allow_origin_regex = (
            os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip() or None
        )
        allow_methods = _get_env_list("CORS_ALLOW_METHODS") or ["*"]
        allow_headers = _get_env_list("CORS_ALLOW_HEADERS") or ["*"]
        allow_credentials = _get_env_bool_default(
            "CORS_ALLOW_CREDENTIALS", False
        )

        if not allow_origins and not allow_origin_regex:
            allow_origins = ["*"]
        if allow_credentials and "*" in allow_origins:
            allow_credentials = False
            _EVENT_LOGGER.warning(
                "CORS_ALLOW_CREDENTIALS ignored with wildcard origins",
                logger=_LOGGER,
            )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_origin_regex=allow_origin_regex,
            allow_credentials=allow_credentials,
            allow_methods=allow_methods,
            allow_headers=allow_headers,
        )

    admin_enabled = _get_env_bool("SERVICE_ADMIN_ENABLED") or False

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/healthz", status_code=307)

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
                "algorithm_type": s.algorithm_type.value,
            }
            for s in specs
        ]
        return api_success(data=data)

    @app.get("/service/info")
    async def service_info():
        """Describe the current service instance and its algorithms."""
        registry_config = load_registry_config()
        catalog = build_algorithm_catalog(registry_config, reg.list())
        return api_success(
            data={
                "service": {
                    "name": registry_config.service_name,
                    "instance_id": registry_config.instance_id,
                    "version": registry_config.service_version,
                    "host": registry_config.service_host,
                    "port": registry_config.service_port,
                },
                "base_url": catalog.get("base_url"),
                "list_url": catalog.get("list_url"),
                "algorithms": catalog.get("algorithms", []),
            }
        )

    @app.get("/algorithms/{name}/{version}/schema")
    async def get_schema(name: str, version: str):
        """Get input/output schema for an algorithm."""
        try:
            spec = reg.get(name, version)
            hyper_schema = spec.hyperparams_schema()
            hyper_fields = spec.hyperparams_fields()
            hyperparams = None
            if hyper_schema is not None:
                hyperparams = {
                    "schema": hyper_schema,
                    "fields": hyper_fields or [],
                }
            return api_success(
                data={
                    "input": spec.input_schema(),
                    "output": spec.output_schema(),
                    "execution": _execution_to_dict(spec.execution),
                    "algorithm_type": spec.algorithm_type.value,
                    "hyperparams": hyperparams,
                }
            )
        except Exception as e:
            return api_error(code=404, message=str(e))

    @app.get("/registry/algorithms")
    async def list_registry_algorithms(
        prefix: str = "algo_services/",
        healthy_only: bool = True,
    ):
        """List algorithms registered in the service registry."""
        try:
            catalogs, errors = fetch_registry_algorithm_catalogs(
                kv_prefix=prefix,
                healthy_only=healthy_only,
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


def run(*, env_path: str | os.PathLike[str] | None = None) -> None:
    """Start uvicorn server with configuration from environment."""
    _load_env_file(env_path)
    configure_sdk_logging()

    bind_host = os.getenv("SERVICE_BIND_HOST", "127.0.0.1")
    port = int(os.getenv("SERVICE_PORT", "8000"))

    # Load modules to register algorithms
    modules_str = os.getenv("ALGO_MODULES", "")
    if modules_str:
        load_algorithm_modules([m.strip() for m in modules_str.split(",")])

    app = create_app()
    uvicorn.run(app, host=bind_host, port=port)


if __name__ == "__main__":
    run()
