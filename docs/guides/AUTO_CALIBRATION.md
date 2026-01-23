# 投影機自動校正使用指南

## 功能概述

投影機自動校正功能使用 OpenCV 自動識別棋盤格,簡化校正流程,一次完成相機-投影機座標映射和投影範圍設定。

**核心特性**:
- ✅ 自動識別 4×4 棋盤格
- ✅ 方向鍵控制棋盤格位置
- ✅ 即時預覽綠色框線 + 白色填充
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

### 步驟 3: 調整棋盤格位置

**投影機畫面**:
- 自動顯示 4×4 黑白棋盤格
- 棋盤格初始位置在畫面中央

**前端控制**:
```
使用方向鍵移動棋盤格:
  ↑ : 向上移動
  ↓ : 向下移動
  ← : 向左移動
  → : 向右移動
```

**目標**: 將棋盤格移動到撞球桌範圍內

### 步驟 4: 自動檢測

**系統行為**:
- 相機持續拍攝畫面
- OpenCV 自動檢測棋盤格
- 檢測成功後顯示:
  - 綠色框線 (棋盤格外框)
  - 白色半透明填充
  - 四個角點標記

**檢測狀態**:
- ✓ 已檢測到棋盤格 → 可以確認
- ✗ 未檢測到 → 調整投影位置

### 步驟 5: 確認校正

1. 檢查預覽畫面中的綠色框線是否對齊球桌
2. 點擊「確認校正」按鈕
3. 系統計算校準矩陣並儲存

**完成提示**:
```
✅ 校正完成!
相機-投影機座標映射已建立
投影範圍: 800×800 (居中)
```

---

## 界面說明

### 投影機畫面

```
┌─────────────────────────┐
│                         │
│    ■ □ ■ □             │
│    □ ■ □ ■             │
│    ■ □ ■ □             │
│    □ ■ □ ■             │
│                         │
│  ● 綠色角點標記         │
└─────────────────────────┘
```

### 相機預覽畫面

```
┌─────────────────────────┐
│  相機即時畫面           │
│  ┌───────────────┐      │
│  │ ●──────────● │      │
│  │ │ 白色填充 │ │      │
│  │ │          │ │      │
│  │ ●──────────● │      │
│  └───────────────┘      │
│  綠色框線 = 投影範圍    │
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

### Q1: 檢測不到棋盤格?

**原因**:
- 投影位置超出相機視野
- 光線條件不佳
- 棋盤格變形過大

**解決方法**:
1. 調整投影機位置,確保棋盤格在相機視野內
2. 改善環境光線
3. 使用方向鍵微調棋盤格位置

### Q2: 檢測結果不準確?

**原因**:
- 棋盤格邊緣模糊
- 投影機梯形變形嚴重

**解決方法**:
1. 調整投影機焦距
2. 先進行梯形校正 (如果投影機支援)
3. 增加環境光線對比度

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

### 棋盤格檢測

使用 OpenCV 的 `findChessboardCorners()` 函式:

```python
# 檢測 3×3 內角點 (4×4 棋盤格)
ret, corners = cv2.findChessboardCorners(
    gray_image, 
    (3, 3),
    cv2.CALIB_CB_ADAPTIVE_THRESH
)

# 亞像素精度優化
corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
```

### 座標轉換

```python
# 相機座標 → 投影機座標
homography_matrix = cv2.findHomography(camera_corners, projector_corners)

# 應用轉換
transformed = cv2.perspectiveTransform(points, homography_matrix)
```

---

## 進階設定

### 調整檢測參數

修改 `backend/checkerboard_detector.py`:

```python
# 更改棋盤格尺寸
detector = CheckerboardDetector(pattern_size=(3, 3))  # 預設

# 更改檢測標誌
cv2.findChessboardCorners(
    gray,
    pattern_size,
    cv2.CALIB_CB_ADAPTIVE_THRESH +  # 自適應閾值
    cv2.CALIB_CB_NORMALIZE_IMAGE +  # 正規化
    cv2.CALIB_CB_FAST_CHECK         # 快速檢查
)
```

### 調整移動步長

前端控制:

```typescript
// 預設步長 20px
const step = 20;

// 精細調整 (10px)
const step = 10;

// 快速移動 (50px)
const step = 50;
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

**01/23**: 建立投影機自動校正使用指南,包含完整操作流程、界面說明、常見問題和技術原理。
