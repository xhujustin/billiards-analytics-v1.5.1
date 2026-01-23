"""
ArUco 標記檢測器
用於投影機自動校正,檢測 ID 0-3 的 ArUco 標記
"""

import cv2
import numpy as np
from typing import Optional, Dict

class ArucoDetector:
    """ArUco 標記自動檢測器"""
    
    def __init__(self):
        # 使用 4x4 字典 (50 個標記)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.last_corners = None
    
    def detect(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        檢測 ArUco 標記 (ID 0-3)
        
        Args:
            frame: 輸入影像 (BGR)
        
        Returns:
            corners: 4個角點座標 [[x,y], [x,y], [x,y], [x,y]]
                    順序: 左上(ID=0), 右上(ID=1), 右下(ID=2), 左下(ID=3)
            None: 未檢測到完整的 4 個標記
        """
        # 轉灰階
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 檢測 ArUco 標記
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray, 
            self.aruco_dict,
            parameters=self.aruco_params
        )
        
        if ids is None or len(ids) < 4:
            return None
        
        # 提取 ID 0-3 的標記中心點
        detected_corners = {}
        for i, marker_id in enumerate(ids.flatten()):
            if marker_id < 4:  # 只處理 ID 0-3
                # 計算標記中心點 (4個角點的平均)
                center = corners[i][0].mean(axis=0)
                detected_corners[marker_id] = center
        
        # 檢查是否檢測到全部 4 個標記
        if len(detected_corners) != 4:
            return None
        
        # 按 ID 順序排列
        result = np.array([
            detected_corners[0],  # 左上
            detected_corners[1],  # 右上
            detected_corners[2],  # 右下
            detected_corners[3]   # 左下
        ], dtype=np.float32)
        
        self.last_corners = result
        return result
    
    def draw_detection(self, frame: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """
        繪製檢測結果 (綠色框線 + 位置標籤)
        
        Args:
            frame: 輸入影像
            corners: 檢測到的角點
        
        Returns:
            繪製後的影像
        """
        result = frame.copy()
        
        # 繪製外框 (綠色)
        pts = corners.astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(result, [pts], True, (0, 255, 0), 3, cv2.LINE_AA)
        
        # 繪製角點和位置標籤
        labels = ['左上', '右上', '右下', '左下']
        for i, corner in enumerate(corners):
            pos = tuple(corner.astype(int))
            # 角點圓圈
            cv2.circle(result, pos, 8, (0, 0, 255), -1)
            # 位置標籤
            cv2.putText(result, labels[i], 
                       (pos[0] + 15, pos[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return result
