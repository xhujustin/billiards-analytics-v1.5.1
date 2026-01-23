# 投影機即時疊加技術文檔

## 概述

本文檔說明撞球分析系統中「投影機即時疊加」功能的技術實作方案。

## 功能目標

將分析結果(球位、軌跡預測、瞄準輔助線)即時疊加到投影機畫面,投射到實體撞球桌上,提供 AR 輔助功能。

## 推薦技術方案

### 方案選擇: 後端 OpenCV 疊加 ⭐⭐⭐⭐⭐

**選擇理由**
- 專案已整合 OpenCV,無需額外依賴
- 後端統一處理,前端只需播放 MJPEG 串流
- 效能穩定,支援複雜圖形繪製
- 已有 `Calibrator` 類別提供座標轉換基礎

**核心技術棧**
```python
import cv2              # 圖像處理與繪圖
import numpy as np      # 座標轉換與矩陣運算
```

## 推薦函式庫

### OpenCV 繪圖函式

| 函式 | 用途 | 範例 |
|------|------|------|
| `cv2.line()` | 繪製直線 | 瞄準輔助線 |
| `cv2.circle()` | 繪製圓形 | 球位標記 |
| `cv2.polylines()` | 繪製多段線 | 軌跡曲線 |
| `cv2.putText()` | 繪製文字 | 球號、提示 |
| `cv2.addWeighted()` | 半透明疊加 | 區域標記 |

### 座標轉換

| 函式 | 用途 |
|------|------|
| `cv2.findHomography()` | 計算校準矩陣 |
| `cv2.perspectiveTransform()` | 座標點轉換 |
| `cv2.warpPerspective()` | 影像變形 |

## 快速實作指南

### 步驟 1: 建立疊加渲染器

**檔案**: `backend/projector_overlay.py`

```python
import cv2
import numpy as np

class ProjectorOverlay:
    """投影機疊加渲染器"""
    
    def draw_trajectory(self, frame, path_points, color=(0, 255, 0), thickness=3):
        """繪製軌跡線"""
        if len(path_points) < 2:
            return frame
        
        pts = np.array(path_points, np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], False, color, thickness, cv2.LINE_AA)
        return frame
    
    def draw_ball_markers(self, frame, balls):
        """繪製球位標記"""
        for ball in balls:
            x, y = int(ball['x']), int(ball['y'])
            color = (255, 255, 255) if ball.get('type') == 'cue' else (0, 255, 0)
            cv2.circle(frame, (x, y), 15, color, 2, cv2.LINE_AA)
        return frame
```

### 步驟 2: 整合到主程式

**檔案**: `backend/main.py` (修改 `camera_capture_loop` 函式)

```python
# 在投影機串流更新處 (約 line 426)
if calibrator is not None:
    # 座標轉換
    projector_frame = calibrator.warp_frame_to_projector(display_frame)
    
    # 疊加 AR 資訊
    if system_state["is_analyzing"] and latest_analysis_data.get("ar_paths"):
        overlay = ProjectorOverlay()
        
        # 繪製軌跡
        ar_paths = latest_analysis_data["ar_paths"]
        projector_frame = overlay.draw_trajectory(projector_frame, ar_paths)
        
        # 繪製球位
        balls = latest_analysis_data.get("data", {}).get("balls", [])
        if balls:
            # 轉換座標到投影機空間
            ball_positions = [(b['x'], b['y']) for b in balls]
            transformed_balls = calibrator.transform_points(ball_positions)
            for i, ball in enumerate(balls):
                if i < len(transformed_balls):
                    ball['x'], ball['y'] = transformed_balls[i]
            
            projector_frame = overlay.draw_ball_markers(projector_frame, balls)
    
    mjpeg_manager.update_projector(projector_frame)
```

### 步驟 3: 投影機校正

#### 3.1 四角定位點校正 (必須) ⭐

**目的**: 建立相機座標與投影機座標的映射關係

**操作流程**:
1. 投影機投射四角定位點: `GET /api/calibration/corner-markers`
2. 相機拍攝畫面
3. 使用者在前端點擊相機畫面中的四個角點 (左上→右上→右下→左下)
4. 系統計算校準矩陣: `POST /api/calibration/compute`

**後端 API**:
```python
# 投射定位點圖案
GET /api/calibration/corner-markers

# 計算校準矩陣
POST /api/calibration/compute
Body: [{"x": 100, "y": 200}, {"x": 1800, "y": 200}, ...]
```

#### 3.2 梯形校正 + 範圍限制 (可選)

**新增功能**: 修正投影機梯形變形和限制投影範圍

#### 後端 API
```python
# 梯形校正
POST /api/calibration/keystone
Body: [{"x": 0, "y": 0}, {"x": 1920, "y": 0}, ...]

# 範圍限制
POST /api/calibration/bounds
Body: {"x": 100, "y": 50, "width": 1720, "height": 980}

# 測試圖案
GET /api/calibration/test-pattern
```

#### 前端整合
在設定頁面新增「投影機校正」按鈕,引導使用者完成梯形校正和範圍設定。

**詳細實作**: 參考 [投影機校正規劃文檔](file:///C:/Users/xhuju/.gemini/antigravity/brain/bfaaa2c6-b49b-40b3-b803-6de7000a8adf/projector_calibration_plan.md)

### 步驟 4: 測試與驗證

```bash
# 啟動後端
cd backend
python main.py

# 開啟投影機串流
# 瀏覽器訪問: http://localhost:8001/burnin/projector.mjpg
# 按 F11 全螢幕,拖曳到投影機螢幕
```

## 輸出方式說明

### 推薦方案: MJPEG 串流 + 瀏覽器全螢幕 ⭐⭐⭐⭐⭐

**使用方式**
1. 後端產生 MJPEG 串流: `mjpeg_manager.update_projector(frame)`
2. 瀏覽器開啟: `http://localhost:8001/burnin/projector.mjpg`
3. 按 F11 進入全螢幕
4. 拖曳視窗到投影機螢幕

**優點**
- ✅ 跨平台 (Windows/Mac/Linux)
- ✅ 支援遠端投影 (網路串流)
- ✅ 多螢幕支援簡單
- ✅ 無需額外視窗管理

### 替代方案: cv2.imshow (不推薦)

```python
cv2.namedWindow('Projector', cv2.WINDOW_NORMAL)
cv2.setWindowProperty('Projector', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
cv2.imshow('Projector', projector_frame)
```

**缺點**: 多螢幕設定複雜、無法遠端投影、視窗管理不穩定



## 效能優化

### 跳幀策略
```python
# 降低繪製頻率,減少 CPU 負擔
if frame_count % 2 == 0:  # 每 2 幀繪製一次
    projector_frame = overlay.render(projector_frame)
```

### 條件渲染
```python
# 僅在有分析資料時才繪製
if latest_analysis_data.get("ar_paths"):
    projector_frame = overlay.draw_trajectory(...)
```

## 進階功能 (可選)

### 前端 Canvas 疊加

適用於需要高度客製化 UI 的場景。

**技術棧**: HTML5 Canvas / WebGL / Three.js

**優點**: 前端靈活控制、降低後端負擔、支援動態互動

**缺點**: 開發複雜度較高、座標同步需額外處理

## 相關文檔

- [完整實作規劃](file:///C:/Users/xhuju/.gemini/antigravity/brain/bfaaa2c6-b49b-40b3-b803-6de7000a8adf/implementation_plan.md) - 詳細技術方案和程式碼範例
- [calibration.py](file:///c:/Users/xhuju/Desktop/billiards-analytics-v1.5/backend/calibration.py) - 現有校準模組
- [main.py](file:///c:/Users/xhuju/Desktop/billiards-analytics-v1.5/backend/main.py#L420-L445) - 投影機串流實作

## 更新記錄

**01/23**: 建立投影機即時疊加技術文檔,推薦使用 OpenCV 後端疊加方案,提供完整實作範例和效能優化建議。
