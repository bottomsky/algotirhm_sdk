# algorithm-service

一个基于 FastAPI 的“算法服务”项目，包含：

- `algo_core_service`：算法服务实例（入口、算法实现）
- `algo_sdk`：算法 SDK（注册、执行、HTTP 服务、观测、注册中心）
- `algo_dto`：DTO 数据模型（Pydantic v2）

## 项目架构

### 目录结构

```
algorithm_service/
  src/
    algo_core_service/        # 服务实例（入口 + 内置算法）
      algorithms/             # 示例/Mock 算法集合
      main.py                 # 入口：加载 .env 后启动 HTTP 服务
    algo_sdk/                 # SDK：HTTP 服务、注册中心、执行器、运行时等
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

## 配置说明（.env）

关键环境变量（示例见项目根目录 `.env`）：

- `SERVICE_PORT` / `SERVICE_BIND_HOST`：监听端口与绑定地址
- `SERVICE_HOST` / `SERVICE_PROTOCOL`：对外访问地址（注册中心/健康检查使用）
- `ALGO_MODULES`：算法模块自动加载列表（逗号分隔）
- `SERVICE_REGISTRY_ENABLED` / `SERVICE_REGISTRY_HOST`：是否启用 Consul 注册
- `SERVICE_SWAGGER_ENABLED`：是否开启 Swagger
- `SERVICE_SWAGGER_OFFLINE`：是否启用离线 Swagger（配合 `assets/swagger-ui/`）

## 示例请求

示例 JSON 在 `data/` 目录（用于调用算法接口时参考）：

- `data/prediction_request.json`
- `data/programme_request.json`

## 打包（zip / whl）

打包脚本位于 `scripts/`：

- Windows：`scripts/package_modules.ps1`
- Linux/macOS：`scripts/package_modules.sh`

### Windows（PowerShell）

构建 zip + whl：

```powershell
.\scripts\package_modules.ps1 -Modules @('algo_sdk','algo_dto') -PackageVersion 0.2.0 -Format both
```

只构建 whl：

```powershell
.\scripts\package_modules.ps1 -Modules @('algo_sdk','algo_dto') -PackageVersion 0.2.0 -Format whl
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
