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

### 04/24:'新增條紋球時序鎖定與不對稱切換規則'

### 功能摘要
- 在 `tracking_engine.py::_smooth_color_info_temporal()` 新增 `style_lock` 機制，對同一顆球做短時窗條紋/實心鎖定。
- `Unknown` 不再覆蓋既有 `Solid/Stripe` 結果，避免 9 號在旋轉或反光時跳成 `unknown`。
- `Stripe -> Solid` 改為不對稱切換，需要更強、且連續更多幀的證據；用來避免 9 號因為白帶暫時不可見而被誤判成 1 號。

### 規範用法
- 後端呼叫流程不變，仍由 `_detect_ball_color_hsv()` 產生 `label/style`，再交給 `_smooth_color_info_temporal()` 平滑。
- 若同位置彩球在歷史上已穩定為 `Stripe`，後續單幀 `Solid` 觀測不會立即覆蓋。
- 僅在連續多幀強證據成立時才允許 `Stripe -> Solid` 切換。
- 黃球若落在 `Yellow + Unknown`，目前會先保守映射為 9 號，避免即時畫面在 `9號 / 1號 / unknown` 之間來回跳動。

### 輸出格式（新增除錯欄位）
```json
{
  "temporal_debug": {
    "label_raw": "Yellow",
    "style_raw": "Solid",
    "label_smoothed": "Yellow",
    "style_smoothed": "Stripe",
    "style_lock": "Stripe",
    "switch_candidate": "Solid",
    "switch_hits": 2,
    "style_signal_strength": 0.82
  }
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

### 04/23:'新增真正多球路徑規劃（雙規則 + 雙通道）'

### 功能摘要
- 新增 `RoutePlanner` 子模組，將路徑規劃拆分為 `state_extractor / candidate_generator / physics_validator / route_scorer / stroke_recommender`。
- 多球候選支援：`straight / cut / bank / combo`，並輸出 `best_route + routes[] + coach_notes`。
- 同時支援 `practice` 與 `9ball` 規則評分；`9ball` 會優先檢查首碰合法目標球。
- WebSocket `metadata.update` 新增 `multi_plan`，並新增 `planner.update / planner.error` 推送。
- `multi_plan.best_route.route_segments` 會分段輸出全局路線：母球入射、子球路線、母球擊後路線。
- 每條路線新增 `cue_landing_point / cue_landing_zone`，用於顯示預計母球落點。
- 新增 `POST /api/planner/select-route`，可從 Top-N 候選中切換目前 AR/metadata 顯示的進球線路。
- AR 投影端新增 `ar_route_segments`，會將 `route_segments` 轉成投影機座標後分段渲染；新版路線存在時不再混畫舊版 `ar_paths/aim_lines`。

### 規範用法
- 後端追蹤主流程會優先執行多球規劃；無法規劃時自動 fallback 至舊版單路徑預測。
- API：
  - `POST /api/planner/plan`
  - `POST /api/planner/disable`
  - `POST /api/planner/select-route`
  - `GET /api/planner/state`
- 建議參數：
  - `top_n=5`
  - `max_bounces=2`
  - `combo_depth=2`
- 未指定 `target_ball_number` 時，practice 模式預設以桌面最小球號作為第一目標；9ball 模式優先使用目前局面的合法目標球。
- 即時 planner 預設關閉，只在一般練習 `practice_single` 啟動時開啟；主頁、設定、顏色校正、投影校正與球型練習都必須關閉並清空舊路線。
- 前端 Top-N 列表點選 route 時，呼叫 `POST /api/planner/select-route`，後端會把該 route 設為 `best_route` 並更新投影線路。
- AR projector 使用 `ar_route_segments` 作為主要資料源；`ar_paths` 只作為舊版 fallback。

### 輸出格式（範例）
```json
{
  "rule_profile": "9ball",
  "latency_ms": 126.4,
  "best_route": {
    "route_type": "bank",
    "target_ball_number": 1,
    "score": 0.61,
    "difficulty": 39,
    "success_prob": 0.61,
    "path_points": [[620, 410], [738, 392], [970, 240], [1130, 125]],
    "route_segments": [
      { "type": "cue_to_contact", "points": [[620, 410], [738, 392]], "color": "white" },
      { "type": "object_to_rail", "points": [[738, 392], [970, 240]], "color": "green" },
      { "type": "object_to_pocket", "points": [[970, 240], [1130, 125]], "color": "green" },
      { "type": "cue_after_contact", "points": [[738, 392], [760, 548]], "color": "cyan" }
    ],
    "cue_landing_point": [760, 548],
    "cue_landing_zone": { "center": [760, 548], "radius": 34, "label": "預計母球落點" },
    "stroke_hint": {
      "type": "bank_shot",
      "power": "medium",
      "spin": "running_english",
      "rationale": "反彈球建議順塞，提升吃庫後前進穩定度。"
    },
    "risk_flags": []
  },
  "routes": [],
  "coach_notes": [
    "最佳路線：bank，成功率 61%，難度 medium。",
    "建議桿法：bank_shot / running_english / 力道 medium。"
  ]
}
```

### 04/24:'新增多球規劃 P0-1/P0-3 幾何可信化'

### 功能摘要
- `planner.state_extractor` 新增 `table_ball_radius_px`，從桌面現有球半徑中位數推估全桌統一球徑。
- `PlannerBall` 新增：
  - `radius_px_raw`
  - `radius_px`
  - `radius_source`
- 各球半徑改為先做正規化，再交給 Ghost Ball、遮擋檢查與吃庫點計算，避免 bbox 抖動直接把球徑帶歪。
- `physics_validator.is_path_clear()` 升級為 capsule sweep 概念：
  - 以移動球半徑 + 阻擋球半徑 + clearance margin 做掃掠碰撞檢查
  - 不再只用中心線距離判斷是否擋球

### 規範用法
- `PlannerState.table_ball_radius_px` 為 planner 幾何統一尺度，後續候選生成與碰撞檢查都應優先使用它。
- `PlannerBall.radius` 目前對外仍維持可用，但內部實際回傳正規化後的 `radius_px`，以保持既有模組相容。
- 若單顆球偵測半徑異常，系統只允許在全桌球徑附近做小幅修正，不直接信任單幀 bbox。

### 輸出格式（內部型別補充）
```json
{
  "table_ball_radius_px": 14.0,
  "ball": {
    "radius_px_raw": 40.0,
    "radius_px": 15.68,
    "radius_source": "object_median"
  }
}
```

### 04/24:'新增多球規劃 P0-2/P0-4/P0-5 洞口窗口、有效反射區與一致錯誤輸出'

### 功能摘要
- `PlannerState` 新增：
  - `pockets[]`：每個袋口的 `center / mouth_segment / capture_radius / approach_normal`
  - `rail_segments`：四條庫邊的有效反射區段
- `candidate_generator` 的 `straight / cut / bank / combo / kick` 改為優先使用 `pockets[]`
  - 進袋前先檢查是否符合袋口窗口與進袋方向
  - bank / kick 反射點必須落在 `rail_segments` 內
- `route_planner` 補一致錯誤碼：
  - `NO_POTTING_ROUTE`
  - `ONLY_ESCAPE_ROUTE_AVAILABLE`
  - `TARGET_BLOCKED_NO_LEGAL_ROUTE`

### 規範用法
- 直球、切球、組合球不再只對袋口中心連線；需通過 `can_pocket_ball()` 的袋口窗口檢查。
- bank / kick 的反射點若超出有效庫邊區段，直接淘汰，不再只靠 `near_hole` 粗略過濾。
- 當候選路線在排序後全部被幾何條件或難度門檻淘汰時，planner 必須回傳錯誤碼與教練提示，而不是留空白或切回舊預測。
- `kick_escape` 屬於 contact-only 解球候選，只要求母球翻袋後合法碰到目標球，不要求目標球有進袋線；候選必須由鏡像反射幾何產生，不允許用任意庫邊採樣補假路線。

### 輸出格式（內部型別補充）
```json
{
  "pockets": [
    {
      "id": "pocket-0",
      "center": [120, 120],
      "mouth_segment": [[132, 146], [158, 120]],
      "capture_radius": 16.8,
      "approach_normal": [1.0, 1.0]
    }
  ],
  "rail_segments": {
    "top": [[180, 122], [1100, 122]],
    "bottom": [[180, 598], [1100, 598]]
  },
  "error": "NO_POTTING_ROUTE"
}
```

### 04/24 補充：恢復 contact-only 翻袋解球
- 新增 `route_type="kick_escape"`，用於最低號被擋住但仍可透過翻袋合法碰球的場景。
- `kick_escape` 不輸出 `object_to_pocket`，避免被進球窗口檢查誤殺；改輸出 `object_after_contact` 表示合法碰球後子球預估行進方向。
- 評分器會將其標為 `contact_only` 風險，成功率上限較低，只作為解球/安全球建議。

### 04/24:'修正翻袋解球反射幾何與 Top-N 去重'
- bank / kick / kick_escape 反射點檢查統一使用「母球中心可行反射線」，避免用實體庫邊線誤殺合法鏡像反射。
- 移除 `kick_escape` 的 fallback 庫邊採樣；無鏡像解時回傳無進球/無合法路線，不再用錯誤角度硬畫路線。
- `kick_escape` 增加 `route_segments[].type="object_after_contact"`，前端與 AR 可顯示子球接觸後短行進線。
- Top-N 對 `kick_escape` 依 `target_ball_number + rail + kick_bounces` 去重，避免同一顆球同一組庫邊因接觸點微差重複洗版。

### 04/24:'新增 P1-1/P1-2 多庫解球分類與 Top-N 策略分群'
- `max_bounces` 預設提高為 `3`，允許 1/2/3 庫鏡像解球候選，但仍受有效反射區、洞口避讓與 capsule sweep 檢查限制。
- 解球候選新增分類：
  - `route_class="potting_route"`：可進袋路線，包含 `straight / cut / bank / combo / kick`。
  - `route_class="safe_escape"`：合法首碰且預估母球/子球分離較好的安全解球。
  - `route_class="contact_only"`：只保證合法碰到目標球，不宣稱可進袋或安全。
- `metadata.strategy_label` 供前端 Top-N 顯示策略名稱，例如 `直接進攻 / 翻袋進攻 / 顆星進攻 / 安全解球 / 合法碰球`。
- Top-N 選路改為策略分群：
  - 先保留最高分路線。
  - 再依 `route_class + route_type + rail + kick_bounces` 補不同策略。
  - `safe_escape` 最多保留 2 條，`contact_only` 最多保留 1 條，避免解球線洗版。

### 輸出格式（P1 補充）
```json
{
  "route_type": "safe_escape",
  "metadata": {
    "base_route_type": "kick_escape",
    "route_class": "safe_escape",
    "strategy_label": "安全解球",
    "rail": "top-bottom",
    "kick_bounces": 2,
    "safety_score": 0.68
  },
  "route_segments": [
    {"type": "cue_to_contact", "points": [[260, 390], [500, 134], [720, 360]]},
    {"type": "object_after_contact", "points": [[730, 370], [860, 430]]},
    {"type": "cue_after_contact", "points": [[720, 360], [650, 500]]}
  ]
}
```

### 04/24:'修正解球母球落點可達性'
- `kick_escape / safe_escape / contact_only` 新增最後一腿撞擊面對齊檢查：
  - `impact_alignment < 0.22` 的候選會被淘汰，避免母球從不可能的背面/側面接觸目標球。
- 母球碰球後落點不再固定畫長切線：
  - 可用切線時輸出 `metadata.cue_leave_model="tangent"`。
  - 近滿球或切線不可信時改為接觸點外側短停球區，輸出 `metadata.cue_leave_model="stop_zone"`。
- `stop_zone` 會降低 `safety_score`，避免把不能實際走到遠端落點的解球誤判成安全解球。

### 輸出格式（母球落點補充）
```json
{
  "route_type": "contact_only",
  "cue_landing_point": [512, 386],
  "metadata": {
    "cue_leave_model": "stop_zone",
    "impact_alignment": 0.41,
    "safety_score": 0.38
  }
}
```
