# 調試指南 - 啟動辨識無反應問題

## 問題描述

按下「啟動辨識」按鈕後，即時影像沒有顯示檢測框和球號標註。

## 診斷步驟

### 步驟 1: 啟動後端並觀察日誌

```bash
cd backend
python main.py
```

**預期輸出**:
```
✅ YOLO model loaded successfully from ...
✅ Calibrator initialized successfully
✅ MJPEG Stream Manager initialized
🚀 Starting camera capture thread for burn-in stream...
🎥 Starting camera capture loop for burn-in stream...
✅ Camera opened successfully...
```

### 步驟 2: 檢查攝影機是否正常

觀察後端日誌，確認沒有以下錯誤：
- ❌ Failed to open camera
- ⚠️ Failed to read frame

如果有攝影機錯誤，檢查：
1. 攝影機是否被其他程式佔用
2. backend/config.py 中的攝影機設定
3. 嘗試切換攝影機設備 ID (0, 1, 2...)

### 步驟 3: 啟動前端

```bash
cd frontend
npm run dev
```

訪問 `http://localhost:5173`

### 步驟 4: 檢查 WebSocket 連接

在前端頁面中，確認：
- WebSocket 狀態顯示「🟢 已連接」
- Burn-in 影像正常顯示

### 步驟 5: 點擊「啟動辨識」並觀察後端日誌

**預期輸出**:
```
🎛️  YOLO Analysis toggled: True
   Tracker available: True
🔍 [Frame XXX] Running YOLO detection...
✅ [Frame XXX] YOLO complete - Status: analyzing
```

如果看不到這些日誌，說明：
1. API 請求沒有到達後端
2. 前端和後端沒有正確連接

### 步驟 6: 檢查球桌檢測

如果看到：
```
⚠️  Table not detected, scanning...
```

說明系統無法檢測到球桌（綠色區域）。解決方案：
1. 確認攝影機畫面中有綠色撞球桌
2. 調整 `backend/config.py` 中的 HSV 閾值：
   ```python
   HSV_LOWER = [35, 40, 40]   # 降低飽和度和亮度
   HSV_UPPER = [85, 255, 255]
   ```
3. 確認 `TABLE_MIN_AREA` 設定合適

如果看到：
```
✅ Table detected: x=..., y=..., w=..., h=...
```

說明球桌檢測成功！

### 步驟 7: 檢查 YOLO 檢測結果

觀察後端日誌中的：
```
✅ [Frame XXX] YOLO complete - Status: analyzing
```

然後在前端的 Metadata 頁面檢查：
- 檢測數量是否 > 0
- detections 陣列是否有資料

## 常見問題

### 問題 1: 沒有看到 YOLO 檢測日誌

**可能原因**:
- `system_state["is_analyzing"]` 沒有正確切換
- `tracker` 為 None

**檢查方法**:
使用瀏覽器開發者工具檢查 API 請求：
1. 打開 F12 → Network
2. 點擊「啟動辨識」
3. 檢查 `/api/control/toggle` 請求
4. 確認 Response: `{"status": "success", "is_analyzing": true}`

### 問題 2: 球桌一直檢測不到

**可能原因**:
- 攝影機畫面中沒有綠色區域
- HSV 閾值設定不正確

**解決方案**:
1. 使用測試影片代替攝影機：
   ```python
   # backend/config.py
   VIDEO_SOURCE = "path/to/test_video.mp4"
   ```

2. 調整 HSV 閾值（降低標準）：
   ```python
   HSV_LOWER = [30, 30, 30]  # 更寬容
   HSV_UPPER = [90, 255, 255]
   ```

### 問題 3: 球桌檢測成功，但沒有球

**可能原因**:
- YOLO 模型信心度閾值太高
- 畫面中確實沒有球

**解決方案**:
1. 降低信心度閾值：
   ```python
   # backend/config.py
   CONF_THR = 0.25  # 從 0.35 降低到 0.25
   ```

2. 確認 YOLO 模型正確載入：
   ```
   ✅ YOLO model loaded successfully from ...
   ```

### 問題 4: 有球檢測，但沒有標註

**可能原因**:
- `_draw_annotations()` 函數沒有執行
- MJPEG 串流沒有更新

**檢查**:
在 tracking_engine.py 的 `_draw_annotations()` 開頭添加：
```python
def _draw_annotations(self, img: np.ndarray, data: Dict[str, Any]):
    print(f"🎨 Drawing annotations - Balls: {len(data.get('balls', []))}")
    ...
```

## 調試輔助工具

### 1. 測試 tracking_engine.py

```bash
cd backend
python test_tracking.py
```

這會測試：
- PoolTracker 初始化
- 球桌檢測
- YOLO 推論
- HSV 顏色檢測

### 2. 直接測試 API

```bash
# 測試 toggle API
curl -X POST http://localhost:8001/api/control/toggle

# 檢查 health
curl http://localhost:8001/health
```

### 3. 檢查 MJPEG 串流

在瀏覽器直接訪問：
```
http://localhost:8001/burnin/camera1.mjpg
```

應該能看到即時影像。

## 預期行為總結

| 步驟 | 操作 | 預期結果 |
|------|------|----------|
| 1 | 啟動後端 | 攝影機成功開啟，MJPEG 串流啟動 |
| 2 | 訪問前端 | Burn-in 影像顯示原始攝影機畫面 |
| 3 | 點擊「啟動辨識」 | 後端日誌顯示 "YOLO Analysis toggled: True" |
| 4 | 第一次檢測 | 後端檢測球桌並輸出 "Table detected" |
| 5 | 持續檢測 | 每幀輸出 "Running YOLO detection..." |
| 6 | 前端顯示 | 影像切換為標註後的畫面（球號、顏色、路徑） |
| 7 | Metadata 頁面 | 顯示 detections 陣列和球的詳細資訊 |

## 常見警告訊息（可忽略）

### POST /api/sessions/.../renew 404 (Not Found)

**現象**:
```
POST http://localhost:8001/api/sessions/s-c1e099b08a12/renew 404 (Not Found)
```

**原因**:
- 前端 SDK 嘗試續期一個已過期或不存在的 session
- Session 預設有效期為 3600 秒（1小時）
- 頁面長時間開啟或重新整理後，舊 session 已被清除

**影響**:
- ✅ **無影響** - 前端會自動創建新 session
- 系統會繼續正常運作

**解決方案**:
1. **不需要處理** - 這是正常行為
2. 如果想減少這類訊息，可以延長 session 有效期：
   ```python
   # backend/config.py
   SESSION_TTL = 7200  # 改為 2 小時
   ```

### 多次切換畫質導致黑屏

**現象**:
- 快速切換「低」、「中」、「高」畫質
- 特別是第 6 次切換時畫面黑屏

**原因**:
- 每次切換會創建新的 MJPEG HTTP 連接
- 瀏覽器對每個域名有並發連接數限制（通常是 6 個）
- 舊連接未正確關閉，累積到第 6 個時達到上限
- 新連接無法建立，導致黑屏

**已修復**: ✅
- 在切換畫質前強制中斷當前 HTTP 連接（設置 `img.src = ''`）
- 添加 100ms 延遲確保舊連接完全關閉
- 實現防抖動機制，防止狀態衝突
- 5 秒超時自動恢復
- 顯示載入提示和視覺反饋

**技術細節**:
```typescript
// 關鍵修復：強制中斷當前連接
if (imgRef) {
  imgRef.src = ''; // 立即中斷 HTTP 連接
}

// 延遲載入新串流，確保舊連接已關閉
setTimeout(() => {
  setStreamKey(prev => prev + 1);
}, 100);
```

**使用建議**:
- 現在可以隨意切換畫質，不會再有黑屏問題
- 每次切換約需 0.5-1 秒載入時間（屬於正常）

## 如果問題仍然存在

請提供以下資訊：

1. **後端啟動日誌**（前 20 行）
2. **點擊「啟動辨識」後的日誌**（完整輸出）
3. **前端 Console 錯誤**（F12 → Console）
4. **Network 請求狀態**（F12 → Network → /api/control/toggle）
5. **攝影機畫面描述**（是否有綠色球桌？是否有球？）

---

**最後更新**: 2026-01-05
**相關文件**:
- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md)
- [QUICK_START.md](QUICK_START.md)
- [YOLO_CONTROL_UI.md](YOLO_CONTROL_UI.md)
- [TABLE_DETECTION_FIX.md](TABLE_DETECTION_FIX.md) - 球桌檢測修復
- [QUALITY_CONTROL_FIX.md](QUALITY_CONTROL_FIX.md) - 畫質控制修復
- [BLACK_SCREEN_FIX.md](BLACK_SCREEN_FIX.md) - 黑屏問題修復（瀏覽器連接數限制）
- [HOW_TO_ADJUST_QUALITY.md](HOW_TO_ADJUST_QUALITY.md) - 畫質調整使用說明
