# 快速啟動指南

## 🚀 啟動步驟

### 1. 啟動後端
```bash
cd backend
python main.py
```

**預期輸出**：
```
✅ YOLO model loaded successfully
✅ Calibrator initialized successfully
✅ MJPEG Stream Manager initialized
🚀 Starting camera capture thread for burn-in stream...
🎥 Starting camera capture loop for burn-in stream...
✅ Camera opened successfully...
```

### 2. 啟動前端
```bash
cd frontend
npm run dev
```

**預期輸出**：
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 3. 訪問介面

打開瀏覽器訪問：**http://localhost:5173**

## 🎯 使用 YOLO 辨識

1. **點擊頂部的** 🟢 **啟動辨識** 按鈕
2. 觀察即時影像出現物件檢測框和軌跡線
3. 查看下方狀態卡片顯示辨識數據
4. **點擊** 🔴 **停止辨識** 按鈕停止

## 📁 檔案結構

```
frontend/src/components/
├── Dashboard.tsx          # 主組件
├── Dashboard.css         # 主樣式
├── Layout.tsx            # 佈局框架
├── TopBar.tsx            # 頂部欄（含按鈕）
├── Sidebar.tsx           # 側邊欄
└── pages/
    ├── StreamPage.tsx    # 即時影像頁面
    ├── SessionPage.tsx   # Session 頁面
    ├── MetadataPage.tsx  # Metadata 頁面
    └── SettingsPage.tsx  # 設定頁面
```

## ✅ 功能檢查清單

- [ ] 後端成功啟動，攝影機正常運行
- [ ] 前端成功連接，WebSocket 狀態為「已連接」
- [ ] Burn-in 影像正常顯示
- [ ] 點擊「啟動辨識」後，影像出現檢測框
- [ ] YOLO 狀態卡片顯示「已啟用」
- [ ] 點擊「停止辨識」後，影像恢復原始畫面
- [ ] 側邊欄可以正常切換頁面

## 🐛 常見問題

### 問題 1: 攝影機無法開啟
**解決方案**：
- 檢查攝影機是否被其他程式佔用
- 嘗試更改 `backend/config.py` 中的 `CAMERA_DEVICE` 設定

### 問題 2: 前端無法連接後端
**解決方案**：
- 確認後端運行在 `http://localhost:8001`
- 檢查 `frontend/.env` 中的 API URL 設定

### 問題 3: YOLO 辨識無反應
**解決方案**：
- 查看瀏覽器控制台是否有錯誤訊息
- 檢查後端日誌確認 YOLO 模型是否正確載入

## 📖 詳細文檔

請參閱：
- [YOLO_CONTROL_UI.md](YOLO_CONTROL_UI.md) - 完整使用說明
- [BURN_IN_FIX.md](BURN_IN_FIX.md) - Burn-in 串流修復說明

## 🎉 享受使用！
