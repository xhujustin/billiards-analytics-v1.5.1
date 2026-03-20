# 相機參數設定功能 - 技術文檔更新

## 更新日期
01/30: 新增相機參數設定功能

## 功能概述
實作完整的相機參數控制系統,包含硬體參數調整、軟體降噪、影像增強等功能。

## 新增 API 端點

### 1. GET /api/camera/params
獲取當前相機參數

**回應範例**:
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

### 2. POST /api/camera/params
更新相機參數

**請求範例**:
```json
{
  "exposure": -5,
  "denoise_enabled": true,
  "denoise_strength": 30,
  "denoise_method": "bilateral"
}
```

**回應範例**:
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

### 3. POST /api/camera/auto-adjust
自動調整相機參數

**回應範例**:
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

### 4. GET /api/camera/format
獲取當前相機格式資訊

**回應範例**:
```json
{
  "format": "YUYV",
  "description": "未壓縮格式",
  "is_compressed": false,
  "warning": null,
  "recommendation": "當前使用最佳格式"
}
```

### 5. GET /api/camera/stats
獲取影像處理統計資訊

**回應範例**:
```json
{
  "denoise_enabled": true,
  "denoise_method": "fastNlMeans",
  "denoise_strength": 30,
  "brightness_adjust": 0,
  "contrast_adjust": 1.0,
  "processing_time_ms": 12.5,
  "frame_count": 1523,
  "avg_processing_time_ms": 12.5
}
```

## 配置參數

新增以下環境變數支援 (backend/config.py):

```python
# 相機進階參數
CAMERA_EXPOSURE = -6          # 曝光時間 (-13 to -1)
CAMERA_ISO = 0                # ISO 感光度 (0=auto, 100-3200)
CAMERA_BRIGHTNESS = 128       # 亮度 (0-255)
CAMERA_CONTRAST = 128         # 對比度 (0-255)
CAMERA_SATURATION = 128       # 飽和度 (0-255)
CAMERA_SHARPNESS = 128        # 銳利度 (0-255)
CAMERA_AUTO_WB = true         # 自動白平衡
CAMERA_WB_TEMP = 4000         # 白平衡色溫 (2800-6500K)

# 軟體降噪參數
DENOISE_ENABLED = false       # 是否啟用降噪
DENOISE_STRENGTH = 10         # 降噪強度 (0-100)
DENOISE_METHOD = "fastNlMeans"  # 降噪演算法
```

## 降噪演算法說明

### 1. fastNlMeans (快速非局部平均)
- **優點**: 降噪效果好,保留細節
- **缺點**: 處理速度較慢
- **適用**: 1080p@30fps 以下,需要高品質影像

### 2. bilateral (雙邊濾波)
- **優點**: 保留邊緣,速度適中
- **缺點**: 強度過高會產生卡通效果
- **適用**: 一般場景,平衡品質與速度

### 3. gaussian (高斯模糊)
- **優點**: 速度最快
- **缺點**: 會模糊邊緣
- **適用**: 高解析度或高幀率,對速度要求高

## FOURCC 格式冗餘機制

系統會自動嘗試以下格式,優先使用未壓縮格式:

1. **YUYV** (未壓縮) - 最佳品質
2. **MJPEG** (硬體壓縮) - 降級選項
3. **YUY2** (YUV格式) - 備用選項
4. **DEFAULT** (系統預設) - 最後選項

格式資訊會儲存在 `camera_state["fourcc_info"]` 供 API 查詢。

## 統一影像處理管線 (方案 A)

在 `camera_capture_loop()` 中,所有影像處理在捕獲後立即執行:

```python
# 讀取幀
ret, frame = cap.read()

# 統一影像處理管線
if image_processor:
    frame = image_processor.process_frame(frame)

# YOLO 和前端串流都使用處理後的影像
yolo_future = executor.submit(tracker.process_frame, frame.copy())
mjpeg_manager.update_monitor(frame)
```

**優點**:
- YOLO 和前端看到完全相同的影像
- 降噪後的影像提升 YOLO 辨識準確度
- 統一處理管線,易於維護
- 參數調整立即影響所有輸出

## 前端 UI 元件

新增 `CameraParamsSettings.tsx` 元件,整合到 `SettingsPage.tsx`:

**功能**:
- 軟體降噪控制 (啟用/強度/演算法)
- 曝光設定 (曝光時間/ISO)
- 影像調整 (亮度/對比度/飽和度)
- 白平衡控制 (自動/手動色溫)
- 自動調整按鈕
- 格式警告顯示

## 使用範例

### 啟用降噪
```bash
curl -X POST http://localhost:8001/api/camera/params \
  -H "Content-Type: application/json" \
  -d '{"denoise_enabled": true, "denoise_strength": 30, "denoise_method": "bilateral"}'
```

### 調整曝光
```bash
curl -X POST http://localhost:8001/api/camera/params \
  -H "Content-Type: application/json" \
  -d '{"exposure": -5, "iso": 400}'
```

### 自動調整
```bash
curl -X POST http://localhost:8001/api/camera/auto-adjust
```

### 查詢格式
```bash
curl http://localhost:8001/api/camera/format
```

## 效能考量

- **降噪處理時間**: 10-15ms (1080p, bilateral)
- **建議**: 1080p@30fps 以下使用 bilateral 或 gaussian
- **監控**: 使用 `/api/camera/stats` 查看處理時間
- **調整**: 若 FPS 下降,降低降噪強度或切換到更快的演算法

## 注意事項

1. **硬體支援**: 部分相機可能不支援所有參數,API 會返回警告
2. **格式壓縮**: 若使用 MJPEG 格式,會有二次壓縮問題,建議啟用降噪
3. **效能影響**: 降噪會增加 CPU 負載,需監控 FPS
4. **參數範圍**: 確保參數在有效範圍內,否則可能無效

## 檔案清單

**後端**:
- `backend/config.py` - 新增配置參數
- `backend/core/image_processor.py` - 影像處理模組
- `backend/api/camera_api.py` - 新增 API 端點
- `backend/main.py` - 整合影像處理管線和 FOURCC 機制
- `backend/data/camera_params_history.json` - 參數歷史記錄

**前端**:
- `frontend/src/components/settings/CameraParamsSettings.tsx` - 參數設定元件
- `frontend/src/components/settings/CameraParamsSettings.css` - 樣式
- `frontend/src/components/pages/SettingsPage.tsx` - 整合元件
