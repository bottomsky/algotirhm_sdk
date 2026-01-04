# 算法核心服务 + SDK 设计方案

> 目标：通过 `@Algorithm` 装饰器注册算法（函数/类），自动暴露为 HTTP 接口。  
> SDK 提供标准算法模板（生命周期 `initialize/run/after_run/shutdown`）、进程隔离执行（支持全局共享池/算法独立池）、标准化输入输出协议（含 `AlgorithmContext`）、崩溃/异常日志与观测能力，以及可选的 Consul 服务注册。

---

## 1. 项目整体结构

```text
algo-platform/
├─ README.md
├─ algo_sdk/                 # 提供给算法开发者使用的 SDK（核心抽象 + 默认实现）
│  ├─ __init__.py
│  ├─ protocol/              # 标准输入输出协议（request/response/context）
│  │  ├─ context.py                  # AlgorithmContext 定义
│  │  ├─ envelope.py                 # AlgorithmRequest/AlgorithmResponse 定义
│  ├─ core/
│  │  ├─ base_model_abc.py          # 抽象：基础模型接口定义
│  │  ├─ base_model_impl.py         # 实现：对接 Pydantic BaseModel
│  │  ├─ algorithm_spec_abc.py      # 抽象：算法元数据结构接口
│  │  ├─ algorithm_spec_impl.py     # 实现：默认的算法元数据结构
│  │  ├─ registry_abc.py            # 抽象：算法注册中心接口
│  │  ├─ registry_impl.py           # 实现：进程内全局注册中心
│  │  ├─ app_factory_abc.py         # 抽象：HTTP 应用工厂接口
│  │  ├─ app_factory_impl.py        # 实现：基于 FastAPI 的默认实现
│  │  ├─ errors_abc.py              # 抽象：错误结构与业务异常接口
│  │  ├─ errors_impl.py             # 实现：默认错误码与业务异常
│  │  ├─ types.py                   # 一些公共类型别名（非必须抽象）
│  │
│  ├─ decorators/
│  │  ├─ algorithm_decorator_abc.py # 抽象：算法装饰器接口
│  │  ├─ algorithm_decorator_impl.py# 实现：@Algorithm 的默认实现
│  │
│  ├─ http/
│  │  ├─ api_schema_abc.py          # 抽象：HTTP 请求/响应包装结构接口
│  │  ├─ api_schema_impl.py         # 实现：标准 envelope 的默认协议
│  │
│  ├─ config/
│  │  ├─ settings_abc.py            # 抽象：SDK 配置接口（如是否固定 HTTP 状态码等）
│  │  ├─ settings_impl.py           # 实现：基于环境变量的默认配置
│  │
│  ├─ runtime/                # 执行运行时（进程池/worker/生命周期）
│  │  ├─ algorithm_abc.py            # 抽象：IAlgorithm 生命周期接口
│  │  ├─ algorithm_adapter.py        # 适配：把函数包装成 IAlgorithm
│  │  ├─ executor_abc.py             # 抽象：算法执行器（进程隔离/超时/并发）
│  │  ├─ executor_impl.py            # 实现：multiprocessing 进程池 + 监控
│  │  ├─ worker_main.py              # worker 进程入口（initialize/run/after_run）
│  │
│  ├─ logging/                # 日志模块（结构化日志 + 多进程汇聚 + 标准异常记录）
│  │  ├─ logger.py
│  │  ├─ exception_schema.py
│  │  ├─ mp_logging.py
│  │
│  ├─ observability/          # 观测模块（metrics/tracing/health）
│  │  ├─ metrics.py
│  │  ├─ tracing.py
│  │  ├─ health_abc.py
│  │  ├─ health_impl.py
│  │
│  ├─ service_registry/       # 服务注册（可选 Consul）
│  │  ├─ registrar_abc.py
│  │  ├─ consul_registrar.py
│  │
│  └─ utils/
│     ├─ import_utils.py            # 通用 import 工具（如果需要）
│
└─ algo_core_service/        # 具体部署的算法核心服务工程
   ├─ main.py                # 入口：加载算法模块 + 创建 app + 启动服务
   ├─ settings.py            # 服务级别配置（端口、要加载的模块等）
   └─ algorithms/            # 示例算法集合（便于开发调试）
      ├─ __init__.py
      └─ orbit_demo.py       # 示例算法：orbit_propagation
```

---

## 2. 模块划分与职责说明

### 2.1 `algo_sdk.core` 模块

#### 2.1.1 `base_model_abc.py`

**职责**：  
对“基础模型（输入输出数据模型）”抽象一层，未来可以从 Pydantic 切换到其它实现。

**抽象类：**

```python
# algo_sdk/core/base_model_abc.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class IBaseModel(ABC):
    """
    所有算法输入/输出模型的抽象接口。
    实际实现可以基于 Pydantic 或其它校验库。
    """

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IBaseModel":
        """从 dict 构建模型实例，并执行校验。"""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """将模型实例序列化为 dict。"""

    @classmethod
    @abstractmethod
    def json_schema(cls) -> Dict[str, Any]:
        """返回用于对外暴露的 JSON Schema。"""
```

#### 2.1.2 `base_model_impl.py`

**职责**：  
用 Pydantic 实现 `IBaseModel`。

```python
# algo_sdk/core/base_model_impl.py
from pydantic import BaseModel as _PydanticBaseModel
from typing import Any, Dict
from .base_model_abc import IBaseModel

class BaseModel(_PydanticBaseModel, IBaseModel):
    """
    SDK 对外暴露的基类：
        from algo_sdk import BaseModel
    """

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def json_schema(cls) -> Dict[str, Any]:
        return cls.model_json_schema()
```

> 对算法开发者来说，直接 `from algo_sdk import BaseModel` 即可，不需要关心 Pydantic 细节。

---

#### 2.1.3 `algorithm_spec_abc.py`

**职责**：  
定义“算法元数据、输入/输出元信息、算法入口（函数/类）+ 执行参数”的抽象接口。

```python
# algo_sdk/core/algorithm_spec_abc.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Callable, Type
from .base_model_abc import IBaseModel

class IAlgorithmInputMeta(ABC):
    @property
    @abstractmethod
    def model_cls(self) -> Type[IBaseModel]:
        """输入模型类型。"""

    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """输入 JSON Schema。"""

class IAlgorithmOutputMeta(ABC):
    @property
    @abstractmethod
    def model_cls(self) -> Type[IBaseModel]:
        """输出模型类型。"""

    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """输出 JSON Schema。"""

class IAlgorithmExecutionMeta(ABC):
    """
    执行参数（影响运行时进程池/超时/并发/GPU 等）。

    注意：这里描述的是“期望策略”，实际是否生效由 runtime.executor 决定。
    """

    @property
    @abstractmethod
    def isolated_pool(self) -> bool:
        """是否使用算法独立进程池（通常用于 GPU/大模型/重资源算法）。"""

    @property
    @abstractmethod
    def max_workers(self) -> int:
        """该算法可并发的 worker 数。"""

    @property
    @abstractmethod
    def timeout_s(self) -> float | None:
        """单次 run 的超时秒数（None 表示不超时）。"""

    @property
    @abstractmethod
    def gpu(self) -> str | None:
        """GPU 资源声明（例如 '0'、'0,1'、或 None 表示不绑定）。"""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """用于对外暴露（/algorithms, /schema 等）。"""

class IAlgorithmSpec(ABC):
    """算法描述信息抽象接口。"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def tags(self) -> list[str]: ...

    @property
    @abstractmethod
    def input_meta(self) -> IAlgorithmInputMeta: ...

    @property
    @abstractmethod
    def output_meta(self) -> IAlgorithmOutputMeta: ...

    @property
    @abstractmethod
    def execution_meta(self) -> IAlgorithmExecutionMeta: ...

    @property
    @abstractmethod
    def entrypoint_ref(self) -> str:
        """
        算法入口引用（建议格式：'{module}:{qualname}'）。
        运行时在 worker 进程中通过该引用 import 并实例化/调用。
        """

    @property
    @abstractmethod
    def entrypoint(self) -> Callable[..., Any]:
        """
        进程内入口（用于调试/单元测试）。
        生产环境建议交由 runtime 在独立进程执行。
        """
```

#### 2.1.4 `algorithm_spec_impl.py`

**职责**：  
给出默认的 `IAlgorithmInputMeta` / `IAlgorithmOutputMeta` / `IAlgorithmSpec` 实现。

```python
# algo_sdk/core/algorithm_spec_impl.py
from dataclasses import dataclass
from typing import Any, Dict, Callable, Type
from .algorithm_spec_abc import (
    IAlgorithmInputMeta,
    IAlgorithmOutputMeta,
    IAlgorithmExecutionMeta,
    IAlgorithmSpec,
)
from .base_model_abc import IBaseModel

@dataclass
class AlgorithmInputMeta(IAlgorithmInputMeta):
    _model_cls: Type[IBaseModel]
    _schema: Dict[str, Any]

    @property
    def model_cls(self) -> Type[IBaseModel]:
        return self._model_cls

    @property
    def schema(self) -> Dict[str, Any]:
        return self._schema

@dataclass
class AlgorithmOutputMeta(IAlgorithmOutputMeta):
    _model_cls: Type[IBaseModel]
    _schema: Dict[str, Any]

    @property
    def model_cls(self) -> Type[IBaseModel]:
        return self._model_cls

    @property
    def schema(self) -> Dict[str, Any]:
        return self._schema

@dataclass
class AlgorithmExecutionMeta(IAlgorithmExecutionMeta):
    _isolated_pool: bool = False
    _max_workers: int = 1
    _timeout_s: float | None = None
    _gpu: str | None = None

    @property
    def isolated_pool(self) -> bool:
        return self._isolated_pool

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def timeout_s(self) -> float | None:
        return self._timeout_s

    @property
    def gpu(self) -> str | None:
        return self._gpu

    def to_dict(self) -> Dict[str, Any]:
        return {
            "isolated_pool": self._isolated_pool,
            "max_workers": self._max_workers,
            "timeout_s": self._timeout_s,
            "gpu": self._gpu,
        }

@dataclass
class AlgorithmSpec(IAlgorithmSpec):
    _name: str
    _version: str
    _description: str
    _tags: list[str]
    _input_meta: IAlgorithmInputMeta
    _output_meta: IAlgorithmOutputMeta
    _execution_meta: IAlgorithmExecutionMeta
    _entrypoint_ref: str
    _entrypoint: Callable[..., Any]

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        return self._description

    @property
    def tags(self) -> list[str]:
        return self._tags

    @property
    def input_meta(self) -> IAlgorithmInputMeta:
        return self._input_meta

    @property
    def output_meta(self) -> IAlgorithmOutputMeta:
        return self._output_meta

    @property
    def execution_meta(self) -> IAlgorithmExecutionMeta:
        return self._execution_meta

    @property
    def entrypoint_ref(self) -> str:
        return self._entrypoint_ref

    @property
    def entrypoint(self) -> Callable[..., Any]:
        return self._entrypoint
```

---

#### 2.1.5 `registry_abc.py`

**职责**：  
抽象“算法注册中心”的基本行为。

```python
# algo_sdk/core/registry_abc.py
from abc import ABC, abstractmethod
from typing import Iterable
from .algorithm_spec_abc import IAlgorithmSpec

class IAlgorithmRegistry(ABC):
    @abstractmethod
    def register(self, spec: IAlgorithmSpec) -> None:
        """注册算法。"""

    @abstractmethod
    def get(self, name: str, version: str) -> IAlgorithmSpec | None:
        """根据名称和版本获取算法信息。"""

    @abstractmethod
    def list_all(self) -> Iterable[IAlgorithmSpec]:
        """列出所有已注册算法。"""
```

#### 2.1.6 `registry_impl.py`

**职责**：  
默认的“进程内内存注册中心”实现 + 全局单例。

```python
# algo_sdk/core/registry_impl.py
from typing import Dict, Tuple, Iterable
from .registry_abc import IAlgorithmRegistry
from .algorithm_spec_abc import IAlgorithmSpec

class InMemoryAlgorithmRegistry(IAlgorithmRegistry):
    def __init__(self) -> None:
        self._algos: Dict[Tuple[str, str], IAlgorithmSpec] = {}

    def register(self, spec: IAlgorithmSpec) -> None:
        key = (spec.name, spec.version)
        if key in self._algos:
            # 简单处理：直接抛异常
            raise ValueError(f"Algorithm already registered: {key}")
        self._algos[key] = spec

    def get(self, name: str, version: str) -> IAlgorithmSpec | None:
        return self._algos.get((name, version))

    def list_all(self) -> Iterable[IAlgorithmSpec]:
        return self._algos.values()

# 默认全局单例
global_registry = InMemoryAlgorithmRegistry()
```

---

#### 2.1.7 `errors_abc.py`

**职责**：  
抽象错误码/错误结构，方便未来扩展为统一错误中心。

```python
# algo_sdk/core/errors_abc.py
from abc import ABC

class IAlgoError(ABC, Exception):
    """所有 SDK 定义的业务异常基类。"""

class IAlgoBizError(IAlgoError):
    """算法业务层的错误（如不可收敛、数据条件不满足等）。"""

    @property
    def code(self) -> int: ...
    @property
    def message(self) -> str: ...
    @property
    def data(self): ...
```

#### 2.1.8 `errors_impl.py`

**职责**：  
默认错误码与异常实现。

```python
# algo_sdk/core/errors_impl.py
from typing import Any
from .errors_abc import IAlgoBizError

class AlgoBizError(IAlgoBizError):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self._code = code
        self._message = message
        self._data = data

    @property
    def code(self) -> int:
        return self._code

    @property
    def message(self) -> str:
        return self._message

    @property
    def data(self) -> Any:
        return self._data
```

---

#### 2.1.9 `app_factory_abc.py`

**职责**：  
抽象 HTTP 应用工厂，未来可替换 FastAPI 为其它框架。

```python
# algo_sdk/core/app_factory_abc.py
from abc import ABC, abstractmethod
from typing import Any
from .registry_abc import IAlgorithmRegistry
from ..runtime.executor_abc import IAlgorithmExecutor

class IAppFactory(ABC):
    @abstractmethod
    def create_app(
        self,
        registry: IAlgorithmRegistry,
        executor: IAlgorithmExecutor,
        health: "IHealthService | None" = None,
    ) -> Any:
        """
        创建 Web 应用实例。
        返回值类型由具体框架决定（例如 FastAPI App）。
        """
```

#### 2.1.10 `app_factory_impl.py`

**职责**：  
提供基于 FastAPI 的默认应用工厂，实现统一的路由与调用逻辑。

```python
# algo_sdk/core/app_factory_impl.py
from fastapi import FastAPI
from pydantic import BaseModel as PydanticBaseModel
from typing import Any, Dict

from .app_factory_abc import IAppFactory
from .registry_abc import IAlgorithmRegistry
from .errors_impl import AlgoBizError
from ..http.api_schema_impl import api_success, api_error
from ..runtime.executor_abc import IAlgorithmExecutor
from ..protocol.context import AlgorithmContext
from ..observability.health_abc import IHealthService
from ..observability.health_impl import InMemoryHealthService

class InvokeRequest(PydanticBaseModel):
    """
    标准输入协议（外部 JSON）：
      - requestId: 每次调用唯一 ID
      - datetime: ISO8601 时间字符串
      - context: 可选上下文（trace/tenant/user 等）
      - data: 业务输入（对应算法输入模型）
    """
    requestId: str
    datetime: str
    context: AlgorithmContext | None = None
    data: Dict[str, Any]

class FastAPIAppFactory(IAppFactory):
    def create_app(
        self,
        registry: IAlgorithmRegistry,
        executor: IAlgorithmExecutor,
        health: IHealthService | None = None,
    ) -> FastAPI:
        app = FastAPI(title="Algo Core Service")
        health = health or InMemoryHealthService(registry=registry, executor=executor)

        @app.get("/algorithms")
        def list_algorithms():
            algos = [
                {
                    "name": spec.name,
                    "version": spec.version,
                    "description": spec.description,
                    "tags": spec.tags,
                    "entrypoint_ref": spec.entrypoint_ref,
                    "execution": spec.execution_meta.to_dict(),
                }
                for spec in registry.list_all()
            ]
            return api_success(data=algos)

        @app.get("/healthz")
        def healthz():
            # 存活探针：只要 HTTP 服务能响应即可（不做重依赖检查）
            return api_success(data=health.liveness())

        @app.get("/readyz")
        def readyz():
            # 就绪探针：算法已加载 + executor 已启动（以及可选的外部依赖）
            ok, payload = health.readiness()
            return api_success(data=payload) if ok else api_error(code=50300, message="Not ready", data=payload)

        @app.get("/algorithms/{name}/{version}/schema")
        def get_schema(name: str, version: str):
            spec = registry.get(name, version)
            if not spec:
                return api_error(code=40401, message="Algorithm not found")
            return api_success(
                data={
                    "name": spec.name,
                    "version": spec.version,
                    "description": spec.description,
                    "entrypoint_ref": spec.entrypoint_ref,
                    "input_schema": spec.input_meta.schema,
                    "output_schema": spec.output_meta.schema,
                    "execution": spec.execution_meta.to_dict(),
                }
            )

        @app.post("/algorithms/{name}/{version}/invoke")
        def invoke(name: str, version: str, req: InvokeRequest):
            spec = registry.get(name, version)
            if not spec:
                return api_error(
                    code=40401,
                    message="Algorithm not found",
                    requestId=req.requestId,
                    datetime=req.datetime,
                    context=req.context,
                )

            # 输入解析
            try:
                input_obj = spec.input_meta.model_cls.from_dict(req.data)
            except Exception as e:
                return api_error(
                    code=40001,
                    message=f"Input validation error: {e}",
                    requestId=req.requestId,
                    datetime=req.datetime,
                    context=req.context,
                )

            # 执行算法
            try:
                # 注意：默认执行应在独立进程中完成（支持全局共享池/算法独立池）
                result = executor.invoke(
                    spec=spec,
                    requestId=req.requestId,
                    datetime=req.datetime,
                    context=req.context,
                    input_obj=input_obj,
                )
            except AlgoBizError as e:
                return api_error(
                    code=e.code,
                    message=e.message,
                    data=e.data,
                    requestId=req.requestId,
                    datetime=req.datetime,
                    context=req.context,
                )
            except Exception as e:
                return api_error(
                    code=50001,
                    message=f"Algorithm execution error: {e}",
                    requestId=req.requestId,
                    datetime=req.datetime,
                    context=req.context,
                )

            # 输出校验
            try:
                out_cls = spec.output_meta.model_cls
                if isinstance(result, out_cls):
                    out_obj = result
                elif isinstance(result, dict):
                    out_obj = out_cls.from_dict(result)
                else:
                    out_obj = out_cls.from_dict(dict(result))  # 简单兜底
                data = out_obj.to_dict()
            except Exception as e:
                return api_error(
                    code=50002,
                    message=f"Output validation error: {e}",
                    requestId=req.requestId,
                    datetime=req.datetime,
                    context=req.context,
                )

            return api_success(
                data=data,
                requestId=req.requestId,
                datetime=req.datetime,
                context=req.context,
            )

        return app
```

---

### 2.2 `algo_sdk.decorators` 模块

#### 2.2.1 `algorithm_decorator_abc.py`

**职责**：  
抽象“算法装饰器”的行为（主要是从 type hints 推断模型类型、构建 spec 并注册）。

```python
# algo_sdk/decorators/algorithm_decorator_abc.py
from abc import ABC, abstractmethod
from typing import Any, Callable
from ..core.algorithm_spec_abc import IAlgorithmSpec

class IAlgorithmDecorator(ABC):
    @abstractmethod
    def __call__(
        self,
        name: str,
        version: str = "v1",
        description: str = "",
        tags: list[str] | None = None,
        execution: dict[str, Any] | None = None,
    ) -> Callable:
        """返回一个可作为装饰器使用的 callable。"""
```

#### 2.2.2 `algorithm_decorator_impl.py`

**职责**：  
默认实现：  
- 从函数/类的 `run` type hints 中提取输入/输出模型（继承自 `BaseModel`）；  
- 生成 `AlgorithmSpec`；  
- 注册到 `global_registry`；  
- 返回原对象（函数或类）。

```python
# algo_sdk/decorators/algorithm_decorator_impl.py
from typing import Any, Callable, get_type_hints, Type
from ..core.base_model_impl import BaseModel
from ..core.algorithm_spec_impl import (
    AlgorithmSpec,
    AlgorithmInputMeta,
    AlgorithmOutputMeta,
    AlgorithmExecutionMeta,
)
from ..core.registry_impl import global_registry
from .algorithm_decorator_abc import IAlgorithmDecorator

class DefaultAlgorithmDecorator(IAlgorithmDecorator):
    def __call__(
        self,
        name: str,
        version: str = "v1",
        description: str = "",
        tags: list[str] | None = None,
        execution: dict[str, Any] | None = None,
    ) -> Callable:

        tags = tags or []
        execution = execution or {}

        def decorator(obj: Any):
            """
            支持两种写法：
              1) 装饰函数：fn(req: In) -> Out
              2) 装饰类：class Algo: def run(self, req: In) -> Out
                 （生命周期由 runtime.algorithm_abc 定义）
            """

            if isinstance(obj, type):
                entry = obj
                fn = obj.run
            else:
                entry = obj
                fn = obj

            hints = get_type_hints(fn)
            if "return" not in hints:
                raise TypeError(f"Algorithm {name} must have return type annotation")

            # 取第一个非 return 的参数类型作为输入模型
            param_names = [p for p in hints.keys() if p != "return"]
            if not param_names:
                raise TypeError(f"Algorithm {name} must have one input parameter")

            input_param_name = param_names[0]
            in_model_cls: Type[BaseModel] = hints[input_param_name]  # type: ignore
            out_model_cls: Type[BaseModel] = hints["return"]         # type: ignore

            if not issubclass(in_model_cls, BaseModel):
                raise TypeError("Input type must subclass BaseModel")
            if not issubclass(out_model_cls, BaseModel):
                raise TypeError("Return type must subclass BaseModel")

            input_meta = AlgorithmInputMeta(
                _model_cls=in_model_cls,
                _schema=in_model_cls.json_schema(),
            )
            output_meta = AlgorithmOutputMeta(
                _model_cls=out_model_cls,
                _schema=out_model_cls.json_schema(),
            )

            execution_meta = AlgorithmExecutionMeta(
                _isolated_pool=bool(execution.get("isolated_pool", False)),
                _max_workers=int(execution.get("max_workers", 1)),
                _timeout_s=execution.get("timeout_s"),
                _gpu=execution.get("gpu"),
            )

            entrypoint_ref = f"{entry.__module__}:{entry.__qualname__}"

            spec = AlgorithmSpec(
                _name=name,
                _version=version,
                _description=description,
                _tags=tags,
                _input_meta=input_meta,
                _output_meta=output_meta,
                _execution_meta=execution_meta,
                _entrypoint_ref=entrypoint_ref,
                _entrypoint=entry,
            )

            global_registry.register(spec)
            return obj

        return decorator

# 对外暴露的装饰器实例
Algorithm = DefaultAlgorithmDecorator()
```

> 使用方式：  
> `from algo_sdk import BaseModel, Algorithm`

---

### 2.3 `algo_sdk.http` 模块

#### 2.3.1 `api_schema_abc.py`

**职责**：  
抽象 HTTP 层的标准输入/输出 envelope（支持 `AlgorithmContext`、`requestId`、`datetime`）。

```python
# algo_sdk/http/api_schema_abc.py
from abc import ABC, abstractmethod
from typing import Any, Dict
from ..protocol.context import AlgorithmContext

class IApiResponseBuilder(ABC):
    @abstractmethod
    def success(
        self,
        data: Any,
        requestId: str | None = None,
        datetime: str | None = None,
        context: AlgorithmContext | None = None,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def error(
        self,
        code: int,
        message: str,
        data: Any = None,
        requestId: str | None = None,
        datetime: str | None = None,
        context: AlgorithmContext | None = None,
    ) -> Dict[str, Any]:
        ...
```

#### 2.3.2 `api_schema_impl.py`

**职责**：  
默认协议实现。

```python
# algo_sdk/http/api_schema_impl.py
from typing import Any, Dict
from .api_schema_abc import IApiResponseBuilder
from ..protocol.context import AlgorithmContext

class DefaultApiResponseBuilder(IApiResponseBuilder):
    def success(
        self,
        data: Any,
        requestId: str | None = None,
        datetime: str | None = None,
        context: AlgorithmContext | None = None,
    ) -> Dict[str, Any]:
        return {
            "code": 0,
            "message": "success",
            "requestId": requestId,
            "datetime": datetime,
            "context": context.model_dump() if context else None,
            "data": data,
        }

    def error(
        self,
        code: int,
        message: str,
        data: Any = None,
        requestId: str | None = None,
        datetime: str | None = None,
        context: AlgorithmContext | None = None,
    ) -> Dict[str, Any]:
        return {
            "code": code,
            "message": message,
            "requestId": requestId,
            "datetime": datetime,
            "context": context.model_dump() if context else None,
            "data": data,
        }

# 简单导出函数，方便 app_factory 使用
_builder = DefaultApiResponseBuilder()

def api_success(
    data: Any,
    requestId: str | None = None,
    datetime: str | None = None,
    context: AlgorithmContext | None = None,
) -> Dict[str, Any]:
    return _builder.success(data, requestId, datetime, context)

def api_error(
    code: int,
    message: str,
    data: Any = None,
    requestId: str | None = None,
    datetime: str | None = None,
    context: AlgorithmContext | None = None,
) -> Dict[str, Any]:
    return _builder.error(code, message, data, requestId, datetime, context)
```

---

### 2.4 `algo_sdk.config` 模块（简要）

可选，抽象一些行为，比如：

- 是否所有错误都返回 HTTP 200；
- 是否打印详细异常信息。

这里先只留结构，具体配置可以后补。

---

### 2.5 `algo_sdk.protocol` 模块

**职责**：  
定义对外统一的输入/输出结构（支持上下文 `AlgorithmContext`），保证所有算法调用具备一致的：`requestId`、`datetime`、`context`、`data` 字段。

建议外部协议（JSON）：

- Request：`{ requestId, datetime, context, data }`
- Response：`{ code, message, requestId, datetime, context, data }`

```python
# algo_sdk/protocol/context.py
from pydantic import BaseModel
from typing import Any, Dict

class AlgorithmContext(BaseModel):
    """
    算法上下文：用于链路追踪/多租户/用户态信息等。
    约定：服务端默认回传（echo）请求的 context（可在算法内部修改/补充）。
    """
    traceId: str | None = None
    tenantId: str | None = None
    userId: str | None = None
    extra: Dict[str, Any] = {}
```

```python
# algo_sdk/protocol/envelope.py
from pydantic import BaseModel
from typing import Any, Dict
from .context import AlgorithmContext

class AlgorithmRequest(BaseModel):
    requestId: str
    datetime: str  # ISO8601
    context: AlgorithmContext | None = None
    data: Dict[str, Any]

class AlgorithmResponse(BaseModel):
    code: int
    message: str
    requestId: str | None = None
    datetime: str | None = None
    context: AlgorithmContext | None = None
    data: Any = None
```

---

### 2.6 `algo_sdk.runtime` 模块

**职责**：  
把算法执行从 HTTP 进程中隔离出去，提供：

- 生命周期：`initialize()`（加载资源/模型/数据集）、`run()`（每次请求执行）、`after_run()`（每次请求后清理）、`shutdown()`（worker 退出前释放资源）；
- 进程隔离并发：默认全局共享进程池；通过装饰器 `execution.isolated_pool=True` 可启用“每算法独立进程池”（更适合 GPU/大模型/重资源算法）；
- 崩溃检测：worker 非 0 退出码视为崩溃，标准化记录日志，并返回可识别的错误码；
- 资源声明：`execution.gpu` 可用于绑定 CUDA 设备（实现层可通过设置 `CUDA_VISIBLE_DEVICES` 等方式）。

```python
# algo_sdk/runtime/algorithm_abc.py
from abc import ABC, abstractmethod
from typing import Any
from ..protocol.context import AlgorithmContext
from ..core.base_model_abc import IBaseModel

class IAlgorithm(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """worker 启动后调用一次（加载模型/文件/数据集等）。"""

    @abstractmethod
    def run(self, req: IBaseModel, context: AlgorithmContext | None = None) -> Any:
        """每次请求调用（建议不要做昂贵的重复初始化）。"""

    def after_run(self) -> None:
        """每次 run 后调用（释放临时资源/清理缓存等）。"""

    def shutdown(self) -> None:
        """worker 退出前调用（释放模型/GPU/文件句柄等）。"""
```

为了兼容“函数式算法”的简单写法，runtime 提供一个适配器：把 `fn(req)->out` 包装成具备生命周期的 `IAlgorithm`（默认 `initialize/after_run/shutdown` 为 no-op）。

```python
# algo_sdk/runtime/algorithm_adapter.py
from typing import Any, Callable
from ..protocol.context import AlgorithmContext
from ..core.base_model_abc import IBaseModel
from .algorithm_abc import IAlgorithm

class FunctionAlgorithmAdapter(IAlgorithm):
    def __init__(self, fn: Callable[[IBaseModel], Any]) -> None:
        self._fn = fn

    def initialize(self) -> None:
        return None

    def run(self, req: IBaseModel, context: AlgorithmContext | None = None) -> Any:
        return self._fn(req)

    def after_run(self) -> None:
        return None

    def shutdown(self) -> None:
        return None
```

```python
# algo_sdk/runtime/executor_abc.py
from abc import ABC, abstractmethod
from typing import Any
from ..protocol.context import AlgorithmContext
from ..core.algorithm_spec_abc import IAlgorithmSpec
from ..core.base_model_abc import IBaseModel

class IAlgorithmExecutor(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def invoke(
        self,
        spec: IAlgorithmSpec,
        requestId: str,
        datetime: str,
        context: AlgorithmContext | None,
        input_obj: IBaseModel,
    ) -> Any:
        """在独立进程执行算法（含超时/崩溃处理），返回结果（dict 或输出模型实例）。"""
```

**并发与池化建议**：

- 默认：全局共享进程池（适合轻量/初始化快的算法，资源利用率高）；
- 对 `execution.isolated_pool=True` 的算法：每算法独立池（适合 GPU/深度学习/初始化昂贵的算法，隔离强且可常驻模型）；
- 可进一步扩展：`dedicated`（独占进程/独占 GPU）用于强 SLA 场景。

---

### 2.7 `algo_sdk.logging` 模块

**职责**：  
提供标准化异常记录 + 多进程日志汇聚，解决两类问题：

1. 算法抛异常（可捕获）需要结构化记录；
2. worker 进程崩溃（不可捕获）需要由父进程监控并记录“崩溃事件”。

建议统一异常日志结构（JSON）包含：

- `requestId`、`datetime`、`algoName`、`algoVersion`、`entrypointRef`
- `errorType`、`errorMessage`、`stack`
- `processPid`、`exitCode`（崩溃场景）

实现建议：基于 `logging.handlers.QueueHandler/QueueListener` 把 worker 日志集中到主进程输出/落盘。

---

### 2.8 `algo_sdk.observability` 模块

**职责**：  
提供可观测性能力，建议最小集合：

- Metrics：请求总数、失败数、延迟直方图、队列长度、worker 存活数（按算法维度标签化）；
- Tracing：从 HTTP 接入层生成/透传 `traceId`（写入 `AlgorithmContext`），并在日志里关联；
- Health：`/healthz`（存活）、`/readyz`（就绪：算法加载完成/worker 池已启动）。

#### 2.8.1 Health 组件设计

**目标**：

- 给负载均衡 / K8s / 运维系统提供“存活/就绪”探针；
- 把“服务是否可接收算法调用”的判定逻辑收敛到一个模块（而不是散落在入口/路由里）；
- 为后续接入更多依赖检查（例如 Consul 注册成功、外部模型文件加载、GPU 可用等）预留扩展点。

**探针语义（推荐）**：

- **Liveness**（存活探针）：`GET /healthz`  
  仅表示“HTTP 进程仍在运行并能响应请求”，不要做重依赖检查，避免抖动导致误杀。
- **Readiness**（就绪探针）：`GET /readyz`  
  表示“服务已完成启动关键路径，可对外接收算法调用”。未就绪时返回 `503`。

**Readiness 默认判定（建议最小集合）**：

- `algorithms_loaded`：算法模块导入完成，且 registry 至少包含一个算法（或允许为空但显式配置）；
- `executor_started`：执行器已启动，能接受任务（必要时可增加 worker 心跳/进程池状态检查）；
- `external_deps_ok`（可选）：如 Consul 注册成功、模型文件可读、GPU/许可证可用等。

**抽象接口：**（`algo_sdk/observability/health_abc.py`）

```python
# algo_sdk/observability/health_abc.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

class IHealthService(ABC):
    @abstractmethod
    def liveness(self) -> Dict[str, Any]:
        """存活探针的 payload（轻量、稳定）。"""

    @abstractmethod
    def readiness(self) -> Tuple[bool, Dict[str, Any]]:
        """
        返回 (is_ready, payload)。
        - is_ready: True -> ready
        - payload: 用于 /readyz 输出细节（检查项、原因等）
        """
```

**默认实现：**（`algo_sdk/observability/health_impl.py`）

```python
# algo_sdk/observability/health_impl.py
from typing import Any, Dict, Tuple
from .health_abc import IHealthService
from ..core.registry_abc import IAlgorithmRegistry
from ..runtime.executor_abc import IAlgorithmExecutor

class InMemoryHealthService(IHealthService):
    def __init__(self, registry: IAlgorithmRegistry, executor: IAlgorithmExecutor):
        self._registry = registry
        self._executor = executor
        self._started = False

    def mark_started(self) -> None:
        self._started = True

    def liveness(self) -> Dict[str, Any]:
        return {"status": "ok"}

    def readiness(self) -> Tuple[bool, Dict[str, Any]]:
        checks = {
            "started": self._started,
            "algorithms_loaded": len(self._registry.list_all()) > 0,
            "executor_started": self._executor.is_started(),
        }
        ok = all(checks.values())
        return ok, {"status": "ready" if ok else "not_ready", "checks": checks}
```

> 说明：`executor.is_started()` 可作为 `IAlgorithmExecutor` 的能力之一（或由具体实现暴露等价状态）；不希望改动 executor 接口时，也可把“executor 已启动”的标记交给 `HealthService` 维护。

**HTTP 暴露方式（推荐）**：

- 路由由 `algo_sdk.core.app_factory_impl.FastAPIAppFactory` 统一挂载，默认提供：
  - `GET /healthz`：固定 `200`（只要进程能响应）
  - `GET /readyz`：就绪返回 `200`，未就绪返回 `503`
- `algo_core_service/main.py` 在关键启动步骤完成后调用 `health.mark_started()`（或更细粒度标记），从而把 ready 状态从 `not_ready` 切换为 `ready`。

---

### 2.9 `algo_sdk.service_registry` 模块

**职责**：  
服务启动后按环境变量开关决定是否注册到 Consul：

- 注册内容（service）：`serviceName`、`address`、`port`、`health check`、tags
- 发现内容（推荐）：提供算法清单入口 URL（如 `/algorithms`）与 schema URL（如 `/algorithms/{name}/{version}/schema`）
- 如需“把算法路由 + 输入输出 schema 写入注册中心”，建议写 Consul KV（避免 service meta 过大）

建议的环境变量：

- `SERVICE_REGISTRY_ENABLED=true/false`
- `SERVICE_REGISTRY_HOST=http://127.0.0.1:8500`
- `SERVICE_NAME=algo-core-service`
- `SERVICE_INSTANCE_ID=<可选，默认自动生成>`
- `SERVICE_PROTOCOL=http`
- `SERVICE_REGISTRY_SESSION_ENABLED=true/false`
- `SERVICE_REGISTRY_SESSION_TTL_S=30`
- `SERVICE_REGISTRY_SESSION_RENEW_S=10`

---

## 3. `algo_core_service` 服务工程

### 3.1 `settings.py`

**职责**：  
配置服务信息：

- 监听端口；
- 要加载的算法模块列表。

```python
# algo_core_service/settings.py
import os

ALGO_MODULES = os.getenv(
    "ALGO_MODULES",
    "algo_core_service.algorithms.orbit_demo",
).split(",")

SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_BIND_HOST = os.getenv("SERVICE_BIND_HOST", "0.0.0.0")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))

# runtime/executor
EXECUTOR_GLOBAL_MAX_WORKERS = int(os.getenv("EXECUTOR_GLOBAL_MAX_WORKERS", "4"))
EXECUTOR_DEFAULT_TIMEOUT_S = float(os.getenv("EXECUTOR_DEFAULT_TIMEOUT_S", "300"))

# service registry (consul)
SERVICE_REGISTRY_ENABLED = os.getenv("SERVICE_REGISTRY_ENABLED", "false").lower() == "true"
SERVICE_REGISTRY_HOST = os.getenv("SERVICE_REGISTRY_HOST", "http://127.0.0.1:8500")
SERVICE_NAME = os.getenv("SERVICE_NAME", "algo-core-service")
```

---

### 3.2 `main.py`

**职责**：  
1. 导入算法模块（触发 `@Algorithm` 注册）；  
2. 启动 runtime executor（进程池/worker）；  
3. 可选注册到 Consul；  
4. 创建 `FastAPI` 应用（路由调用走 executor）；  
5. 用 `uvicorn` 启动。

```python
# algo_core_service/main.py
import importlib
import uvicorn

from algo_sdk.core.registry_impl import global_registry
from algo_sdk.core.app_factory_impl import FastAPIAppFactory
from algo_sdk.runtime.executor_impl import MpAlgorithmExecutor
from algo_sdk.service_registry.consul_registrar import ConsulRegistrar, NullRegistrar
from .settings import (
    ALGO_MODULES,
    SERVICE_HOST,
    SERVICE_BIND_HOST,
    SERVICE_PORT,
    EXECUTOR_GLOBAL_MAX_WORKERS,
    EXECUTOR_DEFAULT_TIMEOUT_S,
    SERVICE_REGISTRY_ENABLED,
    CONSUL_HTTP_ADDR,
    SERVICE_NAME,
)

def load_algorithms():
    for mod_name in ALGO_MODULES:
        mod_name = mod_name.strip()
        if not mod_name:
            continue
        importlib.import_module(mod_name)

def create_app():
    load_algorithms()
    factory = FastAPIAppFactory()

    executor = MpAlgorithmExecutor(
        registry=global_registry,
        global_max_workers=EXECUTOR_GLOBAL_MAX_WORKERS,
        default_timeout_s=EXECUTOR_DEFAULT_TIMEOUT_S,
    )

    # health：负责 /healthz /readyz 的状态判定
    health = InMemoryHealthService(registry=global_registry, executor=executor)

    registrar = (
        ConsulRegistrar(consul_addr=CONSUL_HTTP_ADDR, service_name=SERVICE_NAME)
        if SERVICE_REGISTRY_ENABLED
        else NullRegistrar()
    )

    app = factory.create_app(global_registry, executor, health=health)

    @app.on_event("startup")
    def _startup():
        executor.start()
        health.mark_started()
        registrar.register(app=app, registry=global_registry, host=SERVICE_HOST, port=SERVICE_PORT)

    @app.on_event("shutdown")
    def _shutdown():
        registrar.deregister()
        executor.stop()

    return app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host=SERVICE_BIND_HOST, port=SERVICE_PORT)
```

---

### 3.3 `algorithms/orbit_demo.py`（示例算法）

**职责**：  
示例如何使用 `algo_sdk` 写算法。

```python
# algo_core_service/algorithms/orbit_demo.py
from algo_sdk.core.base_model_impl import BaseModel
from algo_sdk.decorators.algorithm_decorator_impl import Algorithm
from algo_sdk.runtime.algorithm_abc import IAlgorithm
from algo_sdk.protocol.context import AlgorithmContext

class OrbitInput(BaseModel):
    start_time: str
    duration: float
    sats: list[int]

class OrbitOutput(BaseModel):
    trajectories: dict[int, list[list[float]]]

@Algorithm(
    name="orbit_propagation",
    version="v1",
    description="Simple orbit propagation demo",
    execution={"isolated_pool": False, "max_workers": 2, "timeout_s": 60},
)
class OrbitPropagationAlgo(IAlgorithm):
    def initialize(self) -> None:
        # 例如：加载星历文件、读取数据集、加载配置、初始化缓存等（仅一次）
        self._dummy_traj = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]

    def run(self, req: OrbitInput, context: AlgorithmContext | None = None) -> OrbitOutput:
        data = {sat_id: self._dummy_traj for sat_id in req.sats}
        return OrbitOutput(trajectories=data)

    def after_run(self) -> None:
        # 每次调用后清理临时资源（可选）
        pass

    def shutdown(self) -> None:
        # worker 退出时释放资源（可选）
        self._dummy_traj = None
```

---

### 3.4 `algorithms/dl_demo.py`（GPU/深度学习示例）

**要点**：

- 通过 `execution.isolated_pool=True` 启用算法独立进程池，便于模型常驻与隔离；
- `initialize()` 只加载一次模型；`after_run()` 做每次调用后的轻量清理；`shutdown()` 做最终释放；
- `execution.gpu` 由 runtime 用于绑定设备（例如设置 `CUDA_VISIBLE_DEVICES`）。

```python
# algo_core_service/algorithms/dl_demo.py
from algo_sdk.core.base_model_impl import BaseModel
from algo_sdk.decorators.algorithm_decorator_impl import Algorithm
from algo_sdk.protocol.context import AlgorithmContext
from algo_sdk.runtime.algorithm_abc import IAlgorithm

class ImageClsInput(BaseModel):
    image_b64: str

class ImageClsOutput(BaseModel):
    label: str
    score: float

@Algorithm(
    name="image_classification",
    version="v1",
    description="GPU image classification demo",
    execution={"isolated_pool": True, "max_workers": 1, "timeout_s": 300, "gpu": "0"},
)
class ImageClassificationAlgo(IAlgorithm):
    def initialize(self) -> None:
        # load_model(), load_weights(), warmup() ...
        self._model = object()

    def run(self, req: ImageClsInput, context: AlgorithmContext | None = None) -> ImageClsOutput:
        # inference ...
        return ImageClsOutput(label="cat", score=0.9)

    def after_run(self) -> None:
        # 可选：释放临时显存/缓存（如 torch.cuda.empty_cache）
        pass

    def shutdown(self) -> None:
        # 释放模型/句柄等
        self._model = None
```

---

## 4. 小结

- **抽象类和实现类分文件**：
  - `*_abc.py`：定义接口（IBaseModel, IAlgorithmSpec, IAlgorithmRegistry, IAppFactory, IAlgoBizError, IApiResponseBuilder...）
  - `*_impl.py`：给出默认实现（基于 Pydantic、FastAPI、内存 Registry 等）
- **补齐运行时能力**：
  - 标准协议：`requestId/datetime/context/data`，响应统一 `code/message`；
  - 生命周期：`initialize/run/after_run/shutdown`；
  - 进程隔离：默认全局共享池，支持装饰器参数启用算法独立池（更适合 GPU/深度学习）；
  - 观测与治理：结构化异常/崩溃日志、metrics/tracing/health、可选 Consul 注册与发现。
- **对算法开发者**：
  - 只需要：
    - `from algo_sdk import BaseModel, Algorithm`
    - 定义输入/输出模型；
    - 写一个函数或类，`@Algorithm` 装饰；
  - 自动获得 HTTP 接口，外部访问统一返回标准 envelope：`{code, message, requestId, datetime, context, data}`。
