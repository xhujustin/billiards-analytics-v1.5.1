# AI Coach 系統 - 完整功能總結

> 一個整合了台球靜止偵測、座標語意化、LLM 推論和中文視覺化的完整 AI 教練系統。

##  系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                     OpenCV 主程式                              │
│                   (backend/main.py)                           │
└────────┬────────────────────────────────────────────┬────────┘
         │                                            │
         ▼                                            ▼
    YOLO 推論                                    AICoachManager
    (球座標)                                     - 靜止偵測
         │                                      - 語意轉換
         └──────────────────┬──────────────────┘
                            │
                            ▼ (球穩定觸發)
                   非同步 vLLM API
                   (A100 伺服器)
                            │
                            ▼ (JSON 建議)
                  draw_coach_panel()
                  (中文視覺化)
                            │
                            ▼
                      UI 顯示 / 存儲
```

## 📦 系統模組

### 1. **overlay.py** - 穩定性偵測
```python
from ai_coach import StabilityDetector

detector = StabilityDetector()
is_stable = detector.is_stable([(x1, y1), (x2, y2), ...])
```
- 監測 60 幀滾動窗口
- 位移 < 2 像素判斷穩定
- 自動冷卻機制

### 2. **client.py** - 核心管理器
```python
from ai_coach import AICoachManager, CoordinateSemanticizer

# 初始化
ai_coach = AICoachManager(vllm_api_url="http://10.0.0.100:8000/...")

# 實時更新
is_stable = ai_coach.update(ball_centers, session_id="game_1")

# 獲取結果
result = AICoachManager.get_global_result("game_1")
```
- **協調語意化座標** ← (x, y) 轉『左上、中心、底袋』等
- **非同步 API 互動** ← 線程安全的 POST 請求到 vLLM
- **全域結果存儲** ← 供 UI 實時顯示

### 3. **visualizer.py** - 中文視覺化
```python
from ai_coach import draw_coach_panel

result = draw_coach_panel(
    image,           # OpenCV BGR 影像
    advice_json,     # 建議數據字典
    alpha=0.6,       # 背景透明度
    position='right' # 面板位置
)
```
- 自動尋找系統中文字體
- 400 像素寬半透明側邊欄
- 自動換行排版
- 適合藍色球檯顯示

### 4. **train.py** - 模型微調
使用 Unsloth 和 LoRA 微調 Llama-3.1-8B 或 Qwen-2.5-7B
- 配置：LoRA r=16, alpha=32
- 訓練參數：learning_rate=2e-4, epochs=3
- 優化：BF16 混合精度（A100 適配）

### 5. **inference.py** - 推論引擎
支持量化模型推論和聊天模式

---

##  快速集成步驟

### Step 1：安裝依賴

```bash
pip install opencv-python pillow requests numpy
```

### Step 2：初始化 AI Coach

```python
from ai_coach import AICoachManager, draw_coach_panel
import cv2

# 初始化管理器
ai_coach = AICoachManager(
    vllm_api_url="http://10.0.0.100:8000/v1/chat/completions"
)

# 可選：自訂字體（如果系統找不到中文字體）
# ai_coach.semanticizer.font_dir = 'assets/fonts'
```

### Step 3：主推論迴圈

```python
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # YOLO 推論獲得球座標
    results = tracker.detect(frame)
    balls = [(cx, cy) for det in results]
    
    # AI Coach 分析
    is_stable = ai_coach.update(balls, session_id="game_1")
    
    # 獲取 AI 建議
    if is_stable:
        advice = AICoachManager.get_global_result("game_1")
        
        # 渲染教練面板
        if advice:
            frame = draw_coach_panel(frame, advice)
    
    # 顯示結果
    cv2.imshow('AI Coach', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

---

##  工作流程完全示例

### 實時遊戲分析

```python
import cv2
from ai_coach import AICoachManager, draw_coach_panel

# 初始化
ai_coach = AICoachManager(
    vllm_api_url="http://A100_SERVER_IP:8000/v1/chat/completions",
    table_width=1920,
    table_height=1080
)

# 視頻流處理
cap = cv2.VideoCapture('game_video.mp4')
session_id = "game_session_" + str(time.time())

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # 1️⃣ YOLO 檢測球
    yolo_results = tracker.detect(frame)
    ball_centers = extract_ball_centers(yolo_results)
    
    # 2️⃣ 檢測穩定
    is_stable = ai_coach.update(ball_centers, session_id)
    
    # 3️⃣ 如果穩定，獲得 AI 建議（非同步返回）
    advice = AICoachManager.get_global_result(session_id)
    
    # 4️⃣ 渲染教練面板
    if advice:
        frame = draw_coach_panel(
            frame,
            advice,
            alpha=0.65,  # 65% 透明度
            position='right'
        )
    
    # 5️⃣ 顯示/存儲幀
    cv2.imshow('AI Coach Live', frame)
    video_writer.write(frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
video_writer.release()
cv2.destroyAllWindows()
```

---

##  完整的 OpenCV 函數簽名

### `draw_coach_panel()`

```python
def draw_coach_panel(
    image: np.ndarray,                    # OpenCV BGR 影像
    advice_json: Dict[str, Any],          # {'recommendation': '...', ...}
    alpha: float = 0.6,                   # 背景透明度 (0-1)
    position: str = 'right',              # 面板位置
    font_dir: Optional[str] = None,       # 自訂字體目錄
) -> np.ndarray:
    """
    在影像上渲染 AI 教練建議面板。
    
    面板包含：
    - 【教練建議】 - 主策略
    - 【推薦打法】 - 擊球方法
    - 【下塞與力道】 - 力度指引
    
    特性：
    - 自動檢測中文字體
    - 自動換行排版
    - 半透明黑色背景 + 綠色邊框
    - 置信度和時間戳顯示
    """
```

### 建議數據結構

```python
advice = {
    'recommendation': str,      # 【教練建議】內容
    'strategy': str,            # 【推薦打法】內容
    'force_guide': str,         # 【下塞與力道】內容
    'confidence': float,        # 置信度 (0-1)
    'timestamp': str,           # ISO 8601 時間戳
}
```

---

##  視覺化效果

### 面板配置

```
┌──────────────────────────────┐
│        AI 教練        │ (綠色邊框)
├──────────────────────────────┤
│ 【教練建議】                  │
│ 建議先進紅球3號，可以    │
│ 很好地控制白球位置到     │
│ 中心區域...                   │
│                              │
│ 【推薦打法】                  │
│ 斜進法，使用中桿位點擊    │
│                              │
│ 【下塞與力道】                │
│ 中等力道，約70%力度，     │
│ 避免過於用力造成失控...    │
│                              │
│ 置信度: 87%  10:30:45      │
└──────────────────────────────┘
(黑色半透明背景，寬度 400px)
```

### 色彩方案（藍色球檯優化）

| 元素 | 顏色 | 用途 |
|------|------|------|
| 背景 | 黑色 (0,0,0) | 主背景，半透明 |
| 邊框 | 綠色 (100,200,100) | 3px 左邊框 |
| 標題 | 淺綠 (100,255,100) | "AI 教練" |
| 小標題 | 淺綠 (150,200,150) | 各區塊標題 |
| 正文 | 白色 (255,255,255) | 主要內容 |
| 強調 | 黃色 (255,255,100) | 置信度 |

---

## � 部署與啟動指南

> 選擇適合您的部署方式

| 指南 | 用途 | 推薦場景 |
|------|------|---------|
| **[DEPLOYMENT_GUIDE.md](guides/DEPLOYMENT_GUIDE.md)** |  浏览所有部署方式 | 不确定选择？从这里开始 |
| **[DEPLOYMENT_LOCAL_YOLO.md](guides/DEPLOYMENT_LOCAL_YOLO.md)** |  本地 YOLO 推理 | 实时检测、离线工作、快响应 |
| **[DEPLOYMENT_REMOTE_VLLM.md](guides/DEPLOYMENT_REMOTE_VLLM.md)** |  远端 vLLM 推理 | AI 建议、文本生成、精确分析 |

---

##  文檔導航

| 文檔 | 內容 |
|------|------|
| **guides/DEPLOYMENT_GUIDE.md** |  部署方式選擇指南 |
| **guides/DEPLOYMENT_LOCAL_YOLO.md** |  本地 YOLO 部署 |
| **guides/DEPLOYMENT_REMOTE_VLLM.md** |  遠端 vLLM 部署 |
| **guides/QUICKSTART.md** |  5 分鐘快速開始 |
| **guides/QUICK_REFERENCE.md** |  快速參考卡 |
| **guides/VISUALIZATION_GUIDE.md** | 視覺化詳細配置 |
| **guides/INTEGRATION_GUIDE.md** | 系統整合步驟 |
| **guides/USAGE_EXAMPLES.md** | 7 個實用範例 |
| **guides/DEVELOPMENT.md** | 開發和調試 |

---

##  系統需求

### 硬體
- **OpenCV 推論**：CPU 或 GPU
- **vLLM (A100)**：需要 A100 GPU（20GB+ VRAM）
- **字體渲染**：CPU

### 軟體依賴
```
opencv-python >= 4.5.0
Pillow >= 8.3.0
requests >= 2.26.0
numpy >= 1.19.0
```

### 網絡
- OpenCV 主程式需能連接 A100 vLLM 伺服器
- API 超時設定：30 秒

---

## ✨ 核心特性總結

| 特性 | 實現 |
|------|------|
| 靜止偵測 | StabilityDetector (60幀滾動窗口) |
| 座標語意化 | CoordinateSemanticizer (3×3 區域 + 特殊位置) |
| LLM 推論 | AICoachManager (非同步 vLLM API) |
| 中文渲染 | draw_coach_panel (自動字體檢測) |
| 線程安全 | Lock-based 全域結果存儲 |
| 排版 | 自動換行，響應式布局 |

---

## 🚦 集成檢查清單

- [ ] 安裝 OpenCV、Pillow、requests
- [ ] 確認系統已安裝中文字體（或放置到 `assets/fonts/`）
- [ ] A100 伺服器已啟動 vLLM API
- [ ] 確認 OpenCV 主程式的 YOLO 推論正常
- [ ] 在主迴圈中初始化 AICoachManager
- [ ] 集成 draw_coach_panel 到視頻流處理
- [ ] 測試完整工作流程
- [ ] 調整 alpha 和 position 參數至最佳

---

## 🐛 常見問題

### Q: 中文字體找不到？
**A:** 
1. Windows：確認 `C:\Windows\Fonts` 有中文字體（如微軟雅黑）
2. macOS：系統已內置 PingFang
3. Linux：安裝 `fonts-noto-cjk`
4. 或下載字體放到 `assets/fonts/` 並指定 `font_dir`

### Q: API 連接超時？
**A:** 檢查：
1. A100 伺服器是否啟動：`curl http://IP:8000/v1/models`
2. 防火牆設置
3. 網絡連接

### Q: 性能慢？
**A:**
1. vLLM API 延遲 (1-3s) ← 正常，取決於模型
2. 確認 GPU 未滿載
3. 考慮使用更小的模型（如 7B 而非 13B）

### Q: 文字在球檯上看不清？
**A:**
1. 增加 `alpha` (例 0.75 而非 0.6)
2. 改變邊框顏色為更亮的（黃色或白色）
3. 增加字體大小（編輯 visualizer.py）

---

## 📈 性能指標

| 操作 | 時間 |
|------|------|
| YOLO 推論 | 30-50ms (GPU) |
| 穩定偵測 | < 1ms |
| 座標語意化 | < 1ms |
| 中文文字渲染 | 5-8ms |
| vLLM API 往返 | 1-3s |
| **總端到端** | **1-3.1s** |

---

## 🎓 學習路徑

### 初級
1. 閱讀 [QUICK_REFERENCE.md](ai_coach/QUICK_REFERENCE.md)
2. 執行範例 1：基本使用
3. 調整 alpha 和位置

### 中級
1. 閱讀 [VISUALIZATION_GUIDE.md](ai_coach/VISUALIZATION_GUIDE.md)
2. 在實時視頻中集成
3. 自訂字體和顏色

### 進階
1. 閱讀完整源碼 (visualizer.py)
2. 修改 CoachPanelRenderer 以支持自訂版面
3. 優化性能（快取、預計算）

---

## 🔗 相關資源

- **OpenCV**：https://docs.opencv.org/
- **Pillow**：https://pillow.readthedocs.io/
- **Unsloth**：https://github.com/unslothai/unsloth
- **vLLM**：https://docs.vllm.ai/

---

##  支援

遇到問題？檢查：
1. **症狀** → 查看常見問題部分
2. **代碼** → 參考 USAGE_EXAMPLES.md
3. **配置** → 參考 VISUALIZATION_GUIDE.md
4. **整合** → 參考 INTEGRATION_GUIDE.md

---

**版本**: 1.0.0  
**最後更新**: 2026-04-01  
**狀態**:  完整可用
