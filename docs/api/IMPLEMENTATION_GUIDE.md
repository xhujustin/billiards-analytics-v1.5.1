# IMPLEMENTATION_GUIDE.md

## 06/15:'新增數據頁真實統計功能'

### 功能說明

- 新增 `shot_events` 單桿事件資料模型，保存進球、洗袋、厚薄、距離、難度、走位預估與原始事件摘要。
- 新增產品化數據頁 API：`/api/analytics/overview`、`/api/analytics/offense`、`/api/analytics/trends`。
- 練習與 9-ball 自動偵測的一桿結束時會背景寫入 analytics event；寫入失敗只記錄 log，不中斷即時影像分析。
- 前端數據總覽與進攻數據頁改讀真實 API；無資料時顯示空狀態，不再顯示 hardcoded 假數字。
- 桌面端「分析」頁 `StatsPage` 同步接入真實 analytics API，登入玩家可直接查看今日總覽、進攻分析、母球控制、練習紀錄與趨勢。
- AI 建議第一版採規則式推薦練習摘要，僅根據已聚合統計產生，不直接暴露 raw event 給 LLM。

### 規範用法

- `range` 僅接受 `today`、`week`、`month`、`year`。
- `bucket` 僅接受 `day`、`week`、`month`、`year`。
- `confidence` 回傳：
  - `empty`：沒有任何單桿資料。
  - `partial`：已有部分資料，但走位或難球等欄位不足。
  - `complete`：表現分數公式需要的主要欄位皆可計算。
- `thickness_result` 固定值：`too_thick`、`too_thin`、`on_line`、`unknown`。
- `distance_bucket` 固定值：`near`、`mid`、`far`、`unknown`。

### API 範例

```http
GET /api/analytics/overview?range=today
GET /api/analytics/overview?player=amy&range=today
GET /api/analytics/offense?range=week
GET /api/analytics/trends?bucket=day
```

### 輸出格式

```json
{
  "has_data": true,
  "today_shots": 12,
  "performance_score": 74,
  "pocket_rate": 0.6667,
  "mistake_rate": 0.3333,
  "most_common_mistake": {"type": "too_thin", "label": "打太薄", "count": 3},
  "ai_advice": "打太薄是目前最常見失誤，建議用固定角度球重複校正瞄準線。",
  "recommended_practice": "薄球 / 角度球練習",
  "best_streak": 4,
  "scratch_count": 1,
  "confidence": "partial"
}
```

空資料格式：

```json
{
  "has_data": false,
  "today_shots": 0,
  "performance_score": null,
  "pocket_rate": null,
  "confidence": "empty",
  "data_sources": ["shot_events"]
}
```

### 驗證

```powershell
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m py_compile backend\main.py backend\database\database.py backend\api\replay_api.py backend\tracking\game_manager.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\replay\test_analytics_database.py
cd frontend
npm run build
```

## 06/15:'修正手動 ROI 洞口黑區微調'

### 功能說明

- 洞口中心不再被後端硬性推到 ROI 內側安全距離，避免角袋框離實際黑色洞口太遠。
- `PoolTracker` 新增統一洞口估算入口：先依 `table_roi` 產生六個幾何預估點，再用當前畫面的黑色洞口區域微調中心。
- 手動四點 ROI、舊版 monitor space ROI 縮放、自動偵測 ROI 與 ROI 微調後，都會走同一組洞口估算流程。
- 前端即時影像 overlay 繼續依洞口中心到 `table_roi` 邊界距離縮小顯示半徑，確保黃色洞口框不超出綠色球桌框。

### 規範用法

- 後端 `holes` 表示實際洞口黑區中心或最接近的幾何預估中心，不應為了顯示安全距離而偏離洞口本體。
- 若洞口中心靠近 ROI 邊界，前端負責用 `distance_to_roi_edge - 2` 裁切圓半徑，而不是改寫洞口中心。
- 手動 ROI 有目前 frame 時，必須呼叫黑區微調；沒有 frame 的設定儲存流程可先輸出幾何預估點，後續 frame 會重新修正。

### 輸出格式

```json
{
  "table_roi": [50, 30, 980, 460],
  "holes": [[88, 52], [88, 460], [1000, 52], [1000, 460], [540, 48], [540, 462]]
}
```

## 06/14:'修正洞口框 ROI 內縮顯示'

### 功能說明

- 後端 `PoolTracker` 產生 `holes` 後，會依目前 `table_roi` 將洞口中心限制在球桌 ROI 內側安全距離。
- 自動偵測、手動四點 ROI、舊版 monitor space ROI 縮放與 ROI 微調後，都會套用同一套洞口中心夾限規則。
- 前端即時影像 overlay 依洞口中心到 `table_roi` 邊界的距離動態縮小洞口框半徑，避免黃色洞口框超出綠色球桌框。

### 規範用法

- 後端仍以 `holes: [[x, y], ...]` 輸出六個洞口中心，座標使用與 `table_roi` 相同的原始影像座標系。
- 洞口中心應代表實際洞口位置；若中心靠近 ROI 邊界，前端以 `min(18, distance_to_roi_edge - 2)` 顯示洞口框半徑。
- 半徑小於 4px 時不繪製該洞口框，避免偏邊資料產生越界或無意義的小框。

### 輸出格式

```json
{
  "table_roi": [100, 100, 1000, 500],
  "holes": [[120, 120], [120, 580], [1080, 120], [1080, 580], [600, 120], [600, 580]]
}
```

## 06/14:'新增 AI Coach 串流 replace 事件'

### 功能說明

- AI Coach 串流回覆新增 `replace` SSE 事件，讓後端可以明確要求前端以清理後文字取代目前同一則 pending 訊息。
- 串流期間後端會先累積 vLLM raw delta，轉成可顯示文字後再輸出；若清理後文字仍是前一版的延伸，輸出 `delta`，若清理造成前文需要收斂或重寫，輸出 `replace`。
- 串流結束時，後端仍會產生 canonical final reply，並在 final reply 與畫面目前文字不同時先送 `replace`，再送 `done`。
- 前端收到 `done` 後只完成訊息狀態與保存最終文字，不再把 raw streaming 內容暗中換成另一版，避免使用者看到「字先變多再變少」但沒有事件語意。
- 修正 `/api/coach/suggest/stream` 的擊球建議 prompt 亂碼，讓串流建議與非串流建議使用一致的繁中任務描述。

### 規範用法

- `delta`：只代表在目前可顯示文字尾端追加內容。
- `replace`：代表後端清理、移除內部資訊或收斂 action suggestion 後，需要整段取代目前 pending 訊息。
- `done`：代表串流完成，帶回最終 `reply`、`timestamp` 與狀態；前端可用於保存歷史與結束 loading，但不得再造成未標示的文字跳變。

### 輸出格式

```json
{"type":"delta","delta":"部分文字"}
```

```json
{"type":"replace","reply":"清理後目前應顯示的完整文字"}
```

```json
{"type":"done","status":"success","reply":"清理後完整回覆","timestamp":"2026-06-14T00:00:00"}
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\main.py
cd frontend
npm.cmd run build
```

## 06/14:'修正即時畫面球桌邊框顯示'

### 功能說明

- 修正即時影像頁面前端 metadata overlay 未繪製 `table_roi` 的問題。
- `StreamPage` 現在會將 `metadata.table_roi` 正規化為 SVG rectangle，並在即時畫面上顯示球桌邊框。
- 當 metadata 只有球桌 ROI、暫時沒有球框或路線時，overlay 仍會渲染，避免球桌邊框被 `hasOverlay` 條件擋掉。
- WebSocket `metadata.update` 現在會送出 `table_roi`、`table_roi_raw`、`table_roi_points` 與 `table_roi_status`，讓前端即時畫面可取得球桌框資料。
- WebSocket `metadata.update` 現在也會送出 `holes`，前端會在每個球袋中心畫出圓形洞口框。
- ROI 設定頁的「微調邊框」首次會從自動偵測出的 `table_roi` 開始；儲存四點後再次進入會載入已儲存的 `table_roi_points`。
- ROI 編輯頁底部「重設框選」只清除目前草稿並進入四點重新標註；右上「恢復預設」才回到自動偵測出的 `table_roi`。
- 儲存四點後，後端會立即同步 `table_roi_points` 到 runtime metadata，讓監控畫面直接顯示新框選結果。
- 即時畫面顯示球桌框時會優先使用 `table_roi_points` 四點多邊形，沒有四點時才退回 `table_roi` 矩形。
- ROI 設定頁送出的四點使用預覽圖座標；後端保存前會依目前相機原始解析度轉換，回傳給設定頁時再轉回 1280x720 監控座標，避免監控畫面重複縮放造成位移。

### 規範用法

- 後端 metadata 必須提供 `table_roi: [x, y, w, h]`，座標需對應 `img_w` / `img_h` 的原始影像座標。
- 若提供 `table_roi_points: [[x, y], ...]`，前端會以四點多邊形作為主畫面球桌框。
- `POST /api/table/roi-polygon` 應同時帶入 `image_width` / `image_height`，後端會用這組尺寸把點位轉成相機原始座標保存。
- 後端 metadata 可提供 `holes: [[x, y], ...]`，座標需使用與 `table_roi` 相同的影像座標系。
- 前端 overlay 使用 `viewBox="0 0 {img_w} {img_h}"` 對齊影像，球桌邊框以 `stream-table-roi` 樣式固定線寬顯示。
- 洞口框以 `stream-pocket-roi` 樣式固定線寬顯示；若 `holes` 缺失或點位格式錯誤，該洞口不繪製。
- 若 `table_roi` 缺失、長度不足或寬高小於等於 0，前端不繪製球桌邊框。

### 輸出格式

```json
{
  "img_w": 1280,
  "img_h": 720,
  "table_roi": [92, 84, 1096, 552],
  "holes": [[112, 104], [112, 584], [1168, 104], [1168, 584], [640, 104], [640, 584]]
}
```

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 06/12:'修正 AI Coach 袋口名稱對照'

### 功能說明

- 修正 AI Coach 語意層的袋口名稱順序，讓 `tracking_engine._estimate_default_holes()` 產生的洞口座標可正確對應畫面位置。
- runtime 洞口順序為：左上、左下、右上、右下、上中、下中。
- `coach.context.v1.semantic_context.table.pockets[].name` 現在會依原始相機畫面座標正確輸出 `top_left`、`bottom_left`、`top_right`、`bottom_right`、`top_middle`、`bottom_middle`。
- 修正後，合法目標球的 `nearest_pocket.name`、`pocket_options[].name` 與 AI Coach fallback 建議不會再把左下袋誤說成上中袋。

### 範例

```json
{
  "table_roi": [100, 100, 1080, 520],
  "holes": [[120, 120], [120, 600], [1160, 120], [1160, 600], [640, 110], [640, 610]],
  "pockets": [
    {"name": "top_left", "center": [120, 120]},
    {"name": "bottom_left", "center": [120, 600]},
    {"name": "top_middle", "center": [640, 110]},
    {"name": "bottom_middle", "center": [640, 610]}
  ]
}
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py -q
.\.venv\Scripts\python.exe -m py_compile backend\core\coach_semantics.py
```

## 06/06:'新增登入頁測試登入按鈕'

### 功能說明

- 電腦端登入頁右上角新增「測試登入」按鈕，用於快速驗證帳號登入流程。
- 測試登入會走真實前端 auth client 與後端 `/api/auth/login`，成功後建立一般使用者 session，不建立訪客或假 session。
- 預設測試帳號為 `CueVexTest001`，密碼為 `CueVexTest001`。
- 若預設測試帳號不存在，前端會先呼叫 `/api/auth/register` 建立帳號，再呼叫 `/api/auth/login` 完成登入。
- 若預設測試帳號已存在但密碼不同，前端會建立 `CueVexTest{timestamp}` 格式的備援測試帳號，再完成登入。
- 後端 `AccountStore.login()` 會在成功與失敗登入時寫入 `login_history`，因此測試登入成功後可在帳號管理登入紀錄中看到紀錄。

### 規範用法

- 測試登入按鈕只顯示於 `login` 模式，不顯示於歡迎、註冊或忘記密碼畫面。
- 點擊測試登入後，登入頁切到密碼步驟並停用其他登入操作，避免重複送出。
- 測試登入仍使用 `getDeviceLabel()` 帶入裝置資訊，登入紀錄的 `device` 欄位與一般登入一致。
- 測試登入完成後會寫入 `qtrack_recent_login_accounts`，讓測試帳號出現在登入過的帳號清單。
- 若後端帳號 API 未啟用，畫面顯示既有 `帳號服務尚未啟用，請重啟後端後再試` 錯誤文案。

### 輸出格式

```tsx
<button
  className="auth-test-login-button"
  type="button"
  onClick={handleTestLogin}
  disabled={isLoginLoading || isRegisterLoading || isForgotLoading}
>
  {isTestLoginLoading ? t('auth.testLoginLoading') : t('auth.testLogin')}
</button>
```

登入紀錄格式沿用帳號管理頁既有資料：

```json
{
  "created_at": "2026-06-06T10:00:00+00:00",
  "status": "success",
  "device": "Chrome / Win32"
}
```

### 驗證

```powershell
cd frontend
npm.cmd run build
```

- 開啟登入頁，確認右上角顯示「測試登入」。
- 點擊「測試登入」，確認可登入 Dashboard，且 session type 為一般使用者。
- 進入帳號管理頁，確認登入紀錄中出現本次測試登入紀錄。
- 後端未啟動時點擊「測試登入」，確認顯示帳號服務不可用提示。

## 06/06:'新增訪客個人化功能限制'

### 功能說明

- 電腦端訪客進入頂部「分析」或「歷史 / 回放紀錄」時，不載入個人統計、玩家列表、回放入口、回放列表或播放器內容。
- 訪客限制頁保留主框架、頂部列與側欄，只在主內容區顯示登入提示，不會直接跳離 Dashboard。
- 帳號管理頁維持既有訪客登入提示，仍需登入後才可管理個人資料與安全設定。
- AI Coach 訪客可使用一次性問答與建議，但不讀取、不顯示、不建立、不保存歷史對話。

### 規範用法

- 「分析」限制只指個人統計分析頁，不影響右上角即時 YOLO 啟停按鈕。
- 「歷史紀錄」限制指 `replay` 回放紀錄頁與其子頁。
- 訪客限制畫面需包含：
  - 標題：`需要登入`
  - 描述：`目前是訪客身分，登入後即可使用此頁功能`
  - 身分列：`目前身分 = 訪客`
  - 動作列：`登入後使用 = 登入`
- 登入按鈕呼叫既有 `onAuthAction`，清除 guest session 並進入登入頁。
- 訪客 AI Coach 使用固定一次性 session，不讀寫 `ai-coach-sessions-v1`、`ai-coach-active-session-v1`、`ai-coach-chat-messages-v1`。
- 登入使用者仍沿用原本歷史對話清單、訊息保存、重新命名、置頂與刪除行為。

### 輸出格式

```tsx
{renderPanelRow(
  t('guestAccess.loginToUse'),
  t('guestAccess.loginToUseDesc'),
  <button className="settings-button primary" type="button" onClick={onAuthAction}>
    {t('common.login')}
  </button>,
)}
```

### 驗證

```powershell
cd frontend
npm.cmd run build
```

- 以訪客登入後點頂部「分析」，確認顯示登入提示，且不呼叫 `/api/stats/summary`。
- 以訪客登入後點頂部或側欄「歷史 / 回放紀錄」，確認顯示登入提示，且不載入回放入口或列表。
- 在訪客限制畫面點「登入」，確認直接進入登入頁。
- 訪客開啟 AI Coach 可送出一次性問題；重新整理後對話不保留。
- 使用一般帳號登入後，確認分析、歷史與 AI Coach 歷史對話仍照常可用。

## 05/28:'新增準度訓練隨機題目與監控投影模式'

### 功能說明

- 練習首頁的「準度訓練」改為獨立 `accuracy` 流程，不再直接共用一般練習的即時 planner 入口。
- 準度訓練使用前端系統隨機題目產生器，產生母球、子球、目標洞口、幽靈球、入袋輔助線與母球停點。
- 題目座標沿用球型練習 `pattern_layout.coordinate_space="relative"`，後端使用既有固定投影流程轉成投影機座標。
- 練習中可切換「進袋線 / 母球停點」顯示重點，並可按「下一題」更新題目，不重置成功/失敗統計。
- 第一版不呼叫 Gemma；前端保留 `generateAccuracyDrill()` 題目產生封裝，後續可替換為 Gemma 或題庫來源。

### API 與輸出格式

- `POST /api/practice/start`
  - `mode="accuracy"` 時會接受 `pattern_layout`，並以固定投影模式啟動。
  - `pattern_layout` 欄位與球型練習一致：

```json
{
  "coordinate_space": "relative",
  "balls": [
    { "x": 0.24, "y": 0.52, "r": 24, "type": "cue", "label": "母球" },
    { "x": 0.58, "y": 0.42, "r": 24, "type": "object", "label": "子球" }
  ],
  "route_segments": [
    { "type": "cue_to_contact", "points": [[0.24, 0.52], [0.53, 0.43]] },
    { "type": "object_to_pocket", "points": [[0.58, 0.42], [0.94, 0.12]] },
    { "type": "cue_after_contact", "points": [[0.53, 0.43], [0.62, 0.58]] }
  ],
  "ghost_balls": [{ "x": 0.53, "y": 0.43, "r": 1.14 }],
  "cue_landing_point": [0.62, 0.58],
  "guide_options": {
    "cue_laser_enabled": true,
    "ball_guides_enabled": true
  }
}
```

- `POST /api/practice/layout`
  - 更新目前固定投影練習的 `pattern_layout`，用於準度訓練「下一題」。
  - 不重置 `attempts / successes / success_rate`。
  - 僅允許 `practice_pattern` 與 `practice_accuracy` 使用。
- 錄影 `game_type="practice_accuracy"` 會存入 `practice/accuracy` 分類。

### 規範用法

- 準度訓練進入監控畫面後，MJPEG 串流仍使用 `/burnin/camera1.mjpg`。
- `ball_guides_enabled=false` 時，投影與監控固定題目只保留擺球點，不顯示路線、幽靈球與母球停點。
- 一般練習維持 `practice_single` 與即時 route planner；球型練習維持原本拖曳球位與固定投影。

### 驗證

```powershell
cd frontend
npm.cmd run build
```

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\tracking\game_manager.py backend\streaming\recording_manager.py backend\database\database.py
```

## 05/28:'限制 AI Coach 不可於遊玩模式開啟'

### 功能說明

- 前端 AI Coach 側邊入口改為只在非 `game` 遊玩頁顯示；遊玩模式視為正式對局情境，不提供 AI Coach，避免形成作弊體驗。
- 開啟 AI Coach 時不再因練習頁保護流程切回 `stream` 監控頁，避免使用者在非監控頁操作時被強制導回監控畫面。
- 若使用者進入遊玩頁，既有保護流程會自動關閉 AI Coach 選單與對話窗。

### 規範用法

- 允許：`currentPage !== 'game'` 時可建立、切換、開啟 AI Coach 對話。
- 禁止：`game` 遊玩模式不傳入 AI Coach 點擊 handler。

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 05/26:'調整首頁監控導覽與影像頁標題'

### 功能說明

- 頂部導覽原本的「首頁」改名為「監控」，仍指向既有 `stream` 監控頁。
- 監控頁移除影像區上方的頁面標題與副標題，讓即時影像卡片直接作為主要內容起點。
- 不變更串流來源、YOLO 狀態卡、系統健康度與 AI Coach 嵌入區邏輯。

### 規範用法

- 使用者點擊頂部導覽「監控」會進入原本的即時影像監控頁。
- 監控頁首屏不再顯示「即時影像」標題與說明文字；狀態資訊仍保留在下方卡片。

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 05/12:'修正 YOLO 停擺時 AI Coach 仍產生建議'

### 問題

- 當後端偵測到 `YOLO future stalled after ... disabling analysis until backend restart` 後，`latest_analysis_data["data"].status` 會變成 `yolo_stalled`。
- 舊版 `/api/coach/suggest` 與 `/api/coach/chat` 會呼叫 `ensure_live_analysis_for_coach()` 重新把 `system_state["is_analyzing"]` 設為 `true`，並可能使用前端送來的舊 `multi_plan` 產生建議。

### 規範用法

- YOLO 進入 `yolo_stalled` 後，後端會保留 `system_state["yolo_stalled"]=true`，直到重啟後端。
- `/api/control/toggle` 與 `/api/control/analysis` 在 `yolo_stalled` 狀態下不再重新啟動辨識，回傳：

```json
{
  "status": "yolo_stalled",
  "is_analyzing": false,
  "message": "YOLO inference stalled; restart backend before enabling analysis again."
}
```

- `/api/coach/suggest` 在 `yolo_stalled` 狀態下回傳暫停訊息，不呼叫 AI Coach WebSocket，也不產生球路建議。
- `/api/coach/chat` 在 `yolo_stalled` 狀態下回傳暫停訊息，避免依停擺畫面回答。
- `coach.context.v1` 的 `multi_plan` 來源以後端最新 runtime/planner 為準；前端提供的 `context.multi_plan` 不可覆蓋後端狀態，避免使用過期路線。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\core\coach_payload_builder.py
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py
```

## 05/11:'調整投影機校正為彈窗流程'

### 功能說明

- 設定頁「投影」區塊的「投影機校正」不再切換到獨立頁面，改為與 ROI 微調一致的背景虛化彈窗。
- 彈窗外層點擊背景會直接關閉，關閉時會沿用 `AutoCalibrationPage` unmount 清理流程，把投影機模式切回 `idle`。
- 投影機校正視窗內的工作區與影像預覽改為同列對齊：左側為標記選擇與方向控制，右側為即時影像預覽。
- 底部操作列改為「重置位置 / 關閉 / 儲存並退出」；「儲存並退出」會先執行 ArUco 偵測，再呼叫 `/api/calibration/confirm` 儲存校正結果，成功後退出彈窗。

### 操作流程

1. 開啟設定頁的「球桌校正」分頁。
2. 在「投影」區塊按下「投影機校正」。
3. 在彈窗內選擇角點並使用方向鍵或方向按鈕微調 ArUco 標記位置。
4. 按「儲存並退出」完成偵測與校正儲存；若只要離開，按「關閉」或點擊模糊背景。

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 05/11:'調整投影機校正為設定子頁'

### 功能說明

- 設定頁「投影」區塊的「投影機校正」改為與 ROI 微調一致的設定內容區子頁，不再使用背景虛化彈窗。
- 投影機校正子頁保留 `AutoCalibrationPage` 原本的 API 流程；子頁關閉或儲存退出時仍會 unmount，並把投影機模式切回 `idle`。
- 第一階段排版改為上方即時影像預覽、下方控制區；控制區左下以「目前控制」顯示目前標記與座標並提供標記選擇，右下為無外框卡片的「移動控制」。
- 移動控制按鍵採鍵盤方向鍵排列並對齊：上排 `↑`，下排 `← ↓ →`，不再顯示中間圓點。
- 影像預覽寬度與設定子頁一致為 `960px`，維持 `aspect-ratio: 16 / 9`、黑底、`object-fit: contain`。
- 底部操作列維持「重置位置 / 關閉 / 儲存並退出」。

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 05/11:'新增 ROI 四點微調箭頭控制'

### 功能說明

- ROI 四點微調視窗下方控制改為固定顯示的上下左右箭頭按鈕，不再需要先點「上、下、左、右」再開啟彈出控制。
- 使用者可直接點選預覽圖上的 1、2、3、4 頂點切換目前調整點。
- 視窗開啟時支援鍵盤 `1`、`2`、`3`、`4` 切換頂點；方向鍵或下方箭頭按鈕每次微調選取頂點 1px。

### 操作用法

1. 開啟「ROI 邊框微調」。
2. 點選任一頂點，或按 `1`、`2`、`3`、`4` 選取 P1-P4。
3. 使用鍵盤方向鍵，或下方 `↑`、`↓`、`←`、`→` 按鈕微調位置。
4. 按「儲存並退出」送出 `POST /api/table/roi-polygon`。

### 輸出格式

```json
{
  "points": [
    { "x": 92, "y": 48 },
    { "x": 1705, "y": 48 },
    { "x": 1705, "y": 813 },
    { "x": 92, "y": 813 }
  ]
}
```

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 05/11:'調整設定頁返回主畫面位置'

### 功能說明

- 設定頁左側導覽的「返回主畫面」改放在「一般」分類上方。
- 「返回主畫面」文字左側新增左箭頭，點擊後回到主畫面串流頁。
- 設定頁左側導覽底部不再顯示任何按鈕或選單內容。

### 規範用法

- 進入 `設定` 頁時，左側排序應為：`返回主畫面`、`一般`、`外觀`、`相機`、`球桌校正`、`追蹤設定`。
- 只有非設定頁才顯示底部帳號/設定選單入口。

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 05/11:'調整畫面品質設定位置'

### 功能概要

- 即時影像頁不再顯示低/中/高畫質切換按鈕，避免在影像卡片內重複調整。
- 畫質設定移到設定頁「一般」區塊，欄位名稱改為「畫面品質」。
- 訪客登入時，畫面品質只保存於目前前端 session，退出後不保留。
- 帳號登入時，畫面品質寫入瀏覽器 `localStorage` 的 `stream-quality:{username}`，登出後再次登入會沿用原設定；後續可替換為資料庫設定。
- 即時影像串流繼續使用既有 `quality=low|med|high` 查詢參數。
- 設定頁原「一般設定」標題改為「一般」。

### 驗證

```powershell
cd frontend
npm.cmd run build
```

## 05/10:'新增 ROI 四點微調視窗'

### 功能概要

- 設定頁「球桌 ROI 微調」保留 HSV 自動 ROI、調整後 ROI 與偵測狀態，偵測狀態以下改為單一「微調邊框」入口。
- 「微調邊框」會開啟背景模糊的四點 ROI 視窗，視窗內顯示既有 MJPEG 即時影像。
- 「重設框選」會清除目前四點並進入連擊模式；使用者依序點擊四次後儲存四個角點。
- 點選任一頂點後，可用鍵盤方向鍵或 UI 上/下/左/右按鈕每次微調 1px。

### API

```http
GET  /api/table/roi-polygon
POST /api/table/roi-polygon
POST /api/table/roi-polygon/reset
```

### 輸入範例

`POST /api/table/roi-polygon` 接收四個點，順序為使用者點擊順序：

```json
{
  "points": [
    { "x": 92, "y": 48 },
    { "x": 1705, "y": 48 },
    { "x": 1705, "y": 813 },
    { "x": 92, "y": 813 }
  ]
}
```

也相容陣列格式：

```json
{
  "points": [[92, 48], [1705, 48], [1705, 813], [92, 813]]
}
```

### 輸出格式

```json
{
  "status": "success",
  "points": [[92, 48], [1705, 48], [1705, 813], [92, 813]],
  "table_roi": [92, 48, 1613, 765],
  "table_roi_status": "manual_polygon"
}
```

### 相容規則

- `table_roi_points` 會寫入 `runtime/table_roi_polygon.json` 並隨 metadata 輸出。
- 既有 YOLO、球洞、planner 與 AI Coach 仍使用矩形 `table_roi`；四點 ROI 會計算外接矩形後同步更新 `table_roi`。
- 舊版 `/api/roi/*` 與 polygon mask 流程仍不恢復；新的四點 API 僅服務設定頁 ROI 校正視窗。
- `POST /api/table/roi-polygon/reset` 會清除手動四點 ROI，下一個分析 frame 回到 HSV/既有 ROI 偵測流程。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\tracking\tracking_engine.py
cd frontend
npm.cmd run build
```

## 05/10:'新增全站語言切換功能'

### 功能說明

- 前端支援 `zh-TW`、`zh-CN`、`en-US` 三種語言。
- 語言偏好保存於 `localStorage` 的 `ncut.language`。
- 切換語言會同步更新 `document.documentElement.lang`、i18next runtime language，以及使用 `t()` 的 UI 文案。
- 設定入口位於「設定 > 一般 > 系統資訊」下方的「一般設定」，第一版只放「語言」選項。

### 規範用法

- 新增 UI 顯示文字時，必須在 `frontend/src/i18n/locales/` 的三語字典新增翻譯 key。
- React 元件內不得直接硬寫新的使用者可見文案，需使用 `useTranslation()` 與 `t("...")`。
- API enum、資料欄位名稱、schema key 不翻譯；只翻使用者看得到的 UI 文案。

### AI Coach 語言同步

- 前端呼叫 `/api/coach/chat` 與 `/api/coach/suggest` 時會帶入：

```json
{
  "locale": "zh-TW"
}
```

- 主後端會驗證並正規化 `locale`，再透過 `CoachBridge` WebSocket payload 轉送給 `ai_coach` service。
- `ai_coach` service 依 `locale` 調整 system prompt，讓切換語言後的新回覆使用目前語言。
- 既有聊天紀錄不會被自動翻譯或改寫。

### 相關檔案

```text
frontend/src/i18n/
frontend/src/App.tsx
frontend/src/components/pages/SettingsPage.tsx
frontend/src/components/AICoachFloatingChat.tsx
backend/main.py
backend/core/coach_bridge.py
ai_coach/src/ai_coach/service.py
```

## 05/10:'新增 YOLO future 卡死保護'

### 問題背景

- 監控串流啟用 YOLO 後，若單一 `yolo_future` 長時間不返回，後端會持續輸出 `YOLO future is still running after ... waiting instead of resubmitting`。
- `Future.cancel()` 無法中止已進入執行中的 Python thread / GPU 推論，因此不能在逾時後直接重送，否則可能把 ThreadPool 或 GPU 工作堆滿。

### 規範用法

- `YOLO_FUTURE_TIMEOUT_MS`：軟逾時，只負責每 5 秒輸出等待警告，預設 `2500`。
- `YOLO_FUTURE_HARD_TIMEOUT_MS`：硬逾時，超過後自動停用 `system_state["is_analyzing"]`，預設 `30000`。
- 硬逾時觸發後，`latest_analysis_data["data"]` 會回報：

```json
{
  "status": "yolo_stalled",
  "message": "YOLO inference stalled; restart backend before enabling analysis again.",
  "stalled_after_ms": 30001,
  "source_frame_id": 123
}
```

### 恢復方式

- 若 log 出現 `YOLO future stalled after ... disabling analysis until backend restart`，代表 YOLO 推論 thread 已卡死。
- 請重啟後端，讓 YOLO model、ThreadPool 與 GPU context 重新初始化。
- 若頻繁發生，可先降低負載：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8001/api/control/yolo-skip -ContentType "application/json" -Body '{"skip_frames":3}'
```

### 相關檔案

```text
backend/main.py
backend/config.py
```


## 05/10:'提高前端 overlay metadata 更新頻率'

### 功能說明

- `METADATA_RATE_HZ` 預設由 `10` 提高到 `20`，讓 monitor 與練習模式前端 SVG overlay 更快收到最新球框、球號、cue 與路線資料。
- WebSocket control loop 的接收 timeout 改為依 metadata interval 動態計算，避免固定 `100ms` timeout 把 metadata 推送硬卡在約 10Hz。
- `PROJECTOR_RENDER_MAX_FPS` 預設由 `12` 提高到 `15`，讓 projector renderer 在 CPU 足夠時可更快更新。
- 這只提高「繪圖資料送出與投影繪製上限」，不會讓 YOLO 推論本身超過實際 FPS；若 YOLO 只有 9 FPS，overlay 仍只能在新 metadata 出現時更新真實位置。

### 規範用法

```env
METADATA_RATE_HZ=20
PROJECTOR_RENDER_MAX_FPS=15
```

- 若 CPU 使用率上升或 WebSocket client 很多，可把 `METADATA_RATE_HZ` 降回 `12~15`。
- 若 projector render avg/max ms 明顯升高，可把 `PROJECTOR_RENDER_MAX_FPS` 降回 `12`。
- 若 `/api/performance/stats` 看到 `metadata_rate_hz=20` 但前端仍只有約 9 FPS，瓶頸通常是 YOLO 推論或相機取幀，不是前端繪圖。

### 相關檔案

```text
backend/config.py
backend/main.py
```

## 05/10:'修正前端球圓標註與桿頭白球誤判'

### 功能說明

- `metadata.update` 新增輸出 monitor 座標系的 `white_ball`，前端 overlay 會把它合併到球標註清單，避免白球因不在 `balls` / `detections_view` 內而沒有框。
- monitor 與練習模式的球標註由方框改為 bbox 內接圓，圓框顏色依球號/球色決定，中心顯示球號；白球使用 `0`。
- 後端會使用 segmentation refine 後的 `mask_center`、`mask_bbox` 與 `cue_axis` 排除貼在球桿軸線上的白球候選，降低白色桿頭或桿身高光被誤判成母球的機率。

### 規範用法

```env
CUE_TIP_WHITE_SUPPRESS_ENABLED=true
CUE_TIP_WHITE_SUPPRESS_PAD_RATIO=0.20
CUE_TIP_WHITE_AXIS_DISTANCE_RATIO=0.72
CUE_TIP_WHITE_AXIS_ENDPOINT_MARGIN_RATIO=0.08
```

- `CUE_TIP_WHITE_SUPPRESS_ENABLED=false`：關閉 cue 桿頭白球候選過濾。
- `CUE_TIP_WHITE_SUPPRESS_PAD_RATIO`：以 cue bbox 短邊比例外擴候選檢查區。
- `CUE_TIP_WHITE_AXIS_DISTANCE_RATIO`：候選白球中心距離 cue 軸線小於 `ball_radius * ratio` 時才視為桿頭/桿身誤判；若真母球被誤濾，可調低至 `0.45~0.60`。
- `CUE_TIP_WHITE_AXIS_ENDPOINT_MARGIN_RATIO`：允許 cue 軸線端點外少量範圍仍視為桿頭區，避免端點白色桿頭被漏掉。
- 前端 overlay 若同時收到 `detections_view` 內的白球與獨立 `white_ball`，會以中心距離去重，只畫一次。

### 輸出格式

```json
{
  "img_w": 1280,
  "img_h": 720,
  "white_ball": [920, 190, 28, 28],
  "detections_view": [
    {"x": 410, "y": 250, "w": 28, "h": 28, "number": 3, "color": "Red"}
  ],
  "cue": [830, 310, 38, 190]
}
```

### 相關檔案

```text
backend/config.py
backend/main.py
backend/tracking/tracking_engine.py
frontend/src/sdk/types.ts
frontend/src/components/pages/StreamPage.tsx
frontend/src/components/pages/PracticePage.tsx
```

## 05/10:'新增練習模式前端 metadata overlay'

### 功能說明

- 練習模式的標註顯示模式改由前端 `PracticePage` 使用 WebSocket `metadata.update` 疊 SVG overlay，不再依賴 monitor MJPEG 後端 burn-in overlay。
- `none` 會隱藏練習頁 overlay，`tactical` 會顯示球框、球號、路線、TARGET、AVOID、下一球、cue bbox 與 cue laser，`full` 會額外顯示 label 與 confidence。
- 球框顏色會依球號對應撞球顏色，框中央顯示球號；母球顯示 `0`，無法判定球號時保留空標籤。
- SVG 使用 metadata 的 `img_w` / `img_h` 作為 viewBox，並與練習頁影像同樣使用 `contain` 對齊，避免 overlay 與影像比例不同步。

### 規範用法

- 練習頁上方「無 / 戰術 / 完整」切換只影響前端 overlay 可視內容。
- 後端 `/api/control/overlay-mode` 仍會同步收到切換狀態，用於保留既有後端模式語意，但練習頁可視標註以 WebSocket metadata 為準。
- 若 overlay 消失，先確認 WebSocket `metadata.update` 仍包含 `detections_view` 或 `detections`，以及 `multi_plan.best_route` 是否存在。

### 輸出格式

```json
{
  "img_w": 1280,
  "img_h": 720,
  "detections_view": [
    {"x": 210, "y": 204, "w": 30, "h": 30, "number": 1, "color": "yellow"}
  ],
  "cue": [840, 310, 36, 198],
  "cue_laser_line": [[835, 505], [920, 120]],
  "multi_plan": {
    "best_route": {
      "route_segments": [{"type": "cue_to_contact", "points": [[730, 330], [790, 300]]}],
      "position_play": {
        "next_ball": {"number": 2, "center": [1010, 105]},
        "cue_ball_after_contact": {
          "target_zone": {"center": [820, 290], "radius": 36},
          "avoid_zones": [{"type": "object_ball", "center": [640, 210], "radius": 34}]
        }
      }
    }
  }
}
```

### 相關檔案

```text
frontend/src/components/pages/PracticePage.tsx
frontend/src/components/pages/PracticePage.css
```

## 05/10:'改用前端 metadata 繪製 monitor overlay'

### 功能說明

- monitor MJPEG 預設改為乾淨相機影像，避免後端 OpenCV 將舊 metadata 直接燒進最新 frame。
- 前端 `StreamPage` 會使用 WebSocket `metadata.update` 在影像上方疊 SVG overlay，繪製球框、路線、TARGET、AVOID、下一球、cue bbox 與 cue laser。
- 後端送給前端的 `multi_plan` 會縮放到 monitor metadata 的 `img_w=1280`、`img_h=720` 座標系，與 `detections_view`、`cue` 欄位一致。
- projector 仍維持後端 renderer，不受 monitor 前端 overlay 改動影響。

### 規範用法

```env
MONITOR_STREAM_USE_YOLO_OVERLAY=false
```

- monitor 端需要看前端疊圖時，開啟即時影像頁即可。
- dev mode 下會顯示 bbox label 與 confidence；一般模式保留較乾淨的線、圈與框。
- 若要回到後端 burn-in overlay，可手動設定 `MONITOR_STREAM_USE_YOLO_OVERLAY=true`，但即時監控建議維持 `false`。

### 輸出格式

```json
{
  "img_w": 1280,
  "img_h": 720,
  "detections_view": [{"x": 120, "y": 90, "w": 28, "h": 28, "number": 2}],
  "cue": [300, 280, 260, 24],
  "cue_laser_line": [[300, 292], [820, 340]],
  "multi_plan": {
    "best_route": {
      "route_segments": [{"type": "cue_to_contact", "points": [[400, 300], [520, 260]]}],
      "position_play": {
        "cue_ball_after_contact": {
          "target_zone": {"center": [650, 180], "radius": 42},
          "avoid_zones": [{"type": "object_ball", "center": [500, 160], "radius": 38}]
        }
      }
    }
  }
}
```

### 相關檔案

```text
backend/config.py
backend/main.py
frontend/src/components/pages/StreamPage.tsx
frontend/src/components/pages/StreamPage.css
```

## 05/10:'新增進階監控 Cue 數據'

### 功能說明

- 後端 `metadata.update` 現在會輸出監控畫面座標系的 cue bbox、cue axis、cue laser line、raw YOLO cue boxes 與 `cue_laser_only` 狀態。
- 前端「一般 > 顯示進階數據監控」啟用後，會新增 `Cue 數據` 區塊，顯示偵測狀態、YOLO cue 數量、bbox、中心點、最高信心值、laser 主線長度/角度、cue axis 與反向線。
- 座標已由後端縮放至 monitor metadata 的 `img_w` / `img_h`，可直接與監控畫面疊圖對照。

### 規範用法

- 開啟設定頁「顯示進階數據監控」。
- 若 `偵測狀態` 為 `None`，先檢查 YOLO 是否輸出 `cue` label，並確認後端正在分析。
- 若 `Cue bbox` 有值但 `Laser 主線` 無值，代表球桿框有偵測到，但軸線估計或 laser line 推算尚未通過。

### 輸出格式

```json
{
  "cue": [120, 210, 340, 28],
  "cue_axis": [[130, 222], [450, 245], [0.99, 0.07]],
  "cue_laser_line": [[130, 222], [780, 268], [130, 222], [20, 214]],
  "cue_laser_only": false,
  "raw_yolo_boxes": [
    {"x": 120, "y": 210, "w": 340, "h": 28, "label": "cue", "conf": 0.83}
  ]
}
```

### 相關檔案

```text
backend/main.py
backend/tracking/tracking_engine.py
frontend/src/sdk/types.ts
frontend/src/components/pages/SettingsPage.tsx
frontend/src/components/pages/SettingsPage.css
```

## 05/10:'限制 projector 走位避讓區顯示'

### 功能說明

- projector 上大量紅色 `AVOID` 圈來自 `position_play.cue_ball_after_contact.avoid_zones`，資料包含非目標球避讓區與袋口 scratch 風險區。
- 投影端預設只顯示前 3 個非袋口避讓區，避免整桌被紅圈蓋滿。
- 完整 `avoid_zones` 仍保留在 planner payload，不影響走位分數與 AI Coach 判斷。

### 規範用法

```env
PROJECTOR_SHOW_POSITION_AVOID_ZONES=true
PROJECTOR_SHOW_POCKET_AVOID_ZONES=false
PROJECTOR_MAX_AVOID_ZONES=3
```

- `PROJECTOR_SHOW_POSITION_AVOID_ZONES=false`：完全不投影紅色 `AVOID` 圈。
- `PROJECTOR_SHOW_POCKET_AVOID_ZONES=true`：重新顯示袋口 scratch 風險區。
- `PROJECTOR_MAX_AVOID_ZONES=0`：不限制顯示數量。

### 輸出格式

```json
{
  "projector_position_avoid_zones": {
    "enabled": true,
    "show_pocket_scratch": false,
    "max_zones": 3
  }
}
```

### 相關檔案

```text
backend/config.py
backend/calibration/projector_renderer.py
backend/tracking/tracking_engine.py
backend/main.py
```

## 05/10:'調整相機偵測流程避免 OpenCV obsensor 無效索引警告'

### 功能說明

- 後端相機偵測新增 `CAMERA_ENABLE_ANY_BACKEND` 開關，預設為 `false`。
- `/api/camera/list` 與 `open_camera()` 共用明確 backend 候選順序：上次成功 backend、`DSHOW`、`MSMF`。
- 預設流程不再自動嘗試 `CAP_ANY`，避免 OpenCV 在 Windows 自動輪詢 `obsensor` 等不存在來源時輸出 `Camera index out of range`。
- 若使用特殊擷取卡或非標準 OpenCV backend，可在 `.env` 設定 `CAMERA_ENABLE_ANY_BACKEND=true`，或透過 `/api/camera/switch` 明確指定 `backend: 0` 來啟用 `CAP_ANY` fallback。

### 規範用法

```env
CAMERA_WIDTH=1920
CAMERA_HEIGHT=1080
CAMERA_FPS=50
CAMERA_ENABLE_ANY_BACKEND=false
CAMERA_FOURCC_PRIORITY=MJPG,YUY2,YUYV
```

### 輸出格式

```text
Device 0: trying backend=700, 1920x1080@50...
Device 0: trying backend=1400, 1920x1080@50...
```

- 預設不會出現 `backend=0` 的 `CAP_ANY` 嘗試。
- 成功時仍會輸出實際 FOURCC、解析度與 FPS。

### 相關檔案

```text
backend/main.py
backend/config.py
backend/.env.example
```

### 驗證

```powershell
python -m py_compile backend\main.py backend\config.py
```

## 05/10:'整理後端 .env 與 config.py 設定結構'

### 功能說明

- `backend/.env` 縮成最小本機設定檔，只保留現場常調的 YOLO 模型/門檻、球桌顏色、相機串流、AI Coach 與診斷開關。
- second-pass、Overlay、球體後處理、球桿軸線、Session、metadata 與其他穩定預設統一回到 `config.py` 管理，避免 `.env` 變成第二份設定檔。
- `.env` 明確指定 `MODEL_PATH=yolo-weight/best.pt`，符合目前使用 `best.pt` 的辨識基準。
- 移除 `.env` 內硬覆蓋的 `HSV_LOWER/HSV_UPPER`，改用 `TABLE_CLOTH_COLOR=blue` 與 runtime 色彩偏好；手動 HSV 僅保留為註解範例，避免覆蓋藍色桌布設定。
- `config.py` 新增 `get_path_env()` / `resolve_project_path()`，讓 `MODEL_PATH` 固定以 `backend/` 解析，`TABLE_COLOR_PREFERENCES_PATH` 與 `TABLE_ROI_ADJUSTMENT_PATH` 固定以專案根目錄解析。
- `get_np_array_env()` 會檢查 HSV 陣列長度並回傳 `np.uint8`，避免 `.env` 逗號數量錯誤時默默產生非預期陣列。

### 規範用法

```env
MODEL_PATH=yolo-weight/best.pt
CONF_THR=0.35
TABLE_CLOTH_COLOR=blue
CAMERA_WIDTH=1920
CAMERA_HEIGHT=1080
CAMERA_FPS=50
AI_COACH_ENABLED=true
```

- `MODEL_PATH` 使用相對路徑時，相對於 `backend/`。
- `TABLE_COLOR_PREFERENCES_PATH` 與 `TABLE_ROI_ADJUSTMENT_PATH` 使用相對路徑時，相對於專案根目錄。
- 只有需要完全手動鎖定桌布 HSV 時，才取消 `.env` 裡 `HSV_LOWER/HSV_UPPER` 的註解；啟用後會覆蓋 `TABLE_CLOTH_COLOR` 與 runtime 偏好。

### 相關檔案

```text
backend/.env
backend/config.py
docs/api/IMPLEMENTATION_GUIDE.md
```

### 驗證

```powershell
python -m py_compile backend\config.py
python -m pytest backend\test-program\tracking\test_tracking.py
```

## 05/09:'恢復 best.pt 高精度辨識基準'

### 功能說明

- 後端 `.env` 的 `MODEL_PATH` 改為 `yolo-weight/best.pt`，避免載入已移走的 `pool.pt` 導致 YOLO 初始化失敗。
- `CONF_THR` 程式預設值恢復為參考 commit `535c872d75f78c6545913acb1ebddc2d517230af` 的 `0.60`，以高精度基準為主。
- `SECOND_PASS_MIN_BALLS` 預設改為 `0`，不再每幀因球數不足強制跑 `conf=0.04` 的高解析補框，避免誤框讓準確率下降。
- 若日後需要補球，可在 `.env` 額外設定 `SECOND_PASS_MIN_BALLS=9`，但此模式偏召回，可能降低精度。
- 球型練習 `cue_laser_only` 模式仍維持 `CUE_LASER_ONLY_DISABLE_SECOND_PASS=true` 時停用 second-pass，避免球桿雷射線場景延遲上升。
- `_analyze_balls()` 對 `table_roi_raw`、`table_roi_adjustment`、`table_roi_status` 改為容錯輸出，讓輕量測試實例也能回傳完整 metadata。

### 規範用法

```text
MODEL_PATH=yolo-weight/best.pt
CONF_THR=0.35
SECOND_PASS_ENABLED=true
SECOND_PASS_MIN_OBJECTS=4
SECOND_PASS_MIN_BALLS=0
SECOND_PASS_CONF_THR=0.04
SECOND_PASS_IMG_SIZE=960
```

- `SECOND_PASS_MIN_BALLS` 計算 `white-ball` 與 `color-ball`，不包含 `cue`。
- 預設 `0` 代表停用「依球數不足強制 second-pass」；仍保留原本 `SECOND_PASS_MIN_OBJECTS` 的低檢出補強。
- `SECOND_PASS_SKIP_WHEN_CUE_FOUND=true` 只會在球數已達 `SECOND_PASS_MIN_BALLS` 時跳過 second-pass；球數不足時仍以召回率優先。

### 輸出格式

```text
Loading YOLO model from: ...\backend\yolo-weight\best.pt
```

### 相關檔案

```text
backend/.env
backend/config.py
backend/tracking/tracking_engine.py
backend/test-program/tracking/test_tracking.py
```

### 驗證

```powershell
python -m py_compile backend\tracking\tracking_engine.py backend\config.py
python -m pytest backend\test-program\tracking\test_tracking.py
```

## 05/08:'拆分帳號管理密碼與安全問題卡片'

### 功能說明

- 帳號管理頁的「更新密碼」與「安全問題」拆成兩個獨立 section。
- 兩個區塊各自擁有標題、副標題與卡片，不再共用「安全與驗證」標題。
- 安全問題區塊增加上方間距，避免兩張設定卡片黏在一起。

### 相關檔案

```text
frontend/src/components/pages/AccountManagementPage.tsx
frontend/src/components/pages/AccountManagementPage.css
```

## 05/08:'恢復開始探索原版純 CSS 視覺'

### 功能說明

- 開始探索頁恢復為原本純 CSS 深色科技背景，不使用參考圖資產。
- 顯示中央 `Q Track`、`BILLIARDS ANALYSIS SYSTEM` 副標與單一「開始探索」按鈕。
- 移除先前新增的 `frontend/src/assets/explore-reference.png`。

### 相關檔案

```text
frontend/src/components/ExploreScreen.tsx
frontend/src/components/ExploreScreen.css
```

## 05/08:'更新安全問題下拉選單'

### 功能說明

- 安全問題共用來源 `securityQuestions` 更新為五個日常生活題目。
- 註冊頁、找回密碼顯示、帳號管理頁皆使用同一份 `securityQuestions` 或其儲存結果，確保內容同步。
- 讀取舊 Mock 帳號資料時，若既有 `securityQuestion` 不在新版清單內，會自動遷移為新版第一題。

### 新版選項

```text
你人生中養過的第一隻寵物叫什麼名字？
你最要好的朋友名字是？
你最喜歡的休閒活動是？
你最嚮往或最喜歡去旅行的一個國家？
你最喜歡的一部電影或動漫名稱？
```

### 相關檔案

```text
frontend/src/auth/mockAccountStore.ts
frontend/src/components/AuthScreens.tsx
frontend/src/components/pages/AccountManagementPage.tsx
```

## 05/08:'新增歡迎頁返回開始探索'

### 功能說明

- 歡迎介面新增 `<` 返回按鈕，位置固定在整個畫面左上角，不放在卡片框內。
- 使用者點擊後會從 `AuthScreens` 回到 `ExploreScreen` 開始探索頁。
- 返回行為由 `App.tsx` 管理 `hasExplored=false`，`AuthScreens` 只透過 `onBackToExplore` 觸發，不自行管理全域流程狀態。
- 登入、註冊、找回密碼等認證流程既有返回鍵也統一固定於畫面左上角，顯示文字一律為 `<`。
- 05/08 補充：返回鍵統一改由 `auth-screen-back-button` 在 `auth-screen` 畫面層渲染，移除各卡片內原本的返回按鈕，避免不同頁面箭頭位置偏差。

### 規範用法

```tsx
<AuthScreens
  initialMode={authInitialMode}
  onAuthenticated={handleAuthenticated}
  onBackToExplore={() => setHasExplored(false)}
/>
```

### 相關檔案

```text
frontend/src/App.tsx
frontend/src/components/AuthScreens.tsx
frontend/src/components/AuthScreens.css
```

## 05/08:'修正登入紀錄改為實際 Mock 登入資料'

### 功能說明

- 帳號管理頁移除寫死的登入紀錄資料，改由目前 Mock 使用者的 `loginHistory` 顯示最近 3 筆紀錄。
- 使用者登入成功時會新增一筆「成功」紀錄；密碼錯誤且帳號存在時會新增一筆「失敗」紀錄。
- 每筆紀錄包含日期時間、登入狀態與裝置資訊，資料保存在 `qtrack_mock_users` 的使用者物件中。
- 舊帳號資料讀取時若沒有 `loginHistory`，會自動補成空陣列，避免舊資料格式造成頁面錯誤。

### 範例

```json
{
  "username": "QTrack_User",
  "loginHistory": [
    {
      "datetime": "2026-05-08 03:15",
      "status": "成功",
      "device": "Chrome / Windows"
    }
  ]
}
```

### 規範用法

```tsx
const nextUsers = appendLoginRecord(users, username, '成功');
setUsers(nextUsers);
saveMockUsers(nextUsers);
```

帳號管理頁僅顯示最近 3 筆，儲存層最多保留 10 筆，避免 localStorage 無限制累積。

### 相關檔案

```text
frontend/src/auth/mockAccountStore.ts
frontend/src/components/AuthScreens.tsx
frontend/src/components/pages/AccountManagementPage.tsx
frontend/src/components/pages/AccountManagementPage.css
```

## 05/08:'新增登出確認與登出中波浪提示'

### 功能說明

- 使用者在已登入帳號狀態按下「登出」時，頁面會先套用背景虛化並顯示中央確認視窗。
- 按下「取消」會關閉確認視窗並恢復原頁面。
- 按下「確認」後，確認視窗切換為「正在登出中，請稍後」，彈窗上方顯示與登入流程一致的藍色流水線，持續 2.5 秒後清除登入狀態並回到歡迎登入流程。
- 訪客狀態下按下「登入」維持原流程，直接切換到登入畫面，不顯示登出確認。

### 規範用法

```tsx
const [logoutDialogState, setLogoutDialogState] = useState<'idle' | 'confirming' | 'logging-out'>('idle');
```

登出流程應集中由 `App.tsx` 控制，避免側欄、帳號頁與各功能頁各自實作不同登出行為。畫面虛化與波浪動畫樣式統一放在 `App.css`。

### 輸出格式

```text
確認階段: 確定要登出嗎？
登出階段: 正在登出中，請稍後
登出等待時間: 2500ms
載入動畫: 藍色流水線
```

### 相關檔案

```text
frontend/src/App.tsx
frontend/src/App.css
```

## 05/08:'維持設定子頁側邊欄'

### 功能說明

- 從設定頁「球桌校正」進入 `顏色校正` 或 `投影機校正` 時，左側 Sidebar 仍保持設定 Tab 導覽，不再切回主頁面的功能導覽。
- `Dashboard` 仍以 `currentPage` 決定主內容顯示，但傳給 `Sidebar` 的頁面狀態會將 `calibration`、`color-calibration`、`camera-params` 視為 `settings`。
- 這讓使用者在校正流程中可持續看到「一般、外觀、相機、球桌校正、追蹤設定」設定側邊欄，符合設定子頁的導覽語意。

### 範例

```tsx
const sidebarPage: PageType =
  currentPage === 'calibration' || currentPage === 'color-calibration' || currentPage === 'camera-params'
    ? 'settings'
    : currentPage;

<Sidebar currentPage={sidebarPage} />
```

### 影響檔案

```text
frontend/src/components/Dashboard.tsx
```

## 05/07:'修正 YOLO 推論逾時重送造成無標註'

### 功能說明

- 修正相機擷取迴圈中 YOLO future 逾時後重複 `cancel()` 並重新提交任務的問題。
- Python ThreadPool 中已開始執行的 GPU 推論無法被 `Future.cancel()` 中止；原行為會持續堆積未完成推論，導致 `yolo_result` 長時間停在舊 frame，畫面只剩原始影像而沒有球桌與球的框線。
- 新行為在超過 `YOLO_FUTURE_TIMEOUT_MS` 時只每 5 秒記錄一次警告，並等待同一個推論完成，不再重送堆積任務。

### 診斷指標

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/performance/stats
Get-Content backend\logs\backend-runtime.log -Tail 120
```

若 `stage_latency_ms.yolo_result.stale_frames` 持續增加，且 log 反覆出現 `YOLO future timed out after ... resubmitting`，代表舊版本已把推論 worker 堆滿，需要重啟後端載入修正。

### 規範用法

- 啟動辨識後若畫面沒有框，先確認 `/api/performance/stats` 中 `is_analyzing=true`、`monitor_effective_overlay=true`、`camera.last_frame_age_ms` 有更新。
- 若相機與 overlay 皆啟用，但 `overlay_metadata_fresh=false` 且 `yolo_result.stale_frames` 很高，優先判定為 YOLO 推論結果未回來，而不是前端繪圖問題。
- 後端從 `backend` 工作目錄啟動時，runtime 狀態檔統一寫入 `backend/runtime`，避免寫入上一層 `runtime` 時被 Windows 權限拒絕。

## 05/07:'調整進階監控顯示於一般設定下方'

### 功能說明

- 開發者工具的 `顯示進階數據監控` 開啟後，不再於左側 Sidebar 顯示第 6 個 `進階監控` Tab。
- 進階監控內容會直接接在 `一般` 設定頁的開發者工具區塊下方。
- 若舊狀態仍停在 `advanced-monitoring`，設定內容會 fallback 顯示 `一般`，避免出現第二導覽或獨立進階監控頁。
- 全設定頁維持無 icon，進階監控仍只綁本地 `isDevMode` state，不串接後端設定 API。

### 影響檔案

```text
frontend/src/components/Sidebar.tsx
frontend/src/components/pages/SettingsPage.tsx
```

### 驗證

```powershell
.\node_modules\.bin\tsc.cmd --noEmit
npm.cmd run build
```

## 05/07:'修正 overlay metadata 過期與 YOLO future 卡住'

### 調整範圍

- 一般即時影像與 AI Coach 共用同一套 overlay 保護流程，避免使用一段時間後外框、球框與球號消失。
- `camera_capture_loop()` 會依 `YOLO_FUTURE_TIMEOUT_MS` 檢查未完成的 YOLO future，超時後取消該 future 並重新提交下一張影格，避免推論 worker 卡住造成 overlay 永久停在舊資料。
- overlay freshness 優先使用 `latest_analysis_data["overlay_timestamp"]`，也就是分析完成並寫入 overlay cache 的時間；只有沒有 overlay timestamp 時才 fallback 到 `_source_timestamp`。
- `_has_drawable_overlay_data()` 不再要求同時有母球與子球。只要有 `table_roi`、洞口、母球或子球任一可繪製資料，就會保留為最新 overlay，讓球桌外框能獨立維持。

### 設定

```text
YOLO_FUTURE_TIMEOUT_MS=2500
LAST_GOOD_OVERLAY_HOLD_MS=5000
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\tracking\tracking_engine.py backend\config.py
Invoke-RestMethod http://127.0.0.1:8001/api/performance/stats | ConvertTo-Json -Depth 6
```

## 05/07:'移除 legacy 四點 ROI mask'

### 功能說明

- 移除舊版四點 polygon ROI mask 工具與設定檔。
- 主流程維持使用 HSV table ROI 偵測與 `table_roi_adjustment` 微調。
- 後端不再 import `roi_manager.apply_roi_mask`，YOLO 前處理不再保留舊 mask 分支。
- 移除舊 `/api/roi/*` 端點，避免與目前 `/api/table/roi-adjustment` 工作流混淆。

### 移除檔案

```text
roi_manager.py
roi_config.json
tests/test_roi_manager.py
```

### 仍保留的 ROI 工作流

```http
GET  /api/table/roi-adjustment
POST /api/table/roi-adjustment
POST /api/table/roi-adjustment/reset
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\tracking\tracking_engine.py
```

## 05/07:'新增 AI Coach 後續實作計畫'

### 目的

- 新增 `docs/architecture/AI_COACH_NEXT_STEPS.md`，整理下一階段實作順序與驗證方式。
- 優先順序為：ROI 設定頁整理、ROI/planner/coach 一致性檢查、AR 實機校驗、AI Coach 回答品質、第二版走位模型。
- 此文件只更新規劃，不修改功能行為。

### 後續文件

```text
docs/architecture/AI_COACH_NEXT_STEPS.md
```

## 05/07:'修正練習模式返回後球號不完整'

### 功能說明

- 練習模式會把後端影像標註切到 `tactical` 精簡模式，用於練習路線與目標球提示。
- 結束練習或離開練習頁後，系統現在會恢復 `full` 完整標註模式，讓即時影像重新顯示球桌框、洞口、白球與全部可辨識子球球號。
- 後端 `/api/practice/end` 與 `/api/planner/disable` 都會呼叫 `restore_live_annotation_mode()`，避免頁面切換或 keepalive 清理時殘留精簡標註。
- 前端「結束練習」流程會在 `/api/practice/end` 後補送 `/api/control/overlay-mode`，確保 UI 狀態同步回 `full`。
- 若使用者直接從練習頁點左側導覽離開，`Dashboard` 也會先呼叫 `/api/practice/end` 並恢復 `full` 標註模式。

### 影響檔案

```text
backend/main.py
frontend/src/components/Dashboard.tsx
frontend/src/components/pages/PracticePage.tsx
```

### 驗證

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/control/overlay-mode -Method Post -ContentType 'application/json' -Body '{"mode":"full"}'
Invoke-RestMethod http://127.0.0.1:8001/api/performance/stats | ConvertTo-Json -Depth 6
npx.cmd tsc --noEmit
```

## 05/07:'修正 AI Coach 開啟後影像 overlay 消失'

### 功能說明

- 開啟或選擇 AI Coach 對話時，前端會恢復即時影像完整標註模式，避免練習模式留下的 `tactical` 精簡標註讓 overlay 看起來消失。
- 若使用者在練習頁直接開啟 AI Coach，前端會先呼叫 `/api/practice/end`，再關閉 planner 並切回 `full` overlay。
- AI Coach 開啟時若辨識尚未啟動，前端會呼叫 `/api/control/analysis` 明確啟用 YOLO，避免只開聊天欄但串流沒有 overlay。
- 新增 `POST /api/control/analysis`，Body 使用 `{ "enabled": true | false }`，避免前端用 toggle 時因狀態不同步而反向關閉辨識。
- 後端 `/api/coach/suggest` 與 `/api/coach/chat` 會呼叫 `ensure_live_analysis_for_coach()`，讓舊前端或直接 API 呼叫也能恢復 `full` overlay 並維持 YOLO 辨識開啟。
- AI Coach 側欄只要被打開，前端就會先恢復即時影像完整 overlay，不必等到建立新對話。

### 影響檔案

```text
backend/main.py
frontend/src/components/Dashboard.tsx
```

### 驗證

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/control/overlay-mode -Method Post -ContentType 'application/json' -Body '{"mode":"full"}'
Invoke-RestMethod http://127.0.0.1:8001/api/control/analysis -Method Post -ContentType 'application/json' -Body '{"enabled":true}'
Invoke-RestMethod http://127.0.0.1:8001/api/performance/stats | ConvertTo-Json -Depth 6
npm.cmd run build
```

## 05/07:'一般即時影像維持 overlay 辨識'

### 功能說明

- 一般 `即時影像` 頁也納入 overlay 保護，不只限 AI Coach。
- 前端不再用 `/api/control/toggle` 猜測辨識狀態，改呼叫 `/api/control/analysis` 明確啟用或停用 YOLO。
- 在即時影像頁中，只要不是使用者明確按下 `停止辨識`，若 metadata 顯示辨識掉到 idle，前端會自動重新啟用 YOLO。
- 使用者按下 `停止辨識` 後會記錄為手動停止，不會被一般模式自動啟用流程覆蓋。

### 影響檔案

```text
frontend/src/components/Dashboard.tsx
backend/main.py
```

### 驗證

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/control/analysis -Method Post -ContentType 'application/json' -Body '{"enabled":true}'
Invoke-RestMethod http://127.0.0.1:8001/api/performance/stats | ConvertTo-Json -Depth 6
npm.cmd run build
```

## 05/07:'完成走位 AR 顯示、AI Coach 解說與路線排序'

### 功能說明

- 新增 `transform_best_route_for_ar(data_packet)`，保留既有 `transform_route_segments_for_ar()` 回傳格式不變，額外轉換最佳路線的 `cue_landing_point`、`cue_landing_zone` 與 `position_play`。
- 投影 AR 現在可接收並繪製 `position_play.cue_ball_after_contact.target_zone`、`avoid_zones`、`next_ball` 與母球落點區。
- burn-in 畫面會在多球路線上補畫走位目標區、避開區與下一球標記。
- AI Coach service prompt 會辨識 `coach.context.v1`，優先使用 `planner.best_route` 與 `planner.position_play`，並要求繁中回答包含目標球/袋、力道、桿法、母球走位、下一球目的與風險。
- `RouteScorer` 新增走位混分，第一版以原路線分數 70%、走位分數 30% 混合，並加入 `poor_position`、`cue_landing_near_pocket`、`next_ball_missing` 風險旗標。

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test-program\tracking\test_route_planner.py backend\test-program\test_coach_payload_builder.py
.\.venv\Scripts\python.exe -m pytest ai_coach\tests
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\tracking\tracking_engine.py backend\calibration\projector_renderer.py backend\tracking\planner\route_scorer.py backend\tracking\planner\route_planner.py backend\core\coach_payload_builder.py ai_coach\src\ai_coach\service.py
cd frontend
npx.cmd tsc --noEmit
```

## 05/07:'實作 planner.result.v1、position_play.v1 與 coach.context.v1'

### 功能說明

- `backend/tracking/planner/models.py` 新增 `planner.result.v1` 輸出與 `RouteCandidate.position_play` 欄位。
- 新增 `backend/tracking/planner/position_planner.py`，第一版針對可進攻路線輸出 `position_play.v1`，包含下一球、母球預估點、走位目標區、避開區、桿法建議與走位分數。
- `RoutePlanner` 會在產生 Top-N 路線後注入 `position_play`，目前不改變既有路線排序權重。
- 新增 `backend/core/coach_payload_builder.py`，統一 `/api/coach/chat`、`/api/coach/suggest`、auto analysis 的 `coach.context.v1` payload。
- 新增 `GET /api/coach/debug-payload`，可檢查 main 目前準備送給 AI Coach 的完整結構化資料。
- 前端 `RouteCandidate` 型別新增 `position_play`，即時影像與練習模式 planner 面板會顯示下一球、母球預估點、走位目標區與走位成功率。

### 輸出格式

```json
{
  "schema_version": "planner.result.v1",
  "best_route": {
    "position_play": {
      "schema_version": "position_play.v1",
      "next_ball": {"number": 2},
      "cue_ball_after_contact": {
        "expected_point": [705, 360],
        "target_zone": {"center": [720, 350], "radius": 48.0},
        "avoid_zones": []
      },
      "score": {
        "position_success_prob": 0.62,
        "shape_quality": 0.7,
        "risk": 0.24
      }
    }
  }
}
```

### 05/07:'調整球桌 HSV ROI 工作流與桌布自動檢測'
- 主流程已移除四點 `roi_config.json` / `roi_manager.py` mask 與 `ROI_MASK_ENABLED` 設定；tracker 目前直接使用 HSV 偵測出的球桌 ROI。
- `backend/.env` 移除固定 `HSV_LOWER` / `HSV_UPPER`，避免覆蓋 `runtime/table_color.json` 的上次桌布模式。
- 新增 HSV ROI 邊界微調，會保存至 `runtime/table_roi_adjustment.json`：
  - `left`、`top`、`right`、`bottom` 以像素調整 HSV 原始框。
  - metadata 同時輸出 `table_roi_raw`、`table_roi`、`table_roi_adjustment`、`table_roi_status`。
  - AI Coach 使用調整後的 `table_roi`。
- 桌布風格保留預設色與自訂 HSV，並新增「自動檢測顏色」：
  - 從目前 monitor frame 比對 `TABLE_COLOR_PRESETS` 的遮罩品質。
  - 選出最佳桌布色後呼叫 tracker 套用並寫入 `runtime/table_color.json`。

### API
```http
POST /api/table/color/auto-detect
GET  /api/table/roi-adjustment
POST /api/table/roi-adjustment
POST /api/table/roi-adjustment/reset
```

### 範例
```json
{
  "adjustment": { "left": -8, "top": 4, "right": 12, "bottom": -6 },
  "table_roi_raw": [160, 46, 1653, 783],
  "table_roi": [152, 50, 1673, 773],
  "table_roi_status": "preset-blue"
}
```

### 驗證
```powershell
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\tracking\tracking_engine.py
npx.cmd tsc --noEmit
npm.cmd run build
```

### API 範例

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/coach/debug-payload
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test-program\tracking\test_route_planner.py backend\test-program\test_coach_payload_builder.py
cd frontend
npx.cmd tsc --noEmit
```

## 05/07:'新增 AI Coach 路徑規劃與走位擴充 Roadmap'

### 目的

- 新增 `docs/architecture/AI_COACH_PATH_PLANNING_ROADMAP.md`，保留 AI Coach、路徑規劃、走位建議與後續路徑規劃器擴充待辦。
- 明確規範後端 planner 負責 deterministic 幾何、規則、物理、評分與走位結果；AI Coach 只透過 WebSocket/HTTP 使用結構化 payload 做教練解說。
- 建議後續統一 `planner.result.v1`、`position_play.v1`、`coach.context.v1`，避免前端與 AI Coach 直接依零散欄位推斷資料格式。

### 後續修改切點

```text
backend/tracking/planner/models.py
backend/tracking/planner/route_planner.py
backend/tracking/planner/candidate_generator.py
backend/tracking/planner/route_scorer.py
backend/core/coach_payload_builder.py
backend/main.py
frontend/src/components/*
```

### Roadmap 文件

```text
docs/architecture/AI_COACH_PATH_PLANNING_ROADMAP.md
```

## 05/07:'修正 AI Coach disabled 啟用設定'

### 問題

- 前端呼叫 `/api/coach/chat` 或 `/api/coach/suggest` 時出現 `AI Coach WebSocket unavailable: AI Coach disabled`。
- 根因是 `backend/config.py` 預設 `AI_COACH_ENABLED=false`，且 `backend/main.py` 原本在 `load_dotenv()` 前就 `import config`，導致 `backend/.env` 內的 AI Coach 設定不會套用到 config。

### 修正

- `backend/main.py` 改為先 `load_dotenv(PROJECT_ROOT / "backend" / ".env")`，再 `import config`。
- `backend/config.py` 的 `AI_COACH_ENABLED` 預設值改為 `true`，未設定環境變數時仍啟用 WebSocket bridge。
- `backend/.env` 新增 AI Coach WebSocket 啟用設定。
- 根目錄 `start.bat` 啟動時會先開啟 `ai_coach\start.bat`，再啟動後端，並明確傳入 `AI_COACH_ENABLED=true`、`AI_COACH_MODE=websocket`、`AI_COACH_WS_URL=ws://localhost:8010/ws/coach`。

### 設定

```env
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

### 驗證

```powershell
cd backend
..\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path.cwd() / '.env'); import config; print(config.AI_COACH_ENABLED, config.AI_COACH_WS_URL)"
```

預期輸出：

```text
True ws://localhost:8010/ws/coach
```

## 05/07:'一般網路連線新增 AI Coach WebSocket 網址'

### 功能說明

- 設定頁 `一般` Tab 的 `網路連線` 區塊新增 `AI Coach WebSocket URL` 欄位。
- 欄位預設值使用 `VITE_AI_COACH_WS`，未設定時顯示 `ws://localhost:8010/ws/coach`。
- 此欄位用於顯示與調整 AI Coach 遠端服務 WebSocket 連線位置；目前維持 UI 本地 state，不直接覆寫後端 runtime 設定。

### 欄位格式

```text
Backend API: http://localhost:8001
WebSocket URL: ws://localhost:8001
AI Coach WebSocket URL: ws://localhost:8010/ws/coach
```

### 影響檔案

```text
frontend/src/components/Dashboard.tsx
frontend/src/components/pages/SettingsPage.tsx
```

### 驗證

```powershell
npx.cmd tsc --noEmit
```

## 05/07:'強化 AI Coach 服務解耦邊界'

### 功能說明

- `ai_coach` 啟動腳本不再探測或使用主專案根目錄 `.venv`，改為只使用 `ai_coach\.venv\Scripts\python.exe` 或系統 Python。
- `ai_coach/docs/guides/INTEGRATION_GUIDE.md` 改為 WebSocket/HTTP 契約文件，明確禁止主後端直接 `import ai_coach` 或用 `sys.path` 指向 `ai_coach/src`。
- 主後端維持透過 `CoachBridge` 連線 `AI_COACH_WS_URL=ws://localhost:8010/ws/coach`；前端維持呼叫主後端 `/api/coach/chat`、`/api/coach/suggest`、`/api/coach/state`。

### 規範用法

```powershell
cd ai_coach
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\start.bat
```

### 連線格式

```text
frontend -> backend /api/coach/*
backend  -> ai_coach ws://localhost:8010/ws/coach
ai_coach -> vLLM http://localhost:8002/v1/chat/completions
```

### 禁止用法

```python
from ai_coach import AICoachManager
from ai_coach.core.client import AICoachManager
from ai_coach.tools.websocket_coach import SuggestionGenerator
```

### 驗證

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\core\coach_bridge.py backend\main.py backend\config.py ai_coach\src\ai_coach\service.py
```

## 05/07:'新增後端自動停止診斷功能'

### 功能說明

- 後端啟動後會把 stdout、stderr 與 runtime logger 同步寫入啟動工作目錄下的 `logs/backend-runtime.log`，用來追蹤非人工操作造成的關閉、例外與 Uvicorn 退出紀錄；透過 `start.bat` 啟動時路徑為 `backend/logs/backend-runtime.log`。
- 若 `logs/backend-runtime.log` 被舊程序鎖住，後端會自動改寫入 `logs/backend-runtime-<pid>.log`，避免因日誌檔鎖定造成啟動失敗。
- FastAPI startup/shutdown hook 會記錄 PID、uptime、相機擷取執行緒狀態與 active thread 數量。
- `/health` 回傳新增 `pid` 與 `uptime_sec`，可快速判斷目前回應的是哪一個後端程序。
- 新增 `GET /api/diagnostics/runtime`，輸出後端程序、相機、MJPEG 串流與執行緒診斷資訊。
- 後端啟動前會先檢查 `0.0.0.0:8001` 是否可綁定；若已被舊程序佔用，直接輸出明確錯誤並退出，不再進入 FastAPI startup/shutdown 流程，避免誤判為相機執行緒自動停止。

### API 範例

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/api/diagnostics/runtime
Get-Content backend\logs\backend-runtime.log -Tail 80
```

### 05/07:'調整設定頁一般內容為撞球系統設定'
- 設定頁右側保留 Codex 風格的窄版分段、panel row 與右側控制項排版。
- 一般頁內容改回 NCUT 撞球分析系統設定，不再顯示參考圖中的「工作模式」、「權限」、「預設權限」、「自動審查」等 Codex 範例文字。
- 一般頁目前包含：
  - 系統資訊：版本 `v1.5.1`。
  - 網路連線：`Backend API`、`WebSocket URL`，先以本地 state 綁定。
  - 開發者工具：`顯示進階數據監控` toggle，控制左側 `進階監控` Tab 顯示。
- 此調整仍屬 UI-only，不串接後端 API，也不持久化設定。

### 05/07:'顯示全部布料顏色預設'
- 外觀頁的「布料顏色預設集」由單一下拉選單改為可直接檢視的色塊按鈕清單。
- 目前預設色包含：綠色標準布、藍色競賽布、灰色低反光布、青綠訓練布、紅色展示布、黑色高對比布。
- 點選色塊後以本地 state 更新目前球桌顏色預覽；此設定仍不串接後端 API，也不持久化。

### 05/07:'設定頁底部返回主頁'
- 進入設定頁後，左側 Sidebar 底部原「設定」位置改顯示「回到主頁面」。
- 點擊「回到主頁面」會切回 `stream` 即時影像主頁。
- 非設定頁仍維持原本「設定」按鈕開啟帳戶選單，再由選單進入設定頁。

### 05/07:'調整球桌校正段落命名'
- 設定頁「球桌校正」Tab 內第一段標題由 `ROI 範圍校正` 改為 `AI 教練範圍檢測`。
- 既有 ROI 狀態、座標摘要、Mask、清除 ROI 與硬體輔助校正控制項維持 UI-only 行為不變。

### 05/07:'記憶球桌風格顏色校正'
- 外觀頁「球桌風格」的目前顏色會同時同步後端與瀏覽器 `localStorage`。
- 前端本機儲存 key：`ncut.tablePreset`，作為後端不可用時的 UI fallback。
- 設定頁載入時會先呼叫 `GET /api/table/colors` 讀取後端目前顏色。
- 切換顏色時會呼叫 `POST /api/table/color`，Body 範例：`{ "color": "blue" }`。
- 後端會將成功套用的顏色寫入 `runtime/table_color.json`，下次後端啟動時由 `backend/config.py` 載入。
- `runtime/` 為本機執行偏好資料，不納入 git 版控。

### 05/07:'球桌風格顏色選單對齊 config'
- 外觀頁「球桌風格」改為在「目前顏色」右側顯示顏色預覽與下拉選單。
- 移除下方獨立的布料色塊按鈕區，避免同一設定出現兩組控制。
- 前端顏色項目對齊 `backend/config.py` 的 `TABLE_COLOR_PRESETS`：
  - `green`：綠色
  - `gray`：灰色
  - `blue`：藍色
  - `pink`：粉色
  - `purple`：紫色
  - `custom`：自訂
- 顏色預覽使用各 HSV 範圍中間值換算出的近似顯示色；實際辨識仍以後端 config 的 HSV 為準。

### 05/07:'記住子球顏色校正套用狀態'
- 「顏色校正」頁處理的是子球顏色 HSV 校正設定檔，與外觀頁球桌風格顏色不同。
- 套用子球顏色校正設定檔時，後端會將套用狀態寫入 `runtime/color_calibration_state.json`。
- `GET /api/color-calibration/state` 會回傳上次套用的 `profile_id`、`profile_name`、`mode`、`applied_at`。
- 前端進入顏色校正頁時會讀取該 state，並自動切換到上次套用的模式與設定檔，讓 HSV 子球顏色調整在下次開啟時仍可看到。
- 回復預設模板時會清空套用的 profile 狀態並同步更新 runtime state。

### 05/07:'啟動時自動套用上次子球顏色模式'
- 後端 FastAPI `startup_event` 會呼叫 `_apply_saved_color_calibration()`。
- 若 `runtime/color_calibration_state.json` 內有有效的 `profile_id`，後端會從資料庫讀取該 profile，並立即呼叫 `tracker.apply_color_calibration(mode, mappings)`。
- 這讓系統一啟動就套用上次的子球顏色校正模式，不需要使用者重新進入顏色校正頁手動套用。
- 若 tracker 未初始化、profile id 無效或 profile 已刪除，啟動流程會略過套用並輸出 warning，不阻擋後端啟動。

### 05/07:'修正子球顏色套用後辨識標註失效'
- `tracker.apply_color_calibration()` 現在會同步重設 `COLOR_VAL_REF`，避免上次 White/Black 亮度基準殘留。
- 套用子球 HSV profile 時會跳過空白 `[0,0,0]~[0,0,0]` 與全範圍 `[0,0,0]~[180,255,255]` mapping，避免未校正完成的顏色覆蓋系統預設模板。
- 切換球桌布料顏色後會清除 `latest_analysis_data`、overlay 與 planner 快取，避免舊標註殘留。
- 若使用者選錯球桌風格，球桌偵測 fallback 成功使用其他 config preset 時，tracker 會同步更新目前桌布 HSV preset，讓後續 frame 以實際偵測成功的桌布色繼續追蹤。

### 05/07:'修正球桌 ROI fallback 過大'
- 球桌 HSV 偵測失敗時，不再直接使用整張畫面 90% 作為 fallback ROI。
- 新增 `_estimate_table_roi_from_dark_pockets()`：以黑色球袋與桌框暗區推估球桌 ROI，避免綠框下緣跑到畫面外。
- 新增 `_clamp_table_roi()`，所有 HSV 與 fallback ROI 都會限制在影像範圍內，確保四邊框線可見。
- 若暗區推估也失敗，才使用較保守的畫面 fallback，高度限制為畫面約 72%。

### 輸出格式

```json
{
  "status": "ok",
  "pid": 14836,
  "uptime_sec": 123.456,
  "log_path": "C:\\Users\\User\\Documents\\billiards-analytics-v1.5.1\\backend\\logs\\backend-runtime.log",
  "thread_count": 8,
  "camera": {
    "running": true,
    "thread_alive": true,
    "selected_device_id": 0,
    "capture_opened": true,
    "last_frame_age_ms": 33.2
  },
  "mjpeg": {
    "monitor": {
      "active_connections": 1,
      "max_connections": 10
    }
  }
}
```

### 規範用法

- 若終端出現 `Application shutdown complete` 但使用者未手動關閉，先查看 `backend/logs/backend-runtime.log` 中 `FastAPI shutdown started`、`Uvicorn run returned` 或 `Uvicorn server exited with exception` 的前後紀錄。
- 若啟動時顯示 `backend-runtime.log is locked`，改查訊息中指定的 `logs/backend-runtime-<pid>.log`。
- 若 log 出現 `error while attempting to bind on address ('0.0.0.0', 8001)` 或 `port 8001 is already in use`，代表已有另一個後端程序佔用連接埠；先用 `netstat -ano | findstr :8001` 找出 LISTENING PID，再關閉舊後端視窗或停止該程序。
- 若 `/health` 或 `/api/diagnostics/runtime` 逾時，但 `netstat` 仍顯示 `:8001` LISTENING，判定為後端程序仍存活但事件迴圈或串流處理卡住，需優先檢查 MJPEG active connections 與相機擷取執行緒狀態。

## 05/07:'隱藏設定頁底部設定入口'

### 功能說明

- 進入設定頁後，最左側 Sidebar 底部不再顯示 `設定` 按鈕。
- 設定頁只保留 Sidebar 上方的設定 Tab 導覽，避免同畫面出現兩個設定入口。
- 非設定頁仍保留底部 `設定` 按鈕與帳戶選單入口。

### 影響檔案

```text
frontend/src/components/Sidebar.tsx
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/07:'調整設定頁為 Codex 風格設定格式'

### 功能說明

- 保留設定 Tab 在最左側 Sidebar 的架構，不新增第二導覽列。
- 右側設定內容改為窄版置中排版，接近 Codex 設定頁格式。
- 每個設定 Tab 使用 `section -> panel -> row` 結構，左側顯示設定名稱與說明，右側放控制項。
- `一般` Tab 新增工作模式選項、權限開關與一般設定列表。
- 所有設定內容維持 UI-only 與本地 state 綁定，不串接後端設定 API。
- 全設定頁不使用 icon、SVG 或 icon library。

### 影響檔案

```text
frontend/src/components/pages/SettingsPage.tsx
frontend/src/components/pages/SettingsPage.css
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/07:'新增頂部品牌回首頁'

### 功能說明

- 頂部左側 `NCUT 撞球分析系統 v1.5.1` 改為可點擊品牌按鈕。
- 點擊後呼叫主版面導覽，回到 `即時影像` 主頁。
- 視覺保持原本純文字樣式，不新增 icon。

### 影響檔案

```text
frontend/src/components/TopBar.tsx
frontend/src/components/TopBar.css
frontend/src/components/Dashboard.tsx
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/07:'移除設定頁第二導覽列'

### 功能說明

- 設定頁不再於主內容區左側顯示第二組設定導覽。
- 進入設定頁後，原本最左側全域 Sidebar 的主要功能區會改為設定 Tab 導覽。
- `一般`、`外觀`、`相機`、`球桌校正`、`追蹤設定` 直接顯示在原 Sidebar。
- `進階監控` 仍只在 `isDevMode=true` 時顯示。
- AI Coach 對話清單在設定頁不顯示，避免左側同時出現兩套導覽或功能清單。

### 影響檔案

```text
frontend/src/components/Sidebar.tsx
frontend/src/components/Dashboard.tsx
frontend/src/components/Dashboard.css
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/07:'重構設定頁 Tab 與開發者模式進階監控'

### 功能說明

- 設定頁改為左右兩欄：左側設定 Tab 導覽放在原 AI Coach embedded 欄位，右側只顯示目前選中的設定內容。
- `Dashboard` 新增 `activeSettingsTab` 與 `isDevMode` 狀態。
- `進階監控` Tab 只在 `isDevMode=true` 時顯示；關閉開發者模式時若目前停在 `進階監控`，會自動切回 `一般`。
- 設定頁內容改為 UI-only 與本地 state 綁定，暫不串接後端設定 API。
- 設定頁與設定導覽不使用 icon，只用文字與表單元件。

### Tab 內容

```text
一般：版本、Backend API、WebSocket URL、顯示進階數據監控
外觀：介面主題、球桌顏色預覽、布料顏色預設集
相機：攝影機切換、重新讀取設備、Lighting Profile、進階相機參數
球桌校正：ROI 狀態、四點校正、Mask 開關、清除 ROI、顏色校正、投影機校正
追蹤設定：運算品質、儲存設定
進階監控：Session、Metadata、原始偵測資料示意
```

### 影響檔案

```text
frontend/src/components/Dashboard.tsx
frontend/src/components/Dashboard.css
frontend/src/components/pages/SettingsPage.tsx
frontend/src/components/pages/SettingsPage.css
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/07:'新增設定帳戶選單與設定頁側欄'

### 功能說明

- 左側欄底部第一個 `設定` 按鈕不再直接切頁，改為開啟帳戶選單。
- 帳戶選單由上到下只顯示：帳戶顯示名稱、`帳號管理`、`設定`、`登出`。
- 依使用者要求，帳戶選單與設定頁側欄先移除圖示，只保留文字。
- 帳戶選單中的第二個 `設定` 按鈕會切換到設定頁。
- 設定頁改為類 Codex 設定版面：左側分類欄、右側 `一般` 設定內容。
- 目前專案沒有登入帳戶資料來源，顯示名稱先使用前端常數 `NCUT 使用者`。

### 影響檔案

```text
frontend/src/components/Sidebar.tsx
frontend/src/components/Sidebar.css
frontend/src/components/pages/SettingsPage.tsx
frontend/src/components/pages/SettingsPage.css
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/07:'調整 AI Coach 左側欄位寬度'

### 功能說明

- 即時影像頁開啟 AI Coach 聊天室時，左側 embedded Coach 欄位往右延伸。
- `.main-content.with-coach` 左欄桌面寬度由 `minmax(460px, 560px)` 調整為 `minmax(540px, 660px)`。
- 1280px 以下桌面斷點左欄由 `minmax(380px, 460px)` 調整為 `minmax(460px, 560px)`。
- 目的為讓聊天室輸入列兩側留白更接近等長，符合紅線標示的視覺對齊需求。

### 影響檔案

```text
frontend/src/components/Dashboard.css
```

### 驗證

```powershell
npx.cmd tsc --noEmit
```

## 05/06:'新增 AI Coach 停止思考功能'

### 功能說明

- 玩家送出 AI Coach 訊息後，聊天室會先追加玩家訊息與 `思考中` pending 訊息。
- AI Coach 正在思考期間，原本的送出鍵會切換為方形停止按鈕 `■`，按鈕語意為 `停止思考`。
- 使用者按下停止按鈕後，前端會透過 `AbortController` 中止目前 `/api/coach/chat` 或 `/api/coach/suggest` 請求。
- 被中止的 pending 訊息不會移除，會在聊天室中改為 `已停止思考`，避免使用者誤以為訊息遺失。
- 停止後會清除 sending/suggesting 狀態，輸入框恢復可用，錯誤區不顯示取消錯誤。

### 範例流程

```text
玩家送出問題
-> AI Coach 顯示「思考中....」
-> 送出鍵切換成「■」停止按鈕
-> 使用者按下停止
-> fetch abort
-> pending 訊息改為「已停止思考」
```

### 影響檔案

```text
frontend/src/components/AICoachFloatingChat.tsx
frontend/src/components/AICoachFloatingChat.css
```

### 驗證

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
.\.venv\Scripts\python.exe -m py_compile backend\main.py backend\config.py backend\tracking\tracking_engine.py
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
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
.\.venv\Scripts\python.exe -m pytest backend\test-program\test_coach_payload_builder.py backend\test-program\tracking\test_route_planner.py -q
npx.cmd tsc --noEmit
npm.cmd run build
```

## 05/03:'legacy 四點 ROI API 與 roi_manager 已移除'

此段原本記錄舊版 `/api/roi/*`、`roi_manager.py`、`roi_config.json`、`ROI_MASK_ENABLED` 與 `ROI_CONFIG_PATH` 使用方式。這些項目已在 05/07 cleanup 移除，不再是有效 API 或設定。

目前球桌 ROI 僅保留 HSV table ROI 與微調 API：

```http
GET  /api/table/roi-adjustment
POST /api/table/roi-adjustment
POST /api/table/roi-adjustment/reset
```

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

### 05/10:'修正顏色校正 Auto Scan HSV 取樣'
- `GET /api/color-calibration/auto-scan?mode=pool|snooker` 新增可選參數 `target_color`，例如 `target_color=Yellow`。後端會針對目前要校正的系統顏色計算 `target_score`，多顆球同時在畫面中時優先回傳最符合目標顏色的 ROI。
- 彩球 HSV 擷取改為優先分析高飽和、非高光、非陰影像素，再以 K-Means 群集分數挑選主色；分數會同時考慮像素數、飽和度、亮度與目標 Hue 接近程度，避免白色號碼區、高光或桌布殘留被誤判成主色。
- 彩球 `target_score` 對低飽和 ROI 採硬性降權；因目前 YOLO 原始 label 只有 `color ball`、`cue`、`white ball`，Auto Scan 會先做硬過濾：彩球校正只接受 `color ball` 類別，排除 `white ball` 與 `cue`；White 校正只接受 `white ball`。若偵測資料含 `number`，例如 Yellow 的 `1/9`，則會再加權優先選擇該球。
- Auto Scan 會讀取 `balls` 中的彩球與 `white_ball` 中的白球，並支援 `color`/`label`/`ball_color` 欄位判斷。若 YOLO 座標來源解析度與 raw frame 不一致，會依 `_source_img_w/_source_img_h` 或 `img_w/img_h` 自動縮放 ROI，避免裁切到錯誤位置。
- 若球桌 HSV mask 過寬導致 ROI 內所有像素都被視為桌布，Auto Scan 會保留原始圓形 ROI 取樣，不再直接回傳 `No valid ball ROI from current YOLO result`。
- 黑球與白球使用獨立規則：白球以低飽和高亮度像素建立 `[0,0,V] ~ [180,S,255]`；黑球以低亮度像素建立 `[0,S,0] ~ [180,S,V]`。這可避免黑白球被一般彩球 Hue 規則干擾。
- 輸出格式新增 `target_color`、每顆掃描項目的 `target_score` 與 `sample_pixels`：
```json
{
  "status": "success",
  "mode": "pool",
  "target_color": "Yellow",
  "scans": [
    {
      "hsv_center": [30, 180, 190],
      "hsv_lower": [22, 140, 150],
      "hsv_upper": [38, 230, 230],
      "target_score": 0.94,
      "sample_pixels": 86
    }
  ]
}
```
- 前端 `ColorCalibrationPage` 的「掃描目前球體 (Auto Scan)」會傳入目前步驟顏色，並在回傳多筆掃描結果時選擇 `target_score` 最高者，同時顯示匹配分數供使用者判斷。

### 05/10:'修正球號 9/1 與 4/2 跳號'
- 9 號與 1 號同為 Yellow，球號差異依賴 `style=Stripe|Solid`。追蹤端已加強 Yellow 的白帶判斷：當白色比例、中心白區或外圈白區顯示條紋特徵時優先判定 `Stripe`；若 Yellow 有白帶但 Solid 證據不足，改回 `Unknown`，再由既有規則保守映射到 9，避免硬判成 1。
- 4 號 Purple 與 2 號 Blue 在低光源下 Hue/LAB 容易接近。主色分類新增 Blue/Purple 邊界保護：若 K-Means 主色 Hue 已進入紫色區且 Purple 分數接近 Blue，輸出 Purple；反向在 Hue 明顯偏藍時才保留 Blue。
- 針對仍偶發的 4/2 跳號，新增跨幀 `label_lock`：同一位置的球一旦穩定為 Purple 或 Blue，另一個 label 必須連續多幀且分類信號夠強才允許切換，避免單幀光線或反光造成號碼閃爍。
- 幾何平滑不再因同位置球號短暫不同就中斷快取；同色系號碼或中心距離很近的球會沿用同一幾何歷史，減少跳號造成的 tracking reset。
- 驗證命令：
```bash
python -m py_compile backend/tracking/tracking_engine.py
python -m pytest backend/test-program/tracking/test_tracking.py
```

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

### 05/07:'新增 WebSocket session 還原防呆與同源連線預設'
- 功能：
  - 前端 SDK 還原 `localStorage` session 時，會檢查 `billiards_session_id` 與 `billiards_session.session_id` 是否一致。
  - 若 session 過期、格式錯誤、續期失敗或後端已重啟導致 session 不存在，會清除舊 session 並建立新 session，避免 `/ws/control` 因 `Invalid session_id` 反覆關閉。
  - 未設定 `VITE_BACKEND_URL` 時，REST API 預設走同源路徑，例如 `/api/sessions`。
  - 未設定 `VITE_BACKEND_WS` 時，WebSocket 會依目前頁面來源自動組成 `ws://host` 或 `wss://host`，並透過 Vite `/ws` proxy 連到後端。
- 規範用法：
  - 本機 Vite 開發模式可不設定前端 `.env`，直接使用同源 proxy。
  - 若前後端部署在不同網域，才設定：
    ```env
    VITE_BACKEND_URL=http://127.0.0.1:8001
    VITE_BACKEND_WS=ws://127.0.0.1:8001
    ```
  - session 建立流程仍維持：
    ```http
    POST /api/sessions
    ```
  - WebSocket 連線仍維持：
    ```text
    /ws/control?session_id={session_id}
    ```
- 輸出格式：
  - `POST /api/sessions`
    ```json
    {
      "session_id": "s-xxxxxxxxxxxx",
      "stream_id": "camera1",
      "ws_url": "/ws/control?session_id=s-xxxxxxxxxxxx",
      "burnin_url": "/burnin/camera1.mjpg",
      "expires_at": 1778172493947
    }
    ```
  - WebSocket 首包：
    ```json
    {
      "v": 1,
      "type": "protocol.welcome",
      "session_id": "s-xxxxxxxxxxxx",
      "stream_id": "camera1",
      "payload": {
        "version": "1.5.0",
        "features": ["heartbeat", "metadata", "commands", "stream_switch"]
      }
    }
    ```

### 05/08: '新增 Q Track 前端 Mock 使用者認證系統'

**功能說明**:
- 前端新增 Q Track 認證閘門，未登入時先顯示歡迎頁、登入、註冊與找回密碼四個介面，通過後才掛載既有 `Dashboard` 主程式。
- 使用 `AuthMode = 'welcome' | 'login' | 'register' | 'forgot'` 管理畫面切換，不新增前端路由。
- 訪客模式只建立前端 session 狀態並直接進入主程式，不寫入 Mock 使用者資料。

**驗證規範**:
- 使用者名稱、密碼與新密碼統一使用 Regex `/^[a-zA-Z0-9_]+$/` 驗證。
- 註冊名稱重複時顯示「名稱已被使用」。
- 輸入非法字元時顯示「格式錯誤，僅允許英文字母、數字、與下底線 (_)」。
- 註冊與改密碼流程都會驗證確認密碼是否一致。

**Mock Data 與儲存格式**:
- Mock 使用者資料以 `localStorage` key `qtrack_mock_users` 保存，仍屬開發與展示用資料，不呼叫後端 API、不加密密碼。
- 資料結構:
  ```json
  [
    {
      "username": "QTrack_User",
      "password": "QTrack_123",
      "securityQuestion": "你最喜歡的球星？",
      "securityAnswer": "Efren"
    }
  ]
  ```

**找回密碼流程**:
- 使用者先輸入名稱，系統查到帳號後顯示該帳號的安全問題。
- 安全答案以 `trim()` 後比對，大小寫敏感。
- 答案正確後才顯示「新密碼」與「確認新密碼」欄位。
- 更新成功後導回登入頁，使用者可用新密碼登入。

**前端檔案**:
- `frontend/src/App.tsx`
- `frontend/src/components/AuthScreens.tsx`
- `frontend/src/components/AuthScreens.css`

### 05/08: '新增 Q Track 訪客與帳戶顯示狀態'

**功能說明**:
- `App` 會保留目前認證 session，並將帳戶狀態傳入 `Dashboard` 與 `Sidebar`。
- 使用「以訪客身分進入」時，帳戶選單顯示名稱為「訪客」。
- 訪客狀態下，帳戶選單最後一個按鈕顯示「登入」，點擊後離開主程式並直接開啟登入頁。
- 一般使用者登入後，帳戶選單顯示 `@使用者名稱`，最後一個按鈕顯示「登出」，點擊後回到歡迎頁。

**規範用法**:
- 訪客 session 不寫入 Mock 使用者資料，只用於前端通過認證閘門。
- 使用者顯示名稱由 `authSession.type` 決定：`guest` 顯示「訪客」，`user` 顯示 `@${username}`。
- `AuthScreens` 支援 `initialMode`，讓主程式中的「登入」按鈕可直接導到登入介面。

### 05/08: '修正左側欄顯示文字亂碼'

**功能說明**:
- 修正 `Sidebar` 中殘留的亂碼標籤，左側主選單改為「即時影像、回放紀錄、練習模式、遊戲模式」。
- 設定子選單維持可讀繁體中文：「一般、外觀、相機、球桌校正、追蹤設定」。
- AI Coach 區塊與帳戶選單改為可讀文字：「對話、尚無對話、新增對話、重新命名、置頂、刪除對話、帳號管理、設定、返回主畫面」。

**驗證**:
- `node_modules\\.bin\\tsc.cmd --noEmit`
- `npm.cmd run build`

### 05/08: '新增 Q Track 帳號管理分頁'

**功能說明**:
- 新增 `AccountManagementPage`，沿用設定頁 `settings-page`、`settings-section`、`settings-panel`、`settings-row` 版面配置。
- 帳戶選單中的「帳號管理」會切換至帳號管理分頁。
- 訪客進入帳號管理時顯示登入提示與「前往登入」按鈕，不提供資料修改。
- 登入使用者可修改名稱、密碼與安全問題，並顯示最近 3 筆 Mock 登入紀錄。

**Mock Data 規格**:
- 共用帳戶資料工具位於 `frontend/src/auth/mockAccountStore.ts`。
- localStorage key 維持 `qtrack_mock_users`。
- 既有使用者資料讀取時會自動補上穩定 `userId`，格式為 `CUE-XXXXXX`。
- 使用者資料格式:
  ```json
  {
    "username": "QTrack_User",
    "password": "QTrack_123",
    "securityQuestion": "你最喜歡的球星？",
    "securityAnswer": "Efren",
    "userId": "CUE-7B1D90"
  }
  ```

**操作規則**:
- 使用者名稱與密碼都必須符合 `/^[a-zA-Z0-9_]+$/`。
- 修改名稱會檢查重複名稱；重複時顯示「名稱已被使用」。
- 修改名稱成功後會同步更新目前 `authSession.username`，側欄立即顯示新的 `@使用者名稱`。
- 修改密碼需先輸入正確舊密碼，且新密碼與確認新密碼一致。
- 更新安全問題需先輸入目前安全答案；答案以 `trim()` 後比對，大小寫敏感。
- 頭像上傳目前只觸發 UI，暫不保存圖片。

**驗證**:
- `node_modules\\.bin\\tsc.cmd --noEmit`
- `npm.cmd run build`

### 05/08: '新增 Q Track 刪除帳號功能'

**功能說明**:
- 帳號管理頁新增「刪除帳號」危險操作區塊，使用水平線與上方個人設定區隔。
- 刪除按鈕使用 `settings-button danger` 樣式，文字為「刪除帳號」。
- 點擊後開啟 Modal，顯示不可恢復警語：
  「確定要刪除帳號嗎？一旦刪除，您的個人設定、慣用手偏好及所有歷史數據將會永久消失，無法恢復。」
- Modal 內需輸入當前密碼；密碼正確前「確認刪除」按鈕不可點擊。

**刪除流程**:
- 使用者點擊「確認刪除」後，Modal 會切換為「正在刪除帳號...」狀態。
- Loading 狀態維持 2.5 秒，並顯示三點波浪狀動畫。
- Loading 結束後才執行資料移除：
  1. 從 `qtrack_mock_users` 移除目前 `currentUser.userId` 對應使用者。
  2. 清除 `billiards_session_id`。
  3. 清除 `billiards_session`。
  4. 清除目前 `authSession`，並將認證入口重設為歡迎頁。
- 刪除後畫面回到「歡迎使用Q Track」首頁。

**驗證**:
- `node_modules\\.bin\\tsc.cmd --noEmit`
- `npm.cmd run build`

### 05/08: '新增 Q Track 開始探索前導頁'

**功能說明**:
- 在既有歡迎、登入、註冊與找回密碼流程之前新增 `ExploreScreen`。
- 前導頁顯示 `Q Track`、`BILLIARDS ANALYSIS SYSTEM` 與「開始探索」按鈕。
- 點擊「開始探索」後才進入既有 `AuthScreens` 的「歡迎使用Q Track」介面。
- 前導頁由 `App` 的 `hasExplored` 狀態控制；重新整理頁面會重新顯示，登入、登出或刪除帳號後不會在同一次分頁生命週期內重複顯示。

**UI 規範**:
- 不使用 Icon、不引入圖片檔。
- 背景以 CSS radial-gradient、linear-gradient 與 repeating-radial-gradient 模擬深色科技感弧線與點陣。
- 桌面與手機都需保持中央標題、系統副標與按鈕不重疊。

**前端檔案**:
- `frontend/src/components/ExploreScreen.tsx`
- `frontend/src/components/ExploreScreen.css`
- `frontend/src/App.tsx`

**驗證**:
- `node_modules\\.bin\\tsc.cmd --noEmit`
- `npm.cmd run build`

### 05/08: '新增登入藍色流水線載入狀態'

**功能說明**:
- 登入表單在帳號密碼驗證成功後，不會立即進入主程式，而是先進入 2.5 秒載入狀態。
- 載入期間登入框上方會顯示藍色流水線動畫。
- 載入期間停用返回、使用者名稱、密碼、登入與忘記密碼操作，避免重複提交。
- 帳號或密碼錯誤時仍立即顯示錯誤，不進入載入狀態。

**驗證**:
- `node_modules\\.bin\\tsc.cmd --noEmit`
- `npm.cmd run build`
### 05/11: '調整註冊介面為三步驟視窗流程'

**功能說明**:
- `AuthScreens` 的註冊模式改為三段式流程：先設定使用者名稱，再設定密碼與確認密碼，最後設定安全問題與答案。
- 每個步驟只顯示當前必要欄位，避免一次顯示所有註冊欄位造成畫面負擔。
- 左上返回鍵在註冊流程中會優先返回上一個註冊步驟；在第一步時才返回歡迎頁。
- 最後一步仍沿用既有 `registerAccount` API，一次送出 `username`、`password`、`security_question`、`security_answer`。

**流程規範**:
1. 使用者名稱步驟需通過 `validateUsernameFormat()`，合法後才進入密碼步驟。
2. 密碼步驟需通過 `validatePasswordFormat()` 並確認兩次密碼相同，合法後才進入安全問題步驟。
3. 安全問題步驟需輸入答案，答案會先 `trim()` 再送出註冊。

**輸出格式**:
```json
{
  "username": "Lucian039_",
  "password": "Lucian0399",
  "security_question": "你最嚮往或最喜歡去旅行的一個國家？",
  "security_answer": "澳洲"
}
```

**驗證**:
- `npm.cmd run build`
- Playwright 本機瀏覽器檢查：註冊新帳號 -> 使用者名稱 -> 密碼 -> 安全問題，並確認安全問題頁返回後會回到密碼頁。

### 05/11: '新增帳號服務未啟用錯誤提示'

**功能說明**:
- 前端帳號 API 若遇到連線失敗或路由不存在，會統一顯示「帳號服務尚未啟用，請重啟後端後再試」。
- 適用註冊、登入、忘記密碼與帳號管理相關操作，避免只顯示「請求失敗」而無法判斷原因。
- 此情境常見於前端連到舊版後端，舊後端未載入 `/api/auth/*` router。

**錯誤碼規範**:
```text
CONNECTION_FAILED -> auth.errorAuthServiceUnavailable
API_NOT_FOUND     -> auth.errorAuthServiceUnavailable
```

**驗證**:
- `npm.cmd run build`
- 重啟目前專案後端後，透過 `POST /api/auth/register` 與前端三步驟 UI 註冊皆可成功建立帳號。

### 05/11: '調整註冊完成後回到登入介面'

**功能說明**:
- 註冊 API 成功後不再直接建立前端登入 session，也不直接跳轉進主系統。
- 成功後清空註冊表單，回到登入介面，並顯示「註冊完成，請登入新帳號」。
- 登入頁會預填剛註冊的使用者名稱，密碼欄位保持空白，由使用者自行登入。

**流程規範**:
1. 註冊三步驟完成後送出 `POST /api/auth/register`。
2. API 成功時只視為帳號建立成功，不使用回傳 token 呼叫 `onAuthenticated()`。
3. 使用者必須在登入介面輸入密碼並通過 `POST /api/auth/login` 後，才可進入系統。

**驗證**:
- `npm.cmd run build`

### 05/11: '恢復登入成功 2.5 秒流水線'

**功能說明**:
- 登入帳密驗證成功後，登入面板維持 `is-login-loading` 狀態 2.5 秒，再進入主系統。
- 載入期間保留面板上方流水線動畫，並停用返回、輸入欄位、登入與忘記密碼操作。
- 登入失敗時不等待 2.5 秒，立即顯示錯誤訊息並恢復操作。

**規範用法**:
```ts
const LOGIN_SUCCESS_LOADING_MS = 2500;
```

**驗證**:
- `npm.cmd run build`

### 05/11: '新增登入帳號選擇卡片'

**功能說明**:
- 按下「登入現有帳號」後，先顯示登入過的帳號清單，不直接顯示帳號密碼表單。
- 點選登入過的帳號後進入密碼介面，只顯示所選帳號與密碼欄位，不再要求輸入使用者名稱。
- 「使用其他帳號」會先顯示使用者名稱欄位，驗證格式後再進入密碼介面。
- 「移除帳號」只會從本機登入清單移除該帳號，不會呼叫刪除帳號 API，也不會刪除後端帳號。
- 登入成功後，帳號會寫入本機登入清單並置頂，最多保留 5 筆。

**本機儲存格式**:
```json
{
  "qtrack_recent_login_accounts": ["Player001", "Lucian039_"]
}
```

**流程規範**:
1. `登入現有帳號` -> 帳號選擇卡片。
2. 點選既有帳號 -> 密碼卡片 -> `POST /api/auth/login`。
3. 點選 `使用其他帳號` -> 使用者名稱卡片 -> 密碼卡片 -> `POST /api/auth/login`。
4. 點選 `移除帳號` -> 移除本機清單項目，不影響後端資料。

**驗證**:
- `npm.cmd run build`
- Playwright 本機瀏覽器檢查：帳號清單、既有帳號密碼登入、使用其他帳號、移除清單項目、登入成功後清單置頂。

### 05/11: '新增顯示密碼勾選'

**功能說明**:
- 登入密碼欄位下方新增「顯示密碼」勾選。
- 註冊密碼步驟在密碼與確認密碼欄位下方新增「顯示密碼」勾選，勾選後兩個欄位同步顯示明文。
- 忘記密碼的重設密碼區也使用相同顯示密碼規則。

**規範用法**:
```text
未勾選: input type="password"
已勾選: input type="text"
```

**驗證**:
- `npm.cmd run build`
- Playwright 本機瀏覽器檢查：登入密碼、註冊密碼、註冊確認密碼勾選後皆由 `password` 切換為 `text`。

### 05/11: '整合球色與投影設定入口'

**功能說明**:
- 設定頁「球桌校正」中的區塊名稱改為「球色與投影」，並拆成「球色」與「投影」兩個子區。
- 「球色」子區直接提供模式下拉選單，支援 `pool`（花式撞球）與 `snooker`（斯諾克），預設使用 `pool`。
- 設定檔列表沿用 `GET /api/color-calibration/profiles?mode=pool|snooker`，後端排序維持 `updated_at DESC, id DESC`，越新的設定檔越上方。
- 無設定檔時顯示「還沒有任何設定檔」；下方「新增設定檔」會呼叫 `POST /api/color-calibration/profiles`，Body 範例：`{ "mode": "pool", "name": "20260511" }`。
- 設定檔列右側「編輯」會帶入 `profile_id` 開啟既有 YOLO 自動掃描頁；該頁不再作為設定檔選擇入口，只保留 HSV 掃描、儲存與套用流程。
- 「投影」子區保留原投影機校正按鈕，仍導向既有投影機校正流程；本次不新增後端 API 或資料庫欄位。

**驗證**:
- `npm.cmd run build`

### 05/11: '修正球色校正設定整合細節'

**功能說明**:
- 設定頁區塊標題由「球色與投影」調整為「球色校正」，並移除卡片內多餘的「球色」子標題。
- 「模式」與「設定檔列表」拆成兩張獨立設定卡；模式卡右側使用下拉選單，設定檔列表卡保留新增與編輯入口。
- AI Coach 入口與嵌入聊天只允許在即時影像、練習模式、遊玩模式使用；進入設定、校正、回放與帳號相關頁面會自動收起。
- 球色 YOLO 掃描頁的返回按鈕不再回到已廢棄的設定檔選擇頁，而是直接回到設定頁。

**驗證**:
- `npm.cmd run build`

### 05/11: '球色校正改為設定頁 Modal 編輯'

**功能說明**:
- 設定檔列表的「編輯」不再切換到獨立 `ColorCalibrationPage`，改為在設定頁開啟背景虛化的球色校正 Modal。
- Modal 標題顯示模式與設定檔名稱，例如 `花式撞球 20260423`；左側為相機預覽與全部 HSV 總覽，右側為掃描操作區。
- 進度條移到右上角，顯示目前步驟與目標顏色；主操作按鈕初始為「掃描目前球體」，掃描成功後切換為「確認無誤，前往下一個顏色」。
- 「回上一顆」與「跳過此顏色」固定放在主按鈕下方；HSV Lower / Upper 調整收進「進階 HSV 參數調整」展開區。
- Modal 底部提供「關閉」與「儲存並退出」；若有未儲存 HSV 或步驟變更，關閉前會提示「你尚未儲存任何變更，確定要退出嗎?」。
- 儲存仍沿用 `PUT /api/color-calibration/profiles/{profile_id}/mappings`，不新增後端 API 或資料庫欄位。

**驗證**:
- `npm.cmd run build`

### 05/11: '新增球色校正設定子頁'

**功能說明**:
- 設定檔列表的「編輯」改為切換右側設定內容區，不再使用背景虛化 Modal、新視窗或 `aria-modal` 對話框。
- 球色校正子頁寬度與即時影像一致為 `960px`，採上方狀態列、中間相機參考畫面、下方操作控制區的工作台排版。
- 相機參考畫面沿用 burn-in MJPEG，使用 `quality=med&client_id=color-calibration-editor`，影像區固定 `aspect-ratio: 16 / 9`、黑底、`object-fit: contain`。
- 操作控制區單欄排列，依序顯示目前目標顏色與 ROI HSV、掃描/下一顆/上一顆/跳過操作、進階 HSV Lower/Upper 編輯。
- 底部保留「關閉」與「儲存並退出」；未儲存關閉會提示確認，儲存仍沿用 `PUT /api/color-calibration/profiles/{profile_id}/mappings`。

**輸出格式**:
```json
{
  "mappings": {
    "yellow": {
      "actual_label": "",
      "hsv_lower": [20, 80, 80],
      "hsv_upper": [35, 255, 255]
    }
  }
}
```

**驗證**:
- `npm.cmd run build`

### 05/25: '球色校正設定檔下拉選單與套用流程'

**功能說明**:
- 設定頁「球桌校正 > 球色校正」的設定檔列表改為單一下拉選單，依目前模式列出 `pool/snooker` 的設定檔。
- 下拉選單下方固定顯示「套用」與「編輯」；「套用」會套用目前選中的設定檔，「編輯」會開啟目前選中的設定檔編輯子頁。
- 無設定檔時顯示既有空狀態，並停用「套用」與「編輯」。
- 新增設定檔成功後，前端會自動選取新建立的設定檔；切換模式時會重新載入對應模式清單並預選第一筆。

**規範用法**:
- 套用設定檔沿用既有 API，不新增後端欄位或資料表：

```http
POST /api/color-calibration/apply
Content-Type: application/json
```

**輸出格式**:
```json
{
  "profile_id": 123
}
```

**驗證**:
- `npm.cmd run build`
- 有多個設定檔時，確認下拉選單可切換選取。
- 按「套用」後確認後端套用目前選中的 `profile_id`。
- 按「編輯」後確認進入目前選中的設定檔編輯子頁。
- 無設定檔時確認「套用」與「編輯」停用，且不送出 API 請求。

### 05/12: '新增啟動腳本後端健康檢查等待'

**功能說明**:
- `start.bat` 啟動 FastAPI 後端後，會輪詢 `http://127.0.0.1:8001/health`，最多等待 60 秒。
- 後端健康檢查成功後才啟動 Vite 前端，避免前端在後端尚未綁定 `8001` 時發出 `/api/auth/me` 或 `/ws` 請求造成 `ECONNREFUSED 127.0.0.1:8001`。
- 若 60 秒內後端未就緒，腳本會停止啟動流程並提示檢查 Backend Server 視窗。
- 前端啟動訊息同步修正為 Vite 設定的 `http://localhost:3000`。

**規範用法**:
```bat
start.bat
```

**健康檢查範例**:
```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

**預期輸出格式**:
```json
{
  "status": "ok",
  "version": "1.5.0",
  "pid": 3704,
  "uptime_sec": 74.292,
  "is_analyzing": false,
  "active_sessions": 0
}
```

### 06/05: '更新登入前品牌文案為 CueVex'

**功能說明**:
- 登入前第一屏大標題由 `Q Track` 改為 `CueVex`。
- 點擊「開始探索」後的認證歡迎頁 kicker 與歡迎標題同步改為 `CueVex`。
- 帳號管理頁的個人檔案說明同步使用 CueVex 品牌名稱，避免登入流程與主程式頂部品牌不一致。

**規範用法**:
- 第一屏品牌文案位於 `frontend/src/components/ExploreScreen.tsx`。
- 認證歡迎頁品牌文案位於 `frontend/src/components/AuthScreens.tsx` 與 `frontend/src/i18n/locales/*`。
- 多語系需同步維護 `zh-TW`、`zh-CN`、`en-US` 的 `auth.welcomeTitle` 與帳號說明字串。

**輸出格式**:
```tsx
<h1 id="explore-title">CueVex</h1>
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 重新整理 `http://127.0.0.1:3000/`，確認第一屏顯示 `CueVex`。
- 點擊「開始探索」，確認認證歡迎頁顯示 `CueVex` 與 `歡迎使用 CueVex`。

### 06/05: '同步開始探索頁與登入頁背景按鈕風格'

**功能說明**:
- 開始探索頁背景改用登入頁相同的深色背景：頂部淡光 radial gradient 搭配 `#111111`。
- 移除開始探索頁原本的額外圓環與粒線裝飾，讓進入認證頁前後視覺一致。
- 「開始探索」按鈕改為登入頁按鈕風格：深色底、`#303030` 邊框、7px 圓角、42px 最小高度。

**規範用法**:
- 開始探索頁樣式維護於 `frontend/src/components/ExploreScreen.css`。
- 登入頁樣式維護於 `frontend/src/components/AuthScreens.css`。
- 兩頁背景與主要按鈕視覺應保持一致；若日後調整登入頁背景，需同步檢查開始探索頁。

**輸出格式**:
```css
background:
  radial-gradient(circle at top, rgba(255, 255, 255, 0.08), transparent 34%),
  #111111;
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 重新整理 `http://127.0.0.1:3000/`，確認開始探索頁背景與點擊後的登入頁一致。
- 確認「開始探索」按鈕高度、邊框、圓角與 hover 風格接近登入頁按鈕。

### 06/05: '移除玩家選擇頁返回按鈕'

**功能說明**:
- 個人統計分析的「選擇玩家」頁不再顯示頁首 `← 返回` 按鈕。
- 頂部導覽列仍可切換到監控、訓練、遊戲、歷史等主頁，不影響主導覽流程。

**規範用法**:
- `PlayerSelectionPage` 只保留 `onSelectPlayer` 行為，不再接收或渲染 `onBack`。
- 其他回放列表、播放器與統計詳情頁的返回按鈕維持原樣。

**輸出格式**:
```tsx
<PlayerSelectionPage onSelectPlayer={handleSelectPlayer} />
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入頂部「分析」頁，確認「選擇玩家」標題左側不再顯示 `← 返回`。

### 06/05: '玩家選擇頁卡片隨可視寬度伸縮'

**功能說明**:
- 個人統計分析的「選擇玩家」頁改為吃滿主內容可視寬度。
- 搜尋框移除 `500px` 最大寬限制，改為隨內容區水平伸縮。
- 玩家卡片網格改用 `auto-fit` 與 `minmax(min(100%, 420px), 1fr)`，卡片會依可用寬度自動放大或換欄。

**規範用法**:
- 版面規則集中於 `frontend/src/components/pages/replay/PlayerSelectionPage.css`。
- `.player-selection-page` 保持 `width: 100%` 與 `max-width: none`，避免被主內容 flex 置中壓成窄欄。
- `.player-card` 保持 `width: 100%`，由 grid track 控制實際寬度。

**輸出格式**:
```css
grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入頂部「分析」頁，確認搜尋框與玩家卡片會隨主內容可視寬度水平放大。
- 縮窄視窗時，確認卡片可自然縮成單欄且不產生水平溢出。

### 06/05: '統一分析玩家選擇頁與好友對戰建立頁風格'

**功能說明**:
- 個人統計分析的「選擇玩家」頁改用 `friend-match-page`、`friend-match-panel`、`friend-setup-section`、`friend-player-card` 與 `friend-status-pill` 的視覺語言。
- 搜尋區與玩家列表拆成 numbered section，與 `遊戲 > 建立好友對戰` 的段落節奏一致。
- 玩家卡片保留橫向自適應，桌面以玩家資訊、統計 pill 與箭頭呈現；窄版會改為單欄堆疊。
- 舊版灰色 `#333333` 卡片與白色邊框 hover 樣式已移除。
- 分析、訓練、遊戲、歷史四個主入口頁的內容定位統一以訓練中心為基準：`width: min(100%, 1320px)`、`padding: 20px`、`max-width: 1400px`、`margin: 0 auto`。

**規範用法**:
- 分析玩家選擇頁若新增篩選或排序控制，應放在 `player-search-section` 內，並沿用 `friend-segment-row` 或 `friend-inline-input`。
- 玩家摘要統計應使用 `friend-status-pill`，避免自行新增另一套統計卡片樣式。
- 主入口頁標題區不應額外加 `padding-top`；若需要調整垂直位置，需同步檢查訓練中心、分析、遊戲與歷史四頁。

**輸出格式**:
```tsx
<div className="player-selection-page friend-match-page">
  <div className="friend-match-panel player-selection-panel">
    <section className="friend-setup-section player-list-section">...</section>
  </div>
</div>
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 點擊頂部「分析」，確認「選擇玩家」頁的標題、搜尋、玩家卡片與統計 pill 風格與「遊戲 > 建立好友對戰」一致。
- 切換頂部「分析 / 訓練 / 遊戲 / 歷史」，確認四頁主標題左上起點與訓練中心一致。

### 06/05: '統一分析玩家統計內頁與好友對戰建立頁風格'

**功能說明**:
- 個人統計分析點選玩家後的內頁改用 `friend-match-page`、`friend-match-panel`、`friend-setup-section` 與 `friend-status-pill` 的視覺語言。
- 頁首返回按鈕改為 `friend-back-button`，時間範圍切換改為 `friend-segment-row`。
- 對戰統計、練習總數、近期練習紀錄與匯出功能改成 numbered section，與分析玩家選擇頁和好友對戰建立頁一致。
- 舊版灰色統計卡、白色 hover 邊框與未使用排行表格樣式已移除。

**規範用法**:
- 統計摘要數字使用 `friend-status-pill`，勝率進度條只作為 pill 內輔助資訊。
- 近期練習紀錄使用 `.practice-item` 列表，不新增獨立卡片主題。
- 匯出按鈕沿用 `friend-segment-row` 的按鈕風格。

**輸出格式**:
```tsx
<div className="stats-page friend-match-page">
  <div className="friend-match-panel stats-panel">
    <section className="friend-setup-section stats-section">...</section>
  </div>
</div>
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 點擊頂部「分析」並選擇玩家，確認內頁標題、時間範圍、統計、練習紀錄與匯出區風格一致。

### 06/05: '移除回放入口頁個人統計分析卡片'

**功能說明**:
- 頂部「歷史」進入的回放功能入口頁不再顯示「個人統計分析」卡片。
- 回放入口頁只保留「遊玩模式」與「練習模式」兩個錄影回放入口。
- 頂部「分析」導覽仍直接進入玩家選擇與個人統計流程，不移除統計功能本身。

**規範用法**:
- `ReplayEntryPage` 的 `onNavigate` 僅支援 `game` 與 `practice`。
- 個人統計流程由 `Dashboard.handleOpenAnalysisPage()` 控制，避免同一入口同時出現在「歷史」與「分析」兩處。

**輸出格式**:
```ts
onNavigate?: (page: 'game' | 'practice') => void;
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 點擊頂部「歷史」，確認回放入口頁不再出現「個人統計分析」卡片。
- 點擊頂部「分析」，確認仍可進入「選擇玩家」頁。

### 06/05: '回放入口頁卡片隨可視寬度伸縮'

**功能說明**:
- 頂部「歷史」的回放入口頁改為吃滿主內容可視寬度。
- 入口卡片移除固定窄欄置中效果，改由 grid 欄位依可用寬度自動放大或換欄。
- 區段標題分隔線保持跨滿整個 grid，避免與入口卡片混排時只佔單欄。
- 回放入口頁收斂為 1040px 內容寬度，並使用與「練習模式 - 準度訓練」一致的 `friend-setup-section` 與 `var(--color-surface-active)` 卡片底色。
- 「回放記錄」區段標題與入口卡片需保留足夠垂直間距，避免標題貼近第一列卡片。

**規範用法**:
- 版面規則集中於 `frontend/src/components/pages/replay/ReplayEntryPage.css`。
- `.replay-entry-page` 保持 `width: min(100%, 1040px)`，與回放列表和練習設定頁的內容寬度一致。
- `.entry-card` 保持 `width: 100%`，由 `.replay-entry-content` 的 grid track 控制實際寬度。
- 入口卡片不使用額外圓形模式標記，避免和回放列表頁風格不一致。

**輸出格式**:
```css
.replay-entry-content {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
}
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 點擊頂部「歷史」，確認「遊玩模式」與「練習模式」卡片會隨主內容可視寬度水平放大。
- 縮窄視窗時，確認入口卡片可自然縮成單欄且不產生水平溢出。
- 確認回放入口頁的寬度、卡片底色與 hover 效果和回放列表頁保持一致。
- 確認「回放記錄」標題下方有清楚間距，入口卡片左側不顯示「遊」或「練」圓圈。

### 06/05: '修復回放列表返回與刪除按鈕版面'

**功能說明**:
- 回放列表內頁的返回按鈕改用專用 `.replay-back-button` 樣式，讓「← 返回」維持單行顯示。
- 回放卡片內部改為垂直排列，縮圖、資訊與操作列依序堆疊，避免刪除按鈕被卡片欄位擠壓或截斷。
- 播放與刪除按鈕保留原本操作流程，只調整按鈕尺寸、排列與可視狀態。
- 回放列表頁對齊「練習模式 - 準度訓練」設定頁風格，使用 1040px 內容寬度、圓形返回箭頭、`friend-setup-section` 區塊與 `var(--color-surface-active)` 卡片底色。

**規範用法**:
- 版面規則集中於 `frontend/src/components/pages/replay/ReplayListPage.css`。
- 回放列表返回按鈕需同時保留 `friend-back-button replay-back-button`，文字放入 `.replay-back-button-text` 供語意保留但畫面隱藏，視覺維持練習設定頁的圓形返回按鈕。
- `.recording-card` 使用 `flex-direction: column`，操作列使用 `.recording-actions` 控制播放與刪除按鈕寬度。

**輸出格式**:
```tsx
<button className="friend-back-button replay-back-button">
  ← <span className="replay-back-button-text">返回</span>
</button>
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入「歷史」->「遊玩模式回放」，確認返回按鈕不換行。
- 確認每張回放卡片底部同時完整顯示「播放」與「刪除」按鈕。

### 06/05: '遊玩與練習回放列表改為統計分析式版面'

**功能說明**:
- `ReplayListPage` 的遊玩模式與練習模式共用新版統計分析式版面。
- 頁首新增說明文字，列表內容拆成 `統計概覽`、`篩選與排序`、`回放記錄` 三個 numbered section，對齊玩家個人統計分析頁的資訊層級。
- 回放記錄由原本縮圖格狀卡片改為列式記錄卡：左側縮圖、中間標題與資訊 pill、右側播放與刪除操作。
- 遊玩模式顯示對戰雙方、勝者或比分、時長與日期；練習模式顯示練習類型、玩家、時長與日期。

**規範用法**:
- 版面結構維護於 `frontend/src/components/pages/replay/ReplayListPage.tsx`。
- 視覺規則維護於 `frontend/src/components/pages/replay/ReplayListPage.css`。
- 遊玩與練習回放列表應共用 `.recordings-list`、`.recording-card`、`.recording-meta-row`，避免兩種模式分裂成不同卡片系統。
- 統計概覽使用 `.friend-status-grid` 與 `.friend-status-pill`，與 `StatsPage` 的個人統計卡一致。

**輸出格式**:
```tsx
<section className="friend-setup-section replay-list-overview">
  <div className="friend-section-title">
    <span>1</span>
    <h2>統計概覽</h2>
  </div>
  <div className="friend-status-grid replay-summary-cards">...</div>
</section>
```

```css
.recording-card {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) auto;
}
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入「歷史」->「遊玩模式」，確認頁面含統計概覽、篩選與排序、回放記錄三段，記錄列顯示對戰資訊與比分。
- 進入「歷史」->「練習模式」，確認同一版面顯示練習類型、玩家、時長與日期。
- 縮窄視窗時，確認記錄列會堆疊成單欄，播放與刪除按鈕並排且不被截斷。

### 06/05: '訓練與遊玩進行中內頁優化'

**功能說明**:
- 訓練中心進入練習後的二層內頁改用目前統一的 section/pill 視覺語言。
- 訓練進行頁排版改為「左側主影像 + 右側統計/規劃 + 底部記錄結果」；影像區成為主要視覺焦點，記錄結果移到下方橫向操作列。
- 練習統計不顯示 section 數字，嘗試次數、成功次數與成功率改用 `friend-status-pill` 風格。
- 練習規劃面板與記錄結果面板改用一致的 surface、border、radius 與按鈕密度；成功、失敗快捷鍵提示固定在按鈕右側，主要文字保持置中。
- 多球路徑規劃面板改為底部跨整列顯示，最佳路線資訊在桌面寬度下橫向鋪排，避免被右側窄欄壓縮。
- 記錄結果操作列改為標題加四顆等寬按鈕；成功、失敗、暫停、結束練習在桌面寬度下維持同高同寬。
- 遊玩模式進入對戰後的二層內頁不顯示 section 數字，比分、遊戲狀態、選項列與操作列納入統一區塊。
- 遊玩進行頁排版改為「上方比分 + 左側影像 + 右側狀態 + 底部選項/操作列」的對戰控制台；`自動進球/計分`、`犯規檢測`、`AR 提示` 移到底部並橫向放置。
- 對戰進行頁移除非必要符號，將當前玩家、倒數、錄影與犯規狀態改為文字與 pill 呈現。

**規範用法**:
- 訓練進行頁結構維護於 `frontend/src/components/pages/PracticePage.tsx`，樣式維護於 `PracticePage.css`。
- 遊玩進行頁結構維護於 `frontend/src/components/pages/GamePage.tsx`，樣式維護於 `GamePage.css`。
- 二層內頁應優先使用 `friend-section-title`、`friend-status-pill`、`practice-live-section`、`game-live-section`，避免新增另一套深灰卡片樣式。
- 二層內頁的 `friend-section-title` 不使用數字 badge；若需要區分區塊，以位置、標題與 spacing 表達層級。
- 進行中頁排版應以實時影像為主視覺，資訊面板靠側邊或底部排列；不要回到所有區塊垂直堆疊的統計頁型態。
- 操作按鈕保持可點擊面積，但避免使用過大的漸層色塊；危險與警告操作以低飽和底色加邊框區分。
- 底部橫向列在窄螢幕可堆疊成單欄，但桌面寬度下記錄結果、遊戲選項與對戰操作需維持橫向排列。

**輸出格式**:
```tsx
<div className="practice-content">
  <div className="video-container">...</div>
  <div className="stats-panel practice-live-section practice-live-stats">...</div>
  <div className="action-panel practice-live-section practice-live-actions">...</div>
  <div className="practice-planner-panel practice-live-section">...</div>
</div>
```

```tsx
<div className="game-content">
  <section className="score-section game-live-section">...</section>
  <div className="video-container">...</div>
  <section className="game-status game-live-section">...</section>
  <section className="game-options-panel game-live-section">...</section>
</div>
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入「訓練」並開始任一練習，確認影像在左側主區，統計在右側，多球路徑規劃跨底部整列，記錄結果四顆按鈕等寬橫向排列。
- 進入「遊戲」並開始對戰，確認比分在上方、影像在左側、遊戲狀態在右側，自動進球/計分、犯規檢測、AR 提示與操作列在底部橫向排列。
- 縮窄視窗時，確認對戰 header、比分與操作按鈕可堆疊，不產生水平溢出。

### 06/05: 'AI Coach WebSocket 支援 Cloudflare Tunnel 連線'

**功能說明**:
- 後端設定新增 `AI_COACH_PUBLIC_BASE_URL` 與 `AI_COACH_WS_PATH`。
- 填入 Cloudflare Tunnel 的 HTTPS base URL 後，`backend/config.py` 會自動組成 `wss://<host>/ws/coach` 作為 `AI_COACH_WS_URL`。
- 根目錄 `start.bat` 不再硬性覆蓋 `AI_COACH_WS_URL=ws://localhost:8010/ws/coach`，避免 `.env` 內的 Cloudflare 設定被啟動腳本覆蓋。
- 若 `AI_COACH_PUBLIC_BASE_URL` 留空，仍沿用 `AI_COACH_WS_URL`，預設為本機 `ws://localhost:8010/ws/coach`。

**規範用法**:
- 臨時 Cloudflare Quick Tunnel 請填 tunnel HTTPS base URL，不要手動填 `/ws/coach` 到 base URL。
- 若需要自訂 WebSocket path，修改 `AI_COACH_WS_PATH`；一般保持 `/ws/coach`。
- 若同時設定 `AI_COACH_PUBLIC_BASE_URL` 與 `AI_COACH_WS_URL`，會優先使用 `AI_COACH_PUBLIC_BASE_URL` 產生的 WSS URL。

**輸出格式**:
```env
AI_COACH_ENABLED=true
AI_COACH_PUBLIC_BASE_URL=https://your-ai-coach.trycloudflare.com
AI_COACH_WS_PATH=/ws/coach
AI_COACH_WS_URL=ws://localhost:8010/ws/coach
```

實際生效的 WebSocket URL：

```text
wss://your-ai-coach.trycloudflare.com/ws/coach
```

**驗證**:
```powershell
cd backend
..\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path.cwd() / '.env'); import config; print(config.AI_COACH_WS_URL)"
```

預期輸出：

```text
wss://your-ai-coach.trycloudflare.com/ws/coach
```

### 06/05: '修復前端 build chunk size warning'

**功能說明**:
- `frontend/vite.config.js` 新增 `build.rolldownOptions.output.manualChunks`。
- 將 React、i18n、Recharts/d3、Lucide 與其他第三方依賴拆成 vendor chunks，避免主入口 bundle 超過 Vite 預設 `500kB` 警告門檻。
- 保留既有 `MobilePrototypeApp` 動態載入流程，不改變前端路由與使用者操作。

**規範用法**:
- Vite 8 使用 Rolldown，新增分包設定時應優先使用 `build.rolldownOptions`，不要再新增 deprecated 的 `rollupOptions`。
- 若新增大型第三方套件，應在 `manualChunks()` 依套件用途加入專用 chunk，避免回到單一主 bundle。
- 不以調高 `chunkSizeWarningLimit` 作為預設解法；只有確認 chunk 拆分已合理後，才可調整警告門檻。

**輸出格式**:
```js
build: {
  rolldownOptions: {
    output: {
      manualChunks(id) {
        if (!id.includes('node_modules')) return undefined;
        if (id.includes('recharts') || id.includes('d3-')) return 'chart-vendor';
        return 'vendor';
      },
    },
  },
}
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 預期輸出不再顯示 `Some chunks are larger than 500 kB after minification`。
- 主入口 chunk 約 `315kB`，`chart-vendor` 約 `477kB`，皆低於 Vite 預設警告門檻。

### 06/06: '球色校正內頁更新排版並新增重新掃描'

**功能說明**:
- 設定頁內的球色校正設定子頁改為工作台排版。
- 桌面寬度下左側保留相機參考畫面，右側集中顯示目前目標、掃描結果與操作按鈕。
- 掃描完成後新增「重新掃描」按鈕，可重新呼叫目前顏色的 auto-scan，不會切換到下一個顏色。
- 掃描結果區改為顯示色票與 HSV 中心值；尚未掃描時顯示等待掃描狀態。
- 點擊「儲存並退出」成功更新資料庫後，前端會立即套用同一設定檔到目前檢測。

**規範用法**:
- 重新掃描按鈕沿用 `scanCurrentColorBall()`，不新增後端 API。
- 重新掃描按鈕在 `hasColorModalScanned` 為 `false` 時停用。
- 儲存流程依序呼叫 `PUT /api/color-calibration/profiles/{profile_id}/mappings` 與 `POST /api/color-calibration/apply`。
- `POST /api/color-calibration/apply` 只傳 `profile_id`，後端必須從資料庫讀取 mappings 後同步到 tracker。
- 若儲存成功但套用失敗，前端顯示「設定檔已儲存，但同步到目前檢測失敗」，並保留在編輯頁。
- 新增文字需同步維護 `zh-TW`、`zh-CN`、`en-US`。

**輸出格式**:
```tsx
<button
  className="settings-button secondary"
  type="button"
  onClick={scanCurrentColorBall}
  disabled={isColorModalLoading || !hasColorModalScanned}
>
  {t('settings.tableCalibration.rescanCurrentBall')}
</button>
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入 `設定 > 球桌校正 > 球色校正`，選擇設定檔並點擊「編輯」。
- 點擊「掃描目前球體」後，確認畫面顯示 HSV 掃描結果與「重新掃描」按鈕。
- 點擊「重新掃描」後，確認維持同一顏色步驟並更新掃描結果。

### 06/06: '設定頁內容底部安全留白'

**功能說明**:
- 設定頁主內容在桌面與手機版皆保留底部安全留白，避免最後一段設定卡片貼齊視窗底部或被底部邊界截斷。
- 寬版設定頁如 `球桌校正`、`球色校正` 共用 `.settings-page` 底部留白規則。
- 外層 `.main-content` 在桌面版也保留底部 padding，讓整個可視內容區不再貼齊瀏覽器底部。

**規範用法**:
- `.settings-page` 需使用 `box-sizing: border-box`，避免 padding 影響既有內容寬度。
- 桌面版底部留白為 `128px`；手機版底部留白為 `88px`。
- `.main-content` 桌面版底部 padding 為 `28px`，並使用 `box-sizing: border-box` 讓主內容高度包含安全留白。

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入 `設定 > 球桌校正`，確認主內容藍框或滾動區底部不再貼齊視窗底部。
- 滾動到最下方時，確認最下方「投影」區塊下方仍有可見空間。

### 06/06: '移除頂部列未使用入口'

**功能說明**:
- 移除頂部右側未接功能的搜尋與訊息 icon 按鈕，避免使用者看到無效操作入口。
- 移除帳號膠囊中的固定 `Lv.18` 顯示，避免訪客或未登入狀態出現假等級資訊。
- 保留分析狀態按鈕與帳號選單，因兩者仍對應實際分析啟停與帳號/設定/登入流程。

**規範用法**:
- 頂部列不可顯示沒有事件處理或正式頁面流程的操作按鈕。
- 使用者等級若未接入真實資料來源，不可在帳號顯示區硬編碼。

**驗證**:
- 執行 `cd frontend && npm run build`。
- 進入主介面，確認頂部右側只保留分析狀態按鈕與帳號選單。
- 確認帳號選單仍可開啟「帳號管理 / 設定 / 登入或登出」。

### 06/06: '帳號選單切頁後自動收合'

**功能說明**:
- 頂部帳號選單點擊「帳號管理」、「設定」、「登入 / 登出」後，會先收合選單再執行原本頁面切換或認證動作。
- 避免從帳號選單切換頁面後，選單浮層仍停留在新頁面右上角。

**規範用法**:
- 帳號選單項目需透過共用 action wrapper 呼叫，先 `setIsAccountMenuOpen(false)`，再執行實際 callback。
- 未來新增帳號選單項目時，也必須沿用相同收合流程。

**驗證**:
- 執行 `cd frontend && npm run build`。
- 打開右上角帳號選單，分別點擊「帳號管理」、「設定」、「登入 / 登出」，確認切換後選單不再顯示。

### 06/06: '停止分析同步關閉 CV 標註圖層'

**功能說明**:
- 點擊頂部「停止分析」後，前端不再依舊 metadata 繪製 SVG 偵測框、球號、路線與 cue overlay。
- `/api/control/analysis` 與舊 `/api/control/toggle` 在停用 YOLO 時同步將 `TRACKER_ANNOTATION_MODE` 設為 `none`，讓 burn-in 串流也停止繪製 CV 標註。
- 重新啟動分析時會恢復 `full` 標註模式，讓即時影像回到完整球號與路徑標註。
- 手動停止後，前端不會被尚未更新的舊 metadata `tracking_state=active` 立刻覆蓋回啟用狀態。
- 手動停止狀態使用 ref 與 state 同步記錄，按下停止的同一個事件流程內就會阻止監控頁自動重啟分析。

**規範用法**:
- 即時影像頁的 overlay 顯示條件必須同時滿足 `isAnalyzing=true` 與 metadata 有有效內容。
- 明確啟停分析時，前端需同步呼叫 `/api/control/overlay-mode`，後端控制 API 也需直接維護 `TRACKER_ANNOTATION_MODE` 作為保底。
- 監控頁自動啟用分析與 AI Coach 恢復 overlay 的流程，都必須先檢查手動停止鎖，不能在使用者按下停止後立即重新啟用。

**驗證**:
- 執行 `cd frontend && npm run build`。
- 執行 `python -m py_compile backend/main.py`。
- 在監控頁啟動分析後確認球圈與路線顯示；點擊「停止分析」後確認 CV 標註圖層消失。
- 再次點擊啟動後，確認 CV 標註圖層恢復。

### 06/12: '設定頁暫時隱藏 AI Coach 聊天室'

**功能說明**:
- 使用者進入 `設定`、`自動校正`、`相機參數` 或 `球色校正` 這類設定流程時，前端會暫時隱藏 AI Coach 聊天室。
- 設定頁主內容不再套用 `with-coach` 佈局，避免聊天室佔用設定頁右側空間或遮住設定表單。
- 若切入設定前 AI Coach 聊天室已開啟，返回監控、練習、回放或遊戲頁後會恢復原本開啟狀態，不需要重新點開。
- 若切入設定前 AI Coach 聊天室未開啟，返回一般頁面後仍維持關閉。

**規範用法**:
- 設定相關頁面需透過 `isSettingsPage(page)` 統一判斷，包含 `settings`、`calibration`、`camera-params`、`color-calibration`。
- `handlePageChange()` 切入設定相關頁時不可清除 `isCoachMenuOpen` 與 `isCoachChatOpen`，避免返回一般頁面後原本聊天室狀態遺失。
- `shouldShowEmbeddedCoach` 必須排除設定相關頁，讓設定頁只暫時不渲染聊天室。

**輸出格式**:
```tsx
const shouldShowEmbeddedCoach =
  !isSettingsPage(currentPage) && isCoachMenuOpen && isCoachChatOpen && Boolean(activeCoachSessionId);
```

**驗證**:
- 執行 `cd frontend && npm run build`。
- 在主畫面開啟 AI Coach 聊天室後，點擊左下角或頂部帳號選單的「設定」，確認設定頁不顯示聊天室。
- 從設定頁返回主畫面，確認 AI Coach 聊天室恢復為開啟狀態。
- 在 AI Coach 未開啟時進入設定再返回主畫面，確認聊天室仍維持關閉。

### 06/05: '修正中袋與角袋進球線目標點'

**功能說明**:
- Route planner 的 `object_to_pocket` 目標點不再所有袋口都固定使用 `pocket.center`。
- 角袋與底袋改從 `mouth_segment` 的入口中心往桌內取目標點，不使用黑洞偵測點 `pocket.center`，避免進球線先穿過庫邊。
- 中袋改依子球進袋方向，在桌內入口點的左側或右側取目標點，避免進球線穿過中袋袋角。
- `PhysicsValidator.can_pocket_ball()` 新增 `target_point` 參數，讓袋口窗口驗證與實際輸出的路線終點一致。

**規範用法**:
- `CandidateGenerator._pocket_aim_point()` 統一決定袋口瞄準點。
- direct/cut、bank、combo、kick 等可進袋路線都必須使用同一個 `hole` 目標點產生 ghost ball、路徑檢查、分段路線與 route id。
- 前端與投影端仍讀取 `route_segments[].points`，不需要自行修正袋口目標點。

**輸出格式**:
```json
{
  "route_segments": [
    {
      "type": "object_to_pocket",
      "points": [[884, 183], [623, 110]],
      "color": "green"
    }
  ]
}
```

**驗證**:
```powershell
.\.venv\Scripts\python.exe -m pytest backend\test-program\tracking\test_route_planner.py -q
```

預期結果：
- 角袋路線終點落在 `mouth_segment` 入口中心往桌內偏移後的位置，不會先碰庫邊。
- 中袋路線終點依來球左右方向落在桌內入口點的左側或右側，不再固定畫到中袋中心。

### 06/05: '修正進球線遮擋誤忽略同號球'

**功能說明**:
- Route planner 的路徑遮擋檢查不再只用球號決定是否忽略 blocker。
- 目標球可被忽略，但必須符合實際目標球球心；若 YOLO 產生重號或誤判成同號，路線上的另一顆球仍會被視為阻擋。
- 修正綠色 `object_to_pocket` 線切到其它球時仍被判定可打的問題。

**規範用法**:
- `PhysicsValidator.is_path_clear()` 新增 `ignored_ball_centers` 參數。
- `CandidateGenerator` 呼叫遮擋檢查時，需傳入實際允許忽略的目標球球心。
- direct/cut、bank、combo、kick、kick escape 都需使用同一規則，避免不同路線類型對遮擋判定不一致。

**輸出格式**:
```python
validator.is_path_clear(
    obj_center,
    hole,
    state.object_balls,
    ignore_ball_numbers={0, obj.number},
    safety_radius=obj.radius,
    ignored_ball_centers=[obj.center],
)
```

**驗證**:
```powershell
.\.venv\Scripts\python.exe -m pytest backend\test-program\tracking\test_route_planner.py -q
```

預期結果：
- 目標球本身不會阻擋母球撞擊或子球起點。
- 同號但球心不同、且位於綠色進球線上的球會阻擋該路線。

### 06/14: '修正 9-ball 視覺漏檢誤切目標球'

**功能說明**:
- 9-ball 遊戲模式下，視覺剩餘球號修正不再單靠 YOLO 漏檢或誤標把目前合法目標球移除。
- 若規則狀態仍認定目前目標球存在，例如 `target_ball=1` 且 `remaining_balls` 仍包含 1，即使視覺暫時只看到 2~9，也會保留 1 作為合法首碰球。
- 只有規則流程已確認當前目標球進袋並更新 `target_ball` 後，視覺修正才會跟著切到下一顆球。

**規範用法**:
- `GameManager.apply_visual_remaining_balls()` 可用於補回穩定看見的球號與同步視覺剩餘球列表。
- 視覺資料不得單獨推進當前 9-ball 目標球；進球推進仍由 `check_nine_ball_rules()` 或遊戲規則狀態負責。
- `tracker.set_route_target_ball_number()` 應以遊戲規則的 `target_ball` 為準，避免路線規劃在 1 號球未進時切到 2 號球。

**輸出格式**:
```json
{
  "status": "visual_remaining_applied",
  "remaining_balls": [1, 2, 3, 4, 5, 6, 7, 8, 9],
  "target_ball": 1,
  "remaining_balls_source": "rules+vision"
}
```

**驗證**:
```powershell
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_game_manager.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_route_planner.py
```

預期結果：
- 視覺只回報 2~9 時，遊戲目標仍維持 1。
- 1 號球經規則流程確認進袋後，目標才會切換成 2。

### 06/14: '修正路線規劃同幀性與同號球不穩定'

**功能說明**:
- WebSocket `metadata.update` 的 `multi_plan` 改為只採用目前 `data_packet` 同幀資料，不再優先混用全域 `latest_analysis_data.multi_plan`。
- metadata 新增 `source_frame_id`、`source_timestamp`、`source_img_w`、`source_img_h`，用於前端與除錯工具確認球框、白球、雷射線與路線是否同一幀。
- 當目前幀沒有有效 route/aim/cue laser guide 時，projector renderer 會清空即時動態 AR guide，避免投影端殘留上一筆路線或雷射指標。
- 同一畫面若出現相同球號，會保留分類品質較高的一顆，較弱候選清除 `number`，保留外框供診斷，避免錯號進入 planner。

**規範用法**:
- `metadata.update.multi_plan` 必須與 `detections_view`、`white_ball`、`cue_laser_line` 來自同一個 `data_packet`。
- 前端若發現 `source_frame_id` 變動但 route 不變，應視為後端資料異常，不應自行沿用舊 route。
- Projector live mode 不能因短暫沒有 route 就繼續保留上一幀動態 guide；固定球型練習 `pattern_static` 不受此規則影響。
- `PoolTracker._resolve_duplicate_ball_numbers()` 僅清除較弱候選的球號，不刪除 bbox，方便 color diagnostics 追查誤判來源。

**輸出格式**:
```json
{
  "frame_id": 12,
  "source_frame_id": 103721,
  "source_timestamp": 1781451066.7710092,
  "source_img_w": 1920,
  "source_img_h": 1080,
  "detections_view": [
    {"x": 1031, "y": 430, "w": 35, "h": 35, "number": 1},
    {"x": 929, "y": 157, "w": 37, "h": 37, "number": 2},
    {"x": 472, "y": 187, "w": 39, "h": 39, "number": null}
  ],
  "multi_plan": null,
  "ar_route_segments": []
}
```

**驗證**:
```powershell
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m py_compile backend\main.py backend\tracking\tracking_engine.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_tracking.py -k duplicate_ball_number_resolution
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_game_manager.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_route_planner.py
```

預期結果：
- WebSocket metadata 可直接看出 route 與 detection 的來源幀。
- 沒有同幀 `multi_plan` 時，前端與 projector 都不應繼續畫舊路線。
- 同號球衝突時，畫面不再顯示兩顆相同號碼，planner 不會把較弱錯號候選當成合法目標。

### 06/14: '降低 second-pass YOLO 延遲'

**功能說明**:
- 第二階段 YOLO 補強改用較低成本預設，避免低檢出幀長時間卡住即時偵測結果。
- `SECOND_PASS_MIN_OBJECTS` 預設由 4 降為 3，減少 first-pass 已有基本偵測時仍補跑的機率。
- `SECOND_PASS_IMG_SIZE` 預設由 960 降為 640，`SECOND_PASS_CONF_THR` 預設由 0.04 提高到 0.08，降低每次補跑成本與雜訊。
- 新增 `SECOND_PASS_COOLDOWN_FRAMES`，低檢出狀態觸發一次 second-pass 後會冷卻數幀，避免每幀重跑造成雷射線與路線資料延後。

**規範用法**:
- 延遲優先時可保持預設：
  - `SECOND_PASS_MIN_OBJECTS=3`
  - `SECOND_PASS_IMG_SIZE=640`
  - `SECOND_PASS_CONF_THR=0.08`
  - `SECOND_PASS_COOLDOWN_FRAMES=4`
- 若現場球體召回率不足，可逐步提高 `SECOND_PASS_IMG_SIZE` 或降低 `SECOND_PASS_CONF_THR`，但需同步觀察 `/api/performance/stats` 的 `yolo_result` 與 backend log 的 YOLO future timeout。
- `SECOND_PASS_MIN_BALLS=0` 表示不因球數不足強制補跑；若設定為大於 0，完整辨識模式仍可在球數低於門檻時觸發補強。

**輸出格式**:
```env
SECOND_PASS_ENABLED=true
SECOND_PASS_MIN_OBJECTS=3
SECOND_PASS_MIN_BALLS=0
SECOND_PASS_SKIP_WHEN_CUE_FOUND=true
SECOND_PASS_IMG_SIZE=640
SECOND_PASS_CONF_THR=0.08
SECOND_PASS_COOLDOWN_FRAMES=4
```

**驗證**:
```powershell
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m py_compile backend\config.py backend\tracking\tracking_engine.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_tracking.py -k "second_pass or duplicate_ball_number_resolution"
```

預期結果：
- second-pass 仍會在球數召回不足時補強。
- cue-laser-only 模式仍維持單次推論。
- 連續低檢出幀不會每幀補跑 second-pass。

### 06/15: '修正投影端無 AR 資料時全黑難以辨識'

**功能說明**:
- Projector practice/game 模式若沒有 route、cue laser、setup balls 或 timer，不再只輸出完全黑畫面。
- 新增投影可辨識的低亮度 active 底色、空狀態提示、球桌區域、球桌框與角點，讓現場可確認投影串流仍正常，只是目前沒有可投影的路線資料。
- 修正 `ProjectorRenderer._draw_static_ar_elements()` 無實際繪製元素時仍回傳 `True` 的問題，避免 renderer 誤判已畫出內容。
- 手動 planner 產生的投影路線不再被下一幀空 `live_yolo` 結果立即清空，避免路線只閃一下就消失。
- Idle 模式仍維持純黑，不影響待機與關閉投影的行為。

**規範用法**:
- `PROJECTOR_SHOW_EMPTY_STATUS=true` 時，practice/game 空狀態會顯示淡色診斷提示。
- 若現場需要完全黑底，可設定 `PROJECTOR_SHOW_EMPTY_STATUS=false`。
- `PROJECTOR_MANUAL_ROUTE_HOLD_MS=30000` 控制 `planner_plan`、`planner_select_route`、`planner_stroke` 來源的路線保留時間。
- Planner 回 `Insufficient state for route planning` 時，優先檢查白球與目標球是否被 YOLO 偵測；投影端只會顯示狀態，不會硬投錯誤路線。

**輸出格式**:
```env
PROJECTOR_SHOW_EMPTY_STATUS=true
PROJECTOR_MANUAL_ROUTE_HOLD_MS=30000
```

```json
{
  "projector_status": "waiting_for_route",
  "table_polygon": [[100, 100], [1820, 100], [1820, 980], [100, 980]],
  "route_segments": [],
  "cue_laser_lines": []
}
```

**驗證**:
```powershell
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m py_compile backend\main.py backend\config.py backend\calibration\projector_renderer.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\calibration\test_projector_renderer.py
```

預期結果：
- practice 空狀態輸出的 frame 不再全黑。
- 空狀態輸出需有足夠整體亮度，避免後端已輸出但實體投影看起來仍像黑畫面。
- 關閉空狀態提示時，無 AR practice frame 仍可保持全黑。
- 有 route_segments 時，renderer 仍正常輸出投影線。
- 手動 planner 路線不會被下一幀沒有 route 的 camera loop 清掉。

### 06/15: '修正 YOLO 漏白球導致多球路線不顯示'

**功能說明**:
- `_analyze_balls()` 在 YOLO 未回傳 `white-ball` 且不是 `cue_laser_only` 模式時，會啟用既有影像處理 fallback。
- 若 YOLO 曾產生白球候選但後續被 overlap suppress 清空，輸出前會再次嘗試 fallback。
- fallback 會在球桌畫面中尋找高亮度、低飽和度且近似圓形的區域，並排除已確認的彩球位置。
- 補回的母球會進入正常 `white_ball` payload，讓 planner 可在已有目標球、洞口與 table ROI 時產生 `multi_plan`。
- 若 fallback 白球與當幀 raw YOLO `white-ball` bbox 重疊，即使 stale route artifact 判定命中，也會保留該白球，避免上一條投影線誤殺真實母球。
- 若 fallback 找不到可信白球，仍維持 `white_ball=null`，planner 不會硬產生錯誤路線。

**規範用法**:
- `white_ball` 來源可為 YOLO `white-ball` 類別，或 YOLO 漏檢時的影像 fallback。
- fallback 只補母球，不新增目標球；至少仍需有一顆 `color-ball` 與有效 `holes/table_roi` 才能規劃路線。
- 前端「啟動多球規劃」不需改 API，仍呼叫 `/api/planner/plan`。

**輸出格式**:
```json
{
  "white_ball": [132, 113, 35, 35],
  "balls": [
    {"x": 274, "y": 114, "w": 32, "h": 32, "number": 1}
  ],
  "multi_plan": {"best_route": {"target_ball_number": 1}}
}
```

**驗證**:
```powershell
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m py_compile backend\tracking\tracking_engine.py backend\main.py backend\config.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_tracking.py -k "image_fallback_when_yolo_misses_white_ball or segmentation_mask_for_ball_geometry or segmentation_polygon_for_ball_geometry or duplicate_ball_number_resolution"
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\tracking\test_route_planner.py
```

預期結果：
- YOLO 只回彩球但畫面上有清楚白球時，`_analyze_balls()` 會補回 `white_ball`。
- 白球候選被 suppress 後變空時，仍會在最後輸出前補回可信 fallback 白球。
- fallback 白球與 raw YOLO `white-ball` 重疊時，不會被 stale projected artifact 過濾掉。
- planner 收到白球與目標球後可產生候選路線，不再因 `Insufficient state for route planning` 直接無線。

### 06/15: '桌面端分析頁直接顯示登入玩家數據'

**功能說明**:
- 桌面端上方「分析」入口不再顯示玩家選擇頁。
- 使用者已登入時，分析頁直接以目前登入帳號名稱查詢個人統計。
- 訪客身分仍無法查看分析頁，會顯示需要登入的頁內提示。

**規範用法**:
- 分析入口資料來源以 `authSession.username` 為主，若 session 內有 user 物件則可 fallback 到 `authSession.user.username`。
- 不允許從分析入口手動切換到其他玩家資料，避免訪客或一般使用者查看非本人分析。
- 回放紀錄入口維持原本遊玩模式與練習模式清單，不受分析入口調整影響。

**輸出格式**:
```tsx
<StatsPage playerName={signedInPlayerName} />
```

訪客狀態輸出：
```tsx
renderGuestRestrictedPage('analysis')
```

**驗證**:
```powershell
npm run build
```

預期結果：
- 登入使用者點擊「分析」後直接看到本人統計分析。
- 訪客點擊「分析」後只看到登入提示，不會進入統計 API 查詢。
- 前端 TypeScript build 通過。
