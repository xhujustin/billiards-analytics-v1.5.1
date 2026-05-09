# AI Coach 整合指南

AI Coach 是獨立服務，和 `billiards-analytics-v1.5.1` 主後端之間只允許透過 WebSocket 或 HTTP 溝通。主後端不得直接 `import ai_coach`，也不得用 `sys.path` 指到 `ai_coach/src` 後呼叫內部類別。

## 架構邊界

```text
frontend
  -> HTTP POST /api/coach/chat 或 /api/coach/suggest
  -> billiards backend
  -> WebSocket ws://localhost:8010/ws/coach
  -> ai_coach service
  -> HTTP http://localhost:8002/v1/chat/completions
  -> vLLM / OpenAI-compatible endpoint
```

責任分工：

- 主後端負責 YOLO、ROI、路徑規劃、檯面語意化與對前端提供 `/api/coach/*` API。
- `ai_coach` 只負責接收主後端送來的語意化 context、組 prompt、呼叫 LLM endpoint，並回傳教練建議。
- vLLM 或其他 OpenAI-compatible 服務只由 `ai_coach` 透過 HTTP 呼叫。

## 啟動方式

先啟動 vLLM 或相容服務，確認下列 endpoint 可用：

```powershell
Invoke-RestMethod http://localhost:8002/v1/models
```

再啟動 AI Coach：

```powershell
cd ai_coach
.\start.bat
```

`start.bat` 只會使用 `ai_coach\.venv\Scripts\python.exe` 或系統 Python，不會讀取主專案根目錄 `.venv`。若要固定使用 AI Coach 自己的虛擬環境：

```powershell
cd ai_coach
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\start.bat
```

## 環境變數

AI Coach service：

```text
AI_COACH_HOST=0.0.0.0
AI_COACH_PORT=8010
AI_COACH_API_URL=http://localhost:8002/v1/chat/completions
AI_COACH_MODEL=/home/lucian039/gemma-4-awq
AI_COACH_VLLM_TIMEOUT_SECONDS=300
AI_COACH_MAX_TOKENS=80
AI_COACH_MAX_PROMPT_CHARS=900
AI_COACH_SERVER_WS_PING_INTERVAL=0
AI_COACH_SERVER_WS_PING_TIMEOUT=0
```

主後端：

```text
AI_COACH_ENABLED=true
AI_COACH_MODE=websocket
AI_COACH_WS_URL=ws://localhost:8010/ws/coach
AI_COACH_SESSION_ID=backend_yolo
AI_COACH_RECONNECT_SECONDS=3
AI_COACH_REQUEST_TIMEOUT_SECONDS=90
AI_COACH_WS_PING_INTERVAL=0
AI_COACH_WS_PING_TIMEOUT=0
AI_COACH_AUTO_SUGGESTIONS_ENABLED=false
```

## WebSocket 契約

端點：

```text
ws://localhost:8010/ws/coach
```

手動聊天請求：

```json
{
  "type": "chat.request",
  "request_id": "uuid",
  "session_id": "backend_yolo",
  "payload": {
    "message": "這球怎麼打？",
    "context": {
      "semantic_context": {
        "valid": true,
        "stable": true,
        "rules": {
          "game": "nine_ball",
          "legal_target_number": 1
        }
      }
    }
  }
}
```

自動分析請求：

```json
{
  "type": "analysis.request",
  "request_id": "uuid",
  "session_id": "backend_yolo",
  "payload": {
    "semantic_context": {
      "valid": true,
      "stable": true
    }
  }
}
```

成功回覆：

```json
{
  "type": "coach.result",
  "request_id": "uuid",
  "status": "success",
  "payload": {
    "timestamp": "2026-05-07T15:30:00",
    "semantic_description": "legal target summary",
    "recommendation": "先打 1 號球，控制母球停在中袋附近。",
    "confidence": 0.8,
    "processing_time": 1.234,
    "error": null
  }
}
```

錯誤回覆：

```json
{
  "type": "coach.error",
  "request_id": "uuid",
  "status": "error",
  "payload": {
    "error": "Missing message"
  }
}
```

## HTTP 契約

AI Coach health check：

```powershell
Invoke-RestMethod http://localhost:8010/health
```

主後端對前端提供的 API：

```text
POST /api/coach/chat
POST /api/coach/suggest
GET  /api/coach/state
```

前端只呼叫主後端 `/api/coach/*`，不直接連 `ai_coach` service。主後端再用 `CoachBridge` 轉送到 `ws://localhost:8010/ws/coach`。

## 禁止用法

以下做法會破壞解耦，請勿新增：

```python
from ai_coach import AICoachManager
from ai_coach.core.client import AICoachManager
from ai_coach.tools.websocket_coach import SuggestionGenerator
```

也不要在主後端加入：

```python
import sys
sys.path.insert(0, "ai_coach/src")
```

如需新增能力，先擴充 WebSocket message payload 或 HTTP API 契約，再分別調整主後端與 `ai_coach` service。
## 05/07:'新增 start.bat 自動啟動 vLLM 功能'

`start.bat` 目前預設會自動檢查並啟動 vLLM。啟動流程會先請求 `AI_COACH_VLLM_BASE_URL + /v1/models`，若端點已可用就不重複啟動；若端點不可用，會依 `AI_COACH_VLLM_START_MODE` 開啟獨立 PowerShell 視窗執行 `AI_COACH_VLLM_COMMAND`，再等待 vLLM 就緒後啟動 `python -m ai_coach.service`。

預設設定:

```text
AI_COACH_AUTO_START_VLLM=1
AI_COACH_VLLM_BASE_URL=http://localhost:8002
AI_COACH_VLLM_HOST=0.0.0.0
AI_COACH_VLLM_PORT=8002
AI_COACH_VLLM_START_MODE=wsl
AI_COACH_VLLM_PYTHON=/home/lucian039/miniconda3/envs/vllm_env/bin/python
AI_COACH_VLLM_MAX_MODEL_LEN=16384
AI_COACH_VLLM_GPU_MEMORY_UTILIZATION=0.90
AI_COACH_VLLM_COMMAND=%AI_COACH_VLLM_PYTHON% -m vllm.entrypoints.openai.api_server --model %AI_COACH_MODEL% --host %AI_COACH_VLLM_HOST% --port %AI_COACH_VLLM_PORT% --max-model-len %AI_COACH_VLLM_MAX_MODEL_LEN% --gpu-memory-utilization %AI_COACH_VLLM_GPU_MEMORY_UTILIZATION%
```

若部署環境仍要手動管理 vLLM，請在執行前設定:

```powershell
$env:AI_COACH_AUTO_START_VLLM="0"
.\start.bat
```

若要使用 Windows 原生 vLLM 而非 WSL，請覆寫:

```powershell
$env:AI_COACH_VLLM_START_MODE="windows"
$env:AI_COACH_VLLM_COMMAND="python -m vllm.entrypoints.openai.api_server --model C:\models\gemma-4-awq --host 0.0.0.0 --port 8002"
.\start.bat
```

## 05/07:'調整 RTX 5090 共用 YOLO 的 vLLM context 長度'

vLLM 若讀到模型預設最大序列長度過大，例如 `262144`，會依該長度配置 KV cache，可能在 GPU 可用記憶體不足時啟動失敗。`start.bat` 預設新增下列參數:

```text
AI_COACH_VLLM_MAX_MODEL_LEN=16384
AI_COACH_VLLM_GPU_MEMORY_UTILIZATION=0.90
```

實際啟動參數會包含:

```text
--max-model-len %AI_COACH_VLLM_MAX_MODEL_LEN% --gpu-memory-utilization %AI_COACH_VLLM_GPU_MEMORY_UTILIZATION%
```

RTX 5090 同時跑 YOLO 與 vLLM 時，`16384` 是保守的共用 GPU 設定，可支援較長上下文並保留記憶體給即時影像推論。若未來要處理長對話或大量歷史上下文，再提高 `AI_COACH_VLLM_MAX_MODEL_LEN`，但不可超過 vLLM 啟動錯誤訊息估算的可用上限。

## 05/07:'調整 vLLM 啟動等待時間'

`start.bat` 預設將 `AI_COACH_VLLM_TIMEOUT_SECONDS` 調整為 `300`，讓 RTX 5090 載入 AWQ 模型與初始化 vLLM 時有足夠等待時間。若模型首次載入、CUDA cache 建置或磁碟讀取較慢，可在啟動前覆寫:

```powershell
$env:AI_COACH_VLLM_TIMEOUT_SECONDS="600"
.\start.bat
```

若超過等待時間仍顯示 `vLLM did not become ready within ... seconds.`，代表 `start.bat` 等不到 `http://localhost:8002/v1/models`，需查看獨立 vLLM PowerShell 視窗中的錯誤輸出。
