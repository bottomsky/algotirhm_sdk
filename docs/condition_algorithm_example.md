# 条件算法示例：检测己方故障卫星

`Condition/v1` 判断当前帧中是否存在己方故障卫星。卫星的 `forceType`
与请求中的 `forceType` 相同，且 `isSatFault == 1` 时返回 `true`。
仅敌方故障、己方均正常或卫星字典为空时返回 `false`。
其他整数故障标志不视为故障。

## 实现位置

- 算法：`src/algo_core_service/algorithms/condition.py`
- 输入输出 DTO：`src/algo_dto/condition.py`
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
| `data.projectDto` | 必填项目上下文字典，可为 `{}`，本示例不参与判断 |
| `data.forceType` | 必填整数，当前行为树所属阵营 |
| `data.satId` | 当前行为树的卫星标识字符串，省略时为空；兼容输入别名 `sateId` |

DTO 沿用 `CamelBaseModel` 的行为：接受 camelCase JSON 字段名与 Python
snake_case 字段名，忽略未参与建模的其他帧、卫星和请求业务字段。
`projectDto` 的字典内容正常接收。
`satId` 从行为树黑板的 `SatelliteId` 读取，仅作为上下文传递；本示例仍判断
己方是否存在故障卫星，不按该标识筛选卫星。

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
```
