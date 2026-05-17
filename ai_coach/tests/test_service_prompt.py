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

    assert "coach.context.v1 路線規劃摘要" in prompt
    assert "打哪顆" in prompt
    assert "target_ball_number" in prompt
    assert "左上袋" in prompt
    assert "direct" in prompt
    assert "success_prob" in prompt
    assert "中低桿，四分之三力" in prompt
    assert "expected_point" in prompt
    assert "target_zone" in prompt
    assert "risk_flags" in prompt


def test_prompts_require_visual_context_without_fixed_output_format(monkeypatch):
    monkeypatch.setattr(service, "AI_COACH_MAX_PROMPT_CHARS", 2000)
    prompt = service._build_prompt(
        "給我建議",
        {"schema_version": "coach.context.v1", "semantic_context": _semantic_context()},
        "合法目標球=1",
    )

    assert "不得自行發明球路" in service.NINE_BALL_COACH_SYSTEM_PROMPT
    assert "優先使用 planner.best_route" in service.NINE_BALL_COACH_SYSTEM_PROMPT
    assert "繁體中文" in service.NINE_BALL_COACH_SYSTEM_PROMPT
    assert "合法目標、最近袋口、清線狀態與阻擋資訊" in prompt
    assert "不要固定列出欄位" in prompt
    assert "不要因為路線規劃為空就回覆資料不足" in prompt
    assert "只回答玩家問到的事項" in prompt
    assert "不要主動延伸成完整戰術報告" in prompt
    assert "自然繁體中文 1 到 2 句" in prompt
    assert "剩餘球號摘要" in prompt
    assert "固定欄位格式" in service._system_prompt("zh-TW")
    assert "格式包含：目標球/袋" not in service._system_prompt("zh-TW")
    for label in ("目標球/袋", "力道：", "桿法：", "母球走位：", "下一球目的：", "風險："):
        assert label not in prompt


def test_prompt_summarizes_remaining_balls_for_next_ball_question(monkeypatch):
    monkeypatch.setattr(service, "AI_COACH_MAX_PROMPT_CHARS", 2000)
    context = {
        "schema_version": "coach.context.v1",
        "semantic_context": {
            "valid": True,
            "rules": {"game": "nine_ball", "legal_target_number": 1},
            "balls": [
                {"number": 1, "is_legal_target": True, "nearest_pocket": {"name": "bottom_right", "path_clear": True}},
                {"number": 4, "is_legal_target": False},
                {"number": 6, "is_legal_target": False},
                {"number": 8, "is_legal_target": False},
            ],
        },
    }

    prompt = service._build_prompt("翻袋打下中洞可以嗎 如果進了下一球要打哪一顆", context, "合法目標球=1")

    assert "visible_object_numbers" in prompt
    assert "next_lowest_after_current_if_potted" in prompt
    assert "4" in prompt


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


def test_social_greeting_uses_gemma_non_visual_prompt_without_analysis_context(monkeypatch):
    non_visual_calls = []

    def fake_non_visual(message, route, context=None, locale="zh-TW"):
        non_visual_calls.append((message, route, context, locale))
        return "Gemma 生成的自然問候，不含球路分析。"

    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    monkeypatch.setattr(service, "_call_vllm_non_visual", fake_non_visual)
    result = service.asyncio.run(service._coach_result("你好，在嗎？", {"system_status": {"yolo_status": "offline"}}))

    assert non_visual_calls == [("你好，在嗎？", "social_greeting", {"system_status": {"yolo_status": "offline"}}, "zh-TW")]
    assert result["recommendation"] == "Gemma 生成的自然問候，不含球路分析。"
    assert result["source"] == "non_visual_chat"


def test_morning_greeting_uses_social_route(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": "早，今天先順順開局。")

    result = service.asyncio.run(service._coach_result("早上好", {"system_status": {"yolo_status": "offline"}}))

    assert result["recommendation"] == "早，今天先順順開局。"
    assert result["source"] == "non_visual_chat"


def test_billiards_knowledge_question_skips_analysis_context(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": "Efren Reyes 是很適合新手研究的撞球選手。")

    result = service.asyncio.run(service._coach_result("世界上有名的撞球選手有哪些", {}))

    assert "Efren Reyes" in result["recommendation"]
    assert result["source"] == "non_visual_chat"


def test_non_visual_follow_up_receives_conversation_context(monkeypatch):
    calls = []

    def fake_non_visual(message, route, context=None, locale="zh-TW"):
        calls.append((message, route, context, locale))
        return "台灣也有不少強者，可以接著看台灣選手的比賽。"

    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    monkeypatch.setattr(service, "_call_vllm_non_visual", fake_non_visual)
    context = {
        "request": {"type": "chat", "intent": "non_analysis"},
        "semantic_context": {"valid": False, "reason": "NON_ANALYSIS_CHAT"},
        "conversation_context": {
            "recent_messages": [
                {"role": "player", "text": "有名的撞球選手"},
                {"role": "coach", "text": "Efren Reyes、Shane Van Boening 都很有名。"},
                {"role": "player", "text": "台灣呢"},
            ],
            "last_user_question": "有名的撞球選手",
            "last_coach_answer": "Efren Reyes、Shane Van Boening 都很有名。",
            "possible_follow_up": True,
        },
    }

    result = service.asyncio.run(service._coach_result("台灣呢", context))

    assert result["source"] == "non_visual_chat"
    assert "台灣" in result["recommendation"]
    assert calls[0][2]["conversation_context"]["possible_follow_up"] is True


def test_non_visual_context_forces_gemma_even_when_message_mentions_internal_words(monkeypatch):
    calls = []

    def fake_non_visual(message, route, context=None, locale="zh-TW"):
        calls.append((message, route, context, locale))
        return "台灣也有不少值得看的選手，可以先從比賽節奏和母球控制學起。"

    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    monkeypatch.setattr(service, "_call_vllm_non_visual", fake_non_visual)

    result = service.asyncio.run(service._coach_result(
        "請延續前文回答，不要提 YOLO 或 planner。目前玩家追問：台灣呢",
        {
            "request": {"type": "chat", "intent": "non_analysis"},
            "semantic_context": {"valid": False, "reason": "NON_ANALYSIS_CHAT"},
            "system_status": {"yolo_status": "online", "fps": 30, "detected_count": 8},
        },
    ))

    assert result["source"] == "non_visual_chat"
    assert "偵測狀態" not in result["recommendation"]
    assert calls[0][1] == "non_visual_chat"


def test_private_question_uses_gemma_social_route(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫")
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": f"{route}: 撞球梗回覆")

    result = service.asyncio.run(service._coach_result("你有女朋友嗎？", {}))

    assert "social_private" in result["recommendation"]
    assert result["source"] == "non_visual_chat"


def test_self_appearance_question_uses_social_route(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫")
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": f"{route}: 撞球梗回覆")

    result = service.asyncio.run(service._coach_result("我帥嗎？", {
        "request": {"type": "chat", "intent": "non_analysis"},
        "semantic_context": {"valid": False, "reason": "NON_ANALYSIS_CHAT"},
        "conversation_context": {
            "recent_messages": [
                {"role": "player", "text": "要去哪裡調整投影機"},
                {"role": "coach", "text": "請到設定 > 球桌校正 > 投影機校正。"},
                {"role": "player", "text": "我帥嗎？"},
            ],
            "possible_follow_up": False,
        },
    }))

    assert "social_private" in result["recommendation"]
    assert result["source"] == "non_visual_chat"


def test_mood_goodbye_identity_and_romance_are_social_routes(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": f"{route}: Gemma social")
    mood = service.asyncio.run(service._coach_result("今天打得很爛...", {}))
    profanity = service.asyncio.run(service._coach_result("甚麼雞掰", {}))
    goodbye = service.asyncio.run(service._coach_result("先這樣，掰掰。", {}))
    identity = service.asyncio.run(service._coach_result("我是Gay", {}))
    romance = service.asyncio.run(service._coach_result("我想跟你談一場激情的戀愛", {}))

    assert mood["source"] == "non_visual_chat"
    assert profanity["source"] == "non_visual_chat"
    assert goodbye["source"] == "non_visual_chat"
    assert identity["source"] == "non_visual_chat"
    assert romance["source"] == "non_visual_chat"


def test_rule_question_uses_non_visual_gemma_without_analysis(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm", lambda *args, **kwargs: "不應該呼叫技術分析")
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": "合法碰球是母球先碰到檯面上號碼最小的球。")
    result = service.asyncio.run(service._coach_result(
        "合法碰球是甚麼",
        {
            "request": {"type": "chat"},
            "semantic_context": {"valid": False, "reason": "NON_ANALYSIS_CHAT"},
            "planner": {"best_route": None, "position_play": {}},
        },
    ))

    reply = result["recommendation"]
    assert result["source"] == "non_visual_chat"
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


def test_no_table_context_still_calls_gemma(monkeypatch):
    calls = []

    def fake_vllm(message, context, semantic, locale="zh-TW"):
        calls.append((message, context, semantic, locale))
        return "目前路線判斷不完整，翻袋下中袋風險偏高。建議先用中桿小力碰到合法目標球，讓母球留在檯面中區。"

    monkeypatch.setattr(service, "_call_vllm", fake_vllm)
    result = service.asyncio.run(service._coach_result(
        "目前有沒有甚麼有機會打進的球",
        {},
    ))

    reply = result["recommendation"]
    assert calls
    assert "路線判斷不完整" in reply
    assert "中桿小力" in reply
    assert "資料不足" not in reply
    assert "planner" not in reply


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


def test_post_shot_analysis_without_event_uses_soft_wording():
    result = service.asyncio.run(service._coach_result("這一桿怎樣？", {}))

    reply = result["recommendation"]
    assert result["source"] == "post_shot_analysis"
    assert "看不到完整擊球結果" in reply
    assert "資料不完整" not in reply
    assert "資料不足" not in reply


def test_ui_support_guest_storage_and_appearance_navigation(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": "你說的設定比較像是外觀設定，請到設定 > 外觀調整主題、字體大小或強調色。")
    storage = service.asyncio.run(service._coach_result(
        "為什麼我存不了設定？",
        {"ui_context": {"auth_type": "guest", "accent_color": "emerald"}},
    ))
    color = service.asyncio.run(service._coach_result(
        "要如何更改介面的顏色？",
        {"ui_context": {"auth_type": "user", "accent_color": "emerald"}},
    ))

    assert "設定" in color["recommendation"]
    assert "外觀" in color["recommendation"]
    assert "強調色" in color["recommendation"]
    assert "[emerald]" not in color["recommendation"]


def test_non_visual_prompt_includes_system_manual_and_guessing_rules():
    messages = service._non_visual_prompt("ui_support", "字太小要去哪裡改", "zh-TW")
    system = messages[0]["content"]

    assert "CueVex 系統操作手冊" in system
    assert "設定 > 外觀" in system
    assert "字體大小" in system
    assert "先猜玩家的非正式說法" in system
    assert "不可使用或要求 YOLO" in system
    assert "[emerald]" in system
    assert "優先回答去哪裡設定" in system


def test_non_visual_prompt_includes_recent_conversation():
    messages = service._non_visual_prompt_with_context(
        "non_visual_chat",
        "台灣呢",
        {
            "conversation_context": {
                "recent_messages": [
                    {"role": "player", "text": "有名的撞球選手"},
                    {"role": "coach", "text": "Efren Reyes 很有名。"},
                    {"role": "player", "text": "台灣呢"},
                ],
                "last_user_question": "有名的撞球選手",
                "last_coach_answer": "Efren Reyes 很有名。",
                "possible_follow_up": True,
            }
        },
        "zh-TW",
    )
    user_content = messages[-1]["content"]
    history_roles = [message["role"] for message in messages[1:-1]]
    history_content = "\n".join(message["content"] for message in messages[1:-1])

    assert "近期對話" in user_content
    assert "有名的撞球選手" in user_content
    assert "台灣呢" in user_content
    assert "可能是追問：是" in user_content
    assert history_roles == ["user", "assistant"]
    assert "有名的撞球選手" in history_content
    assert "Efren Reyes 很有名。" in history_content
    assert "根據近期對話補全問題" in messages[0]["content"]


def test_language_setting_routes_to_non_visual_ui_support(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": "你說的換語言比較像是一般設定，請到設定 > 一般調整語言。")
    result = service.asyncio.run(service._coach_result("要去哪裡換語言", {}))

    assert result["source"] == "non_visual_chat"
    assert "設定 > 一般" in result["recommendation"]
    assert "語言" in result["recommendation"]


def test_ui_support_table_roi_navigation(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_non_visual", lambda message, route, context=None, locale="zh-TW": "你說的邊框不準比較像是球桌校正，請到設定 > 球桌校正 > ROI 微調 / 微調邊框。")
    result = service.asyncio.run(service._coach_result(
        "我想調整球桌邊框 要去哪裡調整",
        {"ui_context": {"auth_type": "user"}},
    ))
    desktop_wording = service.asyncio.run(service._coach_result(
        "我想調整桌面邊框 要去哪裡設定",
        {"ui_context": {"auth_type": "user"}},
    ))

    assert result["source"] == "non_visual_chat"
    assert "設定" in result["recommendation"]
    assert "ROI" in result["recommendation"]
    assert "微調邊框" in result["recommendation"]
    assert desktop_wording["source"] == "non_visual_chat"
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


def test_action_suggestion_outputs_productized_plain_text_without_status_or_raw_data(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_action_suggestion", lambda context, locale="zh-TW": service._action_suggestion_reply(context))
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


def test_action_suggestion_scratch_risk_uses_low_cue_advice(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_action_suggestion", lambda context, locale="zh-TW": service._action_suggestion_reply(context))
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


def test_action_suggestion_without_planner_still_gives_conservative_action(monkeypatch):
    monkeypatch.setattr(service, "_call_vllm_action_suggestion", lambda context, locale="zh-TW": service._action_suggestion_reply(context))
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


def test_action_suggestion_requires_gemma_vllm(monkeypatch):
    def fail_action(context, locale="zh-TW"):
        raise RuntimeError("vLLM unavailable")

    monkeypatch.setattr(service, "_call_vllm_action_suggestion", fail_action)
    result = service.asyncio.run(service._coach_result(
        "產生建議",
        _action_suggestion_context(None),
    ))

    assert result["source"] == "action_suggestion_error"
    assert result["recommendation"] == ""
    assert "vLLM unavailable" in result["error"]


def test_action_suggestion_cleaner_removes_markdown_and_debug_terms():
    cleaned = service._clean_action_suggestion(
        "- 目標球/袋：#1\n- FPS 12\n切球點過厚。Coordinates=(1,2)。請將瞄準點向左修正約 5mm。"
    )

    assert "切球點過厚" in cleaned or "請將瞄準點" in cleaned
    for banned in ("FPS", "Coordinates", "目標球/袋", "-", "\n"):
        assert banned not in cleaned


def test_action_suggestion_prompt_uses_yolo_semantic_summary_before_gemma():
    prompt = service._build_action_suggestion_prompt(
        {
            "schema_version": "coach.context.v1",
            "request": {"type": "action_suggestion", "response_mode": "action_suggestion"},
            "semantic_context": {
                "valid": True,
                "stable": True,
                "rules": {"game": "nine_ball", "legal_target_number": 1},
                "balls": [
                    {
                        "id": "ball-1",
                        "number": 1,
                        "is_legal_target": True,
                        "cue_path_clear": True,
                        "nearest_pocket": {
                            "name": "bottom_right",
                            "distance_px": 246,
                            "path_clear": True,
                            "blocked_by": [],
                        },
                    }
                ],
            },
            "planner": {
                "result": {"schema_version": "planner.result.v1"},
                "best_route": {
                    "route_type": "cut",
                    "risk_flags": ["scratch_risk"],
                    "stroke_hint": {"power": "soft", "spin": "draw"},
                },
                "position_play": {},
            },
        }
    )

    assert "YOLO 辨識後的球局摘要" in prompt
    assert "合法目標與袋口清線" in prompt
    assert "bottom_right" in prompt
    assert "path_clear" in prompt
    assert "交由 Gemma" in prompt
    assert "不可套用固定保守模板" in prompt
    assert "目前盤面資訊" in prompt
    assert "最終輸出不要提 YOLO、planner、JSON 或資料不足" in prompt


def test_clean_recommendation_strips_rule_answer_preface():
    cleaned = service._clean_recommendation(
        "根據您詢問的規則問題，在九號球（Nine ball）中，「合法碰球」的定義如下：合法碰球定義：在九號球比賽中，擊球時必須先碰到檯面上號碼最小的球。"
    )

    assert not cleaned.startswith("根據")
    assert "定義如下" not in cleaned
    assert cleaned.startswith("合法碰球是")
