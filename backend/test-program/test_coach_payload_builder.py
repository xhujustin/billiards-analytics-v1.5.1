from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.coach_payload_builder import CoachPayloadBuilder

import main as backend_main


def test_coach_payload_builder_outputs_context_v1_with_planner_debug_signature():
    builder = CoachPayloadBuilder()
    runtime_packet = {
        "status": "ok",
        "frame_count": 12,
        "table_roi": [10, 20, 800, 400],
        "white_ball": [100, 120, 24, 24],
        "balls": [{"id": "ball-1", "number": 1, "x": 200, "y": 220, "w": 24, "h": 24}],
    }
    semantic_context = {
        "valid": True,
        "stable": True,
        "coordinate_space": "original_camera_frame",
        "table": {"pockets": []},
        "cue_ball": {"id": "cue_ball", "center": [112.0, 132.0]},
        "balls": [
            {
                "id": "ball-1",
                "number": 1,
                "center": [212.0, 232.0],
                "nearest_pocket": {"name": "top_left", "path_clear": True},
                "cue_path_clear": True,
            }
        ],
    }
    multi_plan = {
        "schema_version": "planner.result.v1",
        "best_route": {
            "id": "route-1",
            "route_type": "cut",
            "target_ball_number": 1,
            "success_prob": 0.71,
            "position_play": {
                "schema_version": "position_play.v1",
                "stroke_advice": {"speed": "medium"},
            },
        },
        "routes": [],
    }

    payload = builder.build(
        request_type="chat",
        message="下一桿怎麼打？",
        intent="table_dependent",
        response_mode="action_suggestion",
        runtime_packet=runtime_packet,
        semantic_context=semantic_context,
        multi_plan=multi_plan,
        system_status={
            "yolo_status": "online",
            "fps": 28.5,
            "roi_status": "normal",
            "balls_outside_roi": [],
            "hsv_avg": [80, 120, 180],
            "lighting_status": "normal",
        },
        shot_event={
            "event_id": "shot-1",
            "impact_angle": 18.0,
            "ideal_angle": 12.0,
            "velocity_change": 0.22,
            "pocket_result": "made",
        },
        ui_context={
            "auth_type": "guest",
            "user_id": None,
            "username": None,
            "accent_color": "emerald",
        },
        ts_backend=123456,
    )

    assert payload["schema_version"] == "coach.context.v1"
    assert payload["request"]["type"] == "chat"
    assert payload["request"]["response_mode"] == "action_suggestion"
    assert payload["table_state"]["runtime_table"]["table_roi"] == [10, 20, 800, 400]
    assert payload["runtime"]["balls"] == runtime_packet["balls"]
    assert payload["semantic_context"]["cue_ball"]["id"] == "cue_ball"
    assert payload["planner"]["result"] == multi_plan
    assert payload["planner"]["best_route"]["id"] == "route-1"
    assert payload["planner"]["position_play"]["schema_version"] == "position_play.v1"
    assert payload["system_status"]["yolo_status"] == "online"
    assert payload["system_status"]["fps"] == 28.5
    assert payload["shot_event"]["pocket_result"] == "made"
    assert payload["ui_context"]["auth_type"] == "guest"
    assert payload["ui_context"]["accent_color"] == "emerald"
    assert len(payload["debug"]["signature"]) == 64
    assert payload["debug"]["raw_detections"] == runtime_packet["balls"]
    assert payload["table_context_available"] is True
    assert builder.latest() == payload


def test_coach_payload_builder_prefers_backend_multi_plan_over_provided_context():
    builder = CoachPayloadBuilder()
    backend_plan = {
        "schema_version": "planner.result.v1",
        "best_route": {"id": "fresh-route", "target_ball_number": 2},
    }
    stale_plan = {
        "schema_version": "planner.result.v1",
        "best_route": {"id": "stale-route", "target_ball_number": 9},
    }

    payload = builder.build(
        request_type="suggest",
        message="產生建議",
        intent="table_dependent",
        runtime_packet={"status": "ok", "balls": []},
        semantic_context={"valid": True, "stable": True},
        multi_plan=backend_plan,
        provided_context={"multi_plan": stale_plan},
        ts_backend=123456,
    )

    assert payload["planner"]["result"] == backend_plan
    assert payload["planner"]["best_route"]["id"] == "fresh-route"


def test_action_suggestion_backend_cleaner_removes_old_planner_format():
    context = {
        "request": {"type": "action_suggestion", "response_mode": "action_suggestion"},
        "planner": {
            "best_route": {
                "route_type": "cut",
                "risk_flags": ["thick_cut"],
            }
        },
    }
    old_reply = (
        "目標球/袋：先以 #1 為合法首碰，但目前 planner 沒有可採信的進袋路線。\n"
        "力道：小力到中等力道。\n"
        "桿法：中桿，先確保合法碰球。\n"
        "母球走位：不要強行指定走位，優先停在檯面中區或避開袋口。\n"
        "風險：若直接指定袋口，可能與實際球路不符。"
    )

    cleaned = backend_main._clean_action_suggestion_reply(old_reply, context)

    assert "切球點過厚" in cleaned
    assert "容易" in cleaned
    assert "這樣能" in cleaned
    for banned in ("目標球/袋", "力道：", "桿法：", "母球走位：", "風險：", "planner"):
        assert banned not in cleaned
    assert "\n" not in cleaned


def test_action_suggestion_reply_usable_rejects_old_fixed_formats():
    assert backend_main._is_action_suggestion_reply_usable(
        "切球點偏厚，請將瞄準點向薄邊修正，並用中小力保留母球控制。"
    ) is True
    assert backend_main._is_action_suggestion_reply_usable(
        "目標球容易偏厚，請把瞄準點向薄邊修正，並用中小力控制母球。"
    ) is True
    assert backend_main._is_action_suggestion_reply_usable(
        "目標球/袋：#1 下中袋\n力道：中等\nplanner 沒有可採信路線"
    ) is False
    assert backend_main._is_action_suggestion_reply_usable("") is False


def test_action_suggestion_cleaner_can_avoid_fixed_fallback():
    context = {"request": {"type": "action_suggestion", "response_mode": "action_suggestion"}}
    cleaned = backend_main._clean_action_suggestion_reply(
        "目標球/袋：#1 下中袋\n力道：中等\nplanner 沒有可採信路線",
        context,
        allow_fallback=False,
    )

    assert cleaned != backend_main._fallback_action_suggestion_from_context(context)
    assert "planner" not in cleaned
    assert "目標球/袋" not in cleaned


def test_backend_reply_preface_cleaner_answers_directly():
    cleaned = backend_main._strip_coach_reply_preface(
        "根據您詢問的規則問題，在九號球（Nine ball）中，「合法碰球」的定義如下：合法碰球定義：在九號球比賽中，擊球時必須先碰到檯面上號碼最小的球。"
    )

    assert not cleaned.startswith("根據")
    assert "定義如下" not in cleaned
    assert cleaned.startswith("合法碰球是")


def test_rule_question_can_skip_live_analysis():
    assert backend_main._coach_message_can_skip_live_analysis("合法碰球是甚麼") is True


def test_morning_greeting_can_skip_live_analysis():
    assert backend_main._coach_message_can_skip_live_analysis("早上好") is True


def test_billiards_player_question_can_skip_live_analysis():
    assert backend_main._coach_message_can_skip_live_analysis("世界上有名的撞球選手有哪些") is True


def test_standalone_short_knowledge_question_is_not_follow_up():
    context = backend_main._build_coach_conversation_context(
        [
            {"role": "player", "text": "你是男生還是女生"},
            {"role": "coach", "text": "我是 CueVex 的 AI 教練。"},
            {"role": "player", "text": "有名的撞球選手"},
        ],
        "有名的撞球選手",
    )

    assert context["possible_follow_up"] is False
    assert backend_main._coach_message_for_model(
        "有名的撞球選手",
        {"conversation_context": context, "request": {"intent": "non_analysis"}},
    ) == "有名的撞球選手"


def test_social_self_question_is_not_treated_as_follow_up():
    context = backend_main._build_coach_conversation_context(
        [
            {"role": "player", "text": "要去哪裡調整投影機"},
            {"role": "coach", "text": "請到設定 > 球桌校正 > 投影機校正。"},
            {"role": "player", "text": "我帥嗎"},
        ],
        "我帥嗎",
    )

    assert context["possible_follow_up"] is False
    assert backend_main._coach_message_for_model(
        "我帥嗎",
        {"conversation_context": context, "request": {"intent": "non_analysis"}},
    ) == "我帥嗎"


def test_short_follow_up_can_skip_live_analysis():
    assert backend_main._coach_message_can_skip_live_analysis("台灣呢") is True
    assert backend_main._coach_message_requires_visual_analysis("台灣呢") is False


def test_build_conversation_context_marks_follow_up():
    context = backend_main._build_coach_conversation_context(
        [
            {"role": "player", "text": "有名的撞球選手", "timestamp": "t1"},
            {"role": "coach", "text": "Efren Reyes 很有名。", "timestamp": "t2"},
            {"role": "player", "text": "台灣呢", "timestamp": "t3"},
        ],
        "台灣呢",
    )

    assert context["possible_follow_up"] is True
    assert context["last_user_question"] == "有名的撞球選手"
    assert context["last_coach_answer"] == "Efren Reyes 很有名。"
    assert context["recent_messages"][-1]["text"] == "台灣呢"


def test_backend_expands_short_follow_up_for_model_without_hardcoding_answer():
    conversation = backend_main._build_coach_conversation_context(
        [
            {"role": "player", "text": "有名的撞球選手"},
            {"role": "coach", "text": "Efren Reyes、Shane Van Boening 都很常被提到。"},
            {"role": "player", "text": "台灣呢"},
        ],
        "台灣呢",
    )
    model_message = backend_main._coach_message_for_model(
        "台灣呢",
        {"conversation_context": conversation, "request": {"intent": "non_analysis"}},
    )

    assert "上一題：有名的撞球選手" in model_message
    assert "目前追問：台灣呢" in model_message
    assert "Ko Pin Yi" not in model_message
    assert "YOLO" not in model_message
    assert "planner" not in model_message
    assert "資料不足" not in model_message
    assert "系統" not in model_message
    assert "球路" not in model_message


def test_system_operation_synonyms_skip_live_analysis():
    for message in ("字太小要去哪裡改", "球色錯了", "綠框歪掉", "錄影在哪裡看", "存不了設定", "要去哪裡換語言"):
        assert backend_main._coach_message_can_skip_live_analysis(message) is True
        assert backend_main._coach_message_requires_visual_analysis(message) is False


def test_visual_analysis_questions_require_live_analysis():
    for message in ("這一桿怎樣", "下一桿怎麼打", "可以翻袋下中袋嗎", "現在畫面正常嗎", "YOLO 辨識準嗎"):
        assert backend_main._coach_message_can_skip_live_analysis(message) is False
        assert backend_main._coach_message_requires_visual_analysis(message) is True


def test_backend_rule_reply_does_not_reference_planner():
    reply = backend_main._coach_rule_reply("合法碰球 定義")

    assert reply.startswith("合法碰球是")
    assert "planner" not in reply
    assert "NON_ANALYSIS_CHAT" not in reply
    assert "資料" not in reply


def test_backend_ui_reply_answers_color_setting_directly():
    reply = backend_main._coach_ui_reply("要如何更改介面的顏色", {"ui_context": {"auth_type": "user"}})

    assert "設定 > 外觀" in reply
    assert "介面顏色" in reply
    assert "planner" not in reply
    assert "資料不足" not in reply


def test_backend_sanitizer_does_not_template_ui_questions():
    reply = backend_main._sanitize_coach_reply_for_user(
        "由於 planner.best_route 與 planner.position_play 欄位內容為空，目前資料不足以提供具體建議。",
        "要如何更改介面的顏色",
        {"ui_context": {"auth_type": "user"}},
    )

    assert "設定 > 外觀" not in reply
    assert "planner" not in reply
    assert "資料不足" not in reply
    assert "目前資訊有限" in reply


def test_backend_sanitizer_strips_ui_tags_without_rewriting():
    reply = backend_main._sanitize_coach_reply_for_user(
        "如果你想要更像專業訓練台，我會推薦 [emerald]翡翠綠[/emerald]：醒目但不搶戲。",
        "可以換介面顏色嗎",
        {"ui_context": {"auth_type": "user"}},
    )

    assert "翡翠綠" in reply
    assert "醒目但不搶戲" in reply
    assert "設定 > 外觀" not in reply
    assert "[emerald]" not in reply
    assert "[/emerald]" not in reply


def test_backend_sanitizer_cleans_language_setting_without_template():
    reply = backend_main._sanitize_coach_reply_for_user(
        "由於 planner.best_route 欄位內容為空，目前資料不足以提供具體建議。",
        "要去哪裡換語言",
        {},
    )

    assert "設定 > 一般" not in reply
    assert "資料不足" not in reply
    assert "指定目標球" not in reply
    assert "planner" not in reply
    assert "目前資訊有限" in reply


def test_backend_sanitizer_does_not_template_morning_greeting():
    reply = backend_main._sanitize_coach_reply_for_user(
        "由於 planner.best_route 欄位內容為空，目前資料不足以提供具體建議。",
        "早上好",
        {},
    )

    assert "資料不足" not in reply
    assert "指定目標球" not in reply
    assert "planner" not in reply
    assert "目前資訊有限" in reply


def test_backend_sanitizer_does_not_template_billiards_knowledge():
    reply = backend_main._sanitize_coach_reply_for_user(
        "由於 planner.best_route 欄位內容為空，目前資料不足以提供具體建議。",
        "世界上有名的撞球選手有哪些",
        {},
    )

    assert "資料不足" not in reply
    assert "指定目標球" not in reply
    assert "planner" not in reply
    assert "目前資訊有限" in reply


def test_backend_sanitizer_does_not_hardcode_short_knowledge_follow_up():
    reply = backend_main._sanitize_coach_reply_for_user(
        "這題需要更明確的情境才能給到位的建議。你可以直接指定目標球、袋口或想控制的母球位置，我會用球局語言幫你判斷。",
        "台灣呢",
        {
            "conversation_context": {
                "recent_messages": [
                    {"role": "player", "text": "有名的撞球選手"},
                    {"role": "coach", "text": "Efren Reyes、Shane Van Boening 都很有名。"},
                    {"role": "player", "text": "台灣呢"},
                ],
                "last_user_question": "有名的撞球選手",
                "last_coach_answer": "Efren Reyes、Shane Van Boening 都很有名。",
                "possible_follow_up": True,
            }
        },
    )

    assert "需要更明確" not in reply
    assert "指定目標球" not in reply
    assert "袋口" not in reply
    assert "Ko Pin Yi" not in reply
    assert "前面的脈絡" in reply


def test_backend_sanitizer_preserves_table_analysis_answer():
    raw = "由於 planner.best_route 顯示沒有可採信的進袋路線，這顆翻袋打中間風險偏高。"
    reply = backend_main._sanitize_coach_reply_for_user(raw, "可以翻袋打中間嗎", {})

    assert "不建議強攻下中袋" in reply
    assert "母球" in reply
    assert "planner" not in reply
    assert "資料不足" not in reply
    assert "YOLO 辨識穩定" not in reply


def test_backend_sanitizer_rewrites_data_insufficient_table_reply():
    raw = "資料不足，但從畫面看起來可以先打保守路線。"
    reply = backend_main._sanitize_coach_reply_for_user(raw, "可以翻袋打中間嗎", {})

    assert "不建議強攻下中袋" in reply
    assert "檯面中區" in reply
    assert "資料不足" not in reply
    assert "YOLO 辨識穩定" not in reply


def test_backend_status_reply_avoids_yolo_stable_wording():
    reply = backend_main._sanitize_coach_reply_for_user(
        "planner 資料不足",
        "YOLO 辨識穩定嗎",
        {"system_status": {"yolo_status": "online", "fps": 30, "detected_count": 10}},
    )

    assert "持續辨識到 10 顆球" in reply
    assert "穩定" not in reply
    assert "YOLO 辨識穩定" not in reply
    assert "資料不足" not in reply
    assert "10" in reply
