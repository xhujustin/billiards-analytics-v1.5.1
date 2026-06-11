# AI Coach Cloudflare Desktop Remote Access

## 06/05:'新增 AI Coach Cloudflare 桌面遠端啟動'

### 功能規範

- `start_desktop_remote_ai_coach.bat` 用於讓其他裝置透過瀏覽器使用本機電腦端 CueVex 與 AI Coach。
- 本機會啟動三個服務：
  - AI Coach WebSocket service：`http://127.0.0.1:8010`，WebSocket 為 `ws://localhost:8010/ws/coach`。
  - FastAPI 後端：`http://127.0.0.1:8001`。
  - Vite 前端：`http://127.0.0.1:3000`。
- Cloudflare Quick Tunnel 只公開後端與前端，不公開 `8010/ws/coach`。
- 外部裝置只需要開啟腳本輸出的 Frontend URL；前端會使用腳本注入的 `VITE_BACKEND_URL` 與 `VITE_BACKEND_WS` 連到公開後端。
- `https://*.trycloudflare.com` 是臨時網址，每次重新啟動可能改變。

### 啟動方式

在專案根目錄執行：

```bat
start_desktop_remote_ai_coach.bat
```

腳本會依序執行：

1. 檢查 `.venv\Scripts\python.exe`、Node.js 與 `cloudflared`。
2. 若 AI Coach health check 不通，啟動 `start_ai_coach.bat` 並等待 vLLM 與 AI Coach ready。
3. 啟動後端，並設定 `AI_COACH_WS_URL=ws://localhost:8010/ws/coach`。
4. 建立後端 Cloudflare Quick Tunnel，取得 `BACKEND_PUBLIC_URL`。
5. 以 `VITE_BACKEND_URL=%BACKEND_PUBLIC_URL%` 與 `VITE_BACKEND_WS=wss://...` 啟動前端。
6. 建立前端 Cloudflare Quick Tunnel，輸出其他裝置可開啟的 Frontend URL。

### 輸出格式

啟動成功後會顯示：

```text
Open this URL on other devices:
  https://frontend-example.trycloudflare.com

Public Backend API:
  https://backend-example.trycloudflare.com

Local checks:
  AI Coach: http://127.0.0.1:8010/health
  Backend:  http://127.0.0.1:8001/health
  Coach:    http://127.0.0.1:8001/api/coach/state
```

其他裝置請只開啟 `Open this URL on other devices` 下方的前端網址。

### 驗證規範

- `http://127.0.0.1:8010/health` 需回應 AI Coach health payload。
- `http://127.0.0.1:8001/health` 需回應後端 health payload。
- `http://127.0.0.1:8001/api/coach/state` 應顯示 `connected: true`。
- 其他裝置開啟前端 Cloudflare URL 後，AI Coach 對話與「產生建議」需透過 `/api/coach/chat` 或 `/api/coach/suggest` 回覆。

### 故障排除

- 若 AI Coach 等待逾時，先查看 `CueVex AI Coach Service` 視窗，通常是 vLLM 模型載入、WSL 或 GPU 設定尚未 ready。
- 若前端可開啟但 AI Coach 回覆失敗，先檢查 `http://127.0.0.1:8001/api/coach/state` 的 `connected` 與 `last_error`。
- 若其他裝置看到舊頁面或舊後端，重新執行腳本並使用新的 `trycloudflare.com` 前端網址。
- 若 Vite 擋下 tunnel host，確認 `frontend/vite.config.js` 的 `server.allowedHosts` 包含 `.trycloudflare.com`。

## 06/11:'整合 start_ai_coach.bat 自動 Cloudflare 遠端啟動'

### 功能規範

- 06/11 後續調整：固定 Cloudflare Named Tunnel 只用於 AI Coach，不再讓 `start_ai_coach.bat` 預設啟動整個 desktop remote。
- `start_ai_coach.bat` 現在只啟動本機 AI Coach WebSocket service；Cloudflare Named Tunnel 由已安裝的 `cloudflared` Windows service 常駐處理。
- `start_desktop_remote_ai_coach.bat` 保留為手動展示整個 desktop frontend/backend 的 Quick Tunnel 工具，只有明確需要整個桌面遠端時才執行。
- `AI_COACH_DRY_RUN=1` 仍可用於檢查 AI Coach 本體設定。

### 規範用法

啟動 AI Coach 本體：

```bat
start_ai_coach.bat
```

需要整個桌面前端/後端 Quick Tunnel 展示時，才另外執行：

```bat
start_desktop_remote_ai_coach.bat
```

### 輸出格式

Named Tunnel 固定網址由 Cloudflare Zero Trust 的 Public Hostname 設定決定；若使用手動 desktop remote Quick Tunnel，終端會輸出：

```text
Open this URL on other devices:
  https://frontend-example.trycloudflare.com

Public Backend API:
  https://backend-example.trycloudflare.com
```

其他裝置請開啟 `Open this URL on other devices` 下方的 Frontend URL。`trycloudflare.com` 是臨時網址，每次重新啟動可能改變。

## 06/11:'調整為 AI Coach 專用 Named Tunnel'

### 功能規範

- 固定網址模式只需要 Cloudflare Public Hostname 指向 AI Coach 相關服務，不需要把整個桌面 frontend/backend 都放到 Quick Tunnel。
- 本機 `cloudflared` 已安裝為 Windows service 後，`start_ai_coach.bat` 只負責啟動 `http://127.0.0.1:8010`。
- 若公開的是原始 AI Coach service，Cloudflare Public Hostname service 指向 `http://localhost:8010`。
- 若公開的是 CueVex 後端 bridge，Cloudflare Public Hostname service 指向 `http://localhost:8001`，外部只使用 `/api/coach/chat`、`/api/coach/suggest`、`/api/coach/state`。

### 建議設定

安全性較好的設定是公開 backend bridge，而不是直接公開 `8010/ws/coach`：

```text
coach-api.your-domain.com -> http://localhost:8001
backend -> ws://localhost:8010/ws/coach
```

如果只要 AI Coach WebSocket 本體，則設定：

```text
coach.your-domain.com -> http://localhost:8010
```

## 06/11:'修正遠端 AI Coach 顯示為本機 WebSocket 的誤導'

### 功能規範

- 遠端模式下，AI Coach 對話與產生建議走公開 Backend API：`https://backend-example.trycloudflare.com/api/coach/chat` 與 `/api/coach/suggest`。
- `8010/ws/coach` 仍只作為本機內部 bridge，由 backend 連線，不直接公開給其他裝置。
- 遠端啟動腳本現在把 `VITE_AI_COACH_WS` 顯示為 `https://backend-example.trycloudflare.com/api/coach`，避免設定頁誤顯示 `ws://localhost:8010/ws/coach`。

### 驗證方式

```bat
start_ai_coach.bat
```

啟動後確認：

```text
Coach: http://127.0.0.1:8001/api/coach/state
```

應回傳 `connected: true`。其他裝置只需要開啟 Frontend URL，AI Coach 會透過公開 Backend API 轉送，不需要也不能直接連 `localhost:8010`。
