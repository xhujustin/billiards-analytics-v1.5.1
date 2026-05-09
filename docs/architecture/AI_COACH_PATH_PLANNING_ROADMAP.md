# AI Coach 路徑規劃與走位擴充 Roadmap

## 05/07:'保留 AI Coach 路徑規劃擴充待辦'

### 目標

將現有多球路徑規劃器擴充成「路徑規劃 + 走位建議 + AI Coach 解說」架構。後端負責可驗證的規則、幾何、物理與路線評分；AI Coach 只透過 WebSocket/HTTP 接收結構化結果，負責轉成教練語言、戰術解釋與問答。

### 現有能力

- `backend/tracking/planner` 已有完整路徑規劃模組，包含狀態抽取、候選路線生成、物理檢查、路線計分與桿法建議。
- `RouteCandidate` 已輸出 `route_type`、`target_ball_number`、`score`、`difficulty`、`success_prob`、`cut_angle`、`path_points`、`route_segments`、`cue_landing_point`、`cue_landing_zone`、`stroke_hint`、`risk_flags`、`metadata`。
- `RoutePlanner` 已支援 practice 與 9ball 規則、最低號球合法目標、direct/cut/bank/combo/kick/safe escape/contact only、多路線排序、fallback 與 hysteresis。
- `CandidateGenerator` 已估算 ghost ball、母球碰撞後路線、進球線、bank/kick/combo 幾何、cue landing point、cue landing zone 與 P2 physics metadata。
- `RouteScorer` 已依角度、距離、碰撞、袋口速度、rail error、line tolerance、合法第一碰球等因素輸出分數與風險旗標。
- `main.py` 已把 `multi_plan` 放進 metadata WebSocket、`planner.update`、`/api/planner/*` 回應與 AI Coach context。

### 缺口

- `multi_plan` 尚未明確標示 schema version，前端與 AI Coach 目前只能依既有欄位推斷格式。
- 已有 `cue_landing_point`，但尚未提升成完整 `position_play`：缺下一顆球、理想母球落區、避開區、速度/桿法理由與保守策略。
- AI Coach context 目前直接塞 `multi_plan`，缺少統一的 `CoachPayloadBuilder` 將 planner result、semantic context、raw detections 包成穩定 schema。
- route/stroke 的文字說明有部分亂碼，需要改成可讀繁中，否則不適合作為 AI Coach 提示來源。
- front-end/AR 目前主要畫 best route segment，還沒有走位區、下一顆球目標區、風險區與候選路線比較 UI。

### 建議資料格式

`planner.result.v1`：

```json
{
  "schema_version": "planner.result.v1",
  "rule_profile": "9ball",
  "rule_state": {
    "remaining_ball_numbers": [1, 2, 3],
    "legal_target_ball_number": 1,
    "first_contact_required": true
  },
  "best_route": {
    "id": "route-1",
    "route_type": "cut",
    "target_ball_number": 1,
    "success_prob": 0.71,
    "difficulty_level": "medium",
    "route_segments": [],
    "stroke_hint": {},
    "position_play": {},
    "risk_flags": []
  },
  "routes": [],
  "coach_notes": [],
  "error": null
}
```

`position_play.v1`：

```json
{
  "schema_version": "position_play.v1",
  "next_ball": {
    "number": 2,
    "center": [890.0, 300.0],
    "preferred_pocket_id": "pocket-2"
  },
  "cue_ball_after_contact": {
    "expected_point": [705.0, 360.0],
    "target_zone": {
      "center": [720.0, 350.0],
      "radius": 48.0,
      "label": "下一球進攻角度區"
    },
    "avoid_zones": []
  },
  "stroke_advice": {
    "speed": "medium",
    "english": "center",
    "cue_tip": {"x": 0.0, "y": 0.0},
    "reason": "控制母球停在下一顆球可進攻角度。"
  },
  "score": {
    "position_success_prob": 0.62,
    "shape_quality": 0.7,
    "risk": 0.24
  }
}
```

`coach.context.v1`：

```json
{
  "schema_version": "coach.context.v1",
  "request": {
    "type": "chat",
    "message": "這球怎麼打比較好？"
  },
  "table_state": {},
  "semantic_context": {},
  "planner": {
    "result": {},
    "best_route": {},
    "position_play": {}
  },
  "debug": {
    "raw_detections": [],
    "signature": "sha256"
  }
}
```

### Task List

1. 已完成：在 `MultiRoutePlan.to_dict()` 補 `schema_version: planner.result.v1`。
2. 已完成：新增 `PositionPlanner`，輸入 `PlannerState`、`RouteCandidate`、rule state，輸出 `position_play.v1`。
3. 已完成：在 `RouteCandidate` 新增 `position_play` 欄位，並由 `RoutePlanner` 注入。
4. 已完成：在 `RouteScorer` 加入走位分數，避免只選進球率高但母球失位的路線。
5. 已完成：新增 `CoachPayloadBuilder`，讓 `/api/coach/chat`、`/api/coach/suggest`、auto analysis 共用 `coach.context.v1`。
6. 已完成：新增 `/api/coach/debug-payload`，方便檢查 main 實際送給 AI Coach 的資料。
7. 部分完成：AI Coach prompt 已支援 `coach.context.v1` 與繁中固定回答格式；planner 內既有亂碼文字仍需後續整理。
8. 已完成第一版：前端 planner 面板、burn-in 與投影 AR 顯示 `position_play.target_zone`、下一顆球、避開區與候選路線走位分數。
9. 已完成：補測試 schema version、position_play、9ball 下一顆球、手動桿法影響走位、coach payload 結構。
10. 待辦：第二階段再強化 bank/combo/carom/safety 的走位模型。

### 推薦實作順序

1. 先做 schema version 與 `CoachPayloadBuilder`，把資料邊界固定。
2. 再做 `PositionPlanner` 的第一版：只處理 direct/cut 進球路線與九號球下一顆。
3. 接著把 `position_play` 納入 scoring，讓最佳路線開始考慮走位。
4. 最後擴充 front-end/AR 顯示與 AI Coach 解說。
