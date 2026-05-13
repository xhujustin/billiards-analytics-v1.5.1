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


def test_backend_reply_preface_cleaner_answers_directly():
    cleaned = backend_main._strip_coach_reply_preface(
        "根據您詢問的規則問題，在九號球（Nine ball）中，「合法碰球」的定義如下：合法碰球定義：在九號球比賽中，擊球時必須先碰到檯面上號碼最小的球。"
    )

    assert not cleaned.startswith("根據")
    assert "定義如下" not in cleaned
    assert cleaned.startswith("合法碰球是")


def test_rule_question_can_skip_live_analysis():
    assert backend_main._coach_message_can_skip_live_analysis("合法碰球是甚麼") is True


def test_backend_rule_reply_does_not_reference_planner():
    reply = backend_main._coach_rule_reply("合法碰球 定義")

    assert reply.startswith("合法碰球是")
    assert "planner" not in reply
    assert "NON_ANALYSIS_CHAT" not in reply
    assert "資料" not in reply
