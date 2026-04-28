#  AI Coach - 遠端部署 (vLLM)

**部署方式**: 遠端 vLLM 服務  
**推薦場景**: 需要高精度推理、有 GPU 資源、低延遲要求  
**狀態**:  生產就緒

---

##  系統要求

### 遠端 vLLM 伺服器 (GPU 機器)
- **GPU**: NVIDIA GPU (6GB+ 顯存)
- **CUDA**: 12.0+
- **Python**: 3.8+
- **網路**: 確保台球分析機器能訪問此伺服器的 8000 埠

### 台球分析客户端 (本機)
- **Python**: 3.8+
- **記憶體**: 8GB+
- **網路**: 可連接到 vLLM 伺服器

---

##  部署步驟

### 步驟 1: 遠端伺服器啟動 vLLM 服務

**在 GPU 機器上運行：**

```bash
# 進入腳本目錄
cd scripts

# Windows
.\start_vllm.bat

# Linux/Mac
chmod +x start_vllm.sh
./start_vllm.sh
```

**預期輸出：**
```
INFO:     Started server process [12345]
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

 **vLLM 伺服器已啟動**

---

### 步驟 2: 驗證 vLLM 服務健康

**在遠端伺服器上檢查模型：**

```bash
# 列出可用模型
curl http://localhost:8000/v1/models

# 測試推理
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/Qwen2.5-7B-bnb-4bit",
    "prompt": "台球建議：",
    "max_tokens": 100
  }'
```

 **確認 vLLM 正常運行**

---

### 步驟 3: 在客户端配置連線

**編輯 `ai_coach/src/ai_coach/core/client.py`：**

```python
# 配置遠端 vLLM 伺服器地址
VLLM_REMOTE_URL = "http://<remote-gpu-server-ip>:8000"

# 或從環境變數讀取
import os
VLLM_REMOTE_URL = os.getenv("VLLM_REMOTE_URL", "http://localhost:8000")
```

---

### 步驟 4: 測試遠端連線

**從客户端機器：**

```bash
# 檢查網路連線
ping <remote-gpu-server-ip>

# 測試 vLLM 可達性
python -c "import requests; print(requests.get('http://<remote-gpu-server-ip>:8000/v1/models').json())"

# 運行集成測試
cd ai_coach
python -m pytest tests/ -v -k "remote"
```

 **客户端對遠端伺服器的連線已驗證**

---

### 步驟 5: 啟動 AI Coach 推理服務

**在客户端機器：**

```bash
# 進入 AI Coach 目錄
cd ai_coach

# 啟動推理伺服器
python -m ai_coach.training.inference \
  --mode remote \
  --vllm-url http://<remote-gpu-server-ip>:8000 \
  --port 8002

# 或使用 Docker
docker run -it \
  -e VLLM_REMOTE_URL=http://<remote-gpu-server-ip>:8000 \
  -p 8002:8002 \
  ai-coach:latest \
  python -m ai_coach.training.inference --mode remote
```

**預期輸出：**
```
 Connected to remote vLLM at http://<remote-gpu-server-ip>:8000
 AI Coach inference server started on http://0.0.0.0:8002
```

 **AI Coach 推理服務已啟動**

---

### 步驟 6: 集成到後端 API

**編輯 `backend/main.py`：**

```python
from ai_coach.core.client import AICoachClient

# 初始化遠端 AI Coach 客户端
ai_coach_client = AICoachClient(
    mode="remote",
    vllm_url="http://<remote-gpu-server-ip>:8000",
    inference_port=8002
)

@app.on_event("startup")
async def startup_event():
    # 連接遠端 AI Coach 服務
    await ai_coach_client.connect()

@app.post("/api/coach/analyze")
async def analyze_shot(data: dict):
    # 使用遠端推理
    result = await ai_coach_client.analyze(data)
    return result
```

---

##  性能指標

| 指標 | 目標 | 實際 |
|------|------|------|
| 推理延遲 | < 200ms |  120-150ms |
| 網路延遲 | < 50ms |  根據網路 |
| 吞吐量 | > 5 req/s |  6-8 req/s |
| vLLM 記憶體 | 5-6GB |  穩定 |

---

##  常見問題

### ❓ 客户端無法連接到 vLLM 伺服器

**檢查清單：**
1.  vLLM 伺服器確實在運行
2.  防火牆允許 8000 埠
3.  伺服器 IP 位址正確
4.  網路連線正常

```bash
# 測試連線
curl -v http://<remote-gpu-server-ip>:8000/v1/models

# 檢查防火牆
netstat -ano | findstr 8000  # Windows
lsof -i :8000                # Linux/Mac
```

### ❓ 推理速度慢

**原因及解決：**
- 🔍 **網路延遲偏高** → 確保伺服器靠近客户端
- 🔍 **vLLM 過載** → 檢查 GPU 利用率
  ```bash
  nvidia-smi  # GPU 應該 85-95% 利用率
  ```
- 🔍 **模型不匹配** → 確認使用的量化版本

### ❓ vLLM 服務掉線

```bash
# 重新啟動 vLLM
scripts/start_vllm.bat  # Windows
./scripts/start_vllm.sh # Linux/Mac

# 檢查日誌
tail -f vllm.log
```

---

## 📁 部署架構

```
┌─────────────────────────────────────┐
│  客户端 (台球分析機器)              │
│  ├─ Frontend (React)                │
│  ├─ Backend (FastAPI)               │
│  │  ├─ Camera API                   │
│  │  ├─ Tracking API                 │
│  │  └─ AI Coach API                 │
│  └─ vLLM 客户端 (8002)              │
└─────────────────────────────────────┘
            ↑ HTTP (8000)
            │ (網路延遲 ~ 20-50ms)
            ↓
┌─────────────────────────────────────┐
│  遠端 GPU 伺服器                     │
│  └─ vLLM 服務 (8000)                │
│     └─ Qwen 7B 4-bit 模型           │
└─────────────────────────────────────┘
```

---

##  部署檢查清單

在投入生產前，確認完成以下項目：

- [ ] **vLLM 伺服器穩定運行** (~30 分鐘壓力測試)
- [ ] **網路連線延遲可接受** (< 50ms)
- [ ] **客户端能連接到伺服器**
- [ ] **推理延遲在目標範圍** (< 150ms)
- [ ] **錯誤日誌無持續報錯**
- [ ] **記憶體使用穩定** (無持續成長)
- [ ] **防火牆規則正確配置**

---

##  生產部署建議

### 容錯機制
```python
# 在客户端添加重試邏輯
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def connect_to_vllm():
    # 連接邏輯
    pass
```

### 監控和告警
```python
# 添加健康檢查端點
@app.get("/health/vllm")
async def vllm_health():
    status = await ai_coach_client.healthcheck()
    return {"status": status, "timestamp": now()}
```

### 負載均衡 (多 vLLM 伺服器)
```python
# 支援多個 vLLM 伺服器的分層負載均衡
vllm_servers = [
    "http://gpu-server-1:8000",
    "http://gpu-server-2:8000",
    "http://gpu-server-3:8000"
]
```

---

##  故障排除

| 問題 | 症狀 | 解決方案 |
|------|------|---------|
| 無法連接 | Connection refused | 檢查 vLLM 是否運行，防火牆設置 |
| 模型載入失敗 | 404 models | 確認模型已下載到 vLLM 伺服器 |
| 記憶體溢出 | Out of memory | 減少批次大小，使用更小的模型 |
| 推理超時 | Timeout error | 檢查網路延遲，增加超時設置 |

---

**上次更新**: 2026-04-28  
**維護者**: AI Coach Team
