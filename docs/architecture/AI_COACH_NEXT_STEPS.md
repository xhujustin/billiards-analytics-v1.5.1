# AI Coach 後續實作計畫

## 05/07:'ROI 驗證、AR 校準、AI Coach 品質與第二版走位'

### 目前狀態

- `planner.result.v1`、`position_play.v1`、`coach.context.v1` 已完成第一版資料鏈。
- 即時影像頁與練習頁已可顯示下一球、母球預估點、走位目標區與走位成功率。
- burn-in 與投影 AR 已可接收並繪製走位目標區、避開區與下一球標記。
- `RouteScorer` 已把走位分數納入路線排序，第一版權重為原路線分數 70%、走位分數 30%。
- 桌布 ROI 微調已接到前端設定頁、後端 API 與 tracker，實際使用 `table_roi` 會進 planner 與 AI Coach payload。

## 05/10:'新增 ROI 微調後 runtime 資料一致性'

### 規範用法

- 呼叫 `POST /api/table/roi-adjustment` 或 `POST /api/table/roi-adjustment/reset` 後，後端會立即把 tracker 目前的 `table_roi`、`table_roi_raw`、`table_roi_adjustment`、`table_roi_status` 與 `holes` 同步回 `latest_analysis_data.data`。
- ROI 改變後，舊的 `multi_plan`、`ar_route_segments`、`ar_best_route` 會被清空，`planner_error` 會標記為 `TABLE_ROI_CHANGED_REPLAN_REQUIRED`，避免前端或 AR 繼續使用舊桌框計算出的路徑。
- 後端會同步清除 `tracker.route_planner` 的 `last_plan`、`last_error`、`_last_state_hash`、`_last_state_hash_plan` 等快取，下一次規劃會以新的 ROI 與袋口狀態重新計算。

### 輸出格式

`GET /api/planner/state` 會額外回傳 runtime ROI 欄位，供設定頁、AI Coach debug 與 planner state 交叉檢查：

```json
{
  "runtime_table_roi": [100, 120, 900, 460],
  "runtime_table_roi_raw": [96, 118, 910, 468],
  "table_roi_adjustment": {"left": 4, "top": 2, "right": -6, "bottom": -6},
  "table_roi_status": "hsv",
  "planner_error": "TABLE_ROI_CHANGED_REPLAN_REQUIRED"
}
```

## 05/10:'新增多球路徑規劃即時穩定化'

### 目的

降低即時偵測抖動造成的多球路線閃爍。常見來源包含單幀白球/彩球缺失、桌框或袋口狀態短暫不足，以及走位分數混合後候選路線分數非常接近而互相切換。

### 規範用法

- `RoutePlanner` 會在 `position_play` 走位分數混合與最終排序後，再套用上一條最佳路線的 hysteresis。
- 若新最佳路線只小幅領先上一條路線，且目標球相同，會保留上一條顯示路線。
- `PoolTracker` 即時流程在 planner 啟用時，若偵測狀態短暫不足，最多保留上一筆有效 `multi_plan` 8 幀。
- 手動選路 `selected_route_id` 仍優先於自動穩定化，不會被 hysteresis 覆蓋。

### 輸出格式

當即時流程沿用上一筆路線時，`multi_plan` 會保留原本 `planner.result.v1` 結構，並額外帶：

```json
{
  "hysteresis_hold": true,
  "realtime_hold_frames": 1,
  "error": "DETECTION_TEMPORARILY_MISSING"
}
```

`error` 可能為：

- `DETECTION_TEMPORARILY_MISSING`：即時偵測資料短暫不足。
- `INSUFFICIENT_STATE_HELD`：有資料但 planner 無法抽出完整狀態，暫時沿用上一條路線。

### 範例

若第 N 幀規劃出 `route-a`，第 N+1 幀因 YOLO 漏掉目標球導致狀態不足，metadata 仍會回傳 `route-a` 並標記 `hysteresis_hold: true`。前端與 burn-in overlay 可持續繪製上一條路線，避免畫面清空後又重畫。

## 05/10:'新增 RouteScorer 模式化走位權重'

### 規範用法

- `RouteScorer.blend_position_play_score(route, rule_profile, scoring_mode)` 會依模式混合進球分數與走位分數。
- `practice` 使用進球 60%、走位 40%；`9ball` 使用進球 65%、走位 35%；其它模式維持舊版進球 70%、走位 30%。
- `metadata.position_score_component` 保留相容欄位，`metadata.score_breakdown` 提供完整分數拆解。

### 輸出格式

```json
{
  "metadata": {
    "position_score_component": 0.82,
    "position_score_weight": 0.4,
    "score_breakdown": {
      "scoring_mode": "practice",
      "rule_profile": "practice",
      "pot_score": 0.7,
      "pot_weight": 0.6,
      "position_score": 0.82,
      "position_weight": 0.4,
      "final_score": 0.748
    }
  }
}
```

## 05/10:'新增 2-ply Lookahead 策略規劃基礎'

### 規範用法

- 新增 `ShotSimulator`，用現有 `RouteCandidate` 的母球落點、`position_play` 與 `metadata.physics` 近似模擬第一桿後的 `PlannerState`。
- 新增 `StateEvaluator`，將模擬後球局評估為 `state_score`、`attack_score`、`position_score`、`safety_score` 與 `risk_score`。
- 新增 `LookaheadPlanner`，可對候選路線做 2-ply 評估：目前路線分數 + 模擬後球局分數 + 下一桿候選分數。
- `RoutePlanner.plan()` 與 `plan_from_runtime_packet()` 新增可選參數 `lookahead_enabled`、`lookahead_ply`、`lookahead_candidate_count`、`lookahead_next_top_n`、`lookahead_score_weight`；預設關閉以維持即時效能與既有行為。
- 啟用 lookahead 時，資料會寫入 `RouteCandidate.metadata.lookahead`，不更動 `planner.result.v1` 既有欄位。

### 範例

```python
plan = planner.plan_from_runtime_packet(
    packet,
    rule_profile="9ball",
    top_n=5,
    lookahead_enabled=True,
    lookahead_ply=2,
    lookahead_candidate_count=3,
    lookahead_next_top_n=2,
    lookahead_score_weight=0.25,
)
```

### 輸出格式

```json
{
  "metadata": {
    "lookahead": {
      "schema_version": "planner.lookahead.v1",
      "enabled": true,
      "ply": 2,
      "status": "ok",
      "simulator": {
        "model": "shot_simulator.v1",
        "confidence": 0.68
      },
      "state": {
        "potted_ball_numbers": [1],
        "next_target_ball_number": 2,
        "cue_ball_center": [705.0, 360.0]
      },
      "evaluation": {
        "state_score": 0.72,
        "next_best_score": 0.66,
        "score": 0.699,
        "score_weight": 0.25,
        "pre_lookahead_score": 0.64,
        "final_score": 0.6548
      },
      "selected_next_route_id": "cut-2-1160-120",
      "next_routes": [],
      "warnings": []
    }
  }
}
```

## 05/10:'新增 Lookahead 前後端觸發入口'

### 規範用法

- `POST /api/planner/plan` 與 `POST /api/planner/stroke` 支援 lookahead 參數，前端單球練習面板可用「2-ply 走位預判」開關啟用。
- 預設仍為關閉，避免即時路徑規劃在一般使用時增加額外延遲。
- 後端會限制 `lookahead_candidate_count`、`lookahead_next_top_n` 與 `lookahead_score_weight`，避免前端輸入造成規劃成本失控。

### 範例

```json
{
  "rule_profile": "practice",
  "top_n": 5,
  "max_bounces": 3,
  "combo_depth": 2,
  "lookahead_enabled": true,
  "lookahead_ply": 2,
  "lookahead_candidate_count": 5,
  "lookahead_next_top_n": 3,
  "lookahead_score_weight": 0.25,
  "stroke": {
    "tip": "center",
    "power": "medium"
  }
}
```

### 輸出格式

啟用後，候選路線會在既有 `RouteCandidate.metadata` 下新增 `lookahead`，格式沿用 `planner.lookahead.v1`。前端仍使用 `planner.result.v1`，不需要改動既有 `best_route`、`routes`、`coach_notes` 讀取方式。

## 05/11:'改善 Practice Top-N 與 Lookahead 呈現'

### 規範用法

- Practice 模式下，若合法目標球候選不足 `top_n`，後端會補入 `practice_teaching_alternative` 教學候選，避免 Top-N 只剩一列。
- 9-ball 模式仍維持合法首碰球過濾，不補入可能犯規的候選。
- 前端切換「2-ply 走位預判」時，如果已有規劃結果，會立即重新規劃並更新 Top-N。
- Top-N 表格新增 `2-ply` 欄位，讓 `metadata.lookahead.evaluation.final_score` 可直接被比較。
- `metadata.lookahead.next_routes[0]` 必須包含下一手的目標球、路線類型、進球率、走位率、建議落點、路線段與桿法摘要，前端用來顯示「下一顆球要怎麼走」。
- `transform_best_route_for_ar()` 會把 `metadata.lookahead.next_routes[0]` 轉成 `ar_best_route.lookahead.next_routes[0]`，投影 AR 使用紫色 2P 樣式呈現下一手走位。

### 範例

```json
{
  "routes": [
    {
      "route_type": "cut",
      "target_ball_number": 1,
      "metadata": {
        "lookahead": {
          "evaluation": {
            "final_score": 0.42
          },
          "next_routes": [
            {
              "route_type": "straight",
              "target_ball_number": 2,
              "success_prob": 0.55,
              "position_success_prob": 0.38,
              "route_segments": [
                {
                  "type": "cue_to_contact",
                  "points": [[755, 309], [850, 260]]
                },
                {
                  "type": "cue_after_contact",
                  "points": [[850, 260], [900, 320]]
                }
              ],
              "cue_landing_point": [755, 309],
              "stroke_hint": {
                "type": "center",
                "power": "medium",
                "spin": "none"
              }
            }
          ]
        }
      }
    },
    {
      "route_type": "bank",
      "target_ball_number": 4,
      "metadata": {
        "practice_teaching_alternative": true
      }
    }
  ]
}
```

### 輸出格式

`practice_teaching_alternative` 僅表示該候選用於練習教學補位，不代表 9-ball 規則下合法；前端顯示仍沿用 `RouteCandidate`，不新增新的 plan schema。`lookahead.next_routes` 是摘要資料，不取代下一輪完整 `RouteCandidate`，但必須足以支援 UI 與 AR 提示下一手方向。

### 第一階段：整理桌布 ROI 設定頁

目標：讓 ROI 微調 UI 乾淨、可維護，避免 legacy 元件造成維護混亂。

待辦：

1. 刪除舊版 `renderTableCalibration()`，保留 `renderTableCalibrationV2()`。
2. 移除暫時性的 `void` 保留語句。
3. 將 ROI 微調 input 改成更穩定的控制方式：stepper、slider 或「本地編輯後按套用」。
4. 避免每次輸入字元都打 API；可改為 debounce 300ms 或按鈕套用。
5. 將 `table_roi_status` 轉成中文顯示，例如 `hsv`、`hsv_fallback`、`geometry_fallback`、`color_changed`、`custom_color_changed`。

已完成 cleanup：

- 舊四點 polygon ROI mask 已移除。
- `roi_manager.py`、`roi_config.json`、`tests/test_roi_manager.py` 已刪除。
- 舊 `/api/roi/*` 端點已移除。
- 目前只保留 HSV table ROI 與 `/api/table/roi-adjustment` 工作流。

驗證：

```powershell
cd frontend
npx.cmd tsc --noEmit
```

### 第二階段：驗證 ROI 對 planner 與 AI Coach 的實際影響

目標：確認使用者調整 ROI 後，路徑規劃與 AI Coach 都使用同一個調整後的 `table_roi`。

待辦：

1. 檢查三個來源是否一致：
   - `GET /api/table/roi-adjustment` 的 `table_roi`
   - `GET /api/coach/debug-payload` 的 `payload.table_state.runtime_table.table_roi`
   - `GET /api/planner/state` 或 metadata 內的 planner runtime 狀態
2. 在設定頁顯示「AI Coach 使用中的 ROI」或「Planner 使用中的 ROI」。
3. 新增 focused test：模擬 `table_roi_raw`、套用 adjustment、確認 `table_roi` 改變，並確認 holes / hole_bboxes 重新估算。

建議 API 檢查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/table/roi-adjustment
Invoke-RestMethod http://127.0.0.1:8001/api/coach/debug-payload
Invoke-RestMethod http://127.0.0.1:8001/api/planner/state
```

### 第三階段：AR 與 burn-in 實機校驗

目標：確認畫面上的走位圈、下一球、避開區與 JSON 座標一致。

待辦：

1. burn-in 檢查母球預期落點、走位目標圈、下一球標記與避開區。
2. 投影 AR 檢查 `transform_best_route_for_ar()` 是否正確轉換 `route_segments`、`cue_landing_zone`、`position_play.target_zone`、`avoid_zones`。
3. 若半徑偏大或偏小，調整 projector radius 估算法。
4. 新增 debug payload 顯示 camera space 與 projector space 的 `position_play`，方便比對。

### 第四階段：AI Coach 回答品質調整

目標：讓 AI Coach 回答像教練，而不是只轉述 JSON。

待辦：

1. 實測 `這球怎麼打？`、`下一球怎麼走位？`、`這球風險在哪？`、`如果我想保守一點怎麼打？`
2. 檢查回答是否包含目標球、目標袋、力道、桿法、母球走位、下一球目的與風險。
3. 若 AI Coach 發明不存在的袋口、路線或走位，強化 prompt 規則：planner 沒提供時不可補猜。
4. 區分進攻建議、走位建議、防守建議與低信心提醒。

### 第五階段：路徑規劃第二版

目標：讓最佳路線更接近實際玩家會選的路線。

待辦：

1. 調整不同模式的分數權重：
   - practice：進球 60%、走位 40%
   - 9ball：進球 65%、走位 35%
   - safety：防守安全 50%、合法碰球 30%、母球控制 20%
2. 強化 `PositionPlanner`：bank、combo、kick、safety、carom / kiss 風險。
3. 增加風險判斷：母球貼顆星、母球靠袋、下一球被擋、母球穿越球堆、力道過大造成失位。
4. 前端 Top-N 比較新增進球率、走位率、風險、下一球與推薦原因。

### 推薦優先順序

1. 先整理 ROI 設定頁。
2. 加 ROI / planner / coach debug 一致性檢查。
3. 實機校驗 burn-in 與 projector AR。
4. 調整 AI Coach 回答品質。
5. 再進入 RouteScorer 權重與第二版走位模型。

## 05/12:'新增 AI Coach 聊天室持久化功能'

### 範例
- 使用者在 AI Coach 對話中輸入問題或產生建議後，關閉 AI Coach 面板再重新開啟，原本的玩家訊息與 AI Coach 回覆會從瀏覽器 `localStorage` 載回。
- 重新整理前端頁面後，左側對話清單、目前選取的對話與對話訊息會保留。

### 規範用法
- 對話清單儲存在 `ai-coach-sessions-v1`。
- 目前選取對話儲存在 `ai-coach-active-session-v1`。
- 每個對話的訊息儲存在 `ai-coach-chat-messages-v1`，以 session id 分組。
- 每個 session 最多保留最近 200 則訊息，避免瀏覽器儲存空間被長對話佔滿。
- 若 `localStorage` 不可用或資料格式損壞，系統會退回目前頁面記憶體狀態，不阻斷 AI Coach 使用流程。

### 輸出格式
```json
{
  "coach-session-1715490000000": [
    {
      "id": "player-coach-session-1715490000000-1715490001000",
      "role": "player",
      "text": "下一桿怎麼打？",
      "timestamp": "2026-05-12T03:49:00.000Z",
      "kind": "manual"
    }
  ]
}
```
