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
            
            # 根據球類型選擇顏色
            if ball_type == "cue":
                color = (255, 255, 255)  # 白球: 白色
            elif ball_type == "8":
                color = (0, 0, 0)  # 8號球: 黑色 (用深灰顯示)
                color = (50, 50, 50)
            else:
                color = (0, 255, 0)  # 其他球: 綠色
            
            # 繪製外框圓圈 (不填充)
            cv2.circle(frame, (x, y), 20, color, 2, cv2.LINE_AA)
            
            # 可選: 顯示球號
            if ball.get("number"):
                cv2.putText(frame, str(ball["number"]), 
                           (x - 8, y + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return frame
    
    def _render_game(self) -> np.ndarray:
        """遊戲模式: AR 疊加 (軌跡、球位、輔助線)"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 繪製軌跡
        for trajectory in self.ar_data.get("trajectories", []):
            if len(trajectory) > 1:
                pts = np.array(trajectory, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], False, (0, 255, 0), 3, cv2.LINE_AA)
        
        # 繪製球位 (填充)
        for ball in self.ar_data.get("balls", []):
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            ball_type = ball.get("type", "unknown")
            color = (255, 255, 255) if ball_type == "cue" else (0, 255, 0)
            cv2.circle(frame, (x, y), 20, color, -1, cv2.LINE_AA)
        
        # 繪製瞄準線
        for aim_line in self.ar_data.get("aim_lines", []):
            start = tuple(aim_line["start"])
            end = tuple(aim_line["end"])
            cv2.line(frame, start, end, (255, 255, 0), 2, cv2.LINE_AA)
        
        return frame
    
    def _render_practice(self) -> np.ndarray:
        """練習模式: 球外框 + 球形"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 繪製球位 (外框 + 半透明填充)
        for ball in self.ar_data.get("balls", []):
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            ball_type = ball.get("type", "unknown")
            
            # 根據球類型選擇顏色
            if ball_type == "cue":
                color = (255, 255, 255)  # 白球
            elif ball_type == "8":
                color = (50, 50, 50)  # 8號球 (深灰)
            else:
                color = (0, 255, 0)  # 其他球 (綠色)
            
            # 繪製半透明填充球形
            overlay = frame.copy()
            cv2.circle(overlay, (x, y), 20, color, -1, cv2.LINE_AA)
            cv2.addWeighted(frame, 0.7, overlay, 0.3, 0, frame)
            
            # 繪製外框
            cv2.circle(frame, (x, y), 20, color, 2, cv2.LINE_AA)
            
            # 顯示球號
            if ball.get("number"):
                cv2.putText(frame, str(ball["number"]), 
                           (x - 8, y + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return frame
    
    def update_calibration_offsets(self, offsets: Dict):
        """更新校正模式的標記偏移"""
        self.calibration_offsets.update(offsets)
    
    def update_ar_data(self, ar_data: Dict):
        """更新 AR 疊加資料"""
        self.ar_data.update(ar_data)
