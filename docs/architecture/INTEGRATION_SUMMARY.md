# poolShotPredictor.py 整合總結

## 📋 整合概述

本次整合將 `poolShotPredictor.py` 的完整物理模擬邏輯整合到 `tracking_engine.py` 中，實現了以下功能：

### 03/23: '新增顏色分類偵錯指標輸出功能'

**功能說明**:

- 在每顆彩球 metadata 新增 `white_ratio`、`dark_ratio`、`color_ratio`。
- 新增 `COLOR_DEBUG_ENABLED` 與 `COLOR_DEBUG_PRINT` 設定，用於開關偵錯輸出。
- 前端 `SettingsPage` 檢測列表已顯示 `HSV/LAB median` 與 `valid_pixels/mask_pixels` 觀測指標。
- 啟用 `COLOR_DEBUG_ENABLED=true` 時，會額外輸出每顆球的中間特徵：
  - `cx, cy, r`
  - `mask_pixels, valid_pixels, valid_ratio`
  - `hsv_median, lab_median`
  - `final_label, final_style`


### 03/23: '新增多層半徑取樣（核心/中層/外層）'

**功能說明**:
- 顏色分類改為多層圓形取樣：核心層判主色、中層補統計、外層輔助樣式（Solid/Stripe）判斷。
- 透過核心/外層白色分布差異，降低高光造成的條紋誤判。
- 保留既有模板比對 + KMeans 主色流程，不更動 API 主要欄位。

**相關參數**:
- `COLOR_MASK_CORE_RATIO`（預設 `0.45`）
- `COLOR_MASK_MID_RATIO`（預設 `0.65`）
- `COLOR_MASK_OUTER_RATIO`（預設 `0.85`）




### 03/23: '新增暖光／白光燈光情境一鍵切換'

**功能說明**:
- 新增 `GET /api/camera/lighting-profiles`：取得暖光/白光 profile 與當前相機關鍵參數。
- 新增 `POST /api/camera/lighting-profile`：一鍵套用暖光或白光參數組（曝光/白平衡/影像調整）。
- 前端 `SettingsPage` 新增「燈光情境」卡片，支援暖光/白光單擊切換。

**範例用法**:
```json
POST /api/camera/lighting-profile
{ "profile": "warm" }
```

### 03/23: '新增顏色時序平滑（3~5 幀投票）'

**功能說明**:
- 以球心近鄰匹配歷史樣本，對 `label/style` 做短時窗投票平滑。
- 只平滑顏色/樣式分類，不改 YOLO 偵測位置。
- 避免單幀高光或陰影造成顏色/條紋抖動。

**相關參數**:
- `COLOR_TEMPORAL_SMOOTH_ENABLED`
- `COLOR_TEMPORAL_WINDOW`（預設 `4`）
- `COLOR_TEMPORAL_MATCH_DIST`（預設 `28.0`）
- `COLOR_TEMPORAL_MIN_STABLE`（預設 `2`）

### 03/23: '新增局部背景環抑制（1.05r~1.30r）'

**功能說明**:
- 在球外環取樣背景 HSV，估計當下桌布色。
- 對球內與背景過近的像素做排除，降低水藍桌布滲入主色判斷。
- 若排除後有效像素過少，會自動回退到未抑制結果，避免過濾過頭。

**相關參數**:
- `COLOR_BG_RING_ENABLED`
- `COLOR_BG_RING_INNER_RATIO`, `COLOR_BG_RING_OUTER_RATIO`
- `COLOR_BG_HUE_TOL`, `COLOR_BG_SAT_TOL`, `COLOR_BG_VAL_TOL`

### 03/23: '新增局部 Hough 幾何修正（YOLO bbox 內）'

**功能說明**:
- 新增 `LOCAL_HOUGH_REFINE_ENABLED`（預設 `false`），開啟後會在每顆 `white-ball/color-ball` 的 YOLO bbox 內做圓形修正。
- 使用 HSV 中位數門檻過濾陰影候選圓，避免全圖 Hough 常見的陰影誤檢。
- 不會取代 YOLO，只做局部幾何微調（中心點與半徑）。

**相關參數**:
- `LOCAL_HOUGH_PAD_RATIO`
- `LOCAL_HOUGH_MIN_R_SCALE`, `LOCAL_HOUGH_MAX_R_SCALE`
- `LOCAL_HOUGH_DP`, `LOCAL_HOUGH_PARAM1`, `LOCAL_HOUGH_PARAM2`
- `LOCAL_HOUGH_MIN_SAT_MEDIAN`, `LOCAL_HOUGH_MIN_VAL_MEDIAN`

**輸出格式（節錄）**:
```json
{
  "balls": [
    {
      "x": 210,
      "y": 145,
      "radius": 15,
      "geometry_debug": {
        "refined": true,
        "orig_bbox": [206, 140, 30, 30],
        "refined_bbox": [209, 143, 31, 31],
        "score": 0.18,
        "sat_median": 122.4,
        "val_median": 136.8
      }
    }
  ]
}
```


**範例用法**:

```bash
set COLOR_DEBUG_ENABLED=true
set COLOR_DEBUG_PRINT=false
```

**輸出格式（節錄）**:

```json
{
  "balls": [
    {
      "x": 100,
      "y": 200,
      "color": "Blue",
      "style": "Solid",
      "white_ratio": 0.08,
      "dark_ratio": 0.03,
      "color_ratio": 0.71,
      "color_debug": {
        "cx": 116,
        "cy": 216,
        "r": 14,
        "mask_pixels": 620,
        "valid_pixels": 512,
        "valid_ratio": 0.8258,
        "hsv_median": [108.0, 145.0, 132.0],
        "lab_median": [112.0, 141.0, 90.0],
        "final_label": "Blue",
        "final_style": "Solid"
      }
    }
  ]
}
```


### ✅ 已完成功能

1. **HSV 顏色檢測** - 使用 HSV 色彩空間辨識球的顏色
2. **物理碰撞模擬引擎** - 完整的白球、彩球碰撞檢測
3. **球號辨識 (1-15)** - 根據顏色和條紋/實心分類球號
4. **反彈檢測和路徑預測** - 計算彩球反彈路徑和進袋預測
5. **API 回應格式更新** - 包含球號、顏色、樣式資訊

---

## 🔧 技術實作細節

### 1. HSV 顏色檢測 (`_detect_ball_color_hsv`)

**位置**: [tracking_engine.py:259-328](backend/tracking_engine.py#L259-L328)

**功能**:
- 建立圓形遮罩聚焦球中心
- 轉換 BGR 到 HSV 色彩空間
- 分離白球、黑球、彩球
- 計算加權 Hue 值
- 辨識條紋球 vs 實心球

**回傳資料結構**:
```python
{
    "label": "Yellow",       # 顏色名稱
    "style": "Stripe",       # Solid 或 Stripe
    "hue": 35.2,            # Hue 值 (0-180)
    "white_ratio": 0.42,    # 白色區域比例
    "black_ratio": 0.05     # 黑色區域比例
}
```

**顏色映射**:
- **紅色**: Hue ≤ 10 或 ≥ 160
- **棕色**: Hue 10-25 (低 Value)
- **橙色**: Hue 10-25 (高 Value)
- **黃色**: Hue 25-40
- **綠色**: Hue 40-80
- **藍色**: Hue 80-130
- **紫色**: Hue 130-155

---

### 2. 球號分類 (`_classify_ball_number`)

**位置**: [tracking_engine.py:351-374](backend/tracking_engine.py#L351-L374)

**顏色 → 球號映射**:
```python
COLOR_TO_NUM = {
    "Yellow": (1, 9),    # 1號實心, 9號條紋
    "Blue": (2, 10),
    "Red": (3, 11),
    "Purple": (4, 12),
    "Orange": (5, 13),
    "Green": (6, 14),
    "Brown": (7, 15),
}
```

**特殊球**:
- **白球 (Cue ball)**: `number = 0`
- **黑球 (8-ball)**: `number = 8`

**分類邏輯**:
1. 若 `style = "Stripe"` → 回傳條紋球號 (9-15)
2. 若 `style = "Solid"` → 回傳實心球號 (1-7)
3. 若無法判定 → 依 `white_ratio` 猜測

---

### 3. 物理碰撞模擬

#### 3.1 擊球點計算 (`_find_shot_point`)

**位置**: [tracking_engine.py:377-406](backend/tracking_engine.py#L377-L406)

**功能**: 計算球桿接觸白球的位置

**演算法**:
1. 以球桿中心為圓心，半徑為球桿寬度
2. 產生 360 個圓周點
3. 找出最接近白球中心的點
4. 使用滑動平均穩定化結果

#### 3.2 碰撞檢測 (`_collision`)

**位置**: [tracking_engine.py:430-466](backend/tracking_engine.py#L430-L466)

**功能**: 檢測白球與彩球碰撞

**演算法**:
1. 計算白球邊界 360 個點
2. 計算彩球邊界 360 個點
3. 找出兩組點的交集
4. 計算交集點的平均值作為碰撞點

#### 3.3 進袋檢測 (`_bounce_detection`)

**位置**: [tracking_engine.py:468-483](backend/tracking_engine.py#L468-L483)

**功能**: 檢測球是否進袋

**球袋定義** (6個):
```python
[x+52, y+52],        # 左上
[x+52, y+h-52],      # 左下
[x+w-52, y+52],      # 右上
[x+w-52, y+h-52],    # 右下
[x+w//2, y+52],      # 中上
[x+w//2, y+h-52],    # 中下
```

#### 3.4 路徑預測 (`_path_line`)

**位置**: [tracking_engine.py:485-531](backend/tracking_engine.py#L485-L531)

**功能**: 計算彩球反彈路徑

**演算法**:
1. 計算碰撞點到彩球中心的直線方程 (y = mx + c)
2. 模擬最多 2 次反彈
3. 每次反彈：
   - 計算與邊界交點
   - 檢查是否進袋
   - 反轉斜率 (m2 = -m2)
4. 回傳路徑點陣列

#### 3.5 完整預測 (`_pool_shot_prediction`)

**位置**: [tracking_engine.py:533-591](backend/tracking_engine.py#L533-L591)

**回傳資料結構**:
```python
{
    "prediction": True,                    # 是否進袋
    "paths": [[x1, y1], [x2, y2], ...],  # 路徑點
    "color": (80, 145, 75),               # 顯示顏色 (BGR)
    "collision_point": [x, y],            # 碰撞點
    "ball_color": "Yellow - Stripe",      # 球顏色和樣式
    "ball_number": 9,                     # 球號
    "ball_color_meta": {...}              # 完整顏色資訊
}
```

---

### 4. 繪製標註 (`_draw_annotations`)

**位置**: [tracking_engine.py:593-664](backend/tracking_engine.py#L593-L664)

**繪製內容**:
1. **球桌框** - 綠色矩形
2. **球袋** - 紅色圓點 + 碰撞箱
3. **白球** - 圓圈 + "White Ball" 標籤
4. **彩球** - 圓圈 + 顏色/球號標籤
   ```
   Yellow #9 (Stripe)
   Blue #2 (Solid)
   ```
5. **球桿** - 藍色矩形
6. **擊球點** - 洋紅色圓點
7. **預測路徑** - 青色線段
8. **碰撞點** - 黃色圓圈
9. **進袋狀態** - "IN" (綠) 或 "OUT" (紅)

---

## 📡 API 回應格式

### WebSocket Metadata 格式

**端點**: `/ws/control?session_id={id}`

**訊息類型**: `metadata.update`

**Payload 結構**:
```json
{
  "frame_id": 1234,
  "ts_backend": 1704380400000,
  "detected_count": 5,
  "tracking_state": "active",
  "detections": [
    {
      "x": 250,
      "y": 150,
      "w": 32,
      "h": 32,
      "radius": 16,
      "conf": 0.95,
      "color": "Yellow",
      "style": "Stripe",
      "number": 9
    },
    {
      "x": 300,
      "y": 200,
      "w": 30,
      "h": 30,
      "radius": 15,
      "conf": 0.92,
      "color": "Blue",
      "style": "Solid",
      "number": 2
    }
  ],
  "prediction": {
    "prediction": true,
    "paths": [[300, 200], [450, 250], [500, 280]],
    "color": [80, 145, 75],
    "collision_point": [280, 180],
    "ball_color": "Yellow - Stripe",
    "ball_number": 9,
    "ball_color_meta": {
      "label": "Yellow",
      "style": "Stripe",
      "hue": 35.2,
      "white_ratio": 0.42,
      "black_ratio": 0.05
    }
  },
  "ar_paths": [],
  "rate_hz": 10
}
```

---

## 🎯 主要處理流程

### `process_frame()` 流程

**位置**: [tracking_engine.py:120-157](backend/tracking_engine.py#L120-L157)

```
1. 檢查球桌 (detect_table)
   ↓
2. 裁切 ROI (table_roi)
   ↓
3. YOLO 推論 (model.predict)
   ↓
4. 解析球體 (_analyze_balls)
   ├─ 收集白球、彩球、球桿
   ├─ HSV 顏色檢測
   ├─ 球號分類
   ├─ 選擇主要白球/彩球
   └─ 執行物理預測
   ↓
5. 繪製標註 (_draw_annotations)
   ↓
6. 回傳 (frame, data_packet)
```

### `_analyze_balls()` 流程

**位置**: [tracking_engine.py:160-247](backend/tracking_engine.py#L160-L247)

```
1. 遍歷 YOLO 結果
   ├─ white-ball → 加入 white_balls[]
   ├─ color-ball → HSV 檢測 → 球號分類 → 加入 color_balls[]
   └─ cue → 記錄 cue_pos
   ↓
2. 選擇主要白球 (最高信心度)
   ↓
3. 選擇主要彩球
   ├─ 有球桿 → 選最接近球桿
   └─ 無球桿 → 選最高信心度
   ↓
4. 執行物理預測
   ├─ _find_shot_point()
   └─ _pool_shot_prediction()
   ↓
5. 構造回傳數據包
```

---

## 🧪 測試建議

### 1. 單元測試

```python
# 測試 HSV 顏色檢測
def test_hsv_color_detection():
    tracker = PoolTracker()
    # 準備測試球影像 (黃色條紋球)
    test_roi = cv2.imread("test_yellow_stripe.png")
    color_info = tracker._detect_ball_color_hsv(test_roi, [0, 0, 100, 100])
    assert color_info["label"] == "Yellow"
    assert color_info["style"] == "Stripe"

# 測試球號分類
def test_ball_number_classification():
    tracker = PoolTracker()
    color_info = {"label": "Yellow", "style": "Stripe", "white_ratio": 0.42}
    ball_num = tracker._classify_ball_number(color_info)
    assert ball_num == 9
```

### 2. 整合測試

```bash
# 啟動後端
cd backend
python main.py

# 檢查輸出:
# ✅ YOLO model loaded successfully
# ✅ Calibrator initialized successfully
# ✅ MJPEG Stream Manager initialized
# 🚀 Starting camera capture thread for burn-in stream...
```

### 3. 前端測試

```bash
# 啟動前端
cd frontend
npm run dev

# 訪問 http://localhost:5173
# 1. 檢查 WebSocket 連接狀態
# 2. 點擊「啟動辨識」
# 3. 觀察影像中的球號標註
# 4. 檢查 Metadata 頁面的 detections 數據
```

### 4. 驗證項目

- [ ] 白球正確標註為 "White Ball"
- [ ] 黑球正確標註為 "Black #8"
- [ ] 彩球顯示正確顏色和球號 (例: "Yellow #9 (Stripe)")
- [ ] 預測路徑正確繪製 (青色線段)
- [ ] 進袋判定正確 ("IN" 綠色 / "OUT" 紅色)
- [ ] WebSocket metadata 包含完整球號和顏色資訊
- [ ] 前端 Metadata 頁面正確顯示所有球的資訊

---

## 📁 修改檔案清單

### 後端檔案

1. **backend/tracking_engine.py** (664 lines)
   - ✅ 完全重寫
   - 整合 poolShotPredictor.py 所有功能
   - 新增 HSV 顏色檢測
   - 新增物理碰撞模擬
   - 新增球號分類

### 前端檔案 (已在之前完成)

1. **frontend/src/components/Dashboard.tsx** - 主組件重寫
2. **frontend/src/components/TopBar.tsx** - YOLO 控制按鈕
3. **frontend/src/components/pages/MetadataPage.tsx** - 顯示球號資訊

### API 端點 (無需修改)

- `POST /api/control/toggle` - YOLO 控制 (已存在)
- `GET /ws/control` - WebSocket 控制 (已包含 metadata)

---

## 🔍 遵照 v1.5 技術文檔規範

### ✅ 遵循項目

1. **WebSocket 協議**
   - ✅ 使用 envelope 格式
   - ✅ metadata.update 訊息類型
   - ✅ 包含 frame_id, ts_backend
   - ✅ 10Hz 更新頻率

2. **Session 管理**
   - ✅ Kick-Old 策略
   - ✅ Session ID 驗證

3. **數據格式**
   - ✅ 球體資料包含位置、大小、信心度
   - ✅ 新增顏色、樣式、球號欄位
   - ✅ 預測結果包含路徑和進袋判定

4. **錯誤處理**
   - ✅ try-except 捕獲異常
   - ✅ 安全裁切避免越界
   - ✅ 除零檢查

5. **型別標註**
   - ✅ 所有函數有 type hints
   - ✅ 回傳型別明確定義

---

## 🎉 整合成果

### 新增功能

1. **球號辨識**: 可辨識 1-15 號球 + 白球 + 8 號黑球
2. **顏色檢測**: 7 種顏色 (Yellow, Blue, Red, Purple, Orange, Green, Brown)
3. **樣式分類**: Solid (實心) vs Stripe (條紋)
4. **物理預測**: 完整碰撞檢測 + 路徑預測 + 進袋判定
5. **視覺化**: 影像標註球號、顏色、預測路徑

### 前後端整合

- ✅ 後端 tracking_engine.py 產生完整數據
- ✅ 後端 main.py 透過 WebSocket 傳送
- ✅ 前端 Dashboard 接收並顯示
- ✅ 前端 MetadataPage 顯示詳細資訊

### 技術特色

- **準確性**: HSV 色彩空間提高顏色辨識準確度
- **穩定性**: 滑動平均穩定化擊球點
- **效能**: 僅在有球桿時執行預測
- **可視化**: 完整的繪製標註系統

---

## 🚀 啟動指南

詳見 [QUICK_START.md](QUICK_START.md)

### 快速啟動

```bash
# 終端機 1: 啟動後端
cd backend
python main.py

# 終端機 2: 啟動前端
cd frontend
npm run dev

# 瀏覽器訪問
http://localhost:5173
```

### 使用步驟

1. 確認 WebSocket 連接狀態為「已連接」
2. 點擊頂部「🟢 啟動辨識」按鈕
3. 觀察即時影像中的球號標註
4. 切換到 Metadata 頁面查看詳細數據
5. 點擊「🔴 停止辨識」停止

---

## 📖 相關文檔

- [QUICK_START.md](QUICK_START.md) - 快速啟動指南
- [YOLO_CONTROL_UI.md](YOLO_CONTROL_UI.md) - 前端介面使用說明
- [BURN_IN_FIX.md](BURN_IN_FIX.md) - Burn-in 串流修復說明
- [backend/tracking_engine.py](backend/tracking_engine.py) - 追蹤引擎完整程式碼

---

**整合完成時間**: 2026-01-04
**遵照規範**: v1.5 技術文檔
**整合來源**: poolShotPredictor.py
**主要修改**: tracking_engine.py (664 lines)

### 03/23: '修正白光模式切換覆寫與過暗問題'

**功能說明**:
- 後端 `GET /api/camera/lighting-profiles` 新增 `active_profile` 欄位，前端不再用 `wb_temp` 推測模式。
- 後端 `POST /api/camera/lighting-profile` 成功後會更新 `camera_state["lighting_profile"]`，讓頁面重新讀取時維持正確選中狀態。
- 白光參數改為較保守設定（`exposure=-6`、`brightness=136`），避免切到白光後即時影像過暗。

**範例用法**:
```json
GET /api/camera/lighting-profiles
{
  "active_profile": "white",
  "current": { "exposure": -6, "auto_wb": false, "wb_temp": 5200 }
}
```

### 03/23: '白光模式二次調亮（明亮優先）'

**功能說明**:
- 針對現場回報「白光仍過暗」，進一步上調白光 profile。
- 白光參數更新為：`exposure=-4`、`brightness=148`、`brightness_adjust=18`，先確保即時影像可視。
- 後續可依現場再微調至 `brightness_adjust=12~22` 區間平衡亮度與雜訊。

**範例用法**:
```json
POST /api/camera/lighting-profile
{ "profile": "white" }
```

### 03/23: '修正暖/冷模式亮度與生效值回報'

**功能說明**:
- 暖光 profile 調亮：`wb_temp=3600`、`exposure=-5`、`brightness=144`、`brightness_adjust=12`。
- 白光 profile 調亮：`wb_temp=6200`、`exposure=-3`、`brightness=152`、`brightness_adjust=20`。
- `POST /api/camera/lighting-profile` 回傳 `effective_current`，前端訊息會顯示實際 EXP/WB/AutoWB。
- 若驅動不支援參數（例如 WB），前端會顯示後端 warnings，便於判斷是否是硬體限制。

**輸出格式（節錄）**:
```json
{
  "status": "ok",
  "profile": "white",
  "apply_result": {
    "warnings": ["白平衡色溫設定可能不支援"]
  },
  "effective_current": {
    "exposure": -3,
    "auto_wb": false,
    "wb_temp": -1
  }
}
```

### 03/23: '新增 WB 不支援時的軟體色溫補償備援'

**功能說明**:
- 影像後處理新增 `color_temp_shift`（-50~50），在硬體 `wb_temp` 不支援時仍可做暖/冷色調切換。
- `warm/white` 燈光 profile 已內建 `color_temp_shift`（暖光 `+16`、白光 `-16`）。
- `POST /api/camera/lighting-profile` 新增 `wb_fallback_active`，前端會顯示「已啟用軟體色溫補償」。

**範例用法**:
```json
POST /api/camera/lighting-profile
{ "profile": "warm" }
```

**輸出格式（節錄）**:
```json
{
  "status": "ok",
  "profile": "warm",
  "wb_fallback_active": true,
  "effective_current": { "exposure": -5, "auto_wb": false, "wb_temp": -1 }
}
```

### 03/23: '修正白球疊色與袋口黑球誤檢'

**功能說明**:
- `tracking_engine.py` 新增候選球去重（球心距離抑制），避免同顆球被多個框重複標註。
- 新增白球優先重疊抑制：與主白球高度重疊的彩球框會移除，避免白球上方疊到其他顏色標籤。
- 袋口誤檢過濾改為固定生效：進入袋口捕捉區與袋口核心區的黑色/未知假球不再加入 `balls`。

**相關參數**:
- `BALL_DUPLICATE_CENTER_RATIO`（預設 `0.72`）
- `WHITE_OVERLAP_SUPPRESS_RATIO`（預設 `0.88`）
- `POCKET_FALSE_POSITIVE_FILTER_ENABLED`（預設 `true`）
- `POCKET_FALSE_POSITIVE_CORE_RATIO`（預設 `0.62`）

### 03/23: '強化球桌偵測容錯（暖/冷補償後仍可抓桌）'

**功能說明**:
- `detect_table()` 在主 HSV 偵測失敗時，新增次級策略：
  - 先嘗試放寬目前 HSV 範圍（relaxed-current）
  - 再遍歷其他 `TABLE_COLOR_PRESETS` 預設做備援偵測
- 若次級策略成功，直接採用該遮罩結果建立 `table_roi`，避免因色溫偏移造成「抓不到球桌」。

**輸出訊息（節錄）**:
```text
✅ Table detected by fallback mask (relaxed-current): x=..., y=..., w=..., h=...
```
