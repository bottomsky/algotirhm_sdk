# 入手手册

本文面向第一次接手本项目的开发者，重点说明环境配置、算法接入方式，以及 `@Algorithm` 装饰器的实际能力。

## 1. 环境配置

### 1.1 基础要求

- Python：`3.11` 及以上；推荐使用 `3.11`，与当前 `pyright` 配置保持一致。
- 依赖管理：推荐使用 `uv`。
- 启动入口：`python -m algo_core_service.main`，会自动读取项目根目录 `.env`。

### 1.2 `.venv` 切换到目标 Python 解释器

本项目要求优先使用仓库根目录下的 `.venv`。

如果你要把 `.venv` 绑定到另一套 Python 解释器，有两种处理方式：

1. 推荐方式：按目标解释器重建 `.venv`。
2. 快速方式：直接修改 `.venv\pyvenv.cfg` 中记录的解释器路径。

#### 方式一：重建 `.venv`

适合场景：

- 新机器首次拉起项目
- 你希望环境最干净、最稳定
- 修改解释器后不想保留旧虚拟环境状态

Windows 示例：

```powershell
py -0p
uv venv --python C:\Python311\python.exe
uv pip sync uv.lock
```

说明：

- `py -0p`：查看本机可用 Python 路径。
- `uv venv --python ...`：用指定解释器创建或重建 `.venv`。
- `uv pip sync uv.lock`：按锁文件安装依赖，避免环境漂移。

#### 方式二：直接修改 `.venv\pyvenv.cfg`

适合场景：

- 你已经有现成 `.venv`
- 你会提供明确的目标解释器路径
- 你希望快速切换，而不是重建环境

需要修改的文件：

```text
.venv\pyvenv.cfg
```

假设你提供的目标解释器是：

```text
C:\Python311\python.exe
```

那么这一种方法的修改规则是：

- `home`：改成解释器所在目录，例如 `C:\Python311`
- `executable`：如果文件里存在该字段，就改成完整解释器路径 `C:\Python311\python.exe`

示例一：只存在 `home`

```ini
home = C:\Python311
implementation = CPython
version_info = 3.11.9
include-system-site-packages = false
```

示例二：同时存在 `home` 和 `executable`

```ini
home = C:\Python311
implementation = CPython
version_info = 3.11.9
include-system-site-packages = false
executable = C:\Python311\python.exe
```

补充说明：

- 当前项目里的 `pyvenv.cfg` 主要至少会有 `home` 字段，通常先改它。
- 有些虚拟环境还会带 `executable` 或其它解释器相关字段，存在时一并改成你提供的新路径。
- 这种方式适合你已经确定目标 Python 路径，且希望快速复用现有 `.venv` 的场景。
- 如果修改后仍然出现解释器异常、包导入异常或脚本失效，优先回到“重建 `.venv`”方案。

常用检查命令：

```powershell
.\.venv\Scripts\python.exe -V
.\.venv\Scripts\python.exe -m pytest -q
```

如果只是临时激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 1.3 VS Code 使用项目解释器

仓库已经在 `.vscode/settings.json` 中将默认解释器指向：

```text
${workspaceFolder}\.venv\Scripts\python.exe
```

如果你重建了 `.venv`，通常不需要改配置，只要重新选择解释器即可：

1. `Ctrl+Shift+P`
2. 选择 `Python: Select Interpreter`
3. 选择当前仓库下的 `.venv\Scripts\python.exe`

调试配置 `.vscode/launch.json` 也已经固定使用该解释器。

### 1.4 `.env` 主要参数说明

项目默认会读取根目录 `.env`。下面是最常用的参数：

| 变量名 | 是否常改 | 说明 |
| --- | --- | --- |
| `SERVICE_BIND_HOST` | 常改 | Uvicorn 实际监听地址，例如 `0.0.0.0` 或 `127.0.0.1`。 |
| `SERVICE_PORT` | 常改 | 服务监听端口。 |
| `SERVICE_HOST` | 常改 | 服务对外声明的访问地址，主要给注册中心、健康检查和外部访问链接使用。 |
| `SERVICE_PROTOCOL` | 偶尔 | 对外访问协议，通常是 `http`。 |
| `SERVICE_REGISTRY_ENABLED` | 常改 | 是否启用服务注册。本地单机调试通常设为 `false`，接 Consul 时设为 `true`。 |
| `SERVICE_REGISTRY_HOST` | 偶尔 | Consul 地址，例如 `http://127.0.0.1:8500`。 |
| `SERVICE_NAME` | 偶尔 | 注册到服务中心时使用的服务名。 |
| `SERVICE_VERSION` | 偶尔 | 服务版本标识。 |
| `ALGO_MODULES` | 常改 | 启动时要导入的算法模块，默认是 `algo_core_service.algorithms`。 |
| `ALGO_MODULE_DIR` | 偶尔 | 额外算法包目录。用于从目录动态加载算法包。 |
| `ALGO_METADATA_CONFIG_DIR` | 偶尔 | 算法元数据覆盖配置目录，读取其中的 `*.algometa.yaml`。 |
| `EXECUTOR_GLOBAL_MAX_WORKERS` | 偶尔 | 全局执行器最大并发 worker 数。 |
| `EXECUTOR_GLOBAL_QUEUE_SIZE` | 偶尔 | 全局执行队列大小。 |
| `EXECUTOR_DEFAULT_TIMEOUT_S` | 偶尔 | 算法默认执行超时。 |
| `EXECUTOR_KILL_TREE` | 偶尔 | 超时后是否尝试回收整个进程树。 |
| `EXECUTOR_KILL_GRACE_S` | 偶尔 | 强制回收前的等待时间。 |
| `SERVICE_SWAGGER_ENABLED` | 常改 | 是否启用 Swagger。 |
| `SERVICE_SWAGGER_OFFLINE` | 偶尔 | 是否使用仓库内 `assets/swagger-ui/` 的离线 Swagger 静态资源。 |
| `SERVICE_ADMIN_ENABLED` | 偶尔 | 是否开放管理态生命周期接口。 |
| `CORS_ENABLED` | 偶尔 | 是否启用跨域。前后端联调时常用。 |
| `LOG_LEVEL` | 偶尔 | 日志级别，例如 `INFO`、`DEBUG`。 |

本地开发常见最小配置：

```dotenv
SERVICE_REGISTRY_ENABLED=false
SERVICE_HOST=127.0.0.1
SERVICE_BIND_HOST=0.0.0.0
SERVICE_PORT=8000
ALGO_MODULES=algo_core_service.algorithms
SERVICE_SWAGGER_ENABLED=true
SERVICE_SWAGGER_OFFLINE=true
```

几个容易混淆的点：

- `SERVICE_BIND_HOST` 是“服务绑定在哪张网卡上监听”。
- `SERVICE_HOST` 是“服务对外告诉别人自己是谁”。
- 本地不接 Consul 时，`SERVICE_REGISTRY_ENABLED=false` 更合适，否则会尝试做服务注册。

### 1.5 启动方式

推荐直接使用项目脚本：

```powershell
.\scripts\run_algo_core_service.ps1
```

或者使用模块方式启动：

```powershell
.\.venv\Scripts\python.exe -m algo_core_service.main
```

启动后可访问：

- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/readyz`
- `http://127.0.0.1:8000/algorithms`
- `http://127.0.0.1:8000/docs`

### 1.6 VS Code 离线插件安装

如果开发机不能联网，可以通过 `.vsix` 离线安装插件。

建议至少安装这些插件：

- `ms-python.python`
- `ms-python.vscode-pylance`
- `ms-python.black-formatter`

安装步骤：

1. 在可联网机器上下载对应插件的 `.vsix` 文件。
2. 把 `.vsix` 拷贝到目标机器。
3. 打开 VS Code。
4. 进入扩展页。
5. 右上角 `...` -> `Install from VSIX...`
6. 选择对应 `.vsix` 安装。

安装后建议确认：

- Python 插件已启用。
- Pylance 已启用。
- Black Formatter 已启用。
- 当前工作区解释器已经切到 `.venv\Scripts\python.exe`。

## 2. 如何编写算法

### 2.1 放置位置

当前默认配置下，算法代码应放在：

```text
src/algo_core_service/algorithms/
```

例如新增一个算法文件：

```text
src/algo_core_service/algorithms/my_algo.py
```

### 2.2 为什么还要修改 `__init__.py`

当前服务启动时默认加载的是整个模块包：

```dotenv
ALGO_MODULES=algo_core_service.algorithms
```

随后注册器会对 `algo_core_service.algorithms` 执行 `register_from_module(module)`，而这段逻辑只扫描包里的 `__all__` 导出项。

因此新增算法后，必须在：

```text
src/algo_core_service/algorithms/__init__.py
```

里做两件事：

1. 导入你的算法类。
2. 把算法类名加入 `__all__`。

示例：

```python
from .my_algo import MyAlgorithm

__all__ = [
    "MyAlgorithm",
]
```

如果你只新增了 `my_algo.py`，但没有在 `__init__.py` 暴露，当前默认启动方式下该算法不会被注册。

### 2.3 编写算法的基本模板

当前仓库使用“类式算法”，推荐从 `algo_sdk` 直接导入公共 API：

```python
from algo_sdk import Algorithm, BaseAlgorithm, BaseModel
from algo_sdk.core import AlgorithmType


class MyRequest(BaseModel):
    value: int


class MyResponse(BaseModel):
    doubled: int


@Algorithm(
    name="MyAlgorithm",
    version="v1",
    algorithm_type=AlgorithmType.PREDICTION,
    description="示例算法",
    created_time="2026-02-28",
    author="your-name",
    category="Demo",
)
class MyAlgorithm(BaseAlgorithm[MyRequest, MyResponse]):
    def run(self, req: MyRequest) -> MyResponse:
        return MyResponse(doubled=req.value * 2)
```

### 2.4 带超参数的写法

如果算法除了请求体 `data` 之外，还需要额外参数，则第二个参数必须继承 `HyperParams`：

```python
from algo_sdk import Algorithm, BaseAlgorithm, BaseModel, HyperParams
from algo_sdk.core import AlgorithmType


class MyRequest(BaseModel):
    value: int


class MyParams(HyperParams):
    bias: int = 0


class MyResponse(BaseModel):
    result: int


@Algorithm(
    name="MyAlgorithmWithParams",
    version="v1",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-02-28",
    author="your-name",
    category="Demo",
)
class MyAlgorithmWithParams(BaseAlgorithm[MyRequest, MyResponse]):
    def run(self, req: MyRequest, params: MyParams) -> MyResponse:
        return MyResponse(result=req.value + params.bias)
```

请求中的 `hyperParams` 会按这个模型做校验和绑定。

### 2.5 编写算法时的实际约束

为避免注册失败或运行时问题，建议遵守下面这些规则：

- 算法类必须继承 `BaseAlgorithm`。
- 算法类必须是模块顶层定义，不要写在函数内部。
- `run()` 的输入和输出都必须是 Pydantic 模型。
- 如果有第二个参数，它必须继承 `HyperParams`。
- 新增算法后必须在 `algorithms/__init__.py` 中导出。
- 由于默认执行器涉及进程池，模型类和算法类都应保持可导入、可序列化。

## 3. `@Algorithm` 装饰器功能介绍

### 3.1 作用

`@Algorithm` 的核心作用不是“立刻把算法注册进服务”，而是先把算法元数据挂到类上，形成 `__algo_meta__` 标记。

后续在服务启动阶段：

1. 导入 `ALGO_MODULES` 指定的模块。
2. 注册器扫描模块 `__all__`。
3. 找到带 `__algo_meta__` 的算法类。
4. 结合 `run()` 方法签名生成 `AlgorithmSpec` 并注册。

换句话说，装饰器负责“声明算法”，注册器负责“正式收录算法”。

### 3.2 当前支持范围

当前代码只支持“类式算法”：

- 支持：继承 `BaseAlgorithm` 的类。
- 不支持：直接装饰普通函数。

这一点要以当前实现为准，不要按旧设计稿中的“函数式算法”示例来写。

### 3.3 必填参数

下面这些字段在当前实现中是必填或等价必填：

| 参数 | 说明 |
| --- | --- |
| `name` | 算法名称。 |
| `version` | 算法版本。 |
| `algorithm_type` | 算法类型，当前使用 `AlgorithmType` 枚举。 |
| `created_time` | 创建日期，格式必须是 `YYYY-MM-DD`。 |
| `author` | 作者。 |
| `category` | 分类。 |

当前 `algorithm_type` 可选值来自枚举：

- `AlgorithmType.PROGRAMME`
- `AlgorithmType.PREPARE`
- `AlgorithmType.PREDICTION`

### 3.4 可选参数

常用可选参数如下：

| 参数 | 说明 |
| --- | --- |
| `display_name` | 展示名称，默认等于 `name`。 |
| `description` | 算法描述。 |
| `application_scenarios` | 应用场景说明。 |
| `extra` | 自定义元数据，要求是 `dict[str, str]`。 |
| `execution` | 执行策略元数据。 |
| `logging` | 日志采样与脱敏元数据。 |

### 3.5 `execution` 的作用

`execution` 不是在装饰器里直接执行调度逻辑，而是记录算法期望的执行策略，供运行时解释。

当前支持的键：

| 键 | 说明 |
| --- | --- |
| `execution_mode` | 执行模式，必须传 `ExecutionMode` 枚举值。 |
| `stateful` | 是否有状态。 |
| `isolated_pool` | 是否使用独立进程池。 |
| `max_workers` | 该算法期望的最大 worker 数。 |
| `timeout_s` | 该算法期望的超时秒数。 |
| `gpu` | GPU 标记字符串。 |

示例：

```python
from algo_sdk import Algorithm, BaseAlgorithm, BaseModel
from algo_sdk.core import AlgorithmType, ExecutionMode


class PrepareRequest(BaseModel):
    value: int


class PrepareResponse(BaseModel):
    result: int


@Algorithm(
    name="Prepare",
    version="v1",
    algorithm_type=AlgorithmType.PREPARE,
    created_time="2026-02-28",
    author="algo-team",
    category="Decision",
    execution={
        "execution_mode": ExecutionMode.PROCESS_POOL,
        "isolated_pool": True,
        "max_workers": 2,
        "timeout_s": 300,
    },
)
class PrepareAlgorithm(
    BaseAlgorithm[PrepareRequest, PrepareResponse]
):
    def run(self, req: PrepareRequest) -> PrepareResponse:
        return PrepareResponse(result=req.value)
```

注意：当前装饰器对 `execution_mode` 校验较严格，不能写成普通字符串 `"process_pool"`，应传枚举值。

### 3.6 `logging` 的作用

`logging` 用于描述算法调用日志的记录策略，当前支持的键包括：

- `enabled`
- `log_input`
- `log_output`
- `on_error_only`
- `sample_rate`
- `max_length`
- `redact_fields`

示例：

```python
logging={
    "enabled": True,
    "log_input": True,
    "log_output": True,
    "on_error_only": False,
    "sample_rate": 1.0,
    "max_length": 2048,
    "redact_fields": ["password", "token"],
}
```

### 3.7 装饰器会自动做的校验

`@Algorithm` 还会在定义阶段做一批静态校验：

- 目标必须是类，不能是函数。
- 目标类必须继承 `BaseAlgorithm`。
- 目标类不能是抽象类。
- 必须提供可调用的 `run()`。
- `run()` 必须有类型标注。
- 输入参数必须是 `BaseModel` 子类。
- 返回值必须是 `BaseModel` 子类。
- 第二个参数如果存在，必须是 `HyperParams` 子类。
- `created_time` 必须是合法日期。
- `extra` 必须是 `dict[str, str]`。

### 3.8 生命周期配合方式

`BaseAlgorithm` 提供这些生命周期钩子：

- `initialize()`
- `before_run()`
- `run()`
- `after_run()`
- `shutdown()`

你至少要实现 `run()`；其余方法按需覆盖即可。

## 4. 建议的新增算法流程

1. 在 `src/algo_core_service/algorithms/` 下新增算法文件。
2. 定义请求模型、响应模型，以及可选的超参数模型。
3. 编写继承 `BaseAlgorithm` 的算法类，并加上 `@Algorithm(...)`。
4. 在 `src/algo_core_service/algorithms/__init__.py` 中导出该算法类。
5. 启动服务后访问 `/algorithms` 检查是否注册成功。
6. 访问 `/algorithms/{name}/{version}/schema` 检查输入输出 Schema。

## 5. 常见问题

### 5.1 算法文件写了，但 `/algorithms` 里看不到

优先检查：

- 是否放在 `src/algo_core_service/algorithms/` 下。
- 是否在 `algorithms/__init__.py` 中导入并加入 `__all__`。
- 是否加了 `@Algorithm(...)`。
- 是否继承了 `BaseAlgorithm`。
- `run()` 的类型标注是否完整。

### 5.2 本地启动时报注册中心错误

如果本地没有 Consul，把 `.env` 里的：

```dotenv
SERVICE_REGISTRY_ENABLED=false
```

再启动一次。

### 5.3 Swagger 打不开

优先检查：

- `SERVICE_SWAGGER_ENABLED=true`
- 如果启用离线模式，确认 `assets/swagger-ui/` 存在
- 端口是否与 `SERVICE_PORT` 一致
