# ARCHITECTURE.md
## 系統架構與設計決策（v1.5）

---

## 核心架構原則
- Burn-in 優先（後端合成 overlay）
- 前後端雙通道：影像 / 控制與資料
- Session 為最小控制與權限單位

---

## 流程概覽
1. Client 建立 Session
2. 播放 Burn-in MJPEG
3. WebSocket 控制與狀態同步
4. Metadata 作為數據面板與回放來源

---

## 關鍵設計決策
- 為何不在前端畫 overlay
- 為何 stream.changed 必須強制且需 ACK
- 為何引入 Connection Health Score（CHS）

---

## 狀態機
- Connection Health Score（DISCONNECTED / STALE / NO_SIGNAL / DEGRADED / HEALTHY）
- Session Kick-Old 策略

---

## 擴充方向（P1/P2）
- Replay
- 多桌 / 多 workspace
- Mobile / low-bandwidth 最佳化