"""
投影機疊加模組
用於在相機畫面上繪製預覽疊加 (綠色框線 + 白色填充)
"""

import cv2
import numpy as np

class ProjectorOverlay:
    """投影機疊加渲染器"""
    
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
    
    def draw_preview_overlay(self, frame: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """
        繪製預覽疊加 (綠色框線 + 白色半透明填充)
        
        Args:
            frame: 輸入影像
            corners: 四個角點座標
        
        Returns:
            疊加後的影像
        """
        overlay = frame.copy()
        
        # 白色半透明填充
        mask = np.zeros_like(frame)
        pts = corners.astype(np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], (255, 255, 255))
        cv2.addWeighted(overlay, 0.7, mask, 0.3, 0, overlay)
        
        # 綠色框線
        cv2.polylines(overlay, [pts], True, (0, 255, 0), 5, cv2.LINE_AA)
        
        # 角點標記
        labels = ['左上', '右上', '右下', '左下']
        for i, corner in enumerate(corners):
            cv2.circle(overlay, tuple(corner.astype(int)), 10, (0, 255, 0), -1)
            cv2.putText(overlay, labels[i], 
                       tuple((corner + [20, -10]).astype(int)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return overlay
