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
