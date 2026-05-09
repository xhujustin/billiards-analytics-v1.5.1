from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.coach_payload_builder import CoachPayloadBuilder


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
        runtime_packet=runtime_packet,
        semantic_context=semantic_context,
        multi_plan=multi_plan,
        ts_backend=123456,
    )

    assert payload["schema_version"] == "coach.context.v1"
    assert payload["request"]["type"] == "chat"
    assert payload["table_state"]["runtime_table"]["table_roi"] == [10, 20, 800, 400]
    assert payload["runtime"]["balls"] == runtime_packet["balls"]
    assert payload["semantic_context"]["cue_ball"]["id"] == "cue_ball"
    assert payload["planner"]["result"] == multi_plan
    assert payload["planner"]["best_route"]["id"] == "route-1"
    assert payload["planner"]["position_play"]["schema_version"] == "position_play.v1"
    assert len(payload["debug"]["signature"]) == 64
    assert payload["debug"]["raw_detections"] == runtime_packet["balls"]
    assert payload["table_context_available"] is True
    assert builder.latest() == payload
