"""
效能監控模組 - 追蹤 burn-in 串流效能
"""
from collections import deque
import time


class PerformanceMonitor:
    """輕量級效能監控,使用 EWMA 追蹤 FPS 和延遲"""
    
    def __init__(self, window_size: int = 30):
        """
        初始化效能監控
        
        Args:
            window_size: 滑動視窗大小 (幀數)
        """
        self.frame_times = deque(maxlen=window_size)
        self.stage_times = {}
        self.window_size = window_size
        self.last_record_time = time.time()
        self.total_frames = 0
        
    def record_frame(self, processing_time: float) -> None:
        """
        記錄一幀的處理時間
        
        Args:
            processing_time: 處理時間 (秒)
        """
        self.frame_times.append(processing_time)
        self.total_frames += 1
        self.last_record_time = time.time()

    def record_stage(self, name: str, duration: float, frame_id: int) -> None:
        """記錄單一處理階段耗時（秒）。"""
        if name not in self.stage_times:
            self.stage_times[name] = deque(maxlen=self.window_size)
        self.stage_times[name].append((frame_id, duration))

    def record_stages(self, stages: dict) -> None:
        """批次記錄多個處理階段耗時（秒）。"""
        frame_id = self.total_frames + 1
        for name, duration in stages.items():
            if duration is None:
                continue
            self.record_stage(name, duration, frame_id)
    
    def get_current_fps(self) -> float:
        """
        計算當前 FPS
        
        Returns:
            當前 FPS (基於滑動視窗平均)
        """
        if not self.frame_times:
            return 0.0
        
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0.0
    
    def get_average_latency(self) -> float:
        """
        取得平均延遲 (毫秒)
        
        Returns:
            平均處理延遲 (ms)
        """
        if not self.frame_times:
            return 0.0
        
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return avg_time * 1000.0  # 轉換為毫秒
    
    def should_reduce_quality(self) -> bool:
        """
        判斷是否應該降低品質
        
        Returns:
            True 如果 FPS < 25
        """
        fps = self.get_current_fps()
        return fps < 25.0 and fps > 0
    
    def get_stats(self) -> dict:
        """
        取得效能統計資訊
        
        Returns:
            包含 fps, latency, total_frames 的字典
        """
        return {
            "current_fps": self.get_current_fps(),
            "avg_latency_ms": self.get_average_latency(),
            "total_frames": self.total_frames,
            "window_size": len(self.frame_times),
            "stage_latency_ms": self.get_stage_stats(),
        }

    def get_stage_stats(self) -> dict:
        """取得各處理階段平均耗時（毫秒）。"""
        stats = {}
        for name, values in self.stage_times.items():
            if not values:
                continue
            durations = [duration for _, duration in values]
            last_frame_id, last_duration = values[-1]
            stats[name] = {
                "avg_ms": (sum(durations) / len(durations)) * 1000.0,
                "last_ms": last_duration * 1000.0,
                "samples": len(values),
                "last_frame_id": last_frame_id,
                "stale_frames": max(0, self.total_frames - last_frame_id),
            }
        return stats
