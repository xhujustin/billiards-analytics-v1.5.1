"""
投影機獨立渲染器
負責投影機畫面的獨立渲染,不依賴相機畫面
支援多種模式: 待機、校正、遊戲、練習
"""

import cv2
import numpy as np
from enum import Enum
from typing import Optional, Dict, Any, List

class ProjectorMode(Enum):
    """投影機模式"""
    IDLE = "idle"              # 待機 (純黑)
    CALIBRATION = "calibration"  # 校正模式 (ArUco 標記)
    DETECTION = "detection"    # 啟動辨識模式 (球外框)
    GAME = "game"              # 遊戲模式 (AR 疊加)
    PRACTICE = "practice"      # 練習模式 (球外框 + 球形)

class ProjectorRenderer:
    """投影機獨立渲染器"""
    
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.mode = ProjectorMode.IDLE  # 預設顯示待機畫面
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        
        # 校正模式狀態 (縮小偏移使標記更集中)
        self.calibration_offsets = {
            "top-left": {"x": -280, "y": -280},
            "top-right": {"x": 280, "y": -280},
            "bottom-right": {"x": 280, "y": 280},
            "bottom-left": {"x": -280, "y": 280}
        }
        
        # AR 疊加資料
        self.ar_data = {
            "trajectories": [],  # 軌跡路徑
            "balls": [],         # 球位
            "aim_lines": []      # 瞄準線
        }
    
    def set_mode(self, mode: ProjectorMode):
        """切換投影機模式"""
        self.mode = mode
        print(f"Projector mode: {mode.value}")
    
    def render(self) -> np.ndarray:
        """
        根據當前模式渲染投影機畫面
        
        Returns:
            1920×1080 BGR 影像
        """
        if self.mode == ProjectorMode.IDLE:
            return self._render_idle()
        elif self.mode == ProjectorMode.CALIBRATION:
            return self._render_calibration()
        elif self.mode == ProjectorMode.DETECTION:
            return self._render_detection()
        elif self.mode == ProjectorMode.GAME:
            return self._render_game()
        elif self.mode == ProjectorMode.PRACTICE:
            return self._render_practice()
        else:
            return self._render_idle()
    
    def _render_idle(self) -> np.ndarray:
        """待機模式: 純黑畫面"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 顯示提示文字
        text = "NCUT Billiards Analytics System V1.5.2"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 1.5, 3)[0]
        text_x = (self.width - text_size[0]) // 2
        text_y = (self.height + text_size[1]) // 2
        cv2.putText(frame, text, (text_x, text_y), font, 1.5, (50, 50, 50), 3)
        
        return frame
    
    def _render_calibration(self) -> np.ndarray:
        """校正模式: ArUco 標記圖案"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 縮小標記大小
        marker_size = 100
        # 白色邊框寬度（保持對比度）
        border_width = 10
        center_x = self.width // 2
        center_y = self.height // 2
        
        markers_config = [
            (0, "top-left"),
            (1, "top-right"),
            (2, "bottom-right"),
            (3, "bottom-left")
        ]
        
        position_labels = {
            "top-left": "TL",
            "top-right": "TR",
            "bottom-right": "BR",
            "bottom-left": "BL"
        }
        
        for marker_id, corner_key in markers_config:
            offset = self.calibration_offsets.get(corner_key, {"x": 0, "y": 0})
            
            # 計算標記位置（包含邊框）
            total_size = marker_size + border_width * 2
            x = center_x + offset["x"] - total_size // 2
            y = center_y + offset["y"] - total_size // 2
            
            # 繪製白色背景邊框（增強對比度）
            cv2.rectangle(frame, 
                         (x, y), 
                         (x + total_size, y + total_size),
                         (255, 255, 255), 
                         -1)  # 填充白色
            
            # 產生 ArUco 標記
            marker = cv2.aruco.generateImageMarker(
                self.aruco_dict, 
                marker_id, 
                marker_size
            )
            marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
            
            # 將標記放在白色背景中心
            marker_x = x + border_width
            marker_y = y + border_width
            
            # 放置標記
            if 0 <= marker_x < self.width - marker_size and 0 <= marker_y < self.height - marker_size:
                frame[marker_y:marker_y+marker_size, marker_x:marker_x+marker_size] = marker_bgr
            
            # 繪製位置標籤（黑色，放在白色背景上更清晰）
            label = position_labels[corner_key]
            label_pos = (x + total_size // 2 - 20, y + total_size + 35)
            cv2.putText(frame, label, label_pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        
        return frame
    
    def _render_detection(self) -> np.ndarray:
        """啟動辨識模式: 單純投影球的外框"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # 繪製球位外框 (不填充)
        for ball in self.ar_data.get("balls", []):
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            ball_type = ball.get("type", "unknown")
            color = (255, 255, 255) if ball_type == "cue" else (0, 255, 0)
            cv2.circle(frame, (x, y), 20, color, 2, cv2.LINE_AA)
            if ball.get("number"):
                cv2.putText(frame, str(ball["number"]), (x - 8, y + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return frame
    
    def _draw_ar_elements(self, frame: np.ndarray):
        """繪製共用的 AR 元素 (軌跡、瞄準線、幽靈球)"""
        # 繪製軌跡
        for trajectory in self.ar_data.get("trajectories", []):
            if len(trajectory) > 1:
                pts = np.array(trajectory, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], False, (0, 255, 0), 3, cv2.LINE_AA)
        
        # 繪製瞄準線
        for aim_line in self.ar_data.get("aim_lines", []):
            start = tuple(aim_line["start"])
            end = tuple(aim_line["end"])
            ltype = aim_line.get("type", "")
            if ltype == "cue_to_target":
                color = (255, 255, 255)  # 白色
            elif ltype == "target_to_hole":
                color = (0, 255, 255)  # 黃色
            elif ltype == "separation_line":
                color = (255, 105, 180)  #亮粉/紫色
            else:
                color = (255, 255, 0)
            cv2.line(frame, start, end, color, 3, cv2.LINE_AA)
            
        # 繪製幽靈球
        for gb in self.ar_data.get("ghost_balls", []):
            gx, gy, gr = gb["x"], gb["y"], gb["r"]
            cv2.circle(frame, (gx, gy), gr, (255, 255, 255), 2, cv2.LINE_AA)

    def _render_game(self) -> np.ndarray:
        """遊戲模式: AR 疊加 (軌跡、球位、輔助線)"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        self._draw_ar_elements(frame)
        
        # 繪製黑色遮罩，挖空輔助線經過球體的區段
        for ball in self.ar_data.get("balls", []):
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            cv2.circle(frame, (x, y), 28, (0, 0, 0), -1, cv2.LINE_AA)
        
        return frame
    
    def _render_practice(self) -> np.ndarray:
        """練習模式: 球外框 + 球形 + 輔助線"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        self._draw_ar_elements(frame)
        
        # 繪製黑色遮罩，挖空輔助線經過球體的區段，確保投影機光線不打在球上
        for ball in self.ar_data.get("balls", []):
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            cv2.circle(frame, (x, y), 28, (0, 0, 0), -1, cv2.LINE_AA)
        
        return frame
    
    def update_calibration_offsets(self, offsets: Dict):
        """更新校正模式的標記偏移"""
        self.calibration_offsets.update(offsets)
    
    def update_ar_data(self, ar_data: Dict):
        """更新 AR 疊加資料"""
        self.ar_data.update(ar_data)
