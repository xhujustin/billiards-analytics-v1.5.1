# 調試指南 - 啟動辨識無反應問題

## 問題描述

按下「啟動辨識」按鈕後，即時影像沒有顯示檢測框和球號標註。

## 診斷步驟

### 步驟 1: 啟動後端並觀察日誌

```bash
cd backend
python main.py
```

**預期輸出**:
```
✅ YOLO model loaded successfully from ...
✅ Calibrator initialized successfully
✅ MJPEG Stream Manager initialized
🚀 Starting camera capture thread for burn-in stream...
🎥 Starting camera capture loop for burn-in stream...
✅ Camera opened successfully...
```

### 步驟 2: 檢查攝影機是否正常

觀察後端日誌，確認沒有以下錯誤：
- ❌ Failed to open camera
- ⚠️ Failed to read frame

如果有攝影機錯誤，檢查：
1. 攝影機是否被其他程式佔用
2. backend/config.py 中的攝影機設定
3. 嘗試切換攝影機設備 ID (0, 1, 2...)

### 步驟 3: 啟動前端

```bash
cd frontend
npm run dev
```

訪問 `http://localhost:5173`

### 步驟 4: 檢查 WebSocket 連接

在前端頁面中，確認：
- WebSocket 狀態顯示「🟢 已連接」
- Burn-in 影像正常顯示

### 步驟 5: 點擊「啟動辨識」並觀察後端日誌

**預期輸出**:
```
🎛️  YOLO Analysis toggled: True
   Tracker available: True
🔍 [Frame XXX] Running YOLO detection...
✅ [Frame XXX] YOLO complete - Status: analyzing
```

如果看不到這些日誌，說明：
1. API 請求沒有到達後端
2. 前端和後端沒有正確連接

### 步驟 6: 檢查球桌檢測

如果看到：
```
⚠️  Table not detected, scanning...
```

說明系統無法檢測到球桌（綠色區域）。解決方案：
1. 確認攝影機畫面中有綠色撞球桌
2. 調整 `backend/config.py` 中的 HSV 閾值：
   ```python
   HSV_LOWER = [35, 40, 40]   # 降低飽和度和亮度
   HSV_UPPER = [85, 255, 255]
   ```
3. 確認 `TABLE_MIN_AREA` 設定合適

如果看到：
```
✅ Table detected: x=..., y=..., w=..., h=...
```

說明球桌檢測成功！

### 步驟 7: 檢查 YOLO 檢測結果

觀察後端日誌中的：
```
✅ [Frame XXX] YOLO complete - Status: analyzing
```

然後在前端的 Metadata 頁面檢查：
- 檢測數量是否 > 0
- detections 陣列是否有資料

## 常見問題

### 05/09: 新增 IDE 診斷降噪設定

本專案後端大量使用 OpenCV、NumPy、FastAPI 全域共享狀態與執行期注入物件，Pylance/Pyright 在嚴格型別模式下容易產生大量 Optional、operator、OpenCV overload 類假陽性，導致 IDE issues 數量失真。

已新增根目錄 `pyrightconfig.json` 與 `.vscode/settings.json` 的 `python.analysis` 設定：

```json
{
  "typeCheckingMode": "basic",
  "extraPaths": ["backend"],
  "reportMissingImports": "none",
  "reportArgumentType": "none",
  "reportOptionalMemberAccess": "none"
}
```

規範用法：
- VS Code 需以專案根目錄開啟，讓 Pylance 讀取 `pyrightconfig.json`。
- 後端跨模組 import 以 `backend` 作為分析路徑，不需在每個檔案改寫 import。
- OpenCV/NumPy 相關型別假陽性由專案設定處理；真實執行檢查仍以啟動後端、API 測試與前端 build 為準。
- 本機未安裝完整 Python 依賴時，第三方套件 import 解析不作為 IDE issue 顯示；依賴完整性以實際後端環境啟動驗證。
- Pyrefly 若回報 `missing-attribute`、`bad-assignment`、`bad-argument-type`，優先用明確 None guard、`setattr()`、`getattr()` 動態屬性包裝與 API body 型別驗證修正；不要只為了消除診斷移除執行期必要的防護。

輸出格式：
- `npx pyright backend --outputjson` 應回傳 `summary.errorCount` 為 `0`。
- 前端檢查使用 `npm run build`，成功時 Vite 輸出 `built`。

### 05/09: 新增 Pyrefly 專案設定

若在 `C:\Users\xhuju` 執行 `pyrefly init`，Pyrefly 會建立家目錄層級設定並掃描整個使用者資料夾，可能出現：

```text
WARN Pyrefly is checking everything under `C:\Users\xhuju`.
ERROR Failed to run pyrefly check: When resolving pattern `C:\Users\xhuju\**\*.py*`
```

規範用法：
- 請在專案根目錄執行：`cd C:\Users\xhuju\Desktop\billiards-analytics-v1.5`
- 使用專案根目錄的 `pyrefly.toml` 執行：`pyrefly check`
- 若要從其他目錄執行，明確指定設定：`pyrefly check --config C:\Users\xhuju\Desktop\billiards-analytics-v1.5\pyrefly.toml`
- `C:\Users\xhuju\pyrefly.toml` 是家目錄設定，不應作為本專案檢查入口。

本專案 `pyrefly.toml` 限制掃描：

```toml
project-includes = ["backend/**/*.py", "ai_coach/**/*.py"]
search-path = ["backend", "ai_coach/src"]
python-version = "3.11"
python-platform = "windows"
skip-interpreter-query = true

[errors]
deprecated = false
unnecessary-type-conversion = false
```

輸出格式：
- `pyrefly check --count-errors=0 --summarize-errors=0` 會顯示錯誤種類與目錄分佈。
- 若本機 Python/第三方依賴尚未完整安裝，OpenCV、YOLO、Torch 等動態邊界由 `replace-imports-with-any` 與 `ignore-missing-imports` 降噪。
- `unnecessary-type-conversion` 屬於本專案低訊號 warning；`tracking_engine.py` 內的 `int()`、`float()`、`bool()` 多數用於 OpenCV/NumPy 與外部輸入邊界正規化，不應為消除 IDE warning 大量移除。

### 05/09: 修正 tracking_engine.py Pyrefly 診斷

`backend/tracking/tracking_engine.py` 已針對 Pyrefly 單檔掃描修正型別診斷，重點是保留執行期行為並補足靜態分析需要的型別窄化。

規範用法：
- 球桿軸線資料使用 `CueAxis = List[List[float]]`，因第三段方向向量是浮點單位向量，不應標成純整數點位。
- 讀取 `dict.get()` 後若要迭代或做浮點轉換，先存成區域變數並以 `isinstance(..., list)` 或 `value is None` 窄化。
- 瞄準輔助與袋口方向計算需在 `best_hole_dir` 為空時提前返回，避免型別檢查與執行期都可能踩到 `None`。
- `_find_line()` 目前會用 x 偏移避免除零，因此回傳型別為 `Tuple[float, float]`。

驗證範例：
```powershell
C:\tmp\pyrefly-extracted-0641\pyrefly-0.64.1.data\scripts\pyrefly.exe check backend\tracking\tracking_engine.py --config pyrefly.toml
npx pyright backend\tracking\tracking_engine.py --outputjson
```

輸出格式：
- Pyrefly JSON 的 `errors` 應為空陣列。
- Pyright JSON 的 `summary.errorCount` 與 `summary.warningCount` 應為 `0`。

### 05/09: 修正整專案 Pyrefly 診斷

已完成整個專案 Pyrefly 掃描修正，涵蓋後端 API、投影渲染、追蹤規劃、錄影資料庫、vLLM client、測試腳本與 `ai_coach` 工具鏈。

規範用法：
- 全域注入狀態如 `camera_state`、`calibration_state` 需透過 helper 先確認非 `None`，再進行 `.get()` 或索引賦值。
- 外部動態套件、模型、tokenizer、WebSocket 連線物件需在呼叫前使用區域變數與 `None` guard 完成窄化。
- 測試程式若資料庫方法回傳 `Optional[int]` 或 `Optional[dict]`，先 `assert value is not None` 再比較或索引。
- 路線規劃與球桿軸線的 tuple/list 回傳值需用 overload、明確型別別名或 helper 窄化，不依賴隱含推斷。

驗證範例：
```powershell
C:\tmp\pyrefly-extracted-0641\pyrefly-0.64.1.data\scripts\pyrefly.exe check --config pyrefly.toml
npx pyright backend ai_coach --outputjson
```

輸出格式：
- Pyrefly 整專案 JSON 的 `errors` 應為空陣列。
- Pyright `summary.filesAnalyzed` 應涵蓋後端與 `ai_coach`，且 `errorCount`、`warningCount` 均為 `0`。

### 05/09: 修正 YOLO 小球漏檢回歸

合併分支後若桌面仍有多顆球但畫面只標出少數球，優先檢查 `backend/config.py` 的 `CONF_THR`。小球偵測需要較低第一階段信心門檻，過高的 `CONF_THR=0.60` 會讓低信心但正確的球框在後處理前被 YOLO 直接丟棄。

規範用法：
- `CONF_THR` 預設維持 `0.08`，保留小球召回率。
- 若畫面假陽性過多，優先調整後處理過濾、袋口誤檢過濾或顏色分類，不要直接把第一階段 `CONF_THR` 拉到高門檻。
- 現場臨時測試可用環境變數覆蓋，例如 `CONF_THR=0.12`，但不應提交高於小目標召回需求的預設值。

驗證範例：
```powershell
C:\tmp\pyrefly-extracted-0641\pyrefly-0.64.1.data\scripts\pyrefly.exe check backend\config.py --config pyrefly.toml
npx pyright backend\config.py --outputjson
```

輸出格式：
- Pyrefly 與 Pyright 需為 0 errors。
- 啟動辨識後，桌面可見球應出現在 metadata `balls` 或 `white_ball`，不應只剩少數高信心球。

### 問題 1: 沒有看到 YOLO 檢測日誌

**可能原因**:
- `system_state["is_analyzing"]` 沒有正確切換
- `tracker` 為 None

**檢查方法**:
使用瀏覽器開發者工具檢查 API 請求：
1. 打開 F12 → Network
2. 點擊「啟動辨識」
3. 檢查 `/api/control/toggle` 請求
4. 確認 Response: `{"status": "success", "is_analyzing": true}`

### 問題 2: 球桌一直檢測不到

**可能原因**:
- 攝影機畫面中沒有綠色區域
- HSV 閾值設定不正確

**解決方案**:
1. 使用測試影片代替攝影機：
   ```python
   # backend/config.py
   VIDEO_SOURCE = "path/to/test_video.mp4"
   ```

2. 調整 HSV 閾值（降低標準）：
   ```python
   HSV_LOWER = [30, 30, 30]  # 更寬容
   HSV_UPPER = [90, 255, 255]
   ```

### 問題 3: 球桌檢測成功，但沒有球

**可能原因**:
- YOLO 模型信心度閾值太高
- 畫面中確實沒有球

**解決方案**:
1. 降低信心度閾值：
   ```python
   # backend/config.py
   CONF_THR = 0.25  # 從 0.35 降低到 0.25
   ```

2. 確認 YOLO 模型正確載入：
   ```
   ✅ YOLO model loaded successfully from ...
   ```

### 問題 4: 有球檢測，但沒有標註

**可能原因**:
- `_draw_annotations()` 函數沒有執行
- MJPEG 串流沒有更新

**檢查**:
在 tracking_engine.py 的 `_draw_annotations()` 開頭添加：
```python
def _draw_annotations(self, img: np.ndarray, data: Dict[str, Any]):
    print(f"🎨 Drawing annotations - Balls: {len(data.get('balls', []))}")
    ...
```

## 調試輔助工具

### 1. 測試 tracking_engine.py

```bash
cd backend
python test_tracking.py
```

這會測試：
- PoolTracker 初始化
- 球桌檢測
- YOLO 推論
- HSV 顏色檢測

### 2. 直接測試 API

```bash
# 測試 toggle API
curl -X POST http://localhost:8001/api/control/toggle

# 檢查 health
curl http://localhost:8001/health
```

### 3. 檢查 MJPEG 串流

在瀏覽器直接訪問：
```
http://localhost:8001/burnin/camera1.mjpg
```

應該能看到即時影像。

## 預期行為總結

| 步驟 | 操作 | 預期結果 |
|------|------|----------|
| 1 | 啟動後端 | 攝影機成功開啟，MJPEG 串流啟動 |
| 2 | 訪問前端 | Burn-in 影像顯示原始攝影機畫面 |
| 3 | 點擊「啟動辨識」 | 後端日誌顯示 "YOLO Analysis toggled: True" |
| 4 | 第一次檢測 | 後端檢測球桌並輸出 "Table detected" |
| 5 | 持續檢測 | 每幀輸出 "Running YOLO detection..." |
| 6 | 前端顯示 | 影像切換為標註後的畫面（球號、顏色、路徑） |
| 7 | Metadata 頁面 | 顯示 detections 陣列和球的詳細資訊 |

## 常見警告訊息（可忽略）

### POST /api/sessions/.../renew 404 (Not Found)

**現象**:
```
POST http://localhost:8001/api/sessions/s-c1e099b08a12/renew 404 (Not Found)
```

**原因**:
- 前端 SDK 嘗試續期一個已過期或不存在的 session
- Session 預設有效期為 3600 秒（1小時）
- 頁面長時間開啟或重新整理後，舊 session 已被清除

**影響**:
- ✅ **無影響** - 前端會自動創建新 session
- 系統會繼續正常運作

**解決方案**:
1. **不需要處理** - 這是正常行為
2. 如果想減少這類訊息，可以延長 session 有效期：
   ```python
   # backend/config.py
   SESSION_TTL = 7200  # 改為 2 小時
   ```

### 多次切換畫質導致黑屏

**現象**:
- 快速切換「低」、「中」、「高」畫質
- 特別是第 6 次切換時畫面黑屏

**原因**:
- 每次切換會創建新的 MJPEG HTTP 連接
- 瀏覽器對每個域名有並發連接數限制（通常是 6 個）
- 舊連接未正確關閉，累積到第 6 個時達到上限
- 新連接無法建立，導致黑屏

**已修復**: ✅
- 在切換畫質前強制中斷當前 HTTP 連接（設置 `img.src = ''`）
- 添加 100ms 延遲確保舊連接完全關閉
- 實現防抖動機制，防止狀態衝突
- 5 秒超時自動恢復
- 顯示載入提示和視覺反饋

**技術細節**:
```typescript
// 關鍵修復：強制中斷當前連接
if (imgRef) {
  imgRef.src = ''; // 立即中斷 HTTP 連接
}

// 延遲載入新串流，確保舊連接已關閉
setTimeout(() => {
  setStreamKey(prev => prev + 1);
}, 100);
```

**使用建議**:
- 現在可以隨意切換畫質，不會再有黑屏問題
- 每次切換約需 0.5-1 秒載入時間（屬於正常）

## 如果問題仍然存在

請提供以下資訊：

1. **後端啟動日誌**（前 20 行）
2. **點擊「啟動辨識」後的日誌**（完整輸出）
3. **前端 Console 錯誤**（F12 → Console）
4. **Network 請求狀態**（F12 → Network → /api/control/toggle）
5. **攝影機畫面描述**（是否有綠色球桌？是否有球？）

## 05/09: 開發者工具顯示完整 YOLO metadata

### 功能位置

- 設定 > 一般 > 開發者工具：開啟「顯示進階數據監控」
- 即時影像頁：影像上會疊加 YOLO bbox 與信心率，系統狀態下方會列出 bbox 表格與完整 JSON

### 輸出格式

完整資訊來源為前端 WebSocket `metadata.update` payload，包含：

- `frame_id`, `ts_backend`, `img_w`, `img_h`
- `tracking_state`, `detected_count`, `rate_hz`
- 影像疊圖：每個 `detections[]` 的 bbox 與 `conf` / `score`
- bbox 表格：`label`, `conf`, `x`, `y`, `w`, `h`
- JSON：`detections[]` 的球座標、半徑、信心分數、顏色與球號欄位
- `detections_view[]`：後端依照監控串流 `1280x720` 同步縮放後的 bbox，前端疊圖優先使用此欄位
- `multi_plan`, `prediction`, `ar_paths`, `events` 等後端附加資料

疊圖尺寸會優先使用 metadata `img_w/img_h`；若後端未提供，前端會改用 MJPEG 影像的 `naturalWidth/naturalHeight` 對齊 bbox。
後端 `detections[]` 的 `x/y` 為 YOLO 任務提交當下整張處理後 frame 的 bbox 左上角，`w/h` 為 bbox 寬高。即時影像監控流固定輸出 `1280x720`，metadata 需以 data packet 內 `_source_img_w/_source_img_h` 的實際 frame 尺寸縮放出 `detections_view[]`；不可用 `config.CAMERA_WIDTH/HEIGHT` 或 `table_roi` 猜測尺寸，否則 bbox 會被重複縮放或放大偏移。

### 範例

```json
{
  "frame_id": 1204,
  "tracking_state": "active",
  "detected_count": 8,
  "detections": [
    {
      "x": 475,
      "y": 409,
      "radius": 15,
      "w": 30,
      "h": 30,
      "conf": 0.86,
      "color": "yellow",
      "number": 1
    }
  ],
  "rate_hz": 14.7
}
```

---

**最後更新**: 2026-01-05
**相關文件**:
- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md)
- [QUICK_START.md](QUICK_START.md)
- [YOLO_CONTROL_UI.md](YOLO_CONTROL_UI.md)
- [TABLE_DETECTION_FIX.md](TABLE_DETECTION_FIX.md) - 球桌檢測修復
- [QUALITY_CONTROL_FIX.md](QUALITY_CONTROL_FIX.md) - 畫質控制修復
- [BLACK_SCREEN_FIX.md](BLACK_SCREEN_FIX.md) - 黑屏問題修復（瀏覽器連接數限制）
- [HOW_TO_ADJUST_QUALITY.md](HOW_TO_ADJUST_QUALITY.md) - 畫質調整使用說明
