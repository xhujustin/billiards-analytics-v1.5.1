# 畫質調整功能修復說明

## 問題描述

用戶回報：實時顯示的畫質調整沒有反應

## 根本原因

原本的 `MJPEGStream` 實現存在設計缺陷：

1. **編碼時機錯誤**: 在 `update_frame()` 時就編碼成固定畫質的 JPEG
2. **畫質無法動態切換**: 所有客戶端共用同一個已編碼的幀
3. **覆蓋機制失效**: `generate(quality)` 只是臨時改變 `self.quality`，但 `update_frame()` 已經使用舊畫質編碼了

```python
# 原本的問題代碼
def update_frame(self, frame):
    # ❌ 這裡就編碼了，使用的是 self.quality
    ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
    self._current_frame = buffer.tobytes()

async def generate(self, quality=None):
    if quality:
        self.quality = quality  # ❌ 太晚了，幀已經編碼完了
    frame_data = self.get_frame()  # ❌ 返回的是舊畫質的編碼
```

## 解決方案

### 核心改進：按需編碼 (On-Demand Encoding)

**檔案**: [mjpeg_streamer.py](backend/mjpeg_streamer.py)

#### 1. 儲存原始幀而非編碼幀

```python
def __init__(self, ...):
    # 修改前
    self._current_frame: Optional[bytes] = None  # ❌ 儲存編碼後的 JPEG

    # 修改後
    self._current_raw_frame: Optional[Any] = None  # ✅ 儲存原始 OpenCV 幀
    self._encoded_frames: dict[int, bytes] = {}    # ✅ 緩存多種畫質
```

#### 2. 更新幀時只儲存原始數據

```python
def update_frame(self, frame: Any):
    """更新當前幀（儲存原始幀，按需編碼不同畫質）"""
    with self._frame_lock:
        self._current_raw_frame = frame.copy()  # ✅ 儲存原始幀
        self._encoded_frames.clear()            # ✅ 清空舊緩存
        self.total_frames += 1
        self.last_frame_time = time.time()
```

#### 3. 按需編碼指定畫質

```python
def get_frame(self, quality: Optional[int] = None) -> Optional[bytes]:
    """獲取當前幀的 JPEG bytes（指定畫質）"""
    target_quality = quality if quality is not None else self.quality

    with self._frame_lock:
        if self._current_raw_frame is None:
            return None

        # ✅ 檢查是否已經有這個畫質的緩存
        if target_quality in self._encoded_frames:
            return self._encoded_frames[target_quality]

        # ✅ 編碼新畫質
        ret, buffer = cv2.imencode(
            ".jpg",
            self._current_raw_frame,
            [cv2.IMWRITE_JPEG_QUALITY, target_quality]
        )
        if ret:
            encoded = buffer.tobytes()
            # 緩存結果（最多保留3種畫質）
            if len(self._encoded_frames) >= 3:
                self._encoded_frames.pop(next(iter(self._encoded_frames)))
            self._encoded_frames[target_quality] = encoded
            return encoded
```

#### 4. 生成器使用指定畫質

```python
async def generate(self, quality: Optional[int] = None):
    """異步生成器：產出 MJPEG 格式的幀"""
    target_quality = quality if quality is not None else self.quality
    print(f"🎨 {self.name} stream starting with quality={target_quality}")

    while True:
        # ✅ 每次都用指定畫質獲取幀
        frame_data = self.get_frame(quality=target_quality)
        if frame_data:
            yield (boundary + headers + frame_data)
        await asyncio.sleep(self.frame_interval)
```

## 技術亮點

### 1. 多畫質緩存機制

- 每個新幀會清空舊緩存
- 同一幀的不同畫質會被緩存（最多3種）
- 避免重複編碼相同畫質

**範例**:
```
Frame 1:
  - 客戶端A請求 quality=50 → 編碼並緩存
  - 客戶端B請求 quality=70 → 編碼並緩存
  - 客戶端C請求 quality=50 → 直接使用緩存 ✅

Frame 2:
  - 緩存清空（新幀到來）
  - 重新按需編碼
```

### 2. 獨立的畫質控制

每個客戶端可以獨立選擇畫質：

```
客戶端1: /burnin/camera1.mjpg?quality=low  → 50
客戶端2: /burnin/camera1.mjpg?quality=med  → 70
客戶端3: /burnin/camera1.mjpg?quality=high → 90
```

### 3. 性能優化

- **原始幀只複製一次**: 在 `update_frame()` 時
- **編碼延遲到需要時**: 沒有客戶端就不編碼
- **緩存避免重複工作**: 相同畫質的多個客戶端共享編碼結果

### 4. 調試增強

新增日誌輸出：

```bash
🎨 monitor stream starting with quality=90
🎨 monitor stream starting with quality=50
🔌 monitor stream client disconnected (quality=90)
```

可以看到每個客戶端的畫質設定。

## 測試驗證

### 測試 1: 畫質切換

**操作**:
1. 啟動後端和前端
2. 開啟瀏覽器開發者工具 (F12) → Network
3. 在前端選擇不同畫質 (低/中/高)
4. 觀察 Network 中的請求 URL

**預期結果**:
```
quality=low  → /burnin/camera1.mjpg?quality=low&_t=1
quality=med  → /burnin/camera1.mjpg?quality=med&_t=2
quality=high → /burnin/camera1.mjpg?quality=high&_t=3
```

**後端日誌**:
```
🎬 Burnin stream requested: camera1, quality=low (JPEG=50)
🎨 monitor stream starting with quality=50
🎬 Burnin stream requested: camera1, quality=high (JPEG=90)
🎨 monitor stream starting with quality=90
```

### 測試 2: 多客戶端不同畫質

**操作**:
1. 開啟兩個瀏覽器窗口
2. 窗口1選擇「低」畫質
3. 窗口2選擇「高」畫質

**預期結果**:
- 窗口1顯示低畫質影像（檔案小，延遲低）
- 窗口2顯示高畫質影像（檔案大，清晰度高）
- 兩者互不影響

**後端日誌**:
```
🎨 monitor stream starting with quality=50
🎨 monitor stream starting with quality=90
```

### 測試 3: 緩存效果

**操作**:
查看後端統計 API:
```bash
curl http://localhost:8001/api/stream/stats
```

**預期輸出**:
```json
{
  "streams": {
    "monitor": {
      "name": "monitor",
      "total_frames": 1234,
      "quality": 70,
      "max_fps": 30,
      "has_frame": true,
      "cached_qualities": [50, 70, 90]  // ✅ 緩存了3種畫質
    }
  }
}
```

## 使用說明

### 前端畫質選擇

在 Stream 頁面的畫質選擇器：

```
○ 低 (Low)   - 50 品質，適合慢速網路
● 中 (Med)   - 70 品質，預設選項
○ 高 (High)  - 90 品質，最佳畫質
```

### 直接 URL 訪問

也可以直接在瀏覽器訪問：

```
低畫質: http://localhost:8001/burnin/camera1.mjpg?quality=low
中畫質: http://localhost:8001/burnin/camera1.mjpg?quality=med
高畫質: http://localhost:8001/burnin/camera1.mjpg?quality=high
```

### 自定義畫質值

可以使用 1-100 的任意值：

```
http://localhost:8001/burnin/camera1.mjpg?quality=85
```

對應的 JPEG 品質就是 85。

## 性能影響

### 記憶體使用

**修改前**:
- 每幀: ~50KB (已編碼的 JPEG)

**修改後**:
- 原始幀: ~2.7MB (1280×720×3 bytes)
- 緩存編碼: ~50KB × 3 = ~150KB (最多3種畫質)
- **總計**: ~2.85MB per frame

**結論**: 記憶體增加約 2.8MB，但換來了動態畫質控制。

### CPU 使用

**修改前**:
- 每幀編碼一次（固定畫質）

**修改後**:
- 按需編碼（有請求才編碼）
- 緩存機制減少重複編碼

**結論**:
- 單客戶端: CPU 使用相同
- 多客戶端同畫質: CPU 使用減少（緩存）
- 多客戶端不同畫質: CPU 增加（需編碼多個畫質）

### 網路頻寬

**根據畫質選擇**:
- Low (50):  ~20KB/frame → ~600KB/s @ 30fps
- Med (70):  ~50KB/frame → ~1.5MB/s @ 30fps
- High (90): ~100KB/frame → ~3MB/s @ 30fps

用戶可以根據網路狀況選擇合適畫質。

## 常見問題

### Q: 為什麼切換畫質後影像會短暫中斷？

A: 前端在切換畫質時會：
1. 更新 URL 參數（`quality=xxx`）
2. 添加時間戳（`_t=xxx`）強制重新載入
3. 瀏覽器斷開舊連接，建立新連接

這是正常行為，中斷時間約 100-200ms。

### Q: 緩存最多3種畫質夠用嗎？

A: 夠用。實際使用中：
- 大部分用戶使用預設畫質（med）
- 少數用戶切換到 low 或 high
- 超過3種畫質的情況極少

如果需要更多，可以修改：
```python
if len(self._encoded_frames) >= 5:  # 改為5
```

### Q: 能否禁用緩存？

A: 可以，修改 `get_frame()`:
```python
# 每次都重新編碼（不緩存）
ret, buffer = cv2.imencode(...)
return buffer.tobytes()
# 不要存入 self._encoded_frames
```

但這會增加 CPU 負載。

### Q: 低畫質和高畫質的視覺差異明顯嗎？

A: 是的：
- **Low (50)**: 明顯壓縮痕跡，適合快速瀏覽
- **Med (70)**: 平衡品質，大部分情況夠用
- **High (90)**: 接近原始畫質，細節清晰

建議用高畫質觀看球號和路徑標註。

## 相關文件

- [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) - 完整調試指南
- [TABLE_DETECTION_FIX.md](TABLE_DETECTION_FIX.md) - 球桌檢測修復
- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md) - 整合總結

---

**修復時間**: 2026-01-05
**測試狀態**: ✅ 待測試
**影響範圍**: mjpeg_streamer.py
**向後兼容**: ✅ 是（API 保持不變）
