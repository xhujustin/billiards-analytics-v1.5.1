"""
OpenCV 教練建議面板渲染模組。

實現中文文字渲染、半透明背景、排版等功能。
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, Tuple
import os
from pathlib import Path


class ChineseFontManager:
    """中文字體管理器 - 自動尋找系統字體或自訂字體。"""
    
    # 常見的中文字體路徑（Windows, macOS, Linux）
    FONT_PATHS = {
        'windows': [
            r'C:\Windows\Fonts\msyh.ttc',      # 微軟雅黑
            r'C:\Windows\Fonts\msjh.ttc',      # 微軟正黑體
            r'C:\Windows\Fonts\simhei.ttf',    # 黑體
            r'C:\Windows\Fonts\simsun.ttc',    # 宋體
        ],
        'macos': [
            '/System/Library/Fonts/PingFang.ttc',
            '/Library/Fonts/Arial Unicode.ttf',
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
        ],
        'linux': [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
        ]
    }
    
    def __init__(self, custom_font_dir: Optional[str] = None):
        """
        初始化字體管理器。
        
        Args:
            custom_font_dir: 自訂字體目錄（優先使用）
        """
        self.custom_font_dir = custom_font_dir
        self.selected_font = None
        self.find_font()
    
    def find_font(self) -> Optional[str]:
        """
        尋找可用的中文字體。
        
        Returns:
            字體路徑或 None
        """
        import platform
        
        system = platform.system().lower()
        
        # 優先檢查自訂字體目錄
        if self.custom_font_dir:
            custom_fonts = self._search_fonts_in_dir(self.custom_font_dir)
            if custom_fonts:
                self.selected_font = custom_fonts[0]
                print(f"✅ Found custom font: {self.selected_font}")
                return self.selected_font
        
        # 根據系統尋找字體
        if 'windows' in system:
            paths = self.FONT_PATHS.get('windows', [])
        elif 'darwin' in system:
            paths = self.FONT_PATHS.get('macos', [])
        else:
            paths = self.FONT_PATHS.get('linux', [])
        
        for font_path in paths:
            if os.path.exists(font_path):
                self.selected_font = font_path
                print(f"✅ Found system font: {self.selected_font}")
                return font_path
        
        print("⚠️  No Chinese font found. Please install a CJK font or place one in assets/fonts/")
        return None
    
    @staticmethod
    def _search_fonts_in_dir(directory: str) -> list:
        """搜索目錄中的字體文件。"""
        if not os.path.exists(directory):
            return []
        
        font_extensions = ('.ttf', '.ttc', '.otf')
        fonts = []
        
        for file in os.listdir(directory):
            if file.lower().endswith(font_extensions):
                fonts.append(os.path.join(directory, file))
        
        return fonts
    
    def load_font(self, size: int) -> Optional[ImageFont.FreeTypeFont]:
        """
        加載指定大小的字體。
        
        Args:
            size: 字體大小（像素）
            
        Returns:
            ImageFont 對象或 None
        """
        if not self.selected_font:
            return None
        
        try:
            return ImageFont.truetype(self.selected_font, size)
        except Exception as e:
            print(f"❌ Failed to load font: {e}")
            return None


class CoachPanelRenderer:
    """教練建議面板渲染器。"""
    
    # 配色方案
    COLORS = {
        'background': (0, 0, 0),          # 黑色背景
        'border': (100, 200, 100),        # 綠色邊框
        'title': (100, 255, 100),         # 浅綠文字
        'section': (150, 200, 150),       # 淺綠小標題
        'text': (255, 255, 255),          # 白色正文
        'accent': (255, 255, 100),        # 黃色強調
    }
    
    # Layout 參數
    PANEL_WIDTH = 400
    PANEL_HEIGHT_RATIO = 1.0  # 佔滿高度
    MARGIN = 15
    SECTION_GAP = 15
    LINE_HEIGHT_RATIO = 1.3
    
    def __init__(self, font_dir: Optional[str] = None):
        """
        初始化面板渲染器。
        
        Args:
            font_dir: 字體目錄
        """
        self.font_manager = ChineseFontManager(font_dir)
        self.fonts = {
            'title': self.font_manager.load_font(28),
            'section': self.font_manager.load_font(18),
            'text': self.font_manager.load_font(16),
            'small': self.font_manager.load_font(13),
        }
    
    def render(
        self,
        image: np.ndarray,
        advice_json: Dict[str, Any],
        alpha: float = 0.6,
        position: str = 'right',
    ) -> np.ndarray:
        """
        在影像上渲染教練建議面板。
        
        Args:
            image: OpenCV 影像（BGR）
            advice_json: 建議數據字典
            alpha: 背景透明度 (0-1)
            position: 面板位置 ('left' 或 'right')
            
        Returns:
            渲染後的影像
        """
        height, width = image.shape[:2]
        
        # 1. 計算面板位置
        panel_height = height
        if position == 'right':
            panel_x = width - self.PANEL_WIDTH
            panel_y = 0
        else:  # left
            panel_x = 0
            panel_y = 0
        
        # 2. 建立面板層
        panel = self._create_panel(
            width=self.PANEL_WIDTH,
            height=panel_height,
            advice_json=advice_json,
        )
        
        # 3. Alpha 合成
        result = self._compose_alpha(
            image, panel, panel_x, panel_y, alpha
        )
        
        return result
    
    def _create_panel(
        self,
        width: int,
        height: int,
        advice_json: Dict[str, Any],
    ) -> Image.Image:
        """
        建立面板 PIL Image。
        
        Args:
            width: 面板寬度
            height: 面板高度
            advice_json: 建議數據
            
        Returns:
            PIL Image (RGB)
        """
        # 建立黑色背景
        panel = Image.new('RGB', (width, height), self.COLORS['background'])
        draw = ImageDraw.Draw(panel)
        
        # 繪製邊框
        self._draw_border(draw, width, height)
        
        # 繪製內容
        y_offset = self.MARGIN
        y_offset = self._draw_title(draw, y_offset)
        y_offset = self._draw_section(
            draw, y_offset, "【教練建議】",
            advice_json.get('recommendation', '分析中...')
        )
        y_offset = self._draw_section(
            draw, y_offset, "【推薦打法】",
            advice_json.get('strategy', '等待局面穩定')
        )
        y_offset = self._draw_section(
            draw, y_offset, "【下塞與力道】",
            advice_json.get('force_guide', '根據距離調整力度')
        )
        
        # 繪製置信度和時間戳
        self._draw_footer(draw, width, height, advice_json)
        
        return panel
    
    def _draw_border(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """繪製邊框。"""
        border_color = self.COLORS['border']
        border_width = 3
        
        # 左邊框
        draw.rectangle(
            [(0, 0), (border_width, height)],
            fill=border_color
        )
        # 上邊框
        draw.rectangle(
            [(0, 0), (width, border_width)],
            fill=border_color
        )
        # 右邊框
        draw.rectangle(
            [(width - border_width, 0), (width, height)],
            fill=border_color
        )
    
    def _draw_title(self, draw: ImageDraw.ImageDraw, y: int) -> int:
        """
        繪製標題。
        
        Returns:
            新的 Y 坐標
        """
        if not self.fonts['title']:
            return y
        
        title = "AI 教練"
        draw.text(
            (self.MARGIN, y),
            title,
            font=self.fonts['title'],
            fill=self.COLORS['title'],
        )
        
        return y + 40
    
    def _draw_section(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        section_title: str,
        content: str,
    ) -> int:
        """
        繪製一個內容區塊。
        
        Args:
            draw: PIL Draw 對象
            y: 起始 Y 坐標
            section_title: 區塊標題
            content: 內容文字
            
        Returns:
            新的 Y 坐標
        """
        x = self.MARGIN
        max_width = self.PANEL_WIDTH - 2 * self.MARGIN
        
        # 繪製區塊標題
        if self.fonts['section']:
            draw.text(
                (x, y),
                section_title,
                font=self.fonts['section'],
                fill=self.COLORS['section'],
            )
            y += 25
        
        # 繪製內容（自動換行）
        y = self._draw_wrapped_text(
            draw, x, y, max_width, content,
            self.fonts['text'], self.COLORS['text']
        )
        
        return y + self.SECTION_GAP
    
    def _draw_wrapped_text(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        max_width: int,
        text: str,
        font: Optional[ImageFont.FreeTypeFont],
        color: Tuple[int, int, int],
    ) -> int:
        """
        繪製自動換行的文字。
        
        Args:
            draw: PIL Draw 對象
            x: 起始 X
            y: 起始 Y
            max_width: 最大寬度
            text: 文字內容
            font: 字體
            color: 顏色
            
        Returns:
            結束 Y 坐標
        """
        if not font:
            return y
        
        lines = self._wrap_text(text, font, max_width)
        line_height = int(font.size * self.LINE_HEIGHT_RATIO)
        
        for line in lines:
            draw.text((x, y), line, font=font, fill=color)
            y += line_height
        
        return y
    
    def _wrap_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> list:
        """自動換行文字。"""
        lines = []
        current_line = ""
        
        for char in text:
            test_line = current_line + char
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            
            if width > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _draw_footer(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        advice_json: Dict[str, Any],
    ):
        """繪製頁尾（置信度、時間戳）。"""
        if not self.fonts['small']:
            return
        
        y = height - 50
        confidence = advice_json.get('confidence', 0.0)
        timestamp = advice_json.get('timestamp', '')
        
        # 置信度
        conf_text = f"置信度: {confidence*100:.0f}%"
        draw.text(
            (self.MARGIN, y),
            conf_text,
            font=self.fonts['small'],
            fill=self.COLORS['accent'],
        )
        
        # 時間戳
        if timestamp:
            time_text = timestamp.split('T')[1][:8]  # HH:MM:SS
            draw.text(
                (self.MARGIN, y + 20),
                time_text,
                font=self.fonts['small'],
                fill=self.COLORS['text'],
            )
    
    @staticmethod
    def _compose_alpha(
        image: np.ndarray,
        panel: Image.Image,
        x: int,
        y: int,
        alpha: float,
    ) -> np.ndarray:
        """
        使用 Alpha 合成將面板合併到影像。
        
        Args:
            image: OpenCV 影像 (BGR)
            panel: PIL Image (RGB)
            x, y: 位置
            alpha: 透明度
            
        Returns:
            合併後的影像
        """
        result = image.copy()
        
        # 轉換 PIL Image 為 NumPy
        panel_np = np.array(panel, dtype=np.uint8)
        
        # BGR 轉換 (OpenCV 用 BGR，PIL 用 RGB)
        panel_bgr = cv2.cvtColor(panel_np, cv2.COLOR_RGB2BGR)
        
        # 獲取覆蓋區域
        panel_height, panel_width = panel_bgr.shape[:2]
        x_end = min(x + panel_width, image.shape[1])
        y_end = min(y + panel_height, image.shape[0])
        
        # 調整大小（如果超出邊界）
        if x_end - x < panel_width or y_end - y < panel_height:
            panel_bgr = panel_bgr[:y_end-y, :x_end-x]
        
        # Alpha 合成
        result[y:y_end, x:x_end] = cv2.addWeighted(
            result[y:y_end, x:x_end],
            1 - alpha,
            panel_bgr,
            alpha,
            0
        )
        
        return result


def draw_coach_panel(
    image: np.ndarray,
    advice_json: Dict[str, Any],
    alpha: float = 0.6,
    position: str = 'right',
    font_dir: Optional[str] = None,
) -> np.ndarray:
    """
    在影像上渲染 AI 教練建議面板。
    
    此函數是主要的入點，整合了所有渲染邏輯。
    
    Args:
        image: OpenCV 影像 (BGR format)
        advice_json: 建議數據字典，包含：
            {
                'recommendation': '建議文字',
                'strategy': '推薦打法',
                'force_guide': '力道指引',
                'confidence': 0.85,
                'timestamp': '2026-04-01T10:30:45.123456'
            }
        alpha: 背景透明度 (0-1)，默認 0.6
        position: 面板位置 ('left' 或 'right')，默認 'right'
        font_dir: 自訂字體目錄，默認為 None（自動尋找系統字體）
        
    Returns:
        渲染後的 OpenCV 影像
        
    Example:
        ```python
        import cv2
        
        frame = cv2.imread('pool_table.jpg')
        
        advice = {
            'recommendation': '建議先進紅球3號，可以控制位置',
            'strategy': '斜進法，使用中桿位',
            'force_guide': '中等力道，約70%力度',
            'confidence': 0.87,
            'timestamp': '2026-04-01T10:30:45.123456'
        }
        
        result = draw_coach_panel(frame, advice, alpha=0.6, position='right')
        cv2.imshow('Coach Panel', result)
        cv2.waitKey(0)
        ```
    """
    renderer = CoachPanelRenderer(font_dir)
    return renderer.render(image, advice_json, alpha, position)


# ============================================================================
# 便利函數 - 快速調用
# ============================================================================

def draw_coach_panel_simple(
    image: np.ndarray,
    recommendation: str,
    strategy: str = "",
    force_guide: str = "",
) -> np.ndarray:
    """
    簡化版本 - 直接傳入文字。
    
    Args:
        image: OpenCV 影像
        recommendation: 教練建議
        strategy: 推薦打法
        force_guide: 力道指引
        
    Returns:
        渲染後的影像
    """
    advice = {
        'recommendation': recommendation,
        'strategy': strategy,
        'force_guide': force_guide,
        'confidence': 0.85,
        'timestamp': '',
    }
    return draw_coach_panel(image, advice)


# ============================================================================
# 測試和示例
# ============================================================================

def create_test_image(width: int = 1280, height: int = 960) -> np.ndarray:
    """建立測試影像（藍色球檯）。"""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    # 藍色背景（球檯）
    image[:] = (100, 70, 30)  # BGR: 深藍色調
    
    # 添加一些測試內容
    cv2.putText(
        image,
        "Test Pool Table",
        (50, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (255, 255, 255),
        2
    )
    
    return image


if __name__ == "__main__":
    """測試代碼。"""
    # 建立測試影像
    image = create_test_image(1280, 960)
    
    # 準備測試數據
    advice_data = {
        'recommendation': '建議先進紅球3號，這樣可以很好地控制白球位置到中心區域',
        'strategy': '採用斜進法，使用中桿位點擊白球',
        'force_guide': '中等力道，約70%力度，避免過於用力造成失控',
        'confidence': 0.87,
        'timestamp': '2026-04-01T10:30:45.123456'
    }
    
    # 渲染面板
    result = draw_coach_panel(image, advice_data, alpha=0.65, position='right')
    
    # 顯示結果
    cv2.imshow('Coach Panel Test', result)
    print("✅ Rendering complete. Press any key to exit.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
