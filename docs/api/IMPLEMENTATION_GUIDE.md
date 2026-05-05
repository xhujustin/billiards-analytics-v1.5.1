# IMPLEMENTATION_GUIDE.md

## 05/04:'新增 Codex 風格 UI 初版重排'

### 功能說明

- 前端外殼改為 Codex 風格深色介面，字體基準統一為 14px。
- `TopBar` 簡化為系統名稱、FPS、延遲與辨識啟停控制。
- 左側欄依序顯示 `即時影像`、`回放功能`、`練習模式`、`遊玩模式`，`AI Coach` 與上方導覽分開，`設定` 固定放在最下方。
- 即時影像頁改為置中內容欄，影像顯示區控制在主要工作區內，不再滿版撐開。
- 影像下方集中放置畫質控制、全螢幕、YOLO 辨識狀態、系統健康度與 AI Coach 對話卡。
- 清理主要 UI 外殼中的亂碼中文文案，方便後續細改。

### 版面規則

```text
TopBar
Sidebar
  即時影像
  回放功能
  練習模式
  遊玩模式

  AI Coach

  設定
Main Content
  centered content column
  stream video card
  status cards
  AI Coach card
```

### 05/05:'新增 OBS Virtual Camera 相機診斷與切換支援'

- 後端相機列舉改以 OpenCV 實際 probe 為主，不再只依賴 Windows PnP 裝置名稱。
- `/api/camera/list` 回傳每個可讀取來源的 `device_id`、`backend`、`backend_name`、`resolution`、`fps`。
- `/api/camera/switch` 可接收 `{ "device_id": 3, "backend": 700 }`，其中 `700` 為 DirectShow (`DSHOW`)。
- `open_camera()` 會優先使用指定 backend；未指定時依序嘗試 DSHOW、MSMF、ANY。
- OBS 測試流程：
  - 先在 OBS 按下 `Start Virtual Camera`。
  - 後端需使用 Windows Python 環境啟動，WSL 通常無法直接看到 Windows DirectShow 虛擬相機。
  - 到設定頁按重新掃描設備，選擇可讀取的 `Camera N / DSHOW` 或 `Camera N / MSMF`。
- 若設定頁仍找不到 OBS，可用：
  - `.\.venv\Scripts\python.exe backend\test-program\utils\test_camera.py`
  - 找出 OBS 實際落在哪個 device id 與 backend。

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
```

## 05/04:'固定右側黑邊作為 AI Coach 區域'

### 功能說明

- 即時影像頁的串流區改為左右分欄 stage，左側顯示完整串流影像，右側保留固定黑色 AI Coach 區域。
- 右側 Coach 區域寬度使用 `clamp(320px, 22vw, 420px)`，避免不同電腦因瀏覽器寬高不同產生不一致黑邊。
- 串流影像仍使用 `object-fit: contain`，保留完整球桌畫面，不裁切影像。
- `AICoachFloatingChat` 新增 `displayMode="embedded"`，即時影像頁使用嵌入模式；其他頁仍使用浮動模式。
- 左側欄 AI Coach 按鈕仍控制 Coach 開關；在即時影像頁按 `_` 只隱藏右側 Coach 內容，右側黑色區域保留。
- 窄螢幕時 stage 改為單欄排列，Coach 區域移到影像下方，避免擠壓串流畫面。

### 版面規則

```text
stream-stage
  left: stream-video-container, complete stream image
  right: stream-coach-rail, fixed AI Coach area
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
```

## 05/03:'修正 AI Coach 對話切換與視窗控制'

### 功能說明

- 左側欄 AI Coach 選單改由 `Dashboard` 統一管理對話 session，`Sidebar` 只負責顯示列表與觸發操作。
- 點擊左側欄對話紀錄會更新 `activeCoachSessionId`，並同步傳入 `AICoachFloatingChat`。
- `AICoachFloatingChat` 依 `sessionId` 分開保存訊息，切換對話時會顯示該 session 自己的聊天紀錄。
- 聊天室 Header 新增 `_` 最小化與 `X` 關閉控制；`_` 只收起聊天室面板並保留左側對話紀錄，`X` 會關閉並刪除目前對話 session。
- 左側欄保留 `•••` 對話選單，支援重新命名、置頂、取消置頂與刪除對話；刪除目前對話時由 Dashboard 選擇 fallback 對話，刪到空列表時自動建立新對話。
- `•••` 選單改為在對話卡片內下方展開，不再使用絕對定位，避免第一筆或最上方對話的選單被其他區塊遮擋。
- 新建對話會依目前頁面模式與時間自動命名，例如 `即時影像 05/03 23:25`，不再使用 `對話 1`、`對話 2`。
- 聊天室標題列直接顯示目前對話名稱，方便確認正在使用哪一筆 session。

### 前端資料流

```text
Dashboard
  -> coachSessions / activeCoachSessionId
  -> Sidebar 顯示左側對話紀錄
  -> AICoachFloatingChat 依 sessionId 顯示對話內容
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'新增 AICoachChatWindow 多對話元件'

### 功能說明

- 新增獨立 React 元件 `AICoachChatWindow`，使用現有 CSS 架構，不引入 Tailwind。
- 元件內部管理多個對話 session，包含 `sessions`、`activeSessionId`、`openMenuSessionId`、`isMinimized`、`isClosed` 與 `input`。
- Header 顯示目前 mode：`AI Coach - 即時影像模式`，並提供 `建立新對話`、`最小化`、`關閉`。
- History Drawer 顯示所有 sessions，排序規則為置頂優先，再依建立時間與 id 反向排序。
- 每個 session 右側有 `•••` 選單，包含 `置頂/取消置頂` 與 `刪除對話`。
- 選單操作使用 `event.stopPropagation()`，避免觸發切換對話。
- 刪除 active session 時會切換到排序列表中的上一個對話；若刪除後列表為空，會自動建立新對話。
- 點擊元件空白處會關閉 dropdown。
- Chat 區域顯示 active session 的 messages；`handleSend` 目前只清空 input，不接後端 API。
- 依使用者後續調整，Dashboard 保持原本 `AICoachFloatingChat` 聊天室不變。
- 多對話歷史選單改放在左側欄 `AI Coach` 按鈕上方，展開內容只佔用左側欄位，不遮住攝影機主要畫面。

### 檔案

```text
frontend/src/components/AICoachChatWindow.tsx
frontend/src/components/AICoachChatWindow.css
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'新增 AI Coach 思考中點點波浪動畫'

### 功能說明

- 聊天室 pending 訊息改為 `思考中` 加四個獨立點點。
- 點點使用 CSS `@keyframes ai-coach-dot-wave` 做上下波浪動畫。
- 送出按鈕仍固定顯示 `送出`，只用 disabled 狀態變灰不可點擊。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'調整 AI Coach 送出按鈕 loading 狀態'

### 功能說明

- 玩家送出問題後，聊天室內仍顯示 `思考中....`。
- 送出按鈕文字固定為 `送出`，不再切換成 `思考中....`。
- 送出期間按鈕使用 disabled 樣式變灰並不可點擊，避免重複送出。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'新增 AI Coach 聊天自動捲動到底'

### 功能說明

- AI Coach 聊天室在新增訊息、顯示 `思考中....`、收到回覆或顯示錯誤時，會自動捲動到最底部。
- 使用 `messagesEndRef` 搭配 `scrollIntoView({ behavior: "smooth", block: "end" })`。
- 不改變聊天 API 與後端流程。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'新增 AI Coach 思考中訊息'

### 功能說明

- 玩家送出問題後，聊天室會立即追加一則 AI Coach 訊息：`思考中....`。
- 後端回覆成功後，該訊息會被正式回答取代。
- 後端失敗時，`思考中....` 訊息會移除，並顯示錯誤訊息。
- 按「產生建議」時也會先顯示 `思考中....`，完成後替換成建議內容。
- 前端文案已改回乾淨繁體中文，避免亂碼顯示。

### 前端行為

```text
玩家送出問題
玩家訊息加入聊天室
AI Coach 顯示「思考中....」
收到回覆後替換該訊息
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'修正 AI Coach suggestion JSON 與 Orang Unk 一號球 fallback'

### 問題

- Gemma 回覆 `{ "suggestion": "..." }` 時，舊清理邏輯沒有抽取 `suggestion` 欄位，導致前端顯示 JSON 大括號。
- 畫面中的一號球可能被辨識為 `Orang Unk`，舊邏輯會排除 `style=Unknown` 的球，導致最低合法目標誤判為 4 號球。

### 修正

- `_clean_recommendation()` 會抽取 `suggestion` 欄位，只回傳純文字建議。
- `CoachSemanticAdapter` 新增 fallback：
  - `yellow unknown -> 1`
  - `orange unknown -> 1`
- 這是針對九號球場景的保守修正：當黃色一號球因光線或 OBS 畫面被色彩分類成橘色且球型未知時，仍作為疑似一號球處理，避免 AI Coach 改打 4 號球。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile ai_coach\src\ai_coach\service.py backend\core\coach_semantics.py backend\main.py backend\config.py
```

## 05/03:'修正 AI Coach 回覆清理與九號球 1 號合法目標判斷'

### 問題

- Gemma 有時會用 Markdown code fence 或 JSON 格式回覆，例如 ```json，前端會直接顯示不完整包裝文字。
- OBS 靜態圖片測試中，黃色實心球可能被上游 detector 的 `number` 誤標為其他號碼，導致 AI Coach 建議先打 4 號，而九號球實際合法目標應為 1 號。

### 修正

- Coach service 新增 `_clean_recommendation()`：
  - 移除 ``` 與 ```json 包裝。
  - 若模型回傳 JSON，會抽取 `建議`、`recommendation`、`reply` 或 `answer` 欄位。
  - 若回覆以 `建議：` 開頭，會移除前綴，只保留可讀建議文字。
- `CoachSemanticAdapter` 新增九號球顏色與球型對應：
  - yellow solid -> 1
  - blue solid -> 2
  - red solid -> 3
  - purple solid -> 4
  - orange solid -> 5
  - green solid -> 6
  - brown solid -> 7
  - black solid -> 8
  - yellow stripe -> 9
- 語意輸出新增：
  - `raw_detected_number`：保留上游 YOLO 原始號碼。
  - `number_source`：標示使用 `color_style` 或 `detector_number`。

### 範例

```json
{
  "id": "ball-1",
  "number": 1,
  "raw_detected_number": 7,
  "number_source": "color_style",
  "color": "Yellow",
  "style": "solid",
  "is_legal_target": true
}
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile ai_coach\src\ai_coach\service.py backend\core\coach_semantics.py backend\main.py backend\config.py
```

## 05/03:'壓縮 AI Coach Prompt 避免 Gemma 1024 Context 超限'

### 問題

Gemma/vLLM 以 `--max-model-len 1024` 啟動時，原本九號球 System Prompt 加上語意 JSON 會接近上限。實測錯誤如下：

```text
This model's maximum context length is 1024 tokens. However, you requested 140 output tokens and your prompt contains at least 885 input tokens.
```

### 修正

- `AI_COACH_MAX_TOKENS` 預設由 `140` 降為 `80`。
- `AI_COACH_MAX_PROMPT_CHARS` 預設由 `1600` 降為 `900`。
- System Prompt 改為短版九號球規則，保留以下硬性限制：
  - 只允許 `is_legal_target=true` 作為唯一合法目標。
  - 合法目標清線才可建議進攻。
  - 合法目標被擋時必須建議 `Safety Play`，不得改打其他號碼。
- User Prompt 只傳合法目標球、合法目標規則摘要與最佳路徑摘要，不再傳完整候選球列表與完整球桌袋口列表。

### 環境變數

```env
AI_COACH_MAX_TOKENS=80
AI_COACH_MAX_PROMPT_CHARS=900
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile ai_coach\src\ai_coach\service.py backend\core\coach_semantics.py backend\main.py backend\config.py
```

## 05/03:'新增九號球合法目標球語意與 Prompt 規範'

### 功能說明

- `CoachSemanticAdapter` 在輸出 `semantic_context.balls` 前會排除母球與無法辨識號碼的雜訊球。
- 剩餘目標球中，號碼最小者會標記 `"is_legal_target": true`，其餘目標球皆為 `false`。
- `semantic_context.rules` 會記錄九號球規則、合法目標號碼與合法目標 id。
- 若檯面只剩母球，維持 `NO_OBJECT_BALLS` fallback。
- 若有 object ball 但沒有任何可辨識號碼，回傳 `NO_LEGAL_TARGET_BALLS`，避免 AI Coach 猜測合法目標。
- Coach service 新增 `NINE_BALL_COACH_SYSTEM_PROMPT`，明確要求 LLM 只能以 `"is_legal_target": true` 的球作為合法進攻目標；若合法目標路線或入袋線被擋，必須改建議防守策略。

### Semantic Context 範例

```json
{
  "rules": {
    "game": "nine_ball",
    "legal_target_number": 3,
    "legal_target_id": "ball-3",
    "legal_target_policy": "The cue ball must contact the lowest numbered object ball first."
  },
  "balls": [
    {
      "id": "ball-7",
      "number": 7,
      "is_legal_target": false
    },
    {
      "id": "ball-3",
      "number": 3,
      "is_legal_target": true,
      "cue_path_clear": true,
      "nearest_pocket": {
        "name": "bottom_right",
        "path_clear": true
      }
    }
  ]
}
```

### System Prompt 模板

```text
你是撞球九號球 AI Coach。你會收到 Python 後端產生的 semantic_context JSON；後端已完成球心、袋口距離、遮擋與合法目標判斷。

規則必須嚴格遵守：
1. 你必須把 JSON 中 "is_legal_target": true 的球視為唯一合法進攻目標。
2. 九號球規則下，母球必須先碰到檯面上號碼最小的目標球；不得建議玩家先擊打其他號碼的球。
3. 若合法目標球的 cue_path_clear 為 true，且其 nearest_pocket.path_clear 為 true，才可以提供進攻與母球走位建議。
4. 若合法目標球的 cue_path_clear 為 false，或 nearest_pocket.path_clear 為 false，嚴禁建議改打其他號碼的球。此時必須切換為防守策略 Safety Play，建議推顆星解球、防守做球、藏母球或降低風險。
5. 若 semantic_context.valid 為 false，或找不到 "is_legal_target": true 的球，請說明目前缺少合法目標資訊，要求重新辨識檯面，不要自行猜測。
6. 請使用繁體中文，回答限制在 120 字內，內容要具體、可執行。
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile backend\core\coach_semantics.py ai_coach\src\ai_coach\service.py backend\main.py backend\config.py
```

## 05/03:'改為手動觸發 AI Coach 建議'

### 功能說明

- AI Coach 不再於球局穩定後自動生成建議，避免聊天室內容在背景回覆之間跳動。
- 左側 AI Coach 聊天室新增「產生建議」按鈕；只有按下按鈕時才會呼叫後端產生一次建議。
- 自動背景 `analysis.request` 預設停用，主後端不會從影像 loop 主動送 Coach 分析。
- 主後端仍會在 YOLO 影像 loop 中更新 `CoachSemanticAdapter` 穩定快照；因此使用 OBS 靜態圖片作為攝影機來源時，連續偵測幾幀後按「產生建議」可以取得穩定檯面 context。
- 手動聊天 `POST /api/coach/chat` 保持原本行為，玩家輸入問題才送出。
- 前端不再監聽 `metadata.ai_coach.recommendation` 自動更新聊天室內容。
- 「產生建議」按鈕改為右上小型深色按鈕，避免壓縮聊天室訊息區。

### API

```http
POST /api/coach/suggest
Content-Type: application/json

{
  "context": {
    "balls": [],
    "ai_coach": null,
    "multi_plan": null
  }
}
```

成功回應：

```json
{
  "status": "success",
  "reply": "建議先打 7 號球入右下袋，母球控制在中路。",
  "timestamp": "2026-05-03T12:00:00"
}
```

若檯面仍在變動：

```json
{
  "status": "success",
  "reply": "目前檯面狀態變動中，請等球停妥後再產生建議。",
  "timestamp": "2026-05-03T12:00:00"
}
```

### 設定

```env
AI_COACH_AUTO_SUGGESTIONS_ENABLED=false
```

- 預設 `false`。
- 若未來需要恢復背景自動建議，才改為 `true`；目前 UI 預期由「產生建議」按鈕手動觸發。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\core\coach_bridge.py
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'新增 AI Coach 自動建議節流與聊天室去重'

### 功能說明

- 左側 AI Coach 聊天室收到後端 `metadata.ai_coach.recommendation` 時，只維護一則 `自動建議` 訊息。
- 新的自動建議會更新既有自動建議，不再每次 metadata 更新都追加新的對話泡泡。
- 玩家手動輸入仍會保留完整問答紀錄，不受自動建議去重影響。
- 主後端 `_submit_ai_coach_analysis()` 會依語意化檯面簽章與時間間隔節流，避免穩定畫面每一幀都送 `analysis.request`。
- `CoachBridge` 同時間只允許一筆自動分析請求在 WebSocket 中等待回覆，避免 Gemma/vLLM 被連續自動請求塞住。

### 設定

```env
AI_COACH_AUTO_ANALYSIS_INTERVAL_SECONDS=20
```

- 預設 20 秒。
- 同一個檯面簽章在間隔內不會重複送出自動分析。
- 檯面簽章會使用母球、目標球、最近袋口、清線狀態與最佳路徑摘要；球心會以約 12px 網格取整，降低 YOLO 小幅抖動造成的重複建議。

### 前端顯示規則

```text
自動建議：只保留一則，內容有變化時更新。
手動問答：逐則追加並保留到頁面重新整理。
錯誤訊息：顯示在聊天室錯誤區，不清空既有對話。
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\core\coach_bridge.py
npx.cmd tsc --noEmit
```

## 05/03:'新增 AI Coach 幾何語意化 Adapter'

### 功能範圍

- 主後端新增 `CoachSemanticAdapter`，由 Python 先計算球心、最近袋口、入袋距離、母球到目標球距離、遮擋球與檯面穩定狀態。
- Adapter 復用 `StateExtractor.from_runtime_packet()` 與 `PhysicsValidator`，不讓 Gemma 自行推導幾何。
- `analysis.request` 與 `chat.request` 改帶 `semantic_context`，原始 detections 僅作除錯參考。
- Coach service 只接受語意化 context，不再猜測 `x/y/w/h`、`center` 或 YOLO 原生格式。
- `/api/coach/chat` 會判斷問題意圖：檯面局勢問題需穩定快照，通用規則問題可在檯面不穩定時回答。

### Semantic Context 格式

```json
{
  "valid": true,
  "stable": true,
  "coordinate_space": "original_camera_frame",
  "table": {
    "bbox_xywh": [100, 100, 800, 440],
    "bounds": {"left": 100, "top": 100, "right": 900, "bottom": 540},
    "pockets": [{"name": "top_right", "center": [880, 120]}]
  },
  "cue_ball": {
    "id": "cue_ball",
    "center": [200, 480],
    "bbox_semantics": "bbox_xywh_top_left"
  },
  "balls": [
    {
      "id": "ball-1",
      "center": [870, 120],
      "semantic_location": "上方右側，極度靠近top_right，距離 10px",
      "nearest_pocket": {
        "name": "top_right",
        "distance_px": 10,
        "path_clear": true,
        "blocked_by": []
      },
      "cue_path_clear": false,
      "cue_blocked_by": [{"id": "ball-2", "number": 2}]
    }
  ]
}
```

### 錯誤與穩定狀態

- `NO_CUE_BALL`：尚未偵測到母球。
- `NO_OBJECT_BALLS`：尚未偵測到目標球。
- `NO_TABLE_OR_POCKETS`：尚未取得球桌或袋口基準。
- `BALLS_MOVING` / `BALL_COUNT_CHANGED`：檯面狀態仍在變動。
- 檯面依賴問題在不穩定時回覆「目前檯面狀態變動中，請等球停妥後再詢問」。
- 通用規則問題不受穩定快照限制。

### API 狀態

```http
GET /api/coach/state
```

新增欄位：

```json
{
  "stable": true,
  "stable_ball_count": 7,
  "last_snapshot_at": "2026-05-03T12:00:00",
  "last_unstable_reason": null
}
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\core\coach_semantics.py backend\core\coach_bridge.py ai_coach\src\ai_coach\service.py
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'拆分 AI Coach 遠端 WebSocket 服務'

### 功能範圍

- AI Coach 從主後端與 `PoolTracker` 拆出，改由遠端 WebSocket 服務處理穩定判斷、prompt 與 Gemma/vLLM 呼叫。
- 主後端新增 `CoachBridge` 作為 WebSocket client，連線到 `AI_COACH_WS_URL`，非阻塞轉送 YOLO ball context 與手動聊天請求。
- `PoolTracker` 只負責 YOLO/ROI/路徑規劃，不再 import `AICoachManager`，也不直接呼叫 vLLM。
- 前端左側 AI Coach 聊天室維持透過主後端 `/api/coach/chat`，主後端再轉送到遠端 Coach WebSocket。
- Coach 離線時不影響 YOLO、ROI、路徑規劃與即時影像；`/api/coach/state` 會回報未連線。

### 啟動設定

主後端：

```env
AI_COACH_ENABLED=true
AI_COACH_MODE=websocket
AI_COACH_WS_URL=ws://localhost:8010/ws/coach
AI_COACH_SESSION_ID=backend_yolo
AI_COACH_RECONNECT_SECONDS=3
AI_COACH_REQUEST_TIMEOUT_SECONDS=90
AI_COACH_WS_PING_INTERVAL=0
AI_COACH_WS_PING_TIMEOUT=0
```

`AI_COACH_WS_PING_INTERVAL=0` 表示關閉主後端 WebSocket client 的 ping keepalive，避免本機 Gemma/vLLM 長推理時觸發 `keepalive ping timeout`；失敗仍由請求 timeout 與重連機制處理。

遠端 Coach 服務：

```env
AI_COACH_HOST=0.0.0.0
AI_COACH_PORT=8010
AI_COACH_API_URL=http://localhost:8002/v1/chat/completions
AI_COACH_MODEL=/home/lucian039/gemma-4-awq
AI_COACH_VLLM_TIMEOUT_SECONDS=90
AI_COACH_MAX_TOKENS=140
AI_COACH_MAX_PROMPT_CHARS=1600
AI_COACH_SERVER_WS_PING_INTERVAL=0
AI_COACH_SERVER_WS_PING_TIMEOUT=0
```

`AI_COACH_SERVER_WS_PING_INTERVAL=0` 表示關閉 Coach service/Uvicorn WebSocket server 的 ping keepalive，避免 Gemma/vLLM 長推理時由 server 端觸發 `received 1011 keepalive ping timeout`。
Gemma 目前以 `--max-model-len 1024` 啟動時，Coach prompt 必須保持短格式；`AI_COACH_MAX_PROMPT_CHARS` 與 `AI_COACH_MAX_TOKENS` 用來避免 vLLM 回 `400 Bad Request`。

啟動：

```powershell
$env:PYTHONPATH="C:\Users\User\Documents\billiards-analytics-v1.5.1\ai_coach\src"
.\.venv\Scripts\python.exe -m ai_coach.service
```

### WebSocket 訊息格式

主後端送自動分析：

```json
{
  "type": "analysis.request",
  "request_id": "uuid",
  "session_id": "backend_yolo",
  "payload": {
    "balls": [],
    "detections": [],
    "multi_plan": null,
    "frame_id": 123,
    "ts_backend": 1770000000000
  }
}
```

手動提問轉送：

```json
{
  "type": "chat.request",
  "request_id": "uuid",
  "session_id": "backend_yolo",
  "payload": {
    "message": "分析局勢",
    "context": {
      "balls": [],
      "ai_coach": null,
      "multi_plan": null
    }
  }
}
```

Coach 成功回覆：

```json
{
  "type": "coach.result",
  "request_id": "uuid",
  "status": "success",
  "payload": {
    "timestamp": "2026-05-03T12:00:00",
    "semantic_description": "...",
    "recommendation": "...",
    "confidence": 0.8,
    "processing_time": 1.2,
    "error": null
  }
}
```

### API

```http
GET /api/coach/state
```

```json
{
  "status": "success",
  "enabled": true,
  "connected": true,
  "ws_url": "ws://localhost:8010/ws/coach",
  "last_error": null,
  "last_result_at": "2026-05-03T12:00:00"
}
```

`POST /api/coach/chat` 保留原本前端用法，但主後端只轉送 `chat.request` 到 Coach WebSocket，不再直接呼叫 `AI_COACH_API_URL`。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\tracking\tracking_engine.py backend\core\coach_bridge.py ai_coach\src\ai_coach\service.py
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'修正 AI Coach 手動提問 prompt 與 vLLM 錯誤處理'

### 功能範圍

- `POST /api/coach/chat` 不再把完整偵測封包直接送入 vLLM，改為輸出短版球資料、AI Coach 自動分析與最佳路徑摘要。
- prompt 固定要求繁體中文、短句、實戰導向，優先回答下一桿、目標球、母球控制與風險。
- vLLM 回傳 `400` 或其他 HTTP 錯誤時，後端會讀取 upstream response body，並以 `503` 回傳清楚錯誤內容給前端。
- 保留 `/api/planner/*`、`multi_plan` 與 YOLO/ROI 流程，不改變既有練習模式路徑規劃。

### API 用法

```http
POST /api/coach/chat
Content-Type: application/json

{
  "message": "分析局勢",
  "context": {
    "balls": [],
    "ai_coach": null,
    "multi_plan": null
  }
}
```

成功回應：

```json
{
  "status": "success",
  "reply": "先選擇風險較低的目標球，母球控制在桌面中央，避免下一桿失位。",
  "timestamp": "2026-05-03T12:00:00"
}
```

錯誤回應：

```json
{
  "detail": "AI Coach upstream rejected request: HTTP 400: ..."
}
```

### 測試

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\tracking\tracking_engine.py roi_manager.py tests\test_roi_manager.py
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'改為左側欄全域 AI Coach 浮動聊天室'

### 功能範圍

- AI Coach 入口改到左側欄最下方，作為全域按鈕，切換頁面不會消失。
- 聊天室由 `Dashboard` 掛載一次，保留頁面切換期間的對話記錄。
- 聊天室展開時位於左側欄右側，不使用全螢幕 modal，避免遮住攝影機主要畫面。
- 即時影像頁移除固定底部 AI Coach 卡片；練習模式的多球路徑規劃保留。
- 手機或窄螢幕改為底部小面板。

### 前端行為

- 左側欄 `AI Coach` 按鈕負責開啟/關閉聊天室。
- 收到 `metadata.ai_coach.recommendation` 時追加自動建議。
- 手動輸入問題後呼叫 `POST /api/coach/chat`。
- API 失敗只顯示錯誤，不清空既有對話。

### 測試

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'新增即時影像頁 AI Coach 對話框'

### 功能範圍

- 即時影像頁底部由「多球路徑規劃」改為「AI Coach」對話框。
- 對話框會顯示 `metadata.ai_coach.recommendation` 的自動建議，並支援玩家手動輸入問題。
- 練習模式的多球路徑規劃與 `/api/planner/*` 保持不變。
- WebSocket `metadata.update` 新增 `ai_coach` 欄位，來源為 YOLO 分析封包中的 `data_packet["ai_coach"]`。

### API 規格

```http
POST /api/coach/chat
Content-Type: application/json

{
  "message": "我下一桿該怎麼打？",
  "context": {
    "balls": [],
    "ai_coach": null,
    "multi_plan": null
  }
}
```

成功回應：

```json
{
  "status": "success",
  "reply": "建議先選擇風險較低的薄球路線，控制母球停在中袋附近。",
  "timestamp": "2026-05-03T12:00:00"
}
```

錯誤處理：

- 缺少 `message` 回傳 `400`。
- Gemma/vLLM 無法連線、逾時或空回覆回傳 `503`。
- 使用 `AI_COACH_API_URL` 與 `AI_COACH_MODEL` 作為 vLLM OpenAI-compatible endpoint 設定。

### 前端顯示規則

- 無自動建議且沒有對話時顯示「等待球局穩定後產生建議」。
- 收到新的 `metadata.ai_coach.recommendation` 後追加一則 AI Coach 自動建議。
- 玩家送出問題後，先追加玩家訊息，再呼叫 `/api/coach/chat`，成功後追加 AI Coach 回覆。
- API 失敗只顯示錯誤訊息，不清空既有對話。

### 測試

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'新增設定頁 ROI 校正與 ROI API'

### 功能範圍

- 設定頁新增「球桌 ROI 校正」區塊，顯示已校正/未校正、ROI mask 啟用狀態、四點座標摘要。
- 使用 `/stream/monitor` 即時影像作為校正背景，前端點選四個球桌內角後，以原始相機座標儲存。
- 點位與線條視覺規格延續 `roi_manager.py`：大點位、粗線條、四點完成後閉合多邊形。
- 後端 YOLO 流程維持：有 `roi_config.json` 且 `ROI_MASK_ENABLED=true` 時，YOLO 前先套用 `apply_roi_mask()`；沒有 config 時自動回到未遮罩流程。
- 嚴禁在 ROI 流程使用 `warpPerspective` 或 `getPerspectiveTransform`，ROI 座標永遠保留原始畫面座標。

### API 規格

```http
GET /api/roi/state
```

```json
{
  "status": "success",
  "enabled": true,
  "configured": true,
  "config_path": "C:\\Users\\User\\Documents\\billiards-analytics-v1.5.1\\roi_config.json",
  "points": [
    {"x": 120, "y": 80},
    {"x": 920, "y": 84},
    {"x": 910, "y": 520},
    {"x": 132, "y": 516}
  ],
  "coordinate_space": "original_image",
  "point_order": "clicked_order",
  "transform": "none",
  "error": null
}
```

```http
POST /api/roi/config
Content-Type: application/json

{"points":[{"x":120,"y":80},{"x":920,"y":84},{"x":910,"y":520},{"x":132,"y":516}]}
```

- 必須提供剛好四點。
- 儲存成功後會寫入 `roi_config.json`，並將 runtime `ROI_MASK_ENABLED` 設為 `true`。
- 輸出格式同 `/api/roi/state`，`status` 為 `saved`。

```http
POST /api/roi/enabled
Content-Type: application/json

{"enabled": false}
```

- 僅切換 runtime 狀態，不刪除 `roi_config.json`。
- 輸出格式同 `/api/roi/state`，`status` 為 `updated`。

```http
DELETE /api/roi/config
```

- 刪除本機 ROI config，YOLO 自動回到未遮罩流程。
- 輸出格式同 `/api/roi/state`，`configured` 為 `false`。

### 前端用法

1. 進入「設定」頁。
2. 在「球桌 ROI 校正」區塊按「開始 ROI 校正」。
3. 依序點選球桌四個內角。
4. 四點滿足後按「儲存 ROI」。
5. 可用「啟用/停用 ROI mask」暫時切換遮罩，也可用「清除 ROI」刪除設定。

### 測試

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_roi_manager.py -q
npx.cmd tsc --noEmit
```

## 05/03:'新增互動式 ROI 擷取與遮罩生成'

### 功能

- 新增根目錄腳本 `roi_manager.py`。
- `interactive_select_roi(image_path, config_path="roi_config.json")` 使用 OpenCV 視窗讓使用者依序點擊四個球桌內角。
- 點擊過程會即時顯示點位、序號與連線；四點完成後按 `s` 儲存 JSON，按 `q` 取消。
- `apply_roi_mask(frame, config_path="roi_config.json")` 讀取四點座標，使用 `cv2.fillPoly` 建立多邊形遮罩，並用 `cv2.bitwise_and` 將 ROI 外完全塗黑。
- `PoolTracker.process_frame()` 已在 YOLO `model.predict()` 前套用 ROI mask；有 `roi_config.json` 時自動遮掉桌外，沒有設定檔時維持原本未遮罩流程。
- 可選啟用 AI Coach 整合：YOLO 分析完成後會取白球與目標球中心點送入 `AICoachManager`，球穩定後呼叫 Gemma/vLLM，最新結果會附在 `data_packet["ai_coach"]`。
- 已移除舊透視變形輸出 `data/warped_table.jpg` 與舊 ROI pycache 殘留。

### 規範用法

```powershell
.\.venv\Scripts\python.exe roi_manager.py data\sample_frame.jpg --config roi_config.json
```

```env
ROI_MASK_ENABLED=true
ROI_CONFIG_PATH=C:\Users\User\Documents\billiards-analytics-v1.5.1\roi_config.json
AI_COACH_ENABLED=true
AI_COACH_API_URL=http://localhost:8002/v1/chat/completions
AI_COACH_MODEL=/home/lucian039/gemma-4-awq
AI_COACH_SESSION_ID=backend_yolo
```

```python
import cv2
from roi_manager import apply_roi_mask

frame = cv2.imread("data/sample_frame.jpg")
masked = apply_roi_mask(frame, "roi_config.json")
```

### 輸出格式

```json
{
  "points": [
    {"x": 120, "y": 80},
    {"x": 920, "y": 84},
    {"x": 910, "y": 520},
    {"x": 132, "y": 516}
  ],
  "coordinate_space": "original_image",
  "point_order": "clicked_order",
  "transform": "none"
}
```

### 限制

- 嚴禁使用 `cv2.getPerspectiveTransform`、`cv2.warpPerspective` 或任何透視變形流程。
- ROI 必須保留原始畫面座標；輸出影像尺寸與座標系需和輸入 frame 完全一致。
- YOLO 仍使用原始座標偏移與原本 table ROI bbox；ROI mask 僅負責把多邊形外像素塗黑，不改變 frame 尺寸。
- `AI_COACH_ENABLED=false` 時不會初始化 AI Coach，也不會呼叫 Gemma/vLLM；啟用後仍由穩定偵測控制呼叫頻率。
- `roi_config.json` 為本機校正產物，已加入 `.gitignore`。

---
## 實作指南（v1.5）

---

## 前端 SDK 架構

### 模組
- SessionManager
- WebSocketManager
- ConnectionHealthMachine
- CommandDispatcher
- MetadataBuffer

---

## TypeScript 型別（節錄）
（此處直接引用 v1.5 中的 TS 定義，實務上建議獨立為 types.ts）

---

## WebSocket 重連策略
- maxRetries: 5
- exponential backoff + jitter
- close_code=4001 → 不重連

---

## Metadata 高頻處理
- buffer + throttle（1Hz）
- latest-first 策略
- buffer 上限避免記憶體洩漏

---

## Session 管理
- localStorage session_id
- renew window = min(20%, 5min)
- renew fallback → new session

---

## 開發環境
參考 `.env.example`
---

## 05/03:'修正一般練習直球高低桿母球落點'

### 功能摘要
- 修正一般練習近滿球/直球路線中，`stop_zone` 分支固定把母球落點放在撞擊點附近，導致高桿或低桿調整後落點不變的問題。
- 現在直球只有中桿且沒有明顯側旋時才停在撞擊點；高桿會沿子球行進方向延伸母球落點，低桿會沿來球反方向回拉，側旋會加入側向偏移。

### 規範用法
- `POST /api/planner/stroke` 傳入 `tip_y < 0` 或相容 `tip="top"` 時，直球母球落點應往 `object_dir` 方向改變。
- 傳入 `tip_y > 0` 或相容 `tip="draw"` 時，直球母球落點應往 `-incoming` 方向改變。
- `tip_x < 0` 為左塞、`tip_x > 0` 為右塞；測試需覆蓋高桿+左塞、高桿+右塞、低桿+左塞、低桿+右塞四種組合。
- 中桿直球仍維持停球區，不畫成反向回彈。

### 輸出格式
```json
{
  "metadata": {
    "physics": {
      "top_spin_bias": 1.0,
      "draw_spin_bias": 0.0
    }
  },
  "cue_landing_point": [420, 300]
}
```

---

## 05/03:'新增一般練習整顆母球連續拖曳桿法與 100 段力量'

### 功能摘要
- 一般練習浮動桿法面板改為可直接在整顆母球範圍內自由拖曳紅色撞點，不再限制九宮格位置。
- 一般練習擊球力量改為 `1-100` 段滑桿，前端送出 `power_percent`，後端以連續百分比更新路徑規劃物理估算。
- 一般練習桿法面板新增「重置」按鈕，會將撞點回到中心 (`tip_x=0`, `tip_y=0`) 並將力量回到 `50%`。
- 球型練習同步改用同一套連續撞點與 `1-100` 力量控制；預覽路線、母球落點與開始練習送出的 `pattern_layout.stroke` 都會包含連續欄位。
- 後端保留既有 `tip` 與 `power` 桶位作為相容欄位，並將 `tip_x/tip_y/power_percent` 納入 route planner 快取鍵，避免不同撞點或力量百分比共用舊規劃。

### 規範用法
- `POST /api/planner/stroke` 可傳：
  - `tip_x`: `-1.0 至 1.0`，負值代表左塞、正值代表右塞。
  - `tip_y`: `-1.0 至 1.0`，負值代表高桿、正值代表低桿。
  - `tip`: 相容欄位，可傳 `center | top | draw | low | left | right | top_left | top_right | draw_left | draw_right`。
  - `power_percent`: `1-100`
  - `power`: `low | medium | medium_high | high`，可省略；若同時提供 `power_percent`，後端會依百分比重新映射。
- 前端重置按鈕固定送出 `{ "tip": "center", "tip_x": 0, "tip_y": 0, "power": "medium", "power_percent": 50 }`。
- 球型練習重置按鈕同樣套用中心撞點與 `50%` 力量，並立即重算 `cue_after_contact` 與 `cue_landing_point`。
- 百分比映射桶位：
  - `1-25`: `low`
  - `26-50`: `medium`
  - `51-75`: `medium_high`
  - `76-100`: `high`

### 輸出格式
```json
{
  "stroke": {
    "tip": "draw_right",
    "tip_x": 0.8,
    "tip_y": 0.65,
    "power": "medium_high",
    "power_percent": 60
  },
  "multi_plan": {
    "best_route": {
      "stroke_hint": {
        "type": "manual_continuous_tip",
        "power": "medium_high",
        "spin": "continuous_tip"
      },
      "metadata": {
        "physics": {
          "power_scalar": 0.6,
          "side_spin_bias": 0.8,
          "draw_spin_bias": 0.65
        }
      }
    }
  }
}
```

---

## 05/03:'整理後端 config.py 設定分段與註解'

### 功能摘要
- 將 `backend/config.py` 依用途整理為固定章節：環境變數工具、模型權重、YOLO 推論、球桿軸線、顏色分類、球體幾何、球桌 HSV、相機、串流、WebSocket、Metadata、功能旗標與效能診斷。
- 每個設定段落尾端新增用途註解，方便後續調整 `.env` 或排查即時影像、YOLO、投影與串流行為。

### 規範用法
- 設定名稱與預設值維持不變；既有 `.env` 可直接沿用。
- 新增設定時應放入對應章節，並在該章節尾端補充用途說明。
- 若設定會影響即時影像或投影 overlay，應同步更新 `API_REFERENCE.md` 或對應技術文件。

### 輸出格式
```python
SECTION_VALUE = get_env("SECTION_VALUE", "default", str)

# 該章節設定用途說明。
```

---

## 03/22:'新增A+B球色辨識與實心/條紋判定'

### 功能摘要
- 新增 A+B 判定流程：
- A（模板比對）：Hue/LAB/Saturation 統合距離。
- B（K-means）：在彩色像素內分群，取主彩群做二次比對。
- 實心/條紋改為「全區 vs 中心區」規則，降低近袋口與高光誤判。

### 規範用法
- 後端維持既有呼叫：`_detect_ball_color_hsv(roi_img, bbox)`。
- 內部輸出仍回傳 `label/style/hue/white_ratio/black_ratio`，並新增 `template_score` 供除錯。
- `label` 顏色類別：Yellow/Blue/Red/Purple/Orange/Green/Brown/White/Black/Unknown。
- `style` 類別：Solid/Stripe/Cue/Unknown。

### 輸出格式（範例）
```json
{
  "label": "Yellow",
  "style": "Solid",
  "hue": 27.8,
  "white_ratio": 0.11,
  "black_ratio": 0.03,
  "template_score": 0.29
}
```

### 04/27:'修正球型練習投影校正套用與中文問號'
- 問題：
  - 球型練習的 `relative` 座標原本直接乘上 `projection_bounds`，沒有先映射到相機 `table_roi` 再套 homography，導致投影位置與校正後球桌偏差過大。
  - 投影端使用 OpenCV Hershey 字型繪製中文 `母球 / 子球` label，字型不支援中文時會顯示問號。
- 解法：
  - `pattern_layout.coordinate_space="relative"` 時，後端會優先讀取最新 `table_roi` 或 `tracker.table_roi`。
  - 座標流程改為：`relative(0~1)` → `camera table_roi point` → `calibrator.transform_points()` → `projector pixel`。
  - 只有在沒有 homography 或沒有 table_roi 時，才 fallback 到 `projection_bounds`。
  - 投影端 `_draw_setup_balls()` 僅繪製 ASCII label，中文 label 不再投影，避免問號干擾球位。
- 規範用法：
  - 開始球型練習前需先讓相機分析取得 `table_roi`，並完成投影校正矩陣。
  - 前端仍傳 `coordinate_space="relative"`，不需自行套校正。

### 04/27:'新增球型練習幽靈球與母球撞擊線自動對齊'
- 問題：
  - 拖曳子球落袋目標點時，子球進球線會改變，但母球撞擊線仍連到子球中心，看起來沒有自動修正撞擊點。
  - 球型練習預覽與實際投影都沒有幽靈球，使用者無法確認母球應打到的撞擊位置。
- 解法：
  - 前端依 `子球中心 -> 落袋/反彈點` 方向計算幽靈球位置。
  - `cue_to_contact` 改為 `母球中心 -> 幽靈球中心`，拖曳子球進球線路時會同步改變母球撞擊線。
  - `pattern_layout.ghost_balls[]` 會送到後端，後端套用相同 `table_roi + homography` 校正後送入投影 renderer。
  - 投影端沿用既有 `ghost_balls` 繪製流程，以白色虛線圓顯示幽靈球。
- 輸出格式（範例）：
```json
{
  "pattern_layout": {
    "coordinate_space": "relative",
    "route_segments": [
      {"type": "cue_to_contact", "points": [[0.28, 0.5], [0.498, 0.5]]}
    ],
    "ghost_balls": [
      {"x": 0.498, "y": 0.5, "r": 3}
    ]
  }
}
```

### 04/27:'修正球型練習切球母球切線走位'
- 問題：
  - 切球情境中，母球擊中子球後應沿碰撞法線的切線方向移動；原先球型練習用子球行進方向與簡化偏移估算，會讓母球擊後路線看起來不像真實切球。
- 解法：
  - 以前端球型設定中的 `母球中心 -> 幽靈球中心` 作為入射向量。
  - 以 `幽靈球中心 -> 子球中心` 作為碰撞法線。
  - 母球擊後方向改用 `入射向量 - 法線投影` 的切線分量。
  - `高桿` 會加上沿法線的跟進分量；`低桿` 會加上反法線回拉分量；`左塞 / 右塞` 再做小幅側向修正。
- 規範用法：
  - `cue_after_contact` 的起點為幽靈球中心，終點為依切線模型估算的 `cue_landing_point`。
  - 近滿球且切線分量過小時，母球落點會收斂到短停球區，避免畫出不可信的長切線。

### 04/27:'修正球型練習預覽圓形比例與投影幽靈球尺寸'
- 問題：
  - 前端預覽 SVG 使用 `viewBox="0 0 100 100"` 並拉伸到 2:1 球檯，導致幽靈球與母球落點圓圈被壓成橢圓。
  - 前端送出的幽靈球半徑是預覽座標用的小數值，後端直接當投影像素時太小，實際投影幾乎看不到幽靈球。
- 解法：
  - 預覽 SVG 改為 `viewBox="0 0 100 50"`，所有 Y 座標以 `relative_y * 50` 呈現，圓形標記保持正圓。
  - `coordinate_space="relative"` 的 `ghost_balls[]` 在後端固定使用練習球半徑等級，投影端顯示為可辨識的白色幽靈球外框。
- 規範用法：
  - 前端仍可用 `ghost_balls[].r` 控制預覽大小；投影尺寸由後端依相對座標模式轉成實際投影半徑，避免預覽單位誤用為像素。

### 04/27:'限制球型練習座標在庫邊內'
- 問題：
  - 前端球型設定座標原本直接套用整張球檯外框，母球、子球、幽靈球與路線可能落到庫邊或袋口區。
  - 後端投影相對座標也直接映射到整個 `table_roi`，與前端內框概念不一致。
- 解法：
  - 前端將 `pattern_layout` 的 `0~1` 座標定義為「庫邊內有效擊球區」。
  - 預覽渲染時使用 `PLAYFIELD = { left: 0.085, top: 0.12, width: 0.83, height: 0.76 }` 將球、路線、幽靈球、落點映射到內框。
  - 拖曳時會把滑鼠位置反算回 playfield 座標並 clamp 在內框範圍，避免設定點超過庫邊。
  - 後端 `_apply_pattern_practice_projection()` 直接將前端內框座標映射到相機 `table_roi`，再進 homography；不再二次套用 playfield inset，避免投影比預覽更往內縮。
- 規範用法：
  - `pattern_layout.balls[].x/y`、`route_segments[].points`、`ghost_balls[].x/y`、`cue_landing_point` 都代表庫邊內座標，不代表整張桌台外框。

### 04/27:'修正球型投影二次內縮與幽靈球相切距離'
- 問題：
  - 前端已把設定限制在庫邊內，但後端再次套用 playfield inset，造成母球拖到預覽最邊緣時，實際 AR 投影仍離庫邊有一段距離。
  - 幽靈球中心距離使用固定估算，與前端實際球體顯示半徑不一致，導致幽靈球沒有貼著子球外圈。
- 解法：
  - 後端取消二次內縮：`relative 0~1` 直接對應相機 `table_roi` 的有效區，再套 homography。
  - 前端幽靈球中心距離改用真實球桌比例 `BALL_DIAMETER_REL = 0.026`，不再用 UI 顯示像素換算。
  - 後端投影的子球外框與幽靈球外框改用同一個 `projector_ball_radius`，避免兩者半徑不同造成看起來沒有相切。

### 04/27:'修正球型投影邊界使用球半徑內縮'
- 問題：
  - 後端取消固定 playfield inset 後，`relative=0/1` 會把球心映射到 `table_roi` 邊界，導致投影可能落到庫邊外或球檯外。
  - 固定 inset 又會讓投影離庫邊太遠。
- 解法：
  - 後端以 `table_roi` 寬度和 `BALL_DIAMETER_REL=0.026` 推估球半徑。
  - `relative=0/1` 改為映射到 `table_roi` 的半徑內縮區：`x = tx + r + rx * (tw - 2r)`、`y = ty + r + ry * (th - 2r)`。
  - fallback 到 `projection_bounds` 時也套用同樣的球半徑內縮。
- 規範用法：
  - 前端拖曳到最邊代表球心貼近庫邊內側的一顆球半徑位置，不代表球心壓在桌面 ROI 邊界。

### 04/27:'修正球型投影球框半徑過小'
- 問題：
  - 投影端球框半徑使用相機 `table_roi` 寬度直接推估，沒有套 homography 尺度，投到投影機後球框明顯小於真球。
- 解法：
  - 後端以相機 `table_roi` 先推估 camera-space 球半徑。
  - 再用 `calibrator.transform_points()` 轉換中心點、X 半徑點、Y 半徑點到投影座標，取平均距離作為 `projector_ball_radius`。
  - 子球外框與幽靈球外框共用同一個 `projector_ball_radius`。

### 04/27:'修正斜線幽靈球相切與邊界投影內縮'
- 問題：
  - 前端幽靈球中心偏移用 `0~1` 座標直接正規化，斜線時沒有考慮球檯 2:1 顯示比例，造成幽靈球外圈與子球外圈相交。
  - 母球或子球拖到設定區最邊緣時，投影中心只保留一個球半徑，實機上仍可能貼到庫邊或超出有效布面。
- 解法：
  - 前端改用 SVG 實際座標比例計算幽靈球中心：先把 `子球 -> 目標點` 轉成 `viewBox 100x50` 的距離，再沿反方向退一顆球直徑。
  - 後端相對座標轉投影時，邊界內縮由 `1.0x` 球半徑提高為 `1.45x` 球半徑，讓最邊界球位仍保留庫邊安全距離。
- 規範用法：
  - `ghost_balls[].r` 仍代表前端預覽半徑；實際投影半徑由後端 `projector_ball_radius` 計算。
  - `pattern_layout` 的 `0~1` 座標仍表示有效擊球區，但投影端會自動套用球半徑安全內縮，避免設定點落到庫邊。

### 04/27:'調整球型練習預覽左右有效區外擴'
- 問題：
  - 球檯預覽為 2:1 長寬比，若左右與上下都用 `12%` 內縮，左右實際像素間距會比上下大。
- 解法：
  - 前端 `PLAYFIELD` 改為 `{ left: 0.06, top: 0.12, width: 0.88, height: 0.76 }`。
  - CSS 內庫線同步使用左右 `6%`、上下 `12%`，讓畫面上的左右間距與上下間距接近一致。

### 04/27:'新增球型練習 AR 偽影過濾與 CUE 雷射線'
- 問題：
  - 球型練習使用手動固定投影時，YOLO 沒有取得這些投影路線的相機座標，可能把 AR 路線、幽靈球或落點誤判成藍球。
  - 使用者需要的是實體球桿目前指向的雷射線，不是球型設定中的母球到撞點預設線。
- 解法：
  - 後端 `_apply_pattern_practice_projection()` 會同步建立相機座標的 `manual_projected_artifacts`，包含路線線段、幽靈球點、母球落點與受保護的實球中心。
  - `PoolTracker` 在 YOLO 解析球體前，會過濾落在手動 AR 線段或標記附近的圓形偵測框，避免投影被當成球。
  - `PoolTracker` 會在 YOLO 偵測到的 `cue` bbox 內用輕量 Canny 邊緣點與 PCA 估算球桿自身長軸，產生 `cue_axis` 與 `cue_laser_line`。
  - 球桿軸線使用 EMA 時間平滑與短期快取，降低 bbox/邊緣點跳動造成的左右飄。
  - 相機迴圈把 `cue_laser_line` 經 homography 轉成投影座標後寫入 `cue_laser_lines`，renderer 用紅白雷射光束樣式繪製。
- 規範用法：
  - `manual_projected_artifacts` 必須使用相機全圖座標，不是投影座標。
  - 受保護點用於保留真實母球/子球附近偵測，避免把實球本身一起濾掉。
  - 球型練習固定路線仍使用 `route_segments`，不會被當成 CUE 雷射線；雷射線只來自實際偵測到的球桿。
  - `cue_laser_line` 不依賴母球中心；目前沿球桿長軸雙向延伸，後續若能穩定辨識桿頭端，可改為單向雷射。
  - 不再使用 `HoughLinesP` 每幀抓線，避免球桿偵測造成 FPS 明顯下降。

### 04/27:'優化 CUE 雷射線模式 YOLO second-pass'
- 問題：
  - `SECOND_PASS_ENABLED=true` 時，只要 first-pass 偵測數少於 `SECOND_PASS_MIN_OBJECTS=4`，就會以 `SECOND_PASS_IMG_SIZE=960` 再跑一次 YOLO。
  - 球桿雷射線場景通常只需要偵測到 `cue`，若每幀都跑 second-pass，FPS 會掉到約 6~7。
  - 使用 CUDA GPU 時，若 GPU 使用率不高但 CPU 偏高，瓶頸多半在 OpenCV/後處理與第二次推論前後處理。
- 解法：
  - 新增 `SECOND_PASS_SKIP_WHEN_CUE_FOUND=true`，first-pass 已偵測到 `cue` 時跳過 second-pass。
  - 球型練習進入 `cue_laser_only` 模式，只解析 `cue`，跳過彩球 HSV/球號/路線規劃與監控標註繪製。
  - 新增 `CUE_LASER_ONLY_DISABLE_SECOND_PASS=true`，球型練習下完全停用 second-pass，避免沒抓到 cue 時又回到雙推論。
  - 新增 `TRACKER_DRAW_ANNOTATIONS=false`，預設不在 YOLO 監控畫面上畫大量 OpenCV 標註，降低 CPU 負載。
- 規範用法：
  - 若需要強制維持原本高召回雙推論，可在環境變數設定 `SECOND_PASS_SKIP_WHEN_CUE_FOUND=false`。
  - `TRACKER_DRAW_ANNOTATIONS` 預設為 `true`，監控畫面會保留 YOLO 框與文字。
  - 若需要壓測純推論效能，可暫時設定 `TRACKER_DRAW_ANNOTATIONS=false`，但監控畫面將不顯示辨識框。
  - 球型練習的 `cue_laser_only` 模式仍會繪製輕量 YOLO 原始框，不做完整球色分類，避免效能優化造成辨識框消失。

### 04/27:'新增球型練習投影指引線開關與球桿雷射置中'
- 問題：
  - 球桿雷射線若只取球桿邊緣點，可能投影成與實際球桿平行但偏移一段距離。
  - 使用者需要分別控制球桿雷射指引線與母球/子球指引線，並能只保留母球、子球放置點位。
- 解法：
  - 球桿雷射角度與中心線改由 cue bbox 內的球桿像素估算；優先使用木色/白色桿頭遮罩，並從遮罩中挑選長度夠長、寬度夠窄、長寬比高的連通元件，不足時才退回 Canny 邊緣 PCA。
  - 不再信任 YOLO 的 axis-aligned cue bbox 中心；斜長條球桿即使被框成大正方形，也只用框內最像球桿的細長元件估算雷射線。
  - 架桿時手部會貼近球桿，遮罩會排除高飽和膚色區，候選元件評分也偏好低飽和、亮度穩定的細長條帶，降低手指邊緣把雷射中心線拉偏的機率。
  - 若 YOLO 將庫邊或球檯邊緣誤判為 `cue`，後端會依 table ROI、bbox 面積、是否貼近庫邊與長寬比過濾；找不到實際細長球桿元件時，不再用 bbox 本身硬產生雷射線。
  - 新增 `CUE_CONF_THR=0.35`：低於 35% 信心的 `cue` 會被視為庫邊/桌緣等低信心誤判，不畫 CUE 框、不產生雷射線，也不會觸發 second-pass skip。
  - 同一幀若有多個 `cue` 候選，會先全部估軸線並依 YOLO 信心、線段長度、與上一幀中心/角度一致性評分，最後只選一個候選更新時序快取，避免誤框造成雷射線亂跳。
  - 一般練習啟用 route planner 時，不再把 `cue_to_contact` 投影線當成球桿偽影遮罩；否則真實球桿會被 `_is_projected_cue_artifact()` 擋掉，導致球桿雷射線無法使用。該 cue 偽影遮罩只保留給球型練習 `cue_laser_only` 模式。
  - 球桿軸線快取若新中心與上一幀距離過大會立即重置，並降低 cue-laser-only 模式的 EMA 平滑權重，避免雷射線被舊 bbox 位置拖離球桿。
  - 前端新增 `guide_options.cue_laser_enabled` 與 `guide_options.ball_guides_enabled`。
  - 球型練習設定頁保留兩個開關；練習中開關移到「練習統計」面板下方。
  - 一般練習也提供「球桿雷射指引線」啟/閉；練習中切換會呼叫 `POST /api/practice/guides` 即時套用投影，不需要重新開始練習。
  - 投影端預設不畫 `cue_laser_lines`；只有練習狀態 active 且 `cue_laser_enabled=true` 時才會投影球桿雷射線。
  - 舊版 `aim_lines` 與 `trajectories` fallback 預設關閉，避免其他模式或舊路徑資料偶發觸發舊的畫線風格。
  - `ball_guides_enabled=false` 時，前端預覽與投影都隱藏路線、幽靈球、母球落點與落袋目標，只保留母球/子球放置框。
  - `cue_laser_enabled=false` 時，球型練習不啟用 YOLO 球桿雷射模式，並清空投影端 `cue_laser_lines`。

### 04/27:'練習模式與遊玩模式取消 FPS 上限'
- 問題：
  - 後端主相機迴圈固定有 `30 FPS` sleep。
  - `/ws/video` 也固定 `await asyncio.sleep(0.033)`。
  - MJPEG 串流器初始化時同樣帶有 `max_fps=30`，會在練習模式與遊玩模式額外限速。
- 解法：
  - 新增 `_is_high_fps_mode_active()`，只要練習模式或遊玩模式為 active，即視為高 FPS 模式。
  - 主相機迴圈、`/ws/video`、MJPEG monitor/projector 串流都改成在高 FPS 模式下不做 FPS cap。
  - 離開練習/遊玩模式後，恢復一般模式的 `30 FPS` 上限。
- API 補充：
  - `POST /api/practice/guides`
  - Body:
```json
{
  "guide_options": {
    "cue_laser_enabled": true
  }
}
```
  - Response:
```json
{
  "status": "practice_guides_updated",
  "guide_options": {
    "cue_laser_enabled": true
  },
  "pattern_layout": null
}
```

  - `POST /api/practice/pattern-guides`
  - 相容舊球型練習 API，新實作建議使用 `POST /api/practice/guides`。
  - Body:
```json
{
  "guide_options": {
    "cue_laser_enabled": true,
    "ball_guides_enabled": false
  }
}
```
  - Response:
```json
{
  "status": "pattern_guides_updated",
  "guide_options": {
    "cue_laser_enabled": true,
    "ball_guides_enabled": false
  },
  "pattern_layout": {}
}
```
- 輸出格式：
```json
{
  "pattern_layout": {
    "guide_options": {
      "cue_laser_enabled": true,
      "ball_guides_enabled": false
    }
  }
}
```

### 05/03:'穩定球桿雷射指引線快取與平滑'
- 問題：
  - YOLO 某幀漏檢 `cue` 或 cue 候選未通過細長元件檢查時，`cue_laser_line` 會立即變成 `null`，投影端同步清空 `cue_laser_lines`，造成球桿雷射指引線時有時無。
  - cue-laser-only 模式的球桿軸線平滑權重偏低，且新中心稍有跳動就可能重置快取，實機上容易看到雷射線左右抖動。
  - 球桿超過一半進入球檯時，YOLO 的長 `cue` bbox 會把投影綠線、桌邊與藍色桌布一起包進去；若球桿木色遮罩不足，舊流程會退回 Canny 邊緣 PCA，容易把投影線或桌邊當成球桿軸線。
  - 手架桿時手部與木色球桿 Hue 接近，若遮罩把手掌寬面與球桿連成同一區，PCA 會被手掌中心拉偏，造成雷射線平行偏移。
  - 手上墊藍布可排除干擾，但白布/黃布可能被舊遮罩視為球桿候選或高亮桿頭候選，導致長 bbox 內找不到可信球桿窄帶而沒有雷射線。
  - 球桿轉超過 45 度時，YOLO 的 axis-aligned cue bbox 會變成大方框；舊流程在估軸線前先用 bbox 面積過濾，會把斜球桿誤判為桌邊/庫邊而直接沒有雷射線。
  - 大 bbox 內若同時包含手部、布料、桌邊亮線或投影殘影，球桿色遮罩與 PCA 仍可能被非球桿像素拉偏，造成雷射線左右飄。
- 解法：
  - `PoolTracker` 新增 `cue_axis_missing_frames`，當本幀沒有可信 cue 候選時，短暫沿用上一條可信 `cue_axis_cache`。
  - 新增 `_cached_cue_axis_result()`，只在快取仍在允許幀數內、方向與長度有效時回傳軸線；超過保留幀數後停止輸出，避免長時間投影舊位置。
  - `set_cue_laser_only()` 切換模式時會清除球桿軸線快取，避免不同練習模式共用舊線。
  - cue-laser-only 模式若遇到長 bbox，沒有可信木色/桿頭遮罩時不再退回整張 bbox 的 Canny 邊緣，避免投影綠線或桌邊硬生雷射線。
  - 木色遮罩放寬淡木色球桿的 Hue/Saturation 範圍，並排除高飽和投影綠線、紅線與黃字；連通元件被高光切斷時會改用整體球桿色像素做 PCA。
  - 對球桿色像素做 PCA 後，會在垂直球桿方向尋找最密集的窄帶，改用該窄帶中心作為雷射線中心；手掌同色但較寬，不再拉動球桿中心線。
  - 手部貼到球桿時，後端會用較寬鬆的手部/膚色範圍建立「貼手懲罰區」，但不直接從球桿遮罩刪除相近木色；窄帶評分會降低穿過手部寬面的候選，優先保留沿球桿方向連續的窄帶。
  - 將遮罩拆成「木色球桿主體」與「白色/低飽和輔助」；cue-laser-only 的長 bbox 只以木色主體建立軸線，白布與黃布只視為遮擋干擾，不再吃掉雷射線。
  - 窄帶選擇由「像素數最多」改為「沿球桿方向覆蓋最長」，避免手掌寬面面積較大時壓過真正桿身。
  - cue bbox 不再先用面積/貼邊規則丟棄；會先嘗試估出可信球桿軸線，只有估不到軸線時才回到桌邊誤檢過濾。
  - 將上一版過重的快取/EMA 稍微收斂，保留短暫漏檢抗閃爍，但降低錯誤軸線被保留太久造成亂飄的機率。
  - 在 `_estimate_cue_axis_line()` 的球桿色遮罩後，會建立兩條 bbox crop 對角線帶狀 ROI：`左上 -> 右下` 與 `右上 -> 左下`。
  - 分別統計兩條對角線帶內的球桿色像素數；若其中一條明顯較多，後續細長連通元件與 PCA 只使用該對角線帶內的像素。
  - 若兩條對角線像素量接近或有效像素不足，維持原本整體遮罩流程，避免在不明確畫面中硬切錯方向。
  - 手掌貼住球桿且遮罩連成一整塊時，方向不再優先由整體 PCA 決定；後端會先在球桿色遮罩邊緣中找最長、最直、且較少穿過貼手懲罰區的局部直線方向，再用該方向回到球桿色像素中找窄帶中心。
  - 手掌遮住球桿前半段時，若最佳局部直線仍可信，會直接使用該直線附近的支撐像素估算中心線，並優先採用不在貼手區的可見桿身段，再把可見後半段延伸成完整雷射線。
  - 球桿方向穩定時，新增垂直球桿方向的 deadband；小於 `CUE_AXIS_NORMAL_DEADBAND_PX` 的中心線上下抖動會被吸收，降低雷射線平行微飄。
  - 若 YOLO 權重為 segmentation 模型且輸出 `cue` mask，後端會優先使用 segmentation mask 像素直接估 `cue_axis`；只有沒有 mask 或 mask 不可信時，才 fallback 到原本 bbox 內的木色/Hough/PCA 規則。
  - cue segmentation mask 估線時改為 RANSAC/角度掃描優先：YOLO 只提供 cue 大概範圍與 mask 候選點，後端在候選點中找最長、最細、支撐點最多的主軸線；RANSAC 只用來決定方向與支撐範圍，最終中心線會再用 mask 橫截面上下邊界中點重算，避免線貼到球桿上緣或下緣。RANSAC 失敗時才 fallback 到 mask PCA/分段中心線。
  - 若 segmentation mask 因高光、模型邊界或投影反光只吃到球桿上緣/下緣，後端會同時用原影像中的木色/桿身軸線估出中心位置；當 mask 軸線與影像軸線方向一致時，保留 mask 的穩定方向，但沿法線方向平移到影像桿身中心，降低雷射線平行偏在球桿外側的問題。
  - `white-ball` 與 `color-ball` 若有 segmentation mask，也會優先用 mask 輪廓估局部 bbox、中心與半徑；沒有 mask 時才 fallback 到原本局部 Hough 幾何修正。
  - 讀取 segmentation mask 時會優先使用 Ultralytics `masks.xy` polygon 直接 rasterize 到 ROI 座標；只有沒有 polygon 時才 fallback 到 `masks.data` resize，避免 letterbox/resize 後的 data mask 造成球框偏移。
  - 球類 mask 幾何輸出會融合 segmentation 與 YOLO bbox：segmentation 提供球像素與面積半徑，bbox 提供中心錨點、半徑基準與相鄰球約束；同一 crop 內有多個 mask 元件時，會優先選 bbox 中心最近且面積可信的元件。
  - 輸出的 `x/y/w/h` 仍是正方形球框，但中心位移會被 bbox 中心限制，避免上方 cluster 裡相鄰球 mask 或外伸區把框拉走；原始 mask 外接矩形、mask 中心、bbox 中心與半徑資訊會保留在 `geometry_debug` 供診斷。
  - 球 mask 半徑不再完全採用 `minEnclosingCircle`；若 mask 邊緣有細長雜點或局部外伸，會以 mask 面積等效半徑與原 YOLO bbox/table 尺寸上限收斂，避免外框被撐得比實球大很多。
  - 後端診斷標註的球外框不再固定 `radius + 10px`，改由 `BALL_ANNOTATION_RADIUS_PADDING` 控制，預設只外擴 2px 讓圈線貼近球。
  - `white-ball` 與 `color-ball` 在候選去重後會做球心/半徑時序平滑；同一顆球優先以球號匹配，無球號時以中心距離匹配，降低 segmentation polygon 每幀微變造成的子球位置與大小浮動。
- 新增設定：
  - `CUE_SEGMENTATION_MASK_ENABLED=true`：啟用 segmentation mask 優先估球桿軸線；目前 detection-only 權重不會輸出 mask，會自動 fallback。
  - `BALL_ANNOTATION_RADIUS_PADDING=2`：後端診斷畫面球外框額外外擴像素；若要完全貼球可設為 `0`。
  - `BALL_GEOMETRY_TEMPORAL_SMOOTH_ENABLED=true`：啟用球心與半徑短時序平滑。
  - `BALL_GEOMETRY_TEMPORAL_MATCH_DIST=24.0`：同顆球跨幀匹配最大中心距離。
  - `BALL_GEOMETRY_TEMPORAL_ALPHA=0.68`：舊幾何保留權重；值越高越穩，但球移動時跟隨越慢。
  - `BALL_GEOMETRY_TEMPORAL_MAX_AGE=8`：球幾何快取最多保留幀數。
  - `CUE_AXIS_CACHE_MAX_MISSING_FRAMES=3`：短暫漏檢時最多沿用上一條可信球桿軸線 3 幀。
  - `CUE_AXIS_SMOOTH_ALPHA=0.55`：一般模式球桿軸線平滑權重。
  - `CUE_AXIS_LASER_ONLY_SMOOTH_ALPHA=0.62`：球桿雷射模式平滑權重。
  - `CUE_AXIS_RESET_SHIFT_RATIO=0.48`、`CUE_AXIS_RESET_SHIFT_MIN=32.0`、`CUE_AXIS_RESET_SHIFT_MAX=110.0`：控制中心位移多大時視為換桿或誤檢並重置快取。
  - `CUE_AXIS_NORMAL_DEADBAND_PX=3.0`：垂直球桿方向的小幅抖動死區；值越大越穩，但真實上下移動會稍慢跟隨。
- 輸出格式：
  - 偵測穩定或短暫漏檢期間仍維持既有格式：
```json
{
  "cue_axis": [[100, 100], [200, 100], [1.0, 0.0]],
  "cue_laser_line": [[200, 100], [1190, 100], [100, 100], [-890, 100]]
}
```
  - mask 與影像桿身中心合併後不新增 API 欄位，前端與投影端仍讀取同一組 `cue_axis` / `cue_laser_line`；差異只在座標會回到球桿中心線。
  - 超過 `CUE_AXIS_CACHE_MAX_MISSING_FRAMES` 且仍未重新取得可信 cue 時，`cue_axis` 與 `cue_laser_line` 會回到 `null`，避免投影停留在錯誤位置。

### 05/03:'加速球桿雷射軸線收斂'
- 問題：
  - 球桿雷射大致穩定後，固定 EMA 平滑與法線方向 deadband 會讓球桿實際移動時仍以多幀慢慢追上，使用者會感覺雷射線收斂到球桿太慢。
- 解法：
  - `PoolTracker._smooth_cue_axis()` 改為自適應收斂：小於 deadband 的垂直抖動仍被吸收，中心位移超過快速收斂門檻時會自動降低舊軸線保留權重。
  - 法線方向位移在快速收斂狀態下不再固定只保留 42% 的超出量，會依位移量提高響應，讓雷射線在真實移動時更快貼回球桿中心。
  - 快速收斂仍受 `CUE_AXIS_RESET_SHIFT_*` 保護；若位移大到像換桿或誤檢，會重置快取而不是把錯誤線硬拉過去。
- 新增設定：
  - `CUE_AXIS_FAST_CONVERGE_SHIFT_PX=14.0`：中心位移超過此像素門檻後啟用快速收斂；值越低越敏捷，但較容易吃到偵測抖動。
  - `CUE_AXIS_FAST_CONVERGE_ALPHA=0.34`：一般模式快速收斂時的舊軸線保留權重。
  - `CUE_AXIS_LASER_ONLY_FAST_CONVERGE_ALPHA=0.26`：球桿雷射模式快速收斂時的舊軸線保留權重；值越低越快貼上新球桿位置。
- 規範用法：
  - 若現場仍覺得雷射追桿慢，優先降低 `CUE_AXIS_LASER_ONLY_FAST_CONVERGE_ALPHA`，再視情況降低 `CUE_AXIS_FAST_CONVERGE_SHIFT_PX`。
  - 若現場靜止時開始出現抖動，優先提高 `CUE_AXIS_FAST_CONVERGE_SHIFT_PX`，不要直接提高 `CUE_AXIS_LASER_ONLY_SMOOTH_ALPHA`，避免整體收斂再次變慢。
- 輸出格式：
  - API 欄位不變，仍輸出同一組 `cue_axis` 與 `cue_laser_line`。

### 04/27:'修正 WebSocket `socket.send() raised exception.` 斷線刷屏'
- 問題：
  - 瀏覽器或前端先關閉 `/ws/video`、`/ws/analytics` 或 `/ws/control` 後，後端下一次 `send_text()` / `send_bytes()` 可能丟出 `socket.send() raised exception.`。
  - 這類情況通常是正常斷線，但舊程式會記成錯誤，造成 console 持續刷 `WebSocket send error`。
- 解法：
  - `backend/main.py` 新增 `_safe_websocket_send_text()`、`_safe_websocket_send_bytes()` 與 `_is_expected_websocket_close()`。
  - 針對 `socket.send() raised exception`、`websocket is not connected`、`Broken pipe`、`connection reset` 等預期斷線訊息，統一轉成 `WebSocketDisconnect`。
  - `/ws/video` 在影像送出階段若遇到上述斷線，只會正常中止迴圈並記錄 `Client disconnected during send`。
  - `send_ws_envelope()`、`/ws/analytics` 與 heartbeat 任務也改走同一套安全送出流程，避免把正常關閉誤記成後端錯誤。
- 規範用法：
  - 若只是瀏覽器切頁、重整或前端主動重連造成送出失敗，後端應視為正常斷線，不應再列為錯誤。
  - 只有非預期例外才保留 `WebSocket send error` / `WebSocket error` 記錄，方便追真正的傳輸問題。

### 04/27:'改善球型練習球檯設定與二維桿法'
- 功能摘要：
  - 球型練習設定區改為較接近正式球檯的視覺：木紋庫邊、袋口、庫邊點、絨布層與路線光暈。
  - 擊球力量從分段按鈕改為拉桿式 `range` 控制，仍輸出 `low / medium / medium_high / high` 四段值。
  - 母球桿法改為直接拖曳母球撞點紅點，支援九宮格撞點：`中桿 / 高桿 / 低桿 / 左塞 / 右塞 / 高桿+左塞 / 高桿+右塞 / 低桿+左塞 / 低桿+右塞`。
  - 前端會依二維撞點重算 `cue_after_contact` 與 `cue_landing_point`，開始練習後同步投影固定球位、母球路線與落點。
- API 補充：
  - `pattern_layout.stroke.tip` 可接受：
    `center | top | draw | left | right | top_left | top_right | draw_left | draw_right`
  - `pattern_layout.stroke.power` 維持：
    `low | medium | medium_high | high`
- 輸出格式（範例）：
```json
{
  "pattern_layout": {
    "coordinate_space": "relative",
    "stroke": {
      "tip": "top_right",
      "power": "medium_high"
    },
    "cue_landing_point": [0.64, 0.31]
  }
}
```

### 04/25:'新增球型練習虛擬球檯與固定投影'
- 功能摘要：
  - 球型練習選擇 `直線球 / 切球 / 反彈球 / 組合球` 後，前端會顯示虛擬球檯。
  - 使用者可拖曳母球、子球與組合球第二顆球，並設定 `中桿 / 高桿 / 低桿 / 左塞 / 右塞` 與力量。
  - 前端會依球位與桿法產生固定路線：母球撞擊線、子球進袋/反彈/組合線、母球擊後路線與母球落點。
  - 按下開始練習後，`POST /api/practice/start` 會夾帶 `pattern_layout`，後端保存到 `PracticeState.pattern_layout` 並同步到投影機。
  - 球型練習期間相機迴圈不覆蓋手動球型投影，避免 YOLO 即時 AR 資料把固定球位與固定路線清掉。
- API 規範：
  - `POST /api/practice/start`
  - `mode` 為 `pattern` 時可傳 `pattern_layout`。
  - `pattern_layout.balls[]` 使用投影機座標，欄位為 `x / y / r / type / label`。
  - `pattern_layout.route_segments[]` 與 planner 的 `route_segments` 格式一致，投影端優先使用 `route_segments` 畫線。
  - `pattern_layout.cue_landing_point` 為母球擊後預計落點，投影端會用十字落點標記顯示。
- 輸出格式（範例）：
```json
{
  "mode": "pattern",
  "pattern": "cut",
  "player_name": "玩家1",
  "pattern_layout": {
    "balls": [
      {"x": 573, "y": 669, "r": 24, "type": "cue", "label": "母球"},
      {"x": 1066, "y": 466, "r": 24, "type": "object", "label": "子球"}
    ],
    "route_segments": [
      {"type": "cue_to_contact", "points": [[573, 669], [1066, 466]]},
      {"type": "object_to_pocket", "points": [[1066, 466], [1734, 190]]},
      {"type": "cue_after_contact", "points": [[1066, 466], [982, 584]]}
    ],
    "cue_landing_point": [982, 584],
    "stroke": {"tip": "center", "power": "medium"}
  }
}
```

### 04/24:'新增條紋球時序鎖定與不對稱切換規則'

### 功能摘要
- 在 `tracking_engine.py::_smooth_color_info_temporal()` 新增 `style_lock` 機制，對同一顆球做短時窗條紋/實心鎖定。
- `Unknown` 不再覆蓋既有 `Solid/Stripe` 結果，避免 9 號在旋轉或反光時跳成 `unknown`。
- `Stripe -> Solid` 改為不對稱切換，需要更強、且連續更多幀的證據；用來避免 9 號因為白帶暫時不可見而被誤判成 1 號。

### 規範用法
- 後端呼叫流程不變，仍由 `_detect_ball_color_hsv()` 產生 `label/style`，再交給 `_smooth_color_info_temporal()` 平滑。
- 若同位置彩球在歷史上已穩定為 `Stripe`，後續單幀 `Solid` 觀測不會立即覆蓋。
- 僅在連續多幀強證據成立時才允許 `Stripe -> Solid` 切換。
- 黃球若落在 `Yellow + Unknown`，目前會先保守映射為 9 號，避免即時畫面在 `9號 / 1號 / unknown` 之間來回跳動。

### 輸出格式（新增除錯欄位）
```json
{
  "temporal_debug": {
    "label_raw": "Yellow",
    "style_raw": "Solid",
    "label_smoothed": "Yellow",
    "style_smoothed": "Stripe",
    "style_lock": "Stripe",
    "switch_candidate": "Solid",
    "switch_hits": 2,
    "style_signal_strength": 0.82
  }
}
```

### 03/22 補充：黃/橘誤判修正
- 在 `_classify_main_color_ab` 增加暖色交界二次判定（Yellow/Orange/Brown）。
- 依 `final_hue` + `V中位數` 修正：高亮且 hue 較高時優先 Yellow，低亮且 hue 偏低時優先 Brown。
- 用於降低 1 號黃球在暖光下被誤判為 5 號橘球。

## 03/22:'新增顏色校正模式（花式/斯諾克）'

### 功能摘要
- 新增顏色校正設定檔流程：可依 `pool/snooker` 建立、選擇、儲存、套用。
- 前端設定頁新增「顏色校正模式」區塊，可配對「系統顏色 vs 實際顏色」並輸入 HSV 範圍。
- 後端將設定檔寫入 SQLite `color_calibration_profiles`，並可即時套用到顏色分類模板。

### API 規範
- `GET /api/color-calibration/profiles?mode=pool|snooker`：列出設定檔與系統顏色。
- `POST /api/color-calibration/profiles`：新增設定檔，Body: `{ mode, name }`。
- `GET /api/color-calibration/profiles/{profile_id}`：取得設定檔與 mappings。
- `PUT /api/color-calibration/profiles/{profile_id}/mappings`：儲存配色，Body: `{ mappings }`。
- `POST /api/color-calibration/apply`：套用設定檔，Body: `{ profile_id }`。

### mappings 輸入格式
```json
{
  "Yellow": {
    "actual_label": "亮黃",
    "hsv_lower": [20, 80, 80],
    "hsv_upper": [35, 255, 255]
  }
}
```

### 套用輸出格式（範例）
```json
{
  "status": "success",
  "profile_id": 3,
  "mode": "pool",
  "applied": 7
}
```

### 03/22 補充：目前套用設定檔狀態 + 一鍵回復預設模板
- 新增 `GET /api/color-calibration/state`：回傳目前套用中的設定檔名稱、模式、套用時間。
- 新增 `POST /api/color-calibration/reset`：一鍵回復系統預設顏色模板。
- 前端顏色校正模式頁面增加「目前套用中的設定檔」顯示區塊與「一鍵回復預設模板」按鈕。

### 03/22 補充：二層式顏色校正與相機點選取樣
- 設定頁新增「顏色校正」入口，位置在「投影機校正」下方。
- 顏色校正改為二層頁面（獨立 `ColorCalibrationPage`），操作方式與投影機校正一致（進入頁面後調整）。
- 新增相機點選取樣 API：`POST /api/color-calibration/sample-hsv`，可用畫面座標取得 `hsv_center/hsv_lower/hsv_upper`。

### 03/22 補充：相機點選取樣即時回饋
- `POST /api/color-calibration/sample-hsv` 支援 `rx/ry` 比例座標，避免串流尺寸差異造成取樣失敗。
- 回傳新增 `rgb_center`，前端可立即顯示取樣色塊與 HSV，確保點擊後有可見反應。

### 03/22 補充：YOLO ROI 自動逐顆掃描流程
- 顏色校正頁流程改為：選設定檔 → 開始自動掃描 → 逐顆「採用並下一顆」。
- 新增 `GET /api/color-calibration/auto-scan?mode=pool|snooker`：
- 讀取目前 YOLO 球框（`latest_analysis_data.data.balls`），自動裁切 ROI 並回傳每顆球的 `hsv_center/hsv_lower/hsv_upper/rgb_center`。
- 建議操作：確保 YOLO 分析已啟用，畫面內同時有要校正的球，再啟動掃描。

### 03/22 補充：顏色校正單顆引導式精靈與 K-Means 主色擷取
- **單顆引導精靈**：將原本的批次掃描改為依序引導，畫面上每次只提示放入一顆對應顏色的球進行掃描 `Auto Scan`。
- **保留調整空間**：所有掃描結果即時在畫面左下方列表呈現，點擊任一顏色方塊可隨時跳轉回去重新掃描或手動微調 `hsv_lower` 與 `hsv_upper`。
- **未設定預設值**：所有未經掃描或手動跳過的球體，其 `hsv_lower` 與 `hsv_upper` 預設值為 `[0, 0, 0]`。
- **K-Means 擷取主色**：後端 `auto-scan` 邏輯捨棄容易受高光/陰影干擾且有 `0/180` 環邊界問題的簡單算術平均。改將 ROI 內圓形遮罩範圍內的像素保留，轉至標準的 BGR 空間以 K-Means (K=3) 集群分類找出面積最大的「主色 (Dominant Color)」，再轉換回 HSV，大幅提高對真實底色判斷的準確率。

### 03/22 補充：YOLO Second-Pass 備援機制與長寬比容錯
- **Second-Pass Fallback**：當前畫面偵測到的球數少於設定之閾值（例如 `< 4` 顆）時，自動觸發第二次推論，採用更大的 `imgsz` (預設 960) 與更低的 `conf` (預設 0.04) 進行防漏偵測補救，有效應對暗色球或動態模糊情況。
- **長寬比放寬**：將球體的長寬比 (Aspect Ratio) 容忍範圍從 `0.65~1.55` 放寬至 `0.50~1.90`，以適應快速移動時的殘影或不完美的橢圓形狀。
- **環境變數控制**：支援透過 `.env` 進行各項效能與閥值的細部配置：
  - `SECOND_PASS_ENABLED`
  - `SECOND_PASS_MIN_OBJECTS`
  - `SECOND_PASS_CONF_THR`
  - `SECOND_PASS_IOU_THR`
  - `SECOND_PASS_IMG_SIZE`

### 04/23:'新增真正多球路徑規劃（雙規則 + 雙通道）'

### 功能摘要
- 新增 `RoutePlanner` 子模組，將路徑規劃拆分為 `state_extractor / candidate_generator / physics_validator / route_scorer / stroke_recommender`。
- 多球候選支援：`straight / cut / bank / combo`，並輸出 `best_route + routes[] + coach_notes`。
- 同時支援 `practice` 與 `9ball` 規則評分；`9ball` 會優先檢查首碰合法目標球。
- WebSocket `metadata.update` 新增 `multi_plan`，並新增 `planner.update / planner.error` 推送。
- `multi_plan.best_route.route_segments` 會分段輸出全局路線：母球入射、子球路線、母球擊後路線。
- 每條路線新增 `cue_landing_point / cue_landing_zone`，用於顯示預計母球落點。
- 新增 `POST /api/planner/select-route`，可從 Top-N 候選中切換目前 AR/metadata 顯示的進球線路。
- AR 投影端新增 `ar_route_segments`，會將 `route_segments` 轉成投影機座標後分段渲染；新版路線存在時不再混畫舊版 `ar_paths/aim_lines`。

### 規範用法
- 後端追蹤主流程會優先執行多球規劃；無法規劃時自動 fallback 至舊版單路徑預測。
- API：
  - `POST /api/planner/plan`
  - `POST /api/planner/disable`
  - `POST /api/planner/select-route`
  - `GET /api/planner/state`
- 建議參數：
  - `top_n=5`
  - `max_bounces=2`
  - `combo_depth=2`
- 未指定 `target_ball_number` 時，practice 模式預設以桌面最小球號作為第一目標；9ball 模式優先使用目前局面的合法目標球。
- 即時 planner 預設關閉，只在一般練習 `practice_single` 啟動時開啟；主頁、設定、顏色校正、投影校正與球型練習都必須關閉並清空舊路線。
- 前端 Top-N 列表點選 route 時，呼叫 `POST /api/planner/select-route`，後端會把該 route 設為 `best_route` 並更新投影線路。
- AR projector 使用 `ar_route_segments` 作為主要資料源；`ar_paths` 只作為舊版 fallback。

### 輸出格式（範例）
```json
{
  "rule_profile": "9ball",
  "latency_ms": 126.4,
  "best_route": {
    "route_type": "bank",
    "target_ball_number": 1,
    "score": 0.61,
    "difficulty": 39,
    "success_prob": 0.61,
    "path_points": [[620, 410], [738, 392], [970, 240], [1130, 125]],
    "route_segments": [
      { "type": "cue_to_contact", "points": [[620, 410], [738, 392]], "color": "white" },
      { "type": "object_to_rail", "points": [[738, 392], [970, 240]], "color": "green" },
      { "type": "object_to_pocket", "points": [[970, 240], [1130, 125]], "color": "green" },
      { "type": "cue_after_contact", "points": [[738, 392], [760, 548]], "color": "cyan" }
    ],
    "cue_landing_point": [760, 548],
    "cue_landing_zone": { "center": [760, 548], "radius": 34, "label": "預計母球落點" },
    "stroke_hint": {
      "type": "bank_shot",
      "power": "medium",
      "spin": "running_english",
      "rationale": "反彈球建議順塞，提升吃庫後前進穩定度。"
    },
    "risk_flags": []
  },
  "routes": [],
  "coach_notes": [
    "最佳路線：bank，成功率 61%，難度 medium。",
    "建議桿法：bank_shot / running_english / 力道 medium。"
  ]
}
```

### 04/24:'新增多球規劃 P0-1/P0-3 幾何可信化'

### 功能摘要
- `planner.state_extractor` 新增 `table_ball_radius_px`，從桌面現有球半徑中位數推估全桌統一球徑。
- `PlannerBall` 新增：
  - `radius_px_raw`
  - `radius_px`
  - `radius_source`
- 各球半徑改為先做正規化，再交給 Ghost Ball、遮擋檢查與吃庫點計算，避免 bbox 抖動直接把球徑帶歪。
- `physics_validator.is_path_clear()` 升級為 capsule sweep 概念：
  - 以移動球半徑 + 阻擋球半徑 + clearance margin 做掃掠碰撞檢查
  - 不再只用中心線距離判斷是否擋球

### 規範用法
- `PlannerState.table_ball_radius_px` 為 planner 幾何統一尺度，後續候選生成與碰撞檢查都應優先使用它。
- `PlannerBall.radius` 目前對外仍維持可用，但內部實際回傳正規化後的 `radius_px`，以保持既有模組相容。
- 若單顆球偵測半徑異常，系統只允許在全桌球徑附近做小幅修正，不直接信任單幀 bbox。

### 輸出格式（內部型別補充）
```json
{
  "table_ball_radius_px": 14.0,
  "ball": {
    "radius_px_raw": 40.0,
    "radius_px": 15.68,
    "radius_source": "object_median"
  }
}
```

### 04/24:'新增多球規劃 P0-2/P0-4/P0-5 洞口窗口、有效反射區與一致錯誤輸出'

### 功能摘要
- `PlannerState` 新增：
  - `pockets[]`：每個袋口的 `center / mouth_segment / capture_radius / approach_normal`
  - `rail_segments`：四條庫邊的有效反射區段
- `candidate_generator` 的 `straight / cut / bank / combo / kick` 改為優先使用 `pockets[]`
  - 進袋前先檢查是否符合袋口窗口與進袋方向
  - bank / kick 反射點必須落在 `rail_segments` 內
- `route_planner` 補一致錯誤碼：
  - `NO_POTTING_ROUTE`
  - `ONLY_ESCAPE_ROUTE_AVAILABLE`
  - `TARGET_BLOCKED_NO_LEGAL_ROUTE`

### 規範用法
- 直球、切球、組合球不再只對袋口中心連線；需通過 `can_pocket_ball()` 的袋口窗口檢查。
- bank / kick 的反射點若超出有效庫邊區段，直接淘汰，不再只靠 `near_hole` 粗略過濾。
- 當候選路線在排序後全部被幾何條件或難度門檻淘汰時，planner 必須回傳錯誤碼與教練提示，而不是留空白或切回舊預測。
- `kick_escape` 屬於 contact-only 解球候選，只要求母球翻袋後合法碰到目標球，不要求目標球有進袋線；候選必須由鏡像反射幾何產生，不允許用任意庫邊採樣補假路線。

### 輸出格式（內部型別補充）
```json
{
  "pockets": [
    {
      "id": "pocket-0",
      "center": [120, 120],
      "mouth_segment": [[132, 146], [158, 120]],
      "capture_radius": 16.8,
      "approach_normal": [1.0, 1.0]
    }
  ],
  "rail_segments": {
    "top": [[180, 122], [1100, 122]],
    "bottom": [[180, 598], [1100, 598]]
  },
  "error": "NO_POTTING_ROUTE"
}
```

### 04/24 補充：恢復 contact-only 翻袋解球
- 新增 `route_type="kick_escape"`，用於最低號被擋住但仍可透過翻袋合法碰球的場景。
- `kick_escape` 不輸出 `object_to_pocket`，避免被進球窗口檢查誤殺；改輸出 `object_after_contact` 表示合法碰球後子球預估行進方向。
- 評分器會將其標為 `contact_only` 風險，成功率上限較低，只作為解球/安全球建議。

### 04/24:'修正翻袋解球反射幾何與 Top-N 去重'
- bank / kick / kick_escape 反射點檢查統一使用「母球中心可行反射線」，避免用實體庫邊線誤殺合法鏡像反射。
- 移除 `kick_escape` 的 fallback 庫邊採樣；無鏡像解時回傳無進球/無合法路線，不再用錯誤角度硬畫路線。
- `kick_escape` 增加 `route_segments[].type="object_after_contact"`，前端與 AR 可顯示子球接觸後短行進線。
- Top-N 對 `kick_escape` 依 `target_ball_number + rail + kick_bounces` 去重，避免同一顆球同一組庫邊因接觸點微差重複洗版。

### 04/24:'新增 P1-1/P1-2 多庫解球分類與 Top-N 策略分群'
- `max_bounces` 預設提高為 `3`，允許 1/2/3 庫鏡像解球候選，但仍受有效反射區、洞口避讓與 capsule sweep 檢查限制。
- 解球候選新增分類：
  - `route_class="potting_route"`：可進袋路線，包含 `straight / cut / bank / combo / kick`。
  - `route_class="safe_escape"`：合法首碰且預估母球/子球分離較好的安全解球。
  - `route_class="contact_only"`：只保證合法碰到目標球，不宣稱可進袋或安全。
- `metadata.strategy_label` 供前端 Top-N 顯示策略名稱，例如 `直接進攻 / 翻袋進攻 / 顆星進攻 / 安全解球 / 合法碰球`。
- Top-N 選路改為策略分群：
  - 先保留最高分路線。
  - 再依 `route_class + route_type + rail + kick_bounces` 補不同策略。
  - `safe_escape` 最多保留 2 條，`contact_only` 最多保留 1 條，避免解球線洗版。

### 輸出格式（P1 補充）
```json
{
  "route_type": "safe_escape",
  "metadata": {
    "base_route_type": "kick_escape",
    "route_class": "safe_escape",
    "strategy_label": "安全解球",
    "rail": "top-bottom",
    "kick_bounces": 2,
    "safety_score": 0.68
  },
  "route_segments": [
    {"type": "cue_to_contact", "points": [[260, 390], [500, 134], [720, 360]]},
    {"type": "object_after_contact", "points": [[730, 370], [860, 430]]},
    {"type": "cue_after_contact", "points": [[720, 360], [650, 500]]}
  ]
}
```

### 04/24:'修正解球母球落點可達性'
- `kick_escape / safe_escape / contact_only` 新增最後一腿撞擊面對齊檢查：
  - `impact_alignment < 0.22` 的候選會被淘汰，避免母球從不可能的背面/側面接觸目標球。
- 母球碰球後落點不再固定畫長切線：
  - 可用切線時輸出 `metadata.cue_leave_model="tangent"`。
  - 近滿球或切線不可信時改為接觸點外側短停球區，輸出 `metadata.cue_leave_model="stop_zone"`。
- `stop_zone` 會降低 `safety_score`，避免把不能實際走到遠端落點的解球誤判成安全解球。

### 輸出格式（母球落點補充）
```json
{
  "route_type": "contact_only",
  "cue_landing_point": [512, 386],
  "metadata": {
    "cue_leave_model": "stop_zone",
    "impact_alignment": 0.41,
    "safety_score": 0.38
  }
}
```

### 04/25:'新增 P2 輕量速度/力道與庫邊誤差模型'
- 新增 `metadata.physics`，用第一版啟發式動力學替代固定距離畫線：
  - `power_scalar`：估計建議力道，範圍 `0.0 - 1.0`。
  - `object_speed`：子球碰撞後速度比例。
  - `cue_speed_after`：母球碰撞後速度比例，會影響 `cue_after_contact` 與 `cue_landing_point`。
  - `energy_margin`：估計力道是否足夠完成距離、庫數與組合球需求。
  - `rail_error_px`：估計庫邊反彈誤差，庫數越多、力道越大、反彈角越差會越高。
- `route_scorer` 新增 P2 風險旗標：
  - `insufficient_power_margin`
  - `high_rail_error`
- 解球的 `object_after_contact` 不再固定長度，改由 `object_speed` 推估子球接觸後行進距離。
- 母球 LAND 不再固定切線長度，改由 `cue_speed_after` 推估，降低「畫到摸不到的位置」的機率。

### 輸出格式（P2 補充）
```json
{
  "metadata": {
    "physics": {
      "model": "p2_heuristic_v1",
      "power_scalar": 0.58,
      "object_speed": 0.49,
      "cue_speed_after": 0.31,
      "energy_margin": 0.12,
      "rail_error_px": 18.4
    }
  },
  "risk_flags": ["high_rail_error"]
}
```

### 04/25:'補完整 P2 碰撞速度分配與反彈誤差模型'
- `metadata.physics.model` 升級為 `p2_dynamics_v2`，保留舊欄位相容，同時新增更完整的力學欄位。
- 新增碰撞速度分配：
  - `normal_transfer_ratio`：母球速度沿子球行進方向轉移的比例。
  - `tangent_retention_ratio`：母球碰撞後沿切線保留的速度比例。
  - `object_speed`：子球碰撞/組合/吃庫衰減後的速度。
  - `cue_speed_after`：母球碰撞後速度，會影響 `cue_after_contact` 與 `cue_landing_point`。
- 新增組合球與庫邊衰減：
  - `combo_transfer_loss`：組合球傳遞損耗。
  - `rail_decay`：多庫/翻袋後速度衰減。
  - `rail_angle_deg`：估算入射/反射角品質。
  - `spin_shift_px`：順塞/逆塞造成的反彈點偏移估計。
- 新增成功率風險：
  - `object_energy_margin`：子球剩餘能量是否足夠完成路線。
  - `throw_error_px`：切球碰撞 throw 誤差估計。
  - `pocket_speed_risk`：進袋速度過快或過慢風險。
  - `line_tolerance_px`：路線容錯窗口，會隨切角、庫數、組合深度下降。
- `route_scorer` 新增風險旗標：
  - `object_lacks_energy`
  - `collision_throw_error`
  - `poor_pocket_speed`
  - `low_line_tolerance`
- 母球落點模型開始吃桿法：
  - `top_spin` 會讓母球落點偏向子球行進方向。
  - `draw/back_spin` 會讓母球保留回拉傾向。
  - `running/outside_english` 會造成側向偏移，並降低合理順塞 kick/bank 的庫邊誤差。

### 輸出格式（P2 dynamics 補充）
```json
{
  "metadata": {
    "physics": {
      "model": "p2_dynamics_v2",
      "power_scalar": 0.62,
      "object_speed": 0.43,
      "cue_speed_after": 0.27,
      "energy_margin": 0.08,
      "object_energy_margin": -0.04,
      "rail_error_px": 21.6,
      "rail_decay": 0.79,
      "normal_transfer_ratio": 0.72,
      "tangent_retention_ratio": 0.28,
      "combo_transfer_loss": 0.92,
      "throw_error_px": 2.4,
      "pocket_speed_risk": 0.03,
      "line_tolerance_px": 12.8,
      "spin_shift_px": 8.4,
      "side_spin_bias": 1.0,
      "top_spin_bias": 0.0,
      "draw_spin_bias": 0.0,
      "rail_angle_deg": 70.0
    }
  },
  "risk_flags": ["collision_throw_error"]
}
```

### 04/25:'新增投影 Artifact 偵測濾除'
- 問題：投影的 `object_after_contact / cue_after_contact / LAND / ghost_ball / cue_to_contact` 可能被相機拍回，再被 YOLO 誤判為綠球、白球或球桿。
- 解法：一般練習路徑規劃啟用時，tracking 後處理目前只保留 `protected target point`，不再使用 route planner 產生的線段或點位做 YOLO 偽影遮罩。
  - `object_to_pocket / object_after_contact` 的第一點會標記為 protected target point，避免真目標球被誤濾。
- 濾除只在 `route_planner_enabled=True` 且存在上一幀 `best_route` 時啟用；主頁、校正、顏色校正、未啟用規劃時不影響偵測。
- 04/25 修正：protected target point 不再依賴 `target_ball_number` 欄位；任何 `object_to_* / object_after_contact / combo_transfer` 的第一點都視為真球中心保護，避免 1 號球剛好靠近 ghost/投影線時被誤殺。

### 04/25:'新增 P3 Route Hysteresis 防跳線'
- 問題：即時偵測中最低號球可能因投影、遮擋或單幀誤判短暫消失，導致 planner 從 `Ball #1 cut` 跳成 `Ball #2 contact_only`。
- 新增目標球滯後：
  - 若上一幀目標球是較低號球，且本幀只短暫消失，最多 hold `5` 幀。
  - hold 期間沿用上一幀 `best_route`，並輸出 `error="TARGET_TEMPORARILY_MISSING"` 與 `hysteresis_hold=true`。
- 新增路線切換門檻：
  - 同一目標球若舊路線仍在候選內，只有新路線分數高出 `0.12` 以上才切換。
  - 避免 `cut / safe_escape / contact_only` 在相近分數時每幀互跳。

### 輸出格式（P3 補充）
```json
{
  "best_route": {"target_ball_number": 1},
  "error": "TARGET_TEMPORARILY_MISSING",
  "hysteresis_hold": true,
  "coach_notes": [
    "目標球偵測短暫不穩，暫時沿用上一條路線避免畫面跳動。"
  ]
}
```

### 04/25:'新增 P3 State Hash 快取與 9-ball 規則狀態'
- 問題：球框只有數個像素抖動時，planner 仍會每幀重新排序，造成 `cut / contact_only / no route` 之間跳動。
- 新增 `state_hash_reused`：
  - 以母球、彩球中心、球半徑、桌面 ROI、規則與候選參數建立量化球型簽章。
  - 若本幀只是小幅位置微抖，且不是使用者指定 Top-N 切換路線，直接沿用上一筆 `multi_plan`。
  - Top-N 點選 `selected_route_id` 時會略過快取，確保使用者切換線路會立即生效。
- 新增 `rule_state`：
  - `remaining_ball_numbers`：目前桌面可辨識的剩餘球號。
  - `legal_target_ball_number`：本次規劃採用的合法首碰目標。
  - `first_contact_required`：9-ball / practice 下必須優先碰到的球。
- 即時 9-ball 流程不再硬鎖 `1` 號球；若 `1` 號已不在桌上，會改以目前剩餘最小球號作為合法目標。REST 若由比賽狀態提供 `target_ball_number`，仍可覆蓋 planner 預設。

### 輸出格式（P3 state hash 補充）
```json
{
  "state_hash_reused": true,
  "rule_state": {
    "remaining_ball_numbers": [2, 3, 4, 5, 6, 7, 8, 9],
    "legal_target_ball_number": 2,
    "first_contact_required": 2
  }
}
```

### 04/25:'修正直線球母球落點回彈'
- 問題：近滿球/直線球的 `cue_after_contact` 使用 `contact_point - object_dir * 48` 作為停球區，會把母球落點畫回來球方向，看起來像直線球往回彈。
- 解法：
  - `tan_len < 0.18` 時，母球落點改為 `contact_point`。
  - 切線方向不可信、會穿過目標球時，也改為 `contact_point`。
  - `cue_leave_model` 維持 `stop_zone`，但不再畫出反向回彈線。
- 規範用法：
  - 直線/近滿球不可用反方向 offset 表示母球落點。
  - 若沒有可信切線，就讓 `cue_landing_point` 停在 ghost/contact 附近。

### 輸出格式（直線停球補充）
```json
{
  "route_type": "straight",
  "route_segments": [
    {"type": "cue_to_contact", "points": [[700, 300], [500, 300]]},
    {"type": "object_to_pocket", "points": [[480, 300], [120, 300]]},
    {"type": "cue_after_contact", "points": [[500, 300], [500, 300]]}
  ],
  "cue_landing_point": [500, 300],
  "metadata": {
    "cue_leave_model": "stop_zone"
  }
}
```

### 04/25:'新增手動桿法選擇與母球路線重算'
- 功能摘要：
  - 一般練習頁新增浮動母球 icon，點開可選 `中桿 / 高桿 / 低桿 / 左塞 / 右塞` 與力道。
  - 調整桿法後會呼叫後端重新規劃，更新 `cue_after_contact / cue_landing_point / cue_landing_zone`，並同步影像與 AR 投影線路。
  - 功能只在 `practice_single` 一般練習模式啟用；主頁、校正、顏色校正與球型練習不啟用。
- API：
  - `POST /api/planner/stroke`
  - Body 可直接傳 `{ "tip": "top", "power": "high" }`，或包在 `{ "stroke": { ... } }`。
- 可用桿法：
  - `tip`: `center | top | draw | left | right`
  - `power`: `low | medium | medium_high | high`
- 後端規範：
  - `RoutePlanner.plan()` 新增 `stroke_override`，並納入 `state_hash`，避免切換桿法時被 P3 快取誤用舊路線。
  - `CandidateGenerator` 會把手動桿法套到 `stroke_hint` 與 `metadata.physics`。
  - `top` 會增加 `top_spin_bias`，`draw` 會增加 `draw_spin_bias`，`left/right` 會增加側塞偏移並改變母球落點。

### 輸出格式（手動桿法補充）
```json
{
  "stroke": {
    "tip": "top",
    "power": "high"
  },
  "multi_plan": {
    "best_route": {
      "stroke_hint": {
        "type": "manual_top",
        "power": "high",
        "spin": "top_spin",
        "rationale": "使用手動桿法：top / high。母球行進與落點已依此桿法重新估算。"
      },
      "cue_landing_point": [760, 548],
      "metadata": {
        "physics": {
          "top_spin_bias": 1.0,
          "cue_speed_after": 0.42
        }
      }
    }
  }
}
```
