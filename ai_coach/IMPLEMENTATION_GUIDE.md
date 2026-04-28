# Qwen AI 教練系統完整實施指南

## 📐 系統架構

```
┌─────────────────────────────────────────────────────────┐
│                      前端應用 (React)                    │
│  ┌──────────────┐                ┌──────────────────┐  │
│  │ 遊戲場景面板  │◄──────────────►│  AI 教練面板      │  │
│  └──────────────┘                └──────────────────┘  │
│         │                               ▲              │
│         │ 球位數據 (WebSocket)          │              │
│         ▼                               │ 建議推送      │
├─────────────────────────────────────────────────────────┤
│                    WebSocket 網關 (FastAPI)             │
│  ┌─────────────────────────────────────────────────────┐│
│  │ • 連接管理 (ConnectionManager)                      ││
│  │ • 訊息分發 (MessageRouter)                          ││
│  │ • 心跳保活 (Heartbeat)                              ││
│  └─────────────────────────────────────────────────────┘│
│         │                               ▲              │
│         ▼                               │              │
│  ┌──────────────────────────────────────┘              │
│  │ 建議隊列 + 非同步生成器                              │
│  │ (SuggestionQueue + SuggestionGenerator)              │
│  └──────────────────────────────────────┐              │
│         │                               │              │
│         ▼                               ▼              │
├─────────────────────────────────────────────────────────┤
│    AI 模型推論 (Qwen-2.5-7B + 4-bit 量化)              │
│  ┌──────────────────────────────────────────────────────┐│
│  │ • 推論引擎 (InferenceEngine)                         ││
│  │ • 批推論優化 (BatchInferenceOptimizer)               ││
│  │ • KV-Cache 優化                                     ││
│  └──────────────────────────────────────────────────────┘│
│         │                               ▲              │
│         │ 基礎建議                      │              │
│         ▼                               │              │
│  ┌──────────────────────────────────────┘              │
│  │ 個性化調整 (PersonalizedAdvisor)                     │
│  │ • 玩家畫像                                           │
│  │ • 成功率追蹤                                         │
│  │ • A/B 測試                                          │
│  └──────────────────────────────────────┐              │
│         │                               │              │
│         ▼                               ▼              │
├─────────────────────────────────────────────────────────┤
│           數據源 (API + 資料庫)                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │ GET /api/stats/player - 玩家統計                    ││
│  │ GET /api/recordings - 遊戲錄像                      ││
│  │ POST /api/recording/event - 事件記錄                ││
│  │ GET /api/practice/state - 練習狀態                  ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 分步實施流程

### 第 1 步：準備訓練數據集

```bash
# 1. 進入 ai_coach 目錄
cd ai_coach

# 2. 運行數據集構建工具
python tools/dataset_builder.py \
    --output ./billiards_training_data \
    --api-url http://localhost:8001

# 輸出：
# - billiards_training_data/billiards_qwen_dataset.jsonl
# - billiards_training_data/dataset_report.json
```

**預期結果：**
- 500-1000 條訓練樣本
- 包含 3 個玩家等級的變化
- 覆蓋常見球位和球型

### 第 2 步：微調 Qwen 模型

```bash
# 1. 安裝訓練依賴
pip install -e ".[training]"

# 2. 運行微調
python src/ai_coach/training/train.py \
    --model unsloth/Qwen2.5-7B-bnb-4bit \
    --dataset ./billiards_training_data/billiards_qwen_dataset.jsonl \
    --output ./models/qwen_billiards_lora \
    --epochs 3

# 輸出：
# - models/qwen_billiards_lora/adapter_config.json
# - models/qwen_billiards_lora/adapter_model.bin
# - models/qwen_billiards_merged/model (合併後)
```

**關鍵參數：**
- LoRA rank: 16（平衡速度和質量）
- Learning rate: 2e-4
- Batch size: 4（4-bit 量化）
- Epochs: 3（避免過擬合）

### 第 3 步：性能優化和基準測試

```bash
# 執行性能優化基準測試
python tools/performance_optimizer.py \
    --model unsloth/Qwen2.5-7B-bnb-4bit \
    --test-quantization \
    --test-batch-size \
    --test-kv-cache

# 預期結果：
# FP16:  Latency ~200ms, Memory ~14GB
# 8-bit: Latency ~180ms, Memory ~9GB
# 4-bit: Latency ~160ms, Memory ~5GB ✅ 推薦
```

**優化決策：**
| 方案 | 延遲 | 內存 | 品質 | 推薦用途 |
|------|------|------|------|---------|
| FP16 | 200ms | 14GB | 最佳 | 離線分析 |
| 8-bit | 180ms | 9GB | 很好 | 演示 |
| 4-bit | 160ms | 5GB | 良好 | 生產環境 ✅ |

### 第 4 步：後端集成

**模塊 1: 初始化推論引擎**（backend/main.py）

```python
from ai_coach.training.inference import InferenceEngine

# 在啟動時初始化
inference_engine = InferenceEngine(
    model_path="./models/qwen_billiards_merged",
    lora_path=None,  # 已合併
    use_quantized=True,
    max_seq_length=2048,
)
inference_engine.load_model()

print("✅ AI Coach inference engine loaded")
```

**模塊 2: 初始化 WebSocket 系統**（backend/main.py）

```python
from ai_coach.tools.websocket_coach import (
    SuggestionQueue,
    SuggestionGenerator,
    WebSocketConnectionManager,
    CoachWebSocketRouter,
)

# 初始化各個組件
suggestion_queue = SuggestionQueue(max_queue_size=1000)

suggestion_generator = SuggestionGenerator(
    inference_engine=inference_engine,
    suggestion_queue=suggestion_queue
)

connection_manager = WebSocketConnectionManager(suggestion_queue)

coach_router = CoachWebSocketRouter(
    suggestion_queue=suggestion_queue,
    suggestion_generator=suggestion_generator,
    connection_manager=connection_manager
)

# 啟動後台建議生成任務
async def startup_event():
    # 啟動建議生成器
    asyncio.create_task(
        suggestion_generator.process_suggestions_forever()
    )

app.add_event_handler("startup", startup_event)
```

**模塊 3: 新增 WebSocket 端點**（backend/main.py）

```python
@app.websocket("/ws/coach")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query(...),
):
    """AI 教練 WebSocket 端點。
    
    使用方式（前端）：
        const ws = new WebSocket(
            `ws://localhost:8001/ws/coach?session_id=${session_id}`
        );
    """
    await coach_router.websocket_endpoint(websocket, session_id)
```

**模塊 4: 集成個性化建議引擎**（backend/main.py）

```python
from ai_coach.tools.personalized_advisor import (
    PlayerProfileBuilder,
    SuccessRateTracker,
    PersonalizedAdvisor,
)

# 初始化個性化系統
profile_builder = PlayerProfileBuilder(api_base_url="http://localhost:8001")
success_tracker = SuccessRateTracker()

personalized_advisor = PersonalizedAdvisor(
    base_advisor=inference_engine,  # 使用推論引擎作為基礎
    profile_builder=profile_builder,
    success_tracker=success_tracker,
)

# 修改建議生成邏輯（在 SuggestionGenerator 中）
def _generate_suggestion_sync(self, request: Dict) -> Dict:
    """改進的同步生成方法。"""
    
    # 獲取個性化建議
    suggestion_dict = \
        self.personalized_advisor.generate_personalized_advice(
            game_state=request["game_state"],
            player_name=request["player_info"]["name"],
            shot_type=request["game_state"].get("shot_type", "straight"),
        )
    
    return suggestion_dict
```

### 第 5 步：前端集成

**創建文件：frontend/src/hooks/useCoachWebSocket.ts**

```typescript
import { useEffect, useRef, useState } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';

export const useCoachWebSocket = (sessionId: string) => {
  const wsRef = useRef<ReconnectingWebSocket | null>(null);
  const [suggestion, setSuggestion] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8001/ws/coach?session_id=${sessionId}`;
    
    wsRef.current = new ReconnectingWebSocket(wsUrl, [], {
      reconnectInterval: 3000,
      maxReconnectAttempts: 5,
    });
    
    wsRef.current.addEventListener('open', () => {
      setIsConnected(true);
    });
    
    wsRef.current.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      
      if (msg.type === 'coach_suggestion') {
        setSuggestion(msg.data);
        
        // 自動隱藏
        setTimeout(
          () => setSuggestion(null),
          msg.data.display_duration_ms || 5000
        );
      }
    });
    
    return () => wsRef.current?.close();
  }, [sessionId]);

  const requestSuggestion = (gameState, playerInfo) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'suggestion_request',
        data: { game_state: gameState, player_info: playerInfo },
      }));
    }
  };

  return { suggestion, isConnected, requestSuggestion };
};
```

**集成到練習頁面：frontend/src/pages/PracticePage.tsx**

```typescript
import { useCoachWebSocket } from '../hooks/useCoachWebSocket';

export const PracticePage: React.FC = () => {
  const { suggestion, isConnected, requestSuggestion } = 
    useCoachWebSocket(session.id);

  // 當球位穩定時自動請求建議
  useEffect(() => {
    if (gameState.is_stable) {
      requestSuggestion(gameState, {
        name: player.name,
        skill_level: player.skill_level,
      });
    }
  }, [gameState.is_stable]);

  return (
    <div className="practice-container">
      <GameArea />
      
      {suggestion && (
        <CoachPanel
          title={suggestion.title}
          advice={suggestion.advice_text}
          confidence={suggestion.confidence_score}
          priority={suggestion.priority}
        />
      )}
    </div>
  );
};
```

### 第 6 步：A/B 測試和持續優化

**啟動 A/B 測試**

```python
from ai_coach.tools.personalized_advisor import ABTestFramework

# 初始化測試框架
ab_test = ABTestFramework()

# 註冊變體
ab_test.register_variant(
    "variant_verbose",
    "詳細建議",
    "含有基礎提示的建議（新手用）",
    is_control=True
)

ab_test.register_variant(
    "variant_quick",
    "快速建議",
    "簡潔、可立即執行的建議（進階用）"
)

# 為用戶分配變體（50/50 隨機分配）
def assign_test_variant(player_id: str):
    variant = random.choice(["variant_verbose", "variant_quick"])
    ab_test.assign_user_variant(player_id, variant)

# 記錄轉化（用戶是否採納建議）
def record_suggestion_adoption(player_id: str, success: bool):
    ab_test.record_impression(player_id)
    ab_test.record_conversion(player_id, success)
```

**監控指標**

```bash
# 每日報告
curl http://localhost:8001/api/coach/ab-test-report

# 預期結果：
{
  "variant_verbose": {
    "impressions": 450,
    "conversions": 315,
    "conversion_rate": 0.70
  },
  "variant_quick": {
    "impressions": 470,
    "conversions": 376,
    "conversion_rate": 0.80  # 勝出！
  },
  "statistical_significance": {
    "p_value": 0.032,
    "is_significant": true,
    "winner": "variant_quick"
  }
}
```

---

## 📊 監控和調試

### 實時監控儀表板

```bash
# 查詢 WebSocket 連接數
curl http://localhost:8001/api/coach/connections

# 查詢隊列狀態
curl http://localhost:8001/api/coach/queue-status

# 查詢推論性能指標
curl http://localhost:8001/api/coach/performance-metrics
```

### 日誌監控

```bash
# 監控建議生成延遲
grep "Suggestion generated" backend/logs/coach.log | \
  tail -100 | \
  awk '{print $NF}' | \
  sort -n | \
  tail -5

# 預期結果（P95 延遲）：
# ~150ms
```

### 常見問題除錯

**問題 1: WebSocket 連接頻繁斷開**
```python
# 增加心跳間隔（前端）
const ws = new ReconnectingWebSocket(url, [], {
  heartbeatInterval: 30000,  # 30 秒一次
});
```

**問題 2: 建議品質不佳**
```bash
# 1. 檢查訓練數據質量
python tools/dataset_builder.py --validate-only

# 2. 檢查微調模型效果
python -c "
from ai_coach.training.inference import InferenceEngine
engine = InferenceEngine('./models/qwen_billiards_merged')
print(engine.generate('測試提示語'))
"

# 3. 查看個性化調整是否生效
grep "personalized_adjustment" backend/logs/coach.log
```

**問題 3: 延遲過高（>500ms）**
```bash
# 1. 檢查批大小
# 應設為 4-8（太小會浪費資源，太大會增加延遲）

# 2. 啟用 KV-Cache
# 在推論時使用 use_cache=True

# 3. 檢查 GPU 利用率
nvidia-smi  # 應該 > 80%

# 4. 如果仍慢，考慮知識蒸餾
python tools/performance_optimizer.py --distill-model
```

---

## ⚙️ 配置文件

### config/coach_config.yaml

```yaml
# 模型配置
model:
  name: "Qwen2.5-7B"
  quantization: "4bit"
  lora_rank: 16
  max_seq_length: 2048

# 推論配置
inference:
  max_batch_size: 8
  temperature: 0.7
  top_p: 0.95
  max_length: 256
  use_cache: true

# WebSocket 配置
websocket:
  max_connections: 100
  heartbeat_interval: 30
  message_queue_size: 1000

# 個性化配置
personalization:
  enable_player_profiling: true
  enable_ab_testing: true
  update_profile_interval: 3600  # 秒

# 性能目標
performance:
  target_latency_ms: 200
  max_memory_mb: 6000
  target_throughput_per_sec: 10
```

---

## 📈 成功指標

| 指標 | 目標 | 現況 | 狀態 |
|------|------|------|------|
| 平均推論延遲 | <200ms | ~160ms | ✅ |
| 吞吐量 | >5 samples/sec | ~6 samples/sec | ✅ |
| 建議採納率 | >60% | TBD | 測試中 |
| 玩家滿意度 | >4/5 | TBD | 待測 |
| 系統可用性 | >99% | 部署後測 | 待測 |

---

## 🔄 持續迭代

### 週期 1（第 1-2 週）
- [ ] 啟動 WebSocket 系統
- [ ] 初始化基礎推論引擎
- [ ] 進行延遲基準測試

### 週期 2（第 3-4 週）
- [ ] 啟動 A/B 測試（詳細 vs 簡潔建議）
- [ ] 監控建議採納率
- [ ] 收集玩家反饋

### 週期 3（第 5-6 週）
- [ ] 基於 A/B 結果優化提示語模板
- [ ] 進行知識蒸餾（如需要）
- [ ] 優化個性化邏輯

### 週期 4（第 7-8 週）
- [ ] 大規模部署
- [ ] 監控系統穩定性
- [ ] 定期更新訓練數據

---

## 🎯 下一步

1. **數據質量改進**
   - 收集更多高品質訓練數據（目標 5000+）
   - 邀請專業教練複審建議

2. **特徵工程**
   - 引入球型識別（YOLO 輸出）
   - 引入對手分析

3. **多玩家個性化**
   - 基於玩家風格匹配（激進 vs 保守）
   - 基於對手風格調整建議

4. **實時反饋自適應**
   - 根據玩家採納情況實時調整建議
