# 📚 文檔中心

歡迎來到撞球分析系統的文檔中心。所有技術文檔已按類別整理如下：

## 📖 目錄結構

```
docs/
├── README.md                    # 本文件 - 文檔導航
├── guides/                      # 使用指南
│   ├── QUICK_START.md          # 快速啟動指南
│   ├── HOW_TO_ADJUST_QUALITY.md # 畫質調整教學
│   └── YOLO_CONTROL_UI.md      # YOLO控制介面說明
├── troubleshooting/             # 故障排除
│   ├── DEBUGGING_GUIDE.md      # 調試指南
│   ├── BLACK_SCREEN_FIX.md     # 黑屏問題修復
│   ├── BURN_IN_FIX.md          # Burn-in串流修復
│   ├── TABLE_DETECTION_FIX.md  # 球桌檢測修復
│   └── QUALITY_CONTROL_FIX.md  # 畫質控制修復
├── architecture/                # 架構設計
│   ├── INTEGRATION_SUMMARY.md  # 整合摘要
│   └── V1_5_COMPLIANCE_CHECKLIST.md # v1.5合規清單
└── api/                         # API參考
    ├── API_REFERENCE.md         # API參考文檔
    ├── ARCHITECTURE.md          # 架構設計
    ├── IMPLEMENTATION_GUIDE.md  # 實作指南
    ├── TROUBLESHOOTING.md       # API故障排除
    └── billiards_protocol_v1_5_full_schemas.md # v1.5協議完整架構
```

---

## 🚀 新手入門

### 第一次使用？從這裡開始：

1. **[快速啟動指南](guides/QUICK_START.md)** - 5分鐘內啟動系統
2. **[YOLO控制介面說明](guides/YOLO_CONTROL_UI.md)** - 了解主要功能
3. **[畫質調整教學](guides/HOW_TO_ADJUST_QUALITY.md)** - 優化視頻品質

---

## 🔧 常見問題解決

遇到問題？查看這些故障排除指南：

### 🎯 啟動與檢測問題
- **[調試指南](troubleshooting/DEBUGGING_GUIDE.md)** - 系統啟動無反應、YOLO檢測失效
- **[球桌檢測修復](troubleshooting/TABLE_DETECTION_FIX.md)** - 無法檢測球桌（table抓不到）

### 📺 影像串流問題
- **[黑屏問題修復](troubleshooting/BLACK_SCREEN_FIX.md)** - 切換畫質6次後黑屏
- **[Burn-in串流修復](troubleshooting/BURN_IN_FIX.md)** - 即時影像無法顯示
- **[畫質控制修復](troubleshooting/QUALITY_CONTROL_FIX.md)** - 畫質切換失效

---

## 🏗️ 系統架構

深入了解系統設計：

- **[整合摘要](architecture/INTEGRATION_SUMMARY.md)** - v1.5協議整合總覽
- **[v1.5合規清單](architecture/V1_5_COMPLIANCE_CHECKLIST.md)** - 協議實作狀態

---

## 📡 API文檔

開發者專用技術文檔：

### 核心參考
- **[API參考文檔](api/API_REFERENCE.md)** - 完整REST API與WebSocket接口
- **[架構設計](api/ARCHITECTURE.md)** - 系統架構與組件關係
- **[實作指南](api/IMPLEMENTATION_GUIDE.md)** - 前後端實作細節

### 協議規範
- **[v1.5協議完整架構](api/billiards_protocol_v1_5_full_schemas.md)** - TypeScript型別定義與JSON Schema

### 排障
- **[API故障排除](api/TROUBLESHOOTING.md)** - API相關問題診斷

---

## 🔍 快速查找

### 按症狀搜尋

| 症狀 | 參考文檔 |
|------|---------|
| 系統啟動後無反應 | [調試指南](troubleshooting/DEBUGGING_GUIDE.md) |
| 影像無法顯示 | [Burn-in串流修復](troubleshooting/BURN_IN_FIX.md) |
| 畫質切換後黑屏 | [黑屏問題修復](troubleshooting/BLACK_SCREEN_FIX.md) |
| 無法檢測球桌 | [球桌檢測修復](troubleshooting/TABLE_DETECTION_FIX.md) |
| YOLO檢測框不顯示 | [調試指南](troubleshooting/DEBUGGING_GUIDE.md) |
| 需要調整影像品質 | [畫質調整教學](guides/HOW_TO_ADJUST_QUALITY.md) |
| WebSocket連接問題 | [API故障排除](api/TROUBLESHOOTING.md) |

### 按任務搜尋

| 任務 | 參考文檔 |
|------|---------|
| 第一次部署系統 | [快速啟動指南](guides/QUICK_START.md) |
| 前端開發整合 | [實作指南](api/IMPLEMENTATION_GUIDE.md) |
| 後端API開發 | [API參考文檔](api/API_REFERENCE.md) |
| 理解系統架構 | [架構設計](api/ARCHITECTURE.md) |
| 驗證v1.5合規性 | [v1.5合規清單](architecture/V1_5_COMPLIANCE_CHECKLIST.md) |

---

## 📝 文檔維護

- **最後更新**: 2026年1月5日
- **版本**: v1.5
- **維護者**: 開發團隊

### 貢獻指南

如果您發現文檔有誤或需要補充：
1. 直接編輯對應的 `.md` 文件
2. 確保更新本 `README.md` 的索引
3. 提交 Pull Request

---

## 🌟 推薦閱讀順序

### 使用者路徑
```
快速啟動指南 → YOLO控制介面說明 → 畫質調整教學
```

### 開發者路徑
```
架構設計 → API參考文檔 → 實作指南 → v1.5協議完整架構
```

### 問題排查路徑
```
調試指南 → 對應的故障排除文檔 → API故障排除
```

---

**需要協助？** 按照上述路徑查找相關文檔，或直接查看 [調試指南](troubleshooting/DEBUGGING_GUIDE.md) 開始排查問題。
