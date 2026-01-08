# V1.5 Protocol 完整性檢查清單

## ✅ 已完成的 P0 核心功能

### 後端實現
- [x] REST API
  - [x] `POST /api/sessions` - 建立 Session
  - [x] `POST /api/sessions/{id}/renew` - 續期
  - [x] `DELETE /api/sessions/{id}` - 撤銷
  - [x] `GET /api/stream/list` - Stream 列表
  - [x] `GET /api/stream/status` - Stream 狀態
  - [x] `GET /api/config` - 系統配置
  - [x] 標準化錯誤處理（12 種 ERR_* 錯誤碼）

- [x] WebSocket 控制通道
  - [x] v1 Envelope 格式：`{v, type, ts, session_id, stream_id, payload}`
  - [x] `protocol.hello` / `protocol.welcome` - 版本協商
  - [x] `heartbeat` - Server → Client（每 3 秒）
  - [x] `client.heartbeat` - Client → Server（每 5 秒）
  - [x] `metadata.update` - 即時數據推送（10Hz）
  - [x] `session.revoked` - Kick-Old 通知
  - [x] `stream.changed` + `stream.changed.ack` - Stream 切換
  - [x] `cmd.*` / `cmd.ack` / `cmd.error` - 命令系統

- [x] MJPEG Burn-in 串流
  - [x] `GET /burnin/{stream_id}.mjpg?quality=low|med|high`
  - [x] 後端 overlay 合成
  - [x] DualMJPEGManager（原始 + Burn-in）

- [x] Session 管理
  - [x] SessionManager 類（session_manager.py）
  - [x] TTL 機制（預設 3600 秒）
  - [x] Kick-Old 策略（同 session_id 僅一條 WS）
  - [x] 角色與權限（viewer/operator/developer/admin）

- [x] 錯誤處理
  - [x] error_codes.py（12 種錯誤碼定義）
  - [x] create_error_response() 工具函數
  - [x] 所有 REST API 返回 JSONResponse 標準錯誤格式

### 前端實現
- [x] TypeScript 型別定義（types.ts）
  - [x] ProtocolVersion = 1
  - [x] WSMessageType 聯合型別（12 種消息類型）
  - [x] CmdErrorPayload.code（12 種錯誤碼）
  - [x] Session, SessionRole, SessionState
  - [x] Detection, Keypoint, Prediction 介面
  - [x] ApiErrorResponse, PerformanceMetrics

- [x] SessionManager（SessionManager.ts）
  - [x] createSession(), restoreSession()
  - [x] 自動續期（scheduleRenew）
  - [x] 續期視窗計算：`min(ttl * 0.2, 5min)`
  - [x] localStorage 持久化

- [x] WebSocketManager（WebSocketManager.ts）
  - [x] v1 Envelope 解析
  - [x] Protocol Negotiation（sendProtocolHello）
  - [x] Exponential Backoff 重連策略
    - [x] maxRetries = 5
    - [x] baseDelay = 1000ms
    - [x] maxDelay = 30000ms
    - [x] jitter = ±20%（防止 thundering herd）
  - [x] 心跳監控

- [x] ConnectionHealthMachine（ConnectionHealthMachine.ts）
  - [x] 5 級健康狀態：DISCONNECTED / STALE / NO_SIGNAL / DEGRADED / HEALTHY
  - [x] 優先級排序（updateHealth 取最差狀態）
  - [x] STALE → HEALTHY 需連續 2 次健康心跳
  - [x] 閾值常量
    - [x] HEARTBEAT_TIMEOUT_MS = 6000
    - [x] FRAME_TIMEOUT_MS = 2000
    - [x] MIN_FPS = 10

- [x] MetadataBuffer（MetadataBuffer.ts）
  - [x] 高頻緩衝（buffer 上限 100）
  - [x] Latest-first 採樣
  - [x] Throttle 訂閱（1Hz UI 更新）

- [x] BilliardsSDK 主入口（index.ts）
  - [x] initialize() 傳遞 session_id/stream_id
  - [x] 事件處理器設置
    - [x] protocol.welcome
    - [x] heartbeat
    - [x] metadata.update
    - [x] session.revoked（清除 localStorage）
    - [x] stream.changed + ACK
    - [x] cmd.error

- [x] React 整合
  - [x] useBilliardsSDK Hook
  - [x] Dashboard 組件
  - [x] MJPEG 錯誤處理（最多重試 3 次）
  - [x] CHS 狀態顏色映射

## ✅ 已完成的 P1 進階功能

- [x] Protocol Negotiation
  - [x] protocol.hello（client → server）
  - [x] protocol.welcome（server → client）
  - [x] negotiatedVersion 追蹤

- [x] Client Heartbeat
  - [x] 前端每 5 秒發送 client.heartbeat
  - [x] 後端 session_manager.update_heartbeat()

- [x] MJPEG 畫質選項
  - [x] quality=low/med/high 參數
  - [x] DualMJPEGManager 動態調整

- [x] Session Renewal Fallback
  - [x] localStorage 持久化
  - [x] restoreSession() 自動恢復
  - [x] 續期失敗時的錯誤處理

## 📋 未實現的 P2 功能（可選）

- [ ] Stream Failover（後端自動切換備用 Stream）
- [ ] Multi-table 支援（同時追蹤多張桌子）
- [ ] Replay 系統（歷史回放）
- [ ] Advanced Calibration（自動校正）
- [ ] Performance Metrics API（詳細效能指標）

## 🧪 測試驗證項目

### 手動測試
1. [ ] 啟動 backend（`.\start.ps1`）
2. [ ] 啟動 frontend（`npm run dev`）
3. [ ] 訪問 http://localhost:5173
4. [ ] 確認 Dashboard 顯示 Session 資訊
5. [ ] 確認 WebSocket 狀態為「已連接」
6. [ ] 確認 Health 從 STALE → HEALTHY
7. [ ] 確認 Burn-in 影像正常播放
8. [ ] 確認 Metadata 數據即時更新
9. [ ] 測試 Session 自動續期（等待續期視窗）
10. [ ] 測試重新整理頁面（restoreSession）
11. [ ] 測試斷開 backend（重連策略）
12. [ ] 測試 MJPEG 錯誤重試（中斷 camera）

### API 測試
```bash
# 健康檢查
curl http://localhost:8001/health

# 建立 Session
curl -X POST http://localhost:8001/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"stream_id":"camera1","role_requested":"operator"}'

# Stream 列表
curl http://localhost:8001/api/stream/list

# Stream 狀態
curl "http://localhost:8001/api/stream/status?stream_id=camera1"

# 系統配置
curl http://localhost:8001/api/config
```

### WebSocket 測試
```javascript
// 瀏覽器 Console
const ws = new WebSocket('ws://localhost:8001/ws/control?session_id=xxx');

ws.onopen = () => {
  console.log('✅ Connected');
  // 發送 protocol.hello
  ws.send(JSON.stringify({
    v: 1,
    type: 'protocol.hello',
    ts: Date.now(),
    payload: { preferred_version: 1 }
  }));
};

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  console.log('📨', msg.type, msg.payload);
};
```

## 📊 協議符合度評分

| 分類 | 功能數 | 已實現 | 符合度 |
|------|--------|--------|--------|
| P0 REST API | 6 | 6 | 100% |
| P0 WebSocket | 8 | 8 | 100% |
| P0 Session 管理 | 4 | 4 | 100% |
| P0 錯誤處理 | 12 | 12 | 100% |
| P1 進階功能 | 4 | 4 | 100% |
| P2 擴展功能 | 5 | 0 | 0% |
| **總計** | **39** | **34** | **87.2%** |

## ✅ 結論

本專案已**完整實現 V1.5 Protocol 的所有 P0 和 P1 功能**，型別定義、錯誤處理、重連策略、CHS 狀態機、Session 管理等核心模組均嚴格遵循技術文檔規範。

### 關鍵亮點：
1. **1:1 型別對應**：TypeScript 定義完全映射 Protocol Schema
2. **精確重連策略**：Exponential backoff + jitter（maxRetries=5, baseDelay=1s, maxDelay=30s, jitter=±20%）
3. **智能 CHS 狀態機**：5 級健康評分，STALE → HEALTHY 需連續 2 次健康心跳防止抖動
4. **短 Session 適配**：續期視窗 = min(ttl*0.2, 5min) 避免 paradox
5. **Kick-Old 機制**：同 session_id 僅允許單一 WS 控制連線
6. **標準化錯誤**：12 種 ERR_* 錯誤碼支援 i18n

### 未實現的 P2 功能說明：
P2 功能為進階擴展，不影響系統核心運作，可在未來需求明確後逐步實現。
