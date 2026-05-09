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
from typing import Any, Optional

import cv2

# 加速 JPEG 編碼 (可選)
try:
    import simplejpeg as _simplejpeg
    USE_SIMPLEJPEG = True
    print("simplejpeg enabled - 2-3x faster JPEG encoding")
except ImportError:
    _simplejpeg = None  # type: ignore[assignment]
    USE_SIMPLEJPEG = False
    print("simplejpeg not available, using OpenCV (slower)")


class MJPEGStream:
    """MJPEG 串流生成器"""

    def __init__(self, name: str = "stream", quality: int = 70, max_fps: int = 30):
        self.name = name
        self.quality = quality
        self.max_fps = max_fps
        self.frame_interval = 0.0 if max_fps <= 0 else 1.0 / max_fps
        
        # ✅ 自適應品質控制
        self.auto_quality = False  # 預設關閉

        # 儲存原始幀和多種畫質的編碼版本
        self._current_raw_frame: Optional[Any] = None
        self._encoded_frames: dict[int, bytes] = {}  # quality -> encoded_bytes
        self._frame_lock = threading.Lock()
        self._frame_event = asyncio.Event()

        # 連接管理
        self._active_connections = 0
        self._max_connections = 10  # 限制最大並發連接數
        self._connection_lock = threading.Lock()
        self._connections: dict[str, dict[str, Any]] = {}
        self._latest_connection_by_client: dict[str, str] = {}
        self._latest_connection_by_group: dict[str, str] = {}

        # 統計
        self.total_frames = 0
        self.last_frame_time = 0.0
        self._frame_id = 0

    def set_quality(self, quality: int):
        """動態設置 JPEG 畫質 (1-100)"""
        if 1 <= quality <= 100:
            self.quality = quality
            print(f"🎨 {self.name} stream quality set to {quality}")

    def set_max_fps(self, max_fps: int):
        """動態設置串流 FPS 上限；<=0 表示不限制。"""
        self.max_fps = max_fps
        self.frame_interval = 0.0 if self.max_fps <= 0 else 1.0 / self.max_fps
    
    def set_auto_quality(self, enabled: bool):
        """
        啟用/停用自動品質調整
        
        Args:
            enabled: True 啟用, False 停用
        """
        self.auto_quality = enabled
        print(f"🎨 {self.name} auto quality: {'enabled' if enabled else 'disabled'}")
    
    def adjust_quality_if_slow(self, current_fps: float):
        """
        根據 FPS 自動調整品質 (僅在 auto_quality=True 時)
        
        Args:
            current_fps: 當前 FPS
        """
        if not self.auto_quality:
            return
        
        # 根據 FPS 自動調整品質
        if current_fps < 20:
            new_quality = 40  # 低品質
        elif current_fps < 25:
            new_quality = 55  # 中品質
        else:
            new_quality = 70  # 標準品質
        
        # 只在品質改變時才設定
        if new_quality != self.quality:
            self.set_quality(new_quality)
            print(f"📊 {self.name} auto-adjusted quality to {new_quality} (FPS: {current_fps:.1f})")

    def update_frame(self, frame: Any):
        """更新當前幀（儲存原始幀，按需編碼不同畫質）"""
        try:
            with self._frame_lock:
                self._current_raw_frame = frame.copy()
                # 清空舊的編碼緩存，因為有新幀了
                self._encoded_frames.clear()
                self.total_frames += 1
                self._frame_id += 1
                self.last_frame_time = time.time()
        except Exception as e:
            print(f"❌ MJPEG frame update error ({self.name}): {e}")

    def get_frame(self, quality: Optional[int] = None) -> Optional[tuple[int, bytes]]:
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
                return self._frame_id, self._encoded_frames[target_quality]

            frame_id = self._frame_id
            raw_frame = self._current_raw_frame.copy()

        # JPEG 編碼不應持有 frame lock，避免慢 client 阻塞主擷取迴圈更新新幀。
        try:
            if USE_SIMPLEJPEG and _simplejpeg is not None:
                encoded = _simplejpeg.encode_jpeg(
                    raw_frame,
                    quality=target_quality,
                    colorspace='BGR'  # OpenCV 使用 BGR
                )
            else:
                ret, buffer = cv2.imencode(
                    ".jpg",
                    raw_frame,
                    [cv2.IMWRITE_JPEG_QUALITY, target_quality]
                )
                if not ret:
                    return None
                encoded = buffer.tobytes()

            with self._frame_lock:
                # 緩存編碼結果（最多保留3種畫質）
                if self._frame_id == frame_id:
                    if len(self._encoded_frames) >= 3:
                        self._encoded_frames.pop(next(iter(self._encoded_frames)))
                    self._encoded_frames[target_quality] = encoded
            return frame_id, encoded
        except Exception as e:
            print(f"MJPEG encode error ({self.name}, quality={target_quality}): {e}")

        return None

    async def generate(
        self,
        quality: Optional[int] = None,
        client_id: Optional[str] = None,
        exclusive_group: Optional[str] = None,
    ):
        """異步生成器：產出 MJPEG 格式的幀

        Args:
            quality: 可選的畫質覆蓋值 (1-100)，如果提供則使用此畫質
            client_id: 同一前端視圖的穩定 id；新連線會取代舊連線，避免畫質切換殘留。
            exclusive_group: 同一群組只保留最新連線，用於 monitor/projector 單畫面輸出。
        """
        target_quality = quality if quality is not None and 1 <= quality <= 100 else self.quality
        connection_id = str(time.time())[-8:]  # 生成連接ID用於追蹤
        
        # 檢查並發連接數限制
        with self._connection_lock:
            if self._active_connections >= self._max_connections:
                print(f"⚠️ {self.name} max connections reached ({self._max_connections}), rejecting new connection")
                # 返回空生成器，客戶端會收到立即結束的響應
                return
            if client_id:
                old_connection_id = self._latest_connection_by_client.get(client_id)
                if old_connection_id and old_connection_id in self._connections:
                    self._connections[old_connection_id]["replaced"] = True
                self._latest_connection_by_client[client_id] = connection_id
            if exclusive_group:
                old_group_connection_id = self._latest_connection_by_group.get(exclusive_group)
                if old_group_connection_id and old_group_connection_id in self._connections:
                    self._connections[old_group_connection_id]["replaced"] = True
                self._latest_connection_by_group[exclusive_group] = connection_id
            self._active_connections += 1
            self._connections[connection_id] = {
                "quality": target_quality,
                "started_at": time.time(),
                "last_sent_frame_id": -1,
                "last_send_time": None,
                "client_id": client_id,
                "exclusive_group": exclusive_group,
                "replaced": False,
            }
            print(f"🎨 {self.name} stream starting with quality={target_quality} [conn:{connection_id}] (active: {self._active_connections}/{self._max_connections})")

        boundary = b"--frame\r\n"
        last_send_time = time.time()
        last_sent_frame_id = -1
        stale_timeout = 10.0  # 10秒無數據發送則視為連接已斷開
        
        try:
            while True:
                with self._connection_lock:
                    if self._connections.get(connection_id, {}).get("replaced"):
                        print(f"🔁 {self.name} stream replaced by newer client connection [conn:{connection_id}]")
                        break

                # 使用指定畫質獲取幀
                frame_result = self.get_frame(quality=target_quality)
                if frame_result:
                    frame_id, frame_data = frame_result
                    if frame_id == last_sent_frame_id:
                        await asyncio.sleep(0.001)
                        continue
                    try:
                        yield (
                            boundary
                            + b"Content-Type: image/jpeg\r\n"
                            + f"Content-Length: {len(frame_data)}\r\n\r\n".encode()
                            + frame_data
                            + b"\r\n"
                        )
                        last_sent_frame_id = frame_id
                        last_send_time = time.time()
                        with self._connection_lock:
                            if connection_id in self._connections:
                                self._connections[connection_id]["last_sent_frame_id"] = frame_id
                                self._connections[connection_id]["last_send_time"] = last_send_time
                    except Exception as e:
                        # 客戶端已斷開，立即退出
                        print(f"🔌 {self.name} client disconnected during send [conn:{connection_id}]: {e}")
                        break
                
                # 檢測殭屍連接：如果超過10秒沒有成功發送數據，主動斷開
                if time.time() - last_send_time > stale_timeout:
                    print(f"⚠️ {self.name} stream stale (>10s no data), closing [conn:{connection_id}]")
                    break
                    
                if self.frame_interval > 0:
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
                if client_id and self._latest_connection_by_client.get(client_id) == connection_id:
                    self._latest_connection_by_client.pop(client_id, None)
                if exclusive_group and self._latest_connection_by_group.get(exclusive_group) == connection_id:
                    self._latest_connection_by_group.pop(exclusive_group, None)
                self._connections.pop(connection_id, None)
                print(f"✅ {self.name} stream cleanup completed [conn:{connection_id}] (active: {self._active_connections}/{self._max_connections})")

    def get_stats(self) -> dict:
        """獲取統計信息"""
        now = time.time()
        with self._connection_lock:
            connections = [
                {
                    "id": conn_id,
                    "client_id": info.get("client_id"),
                    "exclusive_group": info.get("exclusive_group"),
                    "quality": info.get("quality"),
                    "age_sec": round(now - float(info.get("started_at", now)), 3),
                    "last_sent_frame_id": info.get("last_sent_frame_id"),
                    "replaced": bool(info.get("replaced")),
                    "idle_sec": (
                        round(now - float(info["last_send_time"]), 3)
                        if info.get("last_send_time") is not None
                        else None
                    ),
                }
                for conn_id, info in self._connections.items()
            ]
        return {
            "name": self.name,
            "total_frames": self.total_frames,
            "quality": self.quality,
            "max_fps": self.max_fps,
            "has_frame": self._current_raw_frame is not None,
            "cached_qualities": list(self._encoded_frames.keys()),
            "active_connections": self._active_connections,
            "max_connections": self._max_connections,
            "connections": connections,
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

    def set_max_fps(self, max_fps: int):
        """同步設置監控與投影串流 FPS 上限；<=0 表示不限制。"""
        self.monitor.set_max_fps(max_fps)
        self.projector.set_max_fps(max_fps)

    def get_stats(self) -> dict:
        """獲取雙流統計"""
        return {
            "monitor": self.monitor.get_stats(),
            "projector": self.projector.get_stats(),
        }
