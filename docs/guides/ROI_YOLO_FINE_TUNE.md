# ROI YOLO 四點微調規則

## 05/26: '新增 ROI 已有 YOLO 框的四點微調規則'

### 功能說明
- 進入 `設定 > 球桌校正 > ROI 邊框微調` 時，若後端已有手動四點，前端優先載入手動四點。
- 若沒有手動四點但 YOLO/HSV 已產生 `table_roi`，前端會把矩形 ROI 轉成四個頂點並直接進入微調模式。
- 已有 YOLO/手動框選時，點擊預覽圖不會新增標點；使用者只能點選既有頂點，或按 `1/2/3/4` 與方向鍵微調。
- 使用者按「重設框選」後，前端會呼叫 `POST /api/table/roi-polygon/reset`，清除原本框選並進入重新標四點模式。

### API 範例
重設 ROI 四點：

```http
POST /api/table/roi-polygon/reset
```

成功回應：

```json
{
  "status": "success",
  "points": null,
  "table_roi": null,
  "table_roi_status": "polygon_reset"
}
```

儲存重新標定的四點：

```http
POST /api/table/roi-polygon
Content-Type: application/json

{
  "points": [
    { "x": 57, "y": 20 },
    { "x": 1142, "y": 20 },
    { "x": 1142, "y": 546 },
    { "x": 57, "y": 546 }
  ]
}
```

### 規範用法
- `table_roi` 的矩形格式仍為 `[x, y, w, h]`。
- 前端只在進入 ROI 編輯器時，將矩形格式轉成四點草稿，不改變後端輸出格式。
- 只有「重設框選」會清除原本 YOLO/手動框選；一般點擊預覽圖只在重設後的標點模式生效。
