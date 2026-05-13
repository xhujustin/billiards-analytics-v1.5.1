# AI Coach 整合指南

## 05/13:'新增產生建議產品化輸出'

`產生建議` 按鈕現在使用獨立的 action-oriented suggestion mode，不再共用一般 AI Coach 對話格式。前端呼叫 `/api/coach/suggest` 時需傳入：

```json
{
  "response_mode": "action_suggestion",
  "context": {
    "active_response_mode": "action_suggestion",
    "balls": [],
    "multi_plan": {},
    "ai_coach": null,
    "ui_context": {
      "auth_type": "guest",
      "user_id": null,
      "username": null,
      "accent_color": "emerald"
    }
  },
  "locale": "zh-TW"
}
```

後端會在 `coach.context.v1.request.response_mode` 寫入 `action_suggestion`，AI Coach service 會優先使用 planner、YOLO semantic context 與 shot/event context 轉成單段擊球動作建議。此模式禁止輸出 Markdown、分隔線、標籤、FPS、VRAM、Coordinates、Deviation、座標、原始 JSON、debug 或資料不足說明。

輸出格式必須是純文字 1 到 2 句，只保留擊球建議本身。例如：

```text
切球點過厚。請將瞄準點向薄邊修正約 5mm，使用中桿與中等力道，降低母球失控風險。
```

若偵測到洗袋或母球落袋風險，輸出需直接轉成替代桿法：

```text
此角度容易導致洗袋。建議改用低桿擊打母球中心偏下方位，並降低出桿力道以保留母球控制。
```

同一 AI Coach session 中，前端會把上一個有效的 `active_response_mode` 一起送到 `/api/coach/chat`。若玩家追問仍承接該建議，後端會維持產品化純文字風格；社交與 UI 導覽問題仍依 ConversationRouter 走非分析路由。

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
AI_COACH_MODEL=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit
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

## 05/12:'新增 AI Coach planner-grounded 建議防幻覺規則'

### 功能說明

`POST /api/coach/suggest` 與自動分析類型的 AI Coach 回覆，會優先使用 `coach.context.v1.planner.best_route` 與 `planner.position_play` 產生 deterministic 建議。若 planner 沒有 `best_route`、找不到可對應袋口，或只回傳錯誤狀態，AI Coach 必須回覆保守建議，不得自行指定「右下袋」等未由 planner 提供的袋口。

### 規範用法

- 有 `best_route` 時：只可引用 planner 內的 `target_ball_number`、`route_type`、`route_segments/path_points` 推導出的袋口、`stroke_hint`、`cue_landing_zone`、`position_play.next_ball`。
- 無 `best_route` 時：回覆「目前 planner 沒有可採信的進袋路線」，並建議先確保合法碰球與保守母球控制。
- vLLM 仍可用於一般問答，但「產生建議」按鈕的 zh-TW 回覆會先走 planner-grounded builder，避免模型補出未驗證球路。

### 輸出格式

```text
目標球/袋：打 #1，走 切球 到 左上袋。
力道：中等力道。
桿法：中桿。
母球走位：讓母球留在 planner 標示的母球落點區，勿過度發力。
下一球目的：保留對 #2 的角度。
風險：成功率約 72%。
```

若 planner 不足：

```text
目標球/袋：先以 #1 為合法首碰，但目前 planner 沒有可採信的進袋路線。
力道：小力到中等力道。
桿法：中桿，先確保合法碰球。
母球走位：不要強行指定走位，優先停在檯面中區或避開袋口。
下一球目的：等路線規劃穩定後再選擇進攻袋口。
風險：若直接指定袋口，可能與實際球路不符。
```

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
AI_COACH_VLLM_MAX_MODEL_LEN=2048
AI_COACH_VLLM_GPU_MEMORY_UTILIZATION=0.6
AI_COACH_VLLM_MAX_NUM_SEQS=1
AI_COACH_VLLM_COMMAND=%AI_COACH_VLLM_PYTHON% -m vllm.entrypoints.openai.api_server --model %AI_COACH_MODEL% --host %AI_COACH_VLLM_HOST% --port %AI_COACH_VLLM_PORT% --max-model-len %AI_COACH_VLLM_MAX_MODEL_LEN% --gpu-memory-utilization %AI_COACH_VLLM_GPU_MEMORY_UTILIZATION% --max-num-seqs %AI_COACH_VLLM_MAX_NUM_SEQS%
```

若部署環境仍要手動管理 vLLM，請在執行前設定:

```powershell
$env:AI_COACH_AUTO_START_VLLM="0"
.\start.bat
```

若要使用 Windows 原生 vLLM 而非 WSL，請覆寫:

```powershell
$env:AI_COACH_VLLM_START_MODE="windows"
$env:AI_COACH_VLLM_COMMAND="python -m vllm.entrypoints.openai.api_server --model cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit --host 0.0.0.0 --port 8002 --max-model-len 2048 --gpu-memory-utilization 0.6 --max-num-seqs 1"
.\start.bat
```

## 05/07:'調整 RTX 5090 共用 YOLO 的 vLLM context 長度'

vLLM 若讀到模型預設最大序列長度過大，例如 `262144`，會依該長度配置 KV cache，可能在 GPU 可用記憶體不足時啟動失敗。`start.bat` 預設新增下列參數:

```text
AI_COACH_VLLM_MAX_MODEL_LEN=2048
AI_COACH_VLLM_GPU_MEMORY_UTILIZATION=0.6
AI_COACH_VLLM_MAX_NUM_SEQS=1
```

實際啟動參數會包含:

```text
--max-model-len %AI_COACH_VLLM_MAX_MODEL_LEN% --gpu-memory-utilization %AI_COACH_VLLM_GPU_MEMORY_UTILIZATION% --max-num-seqs %AI_COACH_VLLM_MAX_NUM_SEQS%
```

同時跑 YOLO 與 vLLM 時，`2048` 是較保守的共用 GPU 設定，可降低 Gemma 4 26B A4B AWQ 的 KV cache 顯存壓力並保留記憶體給即時影像推論。若未來要處理長對話或大量歷史上下文，再提高 `AI_COACH_VLLM_MAX_MODEL_LEN`，但不可超過 vLLM 啟動錯誤訊息估算的可用上限。

## 05/07:'調整 vLLM 啟動等待時間'

`start.bat` 預設將 `AI_COACH_VLLM_TIMEOUT_SECONDS` 調整為 `300`，讓 RTX 5090 載入 AWQ 模型與初始化 vLLM 時有足夠等待時間。若模型首次載入、CUDA cache 建置或磁碟讀取較慢，可在啟動前覆寫:

```powershell
$env:AI_COACH_VLLM_TIMEOUT_SECONDS="600"
.\start.bat
```

若超過等待時間仍顯示 `vLLM did not become ready within ... seconds.`，代表 `start.bat` 等不到 `http://localhost:8002/v1/models`，需查看獨立 vLLM PowerShell 視窗中的錯誤輸出。

## 05/12:'新增 AI Coach 對話情境路由與系統警告'

### 功能說明

AI Coach service 會先透過 `ConversationRouter` 判斷使用者意圖，再決定是否讀取技術資料。社交與日常對話只使用 CueVex 專業教練人格模板回覆，不讀 YOLO、planner、shot event，也不呼叫 LLM；即時擊球、狀態查詢與戰術詢問才使用 `coach.context.v1`。

### 規範用法

主後端傳送 `coach.context.v1` 時可包含:

```json
{
  "system_status": {
    "yolo_status": "online",
    "fps": 28.5,
    "roi_status": "normal",
    "balls_outside_roi": [],
    "hsv_avg": [80, 120, 180],
    "lighting_status": "normal",
    "detected_count": 10
  },
  "shot_event": {
    "impact_angle": 18.0,
    "ideal_angle": 12.0,
    "velocity_change": 0.22,
    "pocket_result": "made",
    "potted_balls": [1]
  },
  "ui_context": {
    "auth_type": "guest",
    "user_id": null,
    "username": null,
    "accent_color": "emerald"
  }
}
```

### 輸出格式

- 社交問候: 親切回覆並引導開始訓練。
- 私人問題: 以撞球梗或中二梗化解，例如「我的契約對象只有物理法則」。
- 系統異常: `yolo_status=offline` 直接提示檢查後端連線或重啟服務；`fps < 15` 提醒辨識準確度可能下降。
- 擊球後分析: 固定三段式 `結果判定`、`物理診斷`、`具體建議`。
- UI 強調色: 重要狀態可用 `[emerald]...[/emerald]`，前端可渲染為 `#10B981`。

### 持久化

主後端會把使用者訊息、教練回覆與分析結果寫入既有 `backend/data/recordings.db`，使用 `coach_messages` 與 `coach_analysis_results` 兩張資料表。

## 05/12:'切換 AI Coach vLLM 模型與顯存保守啟動參數'

- **範例**: `AI_COACH_MODEL=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit`
- **規範用法**: `ai_coach\start.bat` 預設使用 `--max-model-len 2048 --gpu-memory-utilization 0.6 --max-num-seqs 1`，在 32GB GPU 約限制 vLLM 使用 19.2GB，預留約 12GB 給 YOLO、OpenCV 影像緩衝與長時間運行碎片。
- **輸出格式**: 腳本會印出 `Model` 與完整 `vLLM command`；可用 `set AI_COACH_DRY_RUN=1 && ai_coach\start.bat` 驗證命令而不啟動服務。
