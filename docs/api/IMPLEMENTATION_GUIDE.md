# IMPLEMENTATION_GUIDE.md

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
