"""
MJPEG 串流模組 - 簡單可靠的 HTTP 視頻串流

類似 IP 攝像頭的實現方式：
- 瀏覽器原生支持，不需要額外播放器
- 直接用 <img src="..."> 即可顯示
- 低延遲，即時顯示
"""

import asyncio
import threading
import time
from collections import deque
from typing import Any, Deque, Optional

import cv2


class MJPEGStream:
    """MJPEG 串流生成器"""

    def __init__(self, name: str = "stream", quality: int = 70, max_fps: int = 30):
        self.name = name
        self.quality = quality
        self.max_fps = max_fps
        self.frame_interval = 1.0 / max_fps

        # 儲存原始幀和多種畫質的編碼版本
        self._current_raw_frame: Optional[Any] = None
        self._encoded_frames: dict[int, bytes] = {}  # quality -> encoded_bytes
        self._frame_lock = threading.Lock()
        self._frame_event = asyncio.Event()

        # 連接管理
        self._active_connections = 0
        self._max_connections = 3  # 限制最大並發連接數
        self._connection_lock = threading.Lock()

        # 統計
        self.total_frames = 0
        self.last_frame_time = 0

    def set_quality(self, quality: int):
        """動態設置 JPEG 畫質 (1-100)"""
        if 1 <= quality <= 100:
            self.quality = quality
            print(f"🎨 {self.name} stream quality set to {quality}")

    def update_frame(self, frame: Any):
        """更新當前幀（儲存原始幀，按需編碼不同畫質）"""
        try:
            with self._frame_lock:
                self._current_raw_frame = frame.copy()
                # 清空舊的編碼緩存，因為有新幀了
                self._encoded_frames.clear()
                self.total_frames += 1
                self.last_frame_time = time.time()
        except Exception as e:
            print(f"❌ MJPEG frame update error ({self.name}): {e}")

    def get_frame(self, quality: Optional[int] = None) -> Optional[bytes]:
        """獲取當前幀的 JPEG bytes（指定畫質）

        Args:
            quality: 畫質 (1-100)，如果為 None 則使用默認畫質
        """
        target_quality = quality if quality is not None else self.quality

        with self._frame_lock:
            if self._current_raw_frame is None:
                return None

            # 檢查是否已經有這個畫質的緩存
            if target_quality in self._encoded_frames:
                return self._encoded_frames[target_quality]

            # 編碼新畫質
            try:
                ret, buffer = cv2.imencode(
                    ".jpg",
                    self._current_raw_frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), target_quality]
                )
                if ret:
                    encoded = buffer.tobytes()
                    # 緩存編碼結果（最多保留3種畫質）
                    if len(self._encoded_frames) >= 3:
                        # 移除最舊的一個
                        self._encoded_frames.pop(next(iter(self._encoded_frames)))
                    self._encoded_frames[target_quality] = encoded
                    return encoded
            except Exception as e:
                print(f"❌ MJPEG encode error ({self.name}, quality={target_quality}): {e}")

            return None

    async def generate(self, quality: Optional[int] = None):
        """異步生成器：產出 MJPEG 格式的幀

        Args:
            quality: 可選的畫質覆蓋值 (1-100)，如果提供則使用此畫質
        """
        target_quality = quality if quality is not None and 1 <= quality <= 100 else self.quality
        connection_id = str(time.time())[-8:]  # 生成連接ID用於追蹤
        
        # 檢查並發連接數限制
        with self._connection_lock:
            if self._active_connections >= self._max_connections:
                print(f"⚠️ {self.name} max connections reached ({self._max_connections}), rejecting new connection")
                # 返回空生成器，客戶端會收到立即結束的響應
                return
            self._active_connections += 1
            print(f"🎨 {self.name} stream starting with quality={target_quality} [conn:{connection_id}] (active: {self._active_connections}/{self._max_connections})")

        boundary = b"--frame\r\n"
        last_send_time = time.time()
        stale_timeout = 10.0  # 10秒無數據發送則視為連接已斷開
        
        try:
            while True:
                # 使用指定畫質獲取幀
                frame_data = self.get_frame(quality=target_quality)
                if frame_data:
                    try:
                        yield (
                            boundary
                            + b"Content-Type: image/jpeg\r\n"
                            + f"Content-Length: {len(frame_data)}\r\n\r\n".encode()
                            + frame_data
                            + b"\r\n"
                        )
                        last_send_time = time.time()
                    except Exception as e:
                        # 客戶端已斷開，立即退出
                        print(f"🔌 {self.name} client disconnected during send [conn:{connection_id}]: {e}")
                        break
                
                # 檢測殭屍連接：如果超過10秒沒有成功發送數據，主動斷開
                if time.time() - last_send_time > stale_timeout:
                    print(f"⚠️ {self.name} stream stale (>10s no data), closing [conn:{connection_id}]")
                    break
                    
                await asyncio.sleep(self.frame_interval)
        except GeneratorExit:
            print(f"🔌 {self.name} stream client disconnected (quality={target_quality}) [conn:{connection_id}]")
            raise
        except asyncio.CancelledError:
            print(f"🔌 {self.name} stream cancelled [conn:{connection_id}]")
            raise
        except Exception as e:
            print(f"❌ {self.name} stream error [conn:{connection_id}]: {e}")
            raise
        finally:
            # 釋放連接計數
            with self._connection_lock:
                self._active_connections = max(0, self._active_connections - 1)
                print(f"✅ {self.name} stream cleanup completed [conn:{connection_id}] (active: {self._active_connections}/{self._max_connections})")

    def get_stats(self) -> dict:
        """獲取統計信息"""
        return {
            "name": self.name,
            "total_frames": self.total_frames,
            "quality": self.quality,
            "max_fps": self.max_fps,
            "has_frame": self._current_raw_frame is not None,
            "cached_qualities": list(self._encoded_frames.keys()),
            "active_connections": self._active_connections,
            "max_connections": self._max_connections,
        }


class DualMJPEGManager:
    """
    管理雙路 MJPEG 串流
    - monitor: 監控畫面
    - projector: 投影畫面
    """

    def __init__(self, quality: int = 70, max_fps: int = 30):
        self.monitor = MJPEGStream("monitor", quality, max_fps)
        self.projector = MJPEGStream("projector", quality, max_fps)
        print(f"✅ MJPEG Stream Manager initialized (quality={quality}, fps={max_fps})")

    def update_monitor(self, frame: Any):
        """更新監控流"""
        self.monitor.update_frame(frame)

    def update_projector(self, frame: Any):
        """更新投影流"""
        self.projector.update_frame(frame)

    def get_stats(self) -> dict:
        """獲取雙流統計"""
        return {
            "monitor": self.monitor.get_stats(),
            "projector": self.projector.get_stats(),
        }
