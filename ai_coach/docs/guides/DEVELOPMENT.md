# 開發指南

本文檔說明如何開發、測試和發佈 AI Coach。

## 快速開始

### 設置開發環境

```bash
# Clone 倉庫
git clone https://github.com/xhujustin/billiards-analytics-v1.5.1.git
cd ai_coach

# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安裝開發依賴
pip install -e ".[dev]"

# （可選）安裝訓練依賴
pip install -e ".[training]"
```

### 使用 Makefile

```bash
# 查看所有可用命令
make help

# 安裝開發依賴
make install-dev

# 運行測試
make test

# 運行測試並生成覆蓋率報告
make test-cov

# 檢查代碼風格
make lint

# 格式化代碼
make format

# 清理
make clean
```

## 開發工作流程

### 1. 建立功能分支

```bash
git checkout -b feature/my-feature
```

### 2. 編碼

遵循以下規範：
- **PEP 8** 風格
- **Type hints** 類型提示
- **Docstrings** 文檔字符串

### 3. 測試

```bash
# 運行所有測試
pytest tests/ -v

# 運行特定測試
pytest tests/test_detector.py -v

# 運行並生成覆蓋率報告
pytest tests/ --cov=ai_coach --cov-report=html
```

### 4. 代碼風格檢查

```bash
# Linting
flake8 ai_coach/
mypy ai_coach/

# 自動格式化
black ai_coach/ tests/ examples/
```

### 5. 提交並推送

```bash
git add .
git commit -m "feat(module): description"
git push origin feature/my-feature
```

### 6. 創建 Pull Request

1. 在 GitHub 上創建 PR
2. 填寫 PR 模板
3. 等待 CI/CD 檢查和審查

## 項目結構

```
ai_coach/
├── ai_coach/                  # 源代碼包
│   ├── __init__.py           # 包初始化
│   ├── overlay.py            # 穩定性偵測
│   ├── client.py             # 核心管理器
│   ├── visualizer.py         # 視覺化渲染
│   ├── train.py              # 模型訓練
│   └── inference.py          # 推論引擎
│
├── tests/                     # 測試
│   ├── __init__.py
│   ├── test_detector.py
│   └── test_manager.py
│
├── examples/                  # 示例程序
│   ├── example_basic.py
│   └── example_realtime.py
│
├── docs/                      # 文檔
│   ├── INDEX.md
│   ├── README.md
│   ├── QUICK_REFERENCE.md
│   └── VISUALIZATION_GUIDE.md
│
├── setup.py                   # Setup 配置
├── pyproject.toml             # 現代 Python 配置
├── requirements.txt           # 依賴表
├── pytest.ini                 # Pytest 配置
├── Makefile                   # 開發任務
├── .gitignore                 # Git 忽略列表
├── LICENSE                    # MIT 許可證
├── CONTRIBUTING.md            # 貢獻指南
└── DEVELOPMENT.md             # 本文件
```

## 編碼規範

### Python 風格

遵循 PEP 8：
- 行長度：100 字符（使用 Black）
- 縮進：4 個空格
- 命名：snake_case 變數，CamelCase 類

### 類型提示

```python
from typing import List, Dict, Optional

def process_frame(
    image: np.ndarray,
    balls: List[Tuple[float, float]]
) -> Dict[str, Any]:
    """Process frame with ball coordinates."""
    pass
```

### 文檔字符串

```python
def my_function(param1: str, param2: int) -> bool:
    """
    簡短描述。
    
    詳細描述（如需要）。
    
    Args:
        param1: 參數1 說明
        param2: 參數2 說明
        
    Returns:
        bool: 返回值說明
        
    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        True
    """
    pass
```

## 測試編寫

### 單元測試

```python
import pytest
from ai_coach.overlay import StabilityDetector

class TestStabilityDetector:
    
    def setup_method(self):
        """測試初始化"""
        self.detector = StabilityDetector()
    
    def test_something(self):
        """測試某個功能"""
        result = self.detector.is_stable([(100, 100)])
        assert isinstance(result, bool)
```

### 運行測試

```bash
# 所有測試
pytest tests/

# 單個文件
pytest tests/test_detector.py

# 單個測試
pytest tests/test_detector.py::TestStabilityDetector::test_initialization

# 帶標記
pytest tests/ -m unit

# 帶詳細信息
pytest tests/ -vv

# 停在第一個失敗
pytest tests/ -x

# 顯示最慢的 10 個測試
pytest tests/ --durations=10
```

## 發佈流程

### 版本號

遵循 Semantic Versioning (SemVer)：
- **MAJOR**: 破壞性變更
- **MINOR**: 新功能（向後相容）
- **PATCH**: Bug 修復

### 發佈步驟

1. **更新版本號**
   ```bash
   # 在 setup.py 和 pyproject.toml 中更新版本
   ```

2. **更新 CHANGELOG**
   ```bash
   # 添加新版本的變更日誌
   ```

3. **提交變更**
   ```bash
   git commit -m "chore: bump version to 1.1.0"
   git tag v1.1.0
   ```

4. **構建分發包**
   ```bash
   python setup.py sdist bdist_wheel
   ```

5. **上傳到 PyPI**
   ```bash
   twine upload dist/*
   ```

## CI/CD

### GitHub Actions

專案使用 GitHub Actions 進行持續集成。工作流程：

1. **代碼風格檢查** (Black, Flake8, MyPy)
2. **單元測試** (Pytest)
3. **覆蓋率報告** (Codecov)

### 本地 CI 模擬

```bash
# 運行與 CI 相同的檢查
make lint
make test-cov
```

## 常見任務

### 添加新功能

1. 創建新分支：`git checkout -b feature/new-feature`
2. 編寫代碼和測試
3. 運行 `make lint` 和 `make test`
4. 提交並創建 PR

### 修復 Bug

1. 創建新分支：`git checkout -b fix/bug-name`
2. 編寫修復代碼
3. 添加回歸測試
4. 運行 `make test`
5. 提交並創建 PR

### 更新文檔

1. 編輯 `docs/` 中的 Markdown 文件
2. 確保代碼示例可運行
3. 提交更改

## 調試技巧

### 使用 print 調試

```python
import logging

logger = logging.getLogger(__name__)

def my_function():
    logger.debug("Debug信息")
    logger.info("信息")
    logger.warning("警告")
    logger.error("錯誤")
```

### 使用 pdb 調試

```python
def my_function():
    import pdb; pdb.set_trace()
    # ... 代碼會在此停止
```

### 使用 IDE 調試

在 VS Code 中：

1. 設置斷點
2. 打開 Run and Debug (Ctrl+Shift+D)
3. 選擇 "Python"
4. 執行

## 性能分析

```bash
# 使用 cProfile 分析性能
python -m cProfile -s cumulative my_script.py

# 使用 line_profiler
pip install line_profiler
kernprof -l -v my_script.py
```

## 故障排除

### 導入錯誤

```bash
# 確保包正確安裝
pip install -e .

# 檢查 PYTHONPATH
python -c "import sys; print('\n'.join(sys.path))"
```

### 測試失敗

```bash
# 運行失敗的測試並顯示詳細信息
pytest tests/test_something.py -vv

# 停在第一個失敗並進入 pdb
pytest tests/ -x --pdb
```

### 代碼風格問題

```bash
# 自動修復代碼風格
black ai_coach/

# 顯示 flake8 錯誤
flake8 ai_coach/
```

## 聯繫方式

- **Issues**: https://github.com/xhujustin/billiards-analytics-v1.5.1/issues
- **Email**: team@example.com

---

祝開發順利！💻
