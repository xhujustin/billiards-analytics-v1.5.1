# AI Coach 後續實作計畫

## 05/07:'ROI 驗證、AR 校準、AI Coach 品質與第二版走位'

### 目前狀態

- `planner.result.v1`、`position_play.v1`、`coach.context.v1` 已完成第一版資料鏈。
- 即時影像頁與練習頁已可顯示下一球、母球預估點、走位目標區與走位成功率。
- burn-in 與投影 AR 已可接收並繪製走位目標區、避開區與下一球標記。
- `RouteScorer` 已把走位分數納入路線排序，第一版權重為原路線分數 70%、走位分數 30%。
- 桌布 ROI 微調已接到前端設定頁、後端 API 與 tracker，實際使用 `table_roi` 會進 planner 與 AI Coach payload。

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
