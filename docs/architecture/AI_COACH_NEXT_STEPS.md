# AI Coach 後續實作計畫

## 06/26:'修正擊打後近袋球造成 overlay 延遲更新'

### 規範用法

- 一般練習偵測到一桿開始時，必須立即重置上一桿的 selected route、target lock、stroke override、planner state hash 與 target hold cache。
- 重置上一桿 planner 狀態時不可關閉即時 route planner，也不可關閉 lookahead 設定；下一個穩定偵測幀應直接產生新的 `multi_plan`。
- 近袋球短暫漏檢時，不應因上一桿 selected route 或 target hold 讓 overlay 長時間保留舊線。

### 輸出格式

擊球開始後允許暫時沒有路線；球停穩後必須回到一般 `planner.result.v1`：

```json
{
  "multi_plan": {
    "schema_version": "planner.result.v1",
    "best_route": {"target_ball_number": 2}
  }
}
```

## 06/26:'修正手動切換路徑後投影被 live 路線覆蓋'

### 規範用法

- `/api/planner/select-route` 發布投影資料時，必須將 `ar_source` 標為 `planner_select_route` 並立即切到 `ProjectorMode.PRACTICE`。
- Camera loop 收到 live_yolo 新幀時，若 projector 目前來源是新鮮的 `planner_select_route`，只能更新球位、球桿雷射、桌框與計時器，不可用 live best route 覆蓋剛選的投影線。
- 這個保護只套用在手動切換路徑；擊打結束後的 `practice_shot_result` 與後續 live route 不受影響，仍可自動更新下一桿路線。

### 輸出格式

```json
{
  "ar_source": "planner_select_route",
  "route_segments": [
    {"type": "cue_to_contact", "points": [[120, 300], [360, 420]]}
  ],
  "projector_status": "planner_route"
}
```

## 06/26:'修正練習擊打後路線規劃不中斷'

### 規範用法

- 一般練習模式判定一桿結束且目標球進袋後，只能清除舊路線、選線快取、投影路線與已選目標球，不可關閉 tracker 的即時 route planner。
- `clear_practice_route_guides()` 必須保留 `route_planner_enabled` 與 lookahead 設定，讓下一幀 YOLO 狀態穩定後自動重新產生下一桿 `multi_plan`。
- 清除舊路線時需同步重置 `RoutePlanner.last_plan`、`last_error`、state hash cache 與 held target 狀態，避免下一桿沿用已進袋目標或舊幾何。

### 輸出格式

擊打結束當幀允許暫時清空路線：

```json
{
  "multi_plan": null,
  "planner_error": null,
  "ar_route_segments": []
}
```

下一個穩定偵測幀必須由即時 planner 自動恢復：

```json
{
  "multi_plan": {
    "schema_version": "planner.result.v1",
    "best_route": {"target_ball_number": 2}
  }
}
```

## 06/26:'修正母球撞擊後分離線依切角延伸'

### 規範用法

- `RoutePlanner` 的 `cue_after_contact` 會依母球入射方向、目標球方向、`cue_speed_after` 與切角 tangent retention 估算母球分離落點。
- 近直球且無高桿、低桿、側旋時仍維持停球區，避免滿球中桿被畫成不合理側跑。
- 非直球會用切角比例放大分離行程；薄球分離線必須明顯長於厚球，避免不同角度看起來都只延伸一小段。

### 輸出格式

`metadata.route_segments` 內的 `cue_after_contact` 維持既有格式，前端與投影端不需要改欄位：

```json
{
  "type": "cue_after_contact",
  "points": [[500.0, 300.0], [610.0, 430.0]],
  "color": "cyan"
}
```

### 範例

22 度厚球會產生較短的母球分離線；68 度薄球在相同距離與力道模型下，母球分離距離需明顯更長。測試以 `test_cue_leave_distance_scales_with_cut_angle` 鎖定這個差異。

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

## 06/25:'修正 Practice 2-ply 前端疊圖對齊與自動啟用'

### 規範用法

- 一般練習模式偵測到兩顆以上非母球時，前端會自動啟用「2-ply 走位預判」，並用 lookahead 參數呼叫 `/api/planner/plan`。
- Practice 前端 SVG overlay 的 `viewBox` 必須優先使用 metadata `img_w/img_h`，並依 MJPEG 影像在 `.video-container` 內的實際可見區域設定 `left/top/width/height`，避免 `object-fit: contain` 留黑邊時造成線段放大或偏移。
- `/api/planner/plan`、`/api/planner/stroke` 與 `/api/planner/select-route` 回傳的是 runtime/source frame 座標；Practice 前端把回傳寫入 `plannerPlan` 前，必須依 metadata `source_img_w/source_img_h -> img_w/img_h` 轉成 monitor overlay 座標。不可直接用 REST 原始座標畫在 1280x720 overlay 上，否則 X=1600+ 的袋口或下一手線會整組向右偏移。
- Practice 前端收到 live metadata 時，若球桌 `state_signature` 已改變，必須接受新的 `multi_plan`，不可因舊 plan 有 lookahead、新 plan 暫時缺 lookahead 就保留舊線；若 live metadata 已沒有可用 `multi_plan`，必須清掉前端 `plannerPlan`，避免球拿掉後舊路線殘留。
- `/api/planner/plan` 與 `/api/planner/stroke` 接到 lookahead 參數後，必須同步保存到 tracker runtime 設定，讓後續即時追蹤 `_generate_multi_plan()` 持續輸出同一層級的 2-ply plan；不可只讓單次 REST 回應有 2-ply。
- 後端 `_scale_annotation_packet()` 產生 monitor metadata 時，必須同步縮放 `RouteCandidate.metadata.lookahead.state.cue_ball_center`、`lookahead.next_routes[*].route_segments`、`cue_landing_point`、`cue_landing_zone` 與 `cue_target_zone`；不可只縮放主層 `best_route`，否則 Practice 前端 1280x720 overlay 會把 2-ply 下一手畫到右側偏移位置。
- 2-ply `lookahead.next_routes[0].route_segments` 在 Practice overlay 需沿用既有 `practice-route-segment cue/object/cue-after/combo` 分段樣式，不另外改成紫色虛線，避免與原本路線視覺風格不一致。
- `StateExtractor._build_pockets()` 的中袋 mouth 必須使用偵測到的袋口 X 座標投影到上下顆星邊，不可硬使用 `table_roi` 幾何中心；否則實機視角或暗區偵測偏移時，中袋路線會明顯歪掉。角袋仍以 ROI 邊界建立入口，避免黑洞中心把進球線拉到袋內。
- `LookaheadPlanner` 展開 2-ply 前必須驗證第一杆模擬後的母球狀態：已進目標球、母球落點沒有重疊剩餘子球、也沒有落在袋口風險區。無效時 `metadata.lookahead.status` 回傳 `invalid_cue_state`、`next_routes` 為空，並在 `warnings` 標出原因，例如 `lookahead_skipped_cue_landing_overlaps_ball_2`。
- Practice overlay 不顯示 2-ply 的紫色 `cue_target_zone` 或 `cue_landing_point` 十字標記；2-ply 只畫下一杆 `route_segments`，避免額外輔助圈被誤認為球或目標點。
- `CandidateGenerator` 的 `cue_after_contact` 可包含母球碰庫反彈點。當簡化母球走位端點超出 `table_roi` 時，先求與顆星邊界的交點，再依剩餘距離反射最多兩庫；輸出仍是原本的 `route_segments[*].points` 折線，不新增 schema。
- `/api/planner/plan` 與 `/api/planner/stroke` 在當幀偵測不足但已有有效 `multi_plan` 時，回傳上一筆有效路線並標記 `rest_hold_reason`，不可直接回 `Insufficient state for route planning` 造成 Practice UI 閃錯。metadata 需同步帶 `planner_error`，前端自動開 2-ply 時若遇到 `DETECTION_TEMPORARILY_MISSING`、`INSUFFICIENT_STATE_HELD` 或 `NO_ANALYSIS_DATA_HELD`，要等下一幀穩定後再重算。

### 範例

```json
{
  "metadata": {
    "img_w": 1280,
    "img_h": 720,
    "multi_plan": {
      "best_route": {
        "metadata": {
          "lookahead": {
            "enabled": true,
            "next_routes": [
              {
                "target_ball_number": 2,
                "route_segments": [
                  {"type": "cue_to_contact", "points": [[720, 420], [840, 300]]},
                  {"type": "object_to_pocket", "points": [[840, 300], [1120, 120]]}
                ]
              }
            ]
          }
        }
      }
    }
  }
}
```

## 06/25:'修正 2-ply 白球後續線穿過未建模球'

### 範例
- 若 1 號球進袋後，母球預估離開線會直接撞到 2 號球，系統不再把這段當成可用走位。
- 畫面上的 `cue_after_contact` 會截在碰撞前的安全距離，避免顯示母球穿過或壓到下一顆球的錯誤路線。

### 規範用法
- `candidate_generator` 產生母球後續路徑後，必須檢查所有未忽略物件球。
- 若路徑會碰到未建模的其他球，加入 `risk_flags`: `cue_leave_hits_object_ball` 與 `cue_leave_blocked_by_ball_{number}`。
- `lookahead_planner` 遇到 `cue_leave_hits_object_ball` 必須回傳 `invalid_cue_state`，不得從該落點繼續產生 2-ply。

### 輸出格式
```json
{
  "risk_flags": ["cue_leave_hits_object_ball", "cue_leave_blocked_by_ball_2"],
  "metadata": {
    "lookahead": {
      "status": "invalid_cue_state",
      "warnings": ["lookahead_skipped_cue_leave_hits_object_ball"]
    }
  }
}
```

## 06/26:'修正 Practice 落點圈與路線終點不一致'

### 範例
- Practice overlay 顯示母球後續線時，青色落點圈必須落在 `cue_after_contact` 線段最後一點。
- 若 route 同時含有 `position_play.cue_ball_after_contact.target_zone`，該 target zone 只代表理想走位區，不可當作實際母球落點圈。

### 規範用法
- 前端顯示「預計落點」、「母球預估」與 Top-N 落點時，優先使用 `route_segments[type=cue_after_contact]` 的最後一個座標。
- 若 route 沒有 `cue_after_contact`，才退回 `cue_landing_point`。
- Practice overlay 不用 `cue_target_zone` 或 `position_play.target_zone` 畫落點圈，避免圈和實際線段端點分離。

### 輸出格式
```json
{
  "route_segments": [
    {"type": "cue_after_contact", "points": [[620, 430], [580, 445]]}
  ],
  "cue_landing_point": [580, 445]
}
```

## 06/26:'修正投影路線不會跟隨 overlay 自動更新'

### 範例
- 手動啟動 planner 或選線後，若 live tracker 已產生新的 `ar_route_segments`，投影必須立即改用新路線，不可因 `PROJECTOR_MANUAL_ROUTE_HOLD_MS` 保留舊投影。
- 若 live tracker 暫時沒有路線，才允許保留上一筆手動投影，避免投影閃空。

### 規範用法
- `_projector_should_hold_manual_route()` 只能阻止空 live 結果清掉手動 route；不能阻止新的 live route 覆蓋舊 route。
- `/api/planner/plan`、`/api/planner/stroke` 與 `/api/planner/select-route` 必須同步呼叫 `set_route_planner_runtime(True, "practice")` 或對應 rule profile，讓 tracker 後續每幀重新產生 `multi_plan` 與 `ar_route_segments`。
- Projector renderer 的落點圈必須跟 `route_segments[type=cue_after_contact]` 最後一點一致。
- Projector renderer 不再額外投影 `position_play.target_zone` 或 2-ply landing/target marker；2-ply 只投影分段路線，避免和 Practice overlay 視覺語意不同。

### 輸出格式
```json
{
  "ar_source": "live_yolo",
  "route_segments": [
    {"type": "cue_after_contact", "points": [[420, 520], [380, 610]]}
  ],
  "projector_status": "planner_route"
}
```

### 輸出格式

- 不新增 API 欄位；仍沿用 `planner.result.v1` 與 `planner.lookahead.v1`。
- 前端 overlay 尺寸由 `metadata.img_w/img_h` 與影像 DOM 實際顯示區共同決定；REST plannerPlan 寫入前需用 `source_img_w/source_img_h` 做座標正規化。
- monitor metadata 的 `multi_plan.best_route.metadata.lookahead.next_routes` 座標必須和 `multi_plan.best_route.route_segments` 使用同一個縮放後座標系。
- 2-ply 線條 class 格式為 `practice-route-segment {segmentClass} practice-lookahead-route-segment`，其中 `{segmentClass}` 依 segment type 對應 `cue`、`object`、`cue-after` 或 `combo`。

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
