# API_REFERENCE.md
## 撞球分析系統 API 參考（v1.5.3）

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

**更新紀錄:**
- 03/21: '新增單球練習自動偵測功能'
  - **範例**: 單球練習下，當母球和子球同時移動時系統判定開始嘗試。待靜止後，若偵測到子球數量減少則表示成功進球。系統將自動呼叫紀錄 API。
  - **規範用法**: 前端介面（如 `PracticePage.tsx`）無需手動按鈕，透過輪詢 `/api/practice/state` 即可自動同步更新介面。
  - **輸出狀態格式** (`/api/practice/state`):
    ```json
    { "active": true, "attempts": 1, "successes": 1, "success_rate": 1.0 }
    ```

### Recording (v1.5 新增)
**更新紀錄:**
- 03/22: '新增錄影列表 mode 分頁查詢優化'
  - **範例**: `GET /api/recordings?mode=practice&limit=6&offset=0`
  - **規範用法**: 優先使用 mode + limit + offset 由後端分頁，避免前端全量抓取。
  - **輸出格式**: `{ recordings, total, limit, offset }`（維持既有結構）

- POST /api/recording/start - 開始錄影
- POST /api/recording/stop - 停止錄影
- POST /api/recording/event - 記錄事件
- GET /api/recordings - 錄影列表
- GET /api/recording/{id}/metadata - 錄影元資料
- GET /api/recording/{id}/events - 錄影事件
**更新紀錄:**
- 03/22: '新增錄影停止非阻塞處理與串流卡頓修正'
  - **範例**: 前端呼叫 `POST /api/recording/stop` 後，可立即切回主頁並持續取得 `/burnin/camera1.mjpg` 影像。
  - **規範用法**: 錄影相關 API 以 threadpool 執行同步 I/O，避免阻塞 FastAPI event loop；錄影停止時會先釋放共享狀態再進行縮圖/轉檔。
  - **輸出格式** (`/api/recording/stop`):
    ```json
    { "game_id": "game_20260322_173000", "duration": 42.5, "frame_count": 1280, "file_size_mb": 55.3 }
    ```

### Game Timer (v1.5 新增)
- GET /api/game/timer/state - 獲取計時器狀態
- POST /api/game/timer/delay - 應用延時 (+30秒)

### Camera Parameters (v1.5.3 新增)
- GET /api/camera/params - 獲取相機參數
- POST /api/camera/params - 更新相機參數
- POST /api/camera/auto-adjust - 自動調整相機參數
- GET /api/camera/format - 獲取相機格式資訊
- GET /api/camera/stats - 獲取影像處理統計

---

## 回放功能 API（v1.5.3 新增）

### 錄影查詢

#### `GET /api/recordings`
列出錄影列表（支援篩選、分頁）

**Query Parameters:**
- `mode` (optional): 模式篩選 (`game`, `practice`)，會自動映射到多遊戲類型
- `game_type` (optional): 遊戲類型篩選 (`nine_ball`, `practice_single`, `practice_pattern`)，優先級高於 `mode`
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

**更新紀錄:**
- 03/22: '新增玩家統計 API 聚合查詢優化'
  - **範例**: `GET /api/stats/player/玩家1`
  - **規範用法**: 後端改以 SQL 聚合 + 限量查詢（近期 5 筆）產生 `recent_games` 與 `recent_practice`，不再使用 `limit=10000` 全量載入。
  - **輸出格式**: 維持既有欄位 `{ name, total_games, total_wins, win_rate, recent_games, total_practice_sessions, recent_practice }`。


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

**說明：**
- 直接從 recordings 表計算統計，不依賴 players 表
- 即使玩家沒有任何記錄，也會返回初始化的統計數據（total_games=0, total_wins=0, win_rate=0.0）

---

#### `GET /api/stats/summary`
獲取統計摘要

**更新紀錄:**
- 03/22: '新增總覽統計 API 聚合查詢優化'
  - **範例**: `GET /api/stats/summary?start_date=2026-03-01&end_date=2026-03-22`
  - **規範用法**: 後端以 SQL 聚合計算 `total_games`、`total_practice_sessions`、`most_active_player`、`average_game_duration`、`player_rankings`，避免載入全部錄影資料後再於 Python 計算。
  - **輸出格式**: 維持既有欄位 `{ period, total_games, total_practice_sessions, most_active_player, average_game_duration, player_rankings }`。


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
  "average_game_duration": 1800.0,
  "player_rankings": [
    {
      "name": "玩家1",
      "total_games": 50,
      "total_wins": 30,
      "win_rate": 0.6
    },
    {
      "name": "玩家2",
      "total_games": 30,
      "total_wins": 15,
      "win_rate": 0.5
    }
  ]
}
```

**說明：**
- `player_rankings` 欄位包含所有玩家的統計排名
- 只統計 nine_ball 類型的遊戲
- 按照總局數從多到少排序


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
<video controls>
  <source src="http://localhost:8001/api/recordings/game_20260115_152908/video" type="video/mp4">
</video>
```

---

## 相機參數控制 API（v1.5.3 新增）

### 獲取相機參數

#### `GET /api/camera/params`
獲取當前相機的所有參數設定

**Response 200:**
```json
{
  "exposure": -6,
  "iso": 0,
  "brightness": 128,
  "contrast": 128,
  "saturation": 128,
  "sharpness": 128,
  "auto_wb": true,
  "wb_temp": 4000,
  "denoise_enabled": false,
  "denoise_strength": 10,
  "denoise_method": "fastNlMeans",
  "brightness_adjust": 0,
  "contrast_adjust": 1.0
}
```

**Error Responses:**
- `503 Service Unavailable`: 相機不可用

---

### 更新相機參數

#### `POST /api/camera/params`
更新一個或多個相機參數

**Request Body:**
```json
{
  "exposure": -5,
  "iso": 400,
  "denoise_enabled": true,
  "denoise_strength": 30,
  "denoise_method": "bilateral"
}
```

**Response 200:**
```json
{
  "status": "ok",
  "updated": {
    "exposure": -5,
    "denoise": {
      "enabled": true,
      "strength": 30,
      "method": "bilateral"
    }
  },
  "warnings": ["ISO 設定可能不支援"]
}
```

**參數說明:**
- `exposure`: 曝光時間 (-13 to -1)
- `iso`: ISO 感光度 (0=自動, 100-3200)
- `brightness`: 亮度 (0-255)
- `contrast`: 對比度 (0-255)
- `saturation`: 飽和度 (0-255)
- `sharpness`: 銳利度 (0-255)
- `auto_wb`: 自動白平衡 (boolean)
- `wb_temp`: 白平衡色溫 (2800-6500K)
- `denoise_enabled`: 啟用軟體降噪 (boolean)
- `denoise_strength`: 降噪強度 (0-100)
- `denoise_method`: 降噪演算法 ("fastNlMeans", "bilateral", "gaussian")
- `brightness_adjust`: 軟體亮度調整 (-100 to 100)
- `contrast_adjust`: 軟體對比度調整 (0.5 to 2.0)

**Error Responses:**
- `503 Service Unavailable`: 相機不可用
- `500 Internal Server Error`: 更新失敗

---

### 自動調整相機參數

#### `POST /api/camera/auto-adjust`
啟用自動曝光和自動白平衡

**Response 200:**
```json
{
  "status": "ok",
  "message": "Auto-adjustment enabled",
  "adjusted_params": {
    "auto_exposure": true,
    "auto_wb": true
  }
}
```

**Error Responses:**
- `503 Service Unavailable`: 相機不可用
- `500 Internal Server Error`: 自動調整失敗

---

### 獲取相機格式資訊

#### `GET /api/camera/format`
獲取當前相機使用的 FOURCC 格式資訊

**Response 200:**
```json
{
  "format": "YUYV",
  "description": "未壓縮格式",
  "is_compressed": false,
  "warning": null,
  "recommendation": "當前使用最佳格式"
}
```

**格式說明:**
- `YUYV`: 未壓縮格式 (最佳品質)
- `MJPG`: MJPEG 壓縮格式
- `YUY2`: YUV 格式

---

### 獲取影像處理統計

#### `GET /api/camera/stats`
獲取影像處理模組的效能統計資訊

**Response 200:**
```json
{
  "denoise_enabled": true,
  "denoise_method": "bilateral",
  "denoise_strength": 30,
  "brightness_adjust": 0,
  "contrast_adjust": 1.0,
  "processing_time_ms": 12.5,
  "frame_count": 1523,
  "avg_processing_time_ms": 12.5
}
```

**Error Responses:**
- `503 Service Unavailable`: 影像處理器不可用

---

## 相機參數 API 使用範例

### 啟用降噪
```bash
curl -X POST http://localhost:8001/api/camera/params \
  -H "Content-Type: application/json" \
  -d '{"denoise_enabled": true, "denoise_strength": 30, "denoise_method": "bilateral"}'
```

### 調整曝光和 ISO
```bash
curl -X POST http://localhost:8001/api/camera/params \
  -H "Content-Type: application/json" \
  -d '{"exposure": -5, "iso": 400}'
```

### 自動調整
```bash
curl -X POST http://localhost:8001/api/camera/auto-adjust
```

### 查詢相機格式
```bash
curl http://localhost:8001/api/camera/format
```

### 查詢處理統計
```bash
curl http://localhost:8001/api/camera/stats
```


### 獲取玩家統計
```bash
curl "http://localhost:8001/api/stats/player/玩家1"
```


---

## 錄影後處理狀態 API

### `GET /api/recording/postprocess/{game_id}`
查詢錄影停止後的背景處理狀態（縮圖、轉檔、資料庫同步）。

**Response 200:**
```json
{
  "game_id": "game_20260323_123456",
  "status": "processing",
  "started_at": 1774200000.12,
  "updated_at": 1774200002.91,
  "recording_dir": "recordings/game/nine_ball/game_20260323_123456"
}
```

**status 說明：**
- `queued`: 已排入背景工作佇列
- `processing`: 後處理進行中
- `done`: 後處理完成
- `failed`: 後處理失敗（會含 `error`）
- `unknown`: 找不到該 `game_id`

## 更新紀錄

- 03/23: '新增錄影後處理狀態查詢 API'
  - 範例：`GET /api/recording/postprocess/game_20260323_123456`
  - 規範用法：錄影停止 API 快速回應後，前端可輪詢本 API 顯示「後製中 / 已完成」。
  - 輸出格式：如上 `Response 200`。

- 03/23: '錄影停止 API 改為快回應'
  - 範例：`POST /api/recording/stop`
  - 規範用法：停止錄影請以 `status=stopped_pending_finalize` 視為已停止寫入；影片縮圖與轉檔在背景完成。
  - 輸出格式：
    ```json
    {
      "status": "stopped_pending_finalize",
      "game_id": "game_20260323_123456",
      "duration": 125.3,
      "frame_count": 3760,
      "file_size_mb": 0.0
    }
    ```
