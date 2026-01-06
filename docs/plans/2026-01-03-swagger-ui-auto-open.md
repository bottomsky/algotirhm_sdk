# Swagger UI Auto-Open Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Swagger UI exposure in the algo_sdk HTTP server with env-configurable auto-open on startup.

**Architecture:** Read swagger flags from environment (dotenv already loaded in `run`). When enabled, set FastAPI `docs_url`/`openapi_url` and trigger a lifespan-time browser open if `SERVICE_SWAGGER_OPEN_ON_STARTUP=true`. Default behavior keeps Swagger enabled and does not auto-open.

**Tech Stack:** Python 3.11, FastAPI, pytest, python-dotenv, standard library `webbrowser`.

### Task 1: Swagger UI config tests + implementation

**Files:**

- Modify: `tests/http/test_server.py`
- Modify: `src/algo_sdk/http/impl/server.py`
- Modify: `.env`

**Step 1: Write the failing tests** (follow @superpowers:test-driven-development)

Add the import near the top of `tests/http/test_server.py`:

```python
from types import SimpleNamespace
```

Append these tests near the bottom of `tests/http/test_server.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/http/test_server.py -k swagger -v`

Expected: FAIL because swagger config and `_open_swagger` do not exist yet.

**Step 3: Write minimal implementation**

Update `src/algo_sdk/http/impl/server.py` to add swagger config parsing and startup open:

```python
import webbrowser
```

```python
def _get_env_bool_default(name: str, default: bool) -> bool:
    value = _get_env_bool(name)
    return default if value is None else value


def _normalize_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def _normalize_path(path: str, fallback: str) -> str:
    if not path or not path.strip():
        return fallback
    path = path.strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def _open_swagger(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
    except Exception:
        _LOGGER.exception("Failed to open Swagger UI")
```

Inside `create_app` before `@asynccontextmanager`:

```python
swagger_enabled = _get_env_bool_default("SERVICE_SWAGGER_ENABLED", True)
swagger_open_on_startup = _get_env_bool_default(
    "SERVICE_SWAGGER_OPEN_ON_STARTUP", False
)
swagger_docs_path = _normalize_path(
    os.getenv("SERVICE_SWAGGER_PATH", "/docs"),
    "/docs",
)
docs_url = swagger_docs_path if swagger_enabled else None
openapi_url = "/openapi.json" if swagger_enabled else None
redoc_url = "/redoc" if swagger_enabled else None

swagger_url = None
if swagger_enabled and swagger_open_on_startup:
    host = _normalize_host(os.getenv("SERVICE_HOST", "127.0.0.1"))
    port = int(os.getenv("SERVICE_PORT", "8000"))
    swagger_url = f"http://{host}:{port}{swagger_docs_path}"
```

Update `lifespan` to open Swagger UI on startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = runtime
    try:
        await runtime.provisioning(reason="startup")
        await runtime.ready(reason="startup")
        await runtime.running(reason="startup")
        if swagger_url is not None:
            _open_swagger(swagger_url)
        yield
    finally:
        ...
```

Pass the docs settings into FastAPI:

```python
app = FastAPI(
    title="Algorithm Service",
    lifespan=lifespan,
    docs_url=docs_url,
    openapi_url=openapi_url,
    redoc_url=redoc_url,
)
```

Update `.env` with new config:

```env
# Swagger UI Configuration
SERVICE_SWAGGER_ENABLED=true
SERVICE_SWAGGER_OPEN_ON_STARTUP=false
# Optional: override Swagger UI path (default /docs)
# SERVICE_SWAGGER_PATH=/docs
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/http/test_server.py -k swagger -v`

Expected: PASS for swagger tests.

**Step 5: Commit**

```bash
git add tests/http/test_server.py src/algo_sdk/http/impl/server.py .env
git commit -m "feat: add swagger ui config and optional auto-open"
```
