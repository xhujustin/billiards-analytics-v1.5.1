# 投影機自動校正使用指南

## 功能概述

投影機自動校正功能使用 ArUco 標記進行相機-投影機座標映射,簡化校正流程,快速完成投影範圍設定。

**核心特性**:
- ✅ 自動顯示 4 個 ArUco 標記 (ID: 0-3)
- ✅ API 控制標記位置
- ✅ 相機自動檢測 ArUco 標記
- ✅ 一鍵確認完成校正

---

## 使用流程

### 步驟 1: 準備工作

1. **連接投影機**: 確保投影機已連接並對準撞球桌
2. **啟動系統**: 
   ```bash
   cd backend
   python main.py
   ```
3. **開啟前端**: 瀏覽器訪問 `http://localhost:5173`

### 步驟 2: 進入校正頁面

1. 點擊左側導航「設定」
2. 點擊「投影機校正」按鈕
3. 系統自動開啟校正介面

### 步驟 3: 調整 ArUco 標記位置

**投影機畫面**:
- 自動顯示 4 個 ArUco 標記
- 標記位置: 左上(TL)、右上(TR)、右下(BR)、左下(BL)

**API 控制**:
```bash
# 移動左上角標記
curl -X POST http://localhost:8001/api/calibration/move-corner \
  -H "Content-Type: application/json" \
  -d '{"corner": "top-left", "offset": {"x": -400, "y": -400}}'
```

**目標**: 將 4 個標記移動到撞球桌四個角落

### 步驟 4: 自動檢測

**系統行為**:
- 相機持續拍攝畫面
- ArUco 檢測器自動識別標記
- 檢測成功後顯示:
  - 標記 ID 和位置
  - 四個角點座標

**檢測狀態**:
- ✓ 已檢測到 4 個標記 → 可以確認
- ✗ 未檢測到 → 調整投影位置或光線

### 步驟 5: 確認校正

1. 確認相機已檢測到 4 個 ArUco 標記
2. 呼叫確認 API 完成校正
3. 系統計算 Homography 矩陣並儲存

**完成提示**:
```
✅ 校正完成!
相機-投影機座標映射已建立
Homography 矩陣已儲存至 calibration_matrix.npy
```

---

## 界面說明

### 投影機畫面

```
┌─────────────────────────┐
│                         │
│  ┌─┐            ┌─┐    │
│  │0│ TL      TR │1│    │
│  └─┘            └─┘    │
│                         │
│  ┌─┐            ┌─┐    │
│  │3│ BL      BR │2│    │
│  └─┘            └─┘    │
└─────────────────────────┘
```

### 相機預覽畫面

```
┌─────────────────────────┐
│  相機即時畫面           │
│  ┌─┐            ┌─┐    │
│  │0│ (檢測到)   │1│    │
│  └─┘            └─┘    │
│                         │
│  ┌─┐            ┌─┐    │
│  │3│            │2│    │
│  └─┘            └─┘    │
└─────────────────────────┘
```

### 控制面板

```
┌─────────────────────────────────┐
│ 投影機自動校正                  │
├─────────────────────────────────┤
│ 步驟 1: 調整位置                │
│   [↑] [↓] [←] [→]  步長: 20px   │
│                                 │
│ 步驟 2: 檢測狀態                │
│   ✓ 已檢測到棋盤格              │
│   座標: [(100,200), ...]        │
│                                 │
│ [重新檢測]  [確認校正]          │
└─────────────────────────────────┘
```

---

## 常見問題

### Q1: 檢測不到 ArUco 標記?

**原因**:
- 投影位置超出相機視野
- 光線條件不佳
- 標記變形或模糊

**解決方法**:
1. 調整投影機位置,確保標記在相機視野內
2. 改善環境光線
3. 使用 API 調整標記位置

### Q2: 檢測結果不準確?

**原因**:
- 標記邊緣模糊
- 投影機梯形變形嚴重
- 相機角度過於傾斜

**解決方法**:
1. 調整投影機焦距
2. 先進行梯形校正 (如果投影機支援)
3. 確保相機和投影機固定不動

### Q3: 校正後投影位置偏移?

**原因**:
- 相機或投影機移動
- 校準矩陣計算誤差

**解決方法**:
1. 重新執行校正流程
2. 確保相機和投影機固定不動
3. 檢查 `calibration_matrix.npy` 是否正確儲存

---

## 技術原理

### ArUco 標記檢測 (OpenCV 4.8.1+)

使用 OpenCV 的 ArUco 模組：

```python
# 初始化 ArUco 字典和檢測參數
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()

# 優化檢測參數
aruco_params.minMarkerPerimeterRate = 0.005  # 降低最小標記周長閾值
aruco_params.polygonalApproxAccuracyRate = 0.08  # 提高容錯性
aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 23
aruco_params.adaptiveThreshWinSizeStep = 10

# 建立檢測器 (OpenCV 4.7+ 新版 API)
detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

# 檢測標記
corners, ids, rejected = detector.detectMarkers(gray_image)
```

> 注意：OpenCV 4.7.0+ 版本已棄用 `cv2.aruco.detectMarkers()` 函數，改用 `ArucoDetector` 類別。

### 投影優化

**白色邊框設計**：
- 每個 ArUco 標記外圍添加白色背景邊框
- 大幅提升標記與黑色桌面的對比度
- 確保在各種光線條件下都能穩定檢測

```python
# 標記尺寸設定 (backend/projector_renderer.py)
marker_size = 280  # ArUco 標記大小
border_width = 40  # 白色邊框寬度
total_size = marker_size + border_width * 2  # 總尺寸 360px

# 繪製白色背景
cv2.rectangle(frame, (x, y), (x + total_size, y + total_size), 
              (255, 255, 255), -1)
# 放置 ArUco 標記在白色背景中心
```

### 座標轉換

```python
# 相機座標 → 投影機座標
# 使用 4 個 ArUco 標記的中心點作為對應點
homography_matrix, status = cv2.findHomography(
    camera_corners,  # 相機中檢測到的 4 個標記中心
    projector_corners  # 投影機中 4 個標記的位置
)

# 應用轉換
transformed = cv2.perspectiveTransform(points, homography_matrix)
```

---

## 進階設定

### 調整標記大小

修改 `backend/projector_renderer.py`:

```python
# 更改標記大小 (目前預設 280px，含 40px 白色邊框)
marker_size = 300  # 較大的標記
marker_size = 200  # 較小的標記
border_width = 30  # 調整邊框寬度
```

### 調整標記位置

使用 API 調整:

```bash
# 調整左上角標記偏移
curl -X POST http://localhost:8001/api/calibration/move-corner \
  -H "Content-Type: application/json" \
  -d '{"corner": "top-left", "offset": {"x": -500, "y": -500}}'
```

---

## 故障排除

### 檢查校準檔案

```bash
# 檢查校準矩陣
ls -la backend/calibration_matrix.npy

# 檢查投影範圍
cat backend/projection_bounds.json
```

### 重置校正

```bash
# 刪除校準檔案
rm backend/calibration_matrix.npy
rm backend/projection_bounds.json

# 重新執行校正
```

### 查看日誌

```bash
# 後端日誌
python backend/main.py

# 檢查輸出:
# ✅ Checkerboard detected: 4 corners
# ✅ Calibration matrix saved
```

---

## 相關文檔

- [API 參考文檔](../api/CALIBRATION_API.md)
- [工程化規劃](../../.gemini/antigravity/brain/.../implementation_plan.md)
- [投影機疊加技術](PROJECTOR_OVERLAY.md)

---

## 更新記錄

**01/23**: 更新投影機自動校正使用指南,改用 ArUco 標記進行校正,包含完整操作流程、界面說明、常見問題和技術原理。

**01/24**: 更新 ArUco 檢測實現為 OpenCV 4.8.1 新版 API，新增白色邊框優化以提高檢測成功率，更新檢測參數設定。
