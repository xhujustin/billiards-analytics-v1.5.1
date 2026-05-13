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


def test_deterministic_route_reply_uses_planner_pocket_without_vllm_hallucination():
    context = {
        "schema_version": "coach.context.v1",
        "request": {"type": "suggest"},
        "semantic_context": {
            "valid": True,
            "stable": True,
            "rules": {"game": "nine_ball", "legal_target_number": 1},
            "table": {
                "pockets": [
                    {"name": "top_left", "center": [10, 10]},
                    {"name": "bottom_right", "center": [810, 410]},
                ]
            },
            "balls": [
                {
                    "id": "ball-1",
                    "number": 1,
                    "is_legal_target": True,
                    "nearest_pocket": {"name": "top_left", "path_clear": True},
                }
            ],
        },
        "planner": {
            "result": {"schema_version": "planner.result.v1", "error": None},
            "best_route": {
                "route_type": "cut",
                "target_ball_number": 1,
                "success_prob": 0.72,
                "route_segments": [
                    {"type": "object_to_pocket", "points": [[220, 180], [10, 10]]}
                ],
                "stroke_hint": {"power": "medium", "spin": "none"},
                "cue_landing_zone": {"label": "中區安全落點"},
                "risk_flags": ["thin_cut"],
            },
            "position_play": {"next_ball": 2},
        },
    }

    reply = service._deterministic_route_reply(context)

    assert "打 #1" in reply
    assert "左上袋" in reply
    assert "右下袋" not in reply
    assert "中區安全落點" in reply
    assert "#2" in reply


def test_deterministic_route_reply_does_not_invent_pocket_when_best_route_missing():
    context = {
        "schema_version": "coach.context.v1",
        "request": {"type": "suggest"},
        "semantic_context": {
            "valid": True,
            "stable": True,
            "balls": [
                {
                    "id": "ball-1",
                    "number": 1,
                    "is_legal_target": True,
                    "nearest_pocket": {
                        "name": "bottom_right",
                        "path_clear": False,
                        "blocked_by": [{"number": 7}],
                    },
                }
            ],
        },
        "planner": {
            "result": {
                "schema_version": "planner.result.v1",
                "best_route": None,
                "error": "TARGET_BLOCKED_NO_LEGAL_ROUTE",
            },
            "best_route": None,
        },
    }

    reply = service._deterministic_route_reply(context)

    assert "沒有可採信的進袋路線" in reply
    assert "右下袋" not in reply
    assert "先確保合法碰球" in reply


def test_social_greeting_uses_gemma_social_prompt_without_analysis_context(monkeypatch):
    social_calls = []

    def fake_social(message, route, locale="zh-TW"):
        social_calls.append((message, route, locale))
        return "Gemma 生成的自然問候，不含球路分析。"

    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    monkeypatch.setattr(service, "_call_vllm_social", fake_social)
    result = service.asyncio.run(service._coach_result("你好，在嗎？", {"system_status": {"yolo_status": "offline"}}))

    assert social_calls == [("你好，在嗎？", "social_greeting", "zh-TW")]
    assert result["recommendation"] == "Gemma 生成的自然問候，不含球路分析。"
    assert result["source"] == "social_greeting"


def test_private_question_uses_gemma_social_route(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫")
    monkeypatch.setattr(service, "_call_vllm_social", lambda message, route, locale="zh-TW": f"{route}: 撞球梗回覆")

    result = service.asyncio.run(service._coach_result("你有女朋友嗎？", {}))

    assert "social_private" in result["recommendation"]
    assert result["source"] == "social_private"


def test_mood_goodbye_identity_and_romance_are_social_routes(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_social", lambda message, route, locale="zh-TW": f"{route}: Gemma social")
    mood = service.asyncio.run(service._coach_result("今天打得很爛...", {}))
    profanity = service.asyncio.run(service._coach_result("甚麼雞掰", {}))
    goodbye = service.asyncio.run(service._coach_result("先這樣，掰掰。", {}))
    identity = service.asyncio.run(service._coach_result("我是Gay", {}))
    romance = service.asyncio.run(service._coach_result("我想跟你談一場激情的戀愛", {}))

    assert mood["source"] == "social_mood"
    assert profanity["source"] == "social_mood"
    assert goodbye["source"] == "social_goodbye"
    assert identity["source"] == "social_identity"
    assert romance["source"] == "social_romance"


def test_rule_question_answers_directly_without_planner_or_vllm(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    result = service.asyncio.run(service._coach_result(
        "合法碰球是甚麼",
        {
            "request": {"type": "chat"},
            "semantic_context": {"valid": False, "reason": "NON_ANALYSIS_CHAT"},
            "planner": {"best_route": None, "position_play": {}},
        },
    ))

    reply = result["recommendation"]
    assert result["source"] == "rule_support"
    assert reply.startswith("合法碰球是")
    assert "planner" not in reply
    assert "資料不足" not in reply
    assert "根據" not in reply


def test_system_status_warnings_are_deterministic():
    offline = service.asyncio.run(service._coach_result(
        "現在畫面正常嗎？",
        {"system_status": {"yolo_status": "offline", "fps": 30}},
    ))
    low_fps = service.asyncio.run(service._coach_result(
        "我這球打得好嗎？",
        {"system_status": {"yolo_status": "online", "fps": 12.4}},
    ))
    roi = service.asyncio.run(service._coach_result(
        "現在辨識準嗎？",
        {"system_status": {"balls_outside_roi": [{"number": 1}], "fps": 30}},
    ))
    hsv = service.asyncio.run(service._coach_result(
        "畫面正常嗎？",
        {"system_status": {"lighting_status": "too_bright", "fps": 30}},
    ))

    assert "偵測系統暫時斷開" in offline["recommendation"]
    assert "FPS 約 12.4" in low_fps["recommendation"]
    assert "ROI" in roi["recommendation"]
    assert "顏色校正" in hsv["recommendation"]


def test_post_shot_analysis_uses_shot_event():
    result = service.asyncio.run(service._coach_result(
        "這一桿怎樣？",
        {
            "semantic_context": _semantic_context(),
            "shot_event": {
                "impact_angle": 18,
                "ideal_angle": 10,
                "velocity_change": 0.42,
                "pocket_result": "missed",
                "potted_balls": [],
            },
        },
    ))

    assert result["source"] == "post_shot_analysis"
    assert "結果判定" in result["recommendation"]
    assert "物理診斷" in result["recommendation"]
    assert "具體建議" in result["recommendation"]
    assert "打太厚" in result["recommendation"]


def test_ui_support_guest_storage_and_emerald_color():
    storage = service.asyncio.run(service._coach_result(
        "為什麼我存不了設定？",
        {"ui_context": {"auth_type": "guest", "accent_color": "emerald"}},
    ))
    color = service.asyncio.run(service._coach_result(
        "哪種顏色比較好看？",
        {"ui_context": {"auth_type": "user", "accent_color": "emerald"}},
    ))

    assert "訪客模式" in storage["recommendation"]
    assert "SQLite" in storage["recommendation"]
    assert "[emerald]翡翠綠[/emerald]" in color["recommendation"]


def test_ui_support_table_roi_navigation():
    result = service.asyncio.run(service._coach_result(
        "我想調整球桌邊框 要去哪裡調整",
        {"ui_context": {"auth_type": "user"}},
    ))
    desktop_wording = service.asyncio.run(service._coach_result(
        "我想調整桌面邊框 要去哪裡設定",
        {"ui_context": {"auth_type": "user"}},
    ))

    assert result["source"] == "ui_support"
    assert "設定" in result["recommendation"]
    assert "ROI" in result["recommendation"]
    assert desktop_wording["source"] == "ui_support"
    assert "球桌校正" in desktop_wording["recommendation"]
    assert "SQLite" not in desktop_wording["recommendation"]


def _action_suggestion_context(best_route=None):
    return {
        "schema_version": "coach.context.v1",
        "request": {"type": "action_suggestion", "response_mode": "action_suggestion"},
        "semantic_context": {"valid": True, "stable": True, "balls": []},
        "planner": {
            "result": {"schema_version": "planner.result.v1"},
            "best_route": best_route,
            "position_play": {"stroke_advice": {"speed": "medium", "english": "center"}},
        },
        "system_status": {"yolo_status": "offline", "fps": 8, "detected_count": 9},
    }


def test_action_suggestion_outputs_productized_plain_text_without_status_or_raw_data():
    result = service.asyncio.run(service._coach_result(
        "產生建議",
        _action_suggestion_context(
            {
                "route_type": "cut",
                "target_ball_number": 1,
                "success_prob": 0.72,
                "risk_flags": ["thick_cut"],
                "stroke_hint": {"power": "medium", "spin": "center"},
            }
        ),
    ))

    reply = result["recommendation"]
    assert result["source"] == "action_suggestion"
    assert "切球點過厚" in reply
    assert "因為" in reply or "容易" in reply
    assert "這樣能" in reply
    for banned in ("FPS", "VRAM", "Coordinates", "Deviation", "座標", "planner", "YOLO", "目標球/袋", "風險："):
        assert banned not in reply
    assert "\n" not in reply
    assert "[" not in reply and "]" not in reply


def test_action_suggestion_scratch_risk_uses_low_cue_advice():
    result = service.asyncio.run(service._coach_result(
        "產生建議",
        _action_suggestion_context(
            {
                "route_type": "cut",
                "target_ball_number": 1,
                "risk_flags": ["scratch_risk"],
                "stroke_hint": {"power": "medium", "spin": "center"},
            }
        ),
    ))

    assert "低桿" in result["recommendation"] or "中心偏下" in result["recommendation"]
    assert "FPS" not in result["recommendation"]


def test_action_suggestion_without_planner_still_gives_conservative_action():
    result = service.asyncio.run(service._coach_result(
        "產生建議",
        _action_suggestion_context(None),
    ))

    reply = result["recommendation"]
    assert "中桿小力" in reply
    assert "進袋路線不穩" in reply
    assert "這樣能" in reply
    assert "資料不足" not in reply
    assert "planner" not in reply


def test_action_suggestion_cleaner_removes_markdown_and_debug_terms():
    cleaned = service._clean_action_suggestion(
        "- 目標球/袋：#1\n- FPS 12\n切球點過厚。Coordinates=(1,2)。請將瞄準點向左修正約 5mm。"
    )

    assert "切球點過厚" in cleaned or "請將瞄準點" in cleaned
    for banned in ("FPS", "Coordinates", "目標球/袋", "-", "\n"):
        assert banned not in cleaned


def test_clean_recommendation_strips_rule_answer_preface():
    cleaned = service._clean_recommendation(
        "根據您詢問的規則問題，在九號球（Nine ball）中，「合法碰球」的定義如下：合法碰球定義：在九號球比賽中，擊球時必須先碰到檯面上號碼最小的球。"
    )

    assert not cleaned.startswith("根據")
    assert "定義如下" not in cleaned
    assert cleaned.startswith("合法碰球是")
