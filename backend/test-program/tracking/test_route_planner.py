import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tracking.planner import RoutePlanner  # noqa: E402
from tracking.planner.models import PlannerBall  # noqa: E402
from tracking.planner.physics_validator import PhysicsValidator  # noqa: E402
from tracking.planner.state_extractor import StateExtractor  # noqa: E402


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


def test_route_planner_generates_candidates():
    planner = RoutePlanner()
    plan = planner.plan_from_runtime_packet(_mock_packet(), rule_profile="practice", top_n=5)
    assert plan is not None
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
