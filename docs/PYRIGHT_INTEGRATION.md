# Pyright 与命名规范集成指南

## 概述

本项目集成了 **Pyright** 进行严格的类型检查，同时提供了自定义的**命名规范检查工具**来强制执行一致的命名约定。

## 组件说明

### 1. Pyright 配置

**文件**:

- `pyproject.toml` - 项目范围配置
- `pyrightconfig.json` - Pyright 专用配置

**主要配置项**：

- `typeCheckingMode`: `strict` - 启用严格类型检查
- `reportUnusedImport`: `warning` - 未使用的导入警告
- `reportUnusedClass`: `warning` - 未使用的类警告
- `reportUnusedFunction`: `warning` - 未使用的函数警告
- `reportUnusedVariable`: `warning` - 未使用的变量警告

### 2. 自定义命名规范检查工具

**文件**: `scripts/check_naming_convention.py`

**功能**：

- 检查 ABC 类是否以 `Base` 开头
- 检查 Protocol 类是否以 `Protocol` 结尾
- 验证实现类不以 `Base` 开头（排除特殊情况）
- 生成详细的违反报告

**使用方式**：

```bash
# 手动运行
python scripts/check_naming_convention.py

# 输出示例
🔍 扫描 D:\LJ_project\algorithm_service/src 中的 Python 文件...
✅ 所有命名规范检查通过！
```

### 3. IDE 集成

**VS Code 配置**：

- `.vscode/settings.json` - 启用 Pyright strict 模式
- `.vscode/extensions.json` - 推荐扩展

**推荐扩展**：

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)

## 使用步骤

### 步骤 1：安装 Pyright

```bash
# 使用 npm
npm install -g pyright

# 或使用 pip
pip install pyright
```

### 步骤 2：运行类型检查

```bash
# 运行 Pyright
pyright

# 或在 VS Code 中使用 Pylance（自动集成）
```

### 步骤 3：运行命名规范检查

```bash
# 检查所有类的命名是否符合规范
python scripts/check_naming_convention.py
```

### 步骤 4（可选）：安装 Pre-commit 钩子

#### Windows (PowerShell)

```powershell
# 复制钩子脚本
Copy-Item scripts/pre-commit.ps1 .git/hooks/pre-commit

# 设置执行策略（如需要）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Unix/Linux/macOS

```bash
# 复制钩子脚本
cp scripts/pre-commit .git/hooks/pre-commit

# 设置可执行权限
chmod +x .git/hooks/pre-commit
```

配置后，每次提交时会自动运行命名规范检查。

## 命名规范详解

### 抽象基类 (ABC)

```python
from abc import ABC, abstractmethod

class BaseServiceRegistry(ABC):
    """服务注册的抽象基类"""
    
    @abstractmethod
    def register(self, service: Service) -> None:
        """注册服务"""
        ...
```

**命名规则**：

- 以 `Base` 开头
- 继承自 `ABC`
- 至少有一个 `@abstractmethod` 方法
- 实例化时必须实现所有抽象方法

### 协议类 (Protocol)

```python
from typing import Protocol

class ExecutorProtocol(Protocol):
    """执行器协议"""
    
    def execute(self, task: Task) -> Result:
        """执行任务"""
        ...
```

**命名规则**：

- 以 `Protocol` 结尾
- 继承自 `Protocol`
- 无需显式实现，支持结构化子类型
- 用于类型注解

### 实现类

```python
class ConsulRegistry(BaseServiceRegistry):
    """Consul 服务注册实现"""
    
    def register(self, service: Service) -> None:
        # 实现
        pass
```

**命名规则**：

- 无特殊前缀/后缀
- 使用标准大驼峰 (PascalCase)
- 继承自 ABC 或实现 Protocol
- 必须实现所有抽象方法，使用 `@override` 标记

## 故障排除

### 问题 1: Pyright 找不到模块

**解决**：

```bash
# 确保 PYTHONPATH 包含 src 目录
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# 或在 pyrightconfig.json 中配置
{
  "include": ["src", "tests"]
}
```

### 问题 2: 命名检查失败

**解决**：

1. 运行检查脚本查看具体违反项
2. 按照规范重命名类
3. 更新所有导入和引用

### 问题 3: Pre-commit 钩子不执行

**解决 (Windows)**：

```powershell
# 检查钩子文件是否存在
Test-Path .git/hooks/pre-commit

# 检查执行权限
Get-ExecutionPolicy

# 临时允许脚本执行
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

## CI/CD 集成

### GitHub Actions 示例

```yaml
name: Type Check and Naming Convention

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pyright
          pip install -e .
      
      - name: Run Pyright
        run: pyright
      
      - name: Run naming convention check
        run: python scripts/check_naming_convention.py
```

## 常见问题 (FAQ)

**Q: 为什么 BaseModel 不被标记为错误？**
A: `BaseModel` 被排除在检查之外，因为它是 Pydantic 模型的包装类，是整个项目的基础类型，合理使用 `Base` 前缀。

**Q: 是否可以为特定类禁用命名检查？**
A: 可以在 `check_naming_convention.py` 中的 `_is_excluded_class` 方法中添加排除规则。

**Q: Pyright 和 Pylance 的区别？**
A: Pylance 是 Pyright 的 VS Code 集成版本，两者共享核心类型检查引擎。

## 参考资源

- [Pyright 官方文档](https://github.com/microsoft/pyright/blob/main/docs/configuration.md)
- [Python 开发规范](../Python开发规范.md.md)
- [命名规范详情](../NAMING_CONVENTION.md)
