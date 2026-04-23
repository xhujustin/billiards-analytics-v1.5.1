import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tracking.planner import RoutePlanner  # noqa: E402


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
