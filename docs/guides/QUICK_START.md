# 快速啟動指南

## 🚀 啟動步驟

### 1. 啟動後端
```bash
cd backend
python main.py
```

**預期輸出**：
```
✅ YOLO model loaded successfully
✅ Calibrator initialized successfully
✅ MJPEG Stream Manager initialized
🚀 Starting camera capture thread for burn-in stream...
🎥 Starting camera capture loop for burn-in stream...
✅ Camera opened successfully...
```

### 2. 啟動前端
```bash
cd frontend
npm run dev
```

**預期輸出**：
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 3. 訪問介面

打開瀏覽器訪問：**http://localhost:5173**

## 🎯 使用 YOLO 辨識

1. **點擊頂部的** 🟢 **啟動辨識** 按鈕
2. 觀察即時影像出現物件檢測框和軌跡線
3. 查看下方狀態卡片顯示辨識數據
4. **點擊** 🔴 **停止辨識** 按鈕停止

## 📁 檔案結構

```
frontend/src/components/
├── Dashboard.tsx          # 主組件
├── Dashboard.css         # 主樣式
├── Layout.tsx            # 佈局框架
├── TopBar.tsx            # 頂部欄（含按鈕）
├── Sidebar.tsx           # 側邊欄
└── pages/
    ├── StreamPage.tsx    # 即時影像頁面
    ├── SessionPage.tsx   # Session 頁面
    ├── MetadataPage.tsx  # Metadata 頁面
    └── SettingsPage.tsx  # 設定頁面
```

## ✅ 功能檢查清單

- [ ] 後端成功啟動，攝影機正常運行
- [ ] 前端成功連接，WebSocket 狀態為「已連接」
- [ ] Burn-in 影像正常顯示
- [ ] 點擊「啟動辨識」後，影像出現檢測框
- [ ] YOLO 狀態卡片顯示「已啟用」
- [ ] 點擊「停止辨識」後，影像恢復原始畫面
- [ ] 側邊欄可以正常切換頁面

## 🐛 常見問題

### 問題 1: 攝影機無法開啟
**解決方案**：
- 檢查攝影機是否被其他程式佔用
- 嘗試更改 `backend/config.py` 中的 `CAMERA_DEVICE` 設定

### 問題 2: 前端無法連接後端
**解決方案**：
- 確認後端運行在 `http://localhost:8001`
- 檢查 `frontend/.env` 中的 API URL 設定

### 問題 3: YOLO 辨識無反應
**解決方案**：
- 查看瀏覽器控制台是否有錯誤訊息
- 檢查後端日誌確認 YOLO 模型是否正確載入

## 📖 詳細文檔

請參閱：
- [YOLO_CONTROL_UI.md](YOLO_CONTROL_UI.md) - 完整使用說明
- [BURN_IN_FIX.md](BURN_IN_FIX.md) - Burn-in 串流修復說明

## 🎉 享受使用！

## 05/26: 新增主程式與 AI Coach 分離啟動

主程式與 AI Coach 現在使用不同批次檔啟動：

```bat
start.bat
```

啟動主程式：Backend `http://localhost:8001` 與 Frontend `http://localhost:3000`。

```bat
start_ai_coach.bat
```

啟動 AI Coach WebSocket service：`ws://localhost:8010/ws/coach`，並沿用 `ai_coach\start.bat` 內的 vLLM 自動啟動設定。

規範用法：
- 只需要追蹤、投影、錄影與前端操作時，只執行 `start.bat`。
- 需要 AI Coach 對話或建議時，另外開一個終端執行 `start_ai_coach.bat`。
- `start.bat` 不再等待 AI Coach health check；AI Coach 未啟動時，主程式仍可獨立啟動。

輸出格式：
- 主程式視窗會顯示 Backend、Frontend、API Docs 與串流網址。
- AI Coach 視窗會顯示 Host、Port、vLLM API、Model 與 service 啟動狀態。

## 05/26: 修正啟動時 YOLO 只辨識半桌問題

修正內容：
- 啟動初期 HSV 偵測若只抓到局部球桌 ROI，系統會再使用暗色袋口幾何估算完整球桌範圍。
- 當袋口估算範圍明顯大於 HSV ROI 時，YOLO 會改用完整 ROI 執行辨識，避免右半邊球未進入裁切範圍。
- 若舊版手動 ROI 是用 `1280x720` 監控畫面座標儲存，後端在 `1920x1080` 相機畫面第一幀會自動縮放到原始解析度，避免啟動後只裁左半桌。

規範用法：
- 正常啟動仍使用 `start.bat`。
- 若即時影像綠色框仍明顯只覆蓋半張球桌，先到 ROI 四點邊框設定區清除舊 ROI，再重新框選四角。

輸出格式：
- 修正後的 table ROI 狀態可能顯示為 `hsv_pocket_expand` 或 `preset-*_pocket_expand`。
- 舊版手動 ROI 被自動轉換時，table ROI 狀態會顯示為 `manual_polygon_scaled`。
- YOLO metadata 會沿用修正後的 `table_roi`、`table_roi_raw` 與 `table_roi_status`。

## 05/26: 修正 AI Coach 收起後聊天室殘留

修正內容：
- AI Coach 側欄收起時，主畫面嵌入式聊天室會同步消失。
- 聊天室顯示條件改為同時需要 AI Coach 可用頁面、側欄展開、聊天室開啟且有作用中對話。
- AI Coach 側欄展開狀態改由主頁狀態控制，預設為收起，避免側欄內部狀態與聊天室狀態不同步。

規範用法：
- 點擊側欄 `AI 教練` 收起後，只保留主工作區內容。
- 重新展開 `AI 教練` 並選擇或新增對話後，聊天室才會再次出現。

輸出格式：
- 收起狀態下主內容區不再套用 AI Coach 雙欄版面。
- 展開且開啟對話時維持原本聊天室與即時影像雙欄版面。

## 05/26: 固定即時影像監控欄

修正內容：
- 桌面版即時影像右側監控欄移除垂直滾輪。
- 監控欄改為固定高度版面，影像卡與狀態卡維持在同一個視窗工作區內。

規範用法：
- 桌面監控頁不再捲動右側欄，主要操作維持在固定畫面內。
- 小螢幕版保留垂直排列與頁面捲動，避免內容被裁切。

輸出格式：
- `.stream-content-column` 桌面版使用固定 grid 版面與 `overflow: hidden`。
- `900px` 以下維持原本 `display: block` 與可見溢出內容。

## 05/26: 修正側欄卡片與 AI Coach 對話選單裁切

修正內容：
- 側欄本身不再使用卡片外框，避免左側設定入口看起來像獨立卡片。
- 右側主畫面與功能面板維持原有卡片式內容容器。
- AI Coach 對話列表的三點選單改用視窗固定座標定位，不再受到對話清單捲動容器裁切。

規範用法：
- 點擊 AI Coach 對話旁的 `...` 後，`重新命名`、`置頂/取消置頂`、`刪除對話` 選單必須完整顯示。
- 點擊側欄空白處、切換對話、切換設定或執行選單動作時，開啟中的對話選單會自動關閉。

輸出格式：
- `.sidebar` 保持無外框與無圓角。
- `.sidebar-coach-session-dropdown` 使用 `position: fixed` 與計算後的 `left/top` 座標。

## 05/26: 調整左側欄間距與背景對比

修正內容：
- 左側欄整體左邊距由 `20px` 縮小為 `8px`，項目文字內距由 `12px` 縮小為 `8px`。
- AI Coach 對話列、空狀態文字與設定選單項目的水平內距同步縮小。
- 側欄背景改為深藍灰漸層面，與主頁深黑背景形成對比，但維持無卡片外框。

規範用法：
- 側欄文字需要靠近左側欄起點，避免主導覽看起來被推太右。
- 側欄可有背景區隔，但不可恢復厚重卡片邊框與大圓角。

輸出格式：
- `.sidebar` 使用 `var(--color-surface-raised)`，並以 `var(--color-border)` 作右側分隔。
- `.sidebar-item` 使用 `padding: 0 8px`。

## 06/05: 遊戲頁啟用 AI 教練側欄與側拉收合

修正內容：
- 遊戲頁左側欄改為與其他主頁一致，顯示 `AI 教練` 對話入口，不再回退為舊版主選單。
- 左側欄新增右邊界側拉收合把手，展開時不佔用 AI 教練列空間，收合時只保留窄側欄與展開把手。
- AI 教練嵌入式聊天室允許在遊戲頁顯示，與監控、訓練、歷史頁的行為一致。

規範用法：
- 將游標移到側欄右邊界可顯示收合把手，點擊後可收合或展開整個左側欄。
- 點擊遊戲頁側欄 `AI 教練` 可開合 AI 教練對話清單；選擇或新增對話後，主內容左側會顯示嵌入式聊天室。
- 側欄收合只影響左側欄可視寬度，不清除目前頁面、AI 教練對話或設定選單狀態。

輸出格式：
- `.sidebar.is-collapsed` 使用 42px 窄欄寬度。
- `.sidebar-collapse-toggle` 是側欄右邊界細把手，展開狀態預設透明、hover 或 focus 時顯示，提供 `收合側欄` / `展開側欄` aria label。

## 05/28: 移除社群頁並統一主題配色

修正內容：
- 前端社群頁已從頂部導覽、側欄頁面型別與 Dashboard 頁面渲染中移除。
- 刪除未再使用的 `CommunityPage.tsx`、`CommunityPage.css` 與 `communityClient.ts`。
- 頂欄、側欄、即時影像、訓練中心與遊戲頁的舊硬寫青色/深色底，改為使用設定頁同一組 theme token。

規範用法：
- 新增頁面或元件時，背景、卡片、文字、邊框需使用 `--color-app-bg`、`--color-surface-*`、`--color-text-*`、`--color-border*`。
- 互動主色、選取狀態、路線或重點標示需使用 `--color-accent`、`--color-primary-bg`、`--color-primary-text`。
- 不可再新增 `community` 導覽項目或 `community` PageType。

輸出格式：
- 主導覽不顯示社群。
- 強調色切換後，頂欄 active、側欄 active、訓練卡片重點色與即時影像 YOLO 框線會跟著設定頁強調色變化。

## 06/11: '整合 AI Coach 啟動腳本自動 Cloudflare 遠端啟動'

06/11 後續調整：固定 Cloudflare Named Tunnel 只用在 AI Coach。`start_ai_coach.bat` 現在只啟動本機 AI Coach/vLLM，不再預設啟動桌面前端、後端與 Quick Tunnel。

```bat
start_ai_coach.bat
```

固定網址由 `cloudflared` Windows service 與 Cloudflare Public Hostname 管理，不由 `start_ai_coach.bat` 產生。

若臨時需要整個 desktop frontend/backend Quick Tunnel 展示，才使用：

```bat
start_desktop_remote_ai_coach.bat
```

該展示模式啟動完成後會輸出：

```text
Open this URL on other devices:
  https://frontend-example.trycloudflare.com

Public Backend API:
  https://backend-example.trycloudflare.com
```

AI Coach 專用 Named Tunnel 建議設定：

```text
coach-api.your-domain.com -> http://localhost:8001
backend -> ws://localhost:8010/ws/coach
```
