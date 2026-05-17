# YOLO 控制介面 - 使用說明

## 功能概述

已成功實現現代化的撞球分析系統前端介面，包含 YOLO 辨識控制功能。

## 介面結構

```
┌──────────────────────────────────────────────────────┐
│  🎱 撞球分析系統 v1.5    [🟢 啟動辨識]  [🔴 停止辨識]  │  ← 頂部欄
├────────────┬─────────────────────────────────────────┤
│            │                                         │
│ 📹 即時影像 │                                         │
│            │         主內容區                         │
│ 📊 Session │      (根據左側選單切換)                   │
│            │                                         │
│ 📈 Metadata│                                         │
│            │                                         │
│ ⚙️ 設定     │                                         │
│            │                                         │
└────────────┴─────────────────────────────────────────┘
   側邊欄              主內容區
```

## 新增的檔案

### 組件檔案
- `frontend/src/components/Layout.tsx` - 主佈局框架
- `frontend/src/components/TopBar.tsx` - 頂部導航欄（含 YOLO 控制按鈕）
- `frontend/src/components/Sidebar.tsx` - 側邊欄選單
- `frontend/src/components/pages/StreamPage.tsx` - 即時影像頁面
- `frontend/src/components/pages/SessionPage.tsx` - Session 資訊頁面
- `frontend/src/components/pages/MetadataPage.tsx` - Metadata 數據頁面
- `frontend/src/components/pages/SettingsPage.tsx` - 系統設定頁面

### 樣式檔案
- `frontend/src/components/Dashboard.css` - 主樣式
- `frontend/src/components/Layout.css` - 佈局樣式
- `frontend/src/components/TopBar.css` - 頂部欄樣式
- `frontend/src/components/Sidebar.css` - 側邊欄樣式
- `frontend/src/components/pages/StreamPage.css` - 即時影像頁面樣式
- `frontend/src/components/pages/SessionPage.css` - Session 頁面樣式
- `frontend/src/components/pages/MetadataPage.css` - Metadata 頁面樣式
- `frontend/src/components/pages/SettingsPage.css` - 設定頁面樣式

### 修改的檔案
- `frontend/src/components/Dashboard.tsx` - 重寫為現代化佈局

## 主要功能

### 1. YOLO 辨識控制

**位置**：頂部導航欄右側

**按鈕**：
- 🟢 **啟動辨識** - 綠色按鈕，點擊後啟動 YOLO 物件檢測
- 🔴 **停止辨識** - 紅色按鈕，點擊後停止 YOLO 物件檢測

**狀態同步**：
- 按鈕狀態會根據當前辨識狀態自動切換（啟用/禁用）
- 顯示 loading 狀態（⏳ 啟動中... / ⏳ 停止中...）
- 自動從 WebSocket metadata 同步狀態

**API 端點**：
- `POST /api/control/toggle` - 切換 YOLO 辨識狀態

### 2. 頁面導航

**側邊欄選單**（左側）：
- 📹 **即時影像** - 顯示 burn-in 串流 + YOLO 狀態 + 系統狀態
- 📊 **Session** - 顯示 Session 詳細資訊和權限
- 📈 **Metadata** - 顯示即時檢測數據和軌跡預測
- ⚙️ **設定** - 系統設定（攝影機、YOLO 參數等）

### 3. 即時影像頁面

**影像區域**：
- 顯示 burn-in 串流（MJPEG）
- 支援畫質切換（低/中/高）
- 支援全螢幕模式
- 自動重試機制（連接失敗時）

**YOLO 辨識狀態卡片**：
- 辨識狀態：● 已啟用 / ○ 已停用
- 追蹤狀態：active / idle
- 檢測數量：實時更新
- 更新頻率：Hz

**系統連接狀態卡片**：
- WebSocket：🟢 已連接 / 🔴 未連接
- Health：健康度狀態（HEALTHY / DEGRADED / NO_SIGNAL等）
- FPS：實時幀率
- Pipeline：管線狀態（RUNNING / NO_SIGNAL / DISCONNECTED）

## 使用流程

### 啟動系統

1. **啟動後端**：
   ```bash
   cd backend
   python main.py
   ```

2. **啟動前端**：
   ```bash
   cd frontend
   npm run dev
   ```

3. **訪問介面**：
   打開瀏覽器訪問 `http://localhost:5173`

### 使用 YOLO 辨識

1. **啟動辨識**：
   - 點擊頂部的 🟢 **啟動辨識** 按鈕
   - 等待按鈕變為 loading 狀態
   - 啟動成功後，按鈕變為禁用狀態
   - 🔴 **停止辨識** 按鈕變為可用

2. **觀察效果**：
   - 即時影像會顯示物件檢測框和軌跡線
   - YOLO 辨識狀態卡片顯示 "● 已啟用"
   - 追蹤狀態變為 "active"
   - 檢測數量實時更新

3. **停止辨識**：
   - 點擊頂部的 🔴 **停止辨識** 按鈕
   - 等待按鈕變為 loading 狀態
   - 停止成功後，影像切換為原始畫面（無標註）
   - YOLO 辨識狀態卡片顯示 "○ 已停用"

### 切換頁面

- 點擊左側側邊欄的選單項目
- 主內容區會切換到對應頁面
- 選中的選單項目會高亮顯示（藍色左邊框）

## 技術特性

### 響應式設計

- **桌面** (> 1024px)：完整佈局（頂部欄 + 側邊欄 + 主內容）
- **平板** (768px - 1024px)：側邊欄可收合
- **手機** (< 768px)：側邊欄變為底部導航欄，垂直堆疊

### 狀態管理

- 使用 React Hooks 管理組件狀態
- 透過 useBilliardsSDK 連接 WebSocket
- 自動同步後端狀態（metadata.tracking_state）

### 錯誤處理

- MJPEG 串流自動重試（最多 3 次）
- API 請求失敗時顯示錯誤提示
- WebSocket 斷線自動重連

### 樣式設計

- **暗色主題**：深藍黑背景 (#0f172a)
- **卡片式設計**：圓角、陰影、清晰分層
- **顏色語義**：
  - 綠色 (#22c55e)：成功、啟用、正常
  - 紅色 (#ef4444)：錯誤、停止、異常
  - 藍色 (#3b82f6)：選中、主要操作
  - 黃色 (#eab308)：警告、降級
  - 灰色 (#64748b)：禁用、次要資訊

## 後端整合

### 已使用的 API

1. **Session 管理**：
   - `POST /api/sessions` - 創建 session
   - 自動透過 SDK 處理

2. **WebSocket 控制**：
   - `/ws/control?session_id={id}` - WebSocket 連接
   - 接收 heartbeat 和 metadata

3. **YOLO 控制**：
   - `POST /api/control/toggle` - 切換辨識狀態
   - 回應：`{"status": "success", "is_analyzing": true/false}`

4. **Burn-in 串流**：
   - `/burnin/{stream_id}.mjpg?quality=med` - MJPEG 串流
   - 自動啟動攝影機（背景線程）

### 資料流

```
前端                                 後端
  │                                   │
  ├─ 初始化 SDK ──────────────────►  創建 Session
  │                                   │
  ├─ 建立 WebSocket ─────────────►  /ws/control
  │                                   │
  │  ◄── Heartbeat (3秒) ────────────┤
  │  ◄── Metadata (10Hz) ────────────┤
  │                                   │
  ├─ 顯示 Burn-in ─────────────────► /burnin/camera1.mjpg
  │                                   │
  │                     (攝影機背景線程持續捕獲)
  │                                   │
  ├─ 點擊啟動辨識 ─────────────────► POST /api/control/toggle
  │  ◄── {is_analyzing: true} ──────┤
  │                                   │
  │       (影像開始顯示檢測框和軌跡)
  │                                   │
  │  ◄── Metadata (tracking_state: active)
  │                                   │
  ├─ 點擊停止辨識 ─────────────────► POST /api/control/toggle
  │  ◄── {is_analyzing: false} ─────┤
  │                                   │
  │       (影像切換為原始畫面)
  │                                   │
```

## 測試建議

### 功能測試

1. **YOLO 控制測試**：
   - [ ] 點擊啟動按鈕，檢查影像是否顯示檢測框
   - [ ] 點擊停止按鈕，檢查影像是否切換為原始畫面
   - [ ] 快速連續點擊按鈕，檢查 loading 狀態是否正確
   - [ ] 檢查狀態卡片是否正確更新

2. **頁面切換測試**：
   - [ ] 切換到 Session 頁面，檢查資訊是否顯示
   - [ ] 切換到 Metadata 頁面，檢查數據是否實時更新
   - [ ] 切換到設定頁面，檢查設定項目是否顯示

3. **響應式測試**：
   - [ ] 縮小瀏覽器視窗，檢查佈局是否正確調整
   - [ ] 在手機模擬器中測試，檢查側邊欄是否變為底部導航

4. **錯誤處理測試**：
   - [ ] 停止後端，檢查連接狀態是否正確顯示
   - [ ] 網路延遲時，檢查 MJPEG 是否自動重試

### 效能測試

1. **WebSocket 效能**：
   - 檢查 metadata 更新是否流暢（10Hz）
   - 檢查 heartbeat 是否正常（每 3 秒）

2. **影像串流效能**：
   - 檢查 MJPEG 串流是否流暢（30 FPS）
   - 檢查切換畫質是否即時生效

## 故障排除

### 常見問題

1. **按鈕點擊無反應**：
   - 檢查後端是否正常運行
   - 檢查瀏覽器控制台是否有錯誤訊息
   - 確認 API URL 設定正確

2. **影像無法顯示**：
   - 檢查攝影機是否正確連接
   - 檢查後端攝影機線程是否啟動
   - 查看後端日誌確認 MJPEG 串流狀態

3. **狀態不同步**：
   - 檢查 WebSocket 連接狀態
   - 確認 metadata 是否正常接收
   - 重新整理頁面重新建立連接

## 未來改進建議

1. **功能增強**：
   - 添加快捷鍵支援（空格鍵切換辨識）
   - 添加截圖功能
   - 添加錄影功能
   - 添加效能統計圖表

2. **使用者體驗**：
   - 添加操作提示（tooltips）
   - 添加引導教學（first-time user guide）
   - 添加深色/淺色主題切換
   - 添加語言切換（中文/英文）

3. **效能優化**：
   - 實作虛擬捲動（大量數據時）
   - 添加數據快取機制
   - 優化 re-render 效能

## 總結

✅ **已完成**：
- 現代化介面設計（頂部欄 + 側邊欄 + 主內容）
- YOLO 辨識控制功能（啟動/停止按鈕）
- 四個功能頁面（即時影像/Session/Metadata/設定）
- 完整的 CSS 樣式和響應式設計
- 與後端 API 完整整合
- 狀態自動同步

✅ **特色**：
- 簡潔直觀的操作介面
- 實時狀態監控
- 流暢的頁面切換
- 支援多裝置（桌面/平板/手機）

現在可以啟動系統，享受全新的撞球分析系統介面！🎱

## 05/14: '新增 CueVex 社群動態牆頁面'

### 功能範例
- 側邊欄主選單新增「社群」入口，點擊後進入 CueVex Community 動態牆。
- 社群頁提供 Stories 橫向列表、貼文卡片、撞球桌路線預覽、姿態分析預覽、統計預覽、熱門話題、推薦球會與本週挑戰。

### 規範用法
- 社群頁目前使用前端 mock/static data，不新增後端 API、不修改資料 schema。
- 愛心、收藏、分類 Tab 與排序選單只維持前端局部狀態。
- 新增動態、留言、分享、更多、熱門話題、推薦球會等按鈕先保留 UI 外觀，不進行頁面跳轉。
- 不移植 V0 的第二套 Home / Analysis / Training / Game / History 頂部導覽，避免與既有 Sidebar 導航衝突。

### 輸出格式
- 前端新增 `community` 頁面型別，透過 `Dashboard` 的 `renderPage()` 輸出 `CommunityPage`。
- i18n 新增 `nav.community`，繁中與簡中顯示「社群」，英文顯示 `Community`。

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 編譯通過。
- 手動確認側邊欄可進入社群頁，並可正常切回即時影像、回放、練習、遊戲與設定頁。

## 05/08: 新增介面深色/淺色主題切換功能

### 功能說明
- 前端介面支援 `dark`、`light`、`system` 三種主題模式。
- 預設為 `dark`，維持原本深色介面基調。
- 使用者選擇會儲存在瀏覽器 `localStorage`，key 為 `ncut.uiTheme`。
- `system` 模式會依瀏覽器 `prefers-color-scheme` 解析為深色或淺色，系統偏好改變時同步更新。

### 使用方式
- 進入 `設定 > 外觀`，在主題下拉選單選擇深色、淺色或跟隨系統。
- TopBar 右側提供快速切換按鈕，可在目前解析主題的深色與淺色之間切換。

### 實作規範
- `frontend/src/theme.ts` 定義 `ThemeMode`、`ResolvedTheme` 與主題儲存 key。
- `frontend/src/App.tsx` 負責讀取、儲存、解析主題，並在 `document.documentElement` 套用 `data-theme="dark"` 或 `data-theme="light"`。
- 核心 UI 樣式使用 `frontend/src/App.css` 的 CSS 變數，不直接依賴單一深色硬編碼。

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 建置通過。
- 驗證深色、淺色、跟隨系統都能立即套用，重新整理後保留選擇。

## 05/11: 新增外觀字體大小設定

### 功能說明
- 在 `設定 > 外觀 > 介面` 新增「字體大小」下拉選單。
- 支援四個固定級距：小 `95%`、標準 `100%`、大 `112.5%`、特大 `125%`。
- 預設值為「標準」，避免初次進入控制台時改變既有版面密度。

### 規範用法
- 前端以 `localStorage` 儲存使用者偏好，key 為 `ncut.uiFontSize`。
- App 層讀取後套用到 `document.documentElement.dataset.fontSize`。
- CSS 以 `--ui-font-scale` 控制關鍵共用元件字級，避免使用瀏覽器縮放造成整體畫面不可控。
- 放大時設定列與控制項允許自然增高，手機寬度維持單欄排列，避免橫向壓迫。

### 輸出格式
```ts
type FontSizeMode = 'small' | 'standard' | 'large' | 'xlarge';
```

對應 DOM 狀態：
```html
<html data-font-size="standard">
```

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 編譯通過。
- 進入 `設定 > 外觀 > 介面`，切換小、標準、大、特大後確認字體立即更新。
- 重新整理頁面後確認字體大小保留。
- 檢查深色、淺色、跟隨系統主題切換不受字體大小設定影響。

## 05/11: 新增外觀強調色設定

### 功能說明
- 在 `設定 > 外觀 > 介面` 的「介面主題」與「字體大小」之間新增「強調色」設定。
- 右側顯示目前強調色色號按鈕，背景為目前色號，文字會依背景亮度自動切換黑色或白色。
- 點擊按鈕後顯示 5 個色標，選取後立即更新主要按鈕與選取狀態的強調色。

### 規範用法
- 前端以 `localStorage` 儲存使用者偏好，key 為 `ncut.uiAccentColor`。
- 儲存值為語意模式，不直接儲存 hex，例如 `default`、`emerald`、`indigo`、`amber`、`cyan`。
- App 層依目前 resolved theme 套用 `--color-accent`、`--color-primary-bg`、`--color-focus` 與 `--color-primary-text`。
- 跟隨系統模式下，系統深淺色改變時會自動套用同一語意模式對應的 deep/light 色號。

### 色票定義
| 模式 | Dark | Light |
| --- | --- | --- |
| default | `#3B82F6` | `#2563EB` |
| emerald | `#10B981` | `#059669` |
| indigo | `#6366F1` | `#4F46E5` |
| amber | `#F59E0B` | `#D97706` |
| cyan | `#06B6D4` | `#0891B2` |

### 輸出格式
```ts
type AccentColorMode = 'default' | 'emerald' | 'indigo' | 'amber' | 'cyan';
```

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 編譯通過。
- 進入 `設定 > 外觀 > 介面`，確認「強調色」位於「介面主題」與「字體大小」之間。
- 點擊色號按鈕後確認 5 個色標選單可開啟，選色後按鈕色號與主要按鈕顏色立即更新。
- 重新整理頁面後確認強調色保留。
- 切換深色、淺色、跟隨系統後，確認同一語意模式會套用對應色號。

## 05/11: 新增球桌 ROI 設定子頁

### 功能說明
- 在 `設定 > 球桌校正` 點擊「微調邊框」後，右側設定內容區會切換為 ROI 四點邊框設定區。
- ROI 設定區不使用背景虛化、新視窗或彈窗遮罩；左側設定導覽與頂部系統列維持原樣。
- 設定區提供回復預設、重新框選、逐點微調、關閉與儲存並退出。

### 規範用法
- 影像來源沿用 burn-in MJPEG，並以 `quality=med&client_id=roi-polygon-editor` 載入。
- 影像區尺寸需與即時影像頁一致：最大寬度 `960px`、`aspect-ratio: 16 / 9`、黑底、`object-fit: contain`。
- 點擊影像依序建立四個角點；已有角點時可點選頂點，或按 `1`、`2`、`3`、`4` 切換頂點。
- 方向鍵或下方方向按鈕每次微調 1px；返回前若有未儲存變更，需顯示確認提示。

### 輸出格式
前端送往 `POST /api/table/roi-polygon` 的格式維持不變：

```json
{
  "points": [
    { "x": 57, "y": 20 },
    { "x": 1142, "y": 20 },
    { "x": 1142, "y": 546 },
    { "x": 57, "y": 546 }
  ]
}
```

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 編譯通過。
- 進入 `設定 > 球桌校正 > 微調邊框`，確認整個設定內容區切換為 ROI 設定區。
- 確認 ROI 設定區沒有背景虛化、新視窗或彈窗遮罩。
- 確認 ROI 影像維持 16:9，大小與即時影像頁一致，且控制列在桌面與窄螢幕不重疊。
- 驗證四點新增、選取、方向微調、重新框選、回復預設、關閉與儲存並退出皆正常。

## 05/11: 新增球色校正設定子頁

### 功能說明
- 在 `設定 > 球桌校正 > 球色校正` 的設定檔列表點擊「編輯」後，右側設定內容區會切換為球色校正設定區。
- 球色校正設定區不使用背景虛化、新視窗或彈窗遮罩；左側設定導覽與頂部系統列維持原樣。
- 設定區提供掃描目前球體、確認下一個顏色、回上一顆、跳過此顏色、進階 HSV 編輯、關閉與儲存並退出。

### 排版規格
- 子頁寬度為 `960px`，和 ROI/即時影像頁一致。
- 頂部狀態列左側顯示 `球色校正 - {模式} {設定檔名稱}`，右側顯示步驟、目前顏色 badge 與進度條。
- 相機參考畫面置於操作區上方，寬度 `100%`、`aspect-ratio: 16 / 9`、黑底、`object-fit: contain`。
- 操作區為單欄控制面板，避免窄螢幕壓縮；手機版按鈕可換行且高度至少 44px。

### 輸出格式
前端儲存時沿用 `PUT /api/color-calibration/profiles/{profile_id}/mappings`：

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

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 編譯通過。
- 點擊設定檔「編輯」後，確認整個設定內容區切換為球色校正設定區。
- 確認球色校正設定區沒有背景虛化、新視窗或彈窗遮罩。
- 驗證掃描、下一顆、上一顆、跳過、進階 HSV、關閉、儲存並退出皆正常。

## 05/11: 修正球色校正與投影校正語系切換

### 功能說明
- 球色校正設定子頁與投影機校正設定子頁所有使用者可見文字必須透過 `react-i18next` 的 `t()` 取得，不可在元件 JSX 或狀態訊息中硬編碼中文。
- 語系 key 放置於 `settings.tableCalibration.*` 與 `settings.projectorCalibration.*`，並同步維護 `zh-TW`、`zh-CN`、`en-US`。
- 後端回傳的錯誤訊息可原樣顯示；前端 fallback 訊息需使用 i18n key。

### 範例
```tsx
setColorModalMessage(t('settings.tableCalibration.scanningCurrentBall'));
<h2>{t('settings.projectorCalibration.livePreview')}</h2>
```

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 編譯通過。
- 切換到 English 後進入 `設定 > 球桌校正 > 球色校正`，確認模式、設定檔列表、掃描流程、按鈕、提示與儲存訊息顯示英文。
- 切換到 English 後進入 `設定 > 球桌校正 > 投影 > 投影機校正`，確認步驟列、投影預覽、標記控制、檢測頁與操作按鈕顯示英文。

## 05/11: 新增投影機校正設定子頁

### 功能說明
- 在 `設定 > 球桌校正 > 投影` 點擊「投影機校正」後，右側設定內容區會切換為投影機校正設定區。
- 投影機校正設定區不使用背景虛化、新視窗或彈窗遮罩；左側設定導覽與頂部系統列維持原樣。
- 關閉或儲存退出時沿用投影機校正頁的清理流程，將投影機模式切回 `idle`。

### 排版規格
- 子頁寬度為 `960px`，和 ROI/即時影像頁一致。
- 第一階段上方顯示投影機即時畫面預覽，維持 `aspect-ratio: 16 / 9`、黑底、`object-fit: contain`。
- 預覽下方控制區分成兩欄：左下以「目前控制」取代「選擇標記」標題並顯示目前標記座標，右下為無外框卡片的「移動控制」。
- 移動控制按鍵採鍵盤方向鍵排列並對齊，上排為 `↑`，下排為 `← ↓ →`。
- 底部操作列維持「重置位置」、「關閉」、「儲存並退出」。

### 驗證方式
- 執行 `cd frontend && npm run build`，確認 TypeScript 與 Vite 編譯通過。
- 點擊「投影機校正」後，確認整個設定內容區切換為投影機校正設定區。
- 確認投影機校正設定區沒有背景虛化、新視窗或彈窗遮罩。
- 確認「目前控制」與標記選擇位於左下，「移動控制」位於右下，方向鍵與方向按鈕皆可移動目前標記。
