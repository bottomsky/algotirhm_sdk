# algorithm-service

一个基于 FastAPI 的“算法服务”项目，包含：

- `algo_core_service`：算法服务实例（入口、算法实现）
- `algo_sdk`：算法 SDK（注册、执行、HTTP 服务、观测、注册中心）
- `algo_decorators`：算法装饰器与元数据声明
- `algo_dto`：DTO 数据模型（Pydantic v2）

## 项目架构

### 目录结构

```
algorithm_service/
  config/                     # 算法元数据覆盖配置（*.algometa.yaml）
  src/
    algo_core_service/        # 服务实例（入口 + 内置算法）
      algorithms/             # 示例/Mock 算法集合
      main.py                 # 入口：加载 .env 后启动 HTTP 服务
    algo_sdk/                 # SDK：HTTP 服务、注册中心、执行器、运行时等
      core/                   # 注册器、执行器、算法元数据模型等
      http/                   # FastAPI 服务实现
      logging/                # SDK 日志与事件
      observability/          # 指标/链路等观测能力
      runtime/                # 服务运行时与生命周期
      service_registry/       # 注册中心（Consul / Memory）
    algo_decorators/          # 装饰器：算法声明与元数据
    algo_dto/                 # DTO：请求/响应数据结构（Pydantic）
  scripts/                    # 常用脚本（启动/打包/构建镜像）
  assets/swagger-ui/          # 离线 Swagger UI 静态资源
  data/                       # 示例请求 JSON
  tests/                      # 单元测试
  pyproject.toml / uv.lock     # 依赖与锁定文件（uv）
  .env                        # 本地运行配置
```

### 关键组件

- HTTP 服务与路由：`algo_sdk.http.impl.server.create_app`（FastAPI 应用工厂）
- 服务启动入口：`python -m algo_core_service.main`
  - `algo_core_service/main.py` 会把项目根目录的 `.env` 路径传给 SDK 启动逻辑
- 算法注册：通过环境变量 `ALGO_MODULES` 指定需要加载的模块（默认 `.env` 为 `algo_core_service.algorithms`）
- 算法包加载：通过环境变量 `ALGO_MODULE_DIR` 追加加载目录下的算法包
- 算法元数据覆盖配置：通过环境变量 `ALGO_METADATA_CONFIG_DIR` 指定目录，读取 `*.algometa.yaml` 覆盖算法元数据
- 服务注册中心（可选）：支持 Consul（见 `.env` 中 `SERVICE_REGISTRY_*`）
- Swagger：
  - 在线模式：`SERVICE_SWAGGER_ENABLED=true`，默认 `/docs`
  - 离线模式：`SERVICE_SWAGGER_OFFLINE=true` 且本地存在 `assets/swagger-ui/`

## 快速启动

### 1) 准备虚拟环境（推荐 uv）

本项目使用 `uv.lock` 锁定依赖，推荐用 uv 同步到 `.venv`：

```powershell
uv venv
uv pip sync uv.lock
```

如果你已经有 `.venv`，确保 VS Code / 终端使用该解释器。

### 2) 使用脚本启动（推荐）

Windows（PowerShell）：

```powershell
.\scripts\run_algo_core_service.ps1
```

Linux/macOS：

```bash
sh scripts/run_algo_core_service.sh
```

启动后常用地址：

- Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/healthz`
- 就绪检查：`http://127.0.0.1:8000/readyz`
- 算法列表：`http://127.0.0.1:8000/algorithms`

### 3) 使用 Python 模块启动（不依赖脚本）

```powershell
python -m algo_core_service.main
```

该方式同样会读取项目根目录 `.env` 并启动服务。

## 配置说明（.env + config/）

关键环境变量（示例见项目根目录 `.env`）：

- `SERVICE_PORT` / `SERVICE_BIND_HOST`：监听端口与绑定地址
- `SERVICE_HOST` / `SERVICE_PROTOCOL`：对外访问地址（注册中心/健康检查使用）
- `ALGO_MODULES`：算法模块自动加载列表（逗号分隔）
- `ALGO_MODULE_DIR`：从目录加载算法包（可选）
- `ALGO_METADATA_CONFIG_DIR`：算法元数据覆盖配置目录（可选，读取 `*.algometa.yaml`）
- `SERVICE_REGISTRY_ENABLED` / `SERVICE_REGISTRY_HOST`：是否启用 Consul 注册
- `SERVICE_SWAGGER_ENABLED`：是否开启 Swagger
- `SERVICE_SWAGGER_OFFLINE`：是否启用离线 Swagger（配合 `assets/swagger-ui/`）

配置目录 `config/`：

- `config/algorithms.algometa.yaml`：算法元数据覆盖文件示例（扩展名必须为 `.algometa.yaml`）

## 示例请求

示例 JSON 在 `data/` 目录（用于调用算法接口时参考）：

- `data/prediction_request.json`
- `data/programme_request.json`

## 打包（zip / whl）

打包脚本位于 `scripts/`：

- Windows：`scripts/package_modules.ps1`
- Linux/macOS：`scripts/package_modules.sh`

脚本支持两种模式：

- 分别打包每个模块（默认）：`algo_sdk` / `algo_dto` / `algo_decorators` / `algo_core_service`
- 合并打包为一个 bundle（可选）：通过 BundleName / --bundle-name

### Windows（PowerShell）

构建 zip + whl：

```powershell
.\scripts\package_modules.ps1 -Modules @('algo_sdk','algo_dto') -PackageVersion 0.2.0 -Format both
```

只构建 whl：

```powershell
.\scripts\package_modules.ps1 -Modules @('algo_sdk','algo_dto') -PackageVersion 0.2.0 -Format whl
```

合并打包（bundle）：

```powershell
.\scripts\package_modules.ps1 -Modules @('algo_sdk','algo_dto','algo_decorators') -BundleName algo_modules -PackageVersion 0.2.0 -Format both
```

输出目录默认：`dist/modules/`

### Linux/macOS（sh）

构建 zip + whl：

```bash
sh scripts/package_modules.sh --format both --version 0.2.0 algo_sdk algo_dto
```

只构建 whl：

```bash
sh scripts/package_modules.sh --format whl --version 0.2.0 algo_sdk algo_dto
```

合并打包（bundle）：

```bash
sh scripts/package_modules.sh --format both --bundle-name algo-modules --version 0.2.0 algo_sdk algo_dto algo_decorators
```

## 构建镜像（Docker）

### 1) 使用脚本构建

Windows（PowerShell）：

```powershell
.\scripts\docker_build.ps1 -Tag algo-core-service:latest
```

Linux/macOS：

```bash
sh scripts/docker_build.sh algo-core-service:latest
```

构建完成后默认容器启动命令为：

```bash
sh scripts/run_algo_core_service.sh
```

### 2) docker-compose（含 Consul）

项目提供 `docker-compose.yml`，会启动：

- Consul（开发模式，端口 8500）
- algo-service（绑定 8000）

```bash
docker compose up --build
```

## 开发与检查

- 单测：

```powershell
python -m pytest -q
```

- 类型检查（Pyright）：

```powershell
python -m pyright
```

## 迁移到其他电脑

当前项目可以通过**复制整个仓库目录**的方式迁移到其他机器，但需要注意虚拟环境和全局解释器路径：

1. **推荐做法：在目标机器上重新创建虚拟环境**
   - 不要直接拷贝 `.venv`，而是在目标机器上执行：

   ```powershell
   uv venv
   uv pip sync uv.lock
   ```

   - 这样可以避免由于 Python 绝对路径变化导致的虚拟环境失效问题。

2. **VS Code 中更新 Python 解释器**
   - 打开命令面板：`Ctrl+Shift+P` → 输入并选择 `Python: Select Interpreter`
   - 选择当前仓库下新的 `.venv` 解释器（例如：`.venv\Scripts\python.exe`）
   - 这一步会自动更新 `.vscode/settings.json` 使用的解释器路径。

3. **检查调试配置（launch.json）**
   - 文件位置：`.vscode/launch.json`
   - 调试配置中使用的是相对路径：

   ```jsonc
   "python": "${workspaceFolder}\\.venv\\Scripts\\python.exe"
   ```

   - 只要目标机器上 `.venv` 仍位于仓库根目录，这个配置无需修改；如果你希望使用系统全局 Python，而非 `.venv`，可以：
     - 删除该字段，让 VS Code 使用默认解释器；或者
     - 手动改为新的绝对路径，例如：
       - `"python": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python311\\python.exe"`

4. **命令行环境变量检查**
   - 迁移后，在新机器的项目根目录下，确认：

   ```powershell
   $Env:PYTHONPATH
   ```

   - 使用脚本启动时（`run_algo_core_service.ps1` / `run_algo_core_service.sh`）会自动将 `src` 添加到 `PYTHONPATH`，无需额外调整。

### 拷贝 .venv 的风险与解决办法

不建议直接拷贝 `.venv` 到其他电脑，主要风险如下：

- **解释器绝对路径固化**：Windows 的 `.venv\Scripts\python.exe`、`.venv\pyvenv.cfg`、以及部分已安装包的元数据可能包含创建环境时的绝对路径；换机器或换用户目录后会出现“找不到解释器/模块”等问题。
- **平台与 ABI 不兼容**：跨操作系统（Windows ↔ Linux/macOS）拷贝必然不可用；即便同为 Windows，不同 Python 小版本/架构也可能导致已编译依赖（如 numpy/scipy 等）不可用。
- **依赖状态不可追溯**：直接拷贝的 `.venv` 往往难以确认是否与 `uv.lock` 完全一致，后续排查问题成本高。

可行的解决办法（推荐顺序）：

1. **重新创建虚拟环境（推荐）**

   ```powershell
   uv venv
   uv pip sync uv.lock
   ```

2. **必须拷贝时的折中方案（同系统/同 Python 版本前提）**
   - 在目标机器上先确保 Python 版本与原机器一致（建议用项目的 `requires-python` 约束，并保持 3.11 运行时一致）。
   - 拷贝 `.venv` 后，若出现 pip 或解释器异常，优先用锁文件“重建到一致状态”：

   ```powershell
   uv pip sync uv.lock
   ```

   - 如果 `.venv` 内缺失 pip（例如 `python -m pip` 报错），可先补齐 pip 再同步依赖：

   ```powershell
   uv pip install pip
   uv pip sync uv.lock
   ```
