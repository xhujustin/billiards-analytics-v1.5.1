# 投影機自動校正 API 文檔

## API 概覽

投影機自動校正功能提供一套 REST API,用於控制棋盤格投射、檢測和校準計算。

**Base URL**: `http://localhost:8001`

---

## API 端點

### 1. 開始校正

**端點**: `POST /api/calibration/start`

**描述**: 啟動校正流程,初始化校正狀態

**請求**:
```http
POST /api/calibration/start
Content-Type: application/json
```

**回應**:
```json
{
  "status": "ok",
  "message": "校正已啟動"
}
```

**狀態碼**:
- `200`: 成功
- `500`: 伺服器錯誤

---

### 2. 移動棋盤格

**端點**: `POST /api/calibration/move-checkerboard`

**描述**: 控制投影機棋盤格的位置

**請求**:
```http
POST /api/calibration/move-checkerboard
Content-Type: application/json

{
  "direction": "up",
  "step": 20
}
```

**參數**:
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `direction` | string | 是 | 移動方向: `up`, `down`, `left`, `right` |
| `step` | integer | 否 | 移動步長(像素),預設 20 |

**回應**:
```json
{
  "status": "ok",
  "offset_x": 40,
  "offset_y": -20
}
```

**狀態碼**:
- `200`: 成功
- `400`: 無效的方向參數

---

### 3. 檢測棋盤格

**端點**: `GET /api/calibration/detect`

**描述**: 自動檢測相機畫面中的棋盤格並返回四角座標

**請求**:
```http
GET /api/calibration/detect
```

**回應 (檢測成功)**:
```json
{
  "detected": true,
  "corners": [
    [100, 200],
    [900, 200],
    [900, 800],
    [100, 800]
  ],
  "message": "棋盤格檢測成功"
}
```

**回應 (檢測失敗)**:
```json
{
  "detected": false,
  "message": "未檢測到棋盤格,請調整投影位置"
}
```

**狀態碼**:
- `200`: 請求成功 (檢測結果在 `detected` 欄位)
- `500`: 相機錯誤

---

### 4. 獲取預覽畫面

**端點**: `GET /api/calibration/preview`

**描述**: 獲取帶有檢測疊加的相機預覽畫面 (綠色框線 + 白色填充)

**請求**:
```http
GET /api/calibration/preview
```

**回應**:
- Content-Type: `image/jpeg`
- 返回 JPEG 圖像數據

**狀態碼**:
- `200`: 成功
- `500`: 相機錯誤

**使用範例**:
```html
<img src="http://localhost:8001/api/calibration/preview" />
```

---

### 5. 確認校正

**端點**: `POST /api/calibration/confirm`

**描述**: 確認校正並計算 homography_matrix 和 projection_bounds

**請求**:
```http
POST /api/calibration/confirm
Content-Type: application/json
```

**回應**:
```json
{
  "status": "ok",
  "message": "校正完成",
  "bounds": {
    "x": 560,
    "y": 140,
    "width": 800,
    "height": 800
  }
}
```

**狀態碼**:
- `200`: 成功
- `400`: 尚未檢測到棋盤格
- `500`: 計算錯誤

**副作用**:
- 儲存 `calibration_matrix.npy`
- 儲存 `projection_bounds.json`
- 重置校正狀態

---

## 完整校正流程範例

```javascript
// 1. 開始校正
await fetch('/api/calibration/start', { method: 'POST' });

// 2. 移動棋盤格到球桌範圍
await fetch('/api/calibration/move-checkerboard', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ direction: 'down', step: 50 })
});

// 3. 檢測棋盤格
const detectResult = await fetch('/api/calibration/detect').then(r => r.json());
if (detectResult.detected) {
  console.log('檢測到角點:', detectResult.corners);
  
  // 4. 確認校正
  const confirmResult = await fetch('/api/calibration/confirm', {
    method: 'POST'
  }).then(r => r.json());
  
  console.log('校正完成:', confirmResult.bounds);
}
```

---

## 錯誤處理

所有 API 端點遵循統一的錯誤格式:

```json
{
  "error_code": "CAMERA_ERROR",
  "error_message": "無法讀取相機畫面",
  "message": "無法讀取相機畫面"
}
```

**常見錯誤碼**:
| 錯誤碼 | 說明 |
|--------|------|
| `CAMERA_ERROR` | 相機初始化或讀取失敗 |
| `DETECTION_FAILED` | 棋盤格檢測失敗 |
| `INVALID_ARGUMENT` | 無效的請求參數 |
| `CALIBRATION_ERROR` | 校準計算失敗 |

---

## WebSocket 即時更新 (可選)

未來可擴展 WebSocket 端點用於即時推送檢測結果:

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/calibration');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'detection_update') {
    console.log('即時檢測:', data.corners);
  }
};
```

---

## 投影機串流

**端點**: `GET /burnin/projector.mjpg`

**描述**: 投影機 MJPEG 串流,包含可移動的棋盤格

**使用方式**:
```html
<img src="http://localhost:8001/burnin/projector.mjpg" />
```

校正過程中,此串流會顯示可移動的 4×4 棋盤格圖案。

---

## 版本資訊

- **API 版本**: v1.5.2
- **協議版本**: 1.0
- **最後更新**: 2026-01-23
