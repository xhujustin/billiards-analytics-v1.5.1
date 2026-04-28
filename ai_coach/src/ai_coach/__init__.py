"""
AI Coach 模組 - 臺球 AI 助教系統

核心功能：
- StabilityDetector：檢測球台靜止狀態
- CoordinateSemanticizer：座標轉語意方位
- AICoachManager：整合管理器，提供實時建議
- draw_coach_panel：渲染中文教練建議面板

使用示例：
    from ai_coach import StabilityDetector, AICoachManager, draw_coach_panel
    
    detector = StabilityDetector()
    is_stable = detector.is_stable(balls=[(100, 100), (150, 150)])
"""

from ai_coach.core import (
    StabilityDetector,
    AICoachManager,
    CoordinateSemanticizer,
    AnalysisResult,
    draw_coach_panel,
    draw_coach_panel_simple,
    CoachPanelRenderer,
    ChineseFontManager,
)

__version__ = "1.0.0"

__all__ = [
    "StabilityDetector",
    "AICoachManager",
    "CoordinateSemanticizer",
    "AnalysisResult",
    "draw_coach_panel",
    "draw_coach_panel_simple",
    "CoachPanelRenderer",
    "ChineseFontManager",
]
