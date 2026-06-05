import copy
import importlib
import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tracking.planner.models import PlannerBall, PlannerState, PocketGeometry, RouteCandidate, StrokeHint  # noqa: E402


CLASS_MODULES = {
    "ShotSimulator": (
        "tracking.planner.shot_simulator",
        "tracking.planner.lookahead_planner",
        "tracking.planner.lookahead",
    ),
    "StateEvaluator": (
        "tracking.planner.state_evaluator",
        "tracking.planner.lookahead_planner",
        "tracking.planner.lookahead",
    ),
    "LookaheadPlanner": (
        "tracking.planner.lookahead_planner",
        "tracking.planner.lookahead",
    ),
}


def _load_class(class_name: str):
    for module_name in CLASS_MODULES[class_name]:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        candidate = getattr(module, class_name, None)
        if candidate is not None:
            return candidate
    pytest.skip(f"{class_name} 尚未實作，保留 lookahead 契約測試")


def _ball(number: int, center: tuple[float, float]) -> PlannerBall:
    return PlannerBall(
        x=center[0] - 10.0,
        y=center[1] - 10.0,
        w=20.0,
        h=20.0,
        radius_px_raw=10.0,
        radius_px=10.0,
        radius_source="test",
        number=number,
        color="test",
        style="Solid",
        conf=1.0,
    )


def _base_state() -> PlannerState:
    pocket = PocketGeometry(
        id="corner-right",
        center=(980.0, 260.0),
        mouth_segment=((980.0, 240.0), (980.0, 280.0)),
        capture_radius=28.0,
        approach_normal=(-1.0, 0.0),
    )
    return PlannerState(
        cue_ball=_ball(0, (220.0, 260.0)),
        object_balls=[
            _ball(1, (360.0, 260.0)),
            _ball(2, (560.0, 260.0)),
            _ball(3, (760.0, 360.0)),
        ],
        holes=[pocket.center],
        pockets=[pocket],
        table_roi=(100.0, 100.0, 900.0, 420.0),
        table_ball_radius_px=10.0,
        rail_segments={},
    )


def _potting_route(
    route_id: str = "pot-1",
    landing_point: list[int] | None = None,
    score: float = 0.7,
) -> RouteCandidate:
    return RouteCandidate(
        id=route_id,
        route_type="cut",
        target_ball_number=1,
        first_contact_ball_number=1,
        score=score,
        difficulty=30,
        difficulty_level="easy",
        success_prob=score,
        cut_angle=10.0,
        total_distance=760.0,
        path_points=[],
        route_segments=[
            {"type": "cue_to_contact", "points": [[220, 260], [340, 260]]},
            {"type": "object_to_pocket", "points": [[360, 260], [980, 260]]},
        ],
        cue_landing_point=landing_point or [420, 260],
        cue_landing_zone=None,
        nodes=[],
        stroke_hint=StrokeHint(type="center", power="medium", spin="none", rationale="test"),
        metadata={
            "potted_ball_number": 1,
            "route_class": "potting_route",
            "physics": {
                "model": "test",
                "object_speed": 0.5,
                "object_energy_margin": 0.0,
                "pocket_speed_risk": 0.0,
                "energy_margin": 0.0,
                "rail_error_px": 0.0,
            },
        },
    )


def _simulate(simulator: Any, state: PlannerState, route: RouteCandidate) -> Any:
    simulate = getattr(simulator, "simulate", None)
    assert callable(simulate), "ShotSimulator 必須提供 simulate(state, route) 介面"
    result = simulate(state, route)
    return result


def _next_state(outcome: Any) -> PlannerState:
    state = getattr(outcome, "next_state", None)
    assert isinstance(state, PlannerState), "ShotSimulator.simulate() 應回傳含 next_state 的 ShotOutcome"
    return state


def _object_numbers(state: PlannerState) -> set[int]:
    return {
        int(ball.number)
        for ball in state.object_balls
        if isinstance(ball.number, int)
    }


def _cue_center(state: PlannerState) -> list[int]:
    return [int(round(state.cue_ball.center[0])), int(round(state.cue_ball.center[1]))]


def _score(evaluator: Any, state: PlannerState, **kwargs: Any) -> float:
    evaluate = getattr(evaluator, "evaluate", None)
    assert callable(evaluate), "StateEvaluator 必須提供 evaluate(state, **kwargs) 介面"
    result = evaluate(state, **kwargs)
    if isinstance(result, dict):
        score = result.get("score", result.get("state_score"))
        assert score is not None
        return float(score)
    return float(result)


def _build_lookahead_planner(cls: Any, simulator: Any, evaluator: Any) -> Any:
    try:
        return cls(simulator=simulator, evaluator=evaluator, depth=2)
    except TypeError:
        planner = cls()
        planner.simulator = simulator
        planner.evaluator = evaluator
        if hasattr(planner, "depth"):
            planner.depth = 2
        return planner


def _select_best_route(planner: Any, state: PlannerState, routes: list[RouteCandidate]) -> Any:
    for method_name in ("select_best_route", "choose_best_route", "plan"):
        method = getattr(planner, method_name, None)
        if not callable(method):
            continue
        result = method(state, routes, rule_profile="9ball", target_ball_number=1)
        if isinstance(result, dict) and isinstance(result.get("best_route"), dict):
            return result["best_route"]
        if isinstance(result, dict):
            return result
        if isinstance(result, RouteCandidate):
            return result
    raise AssertionError("LookaheadPlanner 必須提供 select_best_route/choose_best_route/plan 其中一種介面")


def test_shot_simulator_removes_potted_target_ball():
    simulator = _load_class("ShotSimulator")()

    next_state = _next_state(_simulate(simulator, _base_state(), _potting_route()))

    assert _object_numbers(next_state) == {2, 3}


def test_shot_simulator_updates_cue_ball_to_route_landing_point():
    simulator = _load_class("ShotSimulator")()

    next_state = _next_state(_simulate(simulator, _base_state(), _potting_route(landing_point=[430, 275])))

    assert _cue_center(next_state) == [430, 275]


def test_shot_simulator_does_not_mutate_input_state():
    simulator = _load_class("ShotSimulator")()
    state = _base_state()
    original = copy.deepcopy(state)

    _simulate(simulator, state, _potting_route())

    assert state == original


def test_state_evaluator_prefers_legal_next_ball_shape():
    evaluator = _load_class("StateEvaluator")()
    good_state = _base_state()
    good_state.cue_ball = _ball(0, (510.0, 260.0))
    poor_state = _base_state()
    poor_state.cue_ball = _ball(0, (940.0, 120.0))

    good_score = _score(evaluator, good_state, rule_profile="9ball", target_ball_number=2)
    poor_score = _score(evaluator, poor_state, rule_profile="9ball", target_ball_number=2)

    assert good_score > poor_score


def test_two_ply_lookahead_prefers_lower_immediate_score_with_better_next_state():
    LookaheadPlanner = _load_class("LookaheadPlanner")

    class FakeSimulator:
        def simulate(self, state: PlannerState, route: RouteCandidate) -> dict[str, Any]:
            return {"state_id": route.id}

    class FakeEvaluator:
        def evaluate(self, state: dict[str, Any], **kwargs: Any) -> dict[str, float]:
            values = {"greedy-now": 0.2, "setup-next": 0.95}
            return {"score": values[state["state_id"]]}

    planner = _build_lookahead_planner(LookaheadPlanner, FakeSimulator(), FakeEvaluator())
    routes = [
        _potting_route("greedy-now", landing_point=[930, 120], score=0.86),
        _potting_route("setup-next", landing_point=[510, 260], score=0.68),
    ]

    best_route = _select_best_route(planner, _base_state(), routes)

    best_id = best_route["id"] if isinstance(best_route, dict) else best_route.id
    assert best_id == "setup-next"
