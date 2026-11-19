# 条件算法示例：检测己方故障卫星

`Condition/v1` 判断当前帧中是否存在己方故障卫星。卫星的 `forceType`
与请求中的 `forceType` 相同，且 `isSatFault == 1` 时返回 `true`。
仅敌方故障、己方均正常或卫星字典为空时返回 `false`。
其他整数故障标志不视为故障。

## 实现位置

- 算法：`src/algo_core_service/algorithms/condition.py`
- 输入输出 DTO：`src/algo_dto/condition.py`
- 完整 C# 业务模型：`src/algo_dto/csharp_models.py`
- 注册：算法包导出 `ConditionAlgorithm`，沿用 `@Algorithm` 自动加载机制。

算法类型为 `Condition`，分类为 `BehaviorTree`，采用进程内执行。
业务输入为 `ConditionRequest`，输出为 `ConditionResult(RootModel[bool])`。
`run()` 只返回业务结果，SDK 负责统一的请求解析、校验和响应封装。

## 启动服务

在 SDK 根目录执行 PowerShell 命令：

```powershell
Set-Location D:\project\algotirhm_sdk
uv sync --frozen
$env:SERVICE_REGISTRY_ENABLED = "false"
.\scripts\run_algo_core_service.ps1
```

上述命令临时关闭本地服务注册，便于独立验证示例；需要接入 Consul 时，
省略该环境变量设置并使用已有注册中心配置。无需修改 `.env`。

根目录 `.env` 中的 `ALGO_MODULES` 应包含 `algo_core_service.algorithms`，
当前默认配置已包含。监听地址和端口由服务配置决定；下文以本机 `8000` 端口为例。

可通过以下接口检查加载结果：

- `GET /algorithms`：包含名称 `Condition`、版本 `v1`。
- `GET /algorithms/Condition/v1/schema`：`data.output.type` 为 `boolean`。

## 请求示例

向 `POST /algorithms/Condition/v1` 发送 SDK 标准请求：

```json
{
  "requestId": "condition-demo-001",
  "datetime": "2026-11-13T15:00:00+08:00",
  "context": {},
  "data": {
    "frameData": {
      "data": {
        "1001": {"forceType": 1, "isSatFault": 1},
        "1002": {"forceType": 2, "isSatFault": 0}
      }
    },
    "projectDto": {},
    "forceType": 1,
    "satId": "1001"
  }
}
```

字段约定：

| 字段 | 含义 |
| --- | --- |
| `data.frameData.data` | 卫星 ID 到状态的字典，允许为空 |
| 卫星状态的 `forceType` | 必填整数，卫星所属阵营 |
| 卫星状态的 `isSatFault` | 必填整数，1 表示故障 |
| `data.projectDto` | 必填 ProjectDTO 模型，可为 `{}`，采用 C# 默认值 |
| `data.forceType` | 必填整数，当前行为树所属阵营 |
| `data.satId` | 当前行为树的卫星标识字符串，省略时为空；兼容输入别名 `sateId` |

DTO 沿用 `CamelBaseModel` 的命名约定：接受 C# JSON 字段名与 Python
snake_case 属性名。帧、卫星及项目对象中已知字段均有类型，并保留未知扩展字段；
请求业务根对象仍忽略额外上下文字段。向量复用 SDK 的 Vector3/4/6，校验数组长度。
`satId` 从行为树黑板的 `SatelliteId` 读取，仅作为上下文传递；本示例仍判断
己方是否存在故障卫星，不按该标识筛选卫星。

## 完整 C# 模型

模型来自本服务当前引用的 `LJ.DTO 1.0.12`，从 ProjectDTO、SimData 递归提取
34 个模型、242 个序列化字段，包括装备递归结构、平台能力、八类载荷、轨道参数、
姿态、卫星实时状态、脚本及平台事件。C# 继承属性在 Python 模型中完整展开。
只包含当前 JSON 协议可见的属性；`[JsonIgnore]` 的 RawData、Time，以及未开启
IncludeFields 时不参与序列化的 ScriptVo.PayloadParamsAll 字段不生成。

常用访问方式：

```python
from algo_dto.condition import ConditionRequest
from algo_dto.csharp_models import ProjectDTO

def read_platform(req: ConditionRequest) -> float:
    project: ProjectDTO = req.project_dto
    equipment = project.force.equipment[0]
    platform = equipment.equipment_param.plat_param
    return platform.sat_mass

# JSON algorithmsSatType 对应 Python sat_type。
# AttReFrame、Isp、Thrust、m_TarSize、relations 后的空格等沿用 C# 原始别名。
# 未知参数可通过对应对象的 model_extra 字典读取。
```

保持原有必填规则：frameData.data、projectDto、forceType，以及每颗卫星的
forceType/isSatFault 必填。其他已知字段采用 C# 默认值，可空字段用 `None`。
集合使用 default_factory，实例之间不共享数据。日期在 Python 中为 datetime；
JSON 导出采用 SDK 的 ISO 日期格式，可能规范化时区或小数秒的文本表示。
C# getter 的快照字段（如 bjt、sunPosition）也已建模并在 Schema 中标记 readOnly；
Python 接收这些快照，不实现 C# getter 的运行时计算。

项目参数中的动态字典和 JsonElement 使用 `JsonValue`；已知业务结构不使用 Any
代替。未知 JSON 仅能保留实际收到的内容；C# 强类型 DTO 已丢弃的原始字段需要
通过公共顶层 rawData 通道传递，不能由这些模型恢复。

模型可重复生成。升级共享包后，在 SDK 根目录运行（需安装 .NET 10）：

```powershell
dotnet restore scripts/csharp_contract/DtoContract.csproj --source D:/nuget
dotnet run --project scripts/csharp_contract/DtoContract.csproj --no-restore -- tests/fixtures/csharp_condition_contract.json
.\.venv\Scripts\python.exe scripts/generate_csharp_models.py
```

导出器使用与 C# 条件节点相同的 JsonSerializerDefaults.Web 配置，保存属性元数据和
实际序列化的完整样例。生成器依据该契约输出静态 Pydantic 类，运行 SDK 无需 .NET。
后续升级版本时先修改导出项目的 DtoVersion，再重新生成并运行契约测试。

也可以在 PowerShell 中直接调用：

```powershell
$payload = @{
    requestId = "condition-demo-001"
    datetime = [DateTimeOffset]::Now.ToString("o")
    context = @{}
    data = @{
        frameData = @{
            data = @{
                "1001" = @{ forceType = 1; isSatFault = 1 }
            }
        }
        projectDto = @{}
        forceType = 1
        satId = "1001"
    }
}
$body = $payload | ConvertTo-Json -Depth 20
Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/algorithms/Condition/v1" `
    -ContentType "application/json" -Body $body
```

## 响应示例

上面的己方卫星故障请求返回以下结构，响应时间由 SDK 生成：

```json
{
  "code": 0,
  "message": "success",
  "algorithmName": "Condition",
  "requestId": "condition-demo-001",
  "datetime": "2026-11-13T07:00:00Z",
  "context": null,
  "data": true
}
```

将卫星 `1001` 的 `isSatFault` 改为 `0` 后，响应仍为 `code: 0`，
`data` 变为 `false`。`data` 直接是布尔值，不包装为 `{"root": false}`
或 `{"result": false}`，也不会变为 `null`。

条件不成立是正常执行结果。缺失必要业务字段或字段类型非法时，沿用 SDK
业务校验错误流程：当前 HTTP 状态为 `200`，响应 `code` 为 `400`、`data`
为 `null`。标准请求外层缺失 `requestId`、`datetime` 等字段时，FastAPI
返回 HTTP `422`。

## 行为树后续对接

当前行为树条件节点直接发送 `{frameData, projectDto, forceType, satId}`，
`satId` 每次判断时从黑板读取，缺失时发送空字符串。
接入此示例时，需要将这四个字段放入标准请求的 `data` 中，并补齐
`requestId`、`datetime`。通用请求协议保持不变。
调用方成功判定仍可使用 `code == 0 && data == true`。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core/test_condition.py tests/http/test_condition.py -q
.\.venv\Scripts\python.exe -m pytest tests/core/test_csharp_condition_models.py tests/logging/test_payload_json.py -q
```

本次相关测试 84 项通过，覆盖全部字段映射、完整 C# JSON 往返、未知字段保留、
独立集合默认值、向量校验、生成结果一致性、Schema 和三种 SDK 执行模式。
