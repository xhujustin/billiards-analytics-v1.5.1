# IMPLEMENTATION_GUIDE.md
## 實作指南（v1.5）

---

## 前端 SDK 架構

### 模組
- SessionManager
- WebSocketManager
- ConnectionHealthMachine
- CommandDispatcher
- MetadataBuffer

---

## TypeScript 型別（節錄）
（此處直接引用 v1.5 中的 TS 定義，實務上建議獨立為 types.ts）

---

## WebSocket 重連策略
- maxRetries: 5
- exponential backoff + jitter
- close_code=4001 → 不重連

---

## Metadata 高頻處理
- buffer + throttle（1Hz）
- latest-first 策略
- buffer 上限避免記憶體洩漏

---

## Session 管理
- localStorage session_id
- renew window = min(20%, 5min)
- renew fallback → new session

---

## 開發環境
參考 `.env.example`
---

## 03/22:'新增A+B球色辨識與實心/條紋判定'

### 功能摘要
- 新增 A+B 判定流程：
- A（模板比對）：Hue/LAB/Saturation 統合距離。
- B（K-means）：在彩色像素內分群，取主彩群做二次比對。
- 實心/條紋改為「全區 vs 中心區」規則，降低近袋口與高光誤判。

### 規範用法
- 後端維持既有呼叫：`_detect_ball_color_hsv(roi_img, bbox)`。
- 內部輸出仍回傳 `label/style/hue/white_ratio/black_ratio`，並新增 `template_score` 供除錯。
- `label` 顏色類別：Yellow/Blue/Red/Purple/Orange/Green/Brown/White/Black/Unknown。
- `style` 類別：Solid/Stripe/Cue/Unknown。

### 輸出格式（範例）
```json
{
  "label": "Yellow",
  "style": "Solid",
  "hue": 27.8,
  "white_ratio": 0.11,
  "black_ratio": 0.03,
  "template_score": 0.29
}
```

### 03/22 補充：黃/橘誤判修正
- 在 `_classify_main_color_ab` 增加暖色交界二次判定（Yellow/Orange/Brown）。
- 依 `final_hue` + `V中位數` 修正：高亮且 hue 較高時優先 Yellow，低亮且 hue 偏低時優先 Brown。
- 用於降低 1 號黃球在暖光下被誤判為 5 號橘球。

## 03/22:'新增顏色校正模式（花式/斯諾克）'

### 功能摘要
- 新增顏色校正設定檔流程：可依 `pool/snooker` 建立、選擇、儲存、套用。
- 前端設定頁新增「顏色校正模式」區塊，可配對「系統顏色 vs 實際顏色」並輸入 HSV 範圍。
- 後端將設定檔寫入 SQLite `color_calibration_profiles`，並可即時套用到顏色分類模板。

### API 規範
- `GET /api/color-calibration/profiles?mode=pool|snooker`：列出設定檔與系統顏色。
- `POST /api/color-calibration/profiles`：新增設定檔，Body: `{ mode, name }`。
- `GET /api/color-calibration/profiles/{profile_id}`：取得設定檔與 mappings。
- `PUT /api/color-calibration/profiles/{profile_id}/mappings`：儲存配色，Body: `{ mappings }`。
- `POST /api/color-calibration/apply`：套用設定檔，Body: `{ profile_id }`。

### mappings 輸入格式
```json
{
  "Yellow": {
    "actual_label": "亮黃",
    "hsv_lower": [20, 80, 80],
    "hsv_upper": [35, 255, 255]
  }
}
```

### 套用輸出格式（範例）
```json
{
  "status": "success",
  "profile_id": 3,
  "mode": "pool",
  "applied": 7
}
```

### 03/22 補充：目前套用設定檔狀態 + 一鍵回復預設模板
- 新增 `GET /api/color-calibration/state`：回傳目前套用中的設定檔名稱、模式、套用時間。
- 新增 `POST /api/color-calibration/reset`：一鍵回復系統預設顏色模板。
- 前端顏色校正模式頁面增加「目前套用中的設定檔」顯示區塊與「一鍵回復預設模板」按鈕。

### 03/22 補充：二層式顏色校正與相機點選取樣
- 設定頁新增「顏色校正」入口，位置在「投影機校正」下方。
- 顏色校正改為二層頁面（獨立 `ColorCalibrationPage`），操作方式與投影機校正一致（進入頁面後調整）。
- 新增相機點選取樣 API：`POST /api/color-calibration/sample-hsv`，可用畫面座標取得 `hsv_center/hsv_lower/hsv_upper`。

### 03/22 補充：相機點選取樣即時回饋
- `POST /api/color-calibration/sample-hsv` 支援 `rx/ry` 比例座標，避免串流尺寸差異造成取樣失敗。
- 回傳新增 `rgb_center`，前端可立即顯示取樣色塊與 HSV，確保點擊後有可見反應。

### 03/22 補充：YOLO ROI 自動逐顆掃描流程
- 顏色校正頁流程改為：選設定檔 → 開始自動掃描 → 逐顆「採用並下一顆」。
- 新增 `GET /api/color-calibration/auto-scan?mode=pool|snooker`：
- 讀取目前 YOLO 球框（`latest_analysis_data.data.balls`），自動裁切 ROI 並回傳每顆球的 `hsv_center/hsv_lower/hsv_upper/rgb_center`。
- 建議操作：確保 YOLO 分析已啟用，畫面內同時有要校正的球，再啟動掃描。

### 03/22 補充：顏色校正單顆引導式精靈與 K-Means 主色擷取
- **單顆引導精靈**：將原本的批次掃描改為依序引導，畫面上每次只提示放入一顆對應顏色的球進行掃描 `Auto Scan`。
- **保留調整空間**：所有掃描結果即時在畫面左下方列表呈現，點擊任一顏色方塊可隨時跳轉回去重新掃描或手動微調 `hsv_lower` 與 `hsv_upper`。
- **未設定預設值**：所有未經掃描或手動跳過的球體，其 `hsv_lower` 與 `hsv_upper` 預設值為 `[0, 0, 0]`。
- **K-Means 擷取主色**：後端 `auto-scan` 邏輯捨棄容易受高光/陰影干擾且有 `0/180` 環邊界問題的簡單算術平均。改將 ROI 內圓形遮罩範圍內的像素保留，轉至標準的 BGR 空間以 K-Means (K=3) 集群分類找出面積最大的「主色 (Dominant Color)」，再轉換回 HSV，大幅提高對真實底色判斷的準確率。

### 03/22 補充：YOLO Second-Pass 備援機制與長寬比容錯
- **Second-Pass Fallback**：當前畫面偵測到的球數少於設定之閾值（例如 `< 4` 顆）時，自動觸發第二次推論，採用更大的 `imgsz` (預設 960) 與更低的 `conf` (預設 0.04) 進行防漏偵測補救，有效應對暗色球或動態模糊情況。
- **長寬比放寬**：將球體的長寬比 (Aspect Ratio) 容忍範圍從 `0.65~1.55` 放寬至 `0.50~1.90`，以適應快速移動時的殘影或不完美的橢圓形狀。
- **環境變數控制**：支援透過 `.env` 進行各項效能與閥值的細部配置：
  - `SECOND_PASS_ENABLED`
  - `SECOND_PASS_MIN_OBJECTS`
  - `SECOND_PASS_CONF_THR`
  - `SECOND_PASS_IOU_THR`
  - `SECOND_PASS_IMG_SIZE`
