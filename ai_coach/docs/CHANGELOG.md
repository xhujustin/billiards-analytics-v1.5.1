# 變更日誌 (CHANGELOG)

所有對本項目的重要更改都會記錄在此文件中。

本項目遵循 [Semantic Versioning](https://semver.org/) 和 [Keep a Changelog](https://keepachangelog.com/) 慣例。

---

## [未發佈] - 進行中

### 計劃中的功能

- 球速估計和撞球碰撞預測
- 進袋概率計算
- 多玩家支持
- WebSocket 實時流推送
- Streamlit 可視化儀表板
- Docker 容器化部署

---

## [1.0.0] - 2024年12月

### 首次穩定發佈

#### 新增

**核心功能：**
- ✨ `StabilityDetector` 類：使用 60 幀滾動窗口進行球位穩定性偵測
- ✨ `CoordinateSemanticizer` 類：將坐標轉換為語意描述（3×3 網格 + 6 特殊區域）
- ✨ `AICoachManager` 類：核心管理器，集成穩定性檢測、語意轉換、非同步 API 調用
- ✨ `draw_coach_panel()` 函數：在 OpenCV 幀上渲染半透明教練建議面板
- ✨ `ChineseFontManager` 類：跨平台中文字體自動檢測（Windows/macOS/Linux）

**訓練與推論：**
- ✨ `TrainingConfig` 和 `ModelTrainer` 類：Unsloth + LoRA 微調管線
- ✨ `InferenceEngine` 類：支持 4 位量化模型部署
- ✨ `ModelMerger` 類：合併 LoRA 適配器和模型導出

**項目工程化：**
- 📦 `pyproject.toml`：PEP 517 構建系統配置
- 📦 `setup.py`：傳統 setuptools 包裝
- 📦 `requirements.txt`：依賴管理
- 📦 `pytest.ini`：測試框架配置
- 📦 `Makefile`：開發工作流自動化
- 📦 `.gitignore`：Git 版本控制配置

**文檔：**
- 📚 `README.md`（350 行）：系統架構、模塊概述、集成步驟
- 📚 `QUICK_REFERENCE.md`（200 行）：API 快速參考卡
- 📚 `VISUALIZATION_GUIDE.md`（400 行）：字體配置、代碼示例
- 📚 `INTEGRATION_GUIDE.md`：WebSocket/REST 集成指南
- 📚 `USAGE_EXAMPLES.md`：7 個完整代碼示例
- 📚 `DEVELOPMENT.md`：開發指南和工作流程
- 📚 `ROADMAP.md`：項目路線圖和願景

**測試與示例：**
- 🧪 `tests/test_detector.py`：7 個 StabilityDetector 單元測試
- 📝 `examples/example_basic.py`：靜態圖像演示
- 📝 `examples/example_realtime.py`：實時視頻流集成

#### 改進

- 性能優化：使用 NumPy 向量化操作加速位移計算
- 跨平台相容性：自動檢測 Windows、macOS、Linux 字體
- 線程安全：使用 `threading.Lock` 保護全局狀態
- 錯誤處理：完善的異常捕獲和日誌記錄

#### 修復

- 修復中文字體渲染（OpenCV 原生不支持 CJK）
- 修復線程競態條件（使用顯式鎖）
- 修復面板越界（邊界檢查和調整）

#### 已知限制

- 暫不支持動態 API 配置
- 字體檢測基於系統預設路徑
- 訓練管線需要 GPU（A100 或等效）

---

## 詳細變更歷史

### 開發階段 (2024年11月-12月)

#### 第1周：核心穩定性檢測
- 實現 `StabilityDetector` 類
- 使用 60 幀滾動窗口（1 秒 @ 60fps）
- 位移計算基於歐幾里得距離
- 冷卻機制防止誤報

**commit:** `feat(overlay): implement StabilityDetector`

#### 第2周：語意坐標轉換
- 實現 `CoordinateSemanticizer` 類
- 3×3 網格將台球坐標映射到語言描述
- 6 個特殊區域（四個角 + 兩個邊中點）
- 辅助方法 `balls_to_semantic_description()`

**commit:** `feat(client): add CoordinateSemanticizer`

#### 第3周：非同步 API 集成
- 實現 `AICoachManager` 主管理器
- 非同步 vLLM API 調用
- 線程安全結果存儲
- `AnalysisResult` 數據類

**commit:** `feat(client): implement AICoachManager with async API`

#### 第4周：中文數據可視化
- 實現 `draw_coach_panel()` 函數
- 半透明 400px 側邊欄面板
- `ChineseFontManager` 跨平台支持
- PIL + OpenCV alpha 混合

**commit:** `feat(visualizer): Chinese text rendering with ChineseFontManager`

#### 第5周：項目工程化
- 添加 `pyproject.toml` (PEP 517)
- 配置 `setup.py`、`requirements.txt`、`.gitignore`
- 建立 `Makefile` 和測試框架
- 編寫開發指南和文檔
- 創建示例程序

**commit:** `chore: organize ai_coach as production-grade Python package`

---

## 統計信息

### 代碼行數統計
- **核心模塊**：~2,000 行
  - overlay.py: 620 行
  - client.py: 450+ 行
  - visualizer.py: 500+ 行
  - train.py: 390 行
  - inference.py: 180 行
  
- **測試代碼**：~80 行
  - test_detector.py: 7 個測試案例
  
- **文檔**：~2,500 行
  - 5 個主要指南
  - API 參考和示例

### 依賴信息
- **核心依賴**：4 個
  - opencv-python 4.5+
  - Pillow 8.0+
  - numpy 1.20+
  - requests 2.26+

- **可選依賴**：12+ 個
  - 訓練: torch, transformers, unsloth, peft, trl, datasets, bitsandbytes
  - 開發: pytest, black, flake8, mypy, pytest-cov

---

## 升級指南

### 從 v0.x 升級到 v1.0.0

> 這是第一個穩定發佈版本，無需升級指南。

---

## 貢獻者

本版本的開發得到以下人員的支持：

- 核心開發者：Billiards Analytics Team
- 文檔編写：Documentation Team
- 測試支持：QA Team

---

## 參考資源

- 🔗 [GitHub Releases](https://github.com/xhujustin/billiards-analytics-v1.5.1/releases)
- 🔗 [Issue Tracker](https://github.com/xhujustin/billiards-analytics-v1.5.1/issues)
- 🔗 [Discussion Forum](https://github.com/xhujustin/billiards-analytics-v1.5.1/discussions)

---

### 記錄格式

每個版本的更改遵循以下結構：

```markdown
## [版本號] - 發佈日期

### 新增
- 新功能

### 改進
- 現有功能的改進

### 修復
- Bug 修復

### 移除
- 已移除的功能

### 已棄用
- 將來會移除的功能

### 安全
- 安全相關的更改
```

注意：
- `[未發佈]` 部分用於追蹤尚未發佈的更改
- 按時間逆序排列（最新優先）
- 每個發佈版本應該有清晰的日期
- 使用清晰的語言描述每個更改

---

最後更新：2024年12月

如有疑問，請聯繫：team@example.com
