# 一般練習自動進球偵測規範

## 06/27: '放寬全袋進球消失判定'

### 範例

若任一袋口因鏡頭角度或桌框遮擋，看不到球完整落袋，只要目標球進入進袋接近區後連續消失，即可判定為 `target_ball_potted: true`。

### 規範用法

- 此規則套用六個袋口。
- `missing_confirm_frames` 使用 `2`，降低 YOLO 漏檢造成的成功漏加。
- `pocket_approach_radius` 使用 `hole_radius + 160px`，目前等於約 `212px`。
- `pocket_approach_min_delta` 使用 `0.5px`，只要目標球有往袋口靠近即可累積接近幀。
- 若母球同時被判定進袋，該桿不計成功。

### 輸出格式

```json
{
  "target_ball_potted": true,
  "cue_ball_potted": false,
  "success": true,
  "confirm_frames": 2
}
```

## 06/26: '修正一般練習成功次數偶發漏加'

### 範例

一般練習中，若規劃路線選定 3 號球，3 號球進袋後短暫從 YOLO 結果消失：

```json
{
  "mode": "practice_single",
  "target_ball_number": 3,
  "target_ball_potted": true,
  "cue_ball_potted": false,
  "success": true
}
```

後端應立即把該桿記為成功，並讓 `/api/practice/state` 回傳更新後的 `attempts`、`successes` 與 `success_rate`。

### 規範用法

- 一般練習的成功次數以後端自動偵測為權威來源，前端只輪詢 `/api/practice/state` 顯示統計。
- 目標球追蹤優先使用 planner 的 `target_ball_number` 與上一幀彩球快照。
- 已知目標球號時，不可因附近其他彩球仍在桌上，就把最近球改當成目標球。
- 若目標球在洞口附近或進袋接近區消失，應進入 missing/potted 確認流程；若該幀洞口資料漏檢，仍可以目標球連續消失完成確認。成功條件為子球進袋且母球未進袋。
- 成功後應清除一般練習路線 guide，讓下一桿重新規劃。

### 輸出格式

```json
{
  "attempts": 4,
  "successes": 3,
  "success_rate": 0.75,
  "shot_event": {
    "mode": "practice_single",
    "potted_balls": [3],
    "cue_ball_potted": false,
    "is_foul": false
  }
}
```
