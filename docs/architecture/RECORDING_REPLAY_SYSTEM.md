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
