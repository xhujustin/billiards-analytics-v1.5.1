# 回放 API 測試說明

## 測試程式位置
`backend/test-program/test_replay_api.py`

## 執行方式

### 1. 啟動後端服務
```bash
cd backend
python main.py
```

### 2. 執行測試（另開終端）
```bash
cd backend
python test-program/test_replay_api.py
```

## 測試項目

### 錄影查詢 API
- ✓ `GET /api/recordings` - 列表查詢（含篩選、分頁）
- ✓ `GET /api/recordings/{game_id}` - 單一錄影詳情
- ✓ `GET /api/recordings/{game_id}/events` - 事件日誌查詢
- ✓ 404 錯誤處理驗證

### 統計分析 API
- ✓ `GET /api/stats/practice` - 練習統計
- ✓ `GET /api/stats/player/{player_name}` - 玩家統計
- ✓ `GET /api/stats/summary` - 統計摘要

### 回放控制 API
- ✓ `GET /replay/events/{game_id}` - 事件回放（JSONL/JSON 格式）

### v1.5 協議驗證
- ✓ 錯誤格式符合規範（error.code, error.message, error.details）

## 注意事項

1. **需要測試資料**：測試前需先有錄影資料，可透過以下方式：
   - 執行 `migrate_recordings.py` 匯入現有資料
   - 或透過遊玩/練習模式產生新錄影

2. **後端服務必須啟動**：測試會向 `http://localhost:8001` 發送請求

3. **依賴套件**：需安裝 `requests` 套件
   ```bash
   pip install requests
   ```

## 預期輸出

```
============================================================
回放 API 測試程式
============================================================

[*] 測試目標: http://localhost:8001
[*] 請確保後端服務已啟動
[+] 後端服務正常（版本: 1.5.0）

[TEST] 錄影列表查詢...
  [OK] 基本查詢成功（總筆數: 3）
  [OK] 篩選查詢成功

[TEST] 單一錄影詳情查詢...
  [OK] 查詢成功（game_id: game_20260115_152908）
  [OK] 404 錯誤處理正確

[TEST] 錄影事件查詢...
  [OK] 查詢成功（事件數: 2）
  [OK] 事件類型篩選成功

[TEST] 練習統計...
  [OK] 查詢成功（總場次: 0）

[TEST] 玩家統計...
  [OK] 404 錯誤處理正確
  [SKIP] 玩家資料查詢（需先有資料）

[TEST] 統計摘要...
  [OK] 查詢成功（總遊戲數: 3）

[TEST] 事件回放...
  [OK] JSONL 格式成功
  [OK] JSON 格式成功

[TEST] v1.5 錯誤格式驗證...
  [OK] 錯誤格式符合 v1.5 規範

============================================================
[+] 所有測試通過！
============================================================
```
