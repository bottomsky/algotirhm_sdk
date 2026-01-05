# 命名规范检查报告

## 概述

本项目遵循统一的命名规范：

- **抽象基类 (ABC)**：以 `Base` 开头
- **协议类 (Protocol)**：以 `Protocol` 结尾
- **具体实现类**：无特殊前缀/后缀，使用标准大驼峰命名

## 完整命名清单

### ✅ 服务注册模块 (`service_registry`)

| 类名 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `BaseServiceRegistry` | ABC | protocol.py | 服务注册抽象基类 |
| `ConsulRegistry` | 实现类 | consul_registry.py | Consul 注册实现 |
| `MemoryRegistry` | 实现类 | memory_registry.py | 内存注册实现（用于测试） |
| `ServiceInstance` | 数据类 | protocol.py | 服务实例模型 |
| `ServiceRegistration` | 数据类 | protocol.py | 服务注册请求模型 |
| `HealthCheck` | 数据类 | protocol.py | 健康检查配置 |
| `ServiceStatus` | 枚举 | protocol.py | 服务状态枚举 |

### ✅ 核心算法模块 (`core`)

| 类名 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `BaseAlgorithm` | ABC | lifecycle.py | 算法抽象基类（含默认实现） |
| `AlgorithmLifecycleProtocol` | Protocol | lifecycle.py | 算法生命周期协议 |
| `BaseModel` | 基类 | base_model_impl.py | Pydantic 模型基类 |
| `AlgorithmSpec` | 数据类 | metadata.py | 算法元数据 |
| `ExecutionConfig` | 数据类 | metadata.py | 执行配置 |
| `AlgorithmRegistry` | 注册表 | registry.py | 算法注册中心 |
| `ExecutorProtocol` | Protocol | executor.py | 执行器协议 |
| `ApplicationFactoryProtocol` | Protocol | app_factory.py | 应用工厂协议 |

### ✅ 装饰器模块 (`decorators`)

| 类名 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `DefaultAlgorithmDecorator` | 装饰器 | algorithm_decorator_impl.py | 算法装饰器实现 |

## 使用示例

### 定义新的抽象基类

```python
from abc import ABC, abstractmethod

class BaseMyComponent(ABC):
    """My component abstract base class."""
    
    @abstractmethod
    def process(self, data: dict) -> dict:
        """Process data."""
        ...

# 实现类
class ConsulMyComponent(BaseMyComponent):
    """Consul implementation."""
    
    def process(self, data: dict) -> dict:
        # implementation
        return data
```

### 定义新的协议类

```python
from typing import Protocol

class MyComponentProtocol(Protocol):
    """Contract for my component."""
    
    def process(self, data: dict) -> dict:
        """Process data."""
        ...

# 使用协议进行类型注解（无需显式继承）
def use_component(comp: MyComponentProtocol) -> None:
    result = comp.process({"key": "value"})
```

### 实现抽象基类

```python
from typing import override

class MyImplementation(BaseMyComponent):
    """Implementation of BaseMyComponent."""
    
    @override
    def process(self, data: dict) -> dict:
        return {"processed": data}
```

## 导出规范

### 公开 API 导出

```python
# module/__init__.py

from .protocol import BaseServiceRegistry, ServiceInstance
from .consul_registry import ConsulRegistry
from .memory_registry import MemoryRegistry

__all__ = [
    "BaseServiceRegistry",
    "ServiceInstance",
    "ConsulRegistry",
    "MemoryRegistry",
]
```

## 检查清单

在代码审查时使用以下清单：

- [ ] 所有 ABC 类都以 `Base` 开头
- [ ] 所有 Protocol 类都以 `Protocol` 结尾
- [ ] 所有实现类都继承自对应的 Base 或 Protocol 类
- [ ] 实现类的方法都标记了 `@override` 装饰器
- [ ] 抽象方法都标记了 `@abstractmethod` 装饰器
- [ ] `__init__.py` 中的导出与实际公开 API 一致
- [ ] 类型提示完整，避免使用 `Any`

## 相关文档

- [Python 开发规范](Python开发规范.md.md)
- [算法核心服务设计](Agents.md)
- [算法核心设计文档](docs/algo_core_design.md)
