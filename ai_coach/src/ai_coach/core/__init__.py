"""AI Coach - 臺球 AI 助教系統 (核心模塊)"""

from ai_coach.core.overlay import StabilityDetector
from ai_coach.core.client import (
    AICoachManager,
    CoordinateSemanticizer,
    AnalysisResult,
)
from ai_coach.core.visualizer import (
    draw_coach_panel,
    draw_coach_panel_simple,
    CoachPanelRenderer,
    ChineseFontManager,
)

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
