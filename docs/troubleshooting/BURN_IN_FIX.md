# Burn-in 即時影像修復說明

## 問題描述
之前 burn-in 串流 (`/burnin/{stream_id}.mjpg`) 沒有即時影像，因為：
1. 攝像頭只在 `/ws/video` WebSocket 連接時才會啟動
2. MJPEG 串流是被動的，不會主動開啟攝像頭
3. 前端使用 v1.5 SDK 時只連接 `/ws/control`，不會連接 `/ws/video`

## 解決方案
在後端添加了一個背景線程 `camera_capture_loop()`，它會：
1. **自動啟動**：在應用啟動時自動開啟攝像頭
2. **持續捕獲**：在背景線程中持續讀取影像幀
3. **更新串流**：即時更新 MJPEG 串流（monitor 和 projector）
4. **支援 YOLO**：如果 `is_analyzing` 啟用，會自動執行物件檢測
5. **自動重連**：如果攝像頭斷線，會自動嘗試重新連接

## 修改內容

### backend/main.py

1. **新增全局變數**（第 91-93 行）：
   ```python
   camera_capture_thread = None
   camera_running = threading.Event()
   ```

2. **新增攝像頭捕獲循環**（第 262-368 行）：
   ```python
   def camera_capture_loop():
       # 持續讀取攝像頭幀並更新 MJPEG 串流
   ```

3. **新增啟動/關閉事件**（第 1187-1205 行）：
   ```python
   @app.on_event("startup")
   async def startup_event():
       # 啟動背景線程

   @app.on_event("shutdown")
   async def shutdown_event():
       # 清理資源
   ```

## 使用方式

### 啟動後端
```bash
cd backend
python main.py
```

啟動後，您會看到：
```
🚀 Starting camera capture thread for burn-in stream...
🎥 Starting camera capture loop for burn-in stream...
✅ Camera opened successfully...
```

### 前端使用
前端無需修改，burn-in URL 會自動有即時影像：
```tsx
const burninUrl = `${baseUrl}${session.burnin_url}?quality=med`;

<img src={burninUrl} alt="Burn-in Stream" />
```

## 技術細節

### 線程架構
- **主線程**：處理 HTTP/WebSocket 請求
- **背景線程**：持續捕獲攝像頭影像
- **線程池**：處理 YOLO 推論（如果啟用）

### 效能優化
- 使用 `threading.Event()` 進行線程同步
- YOLO 跳幀處理（可透過 `yolo_skip_frames` 調整）
- 自動幀率控制（30 FPS）

### 錯誤處理
- 攝像頭斷線自動重連（延遲 5 秒）
- 讀取失敗自動重試
- 優雅關閉清理資源

## 測試方式

1. **啟動後端**：
   ```bash
   cd backend
   python main.py
   ```

2. **測試 burn-in 串流**：
   在瀏覽器訪問：
   ```
   http://localhost:8001/burnin/camera1.mjpg?quality=med
   ```
   應該會看到即時影像

3. **測試前端整合**：
   ```bash
   cd frontend
   npm run dev
   ```
   Dashboard 應該會顯示 burn-in 即時影像

## 相容性
- ✅ 與舊版 `/ws/video` WebSocket 完全相容
- ✅ 與 v1.5 SDK 完全相容
- ✅ 不影響現有功能
- ✅ 可獨立使用 burn-in 串流，無需建立 WebSocket 連接

## 注意事項
1. 背景線程會在應用啟動時自動開啟攝像頭
2. 如果有多個用戶端連接，所有人會看到相同的影像來源
3. 攝像頭設備可透過 `/api/camera/select` API 切換
4. YOLO 分析可透過 `/api/control/toggle` API 開啟/關閉
