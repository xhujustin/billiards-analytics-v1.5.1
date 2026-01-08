# 撞球分析系統 v1.5

基於 v1.5 協議規範的完整撞球分析系統，包含後端（Python/FastAPI）與前端（React/TypeScript）。

##  文檔導航

**完整文檔請查看：[docs/README.md](docs/README.md)**

### 快速連結
-  [快速啟動指南](docs/guides/QUICK_START.md) - 5分鐘內啟動系統
-  [YOLO控制介面](docs/guides/YOLO_CONTROL_UI.md) - 了解主要功能
-  [故障排除](docs/troubleshooting/DEBUGGING_GUIDE.md) - 常見問題解決
-  [API參考](docs/api/API_REFERENCE.md) - 開發者文檔

## 專案結構

```
billiards-analytics-test/
├── backend/                 # Python 後端
│   ├── main.py             # FastAPI 主程式（v1.5 REST + WebSocket）
│   ├── config.py           # 環境配置管理
│   ├── session_manager.py  # Session 生命週期管理
│   ├── tracking_engine.py  # YOLO 追蹤引擎
│   ├── calibration.py      # 攝像機校準
│   ├── mjpeg_streamer.py   # MJPEG 串流管理
│   ├── requirements.txt    # Python 依賴
│   └── .env.example        # 環境變數範例
│
├── frontend/               # React 前端
│   ├── src/
│   │   ├── sdk/           # v1.5 SDK 核心
│   │   │   ├── types.ts             # TypeScript 型別定義
│   │   │   ├── SessionManager.ts    # Session 管理
│   │   │   ├── WebSocketManager.ts  # WebSocket 客戶端
│   │   │   ├── ConnectionHealthMachine.ts  # 健康度狀態機
│   │   │   ├── MetadataBuffer.ts    # Metadata 緩衝
│   │   │   └── index.ts             # SDK 統一接口
│   │   ├── hooks/
│   │   │   └── useBilliardsSDK.ts   # React Hooks
│   │   ├── components/
│   │   │   └── Dashboard.tsx        # 儀表板組件
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── .env
│
└── docs/                   # 完整技術文檔
    ├── README.md           # 文檔導航中心
    ├── guides/             # 使用指南
    ├── troubleshooting/    # 故障排除
    ├── architecture/       # 架構設計
    └── api/                # API參考文檔
```

## 快速開始

### 後端設置

1. **創建虛擬環境並安裝依賴**
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

2. **配置環境變數**
```bash
cp .env.example .env
# 編輯 .env 文件，調整配置
```

3. **啟動後端**
```bash
python main.py
```

後端將在 `http://localhost:8001` 啟動

### 前端設置

1. **安裝依賴**
```bash
cd frontend
npm install
```

2. **啟動開發伺服器**
```bash
npm run dev
```

前端將在 `http://localhost:5173` 啟動

## v1.5 核心功能

### 後端特性

**REST API（完整實現）**
- `GET /api/streams` - 列出可用影像來源
- `GET /api/stream/status` - 獲取串流狀態
- `POST /api/sessions` - 創建 session
- `POST /api/sessions/{id}/renew` - 續期 session
- `POST /api/sessions/{id}/switch_stream` - 切換串流
- `DELETE /api/sessions/{id}` - 刪除 session
- `GET /api/config` - 獲取系統配置

**WebSocket 控制通道**
- v1 Envelope 格式（`{v, type, ts, session_id, stream_id, payload}`）
- Protocol Negotiation（protocol.hello / protocol.welcome）
- Heartbeat（每 3 秒，server → client）
- Client Heartbeat（每 5 秒，client → server）
- Metadata Update（10Hz，可配置）
- Stream Changed（強制切換 + ACK）
- Session Revoked（Kick-Old 策略）
- Command 系統（cmd.* / cmd.ack / cmd.error）

**標準化錯誤處理**
- 12 種錯誤碼（ERR_INVALID_ARGUMENT, ERR_NOT_FOUND, ERR_FORBIDDEN, ERR_RATE_LIMIT, ERR_SESSION_EXPIRED, ERR_STREAM_UNAVAILABLE, ERR_INVALID_COMMAND, ERR_UNSUPPORTED_VERSION, ERR_BACKEND_BUSY, ERR_CALIBRATION_REQUIRED, ERR_STREAM_CONFLICT, ERR_INTERNAL）
- 支援國際化（i18n）
- 統一 ApiErrorResponse 格式：`{error: {code, message, details?}}`

**Burn-in MJPEG 串流**
- `GET /burnin/{stream_id}.mjpg?quality=low|med|high`
- 後端合成 overlay，前端直接播放
- 支持 camera1, projector, file1
- 錯誤畫面自動重試（最多 3 次）

**Session 管理**
- 自動過期與續期
- Kick-Old 策略（同 session_id 僅允許一條 WS）
- 權限與角色管理（viewer/operator/developer/admin）

### 前端特性

**完整 SDK**
- TypeScript 型別安全（1:1 對應 v1.5 Protocol Schema）
- SessionManager（自動續期、fallback，續期視窗 = min(ttl*0.2, 5min)）
- WebSocketManager（重連策略：exponential backoff + jitter，maxRetries=5, baseDelay=1s, maxDelay=30s）
- ConnectionHealthMachine（CHS 狀態機：DISCONNECTED / STALE / NO_SIGNAL / DEGRADED / HEALTHY）
  - 優先級排序：DISCONNECTED > STALE > NO_SIGNAL > DEGRADED > HEALTHY
  - STALE → HEALTHY 需連續 2 次健康心跳（防止抖動）
  - 心跳逾時：6000ms，畫面逾時：2000ms，最低 FPS：10
- MetadataBuffer（高頻緩衝與節流，buffer 上限 100，latest-first 採樣避免 UI 卡頓）

**React Hooks**
- `useBilliardsSDK` - SDK 主 Hook
- 自動連接管理
- 狀態訂閱

**UI 組件**
- Dashboard（即時監控面板）
- 連接狀態指示器
- Session 資訊顯示
- Burn-in 影像播放
- Metadata 即時數據

## 配置說明

### 後端環境變數（.env）

```env
# YOLO 模型
MODEL_PATH=yolo-weight/pool-n.pt
CONF_THR=0.35
IOU_THR=0.50

# 攝像機設置
CAMERA_WIDTH=1920
CAMERA_HEIGHT=1080
CAMERA_FPS=50

# Session 設置（v1.5）
SESSION_TTL=3600                  # Session 有效期（秒）
SESSION_RENEW_WINDOW=0.2          # 續期視窗比例（20%）
SESSION_MIN_RENEW_WINDOW=300      # 最小續期視窗（5分鐘）

# WebSocket 設置（v1.5）
WS_HEARTBEAT_INTERVAL=3           # Heartbeat 間隔（秒）
WS_CLIENT_TIMEOUT=15              # Client heartbeat 超時（秒）

# Metadata 設置（v1.5）
METADATA_RATE_HZ=10               # Metadata 推送頻率（10Hz）
METADATA_BUFFER_SIZE=100          # Buffer 大小限制

# Feature Flags
ENABLE_DEV_MODE=false
ENABLE_REPLAY=false
```

### 前端環境變數（.env）

```env
VITE_BACKEND_URL=http://localhost:8001
VITE_BACKEND_WS=ws://localhost:8001
```

## API 使用範例

### 創建 Session

```bash
curl -X POST http://localhost:8001/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "stream_id": "camera1",
    "role_requested": "operator",
    "client_info": {"user": "test"}
  }'
```

### 連接 WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/control?session_id=s-xxx');

ws.onmessage = (event) => {
  const envelope = JSON.parse(event.data);
  console.log('Received:', envelope.type, envelope.payload);
};
```

### 播放 Burn-in

```html
<img src="http://localhost:8001/burnin/camera1.mjpg?quality=med" />
```

## 開發指南

### 新增 WebSocket 消息類型

1. 在 `frontend/src/sdk/types.ts` 添加 payload 型別
2. 在 `backend/main.py` 的 `control_websocket` 處理對應消息
3. 在前端訂閱：`sdk.wsManager.on('your.type', handler)`

### 新增 REST API

1. 在 `backend/main.py` 添加 FastAPI 路由
2. 在 `frontend/src/sdk/types.ts` 添加回應型別
3. 在前端調用：`fetch('/api/your-endpoint')`

## 性能優化

### 後端
- YOLO 跳幀處理（`yolo_skip_frames`）
- 線程池異步處理（MJPEG 編碼）
- Metadata 頻率限制（10Hz）

### 前端
- MetadataBuffer 節流（1Hz UI 更新）
- Latest-first 採樣策略
- Buffer 上限避免記憶體洩漏

## 🔍 故障排除

遇到問題？查看我們的完整故障排除指南：

### 常見問題快速連結
-  [系統啟動無反應](docs/troubleshooting/DEBUGGING_GUIDE.md) - YOLO檢測失效、無法啟動
-  [影像黑屏問題](docs/troubleshooting/BLACK_SCREEN_FIX.md) - 切換畫質後黑屏
-  [球桌檢測問題](docs/troubleshooting/TABLE_DETECTION_FIX.md) - 無法檢測球桌（table抓不到）
-  [串流相關問題](docs/troubleshooting/BURN_IN_FIX.md) - 即時影像無法顯示

### WebSocket 連接失敗
- 檢查後端是否啟動：`http://localhost:8001/health`
- 檢查 session_id 是否有效
- 查看瀏覽器 Console 錯誤訊息
- 確認 protocol.welcome 已收到（版本協商完成）

### Session 過期
- 檢查 `SESSION_TTL` 配置
- 確認自動續期已啟用（`autoRenew: true`）
- 查看後端 log 的續期記錄

**更多診斷資訊請參考：[完整故障排除文檔](docs/troubleshooting/)**

---

## 更多文檔

- **[完整文檔中心](docs/README.md)** - 所有技術文檔的索引
- **[API參考手冊](docs/api/API_REFERENCE.md)** - REST API與WebSocket完整規範
- **[架構設計文檔](docs/api/ARCHITECTURE.md)** - 系統架構深入解析
- **[實作指南](docs/api/IMPLEMENTATION_GUIDE.md)** - 前後端開發指南

## 授權

MIT License

## 相關文檔

- [API_REFERENCE.md](V1.5/API_REFERENCE.md) - API 參考
- [ARCHITECTURE.md](V1.5/ARCHITECTURE.md) - 系統架構
- [IMPLEMENTATION_GUIDE.md](V1.5/IMPLEMENTATION_GUIDE.md) - 實作指南
- [TROUBLESHOOTING.md](V1.5/TROUBLESHOOTING.md) - 故障排除
