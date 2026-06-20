# Burn-in 效能優化指南

## 概述

v1.5 版本針對 burn-in 串流進行了全面的效能優化,主要目標是降低延遲、提升 FPS 穩定性,並減少 CPU 使用率。

## 核心優化

### 1. ThreadPool 非阻塞 YOLO 推論

**問題**: 原先 YOLO 推論為同步執行,阻塞主循環,導致延遲增加。

**解決方案**: 
- 使用 `ThreadPoolExecutor` 將 YOLO 推論移至背景執行
- 主循環繼續更新 MJPEG 串流 (複用快取的 overlay)
- 推論完成後異步更新,延遲最多 1 幀 (約 33ms)

**效果**: 延遲降低約 40%

### 2. 訂閱者檢查機制

**問題**: 即使無客戶端連接,仍持續進行影像編碼和 resize,浪費 CPU。

**解決方案**:
- 檢查 `mjpeg_manager.monitor._active_connections`
- 僅在有訂閱者時才進行編碼
- 透過 `ENABLE_SUBSCRIBER_CHECK` 配置控制

**效果**: 無訂閱者時 CPU 使用率降低 50-70%

### 3. 效能監控模組

**新增模組**: `performance_monitor.py`

**功能**:
- 滑動視窗追蹤 FPS (預設 30 幀)
- 計算平均處理延遲
- 提供效能統計 API

**API 端點**: `GET /api/performance/stats`

### 4. 可選的自適應品質調整

**功能**:
- 根據 FPS 自動調整 MJPEG 品質
- 預設關閉,由用戶啟用

**品質等級**:
- FPS < 20: 品質 40 (低)
- FPS < 25: 品質 55 (中)
- FPS ≥ 25: 品質 70 (標準)

**API 控制**: `POST /api/stream/quality`

### 5. simplejpeg 加速 JPEG 編碼

**功能**:
- 使用 simplejpeg 取代 OpenCV 進行 JPEG 編碼
- 編碼速度提升 2-3倍
- 降低 CPU 使用率

**安裝**:
```bash
pip install simplejpeg>=1.9.0
```

**效果**: 
- MJPEG 串流編碼延遲降低 50-70%
- 支援更高解析度或更高 FPS
- 自動 fallback 到 OpenCV (如果 simplejpeg 不可用)

**實作位置**: `backend/streaming/mjpeg_streamer.py`

## 配置參數

### backend/config.py

```python
# --- Burn-in Performance Settings ---
ENABLE_ADAPTIVE_QUALITY = get_bool_env("ENABLE_ADAPTIVE_QUALITY", "false")  
ENABLE_SUBSCRIBER_CHECK = get_bool_env("ENABLE_SUBSCRIBER_CHECK", "true")   
```

### 環境變數

```bash
# .env
ENABLE_ADAPTIVE_QUALITY=false  # 自適應品質 (預設關閉)
ENABLE_SUBSCRIBER_CHECK=true   # 訂閱者檢查 (預設開啟)
```

## API 參考

### GET /api/performance/stats

獲取即時效能統計數據。

**Response:**
```json
{
  "current_fps": 29.5,
  "avg_latency_ms": 85.2,
  "stream_active": true,
  "is_analyzing": true,
  "mjpeg_stats": {
    "monitor": {...},
    "projector": {...}
  }
}
```

### POST /api/stream/quality

設定串流品質模式。

**Request:**
```json
{
  "stream_id": "camera1",
  "quality": "auto",      // "low" | "med" | "high" | "auto"
  "enable_auto": true
}
```

**Response:**
```json
{
  "stream_id": "camera1",
  "quality": "auto",
  "auto_quality_enabled": true,
  "current_quality": 70
}
```

## 前端整合

### Dashboard 即時效能顯示

TopBar 組件自動顯示即時 FPS 和延遲:

```tsx
<div className="performance-stats">
  <div className="perf-stat">
    <span className="perf-label">FPS:</span>
    <span className="perf-value fps-value">29.5</span>
  </div>
  <div className="perf-stat">
    <span className="perf-label">延遲:</span>
    <span className="perf-value latency-value">85ms</span>
  </div>
</div>
```

**更新頻率**: 每 2 秒自動獲取最新數據

## 效能改善數據

| 指標 | 優化前 | 優化後 | 改善 |
|------|--------|--------|------|
| 延遲 | 150-200ms | 80-120ms | ↓ 40% |
| FPS | 20-25 | 28-30 | ↑ 25% |
| CPU (無訂閱者) | 15-20% | 5-10% | ↓ 50% |

## 故障排除

### FPS 顯示為 0

**原因**: PerformanceMonitor 尚未初始化

**解決**: 
1. 確認後端已啟動 camera_capture_loop
2. 檢查 console 是否有 "Starting optimized camera capture loop" 訊息

### 數值不更新

**原因**: 前端無法連接到效能統計 API

**解決**:
1. 檢查 `/api/performance/stats` 端點是否可訪問
2. 查看瀏覽器 console 的錯誤訊息
3. 確認後端 CORS 設定正確

### 自適應品質無效

**原因**: 功能未啟用

**解決**:
1. 透過 API 啟用: `POST /api/stream/quality` 設定 `quality: "auto"`
2. 或設定環境變數: `ENABLE_ADAPTIVE_QUALITY=true`

## V1.5 規範符合性

✅ **完全符合 v1.5 技術指南**

- Burn-in 優先架構 (後端合成,前端僅播放)
- Metadata 不驅動高頻 re-render
- 使用 throttle/batching 避免 UI 卡頓
- WebSocket 協議不變
- REST API 錯誤處理標準化

## 相關文件

- [API 參考](./api/API_REFERENCE.md)
- [v1.5 規範符合性檢查](../troubleshooting/BURN_IN_FIX.md)
- [實作完成報告](../artifacts/walkthrough.md)

## 更新紀錄

- 04/25: '新增 YOLO GPU/CUDA 啟動診斷與安裝流程'
  - 範例：後端啟動時會輸出 `YOLO inference device: cuda:0, cuda_available=True`，若顯示 `cpu` 則代表 PyTorch 未看到 CUDA。
  - 規範用法：
    - 啟動 YOLO 前可執行 `.\.venv\Scripts\python.exe backend\test-program\utils\check_yolo_gpu.py`。
    - `YOLO_DEVICE=auto` 會在 CUDA 可用時使用 `cuda:0`，否則回退 CPU。
    - `install.bat` 偵測到 `nvidia-smi` 時會優先安裝 CUDA 版 PyTorch。
  - 輸出格式：
    ```text
    torch: 2.x.x+cu128
    torch_cuda: 12.8
    cuda_available: True
    cuda_device_name: NVIDIA GeForce RTX 2070 SUPER
    ```

- 03/22: '新增按需啟動 camera capture 執行緒與回放分頁查詢優化'
  - 範例：首次請求 `GET /burnin/camera1.mjpg?quality=med` 才啟動 `camera_capture_loop`，後端啟動不再立即打開攝影機。
  - 規範用法：
    - 串流端點會在處理請求前呼叫 `ensure_camera_capture_started()`。
    - 回放列表請使用 `/api/recordings?mode=game|practice&limit=6&offset=0` 由後端分頁。
  - 輸出格式：
    ```json
    {
      "recordings": [],
      "total": 0,
      "limit": 6,
      "offset": 0
    }
    ```

- 03/23: '新增可重複執行穩定度測試腳本（PowerShell）'
  - 範例：
    ```powershell
    powershell -ExecutionPolicy Bypass -File backend/test-program/utils/stability_benchmark.ps1 -BaseUrl http://localhost:8001 -PlayerName 玩家1 -Iterations 200 -Warmup 10 -TimeoutSec 5
    ```
  - 規範用法：
    - 先啟動後端，再執行腳本。
    - 腳本固定測試 `health`、`/api/recordings?mode=...`、`/api/stats/player/{name}`、`/api/stats/summary`、`/api/performance/stats`。
    - 每次測試會輸出 PASS/WARN/FAIL，並將完整報告寫入 `backend/test-program/reports/`。
  - 輸出格式（JSON）：
    ```json
    {
      "run_at": "2026-03-23 00:00:00",
      "base_url": "http://localhost:8001",
      "iterations": 200,
      "warmup": 10,
      "overall": {
        "overall_error_rate": 0.5,
        "worst_p95_ms": 180.4,
        "worst_p99_ms": 310.8
      },
      "endpoints": [
        {
          "name": "stats_summary",
          "health": "PASS",
          "error_rate": 0,
          "rps": 55.2,
          "latency_ms": { "p50": 32.1, "p95": 78.4, "p99": 110.2 }
        }
      ]
    }
    ```

- 03/23: '新增前端輪詢可見性降頻與防重疊請求優化'
  - 範例：
    - `TopBar` 改為頁面可見時 2 秒輪詢，背景頁降為 5 秒，且同時間僅允許一個 `/api/performance/stats` 請求。
    - `PracticePage` 練習狀態輪詢由固定 500ms 改為可見頁 1000ms、背景頁 3000ms，並採用「請求完成再排下一次」策略。
  - 規範用法：
    - 高頻監控 API 必須避開 `setInterval` 重疊請求，優先採用遞迴 `setTimeout` + in-flight guard。
    - 背景分頁應啟用 `document.visibilityState` 降頻，降低不必要負載。
  - 輸出格式：
    ```json
    {
      "polling": {
        "topbar_visible_ms": 2000,
        "topbar_hidden_ms": 5000,
        "practice_visible_ms": 1000,
        "practice_hidden_ms": 3000,
        "inflight_guard": true
      }
    }
    ```

- 03/23: '新增相機開啟/重連快速路徑與動態回退優化'
  - 範例：
    - 相機第一次成功後會記住 `last_good_backend` 與 `last_good_profile`，下次重連優先使用該組合。
    - `camera_capture_loop` 讀幀失敗時採用 `reconnect_backoff_sec`（0.2s 起跳，失敗倍增到 2.5s 上限）避免長時間固定阻塞。
  - 規範用法：
    - `open_camera()` 不應使用固定長暖機，優先短暖機驗證（8 幀中至少 3 幀成功）再進入串流。
    - WebSocket 視訊連線優先復用 `camera_state["current_cap"]`，僅在不存在或已關閉時重新開啟硬體。
  - 輸出格式：
    ```json
    {
      "camera_reconnect": {
        "fast_path": true,
        "cached_backend": "CAP_DSHOW",
        "cached_profile": [1280, 720, 30],
        "backoff_seconds": {
          "initial": 0.2,
          "multiplier": 1.8,
          "max": 2.5
        }
      }
    }
    ```

- 03/23: '修正拔插相機後無法重連（自動重新枚舉 + 候選裝置重試）'
  - 範例：
    - 讀幀失敗重連時，先嘗試 `selected_device_id`，若失敗再掃描目前可用相機並逐一嘗試。
    - 當 USB 拔插導致相機編號改變時，系統可改用 fallback id 自動恢復串流。
  - 規範用法：
    - 重連流程必須允許裝置 id 漂移，不可只重試單一 id。
    - `open_camera()` 失敗需清除 `camera_state["current_cap"]`，避免前端誤復用 stale handle。
  - 輸出格式：
    ```json
    {
      "reconnect_result": {
        "preferred_device_id": 0,
        "actual_device_id": 1,
        "used_fallback": true,
        "status": "reconnected"
      }
    }
    ```

- 03/23: '重構相機讀幀與釋放流程，移除重複程式碼'
  - 範例：
    - 新增 `safe_release_capture(cap)` 統一處理 `cap.release()` 的例外保護。
    - 新增 `read_frame_with_looped_video_source(cap)`，統一影片來源結尾回到第 0 幀再讀取的流程。
  - 規範用法：
    - 相機循環與 WebSocket 視訊循環都應呼叫共用 helper，避免複製貼上邏輯分岔。
    - 釋放 `VideoCapture` 時優先使用 `safe_release_capture()`，維持一致錯誤處理。
  - 輸出格式：
    ```json
    {
      "refactor": {
        "helpers": [
          "safe_release_capture",
          "read_frame_with_looped_video_source"
        ],
        "duplicate_paths_removed": [
          "camera_capture_loop frame read",
          "ws/video frame read",
          "multiple cap.release try/except"
        ]
      }
    }
    ```

- 03/23: '主迴圈分流降頻 + 停止錄影快回應優化'
  - 範例：
    - `camera_capture_loop` 依據訂閱者分開更新 monitor/projector，避免「只有監控頁時仍做投影渲染」。
    - `/ws/video` 同步 MJPEG 更新改為 `ws_mjpeg_every_n=2`（每 2 幀更新一次）。
    - `stop_recording` 立即回傳 `stopped_pending_finalize`，縮圖/FFmpeg/DB 同步在背景執行。
  - 規範用法：
    - 監控流降頻參數：`system_state.monitor_stream_every_n`。
    - 投影流降頻參數：`system_state.projector_stream_every_n`。
    - WebSocket 同步 MJPEG 降頻參數：`system_state.ws_mjpeg_every_n`。
    - 錄影停止後可輪詢 `/api/recording/postprocess/{game_id}` 追蹤後處理狀態。
  - 輸出格式：
    ```json
    {
      "recording_stop": {
        "status": "stopped_pending_finalize",
        "game_id": "game_20260323_123456",
        "duration": 125.3,
        "frame_count": 3760,
        "file_size_mb": 0.0
      },
      "postprocess": {
        "game_id": "game_20260323_123456",
        "status": "processing"
      }
    }
    ```

- 03/23: '前端練習模式 FPS/卡頓優化（降重繪與降頻）'
  - 範例：
    - 練習狀態輪詢 `setStats` 改為「數值有變更才更新 state」，避免每次輪詢都觸發重繪。
    - 可見頁輪詢間隔由 1000ms 調整為 1500ms，背景頁由 3000ms 調整為 4000ms。
    - 練習串流改為 `quality=low`，降低解碼與傳輸負載。
  - 規範用法：
    - 高頻輪詢頁面應避免無差異 state 更新（same-value setState）。
    - 在硬體吃緊時，優先降低畫質與輪詢頻率，維持操作流暢度。
  - 輸出格式：
    ```json
    {
      "practice_page": {
        "stats_update_on_change_only": true,
        "polling_visible_ms": 1500,
        "polling_hidden_ms": 4000,
        "stream_quality": "low"
      }
    }
    ```

- 03/23: '修正 DSHOW 無法 index 開啟時的警告洪水與重連失敗'
  - 範例：
    - 相機開啟流程改為 backend preflight（`DEFAULT -> MSMF -> DSHOW -> ANY`），每個 backend 只嘗試一次。
    - 不再對同一 backend 於每個解析度都重新 `VideoCapture(device_id, backend)`，避免重複警告。
  - 規範用法：
    - `last_good_backend` 可為 `None`（代表 DEFAULT backend）。
    - 枚舉相機優先使用 `DEFAULT/MSMF`，`DSHOW` 僅作 fallback。
  - 輸出格式：
    ```json
    {
      "camera_backend": {
        "probe_order": ["DEFAULT", "MSMF", "DSHOW", "ANY"],
        "open_strategy": "one_open_per_backend",
        "last_good_backend": "DEFAULT"
      }
    }
    ```

- 03/23: '降低相機 backend 警告噪音與越界探測'
  - 範例：
    - 啟動時將 OpenCV log level 降為 `ERROR`，避免 `MSMF/DSHOW` 重試時刷屏。
    - 相機枚舉加入「連續 3 個 index miss 即停止」策略，避免 out-of-range 探測過長。
  - 規範用法：
    - backend 候選優先順序：`cached -> DSHOW -> DEFAULT`。
    - 重連候選裝置來源以枚舉結果為主，不再盲試固定 `0..3`。
  - 輸出格式：
    ```json
    {
      "camera_probe": {
        "opencv_log_level": "ERROR",
        "stop_after_consecutive_miss": 3,
        "backend_order": ["cached", "DSHOW", "DEFAULT"]
      }
    }
    ```


- 03/23: '修正 Windows CMD ANSI 壓縮/亂碼與日誌刷屏'
  - 範例：
    - `backend/main.py` 啟動參數改為 `use_colors=False`，停用 ANSI 色碼輸出。
    - 同步設定 `access_log=False`，避免高頻 HTTP access log 擠壓終端畫面。
  - 規範用法：
    - Windows CMD 環境優先關閉色彩控制碼，降低控制字元干擾。
    - 在效能調校期間可暫時關閉 access log，僅保留應用層必要日誌。
  - 輸出格式：
    ```json
    {
      "uvicorn": {
        "use_colors": false,
        "access_log": false
      }
    }
    ```

- 05/03: '新增主影像迴圈分段效能診斷與預覽視窗開關'
  - 範例：
    - `/api/performance/stats` 會回傳 `stage_latency_ms`，用來定位低 CPU/GPU 佔用但 FPS 低的等待點。
    - `cv2.imshow()` / `cv2.waitKey()` 改由 `ENABLE_CAMERA_PREVIEW_WINDOW` 控制，預設關閉，避免 Windows 後端主迴圈被 GUI 預覽拖慢。
  - 規範用法：
    - `PERF_DIAGNOSTICS_ENABLED=true` 開啟分段耗時統計。
    - `ENABLE_CAMERA_PREVIEW_WINDOW=false` 為正式執行預設值；只有本機影像除錯時才開啟。
    - `CAMERA_GRAB_FLUSH_FRAMES=-1` 表示依曝光自動決定清 buffer 次數；設定為 `0` 可測試不清 buffer 的相機讀取延遲。
  - 輸出格式：
    ```json
    {
      "stage_latency_ms": {
        "camera_read": { "avg_ms": 8.2, "last_ms": 7.9, "samples": 30 },
        "camera_grab": { "avg_ms": 2.1, "last_ms": 2.0, "samples": 30 },
        "fps_cap_sleep": { "avg_ms": 12.5, "last_ms": 12.3, "samples": 30 }
      },
      "camera_preview_window": false,
      "camera_grab_flush_frames": -1
    }
    ```

- 05/03: '新增曝光低頻快取與錄影背景 queue'
  - 範例：
    - `CAP_PROP_EXPOSURE` 不再每幀查詢，改用 `CAMERA_EXPOSURE_CACHE_FRAMES` 控制查詢頻率，降低相機屬性查詢等待。
    - 錄影主迴圈改成 `recording_enqueue`，只把 frame 丟入 queue；背景 writer 負責 resize 到錄影解析度與 `VideoWriter.write()`。
  - 規範用法：
    - `CAMERA_EXPOSURE_CACHE_FRAMES=30` 表示每 30 幀更新一次曝光值。
    - 錄影 queue 滿載時會丟棄最舊幀，避免即時串流被磁碟或 encoder 拖慢。
  - 輸出格式：
    ```json
    {
      "stage_latency_ms": {
        "camera_exposure_get": { "avg_ms": 0.2, "samples": 1 },
        "recording_enqueue": { "avg_ms": 1.0, "samples": 30 }
      },
      "recording_stop": {
        "frame_count": 1800,
        "dropped_frames": 0
      }
    }
    ```

- 05/03: '新增 stage 診斷 stale_frames'
  - 範例：
    - `stage_latency_ms` 每個 stage 新增 `last_frame_id` 與 `stale_frames`，用來判斷該耗時是否為最近幀仍在發生。
  - 規範用法：
    - `stale_frames=0` 表示該 stage 在最新幀有更新。
    - `stale_frames>0` 表示該 stage 是舊樣本；解讀平均耗時時應避免把它當成目前瓶頸。
  - 輸出格式：
    ```json
    {
      "stage_latency_ms": {
        "fps_cap_sleep": {
          "avg_ms": 12.5,
          "last_ms": 12.3,
          "samples": 30,
          "last_frame_id": 2400,
          "stale_frames": 0
        }
      }
    }
    ```

- 05/03: '修正 MJPEG 重複送舊幀造成的串流緩衝延遲'
  - 範例：
    - `MJPEGStream.generate()` 改為記錄 `frame_id`，只有新幀到達時才送出，避免高 FPS 模式下 tight loop 重複送同一張 JPEG。
    - MJPEG `StreamingResponse` 加上 `Cache-Control: no-store` 與 `X-Accel-Buffering: no`，降低瀏覽器或代理層緩衝。
  - 規範用法：
    - FPS 正常但體感延遲大時，優先檢查串流是否送出重複舊幀或被瀏覽器緩衝。
    - `mjpeg_stats.total_frames` 代表後端更新幀數；串流端應跟隨新 frame_id，而不是無限制重送快取幀。
  - 輸出格式：
    ```json
    {
      "mjpeg_low_latency": {
        "send_only_new_frame": true,
        "cache_control": "no-store",
        "x_accel_buffering": "no"
      }
    }
    ```

- 05/03: '降低端到端串流延遲與補強相機/連線診斷'
  - 範例：
    - MJPEG JPEG 編碼移出 `_frame_lock`，避免慢速 client 或高畫質編碼阻塞主擷取迴圈更新新幀。
    - 主影像迴圈改為只處理 monitor；projector 渲染交給背景 worker，避免投影畫面拖慢主串流。
    - `/ws/video` 舊影像 WebSocket 預設停用，避免誤連後重複讀相機、重複 resize/warp/encode，或在斷線時釋放主串流相機。
  - 規範用法：
    - `ENABLE_LEGACY_VIDEO_WS=false` 為預設值；前端正式路徑應使用 `/burnin/{stream_id}.mjpg` 搭配 `/ws/control`。
    - `/api/performance/stats` 的 `camera` 欄位用於確認實際 backend、FOURCC 與解析度；若 `camera_read` 偏高，先比較 `MJPG/YUY2/YUYV` 實際格式。
    - `mjpeg_stats.*.connections` 用於確認是否有殘留 `<img>` 或舊分頁造成多條 monitor/projector 串流。
  - 輸出格式：
    ```json
    {
      "camera": {
        "selected_device_id": 0,
        "last_good_backend_name": "DSHOW",
        "last_good_profile": [1280, 720, 30],
        "actual_profile": [1280, 720, 30.0],
        "fourcc_info": {
          "requested": "MJPG",
          "actual": "MJPG",
          "is_compressed": true
        },
        "last_frame_age_ms": 12.5
      },
      "mjpeg_stats": {
        "monitor": {
          "active_connections": 1,
          "connections": [
            {
              "id": "12345678",
              "quality": 70,
              "age_sec": 35.2,
              "last_sent_frame_id": 900,
              "idle_sec": 0.02
            }
          ]
        }
      },
      "legacy_video_ws": {
        "enabled": false,
        "replacement": "/burnin/{stream_id}.mjpg + /ws/control"
      }
    }
    ```

- 05/03: '優先使用 MJPG 相機格式並主動取代舊 MJPEG 連線'
  - 範例：
    - `CAMERA_FOURCC_PRIORITY` 預設改為 `MJPG,YUY2,YUYV`，優先使用相機端 MJPEG 壓縮格式，降低 USB 未壓縮幀造成的 `camera_read` 延遲。
    - `/burnin/{stream_id}.mjpg` 與 `/stream/*` 支援 `client_id`；同一 `client_id` 建立新連線時，後端會標記舊連線為 replaced 並主動結束。
    - `StreamPage` 固定帶 `client_id=stream-page-monitor`，切換畫質時不再讓 high/med/low 多條連線長時間並存。
    - Practice/Game/相機參數/校正頁的 MJPEG `<img>` 都帶 page-specific `client_id`，方便在 `mjpeg_stats.connections` 中定位來源。
    - Burn-in `high` 畫質由 JPEG 100 降為 85，避免高畫質連線大幅增加編碼與瀏覽器解碼延遲。
    - 後端對 monitor/projector 串流套用 `exclusive_group`，同一群組只保留最新連線；即使瀏覽器沒有即時釋放舊 `<img>`，舊連線也會被主動結束。
  - 規範用法：
    - 若特定相機使用 `MJPG` 反而不穩，可用環境變數改回 `CAMERA_FOURCC_PRIORITY=YUY2,MJPG,YUYV`。
    - 前端任何長生命週期 MJPEG `<img>` 都建議帶穩定 `client_id`，例如 `client_id=practice-monitor`。
    - 若要手動開 projector 頁面，建議使用 `/burnin/projector.mjpg?quality=med&client_id=projector-display`。
    - 判讀 `/api/performance/stats` 時，若 `fourcc_info.is_compressed=false` 且 `camera_read` 接近 30ms，代表瓶頸主要在相機/USB/driver 讀幀。
  - 輸出格式：
    ```json
    {
      "camera": {
        "fourcc_info": {
          "requested": "MJPG",
          "actual": "MJPG",
          "is_compressed": true
        }
      },
      "mjpeg_stats": {
        "monitor": {
          "active_connections": 1,
          "connections": [
            {
              "client_id": "stream-page-monitor",
              "exclusive_group": "monitor",
              "quality": 70,
              "replaced": false
            }
          ]
        }
      }
    }
    ```

- 05/03: '限制 projector render FPS，避免 AR 投影拖慢主監控串流'
  - 範例：
    - `projector_renderer.render()` 原本在 projector 有連線時每個相機 frame 都執行；在 1280x720@30 + 1920x1080 投影畫面下，單次 render 可能佔 10-15ms。
    - 新增 `PROJECTOR_RENDER_MAX_FPS`，預設 `12`，讓投影畫面按上限重畫；monitor 串流仍可維持相機主迴圈即時更新。
    - projector render 可獨立限速；即使 YOLO 改為每幀執行，投影畫面仍可用較低 FPS 更新，避免主監控串流被 1920x1080 投影重畫拖慢。
  - 規範用法：
    - `PROJECTOR_RENDER_MAX_FPS=12` 為預設建議值，適合降低主串流延遲。
    - 若要更平滑投影，可設 `PROJECTOR_RENDER_MAX_FPS=20`。
    - 若要完全不限制，可設 `PROJECTOR_RENDER_MAX_FPS=0`，但主迴圈會重新承擔每幀 projector render 成本。
  - 輸出格式：
    ```json
    {
      "projector_render_max_fps": 12,
      "stage_latency_ms": {
        "projector_render_update": {
          "avg_ms": 12.0,
          "stale_frames": 2
        }
      }
    }
    ```

- 05/10: '優化 OpenCV projector 繪圖快取與局部疊圖'
  - 範例：
    - `ProjectorRenderer` 會快取 idle 畫面與 calibration ArUco 畫面。
    - 球型練習固定球位圖層、靜態 AR 路線圖層與 timer 圖層的快取改為 opt-in，預設 `PROJECTOR_RENDER_CACHE_ENABLED=false`，避免動態投影資料延遲時保留舊畫面。
    - `_draw_zone_marker()` 的填色圓改為只複製標記附近 ROI 後做 `cv2.addWeighted()`，不再為單一半透明圓複製整張 1920x1080 frame。
    - 靜態 AR 快取以 `route_segments`、`ghost_balls`、`cue_landing_point`、`cue_landing_zone`、`position_play`、`table_polygon` 等資料建立 fingerprint；球桿雷射線仍每次獨立繪製，避免 live cue laser 被快取鎖住。
    - timer 圖層以 15 FPS bucket 快取，倒數與警示呼吸仍會更新，但不跟著 projector worker 每次都重新計算文字與警示框。
  - 規範用法：
    - 正確性優先時維持 `PROJECTOR_RENDER_CACHE_ENABLED=false`。
    - 若確認投影資料更新穩定、且 projector render 成本仍偏高，再設定 `PROJECTOR_RENDER_CACHE_ENABLED=true` 啟用動態繪圖快取。
    - 若投影路線或球型練習球位沒有更新，先看 `/api/performance/stats.projector_render_stats.cache` 中 `static_ar_misses`、`setup_balls_misses` 是否在資料變更時增加。
    - 若投影 timer 不動，檢查 `game_timer.updated_at`、`remaining_time` 與 `projector_render_stats.stage_latency_ms.projector_game_timer_cache_build` 是否仍有週期性更新。
    - 若半透明 zone 標記成本偏高，觀察 `stage_latency_ms.projector_zone_marker_roi_blend.avg_ms`；正常情況應只反映小區域 ROI 疊圖，而不是整張 frame 複製。
    - 若需要最低延遲，仍優先調整 `PROJECTOR_RENDER_MAX_FPS` 與 overlay 顯示模式；本優化不改 YOLO 推論與 MJPEG wire format。
  - 輸出格式：
    ```json
    {
      "projector_render_stats": {
        "mode": "game",
        "width": 1920,
        "height": 1080,
        "stage_latency_ms": {
          "projector_static_ar_cache_build": 1.8,
          "projector_game_timer_compose": 0.6,
          "projector_render_game": 4.2
        },
        "cache": {
          "static_ar_hits": 120,
          "static_ar_misses": 3,
          "timer_hits": 85,
          "timer_misses": 18,
          "setup_balls_hits": 40,
          "setup_balls_misses": 1
        }
      },
      "stage_latency_ms": {
        "projector_render_worker": {
          "avg_ms": 6.5
        },
        "projector_static_ar_cache_build": {
          "avg_ms": 1.8
        }
      }
    }
    ```

- 05/10: '新增 monitor overlay 圖層快取'
  - 範例：
    - `render_annotations_scaled()` 支援依 metadata 來源幀、標註模式、輸入尺寸與輸出尺寸建立 overlay cache key。
    - 此快取預設 `MONITOR_OVERLAY_CACHE_ENABLED=false`，因為 monitor 是給校正與即時觀察使用，優先避免舊 overlay layer 貼到最新相機 frame。
    - 開啟快取後，metadata 沒變時，只把上一張 overlay layer 透過 mask 合成到最新相機 frame，不再每幀重跑 `_draw_annotations()`。
    - monitor 的走位 zone 半透明填色也改為 ROI 疊圖，避免小範圍標記造成整張畫面 copy。
  - 規範用法：
    - 正確性優先時維持 `MONITOR_OVERLAY_CACHE_ENABLED=false`。
    - 若只需要穩定展示、且 metadata 延遲已低於 `OVERLAY_METADATA_MAX_AGE_MS`，可設定 `MONITOR_OVERLAY_CACHE_ENABLED=true`。
    - `TRACKER_ANNOTATION_MODE=tactical` 仍是低延遲建議值；`full` 可用但會有更多文字與球號繪製成本。
    - 觀察 `/api/performance/stats.monitor_overlay_cache.hits` 是否持續增加；若 misses 每幀增加，代表 YOLO metadata 每幀都在更新，快取幫助會較小。
    - 若要最低延遲監控畫面，可切換 `POST /api/control/overlay-mode` 為 `{ "mode": "none" }`。
  - 輸出格式：
    ```json
    {
      "monitor_overlay_cache": {
        "hits": 240,
        "misses": 30,
        "has_layer": true,
        "has_mask": true
      },
      "stage_latency_ms": {
        "monitor_overlay_compose": {
          "avg_ms": 8.5
        }
      }
    }
    ```

- 05/03: 'YOLO 改為每幀執行'
  - 範例：
    - `system_state["yolo_skip_frames"]` 預設由 `2` 改為 `0`，代表每個相機 frame 都嘗試提交 YOLO。
    - 練習模式啟動時不再強制改成 `1`，維持每幀辨識，提升球桿/球位跟手性。
  - 規範用法：
    - `POST /api/control/yolo-skip` 傳 `{ "skip_frames": 0 }` 表示每幀執行。
    - 若硬體負載或延遲升高，可改 `{ "skip_frames": 1 }` 表示每 2 幀執行一次。
  - 輸出格式：
    ```json
    {
      "status": "success",
      "yolo_skip_frames": 0,
      "inference_frequency": "1/1 frames"
    }
    ```

- 05/03: '監控影像串流與 YOLO overlay 解耦'
  - 範例：
    - monitor MJPEG 預設直接輸出最新相機 frame，不再使用 `cached_overlay/display_frame` 作為主畫面來源。
    - YOLO 繼續在背景更新 metadata、AR route、projector 資料；前端監控畫面不再等待 YOLO overlay。
  - 規範用法：
    - `MONITOR_STREAM_USE_YOLO_OVERLAY=true` 為預設模式，monitor 會顯示後端畫出的 YOLO overlay。
    - 若需要最低延遲原始監控畫面，可設 `MONITOR_STREAM_USE_YOLO_OVERLAY=false`。
  - 輸出格式：
    ```json
    {
      "monitor_stream_use_yolo_overlay": true,
      "stage_latency_ms": {
        "mjpeg_monitor_update": {
          "avg_ms": 2.0,
          "stale_frames": 0
        }
      }
    }
    ```

- 05/03: '新增 tactical overlay 顯示模式'
  - 範例：
    - `TRACKER_ANNOTATION_MODE=full` 保留原本完整標註，包含球桌框、球袋、所有球標籤、球桿文字、成功率與輔助資訊。
    - `TRACKER_ANNOTATION_MODE=tactical` 只顯示母球、目標球、路線與母球落點，降低畫面干擾，也減少不必要的 overlay 繪製。
    - `TRACKER_ANNOTATION_MODE=none` 不繪製 YOLO overlay，保留影像本身與 metadata 更新。
    - 練習模式的「一般練習」與「球型練習」內頁新增 `標註顯示模式：無 / 精簡 / 完整` 切換，進入練習內頁預設套用精簡。
  - 規範用法：
    - 環境變數：`TRACKER_ANNOTATION_MODE=tactical`，重啟後生效；可選值為 `none`、`tactical`、`full`。
    - 即時切換：`POST /api/control/overlay-mode` 傳 `{ "mode": "tactical" }`。
    - 關閉繪圖：`POST /api/control/overlay-mode` 傳 `{ "mode": "none" }`。
    - 還原完整標註：`POST /api/control/overlay-mode` 傳 `{ "mode": "full" }`。
  - 輸出格式：
    ```json
    {
      "status": "success",
      "tracker_annotation_mode": "tactical"
    }
    ```
    ```json
    {
      "tracker_annotation_mode": "tactical",
      "monitor_stream_use_yolo_overlay": true
    }
    ```

- 05/03: 'projector render 移出相機主迴圈'
  - 範例：
    - 原本 projector 有訂閱者時，`camera_capture_loop()` 會同步執行 `projector_renderer.render()` 與 `update_projector()`；若單次投影渲染達 20-40ms，會直接拉高 monitor 延遲與降低 FPS。
    - 新增獨立 `projector_render_worker`，投影串流有訂閱者時由背景 thread 依 `PROJECTOR_RENDER_MAX_FPS` 重畫 projector，主相機迴圈只負責 monitor frame 與 AR data 更新。
    - 06/20：legacy `/ws/video` 不再寫入全域 projector MJPEG channel；它只更新 monitor stream 與自己的 WebSocket frame，避免與 `projector_render_worker` 競爭 `/stream/projector` 輸出。
  - 規範用法：
    - `/api/performance/stats` 中 `projector_render_worker_active=true` 代表投影渲染 worker 已啟動。
    - `projector_render_worker` stage 代表背景投影渲染耗時；它不應再出現在主迴圈 `frame_total` 內。
    - 若 monitor FPS 仍低，優先看 `camera_read`、`mjpeg_monitor_update`、`yolo_result`；不再把 `projector_render_worker` 當作主串流阻塞項。
    - `mjpeg_manager.update_projector()` 僅允許在 `projector_render_loop()` 呼叫；相機 loop、legacy WebSocket 或其他監控輸出流程不得直接寫 projector MJPEG。
  - 輸出格式：
    ```json
    {
      "projector_render_worker_active": true,
      "stage_latency_ms": {
        "projector_render_worker": {
          "avg_ms": 28.0,
          "stale_frames": 0
        },
        "frame_total": {
          "avg_ms": 18.0
        }
      }
    }
    ```

- 05/03: '標註顯示模式 none 強制低延遲 monitor'
  - 範例：
    - 先前 `TRACKER_ANNOTATION_MODE=none` 只是不畫 OpenCV overlay，但 monitor 仍可能使用上一個 YOLO result 的 `cached_overlay`，體感延遲不一定下降。
    - 現在 `none` 會清掉 overlay cache，monitor 改用最新 raw camera frame；YOLO 仍可在背景更新 metadata、練習統計與 AR projector 資料。
  - 規範用法：
    - 練習內頁選 `標註顯示模式：無` 時，`monitor_effective_overlay=false` 才代表 monitor 已走 raw live frame。
    - `精簡` / `完整` 仍是後端畫好 overlay 後再串流，體感延遲會包含 YOLO result 完成時間。
  - 輸出格式：
    ```json
    {
      "tracker_annotation_mode": "none",
      "monitor_stream_use_yolo_overlay": true,
      "monitor_effective_overlay": false
    }
    ```

- 05/03: 'monitor overlay 改為最新相機幀即時合成'
  - 範例：
    - YOLO worker 不再為主 monitor 產生舊的 overlay frame，而是只回傳最新 metadata。
    - 主相機迴圈用最新 camera frame 加上最近一次 YOLO metadata 即時重畫 overlay，再交給 MJPEG 編碼。
    - 這讓影像串流不等待 YOLO 結果；標註可能落後 1 到數幀，但背景影像保持最新。
  - 規範用法：
    - `TRACKER_ANNOTATION_MODE=none`：monitor 直接輸出 raw live frame。
    - `TRACKER_ANNOTATION_MODE=tactical|full`：monitor 使用最新 raw frame + 最新 metadata 合成 overlay。
    - `/api/performance/stats.stage_latency_ms.monitor_overlay_compose` 可用來觀察主迴圈每幀重畫 overlay 的成本。
  - 輸出格式：
    ```json
    {
      "tracker_annotation_mode": "tactical",
      "monitor_effective_overlay": true,
      "stage_latency_ms": {
        "monitor_overlay_compose": {
          "avg_ms": 2.4,
          "stale_frames": 0
        }
      }
    }
    ```

- 05/03: 'metadata 過期時暫停顯示標註與 projector 動態 AR'
  - 範例：
    - 最新相機幀 + 最新 metadata 合成 overlay 會有標註落後問題；現在 metadata 超過門檻時會暫停顯示標註，避免落後線路貼在最新影像上。
    - monitor overlay 以 metadata 對應的原始相機影像時間 `_source_timestamp` 與 `_source_frame_id` 判斷新鮮度，避免用 YOLO 完成時間誤判。
    - projector 也套用同樣策略：`live_yolo` 動態路線、球位、幽靈球、母球落點與球桿雷射線過期時不投影。
    - 球型練習固定投影標記為 `pattern_static`，不受 YOLO metadata 過期影響。
  - 規範用法：
    - `OVERLAY_METADATA_MAX_AGE_MS=350` 控制 monitor 新 metadata 最大可接受年齡；太低會造成 overlay 一直閃，太高會增加錯位感。
    - `MONITOR_OVERLAY_MAX_FRAME_LAG=12` 控制 monitor metadata 最多可落後目前相機幀數。
    - `PROJECTOR_AR_METADATA_MAX_AGE_MS=1200` 控制 projector 新動態 AR 最大可接受年齡。
    - `LAST_GOOD_OVERLAY_HOLD_MS=5000` 控制 monitor 短暫漏檢時最後一筆有效標註保留多久。
    - `LAST_GOOD_PROJECTOR_AR_HOLD_MS=5000` 控制 projector 短暫漏檢時最後一筆有效 AR 保留多久。
    - 若標註閃爍太頻繁，可把門檻調高；若標註仍明顯落後，可把門檻調低。
  - 輸出格式：
    ```json
    {
      "overlay_metadata_max_age_ms": 350,
      "monitor_overlay_max_frame_lag": 12,
      "projector_ar_metadata_max_age_ms": 1200,
      "last_good_overlay_hold_ms": 5000,
      "last_good_projector_ar_hold_ms": 5000,
      "overlay_metadata_age_ms": 85.4,
      "overlay_metadata_frame_lag": 3,
      "overlay_metadata_fresh": true
    }
    ```

- 05/03: '短暫漏檢時保留最後有效標註'
  - 範例：
    - 若新 YOLO metadata 沒有可畫路線，monitor 不會立刻覆蓋掉上一筆有效路線。
    - 若 projector 收到空的動態 AR 結果，也不會立刻清掉上一筆有效投影線。
  - 規範用法：
    - `LAST_GOOD_OVERLAY_HOLD_MS=5000` 表示 monitor 最多保留最後有效標註 5 秒。
    - `LAST_GOOD_PROJECTOR_AR_HOLD_MS=5000` 表示 projector 最多保留最後有效 AR 5 秒。
    - 若線太黏、明顯不跟手，降低這兩個值；若還會消失，提高這兩個值。

- 05/03: 'monitor overlay 改為輸出尺寸繪製'
  - 範例：
    - 原本先在相機原始 frame 上畫 overlay，再 resize 成 1280x720，繪圖面積較大。
    - 現在先把影像縮到 monitor 輸出尺寸，再把 metadata 座標同步縮放後繪製，降低每幀 `monitor_overlay_compose` 成本。
  - 規範用法：
    - 觀察 `/api/performance/stats.stage_latency_ms.monitor_overlay_compose.avg_ms` 是否下降。
    - 若精簡模式仍慢，優先維持 `TRACKER_ANNOTATION_MODE=tactical`，避免完整標註的文字與所有球標籤成本。
