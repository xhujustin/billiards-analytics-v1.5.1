# OpenCV 教練建議面板 - 完整配置指南

## 📺 功能概述

`draw_coach_panel()` 函數可在影像右側（或左側）渲染一個半透明的黑色側邊欄，包含：
- 【教練建議】- 主要策略推薦
- 【推薦打法】- 具體擊球方法
- 【下塞與力道】- 力度和方向指引
- 置信度和時間戳

**特性：**
- ✅ 繁體中文完全支持
- ✅ 自動找到系統中文字體
- ✅ 自動換行排版
- ✅ 半透明背景（可調透明度）
- ✅ 適合在藍色球檯上顯示
- ✅ 綠色邊框設計亮眼

---

## 🔤 字體配置

### 方案 1：系統自動檢測（推薦）

函數會自動搜尋系統中的中文字體，無需額外配置：

```python
from ai_coach import draw_coach_panel
import cv2

frame = cv2.imread('pool_table.jpg')
advice = {'recommendation': '建議先進黃球...', ...}

result = draw_coach_panel(frame, advice)  # ✅ 自動使用系統字體
```

#### Windows
- 自動搜尋：`C:\Windows\Fonts\msyh.ttc` (微軟雅黑)
- 備選：`simsun.ttc` (宋體)、`simhei.ttf` (黑體)

#### macOS
- 自動搜尋：`/System/Library/Fonts/PingFang.ttc`
- 備選：`Hiragino Sans GB`

#### Linux
- 自動搜尋：Noto Sans CJK

### 方案 2：使用自訂字體

如果想使用特定字體，放置在 `assets/fonts/` 目錄：

```bash
# Windows 複製一個 TTF 字體
copy "C:\Windows\Fonts\msyh.ttc" assets\fonts\SimHei.ttf

# macOS/Linux
cp /System/Library/Fonts/PingFang.ttc assets/fonts/

# 或下載免費字體
# https://www.noto-cjk.org/  (Google Noto Sans CJK)
# https://www.google.com/get/noto/  (各種字體)
```

然後指定字體目錄：

```python
result = draw_coach_panel(
    frame, 
    advice, 
    font_dir='assets/fonts'  # 指定字體目錄
)
```

---

## 📋 API 參考

### 主函數：`draw_coach_panel()`

```python
from ai_coach import draw_coach_panel

result = draw_coach_panel(
    image,           # OpenCV 影像 (BGR)
    advice_json,     # 建議數據字典
    alpha=0.6,       # 背景透明度 (0-1)
    position='right',# 面板位置 ('left' 或 'right')
    font_dir=None,   # 字體目錄 (None=自動)
)
```

### 參數詳解

#### `image` (必須)
- OpenCV BGR 影像
- 任意分辨率
- Example: `cv2.imread('frame.jpg')`

#### `advice_json` (必須)
字典結構，包含以下欄位（都是可選，若遺漏則使用默認值）：

```python
{
    'recommendation': '建議先進紅球3號，可以控制位置到中心區域',
    'strategy': '斜進法，使用中桿位點擊',
    'force_guide': '中等力道，約70%力度',
    'confidence': 0.87,          # 0-1 之間，會顯示為百分比
    'timestamp': '2026-04-01T10:30:45'  # ISO 格式，只顯示時間部分
}
```

#### `alpha` (可選，默認 0.6)
- 背景透明度，範圍 0-1
- 0 = 完全透明（不顯示）
- 1 = 完全不透明
- 推薦值：0.65 （在藍色球檯上清晰可見）

#### `position` (可選，默認 'right')
- `'right'`：側邊欄在右側
- `'left'`：側邊欄在左側

#### `font_dir` (可選，默認 None)
- 自訂字體目錄路徑
- None：自動搜尋系統字體

---

## 💻 實用範例

### 範例 1：基本使用

```python
import cv2
from ai_coach import draw_coach_panel

# 讀取影像
frame = cv2.imread('pool_table.jpg')

# 建議數據（假設從 AICoachManager 獲得）
advice = {
    'recommendation': '建議先進黃球，可以很好地控制位置',
    'strategy': '中桿位，力度70%',
    'force_guide': '平穩擊球，避免旋轉',
    'confidence': 0.87,
    'timestamp': '2026-04-01T10:30:45'
}

# 渲染面板
result = draw_coach_panel(frame, advice)

# 顯示
cv2.imshow('With Coach Panel', result)
cv2.waitKey(0)
```

### 範例 2：簡化版本（文字直接傳入）

```python
from ai_coach import draw_coach_panel_simple
import cv2

frame = cv2.imread('frame.jpg')

result = draw_coach_panel_simple(
    frame,
    recommendation='建議進黃球3號',
    strategy='中桿位，力度中等',
    force_guide='避免過度自轉',
)

cv2.imshow('Coach', result)
cv2.waitKey(0)
```

### 範例 3：在實時視頻中集成

```python
import cv2
from ai_coach import draw_coach_panel, AICoachManager

# 初始化
ai_coach = AICoachManager()
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # 假設從某處獲得球座標
    balls = [(100, 100), (200, 200), ...]
    
    # 檢測穩定
    is_stable = ai_coach.update(balls)
    
    # 如果穩定，獲取建議
    if is_stable:
        result_data = AICoachManager.get_global_result()
        frame = draw_coach_panel(frame, result_data)
    
    cv2.imshow('Live Stream', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### 範例 4：自訂字體和透明度

```python
import cv2
from ai_coach import draw_coach_panel

frame = cv2.imread('frame.jpg')

result = draw_coach_panel(
    frame,
    {
        'recommendation': '建議的擊球策略',
        'strategy': '打法說明',
        'force_guide': '力道指引',
        'confidence': 0.92,
    },
    alpha=0.75,          # 更不透明（75%）
    position='left',     # 放在左側
    font_dir='assets/fonts'  # 使用自訂字體
)

cv2.imwrite('output.jpg', result)
```

### 範例 5：逐幀處理和保存

```python
import cv2
from ai_coach import draw_coach_panel

# 打開視頻
cap = cv2.VideoCapture('game_video.mp4')
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('output_with_coach.mp4', fourcc, 30.0, (1280, 960))

frame_count = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # 每 60 幀添加一次建議
    if frame_count % 60 == 0:
        advice = {
            'recommendation': '當前位置適合進球',
            'strategy': f'第 {frame_count // 60} 次建議',
            'force_guide': '根據距離調整',
            'confidence': 0.80 + (frame_count % 100) / 500,
        }
        frame = draw_coach_panel(frame, advice)
    
    out.write(frame)
    frame_count += 1

cap.release()
out.release()
print(f"✅ 已處理 {frame_count} 幀，儲存到 output_with_coach.mp4")
```

---

## 🎨 自訂設計

### 修改顏色方案

編輯 `visualizer.py` 中的 `COLORS` 字典：

```python
class CoachPanelRenderer:
    COLORS = {
        'background': (0, 0, 0),          # 黑色背景 (BGR)
        'border': (100, 200, 100),        # 綠色邊框
        'title': (100, 255, 100),         # 標題文字
        'section': (150, 200, 150),       # 小標題
        'text': (255, 255, 255),          # 正文文字
        'accent': (255, 255, 100),        # 強調色（置信度）
    }
```

#### 常用顏色 (BGR 格式)
- 白色：(255, 255, 255)
- 黑色：(0, 0, 0)
- 紅色：(0, 0, 255)
- 綠色：(0, 255, 0)
- 藍色：(255, 0, 0)
- 黃色：(0, 255, 255)
- 青色：(255, 255, 0)
- 洋紅色：(255, 0, 255)

### 修改面板寬度和邊距

```python
class CoachPanelRenderer:
    PANEL_WIDTH = 400           # 改成 350 或 450
    MARGIN = 15                 # 邊距
    SECTION_GAP = 15            # 各區塊間距
```

---

## 🐛 故障排除

### Q: 顯示大方塊而不是文字？
**A:** 字體找不到。解決方案：
1. 確認 Windows/macOS/Linux 上已安裝中文字體
2. 或下載字體放到 `assets/fonts/` 並指定 `font_dir` 參數

### Q: 文字被截斷或超出邊界？
**A:** 
1. 減少 `PANEL_WIDTH` 值以容納長文字
2. 或縮小字體大小（編輯 `visualizer.py`）

### Q: 在藍色球檯上看不清文字？
**A:** 
1. 增加 `alpha` 值（例如 0.75 而不是 0.6）
2. 或改變邊框顏色為更亮的顏色（如黃色或白色）

### Q: 如何隱藏面板？
**A:** 傳入空的 `advice_json` 或 `alpha=0`

```python
result = draw_coach_panel(frame, {}, alpha=0)  # 不顯示
```

---

## 📊 性能考量

| 操作 | 時間 |
|------|------|
| PIL 文字渲染 | 2-5ms |
| Alpha 合成 | 1-3ms |
| 總計 | ~5-8ms |

**幀率影響：** 在 30 FPS 視頻中，添加教練面板通常不會造成明顯延遲。

---

## 🔗 整合到主程式

### 在 backend/main.py 中：

```python
from ai_coach import draw_coach_panel

@app.get("/stream/video-with-coach")
async def stream_video_with_coach():
    """視頻流 - 包含 AI Coach 建議面板。"""
    
    def generate_frames():
        session_id = "video_coach"
        while True:
            ret, frame = camera.read()
            if not ret:
                break
            
            # YOLO 推論 ...
            ball_centers = [(x, y), ...]
            
            # AI Coach 分析
            is_stable = ai_coach.update(ball_centers, session_id)
            
            # 如果穩定，渲染建議面板
            if is_stable:
                advice = AICoachManager.get_global_result(session_id)
                frame = draw_coach_panel(frame, advice, alpha=0.65)
            
            # 編碼並發送
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   buffer.tobytes() + b'\r\n')
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
```

---

## 📚 相關檔案

- **visualizer.py** - 核心實現
- **QUICK_REFERENCE.md** - 快速參考卡
- **INTEGRATION_GUIDE.md** - 整個系統集成指南

---

## 💡 進階用法

### 直接使用 `CoachPanelRenderer` 類別

如果需要更細緻的控制：

```python
from ai_coach.visualizer import CoachPanelRenderer

renderer = CoachPanelRenderer(font_dir='assets/fonts')

# 修改顏色
renderer.COLORS['border'] = (0, 255, 255)  # 改成青色邊框

# 渲染
result = renderer.render(frame, advice_json, alpha=0.7, position='left')
```

### 自訂字體大小

```python
from ai_coach.visualizer import ChineseFontManager, CoachPanelRenderer

# 初始化
font_mgr = ChineseFontManager('assets/fonts')

# 載入自訂大小的字體
title_font = font_mgr.load_font(40)  # 40px 標題
```

---

## 📈 性能優化建議

1. **快取字體對象**（不要每次都重新載入）
2. **預設計算版面布局尺寸**
3. **在需要時才渲染面板**（不是每幀）

範例：
```python
# 一次初始化
renderer = CoachPanelRenderer('assets/fonts')

# 重複使用
for frame in video_stream:
    result = renderer.render(frame, advice)
```

---

## 📞 支援資源

- **OpenCV 文檔**：https://docs.opencv.org/
- **Pillow 文檔**：https://pillow.readthedocs.io/
- **Google Noto 字體**：https://www.noto-cjk.org/
