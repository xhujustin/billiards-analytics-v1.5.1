# API_REFERENCE.md
## 撞球分析系統 API 參考（v1.5.1）

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

### Control (v1.5 擴充)
- POST /api/control/toggle - 啟用/停用 YOLO 辨識
- POST /api/control/snapshot - 截圖功能
- POST /api/stream/quality - 設定串流品質 (low/med/high/auto)

### Performance (v1.5 新增)
- GET /api/performance/stats - 獲取即時效能統計 (FPS, 延遲)

### Game Mode (v1.5 新增)
- POST /api/game/start - 開始遊戲 (9球)
- POST /api/game/check_rules - 檢查規則
- POST /api/game/end_turn - 結束回合
- GET /api/game/state - 獲取遊戲狀態
- POST /api/game/end - 結束遊戲

### Practice Mode (v1.5 新增)
- POST /api/practice/start - 開始練習
- POST /api/practice/record - 記錄結果
- GET /api/practice/state - 獲取練習狀態
- POST /api/practice/end - 結束練習

### Recording (v1.5 新增)
- POST /api/recording/start - 開始錄影
- POST /api/recording/stop - 停止錄影
- POST /api/recording/event - 記錄事件
- GET /api/recordings - 錄影列表
- GET /api/recording/{id}/metadata - 錄影元資料
- GET /api/recording/{id}/events - 錄影事件

### Game Timer (v1.5 新增)
- GET /api/game/timer/state - 獲取計時器狀態
- POST /api/game/timer/delay - 應用延時 (+30秒)

---

## 回放功能 API（v1.5.1 新增）

### 錄影查詢

#### `GET /api/recordings`
列出錄影列表（支援篩選、分頁）

**Query Parameters:**
- `game_type` (optional): 遊戲類型篩選 (`nine_ball`, `practice_single`, `practice_pattern`)
- `player` (optional): 玩家名稱篩選
- `start_date` (optional): 開始日期篩選 (ISO 8601 格式)
- `end_date` (optional): 結束日期篩選 (ISO 8601 格式)
- `limit` (optional): 每頁筆數 (預設 20, 最大 100)
- `offset` (optional): 偏移量 (預設 0)

**Response 200:**
```json
{
  "recordings": [
    {
      "game_id": "game_20260115_152908",
      "game_type": "nine_ball",
      "start_time": "2026-01-15T15:29:08.873868",
      "end_time": "2026-01-15T15:29:18.594129",
      "duration_seconds": 9.72,
      "player1_name": "玩家1",
      "player2_name": "玩家2",
      "winner": "玩家1",
      "player1_score": 5,
      "player2_score": 3,
      "video_resolution": "1280x720",
      "video_fps": 30,
      "file_size_mb": 150.5
    }
  ],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

**Error Responses:**
- `400 Bad Request`: 參數無效
```json
{
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "Invalid date format",
    "details": {"field": "start_date"}
  }
}
```
- `401 Unauthorized`: 未授權
- `500 Internal Server Error`: 內部錯誤

---

#### `GET /api/recordings/{game_id}`
獲取單一錄影詳情

**Path Parameters:**
- `game_id` (required): 遊戲 ID

**Response 200:**
```json
{
  "game_id": "game_20260115_152908",
  "game_type": "nine_ball",
  "start_time": "2026-01-15T15:29:08.873868",
  "end_time": "2026-01-15T15:29:18.594129",
  "duration_seconds": 9.72,
  "player1_name": "玩家1",
  "player2_name": "玩家2",
  "winner": "玩家1",
  "player1_score": 5,
  "player2_score": 3,
  "target_rounds": 5,
  "video_path": "./recordings/game_20260115_152908/video.mjpg",
  "video_resolution": "1280x720",
  "video_fps": 30,
  "file_size_mb": 150.5,
  "created_at": "2026-01-15T15:29:08.873868",
  "updated_at": "2026-01-15T15:29:18.594129"
}
```

**Error Responses:**
- `404 Not Found`: 錄影不存在
```json
{
  "error": {
    "code": "ERR_RECORDING_NOT_FOUND",
    "message": "Recording not found",
    "details": {"game_id": "game_20260115_152908"}
  }
}
```
- `401 Unauthorized`: 未授權

---

#### `GET /api/recordings/{game_id}/events`
獲取錄影事件日誌

**Path Parameters:**
- `game_id` (required): 遊戲 ID

**Query Parameters:**
- `event_type` (optional): 事件類型篩選
- `from` (optional): 開始時間戳 (Unix timestamp)
- `to` (optional): 結束時間戳 (Unix timestamp)

**Response 200:**
```json
{
  "game_id": "game_20260115_152908",
  "events": [
    {
      "id": 1,
      "timestamp": 1768462148.873868,
      "event_type": "game_start",
      "data": {
        "game_type": "nine_ball",
        "players": ["玩家1", "玩家2"]
      },
      "target_ball": null,
      "potted_ball": null,
      "first_contact": null
    },
    {
      "id": 2,
      "timestamp": 1768462158.592132,
      "event_type": "game_end",
      "data": {
        "winner": "玩家1",
        "final_score": [5, 3]
      }
    }
  ],
  "total": 2
}
```

**Error Responses:**
- `404 Not Found`: 錄影不存在
- `401 Unauthorized`: 未授權

---

#### `DELETE /api/recordings/{game_id}`
刪除錄影記錄（級聯刪除相關事件和統計）

**Path Parameters:**
- `game_id` (required): 遊戲 ID

**Response 204:** No Content (成功刪除)

**Error Responses:**
- `404 Not Found`: 錄影不存在
- `403 Forbidden`: 權限不足
```json
{
  "error": {
    "code": "ERR_FORBIDDEN",
    "message": "Permission denied",
    "details": {"required_permission": "admin"}
  }
}
```

---

### 統計分析

#### `GET /api/stats/practice`
獲取練習統計

**Query Parameters:**
- `type` (optional): 練習類型 (`single`, `pattern`)
- `pattern` (optional): 球型 (`straight`, `cut`, `bank`, `combo`)
- `start_date` (optional): 開始日期
- `end_date` (optional): 結束日期

**Response 200:**
```json
{
  "stats": [
    {
      "practice_type": "single",
      "pattern": "straight",
      "total_attempts": 100,
      "successful_attempts": 75,
      "success_rate": 0.75,
      "avg_shot_time": 15.5,
      "sessions": 10
    }
  ],
  "summary": {
    "total_sessions": 10,
    "total_attempts": 100,
    "overall_success_rate": 0.75
  }
}
```

---

#### `GET /api/stats/player/{player_name}`
獲取玩家統計

**Path Parameters:**
- `player_name` (required): 玩家名稱

**Response 200:**
```json
{
  "name": "玩家1",
  "total_games": 50,
  "total_wins": 30,
  "win_rate": 0.6,
  "recent_games": [
    {
      "game_id": "game_20260115_152908",
      "opponent": "玩家2",
      "result": "win",
      "score": "5-3",
      "date": "2026-01-15T15:29:08"
    }
  ]
}
```

**Error Responses:**
- `404 Not Found`: 玩家不存在

---

#### `GET /api/stats/summary`
獲取統計摘要

**Query Parameters:**
- `start_date` (optional): 開始日期
- `end_date` (optional): 結束日期

**Response 200:**
```json
{
  "period": {
    "start": "2026-01-01",
    "end": "2026-01-31"
  },
  "total_games": 100,
  "total_practice_sessions": 50,
  "most_active_player": "玩家1",
  "average_game_duration": 1800.0
}
```

---

### 回放控制

#### `GET /replay/burnin/{game_id}.mjpg`
影片回放串流（MJPEG 格式）

**Path Parameters:**
- `game_id` (required): 遊戲 ID

**Query Parameters:**
- `quality` (optional): 畫質 (`low`, `med`, `high`, 預設 `med`)

**Response 200:**
- Content-Type: `multipart/x-mixed-replace; boundary=frame`
- MJPEG 串流

**Error Responses:**
- `404 Not Found`: 錄影不存在
- `403 Forbidden`: 需要 replay 權限
```json
{
  "error": {
    "code": "ERR_FORBIDDEN",
    "message": "Replay permission required",
    "details": {"required_permission": "replay"}
  }
}
```

---

#### `GET /replay/events/{game_id}`
事件回放（JSONL 格式）

**Path Parameters:**
- `game_id` (required): 遊戲 ID

**Query Parameters:**
- `from` (optional): 開始時間戳
- `to` (optional): 結束時間戳
- `downsample` (optional): 降採樣率 (1=不降採樣, 2=每2筆取1)
- `format` (optional): 格式 (`jsonl`, `json`, 預設 `jsonl`)

**Response 200:**
- Content-Type: `application/x-ndjson` (jsonl) 或 `application/json`

JSONL 格式（每行一個事件）:
```jsonl
{"timestamp": 1768462148.873868, "event_type": "game_start", "data": {...}}
{"timestamp": 1768462158.592132, "event_type": "game_end", "data": {...}}
```

JSON 格式:
```json
{
  "events": [
    {"timestamp": 1768462148.873868, "event_type": "game_start", "data": {...}},
    {"timestamp": 1768462158.592132, "event_type": "game_end", "data": {...}}
  ]
}
```

**Error Responses:**
- `404 Not Found`: 錄影不存在
- `403 Forbidden`: 需要 replay 權限

---

## 錯誤碼擴充

新增資料庫相關錯誤碼：

| 錯誤碼 | 說明 | HTTP Status |
|--------|------|-------------|
| `ERR_RECORDING_NOT_FOUND` | 錄影不存在 | 404 |
| `ERR_DATABASE_ERROR` | 資料庫錯誤 | 500 |
| `ERR_INVALID_DATE_FORMAT` | 日期格式無效 | 400 |
| `ERR_PLAYER_NOT_FOUND` | 玩家不存在 | 404 |

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

---

## 使用範例

### 查詢錄影列表
```bash
curl "http://localhost:8001/api/recordings?game_type=nine_ball&limit=10"
```

### 獲取單一錄影
```bash
curl "http://localhost:8001/api/recordings/game_20260115_152908"
```

### 刪除錄影
```bash
curl -X DELETE "http://localhost:8001/api/recordings/game_20260115_152908"
```

### 播放回放影片
```html
<img src="http://localhost:8001/replay/burnin/game_20260115_152908.mjpg?quality=med" />
```

### 獲取玩家統計
```bash
curl "http://localhost:8001/api/stats/player/玩家1"
```