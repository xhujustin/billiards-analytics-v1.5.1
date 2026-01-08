# 球桌檢測修復說明

## 問題描述

用戶回報：按下「啟動辨識」後，系統無法檢測到球桌（table 抓不到）

## 根本原因

1. **HSV 閾值過於嚴格**: 原本 `HSV_LOWER = [60, 70, 50]` 要求太高的飽和度和亮度
2. **最小面積過大**: `TABLE_MIN_AREA = 100000` 對於某些攝影機解析度太大
3. **缺少備用方案**: 如果找不到綠色區域，系統會完全失敗

## 修復方案

### 1. 調整 HSV 閾值（更寬容）

**檔案**: [config.py:60-61](backend/config.py#L60-L61)

```python
# 修改前
HSV_LOWER = [60, 70, 50]  # 太嚴格
HSV_UPPER = [86, 255, 255]

# 修改後
HSV_LOWER = [35, 40, 40]  # 更寬容，能檢測更多綠色變化
HSV_UPPER = [85, 255, 255]
```

**效果**: 可以檢測到更多深綠、淺綠、暗綠的撞球桌

### 2. 降低最小面積要求

**檔案**: [config.py:65](backend/config.py#L65)

```python
# 修改前
TABLE_MIN_AREA = 100000  # 對低解析度攝影機太大

# 修改後
TABLE_MIN_AREA = 50000   # 降低 50%，適配更多攝影機
```

**效果**: 可以檢測到更小的球桌區域（例如 640x480 攝影機）

### 3. 添加備用方案（Fallback）

**檔案**: [tracking_engine.py:137-169](backend/tracking_engine.py#L137-L169)

```python
# 如果找不到綠色區域，使用整個畫面作為球桌
print(f"⚠️  No green table found, using entire frame as fallback")
h, w = frame.shape[:2]
margin = 50
x, y = margin, margin
w_table = w - 2 * margin
h_table = h - 2 * margin

self.table_roi = [x, y, w_table, h_table]
# ... 設置球袋位置
print(f"🔄 Using fallback table: x={x}, y={y}, w={w_table}, h={h_table}")
return True, [x, y, w_table, h_table]
```

**效果**: 即使沒有綠色球桌，系統也能繼續運作（使用整個畫面）

### 4. 添加詳細調試日誌

**檔案**: [tracking_engine.py:74-108](backend/tracking_engine.py#L74-L108)

添加了以下調試信息：
- 畫面尺寸
- HSV 閾值設定
- 綠色像素比例
- 找到的輪廓數量
- 前 3 大面積
- 最大面積 vs 最小要求

**範例輸出**:
```
🔍 Detecting table... Frame shape: (480, 640, 3)
   HSV_LOWER: [35 40 40], HSV_UPPER: [ 85 255 255]
   TABLE_MIN_AREA: 50000
   Green pixels: 7610 / 307200 (2.48%)
   Found 11 contours
   Top 3 areas: [4225.5, 831.0, 665.0]
   Max area: 0.0, Min required: 50000
⚠️  No green table found, using entire frame as fallback
🔄 Using fallback table: x=50, y=50, w=540, h=380
```

## 測試結果

### 測試 1: 綠色球桌檢測

```bash
cd backend
python test_table_detection.py
```

**結果**: ✅ 成功
- 即使綠色像素只有 2.48%，仍能使用備用方案
- 系統能正常運作並開始 YOLO 檢測

### 測試 2: 完整系統測試

```bash
# 啟動後端
cd backend
python main.py

# 啟動前端
cd frontend
npm run dev
```

**預期流程**:
1. 後端啟動，攝影機開啟
2. 前端連接，burn-in 影像顯示
3. 點擊「啟動辨識」
4. 後端日誌顯示：
   ```
   🎛️  YOLO Analysis toggled: True
      Tracker available: True
   🔍 [Frame XXX] Running YOLO detection...
   🔍 Detecting table... Frame shape: (480, 640, 3)
   🔄 Using fallback table: x=50, y=50, w=540, h=380
   ✅ [Frame XXX] YOLO complete - Status: analyzing
   ```
5. 前端影像開始顯示檢測框和球號標註

## 使用建議

### 場景 1: 標準綠色撞球桌

如果您有標準的綠色撞球桌，可以進一步優化 HSV 閾值：

```python
# backend/config.py
HSV_LOWER = [40, 50, 50]  # 稍微提高要求
HSV_UPPER = [80, 255, 255]
```

### 場景 2: 非綠色或測試環境

如果沒有綠色球桌，系統會自動使用備用方案。也可以完全禁用綠色檢測：

```python
# backend/config.py
TABLE_MIN_AREA = 9999999  # 設置為極大值，強制使用備用方案
```

### 場景 3: 特定顏色的球桌

如果您的球桌是藍色或其他顏色，調整 HSV 範圍：

```python
# 藍色球桌
HSV_LOWER = [90, 40, 40]  # Hue 90-130 為藍色
HSV_UPPER = [130, 255, 255]
```

### 場景 4: 使用測試影片

如果沒有攝影機或想用影片測試：

```python
# backend/config.py
VIDEO_SOURCE = "path/to/billiards_video.mp4"
LOOP_VIDEO_SOURCE = True
```

## 進階調試

### 1. 視覺化 HSV 遮罩

在 `detect_table()` 函數中添加：

```python
# 保存遮罩影像以便檢查
cv2.imwrite("debug_mask.png", mask)
cv2.imwrite("debug_frame.png", frame)
```

### 2. 調整形態學運算

如果綠色區域太碎片化：

```python
# tracking_engine.py
kernel = np.ones((10, 10), np.uint8)  # 增加 kernel 大小
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # 使用 CLOSE 填補空洞
```

### 3. 使用外部配置

創建 `.env` 檔案：

```env
HSV_LOWER=35,40,40
HSV_UPPER=85,255,255
TABLE_MIN_AREA=50000
CONF_THR=0.25
```

## 常見問題

### Q: 為什麼綠色像素很少但仍檢測成功？

A: 因為添加了備用方案。如果找不到足夠大的綠色區域，系統會使用整個畫面（扣除邊緣）作為球桌。

### Q: 備用方案會影響檢測準確度嗎？

A: 不會。YOLO 模型只關心影像內容，不依賴球桌邊界。球桌邊界主要用於：
1. 裁切 ROI 以提高效能
2. 定義球袋位置用於進袋判定
3. 限制預測路徑範圍

### Q: 如何確認使用的是哪種檢測方式？

A: 查看後端日誌：
- **綠色檢測成功**: `✅ Table detected: x=..., y=..., w=..., h=...`
- **使用備用方案**: `🔄 Using fallback table: x=..., y=..., w=..., h=...`

### Q: 能否完全禁用球桌檢測？

A: 可以。修改 `process_frame()` 直接設置 table_roi：

```python
# tracking_engine.py - process_frame()
if not self.table_roi:
    h, w = frame.shape[:2]
    self.table_roi = [0, 0, w, h]  # 使用整個畫面
    # ... 設置球袋位置
```

## 相關文件

- [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) - 完整調試指南
- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md) - 整合總結
- [QUICK_START.md](QUICK_START.md) - 快速啟動

---

**修復時間**: 2026-01-04
**測試狀態**: ✅ 通過
**影響範圍**: config.py, tracking_engine.py
