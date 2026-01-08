# 撞球分析前後端協議契約（v1.5）— Endpoint Request/Response Schema 完整版

> 目的：把 Burn-in / Metadata / Command / Replay 的需求收斂成可實作的契約（含 REST endpoint schema）。  
> 備註：WebSocket schema 請見本文第 3 節。

---

---

## v1.5 變更摘要（本次合併）
- **P0：TypeScript 型別定義（協議即型別）**：新增完整 WS/REST 對應的 TS types（可作為前端 SDK `types.ts`）。
- **P0：WebSocket 重連策略參數定案**：新增 `RECONNECT_CONFIG`（maxRetries/backoff/jitter）與行為規範。
- **P0：Session 生命週期補齊**：多分頁競爭、離線恢復、續期視窗公式（短 session 特例）與 renew fallback。
- **P0：MJPEG 播放器容錯**：新增前端偵測/降級策略與建議 response header（`X-Billiards-Error-Type`）。
- **P0：CHS 狀態機轉換表**：補齊狀態轉換條件、優先序與邊界條件。
- **P1：MetadataBuffer 細節**：buffer 上限、drop 策略、throttle 期間採樣規則（latest/avg）與記憶體風險。
- **P1：錯誤碼擴充**：新增 timeout/network/stream_unavailable/invalid_state/rate_limit 等。
- **P1：版本管理與協商**：新增 WS version negotiation（握手協商）與相容策略。
- **P0：.env.example**：新增開發環境配置範例。
- **P2：效能監控指標**：新增 metrics 建議介面與最小落地集合。
- **文件拆分建議**：新增建議拆分成 API_REFERENCE / ARCHITECTURE / IMPLEMENTATION_GUIDE / TROUBLESHOOTING。


---

## P0 / P1 / P2 優先級定義（強制）

### P0（必須，MVP 不可缺）
- 系統**無 P0 則不可上線**
- 涉及：穩定性、安全性、控制權一致性、使用者體驗下限
- 任何 P0 缺失都會導致：系統不可用、誤判狀態、或控制衝突

**P0 類型範例**
- Burn-in 播放與 MJPEG 錯誤畫面契約  
- WebSocket 控制通道（cmd / ack / error）  
- Connection Health Score（DISCONNECTED / STALE / NO_SIGNAL）  
- Session 搶佔與 Kick-Old 策略  
- REST / WS 統一錯誤格式（machine-readable error code）

---

### P1（重要，但可延後）
- 不影響基本可用性，但**顯著影響產品完成度與效率**
- 可在 MVP 後第一輪迭代補齊

**P1 類型範例**
- Replay（影像 / 事件）  
- Failover UX 平滑切換  
- Client Heartbeat  
- Metadata sampling / rate_hz  
- Session auto-renew  
- 計分事件擴充（undo / confidence）

---

### P2（進階 / 非關鍵）
- 不影響主流程
- 偏向維運、擴充、工程品質與長期可維護性

**P2 類型範例**
- Feature flags 完整治理  
- Config cache / ETag  
- Dev tools / /dev UI  
- 前端 IndexedDB log / ELK / OTel  
- 多桌 / 多工作區

---

### 優先級衝突原則（必讀）
1. **P0 不得依賴 P1 / P2**
2. **P1 不得破壞 P0 行為**
3. P2 可假設 P0 / P1 已正確實作


---

## v1.1 變更摘要（本次合併）
- **Burn-in 優先定位**：明確定義 metadata 用途以「數據面板/狀態監控/回放」為主，**不作為前端 overlay 繪製來源**。
- **Connection Health Score（CHS）**：新增前端健康度狀態機（DISCONNECTED / STALE / NO_SIGNAL / DEGRADED / HEALTHY）與判定閾值。
- **Session 搶佔與衝突策略**：明定同一 `session_id` 僅允許一條「控制型 WS 連線」，採 **Kick Old** 策略，並規範 WS close_code 與 REST 409。
- **cmd.error 標準化**：新增 machine-readable `code` 規範與建議錯誤碼集合，以支援 i18n。


## 0. 名詞與原則（P0）

- **Burn-in**：後端已合成 overlay 的影像串流，前端僅播放。
- **Metadata**：bbox / keypoints / 狀態等結構化資料。
- **Command**：控制命令，主要透過 WebSocket。
- **Session**：控制與權限的最小單位，由後端建立。
- **Stream**：影像來源（camera / projector / file）。

全域原則：
1. 前端不得以每幀 reload URL 刷新影像（避免 UI thread/React reconciliation 被串流干擾）。
2. 控制與狀態以 **WS** 為主；REST 用於管理/低頻操作與 fallback 監控。
3. 所有 WS message 使用統一 envelope（含 `v/type/ts/session_id/stream_id/payload`）。
4. **Live / Replay 使用不同 URL**，避免 cache/狀態混淆：`/burnin/*` vs `/replay/*`。
5. `stream.changed`（故障切備援/強制切換）為 **強制**，且需 client ACK。

### 前端性能最佳實踐（P0 補充）
- 前端處理高頻 WebSocket 訊息（如 `metadata.update`，10–30Hz）時，**不得直接驅動高頻 React re-render**。
- 建議做法：
  - 使用 **sampling / throttle**（例如每 5 筆 metadata 僅更新一次 UI，或限制 UI 更新至 1Hz）。
  - 使用 **批次更新**（如 `useReducer` + batching、Zustand/Redux store buffer）。
- 目的：避免 UI 卡頓與主執行緒阻塞。


---

## 1. Burn-in 播放端點與可用性契約（P0）

### 1.1 Burn-in 串流端點（MJPEG）

#### `GET /burnin/{stream_id}.mjpg`
- Path params  
  - `stream_id`: `camera1 | camera2 | projector`（P0 固定；P1 可擴充為任意 stream_id）
- Query params
  - `quality`: `low | med | high`（預設 `med`）
- Response
  - `200`：`Content-Type: multipart/x-mixed-replace; boundary=frame`
  - `4xx/5xx`：依後端處理（建議仍回傳 MJPEG 的「NO SIGNAL」畫面以利前端一致播放）

**前端播放建議**
- `<img src="/burnin/camera1.mjpg?quality=med" />` 或 `<iframe src="...">`
- 禁止使用 cache-busting（每幀變更 URL）。

---

### 1.2 Liveness 判定（A+B 定案）

#### A. REST fallback（運維/監控）
##### `GET /api/stream/status`
- Query params
  - `stream_id`（必填）
- Response `200`
```json
{
  "stream_id": "camera1",
  "alive": true,
  "last_frame_ts": 1710000000000,
  "fps_ewma": 28.1,
  "pipeline_state": "RUNNING",
  "last_error": null
}
```
- `pipeline_state` enum：`RUNNING | RECONNECTING | NO_SIGNAL | ERROR`
- `alive`：後端判定 capture/pipe 是否可供應最新畫面（不等同於 client decode 成功）

**建議前端判定**
- `now - last_frame_ts > 2000ms` → `DEGRADED`
- `now - last_frame_ts > 6000ms` → `DOWN/NO_SIGNAL`
- WS 斷線 → `DISCONNECTED`（同時以此 API 顯示後端狀態）

#### B. WS heartbeat（主）
- 見第 3 節：`type="heartbeat"`（每 3 秒推送，含 `last_frame_ts`）



### 1.2.x Connection Health Score（CHS，P0）— 前端健康度狀態機
前端應維護一個「Connection Health Score」，綜合 **WS 連線狀態**、**heartbeat** 與 **last_frame_ts** 判定整體健康度。

#### 狀態定義（優先序由高到低）
1. `DISCONNECTED`：WS `onClose` 觸發，立即標記（控制通道斷線）。  
2. `STALE`：WS 仍連線，但 **超過 6 秒未收到 heartbeat**（2x interval），視為後端卡死或事件迴圈停滯。  
3. `NO_SIGNAL`：`Date.now() - last_frame_ts > 2000ms`，視為影像來源異常，顯示黃色警告。  
4. `DEGRADED`：`pipeline_state != RUNNING` 或 `fps_ewma` 低於門檻（如 `< 10`），顯示黃色警告。  
5. `HEALTHY`：以上皆否，顯示綠燈。

#### 建議判定邏輯（TypeScript pseudo-code）
```ts
if (wsClosed) {
  state = "DISCONNECTED";
} else if (now - lastHeartbeatTs > 6000) {
  state = "STALE";
} else if (now - lastFrameTs > 2000) {
  state = "NO_SIGNAL";
} else if (fpsEwma < MIN_FPS || pipelineState !== "RUNNING") {
  state = "DEGRADED";
} else {
  state = "HEALTHY";
}
```

#### 與 REST fallback 的關係
- WS `STALE` 或 `DISCONNECTED` 時，前端可額外 polling `/api/stream/status` 用於顯示「後端仍活著/仍無訊號」的差異。
- 注意：REST `alive=true` 不代表 client decode 一定成功，但可作為後端 pipeline 健康度指標。



---

## 2. Metadata 啟用條件與權限策略（P0）

### 2.1 權限模型（MVP：可不強制分級，但保留欄位）
- 角色：`viewer | operator | developer | admin`（MVP 可全為 `operator`）
- 權限旗標：`permission_flags`（建議用字串陣列）
  - `view`：可接收 metadata（只讀）
  - `calibrate`：可發校正命令
  - `replay`：可回放控制
  - `score_control`：可手動更正/裁判覆核（P1）

### 2.2 developer 模式進入（A+C 定案）
- 路由：`/dev`（需 token/role）
- feature flag：`GET /api/config` → `flags.dev_ui`

---


---

## 2.x Burn-in 優先下的 Metadata 定位（P0 Clarification）
在 **Burn-in 優先（後端合成 Overlay）** 架構中：
- 前端只需播放 MJPEG（或等價串流），不負責即時疊加繪製。
- **Metadata 的主要用途**：
  - 數據面板（FPS、偵測數量、追蹤狀態、模型版本等）
  - 狀態監控（stale / no-signal / pipeline_state）
  - 開發/除錯（frame_id、ts_capture、confidence 分布）
  - 回放（P1）：事件時間軸資料來源
- **明確不做（P0）**：前端 canvas overlay / bbox/keypoints 繪製 / 以 metadata 驅動高頻 React re-render。

## 3. WebSocket 協議（v1）— Schema（P0）

### 3.1 連線
#### `WS /ws/control?session_id={session_id}`
- Query params
  - `session_id`（必填）

### 3.2 通用 Envelope
```json
{
  "v": 1,
  "type": "heartbeat | cmd.* | cmd.ack | cmd.error | metadata.update | stream.changed | ...",
  "ts": 1710000000000,
  "session_id": "s-abc",
  "stream_id": "camera1",
  "payload": {}
}
```

### 3.3 Heartbeat（Server → Client）

### 3.3.1 client.heartbeat（Client → Server，P1）
用於後端精準偵測 client 活性（特別是背景分頁休眠、網路抖動、或前端主執行緒阻塞情境）。

- 發送頻率：每 5 秒一次（建議）
- 送出條件：WS 連線已建立（onOpen 後啟動 interval），onClose 時停止
- 後端行為：可用於計算 active sessions、偵測「client 停止回應」並觸發告警或回收資源

**Schema（JSON）**
```json
{
  "v": 1,
  "type": "client.heartbeat",
  "ts": 1710000000000,
  "session_id": "s-abc",
  "stream_id": "camera1",
  "payload": { "ts_client": 1710000000000 }
}
```


#### `type = "heartbeat"`（每 3 秒）
`payload` schema：
```json
{
  "alive": true,
  "last_frame_ts": 1710000000000,
  "fps_ewma": 28.1,
  "pipeline_state": "RUNNING"
}
```

### 3.4 Stream 強制切換（Failover）
#### `type = "stream.changed"`（Server → Client）
```json
{
  "reason": "FAILOVER",
  "play_url": "/burnin/camera2.mjpg?quality=med"
}
```

#### `type = "stream.changed.ack"`（Client → Server，必須）
```json
{ "status": "ok" }
```

### 3.5 Commands（Client → Server）
- 命令型別：`cmd.*`
- **必填欄位**：`payload.request_id`（UUID）
- ACK：server 回 `cmd.ack`（accepted / applied）或 `cmd.error`

#### `type = "cmd.ack"`（Server → Client）
```json
{ "request_id": "uuid", "status": "accepted" }
```
或
```json
{ "request_id": "uuid", "status": "applied", "applied_state": {} }
```

#### `type = "cmd.error"`（Server → Client）
```json
{ "request_id": "uuid", "code": "NO_SIGNAL", "message": "capture down" }
```

### 3.6 Metadata（Server → Client，10–30Hz）

- `rate_hz`（可選）：後端告知實際推送頻率（Hz），供前端 SDK `MetadataBuffer` 自動調整 sampling/throttle 策略。
#### `type = "metadata.update"`
`payload` 最小 schema（MVP）：
```json
{
  "frame_id": 12345,
  "ts_capture": 1710000000000,
  "img_w": 1280,
  "img_h": 720,
    "rate_hz": 25.0,
  "detections": [
    { "bbox": [10, 20, 100, 120], "label": "cue_ball", "score": 0.98, "track_id": 7 }
  ],
  "keypoints": null
}
```
- `bbox`：`[x1,y1,x2,y2]`（影像座標系，左上為 (0,0)）
- `keypoints`（可選）：例如 `[[x,y,conf], ...]`

---

## 4. REST API（v1）— Endpoint Request/Response Schema（你要求補齊的部分）

> 風格：以 OpenAPI 的「行為 + schema」方式描述（但不輸出 YAML）。

### 4.1 Streams

#### `GET /api/streams`
列出可用影像來源（前端選取用）

- Request：無 body
- Response `200`（Array）
```json
[
  {
    "stream_id": "camera1",
    "name": "Camera 1",
    "type": "usb",
    "status": "READY",
    "capabilities": {
      "qualities": ["low", "med", "high"],
      "default_quality": "med"
    }
  }
]
```
- 欄位說明
  - `type` enum 建議：`usb | rtsp | file | capture`
  - `status` enum 建議：`READY | DOWN | DEGRADED | UNKNOWN`
  - `capabilities`（可選）：可用畫質/解析度等

- Error responses（建議）
  - `401` 未授權
  - `500` 內部錯誤

---

#### `GET /api/stream/status?stream_id={stream_id}`
（見 1.2）

- Error responses（建議）
  - `400` 缺少 stream_id 或無效
  - `404` stream 不存在
  - `401` 未授權（若你的系統需要）

---

### 4.2 Sessions

#### `POST /api/sessions`
建立 session（後端產生 `session_id`）

- Request `application/json`
```json
{
  "stream_id": "camera1",
  "role_requested": "operator",
  "client_info": {
    "app": "web",
    "version": "1.0.0",
    "ua": "optional"
  }
}
```
- 欄位說明
  - `role_requested`（可選）：MVP 可忽略、由後端決定
  - `client_info`（可選）：方便 debug/audit

- Response `200`
```json
{
  "session_id": "s-abc",
  "stream_id": "camera1",
  "play_url": "/burnin/camera1.mjpg?quality=med",
  "control_ws_url": "/ws/control?session_id=s-abc",
  "role": "operator",
  "permission_flags": ["view", "calibrate", "replay"],
  "expires_at": 1710003600000
}
```

- Error responses（建議）
  - `400` stream_id 無效
  - `401` 未授權
  - `403` 權限不足（例如 viewer 不能拿 operator）
  - `404` stream 不存在
  - `429` 建立 session 過於頻繁
  - `500` 內部錯誤

---

#### `POST /api/sessions/{session_id}/switch_stream`
手動切換來源（低頻管理型命令）

- Path params
  - `session_id`（必填）
- Request `application/json`
```json
{ "stream_id": "camera2" }
```

- Response `200`
```json
{
  "session_id": "s-abc",
  "stream_id": "camera2",
  "play_url": "/burnin/camera2.mjpg?quality=med"
}
```

- 行為規範（P0）
  - 切換成功後，後端 **更新該 session 的 active stream**
  - 前端應重新載入播放區（重建 `<img>` 或 `<iframe>` 一次即可，不是每幀 reload）
  - 若切換期間 pipeline 需時間，建議後端回 `200` 但同時在 WS 推送 `pipeline_state=RECONNECTING`，完成後回 `RUNNING`

- Error responses（建議）
  - `400` stream_id 無效
  - `401/403` 未授權/權限不足
  - `404` session 或 stream 不存在
  - `409` session 正在切換中（避免並發切換）
  - `500` 內部錯誤

---

#### `DELETE /api/sessions/{session_id}`
結束 session（可選，建議支援）
- Response
  - `204 No Content`
- Error responses（建議）
  - `404` session 不存在
  - `401/403` 未授權/權限不足


#### `POST /api/sessions/{session_id}/renew`（P1，定案）
延長 session 租約（renew），避免長時間操作中 session 過期。

- Path params
  - `session_id`（必填）
- Request `application/json`（可選；若無額外參數可為 `{}`）
```json
{}
```
- Response `200`
```json
{
  "session_id": "s-abc",
  "expires_at": 1710007200000
}
```

- 行為規範
  - 後端應驗證呼叫者仍具 session 使用權（role/permission 不變）
  - renew 不應改變 `stream_id`，除非後端同時做 failover（則以 WS `stream.changed` 為準）

- Error responses（建議）
  - `401/403` 未授權/權限不足
  - `404` session 不存在或已過期
  - `409` session 衝突（例如 session 已被取代）

> 備選相容方案（不採定案但可支援）：允許重複呼叫 `POST /api/sessions`（帶相同 client_info）作為 renew；若實作此方案，需清楚定義是否回傳同一 `session_id`。




---


---

## 4.x Session 搶佔與衝突策略（P0）
### 4.x.1 基本規則
- **同一 `session_id` 在任一時間僅允許一條「控制型 WebSocket 連線」**（`/ws/control`）。
- 多分頁（Tab A / Tab B）或多裝置同時使用時，必須明確定義衝突策略以避免控制權不一致。

### 4.x.2 前端建議（Web 開發測試）
- 建議將 `session_id` 存於 `localStorage`，以便同域分頁共用並可做「顯示目前已登入」等提示。
- 若前端偵測到 session 被取代（見下），應清除 localStorage 並導回初始化流程。

### 4.x.3 後端定案策略：Kick Old（踢掉舊連線）
當後端收到新的 `/ws/control` 連線請求且同一 `session_id` 已有現存控制連線時：
1. **接受新連線**（新連線視為最新有效控制端）。
2. 對舊連線推送 `session.revoked`（可選）並關閉舊連線。

#### WebSocket close code（建議定案）
- `close_code = 4001`：`SESSION_REPLACED`

#### 可選通知訊息（Server → Client）
```json
{
  "v": 1,
  "type": "session.revoked",
  "ts": 1710000000000,
  "session_id": "s-abc",
  "stream_id": "camera1",
  "payload": { "reason": "SESSION_REPLACED" }
}
```

### 4.x.4 REST 衝突錯誤（建議）
對於會建立或綁定控制權的 REST 行為（例如某些部署將 session 建立與控制權綁定），建議回：
- HTTP `409 Conflict`
```json
{
  "error": {
    "code": "SESSION_CONFLICT",
    "message": "Session is already active elsewhere",
    "details": { "session_id": "s-abc" }
  }
}
```


### 4.3 Config / Feature flags

#### `GET /api/config`
下發 flags 與參數（前端啟用 dev/metadata/replay 等）

- Response `200`
```json
{
  "env": "prod",
  "flags": {
    "dev_ui": false,
    "metadata": true,
    "replay": true,
    "scoring_beta": false
  },
  "max_age_ms": 1000,
  "quality_presets": {
    "low":  { "jpeg_quality": 55, "target_fps": 15 },
    "med":  { "jpeg_quality": 75, "target_fps": 30 },
    "high": { "jpeg_quality": 85, "target_fps": 30 }
  }
}
```

- Error responses（建議）
  - `401` 未授權（若 config 屬於內部）
  - `500` 內部錯誤

---

### 4.4 Recordings / Replay（P1）

#### `GET /api/recordings`
列出錄影資源

- Query params（建議）
  - `stream_id`（可選，但建議至少支援）
  - `from`（可選，ms timestamp）
  - `to`（可選，ms timestamp）
  - `limit`（可選，預設 50）

- Response `200`
```json
[
  {
    "recording_id": "r-001",
    "stream_id": "camera1",
    "from": 1710000000000,
    "to": 1710000300000,
    "has_video": true,
    "has_events": true,
    "duration_ms": 300000
  }
]
```

- Error responses（建議）
  - `400` 參數無效（例如 from > to）
  - `401/403` 未授權
  - `500` 內部錯誤

---

#### `GET /replay/burnin/{recording_id}.mjpg`
影像回放（burn-in 另一條 stream）

- Path params
  - `recording_id`
- Query params（可選）
  - `quality=low|med|high`（若回放端可調）
  - `speed`（可選；若以 MJPEG 模擬倍速回放，P1 可做）

- Response
  - `200`：MJPEG stream（同 burn-in）
  - `404`：recording 不存在
  - `401/403`：未授權/權限不足（需要 `replay` 權限）

---

#### `GET /replay/events/{recording_id}`
事件回放（metadata 時間軸）— 拉取模式

- Query params（建議）
  - `from`（可選，ms）
  - `to`（可選，ms）
  - `downsample`（可選，例如 `1`=不降採樣，`2`=每 2 筆取 1）
  - `format`（可選：`jsonl | json`，預設 `jsonl`）

- Response `200`
  - `Content-Type: application/x-ndjson`（jsonl）或 `application/json`

- JSONL 單行 schema（建議）
```json
{
  "ts_capture": 1710000000000,
  "frame_id": 12345,
  "stream_id": "camera1",
  "img_w": 1280,
  "img_h": 720,
  "detections": [
    { "bbox": [10, 20, 100, 120], "label": "cue_ball", "score": 0.98, "track_id": 7 }
  ],
  "keypoints": null,
  "events": null
}
```

- Error responses（建議）
  - `404` recording 不存在
  - `401/403` 未授權/權限不足（需要 `replay` 權限）
  - `500` 內部錯誤

---

#### （可選，P1 推薦）`WS /ws/replay/{recording_id}?speed=1.0&from=...`
事件回放（時間軸推送）— 推送模式（更像 live）
- Command 建議使用 `cmd.replay.*`（play/pause/seek/speed）
- markers 由後端保存（已定案）

---

## 5. 計分事件模型（P1）

### 5.1 事件型別
- `score.event`：`pot | foul | turn_change | rack_end | reset | clock`

### 5.2 最小事件 schema（建議）
```json
{
  "event_type": "pot",
  "ts_capture": 1710000000000,
  "frame_id": 12345,
  "payload": {
    "ball": "9",
    "pocket": "top_left"
  }
}
```

---

## 6. 校正流程狀態機（P2）

### 6.1 三段校正輸入/輸出
1. 投影機定位：輸出 homography
2. 桌布顏色：輸出 HSV range
3. 邊界/口袋：輸出 ROI/Mask

### 6.2 WS 命令建議（摘要）
- `cmd.calibration.start { step }`
- `cmd.calibration.next { step }`
- `cmd.calibration.retry { step }`
- `cmd.calibration.back { step }`
- server 推送：`calibration.state`（目前 step、進度、錯誤原因）

---

## 7. Feature Flags / 配置中心（P2）
- `.env` + `GET /api/config`
- 可控功能：overlay、dev tools、replay、scoring beta

---

## 8. 部署與封裝（P2）
- 建議 base paths
  - `/api`（REST）
  - `/ws`（WebSocket）
  - `/burnin`（live stream）
  - `/replay`（replay stream / events）

---

## 9. 監控與紀錄（P2）
- 前端 log 等級：info / warn / error（可匯出 JSON）
- 後端 audit log：以 `request_id` 為關聯鍵（commands/replay/score override）

---

## 附錄 A：錯誤格式（REST 建議）
統一錯誤 response（非必須，但強烈推薦）
```json
{
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "stream_id is invalid",
    "details": { "field": "stream_id" }
  }
}
```

## 附錄 B：命令 type 建議清單（P0 最小）
- `cmd.calibration.start`
- `cmd.calibration.next`
- `cmd.calibration.retry`
- `cmd.calibration.back`
- `cmd.overlay.set_mode`（可選）
- `cmd.replay.play/pause/seek/speed`（P1）


---

## 附錄 C：cmd.error 錯誤碼標準化（i18n 友善，P0）
### C.1 規範
- `cmd.error` 必須包含 **machine-readable** 的 `code`（固定枚舉或可擴充集合）。
- `message` 僅作為除錯用途，不應作為前端多語系顯示的唯一來源。
- 前端建議以 `code` 對應 i18n key，例如：`error.ERR_CAMERA_BUSY`。

### C.2 `cmd.error` payload schema（定案）
```json
{
  "request_id": "uuid",
  "code": "ERR_CALIBRATION_FAILED",
  "message": "Calibration failed at projector step",
  "details": { "step": "projector" }
}
```

### C.3 建議錯誤碼集合（P0 最小）
| code | 說明 |
|---|---|
| `ERR_INVALID_ARGUMENT` | 參數錯誤 |
| `ERR_PERMISSION_DENIED` | 權限不足 |
| `ERR_NO_SIGNAL` | 無影像訊號 |
| `ERR_CAMERA_BUSY` | 相機被佔用 |
| `ERR_CALIBRATION_FAILED` | 校正失敗 |
| `ERR_SESSION_REPLACED` | Session 被取代（常搭配 WS close_code 4001） |
| `ERR_INTERNAL` | 未分類內部錯誤 |


## Failover UX 指南（P1）
當前端收到 `stream.changed`（強制切換來源）時，建議流程如下：
1. 暫停舊播放器（停止舊 `<img>` / `<iframe>`）。
2. 顯示過渡畫面（例如「Switching source…」loading overlay）。
3. 更新播放器 `src` 為新 `play_url`。
4. 成功載入後送出 `stream.changed.ack`。
5. 若 ACK 失敗或超時，fallback 至 `GET /api/stream/status` 檢查後端狀態。


### MJPEG 錯誤畫面處理（P0）
- 即使發生 4xx/5xx 錯誤，後端仍應回傳 **MJPEG 格式** 的錯誤畫面（單幀或循環）。
- 錯誤畫面建議格式：靜態 JPEG + 文字（例如「NO SIGNAL」「CAMERA BUSY」）。
- 禁止回傳 HTML error page，以避免前端播放器崩潰。


### Connection Health Score（CHS）— UI 映射建議（P1）
| 狀態 | 顏色 | Icon | UI 行為 |
|---|---|---|---|
| DISCONNECTED | 紅 | 斷線 | 顯示 Reconnect 按鈕 |
| STALE | 橘 | 時鐘 | Polling REST + Toast |
| NO_SIGNAL | 黃 | 警告 | 顯示無影像提示 |
| DEGRADED | 黃 | 低速 | 顯示品質下降 |
| HEALTHY | 綠 | 正常 | 正常顯示 |


### Metadata 推送頻率與前端處理（P1）
- Metadata schema 可選欄位：`rate_hz`（後端告知實際推送頻率）。
- 前端數據面板建議：
  - 使用 throttle（例如 1Hz）更新 UI。
  - 高頻資料暫存於 store buffer，再批次更新。


### WebSocket 無效 Envelope 處理（P0）
- 前端：收到無效 envelope → 忽略並 `console.warn`。
- 後端：收到無效 cmd → 回傳 `cmd.error`，`code = ERR_INVALID_ARGUMENT`。


### Client Heartbeat（P1）
- 新增 `type="client.heartbeat"`：由 client 每 5 秒發送。
- Server 可用於監控 active session 與 client 活性。


### REST 錯誤格式（Mandatory）
- 所有 REST endpoint 的錯誤回應 **必須** 遵循附錄 A 統一格式。
- 前端建議使用 axios interceptor 解析 `error.code` 並對應 UI/i18n。


### Session 自動續期（P1）
- `POST /api/sessions` 回傳 `expires_at`。
- 前端應在 `expires_at - 5 分鐘` 時自動 renew session（若後端支援）。


### Replay 事件效能優化（P1）
- `GET /replay/events` 建議支援：`offset`、`limit`。
- 對大型 recording，建議前端使用 infinite scroll。


### 計分事件擴充（P1）
- `score.event.payload` 可新增：
  - `confidence`
  - `manual_override`
  - `undoable`


### 校正流程 UI 指南（P1）
- `calibration.state` payload 建議新增：`progress: 0–100`。
- 前端可使用 Stepper / Progress Bar 映射三段校正流程。


### Config Cache（P2）
- `GET /api/config` 建議回傳 `ETag`。
- Response header：`Cache-Control: max-age=300`。


### 部署基底路徑（P2）
- 前端應支援環境變數設定 API base：
  - `REACT_APP_API_BASE`
  - `REACT_APP_WS_BASE`

---

## 前端 SDK 架構（P0/P1）

> 目的：避免每個前端專案自行拼湊 WS / REST / 狀態機邏輯，
> 將協議轉化為**可重用、可測試、可維護**的 SDK。

### 設計原則（P0）
- **協議即型別**：TypeScript interface 需 1:1 映射後端 schema
- **資料與 UI 解耦**：SDK 不直接操作 React state / DOM
- **高頻資料不可直推 UI**：metadata 必須經過 buffer / throttle
- **單一事實來源（SSOT）**：Session / Stream / CHS 狀態由 SDK 維護

---

### SDK 分層架構（建議）

```
┌───────────────────────────┐
│        UI Layer           │  React / Electron
│  (Components / Hooks)     │
└────────────▲──────────────┘
             │ hooks/selectors
┌────────────┴──────────────┐
│     Application Store     │  (Zustand / Redux)
│  - connectionHealth       │
│  - session / stream       │
│  - uiState (low freq)     │
└────────────▲──────────────┘
             │ events
┌────────────┴──────────────┐
│     Frontend SDK Core     │  ⭐核心責任
│  - WS Manager             │
│  - REST Client            │
│  - Session Manager        │
│  - CHS State Machine      │
│  - Command Dispatcher     │
│  - Metadata Buffer        │
└────────────▲──────────────┘
             │
┌────────────┴──────────────┐
│   Transport / Protocol    │
│  - WebSocket              │
│  - HTTP (REST)            │
└───────────────────────────┘
```

---

### 核心模組職責（P0）

#### 1. SessionManager
- 建立 / renew / 銷毀 session
- 處理 Kick-Old（`SESSION_REPLACED`）
- 管理 `session_id`（localStorage / memory）

#### 2. WebSocketManager
- 管理 `/ws/control` 連線生命週期
- 自動 reconnect（含 backoff）
- 處理 close_code（4001 → session replaced）
- 發送 `client.heartbeat`（P1）

#### 3. ConnectionHealthMachine（CHS）
- 狀態：`DISCONNECTED | STALE | NO_SIGNAL | DEGRADED | HEALTHY`
- 輸入：WS state / heartbeat / last_frame_ts
- 輸出：單一健康狀態（供 UI 訂閱）

#### 4. CommandDispatcher
- 發送 `cmd.*`（自動附 request_id）
- 管理 pending / timeout（如 5s）
- 收到 `cmd.ack / cmd.error` 時 resolve / reject


**錯誤處理與重試策略（P2）**
- 自動 retry：僅針對「可判定為網路層錯誤」的失敗（例如 WS 短暫斷線導致未送達），最大重試 3 次（含 exponential backoff）。
- 不對「業務邏輯錯誤」重試（例如 `ERR_INVALID_ARGUMENT`、`ERR_PERMISSION_DENIED`）。
- 全局 error handler：SDK 提供統一入口（hook/event）供應用層做 toast / log / i18n。



#### 5. MetadataBuffer
- 接收 `metadata.update`（10–30Hz）
- 依策略 sampling / throttle（例如 1Hz）
- 僅輸出「UI 可用摘要資料」

---

### SDK 對外 API（示意）

```ts
const sdk = createBilliardsSDK({
  apiBase: process.env.REACT_APP_API_BASE,
  wsBase: process.env.REACT_APP_WS_BASE,
  authToken: process.env.REACT_APP_AUTH_TOKEN, // optional
  // 或提供 async getter 以支援 refresh：
  // authToken: async () => (await getFreshToken()),
});

await sdk.session.create({ streamId: "camera1" });

sdk.on("connectionHealth", (state) => {
  console.log(state); // HEALTHY / STALE / ...
});

sdk.sendCommand("cmd.calibration.start", { step: "projector" });

const stats = sdk.metadata.getSummary(); // low-frequency stats
```

---

### React 整合建議（P0）
- 使用 hooks 作為唯一入口：
  - `useSession()`
  - `useConnectionHealth()`
  - `useMetadataSummary()`
- **禁止**在 React component 中直接操作 WS / REST。

---

### 測試策略（P1）
- SDK core 可用 mock WS / REST 進行 unit test
- CHS state machine 使用 table-driven test 驗證轉移
- CommandDispatcher 驗證 timeout / retry 行為


### SDK 初始化與 Auth（P2）
SDK 初始化建議支援：
- `authToken?: string | (() => Promise<string>)`
  - 允許 Bearer token 直傳
  - 或提供 async getter 以支援 token refresh（例如 OAuth / SSO）


---

## Mobile / Low-bandwidth 環境指南（P2）
- 偵測條件（建議）：`navigator.connection.effectiveType` 或 `type === "cellular"`（若可用）。
- 行為建議：
  1. Burn-in `quality` 自動降級至 `low`
  2. Metadata UI 更新更激進 throttle（例如 0.5–1Hz）
  3. 降低重連頻率或增加 backoff，避免耗電與網路負擔
- 目的：在行動網路下維持可用性與體驗下限。

---

## TypeScript 型別定義（P0，協議即型別）

> 目的：避免 schema 只存在於文件；前端 SDK 必須以 TypeScript types 作為唯一來源（SSOT）。  
> 建議檔名：`packages/sdk/src/types.ts`

```ts
export type ProtocolVersion = 1;

export type WSMessageType =
  | "heartbeat"
  | "client.heartbeat"
  | "metadata.update"
  | "stream.changed"
  | "stream.changed.ack"
  | "session.revoked"
  | "cmd.ack"
  | "cmd.error"
  | `cmd.${string}`;

export interface WSEnvelope<T = unknown> {
  v: ProtocolVersion;
  type: WSMessageType;
  ts: number; // server ts_capture aligned timestamp
  session_id: string;
  stream_id: string;
  payload: T;
}

/** ---- Heartbeat ---- */
export interface HeartbeatPayload {
  alive: boolean;
  last_frame_ts: number;
  fps_ewma: number;
  pipeline_state: "RUNNING" | "RECONNECTING" | "NO_SIGNAL" | "ERROR";
}

export interface ClientHeartbeatPayload {
  ts_client: number;
}

/** ---- Metadata ---- */
export interface Detection {
  bbox: [number, number, number, number]; // x1,y1,x2,y2
  label: string;
  score: number; // 0..1
  track_id?: number;
}

export interface Keypoint {
  x: number;
  y: number;
  conf: number; // 0..1
  name?: string;
}

export interface MetadataPayload {
  frame_id: number;
  ts_capture: number;
  img_w: number;
  img_h: number;
  rate_hz?: number; // optional; actual push rate
  detections: Detection[];
  keypoints?: Keypoint[] | null;
  events?: unknown[] | null; // reserved (P1+)
}

/** ---- Stream failover ---- */
export interface StreamChangedPayload {
  reason: "FAILOVER" | "MANUAL" | "POLICY";
  play_url: string;
}

export interface StreamChangedAckPayload {
  status: "ok" | "error";
}

/** ---- Commands ---- */
export interface CmdAckPayload {
  request_id: string;
  status: "accepted" | "applied";
  applied_state?: Record<string, unknown>;
}

export interface CmdErrorPayload {
  request_id: string;
  code:
    | "ERR_INVALID_ARGUMENT"
    | "ERR_PERMISSION_DENIED"
    | "ERR_NO_SIGNAL"
    | "ERR_CAMERA_BUSY"
    | "ERR_CALIBRATION_FAILED"
    | "ERR_SESSION_REPLACED"
    | "ERR_TIMEOUT"
    | "ERR_NETWORK"
    | "ERR_STREAM_UNAVAILABLE"
    | "ERR_INVALID_STATE"
    | "ERR_RATE_LIMIT"
    | "ERR_INTERNAL";
  message: string; // debug only (not for i18n)
  details?: Record<string, unknown>;
}

/** ---- REST error format ---- */
export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
```


---

## WebSocket 重連策略（P0，定案）

> 目標：在網路抖動、WS 斷線、或後端重啟時提供可預期的恢復能力，並避免「雷擊式重連」。

### 參數定案（SDK 預設）
```ts
export const RECONNECT_CONFIG = {
  maxRetries: 5,
  initialDelay: 1000,      // 1s
  maxDelay: 30000,         // 30s
  backoffMultiplier: 2,    // exponential backoff
  jitter: true,            // randomize delay to avoid thundering herd
};
```

### 行為規範
- WS `onClose` 觸發後：立即進入 CHS `DISCONNECTED`，並啟動重連。
- 重連延遲：`delay = min(maxDelay, initialDelay * backoffMultiplier^attempt)`，jitter 於 ±20% 隨機抖動。
- 達到 `maxRetries`：停止自動重連，改為提示使用者「手動重試」；同時可用 REST `/api/stream/status` 顯示後端狀態。
- 若 close_code = `4001 SESSION_REPLACED`：**禁止重連**，改走「重新建立 session」流程。


---

## Session 生命週期管理（P0，補齊）

### 多頁籤/多視窗競爭（定案）
- 同一 `session_id` 僅允許一條控制型 WS（Kick Old 策略）。
- Web 前端建議：`session_id` 存於 `localStorage`，可顯示「此 session 已在其他分頁使用」訊息。
- 若收到 `session.revoked` 或 WS close_code 4001：清除 localStorage 的 `session_id`，回到建立 session 流程。

### 離線恢復（定案）
- 偵測網路離線：`window.navigator.onLine === false` → 暫停重連、提示離線。
- 網路恢復：重新啟動重連流程；若 session 已過期/被取代 → 重新 `POST /api/sessions` 建立新 session。

### 續期時機（短 session 特例）
原則：以 session 剩餘時間的比例決定續期窗口，避免「session 只有 3 分鐘卻要求提前 5 分鐘續期」的矛盾。

```ts
const renewalWindowMs = Math.min(sessionDurationMs * 0.2, 5 * 60 * 1000);
// 例：3 分鐘 session → 0.6 分鐘（36s）前續期
```

### 續期策略（定案）
- 使用 `POST /api/sessions/{session_id}/renew`（P1 定案 endpoint）
- renew 失敗 fallback：
  - `ERR_SESSION_REPLACED` / 409 → 重新建立新 session
  - `ERR_NETWORK` → 進入重連流程，並延後再嘗試 renew


---

## MJPEG 播放器容錯機制（P0）

### 後端回應契約（補強）
- 即使 4xx/5xx，仍回傳 MJPEG 格式錯誤畫面（單幀或循環），禁止 HTML error page。
- 建議額外回傳 header（可選但推薦）：
  - `X-Billiards-Error-Type: NO_SIGNAL | CAMERA_BUSY | INTERNAL | ...`

### 前端偵測建議
- `<img>` 的 `onError` 可捕捉載入失敗（但無法直接判定幀率降為 0）。
- SDK 建議以 **CHS**（last_frame_ts + heartbeat）作為「是否有畫面」的最終判定。
- 若使用自訂 MJPEG player（canvas decode）：可統計 frame rate；`fps == 0` 持續 N 秒（如 2s）→ 視為 NO_SIGNAL。

### `<img>` 參考（示意）
```tsx
<img
  src={burnInUrl}
  onError={() => {
    // fallback：切換成預設佔位圖，並提示使用者
    // 最終狀態仍以 CHS 判定為準
  }}
/>
```


---

## Connection Health Score（CHS）狀態機（P0，轉換表定案）

### 優先序（高 → 低）
`DISCONNECTED > STALE > NO_SIGNAL > DEGRADED > HEALTHY`

### 狀態判定（摘要）
- DISCONNECTED：WS onClose 或 close_code 不是「正常關閉」
- STALE：WS 連線中但 `now - lastHeartbeatTs > 6000ms`
- NO_SIGNAL：`now - lastFrameTs > 2000ms`
- DEGRADED：`pipeline_state != RUNNING` 或 `fps_ewma < MIN_FPS`
- HEALTHY：以上皆否

### 狀態轉換條件表（核心）
| From → To | 條件 |
|---|---|
| STALE → HEALTHY | 重新連續收到 ≥2 次 heartbeat 且 `now-lastFrameTs <= 2000ms` |
| NO_SIGNAL → HEALTHY | `now-lastFrameTs <= 2000ms` 且 pipeline_state=RUNNING |
| DEGRADED → HEALTHY | pipeline_state=RUNNING 且 fps_ewma 回復門檻以上 |
| ANY → DISCONNECTED | WS close（除非是 app 主動退出且不需重連） |
| DISCONNECTED → HEALTHY | WS 重連成功且 heartbeat/last_frame_ts 恢復正常 |
| NO_SIGNAL → DISCONNECTED | **不自動**（除非 WS 斷線）；NO_SIGNAL 應保持為黃燈而非視為斷線 |
| DEGRADED vs NO_SIGNAL | 以 **NO_SIGNAL** 優先（因為畫面輸入缺失比品質下降更嚴重） |


---

## Metadata 高頻資料處理（P1，細節定案）

### 取樣規則（建議）
- UI 面板類指標（FPS、偵測數量等）：建議 throttle 至 1Hz。
- throttle 期間資料處理策略（定案：latest-first）：
  - UI 顯示使用「最新一筆」metadata（避免延遲累積）。
  - 若需要統計（例如平均 fps），可在 buffer 上做 rolling average（P2）。

### Buffer 上限與記憶體安全
- SDK 必須設定 buffer 上限，避免記憶體洩漏（長時間運行）。
- 建議上限：100（可配置）。

```ts
export class MetadataBuffer {
  private buffer: MetadataPayload[] = [];
  constructor(private readonly maxSize = 100) {}

  push(data: MetadataPayload) {
    if (this.buffer.length >= this.maxSize) this.buffer.shift(); // FIFO drop oldest
    this.buffer.push(data);
  }

  getLatest(): MetadataPayload | undefined {
    return this.buffer[this.buffer.length - 1];
  }
}
```


---

## 附錄 D：錯誤碼擴充清單（P1）

在附錄 C 基礎上，新增常見工程錯誤碼（便於 i18n / UI 行為分流）：
| code | 說明 | 建議 UI 行為 |
|---|---|---|
| `ERR_TIMEOUT` | 命令超時 | 提示重試 / 顯示進度失敗 |
| `ERR_NETWORK` | 網路錯誤 | 進入重連 / 提示離線 |
| `ERR_STREAM_UNAVAILABLE` | 串流不可用 | 顯示 NO_SIGNAL / 建議切換來源 |
| `ERR_INVALID_STATE` | 狀態錯誤（流程不允許） | 禁用按鈕 / 顯示引導 |
| `ERR_RATE_LIMIT` | 請求過於頻繁 | 降頻 / 顯示稍後再試 |


---

## API 版本管理與 WS 協商（P1）

### 版本升級策略（建議定案）
- `v` 欄位代表協議主版本（breaking changes 才升主版）。
- 發佈 v2 後：v1 保留支援期（建議至少 90 天），並提供 deprecation notice（P2）。
- 向下相容：server 可接受 client 舊版本；若不支援，必須明確回錯誤碼。

### WS 版本協商（握手，P1）
為避免 client/server 版本不匹配，建議在 WS 連線建立後先協商：

**Client → Server**
```json
{
  "v": 1,
  "type": "protocol.hello",
  "ts": 1710000000000,
  "session_id": "s-abc",
  "stream_id": "camera1",
  "payload": { "supported_versions": [1, 2] }
}
```

**Server → Client**
```json
{
  "v": 1,
  "type": "protocol.welcome",
  "ts": 1710000000000,
  "session_id": "s-abc",
  "stream_id": "camera1",
  "payload": { "negotiated_version": 1 }
}
```

若無共同版本：回 `cmd.error`（或 `protocol.error`）並關閉 WS。


---

## 開發環境配置範例（P0）

> 建議提供 `.env.example` 於 repo root，便於新工程師快速啟動。

```bash
# .env.example
REACT_APP_API_BASE=http://localhost:8000/api
REACT_APP_WS_BASE=ws://localhost:8000/ws
REACT_APP_BURNIN_BASE=http://localhost:8000/burnin
REACT_APP_AUTH_TOKEN=dev_token_123

# Feature Flags (frontend-side, optional)
REACT_APP_ENABLE_DEV_TOOLS=true
REACT_APP_ENABLE_REPLAY=false
```


---

## 效能監控指標建議（P2）

```ts
export interface PerformanceMetrics {
  // WebSocket
  wsReconnectCount: number;
  wsMessageRate: number;   // msg/s
  wsLatency: number;       // ms (optional if measurable)

  // MJPEG / Video
  videoFrameRate: number;  // fps
  videoLoadTime: number;   // ms

  // Metadata
  metadataProcessTime: number; // ms
  metadataDropRate: number;    // 0..1

  // UI
  renderTime: number;       // ms
  memoryUsage: number;      // MB (best-effort)
}
```

**最小落地集合（建議）**
- `wsReconnectCount`、`wsMessageRate`
- `videoFrameRate`
- `metadataDropRate`
- `renderTime`（可用 Performance API）


---

## 文件拆分建議（可選，但強烈推薦）
為降低單一文件的維護成本與讀者負擔，建議拆分為：
- `API_REFERENCE.md`：純 API/WS 定義與 schema（可對應 OpenAPI/JSON Schema）
- `ARCHITECTURE.md`：架構決策（Burn-in 優先、雙通道、控制權模型、failover）
- `IMPLEMENTATION_GUIDE.md`：前端 SDK / 後端參考實作 / best practices
- `TROUBLESHOOTING.md`：常見問題與除錯手冊（close_code、error codes、NO_SIGNAL）
