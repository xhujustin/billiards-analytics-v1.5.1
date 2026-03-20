"""
影像處理模組 - 負責降噪、亮度調整等後處理
遵照 v1.5 技術文檔規範
"""

import cv2
import numpy as np
from typing import Optional, Tuple
import config


class ImageProcessor:
    """影像處理器 - 支援多種降噪演算法與影像增強"""
    
    def __init__(self):
        # 降噪參數
        self.denoise_enabled = config.DENOISE_ENABLED
        self.denoise_strength = config.DENOISE_STRENGTH
        self.denoise_method = config.DENOISE_METHOD
        
        # 影像調整參數
        self.brightness_adjust = 0  # -100 to 100
        self.contrast_adjust = 1.0  # 0.5 to 2.0
        
        # 效能統計
        self.processing_time_ms = 0.0
        self.frame_count = 0
    
    def apply_denoise(self, frame: np.ndarray) -> np.ndarray:
        """
        應用降噪濾鏡
        
        Args:
            frame: 輸入影像 (BGR 格式)
        
        Returns:
            降噪後的影像
        """
        if not self.denoise_enabled or frame is None or frame.size == 0:
            return frame
        
        try:
            if self.denoise_method == "fastNlMeans":
                # 快速非局部平均降噪 (警告: 仍然較慢,建議改用 bilateral 或 gaussian)
                # h: 濾波強度,值越大降噪效果越強但也越模糊
                h = max(1, min(50, self.denoise_strength // 2))  # 降低強度
                # 極致優化: 使用最小參數 (2, 5) 以達到可用速度
                return cv2.fastNlMeansDenoisingColored(
                    frame, None, h, h, 2, 5
                )
            
            elif self.denoise_method == "bilateral":
                # 雙邊濾波 (保留邊緣,適合中等降噪)
                d = 5  # 優化: 從 9 降到 5 以提升速度
                sigma_color = self.denoise_strength * 1.5  # 降低係數
                sigma_space = self.denoise_strength * 1.5
                return cv2.bilateralFilter(
                    frame, d, sigma_color, sigma_space
                )
            
            elif self.denoise_method == "gaussian":
                # 高斯模糊 (最快但會模糊邊緣)
                kernel_size = max(3, (self.denoise_strength // 10) * 2 + 1)  # 必須是奇數
                kernel_size = min(kernel_size, 15)  # 限制最大值
                return cv2.GaussianBlur(
                    frame, (kernel_size, kernel_size), 
                    self.denoise_strength / 10
                )
            
            elif self.denoise_method == "median":
                # 中值濾波 (快速,對椒鹽噪聲特別有效,保留邊緣)
                kernel_size = max(3, (self.denoise_strength // 10) * 2 + 1)
                kernel_size = min(kernel_size, 13)
                return cv2.medianBlur(frame, kernel_size)
            
            elif self.denoise_method == "morphology":
                # 形態學降噪 (非常快,去除小噪點)
                kernel_size = max(3, (self.denoise_strength // 20) * 2 + 1)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                # 先開運算(去除小白點),再閉運算(去除小黑點)
                frame = cv2.morphologyEx(frame, cv2.MORPH_OPEN, kernel)
                frame = cv2.morphologyEx(frame, cv2.MORPH_CLOSE, kernel)
                return frame
            
            elif self.denoise_method == "fastNlMeansGray":
                # 灰階版 fastNlMeans (比彩色版快 3-5倍)
                h = max(1, min(50, self.denoise_strength // 2))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                denoised_gray = cv2.fastNlMeansDenoising(gray, None, h, 3, 7)
                # 將降噪後的灰階圖轉回彩色(保留原始色彩)
                return cv2.cvtColor(denoised_gray, cv2.COLOR_GRAY2BGR)
            
            else:
                print(f"未知的降噪方法: {self.denoise_method}")
                return frame
                
        except Exception as e:
            print(f"⚠️  降噪處理失敗: {e}")
            return frame
    
    def apply_brightness(self, frame: np.ndarray) -> np.ndarray:
        """
        調整影像亮度
        
        Args:
            frame: 輸入影像
        
        Returns:
            調整後的影像
        """
        if self.brightness_adjust == 0 or frame is None:
            return frame
        
        try:
            # 使用 cv2.convertScaleAbs 進行亮度調整
            # beta 參數控制亮度偏移
            return cv2.convertScaleAbs(frame, alpha=1.0, beta=self.brightness_adjust)
        except Exception as e:
            print(f"⚠️  亮度調整失敗: {e}")
            return frame
    
    def apply_contrast(self, frame: np.ndarray) -> np.ndarray:
        """
        調整影像對比度
        
        Args:
            frame: 輸入影像
        
        Returns:
            調整後的影像
        """
        if self.contrast_adjust == 1.0 or frame is None:
            return frame
        
        try:
            # 使用 cv2.convertScaleAbs 進行對比度調整
            # alpha 參數控制對比度縮放
            return cv2.convertScaleAbs(frame, alpha=self.contrast_adjust, beta=0)
        except Exception as e:
            print(f"⚠️  對比度調整失敗: {e}")
            return frame
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        完整的影像處理管線
        
        處理順序:
        1. 降噪
        2. 亮度調整
        3. 對比度調整
        
        Args:
            frame: 輸入影像
        
        Returns:
            處理後的影像
        """
        if frame is None or frame.size == 0:
            return frame
        
        import time
        start_time = time.time()
        
        # 1. 降噪
        if self.denoise_enabled:
            frame = self.apply_denoise(frame)
        
        # 2. 亮度調整
        if self.brightness_adjust != 0:
            frame = self.apply_brightness(frame)
        
        # 3. 對比度調整
        if self.contrast_adjust != 1.0:
            frame = self.apply_contrast(frame)
        
        # 記錄處理時間
        self.processing_time_ms = (time.time() - start_time) * 1000
        self.frame_count += 1
        
        return frame
    
    def update_settings(
        self, 
        enabled: Optional[bool] = None,
        strength: Optional[int] = None,
        method: Optional[str] = None
    ):
        """
        更新降噪設定
        
        Args:
            enabled: 是否啟用降噪
            strength: 降噪強度 (0-100)
            method: 降噪方法 (fastNlMeans, bilateral, gaussian)
        """
        if enabled is not None:
            self.denoise_enabled = enabled
        
        if strength is not None:
            self.denoise_strength = max(0, min(100, strength))
        
        if method is not None:
            valid_methods = ["fastNlMeans", "bilateral", "gaussian", "median", "morphology", "fastNlMeansGray"]
            if method in valid_methods:
                self.denoise_method = method
            else:
                print(f"無效的降噪方法: {method}, 有效選項: {', '.join(valid_methods)}")
    
    def update_image_adjustments(
        self,
        brightness: Optional[int] = None,
        contrast: Optional[float] = None
    ):
        """
        更新影像調整參數
        
        Args:
            brightness: 亮度調整 (-100 to 100)
            contrast: 對比度調整 (0.5 to 2.0)
        """
        if brightness is not None:
            self.brightness_adjust = max(-100, min(100, brightness))
        
        if contrast is not None:
            self.contrast_adjust = max(0.5, min(2.0, contrast))
    
    def get_stats(self) -> dict:
        """
        獲取處理統計資訊
        
        Returns:
            統計資訊字典
        """
        return {
            "denoise_enabled": self.denoise_enabled,
            "denoise_method": self.denoise_method,
            "denoise_strength": self.denoise_strength,
            "brightness_adjust": self.brightness_adjust,
            "contrast_adjust": self.contrast_adjust,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "frame_count": self.frame_count,
            "avg_processing_time_ms": round(
                self.processing_time_ms if self.frame_count == 0 
                else self.processing_time_ms, 2
            )
        }
    
    def reset_stats(self):
        """重置統計資訊"""
        self.processing_time_ms = 0.0
        self.frame_count = 0
