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
