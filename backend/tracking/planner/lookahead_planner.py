from __future__ import annotations

from typing import Any, Callable, Optional

from .models import PlannerState, RouteCandidate
from .shot_simulator import ShotSimulator
from .state_evaluator import StateEvaluator


NextRouteProvider = Callable[[Any, str, Optional[int], int], list[RouteCandidate]]


class LookaheadPlanner:
    schema_version = "planner.lookahead.v1"

    def __init__(
        self,
        simulator: Optional[Any] = None,
        evaluator: Optional[Any] = None,
        depth: int = 2,
        score_weight: float = 0.70,
        next_route_provider: Optional[NextRouteProvider] = None,
    ) -> None:
        self.simulator = simulator or ShotSimulator()
        self.evaluator = evaluator or StateEvaluator()
        self.depth = max(1, min(2, int(depth)))
        self.score_weight = self._clamp01(score_weight)
        self.next_route_provider = next_route_provider

    def select_best_route(
        self,
        state: PlannerState,
        routes: list[RouteCandidate],
        rule_profile: str = "practice",
        target_ball_number: Optional[int] = None,
        next_top_n: int = 3,
        score_weight: Optional[float] = None,
        next_route_provider: Optional[NextRouteProvider] = None,
    ) -> Optional[RouteCandidate]:
        evaluated = self.evaluate_routes(
            state,
            routes,
            rule_profile=rule_profile,
            target_ball_number=target_ball_number,
            next_top_n=next_top_n,
            score_weight=score_weight,
            next_route_provider=next_route_provider,
        )
        if not evaluated:
            return None
        evaluated.sort(key=lambda route: route.score, reverse=True)
        return evaluated[0]

    def evaluate_routes(
        self,
        state: PlannerState,
        routes: list[RouteCandidate],
        rule_profile: str = "practice",
        target_ball_number: Optional[int] = None,
        next_top_n: int = 3,
        score_weight: Optional[float] = None,
        next_route_provider: Optional[NextRouteProvider] = None,
    ) -> list[RouteCandidate]:
        weight = self._clamp01(self.score_weight if score_weight is None else score_weight)
        provider = next_route_provider or self.next_route_provider
        for route in routes:
            self._evaluate_route(
                state,
                route,
                rule_profile=rule_profile,
                target_ball_number=target_ball_number,
                next_top_n=next_top_n,
                score_weight=weight,
                next_route_provider=provider,
            )
        return routes

    def plan(
        self,
        state: PlannerState,
        routes: list[RouteCandidate],
        rule_profile: str = "practice",
        target_ball_number: Optional[int] = None,
        next_top_n: int = 3,
        score_weight: Optional[float] = None,
        next_route_provider: Optional[NextRouteProvider] = None,
    ) -> dict[str, Any]:
        best = self.select_best_route(
            state,
            routes,
            rule_profile=rule_profile,
            target_ball_number=target_ball_number,
            next_top_n=next_top_n,
            score_weight=score_weight,
            next_route_provider=next_route_provider,
        )
        return {
            "best_route": best.to_dict() if isinstance(best, RouteCandidate) else None,
            "routes": [route.to_dict() for route in routes],
        }

    def _evaluate_route(
        self,
        state: PlannerState,
        route: RouteCandidate,
        rule_profile: str,
        target_ball_number: Optional[int],
        next_top_n: int,
        score_weight: float,
        next_route_provider: Optional[NextRouteProvider],
    ) -> None:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        route.metadata = metadata
        pre_score = self._clamp01(route.score)

        if self._route_class(route) != "potting_route":
            metadata["lookahead"] = self._payload(
                status="skipped_non_potting",
                pre_score=pre_score,
                final_score=pre_score,
                score_weight=score_weight,
            )
            return

        try:
            outcome = self.simulator.simulate(state, route)
        except Exception as exc:
            metadata["lookahead"] = self._payload(
                status="simulation_failed",
                pre_score=pre_score,
                final_score=pre_score,
                score_weight=score_weight,
                warnings=[str(exc)],
            )
            return

        next_state = self._outcome_value(outcome, "next_state", outcome if isinstance(outcome, dict) else None)
        potted_numbers = self._as_int_list(self._outcome_value(outcome, "potted_ball_numbers", []))
        invalid_reason = self._invalid_outcome_reason(state, route, next_state, potted_numbers)
        if invalid_reason is not None:
            evaluation = self._evaluate_state(
                next_state,
                rule_profile=rule_profile,
                target_ball_number=target_ball_number,
            )
            state_score = self._score_from_evaluation(evaluation)
            lookahead_score = self._clamp01(state_score * 0.45)
            final_score = self._clamp01(pre_score * (1.0 - score_weight) + lookahead_score * score_weight)
            route.score = final_score
            route.success_prob = max(0.01, min(0.99, final_score))
            metadata["lookahead"] = self._payload(
                status="invalid_cue_state",
                pre_score=pre_score,
                final_score=final_score,
                score_weight=score_weight,
                potted_ball_numbers=potted_numbers,
                next_target_ball_number=target_ball_number,
                cue_ball_center=self._outcome_value(outcome, "cue_ball_center", None),
                state_score=state_score,
                next_best_score=0.0,
                lookahead_score=lookahead_score,
                evaluation=evaluation,
                next_routes=[],
                simulator_metadata=self._outcome_value(outcome, "metadata", {}),
                warnings=[*self._outcome_value(outcome, "notes", []), invalid_reason],
            )
            return

        next_target = self._next_target_ball_number(next_state, target_ball_number, potted_numbers, rule_profile)
        next_routes: list[RouteCandidate] = []
        if self.depth >= 2 and next_route_provider is not None:
            try:
                next_routes = next_route_provider(next_state, rule_profile, next_target, next_top_n)
            except Exception:
                next_routes = []

        evaluation = self._evaluate_state(
            next_state,
            rule_profile=rule_profile,
            target_ball_number=next_target,
        )
        state_score = self._score_from_evaluation(evaluation)
        next_best_score = max((self._clamp01(route.score) for route in next_routes), default=0.0)
        lookahead_score = self._clamp01(state_score * 0.65 + next_best_score * 0.35)
        if not next_routes and next_route_provider is not None:
            lookahead_score = self._clamp01(lookahead_score * 0.82)
        final_score = self._clamp01(pre_score * (1.0 - score_weight) + lookahead_score * score_weight)

        route.score = final_score
        route.success_prob = max(0.01, min(0.99, final_score))
        metadata["lookahead"] = self._payload(
            status="ok" if next_routes or next_route_provider is None else "no_next_route",
            pre_score=pre_score,
            final_score=final_score,
            score_weight=score_weight,
            potted_ball_numbers=potted_numbers,
            next_target_ball_number=next_target,
            cue_ball_center=self._outcome_value(outcome, "cue_ball_center", None),
            state_score=state_score,
            next_best_score=next_best_score,
            lookahead_score=lookahead_score,
            evaluation=evaluation,
            selected_next_route=next_routes[0] if next_routes else None,
            next_routes=next_routes[:next_top_n],
            simulator_metadata=self._outcome_value(outcome, "metadata", {}),
            warnings=self._outcome_value(outcome, "notes", []),
        )

    def _evaluate_state(
        self,
        state: Any,
        rule_profile: str,
        target_ball_number: Optional[int],
    ) -> Any:
        evaluate = getattr(self.evaluator, "evaluate", None)
        if not callable(evaluate):
            return {"state_score": 0.0, "risk_score": 1.0, "explanation": ["evaluator_missing"]}
        return evaluate(state, rule_profile=rule_profile, target_ball_number=target_ball_number)

    @classmethod
    def _payload(
        cls,
        status: str,
        pre_score: float,
        final_score: float,
        score_weight: float,
        potted_ball_numbers: Optional[list[int]] = None,
        next_target_ball_number: Optional[int] = None,
        cue_ball_center: Any = None,
        state_score: float = 0.0,
        next_best_score: float = 0.0,
        lookahead_score: float = 0.0,
        evaluation: Any = None,
        selected_next_route: Optional[RouteCandidate] = None,
        next_routes: Optional[list[RouteCandidate]] = None,
        simulator_metadata: Any = None,
        warnings: Optional[list[Any]] = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": cls.schema_version,
            "enabled": True,
            "ply": 2,
            "status": status,
            "simulator": {
                "model": "shot_simulator.v1",
                "confidence": round(cls._simulator_confidence(simulator_metadata), 4),
            },
            "state": {
                "potted_ball_numbers": potted_ball_numbers or [],
                "next_target_ball_number": next_target_ball_number,
                "cue_ball_center": cls._point_payload(cue_ball_center),
            },
            "evaluation": {
                "state_score": round(cls._clamp01(state_score), 4),
                "next_best_score": round(cls._clamp01(next_best_score), 4),
                "score": round(cls._clamp01(lookahead_score), 4),
                "score_weight": round(cls._clamp01(score_weight), 4),
                "pre_lookahead_score": round(cls._clamp01(pre_score), 4),
                "final_score": round(cls._clamp01(final_score), 4),
                "details": evaluation if isinstance(evaluation, dict) else {},
            },
            "selected_next_route_id": selected_next_route.id if selected_next_route is not None else None,
            "next_routes": [cls._route_summary(route) for route in (next_routes or [])],
            "warnings": [str(item) for item in (warnings or [])],
        }

    @staticmethod
    def _route_class(route: RouteCandidate) -> str:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        route_class = metadata.get("route_class")
        if isinstance(route_class, str) and route_class:
            return route_class
        if route.route_type in {"safe_escape", "contact_only", "kick_escape"}:
            return route.route_type
        return "potting_route"

    @staticmethod
    def _outcome_value(outcome: Any, key: str, default: Any) -> Any:
        if isinstance(outcome, dict):
            return outcome.get(key, default)
        return getattr(outcome, key, default)

    @classmethod
    def _score_from_evaluation(cls, evaluation: Any) -> float:
        if isinstance(evaluation, dict):
            value = evaluation.get("state_score", evaluation.get("score", 0.0))
            return cls._clamp01(value)
        return cls._clamp01(evaluation)

    @staticmethod
    def _next_target_ball_number(
        state: Any,
        target_ball_number: Optional[int],
        potted_ball_numbers: list[int],
        rule_profile: str,
    ) -> Optional[int]:
        balls = getattr(state, "object_balls", None)
        if not isinstance(balls, list):
            return target_ball_number
        numbers = sorted(
            int(ball.number)
            for ball in balls
            if isinstance(getattr(ball, "number", None), int) and int(ball.number) > 0
        )
        if not numbers:
            return None
        if rule_profile == "9ball":
            return numbers[0]
        if target_ball_number in potted_ball_numbers:
            greater = [number for number in numbers if target_ball_number is None or number > target_ball_number]
            return greater[0] if greater else numbers[0]
        return target_ball_number

    @staticmethod
    def _as_int_list(value: Any) -> list[int]:
        if not isinstance(value, list):
            return []
        return [int(item) for item in value if isinstance(item, int)]

    @classmethod
    def _invalid_outcome_reason(
        cls,
        state: PlannerState,
        route: RouteCandidate,
        next_state: Any,
        potted_numbers: list[int],
    ) -> Optional[str]:
        if not potted_numbers:
            return "lookahead_skipped_target_not_potted"
        if "cue_leave_hits_object_ball" in route.risk_flags:
            return "lookahead_skipped_cue_leave_hits_object_ball"
        if "cue_landing_near_pocket" in route.risk_flags:
            return "lookahead_skipped_cue_landing_near_pocket"

        cue_ball = getattr(next_state, "cue_ball", None)
        cue_center = getattr(cue_ball, "center", None)
        cue_radius = cls._float_attr(cue_ball, "radius", cls._float_attr(state.cue_ball, "radius", 12.0))
        if not isinstance(cue_center, tuple) or len(cue_center) < 2:
            return "lookahead_skipped_missing_cue_landing"
        cx, cy = float(cue_center[0]), float(cue_center[1])

        for ball in getattr(next_state, "object_balls", []) or []:
            ball_center = getattr(ball, "center", None)
            if not isinstance(ball_center, tuple) or len(ball_center) < 2:
                continue
            ball_radius = cls._float_attr(ball, "radius", cue_radius)
            min_clearance = max(cue_radius + ball_radius + 3.0, cue_radius * 2.05)
            if cls._distance((cx, cy), (float(ball_center[0]), float(ball_center[1]))) <= min_clearance:
                number = getattr(ball, "number", None)
                return f"lookahead_skipped_cue_landing_overlaps_ball_{number}"

        for pocket in getattr(next_state, "pockets", []) or []:
            pocket_center = getattr(pocket, "center", None)
            if not isinstance(pocket_center, tuple) or len(pocket_center) < 2:
                continue
            capture_radius = cls._float_attr(pocket, "capture_radius", cue_radius * 2.0)
            min_clearance = max(capture_radius * 1.2, cue_radius * 2.4)
            if cls._distance((cx, cy), (float(pocket_center[0]), float(pocket_center[1]))) <= min_clearance:
                return "lookahead_skipped_cue_landing_near_pocket"

        return None

    @staticmethod
    def _float_attr(obj: Any, name: str, default: float) -> float:
        try:
            value = getattr(obj, name)
            return float(value() if callable(value) else value)
        except (TypeError, ValueError, AttributeError):
            return float(default)

    @staticmethod
    def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return (dx * dx + dy * dy) ** 0.5

    @classmethod
    def _route_summary(cls, route: RouteCandidate) -> dict[str, Any]:
        position_play = route.position_play if isinstance(route.position_play, dict) else {}
        position_score = position_play.get("score") if isinstance(position_play.get("score"), dict) else {}
        cue_after = position_play.get("cue_ball_after_contact") if isinstance(position_play.get("cue_ball_after_contact"), dict) else {}
        target_zone = cue_after.get("target_zone") if isinstance(cue_after.get("target_zone"), dict) else {}
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        return {
            "id": route.id,
            "route_type": route.route_type,
            "target_ball_number": route.target_ball_number,
            "score": round(float(route.score), 4),
            "success_prob": round(float(route.success_prob), 4),
            "position_success_prob": position_score.get("position_success_prob"),
            "strategy_label": metadata.get("strategy_label"),
            "route_segments": [
                {
                    "type": segment.get("type", "unknown"),
                    "points": segment.get("points", []),
                    "color": segment.get("color"),
                }
                for segment in (route.route_segments or [])
                if isinstance(segment, dict)
            ],
            "cue_landing_point": cls._point_payload(route.cue_landing_point),
            "cue_landing_zone": route.cue_landing_zone if isinstance(route.cue_landing_zone, dict) else None,
            "cue_target_zone": {
                "center": cls._point_payload(target_zone.get("center")),
                "radius": target_zone.get("radius"),
                "label": target_zone.get("label"),
            } if target_zone else None,
            "stroke_hint": {
                "type": getattr(route.stroke_hint, "type", None),
                "power": getattr(route.stroke_hint, "power", None),
                "spin": getattr(route.stroke_hint, "spin", None),
            },
        }

    @staticmethod
    def _point_payload(value: Any) -> Optional[list[float]]:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        try:
            return [round(float(value[0]), 2), round(float(value[1]), 2)]
        except (TypeError, ValueError):
            return None

    @classmethod
    def _simulator_confidence(cls, metadata: Any) -> float:
        if not isinstance(metadata, dict):
            return 0.55
        if metadata.get("source") == "route_candidate_approximation":
            return 0.68
        return 0.55

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.0
        return max(0.0, min(1.0, parsed))
