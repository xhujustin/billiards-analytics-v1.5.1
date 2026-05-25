# AI Coach 快速入門指南

**最後更新**: 2024年12月  
**版本**: 1.0.0  
**狀態**: ✅ 工程化完成，生產就緒

---

## 🎯 5 分鐘快速開始

### 1️⃣ 安裝

```bash
# 進入項目目錄
cd ai_coach

# 基礎安裝
pip install -e .

# 開發安裝（推薦）
pip install -e ".[dev]"

# 訓練安裝（可選）
pip install -e ".[training]"
```

### 2️⃣ 驗證安裝

```bash
# 查看版本
python -m ai_coach --version

# 查看信息
python -m ai_coach --info

# 運行基本測試
python -m ai_coach --test
```

### 3️⃣ 運行示例

```bash
# 靜態圖像示例
python examples/example_basic.py

# 實時視頻示例
python examples/example_realtime.py
```

### 4️⃣ 運行測試

```bash
# 運行所有測試
make test

# 生成覆蓋率報告
make test-cov
```

---

## 📚 核心功能速查

### 穩定性檢測

```python
from ai_coach import StabilityDetector

detector = StabilityDetector(
    displacement_threshold=2.0,
    stable_threshold=10,
    cooldown_frames=30,
)

# 檢測球位穩定性
is_stable = detector.is_stable([(100, 100), (150, 150)])
```

### 座標語意化

```python
from ai_coach import CoordinateSemanticizer

semanticizer = CoordinateSemanticizer(
    table_width=2800,
    table_height=1400,
)

# 將座標轉換為語意位置
semantic = semanticizer.coordinate_to_semantic(1400, 700)
# 返回: "中心位置"
```

### 視覺化渲染

```python
from ai_coach import draw_coach_panel
import cv2

# 讀取圖像
image = cv2.imread("frame.jpg")

# 渲染教練建議面板
advice_json = {
    "title": "打球建議",
    "sections": {
        "觀察": "白球位置在左上角",
        "建議": "使用進球角度策略",
        "下一步": "瞄準中袋位置",
    }
}

result = draw_coach_panel(image, advice_json, alpha=0.6)
```

### AI 管理器

```python
from ai_coach import AICoachManager

manager = AICoachManager(
    api_url="http://localhost:8000/api/analyze",
    confidence_threshold=0.5,
)

# 更新球位並觸發分析
manager.update(
    balls=[(100, 100), (150, 150), (200, 200)],
    session_id="game_001",
)

# 獲取分析結果
result = manager.get_result("game_001")
```

---

## 🔧 常用命令

| 命令 | 說明 |
|------|------|
| `make install-dev` | 安裝開發依賴 |
| `make test` | 運行測試 |
| `make test-cov` | 測試 + 覆蓋率 |
| `make lint` | 代碼檢查 |
| `make format` | 代碼格式化 |
| `make clean` | 清理構建 |
| `make examples` | 運行示例 |

---

## 📖 完整文檔

| 文檔 | 內容 |
|------|------|
| [README.md](README.md) | 項目介紹和架構 |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | API 快速對照 |
| [VISUALIZATION_GUIDE.md](VISUALIZATION_GUIDE.md) | 視覺化配置 |
| [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) | 系統集成 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 開發指南 |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 項目狀態 |
| [ROADMAP.md](ROADMAP.md) | 項目路線圖 |
| [CHANGELOG.md](CHANGELOG.md) | 版本歷史 |

---

## 💡 常見問題

### Q1: 如何修改 ThresholdA?
```python
detector = StabilityDetector(
    displacement_threshold=3.0,  # 修改此值
    stable_threshold=8,
    cooldown_frames=30,
)
```

### Q2: 如何改變面板位置?
```python
result = draw_coach_panel(
    image,
    advice_json,
    position='left'  # 或 'center'
)
```

### Q3: 如何自定義字體?
查看 [VISUALIZATION_GUIDE.md](VISUALIZATION_GUIDE.md) 的字體配置部分。

### Q4: 如何連接自己的 LLM?
修改 AICoachManager 中的 `api_url` 參數或查看集成指南。

---

## 🚀 部署

### 開發環境
```bash
pip install -e ".[dev]"
make test
```

### 生產環境
```bash
pip install ai-coach
```

### Docker (即將推出)
```bash
docker build -t ai-coach .
docker run ai-coach
```

---

## 📞 支持

- 🐛 **報告 Bug**: [GitHub Issues](https://github.com/xhujustin/billiards-analytics-v1.5.1/issues)
- 💬 **功能建議**: [GitHub Discussions](https://github.com/xhujustin/billiards-analytics-v1.5.1/discussions)
- 📧 **聯繫團隊**: team@example.com

---

## 📋 檢查清單

部署前確保：

- [ ] 已安裝所有依賴 (`pip install -e ".[dev]"`)
- [ ] 測試全部通過 (`make test`)
- [ ] 代碼檢查通過 (`make lint`)
- [ ] 示例程序可運行 (`python examples/example_basic.py`)
- [ ] 文檔已更新 (如有修改)

---

## ✨ 核心特性

✅ **完整功能**
- 實時穩定性檢測
- 智能座標語意化
- 非同步 AI 分析
- 中文視覺化面板

✅ **生產化**
- PEP 517 構建系統
- 自動化測試框架
- 完整文檔和示例
- 開源化配置

✅ **易於集成**
- 簡明 API 設計
- 豐富的代碼示例
- 詳細的集成指南

---

## 📈 下一步

1. **立即體驗**: `python examples/example_basic.py`
2. **深入瞭解**: 閱讀 [README.md](README.md)
3. **集成系統**: 參考 [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
4. **貢獻代碼**: 遵循 [CONTRIBUTING.md](CONTRIBUTING.md)

---

**祝你使用愉快！** 🎱

最後更新: 2024年12月

## 05/25:'修正 vLLM 啟動狀態檢查'

- **範例**: `ai_coach\start.bat` 會檢查 `http://127.0.0.1:8002/v1/models`，且必須解析到 OpenAI-compatible JSON，例如 `{"object":"list","data":[...]}`。
- **規範用法**: 若 `8002` 被其他服務占用並回傳 HTML，腳本不得視為 vLLM 已啟動，會繼續依 `AI_COACH_VLLM_START_MODE` 啟動 vLLM。WSL 模式會先確認有可用 Linux distribution 與可執行的 `AI_COACH_VLLM_PYTHON`。
- **輸出格式**: 非 vLLM JSON 且 port 未被占用會顯示 `vLLM is not responding at ... Starting vLLM...`；port 被其他服務占用會顯示 `Port ... is already occupied by a non-vLLM service. PID: ...`；WSL 未安裝 distribution 會顯示 `WSL is installed, but no Linux distribution is available or running.`。

## 05/07:'新增 Windows start.bat 啟動 AI Coach 服務'

- **範例**: 在 Windows PowerShell 或檔案總管中執行 `ai_coach\start.bat`。
- **規範用法**: 先在 WSL 啟動 vLLM，確認 `http://localhost:8002/v1/chat/completions` 可用，再啟動 `start.bat`。
- **預設設定**:
  - `AI_COACH_HOST=0.0.0.0`
  - `AI_COACH_PORT=8010`
  - `AI_COACH_API_URL=http://localhost:8002/v1/chat/completions`
  - `AI_COACH_MODEL=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit`
- **輸出格式**: 終端會印出 Host、Port、vLLM API 與 Model，服務由 `python -m ai_coach.service` 啟動。
- **Python 執行環境**: `start.bat` 會優先使用專案根目錄 `.venv\Scripts\python.exe`，找不到才改用 `py -3` 或 `python`。
- **Port 衝突處理**: 若 `8010` 已被占用，`start.bat` 會從 `8011` 起往後尋找可用 port，最多檢查 20 個 port。
- **覆蓋設定**: 若需要改 port 或模型，先設定環境變數再執行，例如 `set AI_COACH_PORT=8011`。
## 05/07:'新增 start.bat 自動啟動 vLLM 功能'

- **範例**: 在 Windows PowerShell 或檔案總管中執行 `ai_coach\start.bat`，腳本會先檢查 `http://localhost:8002/v1/models`。若 vLLM 已在執行，直接啟動 AI Coach；若未執行，會開啟獨立 PowerShell 視窗並透過 WSL 啟動 vLLM。
- **規範用法**: 預設使用 WSL 啟動，並載入 `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit`。若要改用 Windows 原生命令，先設定 `AI_COACH_VLLM_START_MODE=windows` 與 `AI_COACH_VLLM_COMMAND`。
- **新增環境變數**:
  - `AI_COACH_AUTO_START_VLLM=1`: 啟用自動啟動；設為 `0` 可回到手動啟動模式。
  - `AI_COACH_VLLM_BASE_URL=http://localhost:8002`: vLLM 健康檢查 base URL。
  - `AI_COACH_VLLM_HOST=0.0.0.0`: vLLM 綁定 host。
  - `AI_COACH_VLLM_PORT=8002`: vLLM OpenAI-compatible API port。
  - `AI_COACH_VLLM_START_MODE=wsl`: 啟動模式，支援 `wsl` 或 `windows`。
  - `AI_COACH_VLLM_PYTHON=/home/lucian039/miniconda3/envs/vllm_env/bin/python`: WSL 內已安裝 vLLM 的 Python。
  - `AI_COACH_VLLM_MAX_MODEL_LEN=8192`: 限制 vLLM 最大 context 長度，避免模型預設超長 context 造成 KV cache 記憶體不足；此值適合同時跑 YOLO 與 vLLM 的長上下文建議設定。
  - `AI_COACH_VLLM_GPU_MEMORY_UTILIZATION=0.6`: vLLM 可使用的 GPU 記憶體比例，在 32GB GPU 約限制為 19.2GB，預留約 12GB 給 YOLO 與影像緩衝。
  - `AI_COACH_VLLM_MAX_NUM_SEQS=1`: 限制同時推理序列數，降低峰值顯存。
  - `AI_COACH_VLLM_COMMAND=%AI_COACH_VLLM_PYTHON% -m vllm.entrypoints.openai.api_server --model %AI_COACH_MODEL% --host %AI_COACH_VLLM_HOST% --port %AI_COACH_VLLM_PORT% --max-model-len %AI_COACH_VLLM_MAX_MODEL_LEN% --gpu-memory-utilization %AI_COACH_VLLM_GPU_MEMORY_UTILIZATION% --max-num-seqs %AI_COACH_VLLM_MAX_NUM_SEQS%`: 實際 vLLM 啟動指令。
- **輸出格式**: 終端會印出 Host、Port、vLLM API、Model 與 Auto-start vLLM 狀態。若需要啟動 vLLM，會顯示等待 `AI_COACH_VLLM_BASE_URL` 就緒的訊息；逾時會停止啟動並提示錯誤。
- **關閉方式**: 關閉 AI Coach 視窗只會停止 AI Coach service；vLLM 在獨立 PowerShell 視窗中執行，需要另外關閉該視窗或停止其中程序。

## 05/13:'升級 AI Coach 8192 長上下文'

- **範例**: `start.bat` 預設使用 `AI_COACH_VLLM_MAX_MODEL_LEN=8192`、`AI_COACH_MAX_TOKENS=220`、`AI_COACH_MAX_PROMPT_CHARS=4500`。
- **規範用法**: RTX 5090 32GB 同時跑 YOLO 與 vLLM 時，先維持 `gpu_memory_utilization=0.6` 與 `max_num_seqs=1`。若 vLLM 無法啟動，先降回 `4096`，再評估是否提高 GPU 使用比例。
- **輸出格式**: AI Coach 視窗會印出完整 `vLLM command`，可用 `set AI_COACH_DRY_RUN=1 && ai_coach\start.bat` 驗證 `--max-model-len 8192`。

## 05/12:'調整 vLLM 顯存限制與 context 長度'

- **範例**: `start.bat` 啟動 vLLM 時會加上 `--max-model-len 8192 --gpu-memory-utilization 0.6 --max-num-seqs 1`。
- **規範用法**: 若模型宣告超長 context，例如 `262144`，但 GPU 可用 KV cache 不足，必須降低 `AI_COACH_VLLM_MAX_MODEL_LEN`；同時跑 YOLO 與 vLLM 時，預設使用 `8192` 與 `gpu_memory_utilization=0.6`，在 RTX 5090 32GB 上保留 YOLO、OpenCV 影像緩衝與長時間運行碎片的餘裕。若 vLLM 無法啟動，先降回 `4096`，再評估是否提高 `gpu_memory_utilization`。
- **輸出格式**: vLLM 成功啟動後，`start.bat` 會繼續等待 `http://localhost:8002/v1/models` 可用，再啟動 AI Coach service。

## 05/07:'調整 vLLM 啟動等待時間'

- **範例**: `start.bat` 預設 `AI_COACH_VLLM_TIMEOUT_SECONDS=300`，最多等待 300 秒讓 vLLM 完成模型載入與 API 啟動。
- **規範用法**: 若 RTX 5090 載入 AWQ 模型仍超過 300 秒，可在執行前覆寫，例如 `set AI_COACH_VLLM_TIMEOUT_SECONDS=600`。
- **輸出格式**: 若超過等待時間仍無法連線，`start.bat` 會顯示 `vLLM did not become ready within ... seconds.`；此時需查看獨立 vLLM PowerShell 視窗中的實際錯誤。
