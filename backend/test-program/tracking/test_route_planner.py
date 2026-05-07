import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tracking.planner import RoutePlanner  # noqa: E402
from tracking.planner.models import PlannerBall, RouteCandidate, StrokeHint  # noqa: E402
from tracking.planner.physics_validator import PhysicsValidator  # noqa: E402
from tracking.planner.route_scorer import RouteScorer  # noqa: E402
from tracking.planner.state_extractor import StateExtractor  # noqa: E402


_DEFAULT_NEXT_BALL = object()


def _mock_packet() -> dict:
    return {
        "white_ball": [600, 360, 20, 20],
        "balls": [
            {"x": 760, "y": 330, "w": 20, "h": 20, "radius": 10, "number": 1, "color": "Yellow", "style": "Solid", "conf": 0.9},
            {"x": 890, "y": 300, "w": 20, "h": 20, "radius": 10, "number": 2, "color": "Blue", "style": "Solid", "conf": 0.9},
            {"x": 980, "y": 420, "w": 20, "h": 20, "radius": 10, "number": 3, "color": "Red", "style": "Solid", "conf": 0.9},
        ],
        "holes": [[120, 120], [640, 110], [1160, 120], [120, 600], [640, 610], [1160, 600]],
        "table_roi": [100, 100, 1080, 520],
    }


def _route_for_score(
    route_id: str,
    score: float,
    position_play: dict | None = None,
) -> RouteCandidate:
    return RouteCandidate(
        id=route_id,
        route_type="cut",
        target_ball_number=1,
        first_contact_ball_number=1,
        score=score,
        difficulty=0,
        difficulty_level="medium",
        success_prob=score,
        cut_angle=20.0,
        total_distance=600.0,
        path_points=[],
        route_segments=[],
        cue_landing_point=[100, 100],
        cue_landing_zone=None,
        nodes=[],
        stroke_hint=StrokeHint(type="center", power="medium", spin="none", rationale="test"),
        position_play=position_play,
    )


def _position_play_score(
    shape_quality: float,
    position_success_prob: float,
    risk: float,
    *,
    next_ball=_DEFAULT_NEXT_BALL,
    expected_point: list[int] | None = None,
    avoid_zones: list[dict] | None = None,
) -> dict:
    next_ball_payload = {"number": 2} if next_ball is _DEFAULT_NEXT_BALL else next_ball
    return {
        "schema_version": "position_play.v1",
        "next_ball": next_ball_payload,
        "cue_ball_after_contact": {
            "expected_point": expected_point or [100, 100],
            "target_zone": {"center": [100, 100], "radius": 48.0},
            "avoid_zones": avoid_zones or [],
        },
        "stroke_advice": {},
        "score": {
            "shape_quality": shape_quality,
            "position_success_prob": position_success_prob,
            "risk": risk,
        },
    }


def test_route_planner_generates_candidates():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="practice", top_n=5)
    assert plan is not None
    assert plan["schema_version"] == "planner.result.v1"
    assert plan["rule_profile"] == "practice"
    assert isinstance(plan["routes"], list)
    assert len(plan["routes"]) >= 1


def test_route_planner_9ball_prefers_target_ball():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="9ball", top_n=5, target_ball_number=1)
    assert plan is not None
    assert plan["rule_profile"] == "9ball"
    assert len(plan["routes"]) >= 1
    best = plan.get("best_route")
    assert best is not None
    assert "stroke_hint" in best
    assert "difficulty" in best
    assert best["position_play"]["schema_version"] == "position_play.v1"
    assert best["position_play"]["next_ball"]["number"] == 2


def test_route_planner_outputs_position_play_for_potting_routes():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="practice", top_n=5)

    assert plan is not None
    assert plan["best_route"] is not None
    position_play = plan["best_route"]["position_play"]
    assert position_play["schema_version"] == "position_play.v1"
    assert position_play["next_ball"]["number"] == 2
    assert position_play["cue_ball_after_contact"]["expected_point"] == plan["best_route"]["cue_landing_point"]
    assert position_play["cue_ball_after_contact"]["target_zone"]["center"]
    assert isinstance(position_play["cue_ball_after_contact"]["avoid_zones"], list)
    assert position_play["stroke_advice"]["speed"] == plan["best_route"]["stroke_hint"]["power"]
    assert "position_success_prob" in position_play["score"]


def test_route_scorer_blends_position_play_into_route_order():
    scorer = RouteScorer()
    high_pot_low_shape = _route_for_score(
        "high-pot-low-shape",
        0.70,
        _position_play_score(0.0, 0.0, 1.0),
    )
    lower_pot_good_shape = _route_for_score(
        "lower-pot-good-shape",
        0.62,
        _position_play_score(1.0, 1.0, 0.0),
    )

    routes = [
        scorer.blend_position_play_score(high_pot_low_shape),
        scorer.blend_position_play_score(lower_pot_good_shape),
    ]
    routes.sort(key=lambda route: route.score, reverse=True)

    assert routes[0].id == "lower-pot-good-shape"
    assert high_pot_low_shape.metadata["pre_position_score"] == 0.7
    assert lower_pot_good_shape.score > high_pot_low_shape.score


def test_route_scorer_adds_position_risk_flags():
    scorer = RouteScorer()
    route = _route_for_score(
        "poor-position",
        0.82,
        _position_play_score(
            0.2,
            0.24,
            0.72,
            next_ball=None,
            expected_point=[120, 120],
            avoid_zones=[
                {
                    "type": "pocket_scratch",
                    "pocket_id": "pocket-1",
                    "center": [120, 120],
                    "radius": 30.0,
                }
            ],
        ),
    )

    scorer.blend_position_play_score(route)

    assert "poor_position" in route.risk_flags
    assert "next_ball_missing" in route.risk_flags
    assert "cue_landing_near_pocket" in route.risk_flags


def test_route_planner_handles_missing_state():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet({"white_ball": None}, rule_profile="practice")
    assert plan is None


def test_state_extractor_normalizes_ball_radius():
    state = StateExtractor.from_runtime_packet(
        {
            "white_ball": [600, 360, 20, 20],
            "balls": [
                {"x": 760, "y": 330, "w": 20, "h": 20, "radius": 10, "number": 1, "color": "Yellow", "style": "Solid", "conf": 0.9},
                {"x": 890, "y": 300, "w": 20, "h": 20, "radius": 14, "number": 2, "color": "Blue", "style": "Solid", "conf": 0.9},
                {"x": 980, "y": 420, "w": 20, "h": 20, "radius": 40, "number": 3, "color": "Red", "style": "Solid", "conf": 0.9},
            ],
            "holes": [[120, 120], [640, 110], [1160, 120], [120, 600], [640, 610], [1160, 600]],
            "table_roi": [100, 100, 1080, 520],
        }
    )

    assert state is not None
    assert round(state.table_ball_radius_px, 2) == 14.0
    radii = [round(ball.radius, 2) for ball in state.object_balls]
    assert radii == [12.32, 14.0, 15.68]
    assert state.cue_ball.radius == 12.32
    assert len(state.pockets) == 6
    assert set(state.rail_segments.keys()) == {"top", "bottom", "left", "right"}


def test_capsule_sweep_blocks_nearby_ball():
    validator = PhysicsValidator()
    blockers = [
        PlannerBall(
            x=50,
            y=6,
            w=20,
            h=20,
            radius_px_raw=10,
            radius_px=10,
            radius_source="test",
            number=2,
            color="Blue",
            style="Solid",
            conf=1.0,
        )
    ]

    assert validator.is_path_clear((0.0, 0.0), (100.0, 0.0), blockers, ignore_ball_numbers={0}, safety_radius=10.0) is False


def test_route_planner_returns_no_potting_route_when_all_routes_filtered():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(
        {
            "white_ball": [950, 120, 20, 20],
            "balls": [
                {"x": 220, "y": 180, "w": 20, "h": 20, "radius": 10, "number": 1, "color": "Yellow", "style": "Solid", "conf": 0.9},
                {"x": 244, "y": 176, "w": 20, "h": 20, "radius": 10, "number": 2, "color": "Blue", "style": "Solid", "conf": 0.9},
                {"x": 244, "y": 200, "w": 20, "h": 20, "radius": 10, "number": 3, "color": "Red", "style": "Solid", "conf": 0.9},
                {"x": 196, "y": 200, "w": 20, "h": 20, "radius": 10, "number": 4, "color": "Purple", "style": "Solid", "conf": 0.9},
                {"x": 196, "y": 176, "w": 20, "h": 20, "radius": 10, "number": 5, "color": "Orange", "style": "Solid", "conf": 0.9},
            ],
            "holes": [[120, 120], [640, 110], [1160, 120], [120, 600], [640, 610], [1160, 600]],
            "table_roi": [100, 100, 1080, 520],
        },
        rule_profile="9ball",
        target_ball_number=1,
        max_bounces=0,
        combo_depth=1,
        top_n=5,
    )
    assert plan is not None
    assert plan["best_route"] is None
    assert plan["error"] in {"NO_POTTING_ROUTE", "TARGET_BLOCKED_NO_LEGAL_ROUTE", "ONLY_ESCAPE_ROUTE_AVAILABLE"}


def test_route_planner_generates_geometric_kick_escape_segments():
    planner = RoutePlanner()
    state = StateExtractor.from_runtime_packet(
        {
            "white_ball": [250, 380, 20, 20],
            "balls": [
                {"x": 720, "y": 360, "w": 20, "h": 20, "radius": 10, "number": 1, "color": "Yellow", "style": "Solid", "conf": 0.9},
                {"x": 470, "y": 372, "w": 20, "h": 20, "radius": 10, "number": 2, "color": "Blue", "style": "Solid", "conf": 0.9},
            ],
            "holes": [[120, 120], [640, 110], [1160, 120], [120, 600], [640, 610], [1160, 600]],
            "table_roi": [100, 100, 1080, 520],
        }
    )

    assert state is not None
    routes = planner.generator.generate(state, max_bounces=3, combo_depth=1)
    kick_escape_routes = [
        route
        for route in routes
        if route.metadata.get("base_route_type") == "kick_escape"
    ]

    assert kick_escape_routes
    assert not any(route.metadata.get("fallback_rail_sample") for route in kick_escape_routes)
    assert {route.metadata.get("route_class") for route in kick_escape_routes} <= {"safe_escape", "contact_only"}
    assert any(
        segment.get("type") == "object_after_contact"
        for route in kick_escape_routes
        for segment in route.route_segments
    )


def test_route_planner_diversifies_top_n_by_strategy():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(
        {
            "white_ball": [250, 380, 20, 20],
            "balls": [
                {"x": 720, "y": 360, "w": 20, "h": 20, "radius": 10, "number": 1, "color": "Yellow", "style": "Solid", "conf": 0.9},
                {"x": 470, "y": 372, "w": 20, "h": 20, "radius": 10, "number": 2, "color": "Blue", "style": "Solid", "conf": 0.9},
            ],
            "holes": [[120, 120], [640, 110], [1160, 120], [120, 600], [640, 610], [1160, 600]],
            "table_roi": [100, 100, 1080, 520],
        },
        rule_profile="9ball",
        target_ball_number=1,
        max_bounces=3,
        combo_depth=1,
        top_n=5,
    )

    assert plan is not None
    strategy_keys = {
        (
            route["metadata"].get("route_class"),
            route["route_type"],
            route["metadata"].get("rail"),
            route["metadata"].get("kick_bounces"),
        )
        for route in plan["routes"]
    }
    assert len(strategy_keys) == len(plan["routes"])


def test_route_planner_outputs_p2_physics_metadata():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="practice", top_n=5, max_bounces=3)

    assert plan is not None
    assert plan["routes"]
    physics = plan["routes"][0]["metadata"].get("physics")
    assert isinstance(physics, dict)
    assert physics["model"] == "p2_dynamics_v2"
    assert 0.0 < physics["power_scalar"] <= 1.0
    assert 0.0 < physics["object_speed"] <= 1.0
    assert 0.0 < physics["cue_speed_after"] <= 1.0
    assert "energy_margin" in physics
    assert "object_energy_margin" in physics
    assert "rail_error_px" in physics
    assert "normal_transfer_ratio" in physics
    assert "tangent_retention_ratio" in physics
    assert "throw_error_px" in physics
    assert "pocket_speed_risk" in physics
    assert "line_tolerance_px" in physics


def test_p2_physics_splits_speed_by_cut_angle():
    generator = RoutePlanner().generator
    thin = generator._estimate_physics_model("cut", 65.0, 900.0, bounces=0, combo_depth=1, spin="none")
    full = generator._estimate_physics_model("straight", 4.0, 900.0, bounces=0, combo_depth=1, spin="none")

    assert full["object_speed"] > thin["object_speed"]
    assert thin["cue_speed_after"] > full["cue_speed_after"]
    assert thin["throw_error_px"] > full["throw_error_px"]


def test_p2_running_english_reduces_kick_rail_error():
    generator = RoutePlanner().generator
    no_spin = generator._estimate_physics_model("kick", 35.0, 1300.0, bounces=2, combo_depth=1, rail_angle=70.0, spin="none")
    running = generator._estimate_physics_model("kick", 35.0, 1300.0, bounces=2, combo_depth=1, rail_angle=70.0, spin="running_english")

    assert running["rail_error_px"] < no_spin["rail_error_px"]
    assert running["spin_shift_px"] != 0


def test_manual_stroke_override_changes_stroke_and_cue_leave():
    planner = RoutePlanner()
    auto_plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="practice", top_n=5)
    top_plan = planner.plan_from_runtime_packet(
        _mock_packet(),
        rule_profile="practice",
        top_n=5,
        stroke_override={"tip": "top", "power": "high"},
    )

    assert auto_plan is not None
    assert top_plan is not None
    assert auto_plan["best_route"] is not None
    assert top_plan["best_route"] is not None
    assert top_plan["best_route"]["stroke_hint"]["type"] == "manual_top"
    assert top_plan["best_route"]["stroke_hint"]["power"] == "high"
    assert top_plan["best_route"]["metadata"]["physics"]["top_spin_bias"] == 1.0
    assert top_plan["best_route"]["position_play"]["stroke_advice"]["stroke_type"] == "manual_top"
    assert top_plan["best_route"]["position_play"]["stroke_advice"]["speed"] == "high"
    assert top_plan["best_route"]["position_play"]["stroke_advice"]["cue_tip"]["y"] < 0
    assert top_plan["best_route"]["cue_landing_point"] != auto_plan["best_route"]["cue_landing_point"]


def test_manual_stroke_override_uses_power_percent():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(
        _mock_packet(),
        rule_profile="practice",
        top_n=5,
        stroke_override={"tip": "top_left", "power": "medium_high", "power_percent": 72},
    )

    assert plan is not None
    assert plan["best_route"] is not None
    assert plan["best_route"]["stroke_hint"]["type"] == "manual_top_left_english"
    assert plan["best_route"]["stroke_hint"]["power"] == "medium_high"
    assert plan["best_route"]["metadata"]["physics"]["power_scalar"] == 0.72


def test_manual_stroke_override_uses_continuous_tip_offset():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(
        _mock_packet(),
        rule_profile="practice",
        top_n=5,
        stroke_override={"tip": "draw_right", "power_percent": 60, "tip_x": 0.8, "tip_y": 0.65},
    )

    assert plan is not None
    assert plan["best_route"] is not None
    physics = plan["best_route"]["metadata"]["physics"]
    assert plan["best_route"]["stroke_hint"]["type"] == "manual_continuous_tip"
    assert physics["side_spin_bias"] == 0.8
    assert physics["draw_spin_bias"] == 0.65


def test_straight_shot_cue_leave_does_not_rebound_backward():
    planner = RoutePlanner()
    generator = planner.generator

    contact_point = (500.0, 300.0)
    cue_start = (700.0, 300.0)
    object_dir = (-1.0, 0.0)
    cue_leave, model = generator._estimate_cue_leave(
        cue_start,
        contact_point,
        object_dir,
        table_roi=(100.0, 100.0, 900.0, 450.0),
        speed_scalar=0.2,
        return_model=True,
    )

    assert model == "stop_zone"
    assert cue_leave == contact_point


def test_straight_shot_top_and_draw_change_cue_leave():
    planner = RoutePlanner()
    generator = planner.generator

    contact_point = (500.0, 300.0)
    cue_start = (700.0, 300.0)
    object_dir = (-1.0, 0.0)
    table_roi = (100.0, 100.0, 900.0, 450.0)

    top_leave, top_model = generator._estimate_cue_leave(
        cue_start,
        contact_point,
        object_dir,
        table_roi=table_roi,
        physics={"cue_speed_after": 0.55, "top_spin_bias": 1.0},
        return_model=True,
    )
    draw_leave, draw_model = generator._estimate_cue_leave(
        cue_start,
        contact_point,
        object_dir,
        table_roi=table_roi,
        physics={"cue_speed_after": 0.55, "draw_spin_bias": 1.0},
        return_model=True,
    )

    assert top_model == "stop_zone"
    assert draw_model == "stop_zone"
    assert top_leave[0] < contact_point[0]
    assert draw_leave[0] > contact_point[0]
    assert top_leave != draw_leave


@pytest.mark.parametrize(
    ("tip_x", "tip_y", "expected_side", "expected_top", "expected_draw", "expected_x_direction"),
    [
        (-0.8, -0.65, -0.8, 0.65, 0.0, -1),
        (0.8, -0.65, 0.8, 0.65, 0.0, -1),
        (-0.8, 0.65, -0.8, 0.0, 0.65, 1),
        (0.8, 0.65, 0.8, 0.0, 0.65, 1),
    ],
)
def test_straight_shot_top_draw_with_english_changes_cue_leave(
    tip_x,
    tip_y,
    expected_side,
    expected_top,
    expected_draw,
    expected_x_direction,
):
    planner = RoutePlanner()
    generator = planner.generator
    generator._active_stroke_override = {"tip_x": tip_x, "tip_y": tip_y, "power_percent": 65}

    physics = generator._estimate_physics_model(
        "straight",
        3.0,
        900.0,
        bounces=0,
        combo_depth=1,
        spin="continuous_tip",
        power_hint="medium",
    )
    contact_point = (500.0, 300.0)
    cue_start = (700.0, 300.0)
    object_dir = (-1.0, 0.0)
    cue_leave, model = generator._estimate_cue_leave(
        cue_start,
        contact_point,
        object_dir,
        table_roi=(100.0, 100.0, 900.0, 450.0),
        physics=physics,
        return_model=True,
    )

    assert model == "stop_zone"
    assert physics["side_spin_bias"] == expected_side
    assert physics["top_spin_bias"] == expected_top
    assert physics["draw_spin_bias"] == expected_draw
    assert (cue_leave[0] - contact_point[0]) * expected_x_direction > 0
    assert cue_leave[1] != contact_point[1]


def test_route_planner_holds_target_when_lowest_ball_temporarily_missing():
    planner = RoutePlanner()
    first_plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="practice", top_n=5)
    assert first_plan is not None
    assert first_plan["best_route"] is not None
    assert first_plan["best_route"]["target_ball_number"] == 1

    packet = _mock_packet()
    packet["balls"] = [ball for ball in packet["balls"] if ball["number"] != 1]
    held_plan = planner.plan_from_runtime_packet(packet, rule_profile="practice", top_n=5)

    assert held_plan is not None
    assert held_plan["best_route"] is not None
    assert held_plan["best_route"]["target_ball_number"] == 1
    assert held_plan["error"] == "TARGET_TEMPORARILY_MISSING"
    assert held_plan["hysteresis_hold"] is True


def test_route_planner_9ball_uses_lowest_remaining_ball_when_one_is_gone():
    planner = RoutePlanner()
    packet = _mock_packet()
    packet["balls"] = [ball for ball in packet["balls"] if ball["number"] != 1]

    plan = planner.plan_from_runtime_packet(packet, rule_profile="9ball", top_n=5)

    assert plan is not None
    assert plan["rule_state"]["remaining_ball_numbers"] == [2, 3]
    assert plan["rule_state"]["legal_target_ball_number"] == 2
    if plan["best_route"] is not None:
        assert plan["best_route"]["target_ball_number"] == 2


def test_route_planner_reuses_state_hash_for_micro_jitter():
    planner = RoutePlanner()
    first_plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="practice", top_n=5)
    assert first_plan is not None
    assert first_plan["best_route"] is not None

    packet = _mock_packet()
    packet["white_ball"][0] += 2
    packet["balls"][0]["x"] += 2
    packet["balls"][0]["y"] += 2
    second_plan = planner.plan_from_runtime_packet(packet, rule_profile="practice", top_n=5)

    assert second_plan is not None
    assert second_plan.get("state_hash_reused") is True
    assert second_plan["best_route"]["id"] == first_plan["best_route"]["id"]
