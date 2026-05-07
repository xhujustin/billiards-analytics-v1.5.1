import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_coach import service


def _semantic_context():
    return {
        "valid": True,
        "rules": {"game": "nine_ball", "legal_target_number": 1},
        "balls": [
            {
                "id": "ball-1",
                "number": 1,
                "center": [120, 240],
                "semantic_location": "左側中段",
                "is_legal_target": True,
                "cue_path_clear": True,
                "nearest_pocket": {
                    "name": "左上袋",
                    "distance_px": 320,
                    "path_clear": True,
                    "blocked_by": [],
                },
            }
        ],
    }


def test_build_prompt_summarizes_coach_context_v1_planner(monkeypatch):
    monkeypatch.setattr(service, "AI_COACH_MAX_PROMPT_CHARS", 2000)
    context = {
        "schema_version": "coach.context.v1",
        "semantic_context": _semantic_context(),
        "planner": {
            "best_route": {
                "target_ball_number": 1,
                "target_pocket": "左上袋",
                "route_type": "direct",
                "success_prob": 0.82,
                "risk_flags": ["thin_cut", "scratch_risk"],
            },
            "position_play": {
                "stroke_advice": "中低桿，四分之三力",
                "next_ball": 2,
                "expected_point": [420, 300],
                "target_zone": "中線偏右",
                "risk_flags": ["overrun"],
            },
        },
    }

    prompt = service._build_prompt("這球怎麼打？", context, "合法目標球=1")

    assert "coach.context.v1 planner" in prompt
    assert "打哪顆" in prompt
    assert "target_ball_number" in prompt
    assert "左上袋" in prompt
    assert "direct" in prompt
    assert "success_prob" in prompt
    assert "中低桿，四分之三力" in prompt
    assert "expected_point" in prompt
    assert "target_zone" in prompt
    assert "risk_flags" in prompt


def test_prompts_require_planner_first_and_traditional_chinese_format(monkeypatch):
    monkeypatch.setattr(service, "AI_COACH_MAX_PROMPT_CHARS", 2000)
    prompt = service._build_prompt(
        "給我建議",
        {"schema_version": "coach.context.v1", "semantic_context": _semantic_context()},
        "合法目標球=1",
    )

    assert "不得自行發明球路" in service.NINE_BALL_COACH_SYSTEM_PROMPT
    assert "優先使用 planner.best_route" in service.NINE_BALL_COACH_SYSTEM_PROMPT
    assert "繁體中文" in service.NINE_BALL_COACH_SYSTEM_PROMPT
    assert "請勿新增 planner 沒有提供的路線" in prompt
    for label in ("目標球/袋", "力道", "桿法", "母球走位", "下一球目的", "風險"):
        assert label in prompt


def test_legacy_multi_plan_stays_in_prompt(monkeypatch):
    monkeypatch.setattr(service, "AI_COACH_MAX_PROMPT_CHARS", 2000)
    context = {
        "semantic_context": _semantic_context(),
        "multi_plan": {
            "best_route": {
                "route_type": "bank",
                "target_ball_number": 3,
                "success_prob": 0.41,
                "difficulty_level": "hard",
                "risk_flags": ["traffic"],
            }
        },
    }

    prompt = service._build_prompt("舊格式測試", context, "合法目標球=3")

    assert "舊版 multi_plan" in prompt
    assert "bank" in prompt
    assert "target_ball_number" in prompt
    assert "difficulty_level" in prompt
    assert "traffic" in prompt
