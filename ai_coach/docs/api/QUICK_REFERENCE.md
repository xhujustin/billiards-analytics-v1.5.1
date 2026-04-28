# AI Coach 快速參考卡

## 🚀 核心類別

### 1. StabilityDetector （靜止偵測）
```python
from ai_coach.overlay import StabilityDetector

detector = StabilityDetector()
# 監測 60 幀 (1 秒)，位移 < 2像素時觸發
is_stable = detector.is_stable([(x1, y1), (x2, y2), ...])
```

**特性：**
- 自動 1 秒滾動窗口（60 幀）
- 位移標準差 < 2 像素才視為穩定
- 自動冷卻機制避免重複觸發
- 可自訂參數（BUFFER_SIZE, DISPLACEMENT_THRESHOLD 等）

---

### 2. CoordinateSemanticizer （座標語意化）
```python
from ai_coach.client import CoordinateSemanticizer

sem = CoordinateSemanticizer(table_width=1920, table_height=1080)

# 單球描述
pos = sem.coordinate_to_semantic(x=500, y=300)
# 返回：'中心位', '左上角', '底袋位' 等

# 多球描述
desc = sem.balls_to_semantic_description([(100, 100), (500, 300)])
# 返回：'1顆球在左上角，1顆球在中心位'
```

**區域映射（3×3 網格）：**
```
左上角    上中袋    右上角
左中位    中心位    右中位
左下角    底袋位    右下角
```

**特殊位置：** 左邊袋、右邊袋、各角袋等

---

### 3. AICoachManager （整合管理器）
```python
from ai_coach.client import AICoachManager

# 初始化
manager = AICoachManager(
    vllm_api_url="http://10.0.0.100:8000/v1/chat/completions",
    vllm_model="meta-llama/Llama-2-7b-chat-hf",
)

# 主迴圈中調用（每幀）
is_stable = manager.update(ball_centers, session_id="game_123")

# 獲取結果（非同步返回）
result = AICoachManager.get_global_result("game_123")
# 返回：{
#     "timestamp": "2026-04-01T10:30:45.123456",
#     "ball_positions": {"ball_0": "左上角", ...},
#     "semantic_description": "...",
#     "recommendation": "建議進黃球...",
#     "confidence": 0.87,
#     "processing_time": 1.23
# }
```

---

## 📡 API 端點

### WebSocket（實時推送）
```
ws://localhost:8000/ws/ai-coach/{session_id}
```
- 自動推送穩定偵測與建議
- 最低延遲

### REST API（查詢）
```
GET /api/ai-coach/result/{session_id}
```
- 隨時查詢最新結果

### 調試
```
GET /api/ai-coach/detector-state/{session_id}
POST /api/ai-coach/reset/{session_id}
```

---

## 🔧 在 OpenCV 主程式中的整合

### 步驟 1：初始化
```python
from ai_coach.client import AICoachManager

ai_coach = AICoachManager(
    vllm_api_url="http://10.0.0.100:8000/v1/chat/completions"
)
```

### 步驟 2：主推論迴圈
```python
def process_frame(frame, session_id="game_1"):
    # YOLO 推論
    results = tracker.detect(frame)
    
    # 提取球座標
    balls = [(cx, cy) for detection in results]
    
    # AI Coach 分析
    is_stable = ai_coach.update(balls, session_id)
    
    # 如果穩定，取得建議
    if is_stable:
        result = AICoachManager.get_global_result(session_id)
        # 將結果顯示或發送給 UI
```

### 步驟 3：前端顯示（React）
```tsx
const { analysis } = useAICoach('game_1');

if (analysis) {
  return (
    <div className="ai-coach">
      <p>💬 {analysis.semantic_description}</p>
      <p>🎯 {analysis.recommendation}</p>
    </div>
  );
}
```

---

## ⚙️ 配置參數

### StabilityDetector
| 參數 | 默認值 | 說明 |
|------|-------|------|
| `BUFFER_SIZE` | 60 | 滾動窗口幀數 (≈1秒@60FPS) |
| `DISPLACEMENT_THRESHOLD` | 2.0 | 穩定判斷閾值 (像素) |
| `STABILITY_DURATION` | 60 | 需要穩定的幀數 |
| `MOVEMENT_THRESHOLD` | 5.0 | 冷卻退出閾值 (像素) |

### AICoachManager
| 參數 | 默認值 | 說明 |
|------|-------|------|
| `vllm_api_url` | localhost:8000 | vLLM API 地址 |
| `vllm_model` | Llama-2-7b | 模型名稱 |
| `table_width` | 1920 | 球桌寬度 (像素) |
| `table_height` | 1080 | 球桌高度 (像素) |

---

## 📊 結果數據結構

```python
@dataclass
class AnalysisResult:
    timestamp: str                      # ISO 8601 時間戳
    ball_positions: Dict[str, str]      # {'ball_0': '左上角', ...}
    semantic_description: str           # '3顆球在中心...1顆球在右下...'
    recommendation: str                 # 'AI 建議...'
    confidence: float                   # 0-1 之間
    processing_time: float              # 秒
```

---

## 🔌 vLLM 伺服器配置

### 啟動命令（A100）
```bash
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-2-7b-chat-hf \
    --tensor-parallel-size 1 \
    --dtype bfloat16 \
    --port 8000
```

### 測試連接
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 10
  }'
```

---

## 🐛 常見問題

### Q: API 連接超時？
**A:** 
1. 檢查 A100 伺服器是否啟動
2. 驗證 IP 地址和端口：`curl http://10.0.0.100:8000/v1/models`
3. 檢查防火牆設置

### Q: 球總是不穩定？
**A:**
1. 檢查 DISPLACEMENT_THRESHOLD （2 像素可能太嚴格）
2. 驗證 YOLO 座標精度
3. 調整 STABILITY_DURATION （默認 60 幀）

### Q: 建議質量差？
**A:**
1. 檢查 vLLM 當前模型
2. 確保座標語意化正確
3. 增加訓練數據或調整提示詞

### Q: 如何多會話並行？
**A:**
```python
# 不同 session_id 會獨立追蹤
ai_coach.update(balls_table1, session_id="table_1")
ai_coach.update(balls_table2, session_id="table_2")

# 分別獲取結果
result1 = AICoachManager.get_global_result("table_1")
result2 = AICoachManager.get_global_result("table_2")
```

---

## 📈 性能指標

| 操作 | 時間 | 備註 |
|------|------|------|
| 穩定偵測 | < 1ms | CPU，完全本地 |
| 座標語意化 | < 1ms | CPU，完全本地 |
| vLLM API 往返 | 1-3s | 取決於網絡和模型 |
| 整體響應時間 | 1.5-3.5s | 通常由 vLLM 決定 |

---

## 📖 完整文檔

- **[INTEGRATION_GUIDE.md](ai_coach/INTEGRATION_GUIDE.md)** - 詳細整合步驟
- **[USAGE_EXAMPLES.md](ai_coach/USAGE_EXAMPLES.md)** - 實用代碼範例
- **[TRAINING_GUIDE.md](TRAINING_GUIDE.md)** - 模型微調指南

---

## 🔗 相關模組

- `ai_coach.overlay.StabilityDetector` - 靜止偵測
- `ai_coach.client.{AICoachManager, CoordinateSemanticizer}` - 核心功能
- `ai_coach.train.py` - 模型微調腳本
- `ai_coach.inference.py` - 推論引擎
