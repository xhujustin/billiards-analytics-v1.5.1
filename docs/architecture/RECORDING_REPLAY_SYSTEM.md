# 錄影和回放系統技術文檔

## 系統架構

### 錄影流程
1. 使用 OpenCV 的 `VideoWriter` 錄製影片（mp4v 編碼）
2. 錄影完成後自動使用 FFmpeg 轉換為 H.264 編碼
3. 提取第一幀生成縮圖（640x360, 16:9）
4. 將錄影資訊同步到 SQLite 資料庫

### 回放流程
1. 從資料庫查詢錄影列表
2. 提供縮圖 API 顯示預覽
3. 提供影片 API 支援 HTTP 範圍請求
4. 前端使用 HTML5 video 標籤播放

## 核心模組

### RecordingManager
**位置：** `backend/recording_manager.py`

**主要功能：**
- `start_recording()` - 開始錄影
- `write_frame()` - 寫入影片幀
- `stop_recording()` - 停止錄影並處理
  - 生成縮圖
  - FFmpeg 轉換為 H.264
  - 同步到資料庫

**編碼策略：**
```python
# 錄製時使用 mp4v（OpenCV 兼容性好）
fourcc = cv2.VideoWriter_fourcc(*'mp4v')

# 完成後自動轉換為 H.264（瀏覽器支援）
ffmpeg -i video.mp4 -c:v libx264 -preset fast -crf 23 output.mp4
```

### Database
**位置：** `backend/database.py`

**Recordings 資料表：**
- game_id (主鍵)
- game_type (nine_ball, practice_single, practice_pattern)
- start_time, end_time, duration_seconds
- player1_name, player2_name, winner
- player1_score, player2_score, target_rounds
- video_path, video_resolution, video_fps, file_size_mb

###API 路由

#### 1. 縮圖 API
**位置：** `backend/api/thumbnail_api.py`
```
GET /api/recordings/{game_id}/thumbnail
Returns: image/jpeg (640x360)
```

#### 2. 影片 API
**位置：** `backend/api/replay_api.py`
```
GET /api/recordings/{game_id}/video
Returns: video/mp4 (支援 HTTP 範圍請求)
Headers:
  - Accept-Ranges: bytes
  - Content-Range: bytes {start}-{end}/{total}
```

#### 3. 錄影列表 API
```
GET /api/recordings?game_type=&player=&start_date=&end_date=&limit=20&offset=0
Returns: { recordings: [...], total: number }
```

#### 4. 刪除錄影 API
```
DELETE /api/recordings/{game_id}
功能：刪除資料庫記錄和檔案
```

## 檔案結構

```
recordings/
  └── game_YYYYMMDD_HHMMSS/
      ├── video.mp4           # 影片檔案（H.264 編碼）
      ├── thumbnail.jpg       # 縮圖（640x360）
      ├── metadata.json       # 遊戲元資料
      └── events.jsonl        # 遊戲事件日誌
```

## 工具腳本

### 錄影相關（test-program/recording/）
- `sync_recordings.py` - 手動同步錄影到資料庫
- `generate_thumbnails.py` - 批次生成縮圖
- `check_db.py` - 檢查資料庫記錄
- `check_video_codec.py` - 檢查影片編碼格式
- `convert_video.py` - 手動轉換影片為 H.264

### 回放 API 測試（test-program/replay/）
- `test_replay_api.py` - 測試回放 API
- `test_video_api.py` - 測試影片 API
- `test_api.py` - 簡單 API 測試

### 追蹤測試（test-program/tracking/）
- `test_tracking.py` - 測試球體追蹤
- `test_table_detection.py` - 測試球桌偵測
- `test_table_color.py` - 測試球桌顏色

### 工具測試（test-program/utils/）
- `test_camera.py` - 測試攝像頭
- `test_database.py` - 測試資料庫
- `test_performance.py` - 效能測試

## 問題排除

### 影片無法播放
**原因：** mp4v 編碼不被瀏覽器支援
**解決方案：** 
1. 確認已安裝 FFmpeg：`winget install ffmpeg`
2. 重新錄製遊戲，系統會自動轉換為 H.264

### 縮圖 404 錯誤
**原因：** 舊錄影沒有縮圖
**解決方案：**
```bash
cd backend/test-program/recording
python generate_thumbnails.py
```

### 回放列表為空
**原因：** 錄影未同步到資料庫
**解決方案：**
```bash
cd backend/test-program/recording
python sync_recordings.py
```

## 依賴項

- **OpenCV** - 影片錄製和處理
- **FFmpeg** - 影片格式轉換
- **FastAPI** - API 服務器
- **SQLite** - 資料庫

## 效能考量

1. **錄影效能：** mp4v 編碼效能好，適合即時錄製
2. **轉換時間：** H.264 轉換在錄影結束後執行，不影響錄製
3. **串流效能：** HTTP 範圍請求允許影片快進/後退
4. **縮圖大小：** 640x360 提供預覽同時節省頻寬

## 06/27:'新增擊球事件時間軸資料來源'

- 適用 API：`GET /api/recordings/{game_id}/events`
- 背景：舊回放時間軸只讀 `events` 表；實際擊球分析資料寫在 `shot_events` 表，因此 `events` 為空時前端會看不到「擊球」節點。
- 規範：當 `event_type` 未指定時，API 會合併原本 `events` 與 `shot_events`；當 `event_type=shot` 時，只回傳擊球事件。
- 輸出格式：每筆 `shot_events` 會轉為 `event_type: "shot"`，並補上 `source: "shot_events"`、`offset_seconds`、`timestamp` 與 `data`。
- `offset_seconds` 代表相對錄影開始的秒數；前端時間軸優先使用此欄位，避免 `start_time` 時區格式造成時間顯示偏移。
- 範例：
```json
{
  "id": 1000000352,
  "timestamp": 1782400945.006,
  "offset_seconds": 8.639,
  "event_type": "shot",
  "source": "shot_events",
  "data": {
    "shot_event_id": 352,
    "shot_index": 1,
    "mode": "practice_single",
    "target_ball": 1,
    "pocket_result": "missed",
    "cue_ball_potted": false,
    "is_foul": false
  }
}
```

## 06/27:'新增回放事件時間軸點擊跳轉功能'

- 功能位置：`frontend/src/components/pages/replay/ReplayPlayer.tsx`
- 使用方式：在回放播放器的事件時間軸中點擊任一事件列，播放器會將 `<video>` 的 `currentTime` 跳轉到該事件對應秒數。
- 鍵盤用法：事件列以 `<button>` 呈現，可透過 Tab 聚焦，按 Enter 或 Space 觸發跳轉。
- 時間來源規範：
  - 優先使用事件資料的 `offset_seconds`。
  - 若 `offset_seconds` 不存在，則以 `event.timestamp - recording.start_time` 推算相對秒數。
  - 跳轉時間會限制在 `0` 到影片 duration 或錄影 `duration_seconds` 範圍內，避免超出可播放區間。
- 事件格式範例：
```json
{
  "id": 1000000352,
  "timestamp": 1782400945.006,
  "offset_seconds": 8.639,
  "event_type": "shot",
  "data": {
    "shot_index": 1,
    "pocket_result": "missed",
    "cue_ball_potted": false,
    "is_foul": false
  }
}
```
- UI 輸出格式：
  - 事件名稱：`擊球 #1 - 未進`、`擊球 #2 - 進球`、`擊球 #3 - 犯規`
  - 時間格式：`m:ss`，例如 `0:08`、`1:24`
  - 當影片目前時間接近事件時間點 1 秒內時，事件列會顯示目前事件高亮狀態。

## 06/27:'修正分析頁台北時間基準'

- 適用 API：`GET /api/analytics/overview`、`GET /api/analytics/offense`、`GET /api/analytics/trends`、`GET /api/stats/player/{player_name}`
- 規範：分析頁的 `today/week/month/year` 統計區間以台北時間 UTC+8 為基準，`today` 從台北當日 `00:00:00` 開始。
- 寫入規範：新的 `shot_events.created_at` 若呼叫端未提供時間，後端會使用台北本地時間 ISO 字串。
- 顯示規範：近期練習日期前端優先解析 `game_YYYYMMDD_HHMMSS`，解析不到才 fallback 使用 `date` 欄位；避免瀏覽器時區轉換造成日期偏移。
- 範例：
```json
{
  "period": {
    "range": "today",
    "start": "2026-06-27T00:00:00",
    "end": "2026-06-27T23:27:34.778785"
  },
  "recent_practice_date_source": "game_id"
}
```

## 06/27:'修正 mobile analytics 台北時間基準'

- 適用 API：`GET /api/mobile/me`、`GET /api/mobile/profile/{username}` 內的 `analytics_v1`、球型練習、進攻摘要與週圖表資料。
- 資料來源：mobile analytics 一律優先讀 Supabase analytics repository；只有 Supabase 未設定或讀取失敗時才 fallback 本機 SQLite。
- 規範：mobile 的近 7 天、近 30 天、每週練習時數與每週擊球數一律由後端以台北時間 UTC+8 計算；不得直接使用 SQLite `datetime('now')` 作為 mobile analytics 基準。
- 組裝規範：`practice_mix`、`practice_overview`、`ball_shape_summary`、`offense_summary`、`practice_trend`、profile player level 共用 Supabase-first 的 recordings/shot_events helper，避免同一個 mobile payload 混用 Supabase 與 SQLite。
- 相容格式：查詢時會把 `YYYY-MM-DD HH:MM:SS` 正規化成 `YYYY-MM-DDTHH:MM:SS` 再比較，避免舊資料與 ISO 字串排序不一致。
- 輸出格式：`latest_practice_at`、球型練習 `recent_records[].date`、`latest_shot_at`、進攻 `recent_records[].created_at` 會回傳台北本地 ISO 字串。
- 範例：
```json
{
  "analytics_v1": {
    "weekly_summary": {
      "shot_count": 372
    },
    "ball_shape": {
      "latest_practice_at": "2026-06-27T23:24:56.344188"
    },
    "offense": {
      "latest_shot_at": "2026-06-27T23:22:25.006000"
    }
  }
}
```

## 06/27:'新增 mobile 下拉刷新'

- 適用畫面：`?prototype=mobile` 的 mobile prototype 外層容器。
- 互動規範：使用者在頁面頂部向下拖曳時顯示刷新提示；拖曳距離未達門檻時放手復位，達到門檻後顯示「放開刷新」。
- 輸入規範：使用 Pointer Events 實作，需支援手機觸控、平板觸控筆與桌面瀏覽器滑鼠拖曳測試。
- 觸發規範：放手後更新 `refreshKey`，目前頁面會重新掛載；資料頁會重新執行既有 `useEffect` 並重新呼叫 API。
- 狀態文字：`下拉刷新`、`放開刷新`、`更新中...`。
- 範例：
```tsx
<div
  key={`${activeTab}-${dataSection}-${refreshKey}`}
>
  {renderPage()}
</div>
```

## 06/27:'新增回放影片路徑 fallback 與 Range 防呆'

- 適用端點：`GET /api/recordings/{game_id}/video`、`GET /replay/burnin/{game_id}.mjpg`
- 規範用法：後端會先依 `recordings.video_path` 找影片；若資料庫路徑是相對路徑，會以專案根目錄解析；若資料庫路徑已失效，會 fallback 掃描 `recordings/**/{game_id}/video.mp4`。
- 列表規範：`GET /api/recordings?mode=practice` 會包含 `practice_single`、`practice_pattern`、`practice_accuracy`；若 Supabase analytics 已設定但列表回傳空資料，第一頁會 fallback 讀取本機 SQLite，避免本機錄影紀錄消失。
- 播放狀態：列表與明細回傳會附帶 `has_video`，前端可在 `has_video=false` 時顯示「影片檔遺失」提示，但仍需允許使用者進入播放器實際嘗試載入 `/api/recordings/{game_id}/video`；只有影片端點實際失敗時才顯示無法播放，避免路徑偵測誤判擋住可播放影片。
- 舊路徑映射：若資料庫 `video_path` 是舊電腦絕對路徑，但路徑中包含 `recordings/.../{game_id}/video.mp4`，後端會改映射到目前專案的 `recordings/.../{game_id}/video.mp4`。
- 播放器策略：前端播放器使用原本的 HTML5 `<video controls>` 與 `/api/recordings/{game_id}/video` MP4 端點；若遇到 OpenCV 產出的 `mp4v` MP4 在瀏覽器無法解碼，可改用 `/replay/burnin/{game_id}.mjpg` MJPEG 串流作備援或診斷。
- 前端代理：Vite dev server 保留 `/replay` proxy 到 `http://127.0.0.1:8001`，供 MJPEG 備援與診斷端點使用。
- H.264 轉檔規範：錄影後處理已設計為使用 ffmpeg 將 `mp4v` 轉為 `H.264/avc1`；後端會優先讀 `FFMPEG_PATH`，其次使用系統 PATH 的 `ffmpeg`。若找不到 ffmpeg、轉檔失敗或超時，postprocess 狀態會保留 `done_unconverted` 並附錯誤訊息，影片仍保留原始 `mp4v`。
- 本機 FFmpeg：Windows 可攜版安裝在 `tools/ffmpeg/bin/ffmpeg.exe`；`start.bat` 會設定 `FFMPEG_PATH` 指向此檔案，後端需重啟後才會套用。
- 日期規範：前端優先從 `game_YYYYMMDD_HHMMSS` 解析顯示錄製時間；若 ID 不符合格式，才 fallback 使用 `start_time`，避免瀏覽器時區轉換造成日期偏移。
- 範例：資料庫仍保留舊電腦路徑時，只要目前專案的 `recordings/practice/single/{game_id}/video.mp4` 存在，播放器仍可取得影片。
- 輸出格式：成功時回傳 `video/mp4` 與 `Accept-Ranges: bytes`；Range 成功時回傳 `206` 與 `Content-Range`；不合法 Range 回傳 `416` 與 `Content-Range: bytes */{file_size}`；影片不存在時回傳 JSON 錯誤並包含 `game_id` 與原始 `video_path`。
