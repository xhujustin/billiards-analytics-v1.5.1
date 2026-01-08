# API_REFERENCE.md
## 撞球分析系統 API 參考（v1.5）

本文件僅包含 **REST API / WebSocket 協議 / Schema**，作為前後端對接的權威來源。

---

## REST API

### Streams
- GET /api/streams
- GET /api/stream/status

### Sessions
- POST /api/sessions
- POST /api/sessions/{session_id}/renew
- POST /api/sessions/{session_id}/switch_stream
- DELETE /api/sessions/{session_id}

### Config
- GET /api/config

### Replay
- GET /api/recordings
- GET /replay/burnin/{recording_id}.mjpg
- GET /replay/events/{recording_id}

---

## WebSocket

### Endpoint
- WS /ws/control?session_id=...

### Message Types
- heartbeat
- client.heartbeat
- metadata.update
- stream.changed / stream.changed.ack
- session.revoked
- cmd.* / cmd.ack / cmd.error
- protocol.hello / protocol.welcome

---

## Schema（摘要）
請參考 IMPLEMENTATION_GUIDE.md 中的 TypeScript 定義作為實作依據。