# 🎯 AI Coach 部署指南 - 選擇您的方式

**選擇正確的部署方式對系統性能至關重要**

---

## 📊 部署方式對比

|  | **遠端 vLLM** | **近端 YOLO** |
|---|---|---|
| **主要用途** | 文本推理、建議生成 | 物體檢測、實時追蹤 |
| **推理延遲** | 120-150ms | 15-30ms |
| **GPU 要求** | 6GB+ (遠端) | 2GB+ (本機) |
| **離線工作** | ❌ 否 | ✅ 是 |
| **實時性** | ⚠️ 尚可 | ✅ 優秀 |
| **部署複雜度** | 中 | 簡 |
| **網路依賴** | ⚠️ 是 | ✅ 否 |
| **推薦場景** | AI 建議、策略分析 | 實時檢測、邊界計算 |

---

## 🤔 我應該選擇哪一個？

### ✅ 選擇 **遠端 vLLM** 如果您需要：

- 🤖 **AI 台球教練建議**
  - "基於這個局面，最佳下一步是..."
  - 高精度策略分析
  - 個性化建議

- 💡 **複雜文本推理**
  - 長文本輸出 (> 500 詞)
  - 多層邏輯推理
  - 知識庫檢索

- 🚀 **高精度輸出**
  - 推理精度優先於速度
  - 能接受 200ms 延遲

- 🖥️ **有專用 GPU 伺服器**
  - 獨立的高性能 GPU 設備
  - 可與多個台球機器共享

### ✅ 選擇 **近端 YOLO** 如果您需要：

- ⚡ **實時物體檢測**
  - < 50ms 響應時間
  - 30+ FPS 視頻處理
  - 即時反饋

- 🎯 **撞球/球桿追蹤**
  - 檢測球位置
  - 追蹤球動軌跡
  - 計算角度/速度

- 🌐 **離線獨立工作**
  - 無網路連接環境
  - 完全本機推理
  - 無外部依賴

- 💰 **有限 GPU 資源**
  - 本機 GPU 2GB+ 足夠
  - 無需額外伺服器

---

## 💡 推薦組合方案

### 方案 1: **實時系統** (推薦大多數場景)
```
Client Machine:
├─ YOLO (本地) → 實時檢測、追蹤 (8002)
├─ Backend → 融合邏輯、API 層 (8001)
└─ Frontend → UI/UX (5173)

遠端：
└─ vLLM 伺服器 → AI 建議 (可選，延遲可接受時)
```

**優點：**
- ✅ 99% 的操作即時響應
- ✅ 遠端 vLLM 僅用於非時間緊迫的分析
- ✅ 用戶體驗流暢

---

### 方案 2: **純本地方案** (無網路環境)
```
Client Machine:
├─ YOLO (本地) → 物體檢測 (8002)
├─ 輕量級文本模型 → 本地建議 (3B 模型)
├─ Backend → 協調層 (8001)
└─ Frontend → UI (5173)

遠端：
└─ 無 (完全獨立)
```

**優點：**
- ✅ 完全離線工作
- ✅ 無網路延遲
- ✅ 隱私完全保護

---

### 方案 3: **純遠端方案** (主要依賴 AI)
```
Client Machine:
└─ Frontend (5173) + 輕量 API

遠端 GPU 伺服器：
├─ vLLM → 文本推理 (8000)
├─ YOLO → 物體檢測 (8002)
└─ Backend → 業務邏輯 (8001)
```

**優點：**
- ✅ 客户端配置簡單
- ✅ 伺服器集中管理
- ✅ 易於升級 (更換模型)

---

## 🚀 快速開始

### 我想要最快的開始

**→ 選擇 YOLO 本地方案**

```bash
# 1. 進入 ai_coach
cd ai_coach

# 2. 安裝依賴 (5 分鐘)
pip install -e ".[yolo]"

# 3. 啟動服務 (即時)
python -m ai_coach.training.inference --mode local --model-type yolo --port 8002

# ✅ 完成！本地推理已就緒
```

→ 參考完整指南: [DEPLOYMENT_LOCAL_YOLO.md](DEPLOYMENT_LOCAL_YOLO.md)

---

### 我想要最精確的 AI 建議

**→ 選擇遠端 vLLM 方案**

```bash
# 1. 準備遠端 GPU 伺服器
cd scripts
./start_vllm.bat  # 或 Linux: ./start_vllm.sh

# 2. 在客户端連接
export VLLM_REMOTE_URL=http://<gpu-server-ip>:8000

# 3. 啟動 AI Coach
cd ai_coach
python -m ai_coach.training.inference --mode remote --port 8002

# ✅ 完成！遠端推理已就緒
```

→ 參考完整指南: [DEPLOYMENT_REMOTE_VLLM.md](DEPLOYMENT_REMOTE_VLLM.md)

---

### 我想要兩個都用 (混合方案)

**→ 最靈活的配置**

```python
# backend/main.py
from ai_coach.core.client import AICoachClient

# 本地快速檢測
yolo_client = AICoachClient(mode="local", model_type="yolo")

# 遠端精確建議 (可選)
vllm_client = AICoachClient(mode="remote", vllm_url="http://gpu-server:8000")

@app.post("/api/coach/analyze")
async def analyze(data: dict):
    # 1. 快速本地檢測
    detections = await yolo_client.detect(data["frame"])
    
    # 2. 可選遠端建議
    if data.get("request_suggestions"):
        suggestions = await vllm_client.generate_advice(detections)
        return {"detections": detections, "suggestions": suggestions}
    
    return {"detections": detections}
```

→ 參考完整指南: [DEPLOYMENT_REMOTE_VLLM.md](DEPLOYMENT_REMOTE_VLLM.md) + [DEPLOYMENT_LOCAL_YOLO.md](DEPLOYMENT_LOCAL_YOLO.md)

---

## ⚙️ 硬體要求

### 僅用 YOLO (本地)

```yaml
最低配置:
  CPU: Intel i5 或同級
  RAM: 8GB
  GPU: NVIDIA GTX 1050 (2GB)
  儲存: 10GB

推薦配置:
  CPU: Intel i7 / Ryzen 5 以上
  RAM: 16GB
  GPU: RTX 3060 (12GB)
  儲存: 20GB
```

### 僅用 vLLM (遠端)

```yaml
用戶端:
  CPU: Intel i5 或同級
  RAM: 8GB
  GPU: 無需 (可選)
  儲存: 5GB

遠端伺服器:
  CPU: Xeon 或同級
  RAM: 32GB+
  GPU: RTX 4090 / A100 (24GB+)
  儲存: 50GB
```

### 混合方案 (YOLO + vLLM)

```yaml
用戶端:
  CPU: Intel i7 / Ryzen 5
  RAM: 16GB
  GPU: RTX 3060 (12GB)
  儲存: 20GB

遠端伺服器:
  CPU: Xeon 或同級
  RAM: 32GB+
  GPU: RTX 4090 / A100 (24GB+)
  儲存: 50GB
```

---

## 📋 決策樹

```
開始
 │
 ├─ 有遠端 GPU 伺服器?
 │  ├─ 是 → 需要實時反應?
 │  │      ├─ 是 → 混合方案 (YOLO + vLLM)
 │  │      └─ 否 → 遠端方案 (vLLM)
 │  │
 │  └─ 否 → 需要 AI 建議?
 │         ├─ 是 → 本地輕量模型
 │         └─ 否 → YOLO 方案
 │
 └─ 確定方案後
    └─ 跳轉到對應的部署指南
```

---

## 🔄 從一個方案遷移到另一個

### 從 vLLM → 添加 YOLO

```bash
# 1. 安裝 YOLO 依賴
pip install ultralytics opencv-python

# 2. 更新 backend
# - 添加 YOLO 客户端初始化
# - 創建物體檢測端點

# 3. 測試
python -m pytest tests/test_yolo_integration.py
```

### 從 YOLO → 添加 vLLM

```bash
# 1. 準備遠端伺服器
# scripts/start_vllm.bat

# 2. 更新環境
export VLLM_REMOTE_URL=http://<server-ip>:8000

# 3. 更新 backend
# - 添加 vLLM 客户端初始化
# - 創建建議端點

# 4. 測試
python -m pytest tests/test_vllm_integration.py
```

---

## ✅ 部署檢查清單

選擇方案後，按照相應指南進行：

**YOLO 本地方案：**
- [ ] [DEPLOYMENT_LOCAL_YOLO.md](DEPLOYMENT_LOCAL_YOLO.md) 中的所有步驟

**vLLM 遠端方案：**
- [ ] [DEPLOYMENT_REMOTE_VLLM.md](DEPLOYMENT_REMOTE_VLLM.md) 中的所有步驟

**混合方案：**
- [ ] 兩份指南中的所有步驟

---

## 🤝 需要幫助？

1. **不確定選擇?** → 參考上面的決策樹
2. **部署特定方案?** → 查看對應的部署指南
3. **性能問題?** → 查看各指南中的優化建議
4. **遷移方案?** → 查看上面的遷移步驟

---

## 📞 快速參考

| 問題 | 答案 |
|------|------|
| 最快的響應時間? | YOLO 本地 (15-30ms) |
| 最高的 AI 精度? | vLLM 遠端 (7B 模型) |
| 離線工作? | YOLO 本地 + 輕量模型 |
| 易於部署? | YOLO 本地 (5 分鐘) |
| 最靈活? | 混合方案 |
| 最便宜? | YOLO 本地 (無伺服器) |

---

**上次更新**: 2026-04-28  
**維護者**: AI Coach Team
