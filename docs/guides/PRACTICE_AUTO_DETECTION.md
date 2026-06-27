# 一般練習自動進球偵測規範

## 06/27: '修正進袋後仍被 YOLO 框住時成功次數漏加'

### 範例

一般練習中，目標球已往袋口移動並進入袋口捕捉區，但 YOLO 仍短暫把袋口陰影或半顆球辨識成同一顆球：

```json
{
  "target_pocket_approach_frames": 1,
  "target_in_hole_frames": 2,
  "target_ball_potted": true,
  "success": true
}
```

### 規範用法

- 目標球若已累積 `target_pocket_approach_frames >= 1`，且連續進入袋口捕捉區，應視為進球候選。
- 袋口捕捉區使用 `hole_radius + max(8px, ball_radius * 0.8)`，用於處理進袋後 YOLO 尚未立即讓球消失的情境。
- 捕捉區連續確認使用 `2` 幀，與既有 `in_hole_confirm_frames` 保持一致。
- 成功條件仍為 `target_ball_potted == true` 且 `cue_ball_potted == false`。

### 輸出格式

```json
{
  "attempts": 5,
  "successes": 4,
  "success_rate": 0.8
}
```

## 06/27: '修正練習統計 API 來源'

### 範例

桌面前端若透過 LAN 或 Cloudflare 遠端網址連線，手動點擊「成功」後應呼叫同一個後端來源：

```ts
fetch(`${backendUrl}/api/practice/record`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ success: true })
});
```

### 規範用法

- 練習頁所有會影響統計流程的 API 必須使用 `backendUrl`，不可混用相對 `/api/...`。
- 適用範圍包含 `/api/practice/state`、`/api/practice/record`、`/api/practice/end`、`/api/practice/guides` 與 `/api/recording/stop`。
- 手動成功或失敗記錄成功後，前端必須以後端回傳的 `attempts`、`successes`、`success_rate` 更新畫面。
- 自動偵測仍以 `/api/practice/state` 輪詢結果為權威來源。

### 輸出格式

```json
{
  "attempts": 2,
  "successes": 1,
  "success_rate": 0.5
}
```

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
