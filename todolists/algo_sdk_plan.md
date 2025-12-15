# algo_sdk 開發規劃（protocol/core/decorators）

## 前置假設
- 使用根目錄 `.venv` 內的解釋器與環境；依賴新增統一用 `uv add`。
- 代碼佈局：源碼 `src/`、測試 `tests/`、文檔 `docs/`；遵循 `Python開發規範.md`。
- 以 Agents.md 設計和 docs/algo_core_design.md 為基線，不偏離協議/接口。

## 執行步驟與節點
- [ ] 1) 基線準備
  - [ ] 確認虛擬環境可用，`pyproject.toml` 依賴同步；補充必要的 dev 依賴（如測試/型別工具）。
  - [x] 建立/確認測試骨架：`tests/protocol/`、`tests/core/`、`tests/decorators/`。
  - [ ] 完成基礎 lint/格式化約定（與 Python開發規範.md 對齊）。
- [ ] 2) protocol 層落地
  - [x] 定義標準請求/響應模型：`requestId`、`datetime`、`context`、`data`；`AlgorithmContext`；錯誤碼與響應包裝接口。
  - [x] 補充序列化/驗證邏輯、邊界條件（空 context、非法 datetime、缺失 requestId）。
  - [ ] 單元測試覆蓋模型驗證、默認值、錯誤響應封裝；撰寫 docs/ 區塊說明協議。
  - [ ] 里程碑：模型與測試綠燈，文檔初稿完成。
- [ ] 3) core 抽象
  - [x] 定義基礎模型/基類（如 BaseModel 派生）、算法元數據結構、運行時狀態；錯誤/異常層次。
  - [x] 設計/實現算法註冊表（增/查/去重）及查詢接口；准備與 decorators 的集成點。
  - [ ] 預留應用工廠與執行器接口占位（不實現進程池，但定義 Contract）。
  - [ ] 單元測試：元數據建構、註冊重複檢測、查詢行為與錯誤分支。
  - [ ] 里程碑：核心抽象 API 穩定，測試綠燈。
- [ ] 4) decorators 實現
  - [x] 設計 `@Algorithm` 裝飾器：支持函數與類（含 lifecycle: initialize/run/after_run/shutdown）。
  - [x] 校驗輸入/輸出模型類型（依據 protocol/BaseModel）、抓取算法元數據並註冊到核心註冊表。
  - [x] 支持 execution 策略元數據（isolated_pool、max_workers、timeout_s 等）僅記錄/驗證，不實作執行。
  - [ ] 提供 schema/描述信息導出接口，供 HTTP 層 `/algorithms`、`/schema` 使用。
  - [ ] 單元測試：函數/類裝飾註冊、類型錯誤處理、元數據輸出。
  - [ ] 里程碑：裝飾器功能測試綠燈，示例算法（簡單函數/類）可成功註冊。
- [ ] 5) 集成與文檔
  - [ ] 最小集成驗證：在 src/algo_core_service 中用示例算法調用註冊表，確認可列舉算法與 schema。
  - [ ] 更新 docs：新增 SDK 使用示例（註冊/請求示例），對齊 Agents.md 的 HTTP 協議說明。
  - [ ] 梳理 TODO/風險列表（執行器/觀測性後續工作）。
- [ ] 6) 驗收
  - [ ] 測試總結：單元測試全綠，必要的輕量集成測試通過。
  - [ ] 稽核代碼風格與目錄約定，確保依賴均通過 `uv add`。
  - [ ] 產出變更說明與後續任務清單。
