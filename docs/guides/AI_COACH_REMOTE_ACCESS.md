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
