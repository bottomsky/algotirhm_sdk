# 算法核心服务 + SDK 设计方案

> 目标：通过 `@Algorithm` 装饰器注册算法函数，自动暴露为 HTTP 接口。  
> 算法函数只关心输入模型和返回的 **data**，HTTP 对外统一返回 `{ code, message, data, request_id }`。

---

## 1. 项目整体结构

```text
algo-platform/
├─ README.md
├─ algo_sdk/                 # 提供给算法开发者使用的 SDK（核心抽象 + 默认实现）
│  ├─ __init__.py
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
│  │  ├─ api_schema_impl.py         # 实现：{code, message, data, request_id} 的默认协议
│  │
│  ├─ config/
│  │  ├─ settings_abc.py            # 抽象：SDK 配置接口（如是否固定 HTTP 状态码等）
│  │  ├─ settings_impl.py           # 实现：基于环境变量的默认配置
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
定义“算法元数据、输入/输出元信息、算法函数”的抽象接口。

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
    def func(self) -> Callable[[IBaseModel], Any]:
        """算法入口函数。"""
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
class AlgorithmSpec(IAlgorithmSpec):
    _name: str
    _version: str
    _description: str
    _tags: list[str]
    _input_meta: IAlgorithmInputMeta
    _output_meta: IAlgorithmOutputMeta
    _func: Callable[[IBaseModel], Any]

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
    def func(self) -> Callable[[IBaseModel], Any]:
        return self._func
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

class IAppFactory(ABC):
    @abstractmethod
    def create_app(self, registry: IAlgorithmRegistry) -> Any:
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

class InvokeRequest(PydanticBaseModel):
    data: Dict[str, Any]
    request_id: str | None = None

class FastAPIAppFactory(IAppFactory):
    def create_app(self, registry: IAlgorithmRegistry) -> FastAPI:
        app = FastAPI(title="Algo Core Service")

        @app.get("/algorithms")
        def list_algorithms():
            algos = [
                {
                    "name": spec.name,
                    "version": spec.version,
                    "description": spec.description,
                    "tags": spec.tags,
                }
                for spec in registry.list_all()
            ]
            return api_success(data=algos)

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
                    "input_schema": spec.input_meta.schema,
                    "output_schema": spec.output_meta.schema,
                }
            )

        @app.post("/algorithms/{name}/{version}/invoke")
        def invoke(name: str, version: str, req: InvokeRequest):
            spec = registry.get(name, version)
            if not spec:
                return api_error(
                    code=40401,
                    message="Algorithm not found",
                    request_id=req.request_id,
                )

            # 输入解析
            try:
                input_obj = spec.input_meta.model_cls.from_dict(req.data)
            except Exception as e:
                return api_error(
                    code=40001,
                    message=f"Input validation error: {e}",
                    request_id=req.request_id,
                )

            # 执行算法
            try:
                result = spec.func(input_obj)
            except AlgoBizError as e:
                return api_error(
                    code=e.code,
                    message=e.message,
                    data=e.data,
                    request_id=req.request_id,
                )
            except Exception as e:
                return api_error(
                    code=50001,
                    message=f"Algorithm execution error: {e}",
                    request_id=req.request_id,
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
                    request_id=req.request_id,
                )

            return api_success(data=data, request_id=req.request_id)

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
from typing import Callable
from ..core.algorithm_spec_abc import IAlgorithmSpec

class IAlgorithmDecorator(ABC):
    @abstractmethod
    def __call__(
        self,
        name: str,
        version: str = "v1",
        description: str = "",
        tags: list[str] | None = None,
    ) -> Callable:
        """返回一个可作为装饰器使用的 callable。"""
```

#### 2.2.2 `algorithm_decorator_impl.py`

**职责**：  
默认实现：  
- 从函数的 type hints 中提取输入/输出模型（继承自 `BaseModel`）；  
- 生成 `AlgorithmSpec`；  
- 注册到 `global_registry`；  
- 返回原函数。

```python
# algo_sdk/decorators/algorithm_decorator_impl.py
from typing import Callable, get_type_hints, Type
from ..core.base_model_impl import BaseModel
from ..core.algorithm_spec_impl import (
    AlgorithmSpec,
    AlgorithmInputMeta,
    AlgorithmOutputMeta,
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
    ) -> Callable:

        tags = tags or []

        def decorator(fn: Callable):
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

            spec = AlgorithmSpec(
                _name=name,
                _version=version,
                _description=description,
                _tags=tags,
                _input_meta=input_meta,
                _output_meta=output_meta,
                _func=fn,
            )

            global_registry.register(spec)
            return fn

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
抽象 HTTP 层的 `{code, message, data, request_id}` 协议。

```python
# algo_sdk/http/api_schema_abc.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class IApiResponseBuilder(ABC):
    @abstractmethod
    def success(self, data: Any, request_id: str | None = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def error(
        self,
        code: int,
        message: str,
        data: Any = None,
        request_id: str | None = None,
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

class DefaultApiResponseBuilder(IApiResponseBuilder):
    def success(self, data: Any, request_id: str | None = None) -> Dict[str, Any]:
        return {
            "code": 0,
            "message": "success",
            "data": data,
            "request_id": request_id,
        }

    def error(
        self,
        code: int,
        message: str,
        data: Any = None,
        request_id: str | None = None,
    ) -> Dict[str, Any]:
        return {
            "code": code,
            "message": message,
            "data": data,
            "request_id": request_id,
        }

# 简单导出函数，方便 app_factory 使用
_builder = DefaultApiResponseBuilder()

def api_success(data: Any, request_id: str | None = None) -> Dict[str, Any]:
    return _builder.success(data, request_id)

def api_error(
    code: int,
    message: str,
    data: Any = None,
    request_id: str | None = None,
) -> Dict[str, Any]:
    return _builder.error(code, message, data, request_id)
```

---

### 2.4 `algo_sdk.config` 模块（简要）

可选，抽象一些行为，比如：

- 是否所有错误都返回 HTTP 200；
- 是否打印详细异常信息。

这里先只留结构，具体配置可以后补。

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

SERVICE_HOST = os.getenv("SERVICE_HOST", "0.0.0.0")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))
```

---

### 3.2 `main.py`

**职责**：  
1. 导入算法模块（触发 `@Algorithm` 注册）；  
2. 创建 `FastAPI` 应用；  
3. 用 `uvicorn` 启动。

```python
# algo_core_service/main.py
import importlib
import uvicorn

from algo_sdk.core.registry_impl import global_registry
from algo_sdk.core.app_factory_impl import FastAPIAppFactory
from .settings import ALGO_MODULES, SERVICE_HOST, SERVICE_PORT

def load_algorithms():
    for mod_name in ALGO_MODULES:
        mod_name = mod_name.strip()
        if not mod_name:
            continue
        importlib.import_module(mod_name)

def create_app():
    load_algorithms()
    factory = FastAPIAppFactory()
    app = factory.create_app(global_registry)
    return app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)
```

---

### 3.3 `algorithms/orbit_demo.py`（示例算法）

**职责**：  
示例如何使用 `algo_sdk` 写算法。

```python
# algo_core_service/algorithms/orbit_demo.py
from algo_sdk.core.base_model_impl import BaseModel
from algo_sdk.decorators.algorithm_decorator_impl import Algorithm

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
)
def orbit_propagation(req: OrbitInput) -> OrbitOutput:
    dummy_traj = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
    data = {sat_id: dummy_traj for sat_id in req.sats}
    return OrbitOutput(trajectories=data)
```

---

## 4. 小结

- **抽象类和实现类分文件**：
  - `*_abc.py`：定义接口（IBaseModel, IAlgorithmSpec, IAlgorithmRegistry, IAppFactory, IAlgoBizError, IApiResponseBuilder...）
  - `*_impl.py`：给出默认实现（基于 Pydantic、FastAPI、内存 Registry 等）
- **对算法开发者**：
  - 只需要：
    - `from algo_sdk import BaseModel, Algorithm`
    - 定义输入/输出模型；
    - 写一个函数，`@Algorithm` 装饰；
  - 自动获得 HTTP 接口，外部访问统一返回 `{code, message, data, request_id}`。
