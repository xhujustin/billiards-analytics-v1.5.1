# 投影機棋盤格校正 - 快速實作指南

## 功能概述

**目標**: 使用 4×4 黑白棋盤格進行投影機校正,前端提供可拖曳四角控制點,一次完成校準和範圍設定。

## 後端實作

### API 1: 投射棋盤格圖案

**檔案**: `backend/main.py`

```python
@app.get("/api/calibration/checkerboard")
async def get_checkerboard_pattern():
    """產生 4×4 黑白棋盤格圖案"""
    pattern = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    # 棋盤格參數
    rows, cols = 4, 4
    cell_width = 1920 // cols   # 480px
    cell_height = 1080 // rows  # 270px
    
    # 繪製棋盤格
    for i in range(rows):
        for j in range(cols):
            color = (255, 255, 255) if (i + j) % 2 == 0 else (0, 0, 0)
            x1, y1 = j * cell_width, i * cell_height
            x2, y2 = x1 + cell_width, y1 + cell_height
            cv2.rectangle(pattern, (x1, y1), (x2, y2), color, -1)
    
    # 四角綠色標記
    corners = [(50, 50), (1870, 50), (1870, 1030), (50, 1030)]
    for x, y in corners:
        cv2.circle(pattern, (x, y), 20, (0, 255, 0), -1, cv2.LINE_AA)
    
    ret, buffer = cv2.imencode('.jpg', pattern)
    return Response(content=buffer.tobytes(), media_type="image/jpeg")
```

### API 2: 計算校準矩陣 + 投影範圍

```python
@app.post("/api/calibration/compute-with-bounds")
async def compute_calibration_with_bounds(data: dict):
    """
    計算校準矩陣和投影範圍
    data: {
        "camera_points": [{"x": 100, "y": 200}, ...],
        "projector_points": [{"x": 50, "y": 50}, ...]
    }
    """
    camera_points = data.get("camera_points", [])
    projector_points = data.get("projector_points", [
        {"x": 50, "y": 50}, {"x": 1870, "y": 50},
        {"x": 1870, "y": 1030}, {"x": 50, "y": 1030}
    ])
    
    # 計算校準矩陣
    src_points = np.array([(p["x"], p["y"]) for p in camera_points], dtype="float32")
    dst_points = np.array([(p["x"], p["y"]) for p in projector_points], dtype="float32")
    
    calibrator.homography_matrix, _ = cv2.findHomography(src_points, dst_points)
    np.save("calibration_matrix.npy", calibrator.homography_matrix)
    
    # 計算投影範圍
    xs = [p["x"] for p in projector_points]
    ys = [p["y"] for p in projector_points]
    bounds = {
        "x": min(xs), "y": min(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys)
    }
    calibrator.set_projection_bounds(bounds)
    
    return {"status": "ok", "bounds": bounds}
```

## 前端實作

### 拖曳式校正介面

**檔案**: `frontend/src/components/pages/CalibrationWizard.tsx`

**核心功能**:
1. 顯示相機即時畫面
2. 四個可拖曳綠色控制點
3. 即時預覽投影範圍 (綠色框線)
4. 提交校準

**關鍵程式碼**:

```typescript
const [corners, setCorners] = useState<Point[]>([
  { x: 100, y: 100 },   // 左上
  { x: 1180, y: 100 },  // 右上
  { x: 1180, y: 620 },  // 右下
  { x: 100, y: 620 }    // 左下
]);

// 滑鼠拖曳處理
const handleMouseDown = (e) => {
  const { x, y } = getMousePos(e);
  corners.forEach((corner, index) => {
    if (distance(x, y, corner.x, corner.y) < 15) {
      setDraggingIndex(index);
    }
  });
};

const handleMouseMove = (e) => {
  if (draggingIndex !== null) {
    const { x, y } = getMousePos(e);
    const newCorners = [...corners];
    newCorners[draggingIndex] = { x, y };
    setCorners(newCorners);
  }
};
```

## 使用流程

1. **投射棋盤格**: 瀏覽器開啟 `/api/calibration/checkerboard`
2. **拖曳四角**: 在相機畫面上拖曳綠色控制點對齊棋盤格角落
3. **即時預覽**: 綠色框線顯示投影範圍
4. **完成校準**: 點擊「完成校準」按鈕

## 視覺效果

```
投影機畫面:                前端畫面:
┌─────────────┐          ┌─────────────┐
│ ■ □ ■ □     │          │ 相機畫面    │
│ □ ■ □ ■     │          │   ●────●    │ ← 可拖曳控制點
│ ■ □ ■ □     │          │   │    │    │
│ □ ■ □ ■     │          │   ●────●    │
└─────────────┘          └─────────────┘
  4×4 棋盤格              綠色框線 = 投影範圍
```

## 優勢

- ✅ 一次操作完成校準和範圍設定
- ✅ 拖曳式操作直觀易用
- ✅ 棋盤格提供清晰視覺參考
- ✅ 即時預覽投影範圍
