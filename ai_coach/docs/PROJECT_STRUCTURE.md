# AI Coach 項目結構說明

此文檔說明重組後的項目結構。

## 最終目錄結構

```
ai_coach/
│
├── src/ai_coach/                      # 主源代碼包 ⭐
│   ├── __init__.py                    # 包初始化和主導出
│   ├── __main__.py                    # CLI 入口點
│   │
│   ├── core/                          # 核心模塊
│   │   ├── __init__.py
│   │   ├── overlay.py                 # 穩定性檢測 (620行)
│   │   ├── client.py                  # AICoachManager (450+ 行)
│   │   └── visualizer.py              # 視覺化渲染 (550+ 行)
│   │
│   ├── training/                      # 訓練和推論
│   │   ├── __init__.py
│   │   ├── train.py                   # 模型訓練 (390行)
│   │   └── inference.py               # 推論引擎 (180行)
│   │
│   └── utils/                         # 工具模塊
│       ├── __init__.py
│       ├── translator.py              # 翻譯工具
│       └── trigger.py                 # 觸發邏輯
│
├── docs/                              # 完整文檔 📚
│   ├── README.md                      # 項目主文檔
│   ├── ROADMAP.md                     # 開發路線圖
│   ├── CHANGELOG.md                   # 版本歷史
│   ├── PROJECT_STATUS.md              # 項目狀態匯總
│   ├── INDEX.md                       # 文檔索引
│   │
│   ├── guides/                        # 開發和使用指南
│   │   ├── QUICKSTART.md              # 5分鐘快速開始
│   │   ├── DEVELOPMENT.md             # 開發工作流
│   │   ├── INTEGRATION_GUIDE.md       # 系統集成指南
│   │   └── VISUALIZATION_GUIDE.md     # 視覺化配置
│   │
│   └── api/                           # API 文檔
│       ├── QUICK_REFERENCE.md         # API 快速參考
│       └── USAGE_EXAMPLES.md          # 代碼示例
│
├── tests/                             # 測試套件 🧪
│   ├── __init__.py
│   ├── test_detector.py               # 穩定性檢測測試 (7個案例)
│   └── [...待添加更多測試...]
│
├── examples/                          # 示例程序 💡
│   ├── example_basic.py               # 靜態圖像示例
│   ├── example_realtime.py            # 實時視頻示例
│   └── [...待添加更多示例...]
│
├── assets/                            # 資源文件 🎨
│   ├── data/
│   │   └── dataset.example.jsonl      # 訓練數據示例
│   └── fonts/                         # 字體文件 (待添加)
│
├── [構建和配置文件]                   # 根目錄配置 ⚙️
│   ├── setup.py                       # setuptools 配置
│   ├── pyproject.toml                 # PEP 517 現代化構建
│   ├── requirements.txt                # 核心依賴
│   ├── requirements_train.txt          # 訓練依賴
│   │
│   ├── pytest.ini                     # Pytest 配置
│   ├── Makefile                       # 開發任務自動化
│   │
│   ├── LICENSE                        # MIT 開源協議
│   ├── CONTRIBUTING.md                # 貢獻指南
│   ├── .gitignore                     # Git 忽略規則
│   │
│   └── ENGINEERING_CHECKLIST.py       # 工程化驗證清單
```

## 文件分類說明

### 📦 源代碼 (src/ai_coach/)
- **core/**: 核心功能模塊
  - overlay.py: 穩定性檢測系統
  - client.py: AICoachManager 整合
  - visualizer.py: OpenCV 渲染和中文支持
  
- **training/**: LLM 訓練和推論
  - train.py: Unsloth + LoRA 微調
  - inference.py: 模型推論引擎
  
- **utils/**: 工具函式庫
  - translator.py: 多語言支持
  - trigger.py: 事件觸發機制

### 📚 文檔 (docs/)
- **guides/**: 本地開發和使用指南
  - QUICKSTART.md: 最快入門方式
  - DEVELOPMENT.md: 完整開發指南
  - INTEGRATION_GUIDE.md: 如何集成到系統
  - VISUALIZATION_GUIDE.md: 字體和渲染配置
  
- **api/**: 編程接口文檔
  - QUICK_REFERENCE.md: API 速查表
  - USAGE_EXAMPLES.md: 代碼示例

### 🧪 測試 (tests/)
- 使用 pytest 框架
- 組織方式應與 src/ai_coach/ 對應

### 💡 示例 (examples/)
- 各種實際使用案例
- 可獨立運行

### ⚙️ 配置 (根目錄)
所有構建和開發配置保留在根目錄，符合 Python 標準實踐。

## 關鍵改進

✅ **清晰的包結構**
- 代碼組織到邏輯子包中
- 易於維護和擴展

✅ **規範的文檔組織**
- 分離指南、API 文檔等
- 易於查找和導航

✅ **標準的項目佈局**
- 遵循 Python 社區標準
- 符合 setuptools 期望

✅ **減少根目錄混亂**
- 只保留必要的配置文件
- 更容易找到重要文件

## 導入變化

使用新結構後，導入方式變為：

```python
# 從新位置導入
from ai_coach.core.overlay import StabilityDetector
from ai_coach.core.client import AICoachManager
from ai_coach.training.train import ModelTrainer

# 或使用主包導出（在 __init__.py 中重新導出）
from ai_coach import StabilityDetector, AICoachManager
```

## 下一步

1. **更新 pyproject.toml**: 確保包發現規則正確
2. **更新 __init__.py**: 檢查和更新導入路徑
3. **測試導入**: `python -m ai_coach --test`
4. **運行示例**: `python examples/example_basic.py`

---

**工程化完成！** 🎉

此結構現在符合 Python 社區標準和最佳實踐。
