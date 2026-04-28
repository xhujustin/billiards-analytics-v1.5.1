# Contributing to AI Coach

感謝您有興趣貢獻 AI Coach 專案！本文檔說明如何参與開發。

## 行為準則

本專案遵守開源社區的通用準則。請確保尊重和包容所有貢獻者。

## 開發流程

### 1. 設置開發環境

```bash
# Clone 倉庫
git clone https://github.com/xhujustin/billiards-analytics-v1.5.1.git
cd billiards-analytics-v1.5.1/ai_coach

# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安裝開發依賴
pip install -e ".[dev]"
```

### 2. 建立 Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 3. 編碼規範

- **Python 風格**: 遵循 PEP 8
- **代碼格式化**: 使用 Black (`black .`)
- **Linting**: 使用 Flake8 (`flake8 ai_coach`)
- **類型檢查**: 使用 MyPy (`mypy ai_coach`)

### 4. 提交前檢查

```bash
# 運行測試
pytest tests/

# 檢查代碼風格
black ai_coach/
flake8 ai_coach/
mypy ai_coach/

# 生成覆蓋率報告
pytest --cov=ai_coach tests/
```

### 5. 提交消息規範

提交消息應遵循以下格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type** 應為以下之一：
- `feat`: 新功能
- `fix`: Bug 修復
- `docs`: 文檔更改
- `style`: 代碼風格更改（不影響功能）
- `refactor`: 代碼重構
- `perf`: 性能改進
- `test`: 測試相關

**例子**：
```
feat(visualizer): 添加深色主題支持

- 添加新的色彩方案
- 自動根據背景調整文字顏色
- 增加可配性

Closes #123
```

### 6. 發送 Pull Request

1. Push 到你的 Fork
2. 發送 PR 到 `main` 分支
3. 填寫 PR 描述模板
4. 等待 CI/CD 檢查和代碼審查

## 項目結構

```
ai_coach/
├── ai_coach/              # 源代碼
│   ├── overlay.py         # 穩定性偵測
│   ├── client.py          # 核心管理器
│   ├── visualizer.py      # 視覺化渲染
│   ├── train.py           # 模型訓練
│   └── inference.py       # 推論引擎
├── tests/                 # 單元測試
├── examples/              # 示例程序
├── docs/                  # 文檔
└── README.md
```

## 測試指南

### 運行所有測試

```bash
pytest tests/
```

### 運行特定測試

```bash
pytest tests/test_detector.py -v
```

### 生成覆蓋率報告

```bash
pytest --cov=ai_coach --cov-report=html tests/
```

## 文檔貢獻

文檔存放在 `docs/` 目錄。貢獻文檔時：

1. 使用 Markdown 格式
2. 包含代碼示例
3. 確保代碼示例可運行
4. 更新目錄（如適用）

## 問題報告

發現 Bug？請遵循以下步驟：

1. 檢查是否已有相同問題的 Issue
2. 創建新 Issue
3. 包含以下信息：
   - 問題描述
   - 重現步驟
   - 預期行為
   - 實際行為
   - 環境信息（Python 版本、依賴版本等）

## 功能請求

有新想法？請：

1. 先開 Issue 討論
2. 收集社區反饋
3. 如果被批准，提交 PR 實現

## 許可證

通過提交貢獻，您同意您的代碼將在 MIT 許可證下發布。

## 聯繫方式

- **Issues**: https://github.com/xhujustin/billiards-analytics-v1.5.1/issues
- **Email**: team@example.com

---

感謝您的貢獻！🎉
