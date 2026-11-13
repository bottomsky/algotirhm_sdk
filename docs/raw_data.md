# 公共原始参数 rawData

`AlgorithmRequest` 支持顶层可选字段 `rawData: dict[str, Any] | None`。
保留已有 `data` 和超参数协议，不修改算法 `run(req)` 签名。

```json
{
  "requestId": "raw-example",
  "datetime": "2026-11-13T10:00:00+08:00",
  "context": {},
  "data": {"value": 1},
  "rawData": {
    "force": {
      "equipment": [{
        "uuid": "123",
        "equipmentParam": {"platParam": {"customPower": 250}}
      }]
    },
    "unknown_config": {"enabled": true, "optional": null}
  }
}
```

SDK 不解释 `rawData` 的业务结构：内部键名、嵌套对象、列表、数字、字符串、布尔值和
null 均按 JSON 数据传递；不会经过业务 DTO 过滤或命名转换。顶层必须是对象或 null，
省略与 null 都表示未提供，空对象 `{}` 会保留。其他未声明的请求顶层字段仍被拒绝。

## 算法使用

```python
from algo_sdk import get_current_raw_data

def run(self, req: PredictionRequest) -> PredictionResult:
    raw = get_current_raw_data()
    if raw is not None:
        equipments = raw.get("force", {}).get("equipment", [])
        equipment = next(
            item for item in equipments
            if int(item["uuid"]) == req.sat_states.sat_id
        )
        custom_power = equipment["equipmentParam"]["platParam"]["customPower"]
        # 校验必需参数、单位和范围，再用于算法计算。
    # req 继续提供已校验的业务参数和当前仿真状态。
```

API 从 `algo_sdk` 和 `algo_sdk.runtime` 导出。在请求执行范围外或旧调用未提供原始数据时
返回 None。读取值按只读使用；进程内执行通过深复制与调用方对象隔离。
请求数据不存入可复用的算法实例，不会自动出现在响应或 context.extra 中。

执行链路为 `AlgorithmRequest.rawData → ExecutionRequest.raw_data → WorkerPayload
→ ContextVar → get_current_raw_data()`。进程内、共享和独立进程池均支持，
成功、校验失败、算法异常之后都会恢复上下文，嵌套执行也会恢复外层数据。
直接调用执行器时可通过 `ExecutionRequest(..., raw_data=...)` 提供原始数据。

## 仿真后处理服务对接

C# 调用方将外部想定接口的完整 `data` 对象直接保存并放入 `rawData`，不包含外层
code/message；原有算法 `data` 继续携带当前业务输入和实时状态。
筹划、规划、独立威胁分析、任务生成及其内部威胁分析均携带同一调用快照的原始想定。
每份请求只携带一份完整想定，不逐颗卫星重复添加节点。

下面是四类请求的结构示例，仅展示业务容器和 rawData 的位置；实际业务字段仍遵循
各算法输入 Schema，rawData 则替换为完整的原始想定对象：

```json
{"data":{"sat":{},"task":[]},"rawData":{"id":"prepare-scenario","force":{"equipment":[]}}}
```

```json
{"data":{"sat":{},"plannings":[]},"rawData":{"id":"programme-scenario","force":{"equipment":[]}}}
```

```json
{"data":{"sat":{},"targetSats":[]},"rawData":{"id":"prediction-scenario","force":{"equipment":[]}}}
```

```json
{"data":{"sat":{},"sourceSats":[],"targetSats":[],"targetInformation":[]},"rawData":{"id":"task-scenario","force":{"equipment":[]}}}
```

每个示例均需补充公共 requestId、datetime 等信封字段。完整的 C# Prediction 实际请求
示例在调用方仓库 `docs/examples/raw_data_prediction_request.json`。

先发布本 SDK，再发布发送新字段的调用方。旧调用省略 rawData 仍兼容；旧 SDK 会拒绝新字段。

## 验证

```powershell
.venv/Scripts/python.exe -m pytest tests/core/test_raw_data.py -q
```

跨语言测试读取 C# 测试捕获的真实 HTTP 请求体，在三种执行模式下通过 SDK HTTP
入口执行测试算法，并校验完整 JSON 摘要、原始数字字符串、大整数、新载荷和平台参数。
先在 C# 仓库运行：

```powershell
$env:RAW_DATA_CAPTURE_PATH = Join-Path $PWD 'temp/raw-data-http.json'
dotnet test test/unit/SimPost.UnitTests/SimPost.UnitTests.csproj --filter FullyQualifiedName~ActualAlgorithmHttpBodyContainsOriginalScenario
```

然后在 SDK 仓库运行：

```powershell
$env:RAW_DATA_CAPTURE_PATH = 'D:/project/XY/simulation_post_processing/LJ/temp/raw-data-http.json'
.venv/Scripts/python.exe -m pytest tests/http/test_csharp_raw_data_interop.py -q
```

没有提供捕获路径时，这三项跨语言测试会跳过。进程池测试使用测试模块中的可导入类，
保留 Windows spawn 的实际执行方式。

## 请求大小与性能

```powershell
.venv/Scripts/python.exe scripts/benchmark_raw_data.py --satellites 100 1000 --iterations 10
```

合成数据每星包含 6 个载荷。当前机器的一次测量中位数如下；进程启动已预热，
不包含 HTTP 网络和真实算法计算，表中各耗时不能视为生产 SLA。

| 卫星数 | 完整请求字节 | JSON 解码 ms | 信封解析 ms | 进程内执行 ms | 进程池执行 ms |
| --- | --- | --- | --- | --- | --- |
| 100 | 100840 | 1.104 | 2.156 | 5.325 | 7.193 |
| 1000 | 1007140 | 12.294 | 26.623 | 59.041 | 191.786 |

执行耗时包含请求副本；进程池包含 IPC。大想定会增加每次请求的传输、解析及副本成本。
