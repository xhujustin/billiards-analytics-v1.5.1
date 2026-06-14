# AI Coach 整合指南

## 05/25:'修正 vLLM 啟動誤判'

`ai_coach\start.bat` 的 vLLM ready check 必須確認 `AI_COACH_VLLM_BASE_URL + /v1/models` 回傳 OpenAI-compatible JSON，且內容包含 `object=list` 與 `data` 欄位。若 `8002` 被 Vite 或其他服務占用並回傳 HTML，即使 HTTP status 是 200，也不得視為 vLLM 已啟動。

範例:

```powershell
Invoke-RestMethod http://127.0.0.1:8002/v1/models
```

規範用法：啟動前若 `AI_COACH_VLLM_START_MODE=wsl`，腳本會先確認 WSL 有可用 Linux distribution，且 `AI_COACH_VLLM_PYTHON` 在 WSL 內可執行。若沒有 WSL distribution，需先安裝 WSL Linux，或改用 `AI_COACH_VLLM_START_MODE=windows` 並提供有效的 `AI_COACH_VLLM_COMMAND`。

輸出格式：若 `/v1/models` 回傳不是 vLLM JSON 且 port 未被占用，腳本會印出 `vLLM is not responding at ... Starting vLLM...` 並嘗試啟動；若 port 已被非 vLLM 服務占用，會印出 `Port ... is already occupied by a non-vLLM service. PID: ...`。若 WSL 未就緒，會印出 `WSL is installed, but no Linux distribution is available or running.` 並停止，避免誤以為 vLLM 已啟動。

## 05/13:'新增 AI Coach 8192 長上下文設定'

AI Coach 預設 vLLM context 升級為 `AI_COACH_VLLM_MAX_MODEL_LEN=8192`，並同步放寬 `AI_COACH_MAX_TOKENS=220` 與 `AI_COACH_MAX_PROMPT_CHARS=4500`。這讓 Gemma 能同時接收近期對話、CueVex 系統操作手冊與較完整球局摘要，避免只升 vLLM context 但仍被 AI Coach prompt 或輸出 token 截斷。

範例啟動參數:

```text
--max-model-len 8192 --gpu-memory-utilization 0.6 --max-num-seqs 1
```

規範用法：RTX 5090 32GB 同時跑 YOLO 與 vLLM 時先維持 `gpu_memory_utilization=0.6` 與 `max_num_seqs=1`。若 `8192` 啟動失敗，先降回 `4096`，再評估是否提高 GPU 使用比例；不得直接升到 `16384` 作為預設。

## 05/13:'修正 AI Coach 啟動 Port 漂移'

根目錄 `start.bat` 會以 `AI_COACH_STRICT_PORT=1` 啟動 `ai_coach\start.bat`。AI Coach WebSocket service 必須使用 `8010`，因為主後端啟動時固定連到 `ws://localhost:8010/ws/coach`。若 `8010` 已被舊服務占用，`ai_coach\start.bat` 會直接報錯並要求關閉舊視窗或停止占用行程，不再自動漂移到 `8011`。

`ai_coach\start.bat` 的 Python 選擇順序為：`ai_coach\.venv\Scripts\python.exe`、專案根目錄 `.venv\Scripts\python.exe`、`py -3`、系統 `python`。若系統沒有 `python` 指令，也能使用根目錄 `.venv` 啟動 AI Coach service，避免 `9009` 退出導致 `8010` 沒有 listen。vLLM 預設檢查位址使用 `http://127.0.0.1:8002`，避免 `localhost` 在部分 Windows/WSL 網路設定下解析或路由不一致。

主後端 `CoachBridge` 的可用狀態以實際 WebSocket 物件是否存在為準。若 TCP 已與 `8010` 建立連線，但舊的 `connected` 旗標尚未同步，不應阻擋 `/api/coach/chat`；`get_state()` 也應回報實際可用連線，避免已連線卻顯示 `AI Coach WebSocket not connected`。

根目錄 `start.bat` 在啟動後端前會先檢查 `http://127.0.0.1:8010/health`，預設最多等待 `AI_COACH_HEALTH_TIMEOUT_SECONDS=900` 秒。因 AI Coach service 可能需要先等待 vLLM 載入大型 Gemma 模型，health check 不可只等 60 秒。若 AI Coach service 未啟動成功，會直接停止並提示檢查 AI Coach Service 視窗，不再讓後端在沒有 `8010` 的狀態下啟動。

若遇到「全部重啟後仍連到舊行為」，先檢查:

```powershell
netstat -ano | Select-String ":8010"
```

確認 `8010` 只有新啟動的 AI Coach Service 使用。若有舊 PID 占用，停止舊行程後重新執行根目錄 `start.bat`。

## 05/13:'修正 Gemma 畫面分析固定格式'

一般 `/api/coach/chat` 的畫面分析已改為自然語氣輸出，不再要求 Gemma 固定列出「目標球/袋、力道、桿法、母球走位、下一球目的、風險」。Gemma 仍會收到 `coach.context.v1`，但 prompt 會把它整理成目前畫面摘要、九號球規則摘要、合法目標與袋口線索，以及路線規劃摘要。

若 `planner.best_route` 或 `planner.position_play` 為空，但 `semantic_context.valid=true`，Gemma 必須改用 YOLO 語意資料判斷，例如合法目標球、母球到目標球是否清線、目標球最近袋口、袋口線是否被其他球阻擋。玩家端輸出不得出現 `planner`、`YOLO`、`資料不足`、座標、FPS、Deviation 或原始 JSON。

`產生建議` 按鈕也必須走同一個原則：先由後端取得目前 YOLO 辨識後的 `semantic_context`，整理為合法目標、袋口清線、阻擋資訊與路線規劃摘要，再交給 Gemma 生成。即使 `planner.best_route` 為空，也不得由後端直接套固定保守文案；Gemma 需根據 YOLO 語意自行判斷指定袋口是否合理，並給出原因、做法與目的。

一般畫面問答不得問一答二。AI Coach system prompt 不得再附加「格式包含：目標球/袋、力道、桿法、母球走位、下一球目的、風險」這類六欄格式。若玩家只問可不可行，只回答可不可行與一個球路原因；若玩家同時問「進了下一球打哪顆」，才補下一顆。Prompt 需提供剩餘球號摘要，例如 `visible_object_numbers` 與 `next_lowest_after_current_if_potted`，讓 Gemma 能依九號球規則判斷進球後的下一個最低號球。

範例輸出：

```text
不建議直接翻下中袋，因為目前合法球更像是往右下袋有清線，硬翻會放大母球失控風險。先用中桿中小力打合法球，讓母球留在檯面中區，下一桿會比較好接。
```

## 05/13:'移除非畫面固定模板回覆'

規則、知識、問候、閒聊、帳號與系統操作問題都屬於非畫面對話。這類問題只提供 CueVex 人格、近期對話與系統操作手冊給 Gemma，不由後端 sanitizer 改寫成固定答案。只要 Gemma/vLLM 有正常回覆，玩家端就使用 Gemma 原文的自然回答。

後端 sanitizer 僅做最低限度清理：移除 `[emerald]...[/emerald]` 等前端標籤、清掉 `planner`、`semantic_context`、`best_route`、`資料不足` 這類內部字樣，不再因為問題是 UI、規則或知識類就套用 `_coach_ui_reply()`、`_coach_rule_reply()` 或 `_coach_billiards_knowledge_reply()`。

系統設定與帳號問題的正確做法是讓 Gemma 熟讀 `SYSTEM_OPERATION_MANUAL` 後自行推測玩家說法，例如玩家說「換介面」「字太小」「存不了設定」「語言在哪」，Gemma 需根據手冊回答最可能路徑；後端不得硬編固定模板。只有 Gemma/WebSocket 例外、回覆空白或服務不可用時，才允許顯示模型暫時無法回應的降級訊息。

## 05/13:'移除非畫面追問固定模板'

非畫面對話與短追問不得由後端硬編內容答案，例如「台灣呢」不得在 sanitizer 內固定回 Ko Pin Yi 名單。前端需持續送出同一 `coach_session_id` 的 `conversation_history`；AI Coach service 會把近期玩家/教練訊息以 `user`、`assistant` 角色交給 Gemma，讓模型自行根據上下文回答。

後端 sanitizer 僅處理內部字樣外洩與最後安全修正，例如移除 `planner`、`semantic_context`、`資料不足`、前端標籤等，不應因為 UI 回覆沒有出現「設定」兩字就改寫成固定模板。若 Gemma 因舊服務或異常仍回「需要更明確情境」類文字，後端只提供中性降級句，不硬編知識答案。

為了相容 WebSocket AI Coach service 未完整支援 `conversation_context` 的情況，後端在送出短追問時會把 `message` 補成「上一個玩家問題 / 上一個教練回答 / 目前玩家追問」的完整語意。這只補上下文，不寫死答案；例如「台灣呢」只會讓模型看到它延續「有名的撞球選手」，實際球員名單仍由 Gemma 產生。

補全訊息不得包含 `YOLO`、`planner`、`資料不足` 等內部觸發詞，避免非畫面追問被誤判成系統狀態或球路分析。AI Coach service 收到 `request.intent=non_analysis` 或 `semantic_context.reason=NON_ANALYSIS_CHAT` 時，也必須強制走 Gemma 非畫面對話；除非 Gemma/WebSocket 失敗或回覆空白，否則不可使用 deterministic fallback。

`產生建議` 同樣不得在後端因檯面 unstable 或路線不足直接輸出固定保守文案。後端仍會把目前 context 送往 Gemma，由 Gemma 生成產品化建議；若 Gemma 回覆空白或包含舊版條列、內部欄位、原始狀態，後端應回報不可用，而不是自行套用固定擊球建議。

action suggestion prompt 不得把 `planner`、`semantic_context`、`best_route` 或 raw JSON 直接交給 Gemma，應先轉成中性的「目前盤面資訊」摘要，例如盤面是否變動、是否有可參考路線、路線型態、風險線索、力道與桿法線索。玩家端若模型未產生可用建議，只顯示繁中可理解的暫時不可用訊息，不顯示英文 exception。

一般聊天中的球路問題，例如「可以翻袋打下中嗎」「這球能不能攻」，也不得因 `stable=false` 或 `semantic_context.valid=false` 直接回固定模板。後端應照樣把目前畫面 context 交給 Gemma；AI Coach service 也不得在 chat request 中直接使用 `_soft_no_table_context_reply()` 或 deterministic planner reply，除非是獨立的 action suggestion/analysis 工作。

追問判斷不得只因為句子短就成立。像「有名的撞球選手」是完整知識問題，必須直接交給 Gemma；只有「台灣呢」「那個怎麼改」「剛剛為什麼」這類明確承接前文的短句，才補上上一題與上一答。補全文字也不得包含「系統」「球路」等會污染舊路由的詞。

自我外貌或玩笑問題，例如「我帥嗎」「我好看嗎」「你覺得我怎樣」，即使很短也不得視為追問。這類問題要優先走 `social_private` 交給 Gemma，用 CueVex 教練人格自然回覆，不沿用上一輪系統設定或球路上下文。

## 05/13:'新增 AI Coach 對話記憶與追問理解'

前端呼叫 `/api/coach/chat` 時需附上 `coach_session_id` 與同一 session 最近對話 `conversation_history`。後端會整理成 `conversation_context` 放入 AI Coach context，包含 `recent_messages`、`last_user_question`、`last_coach_answer` 與 `possible_follow_up`。

`non_visual_chat` 的 Gemma prompt 必須使用近期對話理解短追問。例如玩家先問「有名的撞球選手」，教練回國際選手後，玩家只問「台灣呢」，Gemma 應根據近期對話理解為「台灣有名的撞球選手有哪些」，不要求玩家重問完整句，也不走 YOLO/planner。

若上下文不足，回覆需先照最可能意思回答，再自然補一句：

```text
我先照前面那題接著回答；如果你指的是另一件事，再補我一下。
```

## 05/13:'新增非畫面 Gemma 路由與系統操作手冊'

AI Coach 對話現在以「是否需要當前畫面」作為最高層路由。只有球路、擊球、走位、力道、指定袋口、辨識狀態與 `產生建議` 會讀取 YOLO、planner、shot_event；問候、知識、規則、閒聊、私人問題、身分、帳號與系統操作問題都使用 `non_visual_chat`，不傳辨識資料。

`non_visual_chat` 的 Gemma prompt 需包含 CueVex 系統操作手冊，並要求 Gemma 先推測玩家非正式說法最接近的功能位置。例如：

```text
你說的字太小比較像是外觀設定，請到「設定 > 外觀」調整字體大小。
```

系統操作手冊需涵蓋主選單、設定 > 一般、設定 > 外觀、設定 > 相機、設定 > 球桌校正、顏色校正、設定 > 追蹤、帳號管理、回放記錄、練習模式、遊戲模式與 AI Coach。若玩家用詞模糊，先給最可能路徑，再補一個備選；不可輸出 `planner`、`semantic_context`、`資料不足` 或要求玩家指定目標球/袋口，除非玩家正在問當前球路。

## 05/13:'修正資料不足與 YOLO 狀態措辭'

AI Coach 對玩家輸出時不得直接顯示「資料不足」、`planner`、`best_route`、`position_play`、`semantic_context` 等內部狀態。若球路或戰術問題缺少可採信路線，必須轉成球局導向建議：

```text
這球目前不建議強攻下中袋，翻袋角度容易讓母球失控。先用中小力碰球，讓母球留在檯面中區，保留下一桿選擇。
```

使用者明確詢問 YOLO 或辨識狀態時，也不要輸出「YOLO 辨識穩定」。可改用中性的輔助判斷語氣：

```text
目前畫面有持續辨識到球，可以用來輔助判斷；若要精準路線，請等球完全靜止後再產生建議。
```

## 05/13:'柔化無檯面資料回覆'

當使用者詢問「目前有沒有球可以打進」、「這一桿怎樣」等需要即時檯面或擊球事件的問題，但目前沒有穩定 `semantic_context`、`planner.best_route` 或 `shot_event` 時，AI Coach 不得直接說「資料不足」。固定使用較自然的保守語氣，例如：

```text
我現在還看不到穩定的檯面路線，先不要硬攻。用中桿小力找最低號球的合法碰球，讓母球停在檯面中區，等畫面與路線穩定後再挑進攻袋口。
```

擊球分析缺少 `shot_event` 時，需說「我現在還看不到完整擊球結果」，再給穩定出桿建議，不使用錯誤訊息式用語。

## 05/13:'修正 UI 設定導覽回覆'

UI 導覽類問題必須優先回答「去哪裡設定」，不得改成推薦語氣或輸出強調色標記。外觀顏色、配色、介面主題、強調色等問題固定回覆：

```text
到「設定 > 外觀 > 介面 > 介面主題、強調色」設定。
```

球桌邊框、ROI、四點微調等問題固定回覆：

```text
到「設定 > 球桌校正 > ROI 微調 / 微調邊框」設定。
```

儲存與帳號問題也需先指出設定位置，再補充登入或保存限制；例如訪客模式需到「設定 > 帳號管理」登入後，個人設定與對話紀錄才會寫入 SQLite 帳號資料庫。

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
AI_COACH_VLLM_TIMEOUT_SECONDS=900
AI_COACH_MAX_TOKENS=220
AI_COACH_MAX_PROMPT_CHARS=4500
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
AI_COACH_VLLM_MAX_MODEL_LEN=8192
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
$env:AI_COACH_VLLM_COMMAND="python -m vllm.entrypoints.openai.api_server --model cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit --host 0.0.0.0 --port 8002 --max-model-len 8192 --gpu-memory-utilization 0.6 --max-num-seqs 1"
.\start.bat
```

## 05/07:'調整 RTX 5090 共用 YOLO 的 vLLM context 長度'

vLLM 若讀到模型預設最大序列長度過大，例如 `262144`，會依該長度配置 KV cache，可能在 GPU 可用記憶體不足時啟動失敗。`start.bat` 預設新增下列參數:

```text
AI_COACH_VLLM_MAX_MODEL_LEN=8192
AI_COACH_VLLM_GPU_MEMORY_UTILIZATION=0.6
AI_COACH_VLLM_MAX_NUM_SEQS=1
```

實際啟動參數會包含:

```text
--max-model-len %AI_COACH_VLLM_MAX_MODEL_LEN% --gpu-memory-utilization %AI_COACH_VLLM_GPU_MEMORY_UTILIZATION% --max-num-seqs %AI_COACH_VLLM_MAX_NUM_SEQS%
```

同時跑 YOLO 與 vLLM 時，`8192` 是 RTX 5090 32GB 的長上下文建議設定，可容納近期對話、系統操作手冊與較完整的球局摘要，同時維持 `gpu_memory_utilization=0.6` 與 `max_num_seqs=1` 保留即時影像推論餘裕。若 vLLM 無法啟動，先降回 `4096`，再評估是否提高 `gpu_memory_utilization`。

## 05/07:'調整 vLLM 啟動等待時間'

`start.bat` 預設將 `AI_COACH_VLLM_TIMEOUT_SECONDS` 調整為 `900`，讓 RTX 5090 載入 AWQ 模型與初始化 vLLM 時有足夠等待時間。若模型首次載入、CUDA cache 建置或磁碟讀取較慢，可在啟動前覆寫:

```powershell
$env:AI_COACH_VLLM_TIMEOUT_SECONDS="1200"
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
- **規範用法**: `ai_coach\start.bat` 預設使用 `--max-model-len 8192 --gpu-memory-utilization 0.6 --max-num-seqs 1`，並同步設定 `AI_COACH_MAX_TOKENS=220` 與 `AI_COACH_MAX_PROMPT_CHARS=4500`。若 vLLM 在 YOLO 同跑時無法啟動，先降回 `4096`，再評估是否提高 GPU 使用比例。
- **輸出格式**: 腳本會印出 `Model` 與完整 `vLLM command`；可用 `set AI_COACH_DRY_RUN=1 && ai_coach\start.bat` 驗證命令而不啟動服務。
## 06/11:'新增 AI Coach LLM streaming 回覆與 mobile remote 啟用'

### 功能範圍

AI Coach 對話與產生建議支援 vLLM OpenAI-compatible streaming。前端預設改呼叫主後端 stream endpoint，主後端透過 `CoachBridge.chat_stream()` 轉送到本機 AI Coach service，AI Coach service 再以 `stream=true` 呼叫 vLLM。

### 呼叫鏈路

```text
frontend AICoachFloatingChat
  -> POST /api/coach/chat/stream 或 /api/coach/suggest/stream
  -> backend CoachBridge.chat_stream()
  -> ws://localhost:8010/ws/coach chat.request payload.stream=true
  -> ai_coach service
  -> POST /v1/chat/completions stream=true
```

### SSE 輸出格式

主後端 stream endpoint 使用 `text/event-stream`，每個事件以 `data: {...}` 輸出。

```json
{"type":"delta","delta":"部分文字"}
```

```json
{"type":"replace","reply":"清理後目前應顯示的完整文字"}
```

```json
{"type":"done","status":"success","reply":"清理後完整回覆","timestamp":"2026-06-11T00:00:00"}
```

```json
{"type":"error","message":"錯誤訊息"}
```

前端收到 `delta` 時只在同一則 pending 訊息尾端追加文字；收到 `replace` 時以 `reply` 整段取代同一則 pending 訊息；收到 `done` 時結束 loading 並保存最終 `reply`。`done` 不應再作為未標示的畫面覆寫來源，避免使用者看到文字先變多再突然變少。

主後端在 streaming 期間會累積 raw delta，先轉成可顯示文字再輸出給前端。若清理後文字仍延伸目前畫面文字，輸出 `delta`；若清理或 action suggestion 收斂造成內容需要改寫，輸出 `replace`。完成時仍以 canonical final reply 為準，必要時先送 `replace` 再送 `done`，確保畫面最後狀態、歷史保存與資料庫紀錄一致。

### WebSocket 內部事件

AI Coach service 對主後端 bridge 使用以下事件：

```json
{"type":"coach.delta","request_id":"uuid","status":"streaming","payload":{"delta":"部分文字"}}
```

完成時仍回傳既有 `coach.result`，錯誤時仍回傳 `coach.error`。未帶 `payload.stream=true` 的舊請求維持一次性 `coach.result`。

### 環境變數

```text
AI_COACH_STREAMING_ENABLED=true
```

`ai_coach/start.bat`、`start_ai_coach.bat`、`start_desktop_remote_ai_coach.bat` 與 `start_mobile_remote.bat` 均以 `true` 作為預設或啟動值。mobile remote 啟動 backend 時會明確帶入此變數，讓遠端展示與本機桌面行為一致。

### 相容性規範

- 保留 `POST /api/coach/chat` 與 `POST /api/coach/suggest`，舊 JSON 呼叫不移除。
- 新增 `POST /api/coach/chat/stream` 與 `POST /api/coach/suggest/stream`。
- 背景 `analysis.request` 不使用 token streaming，避免自動分析佔用 bridge 並干擾手動聊天。
- 若 vLLM streaming 失敗，stream endpoint 回傳 `type=error`，前端顯示既有失敗文案。
