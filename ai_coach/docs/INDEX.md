# AI Coach 文檔

此目錄包含 AI Coach 系統的完整文檔。

##  文檔列表

###  部署與啟動 (新版!)
- **guides/DEPLOYMENT_GUIDE.md** -  部署方式選擇指南（推薦從這裡開始）
- **guides/DEPLOYMENT_LOCAL_YOLO.md** -  本地 YOLO 推理部署
- **guides/DEPLOYMENT_REMOTE_VLLM.md** -  遠端 vLLM 推理部署

### 📖 快速開始
- **README.md** - 系統總覽和核心概念
- **guides/QUICKSTART.md** - 5 分鐘快速開始
- **guides/QUICK_REFERENCE.md** - 快速參考卡

###  集成與使用
- **guides/INTEGRATION_GUIDE.md** - 系統整合步驟
- **guides/USAGE_EXAMPLES.md** - 實用代碼範例 (7 個場景)
- **guides/VISUALIZATION_GUIDE.md** - 視覺化詳細配置

###  進階主題
- **guides/DEVELOPMENT.md** - 開發和調試指南
- **ROADMAP.md** - 功能規劃和路線圖
- **PROJECT_STATUS.md** - 項目狀態和進度

---

##  快速導航

###  我是新用戶，想快速開始
1.  閱讀 [DEPLOYMENT_GUIDE.md](guides/DEPLOYMENT_GUIDE.md) - 選擇合適的部署方式
2. 📖 根據選擇閱讀對應的部署指南
3.  執行 examples/ 中的示例代碼

**推薦路徑：**
- 實時檢測? → [DEPLOYMENT_LOCAL_YOLO.md](guides/DEPLOYMENT_LOCAL_YOLO.md)
- AI 建議? → [DEPLOYMENT_REMOTE_VLLM.md](guides/DEPLOYMENT_REMOTE_VLLM.md)
- 不確定? → [DEPLOYMENT_GUIDE.md](guides/DEPLOYMENT_GUIDE.md)

### 👨‍ 我是開發者，要集成到項目
1. 📖 閱讀 [INTEGRATION_GUIDE.md](guides/INTEGRATION_GUIDE.md)
2.  查看 [USAGE_EXAMPLES.md](guides/USAGE_EXAMPLES.md) 中的代碼示例
3.  參考 [DEVELOPMENT.md](guides/DEVELOPMENT.md) 進行調試

###  我要部署到生產環境
1.  評估 [DEPLOYMENT_GUIDE.md](guides/DEPLOYMENT_GUIDE.md) 中的選項
2.  根據選擇完成對應部署指南的所有步驟
3.  執行每份指南末尾的部署檢查清單

### 📘 我要了解完整的系統原理
1. 📖 閱讀 [README.md](README.md) 了解架構
2.  查看 [USAGE_EXAMPLES.md](guides/USAGE_EXAMPLES.md) 中的示例
3.  查看 [VISUALIZATION_GUIDE.md](guides/VISUALIZATION_GUIDE.md) 了解視覺化
