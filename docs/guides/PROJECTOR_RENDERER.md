# 投影機串流獨立渲染設計

## 問題分析

**目前狀況**:
```python
# main.py line 426-430
projector_frame = calibrator.warp_frame_to_projector(display_frame)
mjpeg_manager.update_projector(projector_frame)
```
- 投影機串流 = 相機畫面的變形版本
- 無法獨立顯示校正圖案、AR 疊加等

**需求**:
投影機串流應該根據不同模式顯示不同內容:
1. **校正模式**: ArUco 標記圖案
2. **遊戲模式**: AR 疊加 (軌跡、球位、輔助線)
3. **待機模式**: 純黑或 Logo

---

## 解決方案: 投影機渲染管線

### 架構設計

```
相機畫面 (camera) ──→ 監控串流 (monitor.mjpg)
                      ↓ 分析
                    YOLO 檢測
                      ↓
                  投影機渲染器
                      ↓
        ┌─────────────┼─────────────┐
        │             │             │
    校正模式      遊戲模式      待機模式
        │             │             │
    ArUco 圖案    AR 疊加       純黑畫面
        │             │             │
        └─────────────┴─────────────┘
                      ↓
            投影機串流 (projector.mjpg)
```

### 核心概念

**投影機畫面 ≠ 相機畫面**
- 投影機畫面是**獨立渲染**的結果
- 根據系統狀態選擇渲染內容
- 可以是純圖案、可以是 AR 疊加、可以是空白

---

## 實作方案

### 1. 投影機渲染管理器

**檔案**: `backend/projector_renderer.py`

```python
import cv2
import numpy as np
from enum import Enum
from typing import Optional, Dict, Any

class ProjectorMode(Enum):
    """投影機模式"""
    IDLE = "idle"              # 待機 (純黑)
    CALIBRATION = "calibration"  # 校正模式 (ArUco 標記)
    GAME = "game"              # 遊戲模式 (AR 疊加)
    PRACTICE = "practice"      # 練習模式 (AR 疊加)

class ProjectorRenderer:
    """投影機獨立渲染器"""
    
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.mode = ProjectorMode.IDLE
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        
        # 校正模式狀態
        self.calibration_offsets = {
            "top-left": {"x": -300, "y": -300},
            "top-right": {"x": 300, "y": -300},
            "bottom-right": {"x": 300, "y": 300},
            "bottom-left": {"x": -300, "y": 300}
        }
        
        # AR 疊加資料
        self.ar_data = {
            "trajectories": [],  # 軌跡路徑
            "balls": [],         # 球位
            "aim_lines": []      # 瞄準線
        }
    
    def set_mode(self, mode: ProjectorMode):
        """切換投影機模式"""
        self.mode = mode
        print(f"📽️ Projector mode: {mode.value}")
    
    def render(self) -> np.ndarray:
        """
        根據當前模式渲染投影機畫面
        Returns: 1920×1080 BGR 影像
        """
        if self.mode == ProjectorMode.IDLE:
            return self._render_idle()
        elif self.mode == ProjectorMode.CALIBRATION:
            return self._render_calibration()
        elif self.mode == ProjectorMode.GAME:
            return self._render_game()
        elif self.mode == ProjectorMode.PRACTICE:
            return self._render_practice()
        else:
            return self._render_idle()
    
    def _render_idle(self) -> np.ndarray:
        """待機模式: 純黑畫面"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 可選: 顯示 Logo 或提示文字
        text = "Billiards Analytics System"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 1.5, 3)[0]
        text_x = (self.width - text_size[0]) // 2
        text_y = (self.height + text_size[1]) // 2
        cv2.putText(frame, text, (text_x, text_y), font, 1.5, (50, 50, 50), 3)
        
        return frame
    
    def _render_calibration(self) -> np.ndarray:
        """校正模式: ArUco 標記圖案"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        marker_size = 200
        center_x = self.width // 2
        center_y = self.height // 2
        
        markers_config = [
            (0, "top-left"),
            (1, "top-right"),
            (2, "bottom-right"),
            (3, "bottom-left")
        ]
        
        position_labels = {
            "top-left": "左上",
            "top-right": "右上",
            "bottom-right": "右下",
            "bottom-left": "左下"
        }
        
        for marker_id, corner_key in markers_config:
            offset = self.calibration_offsets.get(corner_key, {"x": 0, "y": 0})
            
            # 計算標記位置
            x = center_x + offset["x"] - marker_size // 2
            y = center_y + offset["y"] - marker_size // 2
            
            # 產生 ArUco 標記
            marker = cv2.aruco.generateImageMarker(
                self.aruco_dict, 
                marker_id, 
                marker_size
            )
            marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
            
            # 放置標記
            if 0 <= x < self.width - marker_size and 0 <= y < self.height - marker_size:
                frame[y:y+marker_size, x:x+marker_size] = marker_bgr
            
            # 繪製位置標籤 (不顯示 ID)
            label = position_labels[corner_key]
            label_pos = (x + marker_size // 2 - 30, y + marker_size + 30)
            cv2.putText(frame, label, label_pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        
        return frame
    
    def _render_game(self) -> np.ndarray:
        """遊戲模式: AR 疊加 (軌跡、球位、輔助線)"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 繪製軌跡
        for trajectory in self.ar_data.get("trajectories", []):
            if len(trajectory) > 1:
                pts = np.array(trajectory, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], False, (0, 255, 0), 3, cv2.LINE_AA)
        
        # 繪製球位
        for ball in self.ar_data.get("balls", []):
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            ball_type = ball.get("type", "unknown")
            color = (255, 255, 255) if ball_type == "cue" else (0, 255, 0)
            cv2.circle(frame, (x, y), 20, color, -1, cv2.LINE_AA)
        
        # 繪製瞄準線
        for aim_line in self.ar_data.get("aim_lines", []):
            start = tuple(aim_line["start"])
            end = tuple(aim_line["end"])
            cv2.line(frame, start, end, (255, 255, 0), 2, cv2.LINE_AA)
        
        return frame
    
    def _render_practice(self) -> np.ndarray:
        """練習模式: 與遊戲模式相同,但可能有額外的練習輔助"""
        return self._render_game()
    
    def update_calibration_offsets(self, offsets: Dict):
        """更新校正模式的標記偏移"""
        self.calibration_offsets.update(offsets)
    
    def update_ar_data(self, ar_data: Dict):
        """更新 AR 疊加資料"""
        self.ar_data.update(ar_data)
```

### 2. 整合到 main.py

**修改**: `backend/main.py`

```python
# 全域變數新增
from projector_renderer import ProjectorRenderer, ProjectorMode

projector_renderer = ProjectorRenderer()

# 修改相機捕獲循環 (line 420-445)
def camera_capture_loop():
    # ... 前面的程式碼保持不變 ...
    
    while camera_running.is_set():
        # ... 讀取相機畫面 ...
        
        # 監控流: 相機畫面 + YOLO 疊加
        if mjpeg_manager is not None:
            monitor_frame = cv2.resize(display_frame, (1280, 720))
            mjpeg_manager.update_monitor(monitor_frame)
            
            # ✅ 投影機流: 獨立渲染 (不是相機畫面!)
            projector_frame = projector_renderer.render()
            mjpeg_manager.update_projector(projector_frame)
        
        # ... 後面的程式碼保持不變 ...

# 新增 API 端點
@app.post("/api/projector/mode")
async def set_projector_mode(data: dict):
    """設定投影機模式"""
    mode_str = data.get("mode", "idle")
    try:
        mode = ProjectorMode(mode_str)
        projector_renderer.set_mode(mode)
        return {"status": "ok", "mode": mode.value}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mode")

@app.post("/api/projector/calibration/update-offsets")
async def update_calibration_offsets(offsets: dict):
    """更新校正標記偏移"""
    projector_renderer.update_calibration_offsets(offsets)
    return {"status": "ok"}

@app.post("/api/projector/ar/update")
async def update_ar_data(ar_data: dict):
    """更新 AR 疊加資料"""
    projector_renderer.update_ar_data(ar_data)
    return {"status": "ok"}
```

### 3. 前端使用範例

```typescript
// 進入校正模式
await fetch('/api/projector/mode', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ mode: 'calibration' })
});

// 更新標記位置
await fetch('/api/projector/calibration/update-offsets', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    'top-left': { x: -300, y: -300 },
    'top-right': { x: 300, y: -300 },
    // ...
  })
});

// 投影機串流會自動顯示更新後的 ArUco 標記
// <img src="http://localhost:8001/burnin/projector.mjpg" />
```

---

## 模式切換流程

### 校正流程
```
1. 使用者進入校正頁面
   ↓
2. 前端: POST /api/projector/mode { mode: "calibration" }
   ↓
3. 投影機串流顯示 ArUco 標記
   ↓
4. 使用者移動標記
   ↓
5. 前端: POST /api/projector/calibration/update-offsets
   ↓
6. 投影機串流即時更新標記位置
   ↓
7. 完成校正
   ↓
8. 前端: POST /api/projector/mode { mode: "idle" }
```

### 遊戲流程
```
1. 使用者開始遊戲
   ↓
2. 前端: POST /api/projector/mode { mode: "game" }
   ↓
3. YOLO 檢測球位和軌跡
   ↓
4. 後端: projector_renderer.update_ar_data(...)
   ↓
5. 投影機串流顯示 AR 疊加
   ↓
6. 遊戲結束
   ↓
7. 前端: POST /api/projector/mode { mode: "idle" }
```

---

## 優勢

### 1. 完全獨立
- 投影機畫面不依賴相機畫面
- 可以顯示純圖案、純文字、純 AR

### 2. 模式清晰
- 每個模式有明確的渲染邏輯
- 易於擴展新模式

### 3. 效能優化
- 待機模式不需要任何計算
- 校正模式只渲染簡單圖案
- 遊戲模式才進行複雜 AR 疊加

### 4. 易於測試
- 可以獨立測試每個模式的渲染
- 不需要相機也能測試投影機畫面

---

## 擴展方案

### 新增模式範例

```python
class ProjectorMode(Enum):
    IDLE = "idle"
    CALIBRATION = "calibration"
    GAME = "game"
    PRACTICE = "practice"
    DEMO = "demo"  # 新增: 展示模式
    TRAINING = "training"  # 新增: 訓練模式

def _render_demo(self) -> np.ndarray:
    """展示模式: 播放預錄的精彩片段"""
    # 實作展示邏輯
    pass

def _render_training(self) -> np.ndarray:
    """訓練模式: 顯示訓練圖案和提示"""
    # 實作訓練邏輯
    pass
```

---

## 更新記錄

**06/18**: 準度訓練與球型練習靜態投影改回一般練習的座標轉換原則。前端 `coordinate_space: "relative"` 會先換成相機 `table_roi` 上的實際點，再直接走 homography；不在投影層做額外縮放、球位內縮或袋口吸附。輸出格式不變，仍由 `/api/practice/start` 與 `/api/practice/layout` 傳入 `pattern_layout`。

**04/23**: 新增 AR 多球分段路線支援。投影端可接收 `ar_route_segments`，分段渲染母球入射、子球進洞/反彈與母球擊後走位；當 `ar_route_segments` 存在時，會停用舊版 `ar_paths/aim_lines` 混畫，避免顯示錯誤目標球或不連續路線。

**01/23**: 建立投影機串流獨立渲染設計,將投影機畫面從相機畫面分離,支援多種模式(校正、遊戲、待機),提供完整的 API 和前端整合方案。
