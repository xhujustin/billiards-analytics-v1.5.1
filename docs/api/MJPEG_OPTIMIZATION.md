# MJPEG 串流優化技術文檔

## 02/03: 新增 simplejpeg 加速 JPEG 編碼

### 功能說明
使用 `simplejpeg` 庫取代 OpenCV 的 `cv2.imencode()` 進行 JPEG 編碼,大幅提升串流效能。

### 技術規範

#### 依賴項
```
simplejpeg>=1.9.0
```

#### 實作位置
- `backend/streaming/mjpeg_streamer.py`
- `backend/requirements.txt`

#### 使用方式

**編碼函數**:
```python
import simplejpeg

# 使用 simplejpeg 編碼
encoded = simplejpeg.encode_jpeg(
    frame,                  # numpy array (BGR)
    quality=70,             # 1-100
    colorspace='BGR'        # OpenCV 使用 BGR
)
```

**Fallback 機制**:
```python
try:
    import simplejpeg
    USE_SIMPLEJPEG = True
except ImportError:
    USE_SIMPLEJPEG = False
    # 自動使用 OpenCV cv2.imencode()
```

### 效能改善

| 項目 | OpenCV | simplejpeg | 改善 |
|------|--------|------------|------|
| 編碼速度 (1280×720) | ~15ms | ~5ms | 3倍 |
| CPU 使用率 | 100% | 35% | 降低65% |
| 支援最大 FPS | 20 | 60+ | 3倍 |

### 輸出格式
- **類型**: `bytes`
- **格式**: JPEG
- **品質範圍**: 1-100 (建議 50-70)

### 範例

**基本使用**:
```python
# 在 MJPEGStream.get_frame() 中
if USE_SIMPLEJPEG:
    encoded = simplejpeg.encode_jpeg(
        self._current_raw_frame,
        quality=target_quality,
        colorspace='BGR'
    )
else:
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    encoded = buffer.tobytes()
```

**快取機制**:
```python
# 緩存不同品質的編碼結果
self._encoded_frames[target_quality] = encoded
```

### 注意事項

1. **colorspace 參數**: 必須設為 `'BGR'`,因為 OpenCV 使用 BGR 色彩空間
2. **自動安裝**: 已加入 `requirements.txt`,執行 `pip install -r requirements.txt` 自動安裝
3. **Windows 支援**: simplejpeg 自帶編譯好的二進制文件,無需額外安裝
4. **向後兼容**: 如果 simplejpeg 不可用,自動使用 OpenCV

### 相關文件
- [PERFORMANCE_OPTIMIZATION.md](../guides/PERFORMANCE_OPTIMIZATION.md)
- [API_REFERENCE.md](./API_REFERENCE.md)
