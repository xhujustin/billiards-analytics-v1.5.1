# 🎱 AI Coach

**臺球 AI 助教系統** — 實時穩定性檢測、語意轉換、LLM 整合、中文視覺化

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org)
[![Version: 1.0.0](https://img.shields.io/badge/Version-1.0.0-green)]()

---

## ⚡ 快速開始

```bash
# 安裝
pip install -e ".[dev]"

# 測試
make test

# 運行示例
python examples/example_basic.py
```

詳見 **[完整文檔](docs/README.md)** 和 **[快速開始指南](docs/guides/QUICKSTART.md)**

---

## 📦 功能特性

✅ **穩定性檢測** — 60幀滾動窗口，實時識別球位靜止  
✅ **語意轉換** — 坐標轉自然語言方位（"左上角"、"底袋位"）  
✅ **AI 整合** — 非同步 vLLM API 調用，實時建議  
✅ **中文視覺化** — 半透明教練面板，跨平台支持  
✅ **模型訓練** — Unsloth + LoRA 微調，4位量化  
✅ **工程化** — PEP 517 構建、pytest 測試、Makefile 自動化  

---

## 📚 文檔結構

- **[docs/README.md](docs/README.md)** — 完整項目介紹
- **[docs/guides/QUICKSTART.md](docs/guides/QUICKSTART.md)** — 5 分鐘快速開始
- **[docs/guides/DEVELOPMENT.md](docs/guides/DEVELOPMENT.md)** — 開發工作流
- **[docs/api/QUICK_REFERENCE.md](docs/api/QUICK_REFERENCE.md)** — API 快速參考
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** — 項目結構說明

---

## 📂 項目結構

```
ai_coach/
├── src/ai_coach/              # 源代碼包 ⭐
│   ├── core/                  # 核心模塊（穩定性、語意、視覺化）
│   ├── training/              # 訓練和推論
│   └── utils/                 # 工具模塊
├── docs/                      # 完整文檔
├── tests/                     # 測試套件
├── examples/                  # 示例程序
├── assets/                    # 資源文件
└── [配置文件]                 # pyproject.toml, setup.py, Makefile...
```

詳見 **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)**

---

## 🚀 核心模塊

| 模塊 | 文件 | 說明 |
|------|------|------|
| **穩定性偵測** | `core/overlay.py` (620行) | 60幀滾動窗口位移分析 |
| **核心管理** | `core/client.py` (450+行) | AICoachManager + 語意轉換 |
| **視覺化** | `core/visualizer.py` (550+行) | OpenCV + PIL 中文渲染 |
| **訓練** | `training/train.py` (390行) | Unsloth + LoRA 微調 |
| **推論** | `training/inference.py` (180行) | 模型加載和推論 |

---

## 💡 使用示例

```python
from ai_coach import StabilityDetector, draw_coach_panel
import cv2

# 檢測球位穩定性
detector = StabilityDetector()
is_stable = detector.is_stable([(100, 100), (150, 150)])

# 渲染教練建議
image = cv2.imread("frame.jpg")
advice = {
    "title": "打球建議",
    "sections": {
        "觀察": "白球在左上角",
        "建議": "瞄準中袋"
    }
}
result = draw_coach_panel(image, advice)
```

詳見 **[完整示例](docs/api/USAGE_EXAMPLES.md)**

---

## 🔧 開發命令

```bash
make test          # 運行測試
make lint          # 代碼檢查
make format        # 代碼格式化
make clean         # 清理構建
```

詳見 **[開發指南](docs/guides/DEVELOPMENT.md)**

---

## 📈 項目狀態

- ✅ 核心功能完整
- ✅ 工程化完成
- ✅ 文檔齊全
- ⏳ 測試擴展中 (15% → 目標 90%)
- ⏳ CI/CD 設置中

詳見 **[項目狀態](docs/PROJECT_STATUS.md)** 和 **[路線圖](docs/ROADMAP.md)**

---

## 📞 支持

- 📖 **文檔**: [docs/](docs/)
- 🐛 **報告 Bug**: [GitHub Issues](https://github.com/xhujustin/billiards-analytics-v1.5.1/issues)
- 💬 **功能建議**: [Discussions](https://github.com/xhujustin/billiards-analytics-v1.5.1/discussions)

---

## ⚖️ License

MIT License © 2024 Billiards Analytics Team

詳見 [LICENSE](LICENSE) 和 [CONTRIBUTING.md](CONTRIBUTING.md)

---

**準備好了嗎？** 👉 [快速開始](docs/guides/QUICKSTART.md)
