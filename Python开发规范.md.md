# Python 开发常见规范

Python 开发规范围绕**代码可读性、可维护性、一致性**展开，核心是官方推荐的 [PEP 8](https://peps.python.org/pep-0008/)，同时涵盖命名、文档、项目结构等通用准则，以下是详细分类总结。

## 一、代码格式规范（PEP 8 核心）

PEP 8 定义了 Python 代码的基础格式，是所有 Python 开发者的通用准则。

### 1. 缩进

* 使用**4 个空格**作为缩进（禁止使用 Tab，若用 Tab 需保证全项目一致）。

* 换行后的续行应缩进**4 个空格**（或使用括号自动换行，保持视觉对齐）。

```
\# 推荐

total = (first\_variable

&#x20;        \+ second\_variable

&#x20;        \+ third\_variable)

\# 不推荐（Tab 或 2 个空格）

total = first\_variable

&#x20; \+ second\_variable
```

### 2. 行长度

* 单行代码不超过**79 个字符**（注释 / 文档字符串不超过 72 个字符）。

* 超过时需换行，优先在**运算符后**换行，保持逻辑清晰。

### 3. 空行

* 顶层函数 / 类之间用**2 个空行**分隔。

* 类内的方法之间用**1 个空行**分隔。

* 函数内的逻辑块之间用**1 个空行**分隔（避免过多空行）。

```
def func1():

&#x20;   pass

class MyClass:

&#x20;   def method1(self):

&#x20;       pass

&#x20;   def method2(self):

&#x20;       pass
```

### 4. 空格使用

* **二元运算符**（`=`, `+`, `-`, `*`, `/`, `==` 等）两侧各加 1 个空格。

```
x = 1 + 2  # 推荐

x=1+2      # 不推荐
```

* **函数 / 方法参数**的等号两侧**不加空格**（默认参数除外）。

```
def func(a, b=3):  # 推荐

def func(a , b = 3):  # 不推荐
```

* **逗号、分号、冒号前**不加空格，**后加 1 个空格**（切片的冒号两侧空格可选，保持一致即可）。

```
list = \[1, 2, 3]

if x > 0:

&#x20;   pass

arr = arr\[1:5]  # 或 arr\[1: 5]，统一风格
```

### 5. 导入规范

* **导入顺序**：标准库 → 第三方库 → 本地项目库（各部分之间用空行分隔）。

* **禁止通配符导入**（`from module import *`），会导致命名空间混乱。

* **单行导入一个模块**，避免一行多个导入（除非是同模块的多个对象）。

```
\# 推荐

import os

import sys

import requests

from my\_project import utils

\# 不推荐

import os, sys

from module import \*
```

* 导入路径使用**绝对路径**，除非是内部模块的相对导入。

## 二、命名规范（PEP 8 + PEP 257）

命名的可读性直接影响代码理解，Python 有明确的命名风格约定：

| 类型           | 命名风格              | 示例                          |
| ------------ | ----------------- | --------------------------- |
| 变量 / 函数 / 方法 | 蛇形小写（snake\_case） | `user_name`, `get_data()`   |
| 常量           | 全大写蛇形             | `MAX_SIZE`, `PI = 3.14159`  |
| 类 / 异常       | 大驼峰（CamelCase）    | `User`, `FileNotFoundError` |
| **抽象基类**    | `Base` 前缀           | `BaseRegistry`, `BaseAlgorithm` |
| **协议类**      | `Protocol` 后缀       | `ExecutorProtocol`, `ApplicationFactoryProtocol` |
| 私有变量 / 方法    | 前置单下划线（\_）        | `_internal_func`            |
| 避免与关键字冲突的变量  | 后置单下划线（\_）        | `class_`                    |
| 魔术方法（内置）     | 前后双下划线（\_\_）      | `__init__`, `__str__`       |

**注意**：
* 双下划线开头的变量会触发**名称修饰（name mangling）**，一般仅用于类的私有属性，不建议普通场景使用。
* **抽象基类（ABC）**：继承 `ABC` 且定义 `@abstractmethod` 的类，应以 `Base` 开头，如 `BaseServiceRegistry`。实现类无前缀，如 `ConsulRegistry`, `MemoryRegistry`。
* **协议类（Protocol）**：定义结构化类型约束的类，应以 `Protocol` 结尾，如 `AlgorithmLifecycleProtocol`, `ExecutorProtocol`。

## 三、代码编写规范

### 1. 避免冗余代码

* 不用单行 `if/for/while`（除非逻辑极简单），保持代码块的清晰。

* 避免重复的逻辑，提取为函数 / 方法。

### 2. 条件判断

* 直接使用布尔值判断（`if flag` 而非 `if flag is True`）。

* 多条件判断优先用 `in`（`if x in [1,2,3]` 而非 `if x ==1 or x==2 or x==3`）。

* 空值判断用 `if not lst`（而非 `if len(lst) == 0`）。

### 3. 循环与迭代

* 优先使用列表推导式 / 生成器表达式替代简单的循环（但避免过于复杂的推导式）。

```
\# 推荐

squares = \[x\*\*2 for x in range(10)]

\# 不推荐（简单场景）

squares = \[]

for x in range(10):

&#x20;   squares.append(x\*\*2)
```

* 遍历可迭代对象时，用 `enumerate` 获取索引和值（`for i, val in enumerate(lst)`）。

### 4. 异常处理

* 精准捕获异常（`except ValueError` 而非 `except`），避免捕获所有异常。

* 异常处理需有意义（如记录日志、提示用户），不做空的 `except`。

```
\# 推荐

try:

&#x20;   num = int(input("输入数字："))

except ValueError as e:

&#x20;   print(f"输入错误：{e}")

\# 不推荐

try:

&#x20;   num = int(input("输入数字："))

except:

&#x20;   pass
```

* 使用 `finally` 释放资源（如文件、网络连接），或用 `with` 语句（上下文管理器）。

### 5. 函数 / 方法设计

* 遵循**单一职责原则**：一个函数只做一件事。

* 函数参数不宜过多（建议不超过 5 个），过多时用字典 / 数据类封装。

* 函数返回值保持一致（避免有时返回列表，有时返回 None）。

* 使用**默认参数**时，避免用可变对象（如列表、字典）作为默认值（会导致多次调用共享对象）。

```
\# 错误示例

def func(lst=\[]):

&#x20;   lst.append(1)

&#x20;   return lst

\# 调用两次会得到 \[1,1]，而非 \[1]

\# 正确示例

def func(lst=None):

&#x20;   if lst is None:

&#x20;       lst = \[]

&#x20;   lst.append(1)

&#x20;   return lst
```

## 四、文档规范（PEP 257）

良好的文档是代码可维护性的关键，Python 推荐使用**文档字符串（docstring）**。

### 1. 文档字符串类型

* **单行 docstring**：适用于简单函数，用三引号包裹，内容简洁。

```
def add(a, b):

&#x20;   """返回两个数的和。"""

&#x20;   return a + b
```

* **多行 docstring**：适用于复杂函数 / 类，包含功能描述、参数、返回值、异常等。

```
def divide(a, b):

&#x20;   """

&#x20;   计算两个数的商。

&#x20;  &#x20;

&#x20;   参数:

&#x20;       a (int/float): 被除数

&#x20;       b (int/float): 除数（不能为0）

&#x20;  &#x20;

&#x20;   返回:

&#x20;       float: 两个数的商

&#x20;  &#x20;

&#x20;   异常:

&#x20;       ZeroDivisionError: 当除数为0时抛出

&#x20;   """

&#x20;   if b == 0:

&#x20;       raise ZeroDivisionError("除数不能为0")

&#x20;   return a / b
```

### 2. 文档工具

* 常用 `Sphinx` 生成自动化文档，支持 reStructuredText 或 Markdown 格式。

* 遵循 `Google 风格` 或 `NumPy 风格` 的 docstring（更易读，且有工具支持解析）。

## 五、项目结构规范

合理的项目结构能提升可维护性，常见的 Python 项目结构如下：

```
my\_project/

├── my\_project/          # 主包（源代码目录）

│   ├── \_\_init\_\_.py      # 包标识

│   ├── core/            # 核心逻辑模块

│   ├── utils/           # 工具函数模块

│   └── config/          # 配置模块

├── tests/               # 测试用例目录

│   ├── \_\_init\_\_.py

│   └── test\_core.py

├── docs/                # 文档目录

├── requirements.txt     # 依赖清单

├── setup.py/setup.cfg   # 打包配置（若发布包）

└── README.md            # 项目说明
```

**关键要点**：

* 用包（`__init__.py`）组织模块，避免扁平的文件结构。

* 配置文件（如 `config.py`、`settings.yaml`）独立存放，不硬编码常量。

* 测试用例与源代码分离，遵循 `pytest` 或 `unittest` 规范。

## 六、其他通用规范

### 1. 版本与依赖

* 使用 `requirements.txt` 或 `pyproject.toml`（PEP 621）管理依赖，指定版本号（避免依赖冲突）。

* 推荐使用虚拟环境（`venv`、`conda`、`poetry`）隔离项目依赖。

### 2. 代码检查工具

* 用 `flake8`/`pylint` 检查 PEP 8 合规性和代码质量。

* 用 `black`/`yapf` 自动格式化代码（保证团队风格一致）。

* 用 `mypy` 做静态类型检查（PEP 484，提升代码健壮性）。

### 3. 注释规范

* 注释应解释**为什么**，而非**做什么**（代码本身应能说明做什么）。

* 避免无用的注释（如 `# 加 1` 注释 `x += 1`）。

* 复杂逻辑处加注释，临时调试的代码用 `# TODO` 标记，后续清理。

## 总结

Python 开发规范的核心是**PEP 8**，在此基础上结合命名、文档、项目结构等规范，最终目标是让代码**易读、易维护、易协作**。实际开发中，团队可根据自身需求制定更细化的规范，但需保持团队内部的一致性。同时，借助代码检查和格式化工具，能大幅降低规范执行的成本。

> （注：文档部分内容可能由 AI 生成）
