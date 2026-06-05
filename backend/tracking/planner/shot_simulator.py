from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional

from .models import PlannerBall, PlannerState, RouteCandidate


Point = tuple[float, float]


@dataclass(frozen=True)
class ShotAction:
    route_id: str
    route_type: str
    target_ball_number: Optional[int]
    cue_landing_point: Optional[list[int]]
    position_play: Optional[dict[str, Any]]
    physics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "route_type": self.route_type,
            "target_ball_number": self.target_ball_number,
            "cue_landing_point": self.cue_landing_point,
            "position_play": self.position_play,
            "physics": self.physics,
        }


@dataclass(frozen=True)
class ShotOutcome:
    action: ShotAction
    next_state: PlannerState
    success_prob: float
    potted_ball_numbers: list[int]
    cue_ball_center: Point
    risk_flags: list[str]
    notes: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "shot_outcome.v1",
            "action": self.action.to_dict(),
            "success_prob": round(float(self.success_prob), 4),
            "potted_ball_numbers": self.potted_ball_numbers,
            "cue_ball_center": [round(float(self.cue_ball_center[0]), 2), round(float(self.cue_ball_center[1]), 2)],
            "risk_flags": self.risk_flags,
            "notes": self.notes,
            "metadata": self.metadata,
        }


class ShotSimulator:
    schema_version = "shot_outcome.v1"

    def simulate(self, state: PlannerState, route: RouteCandidate) -> ShotOutcome:
        physics = self._physics(route)
        action = ShotAction(
            route_id=route.id,
            route_type=route.route_type,
            target_ball_number=route.target_ball_number,
            cue_landing_point=self._cue_landing_point(route),
            position_play=route.position_play,
            physics=physics,
        )

        cue_center = self._next_cue_center(state, route)
        potted_ball_numbers = self._potted_ball_numbers(route, physics)
        next_state = replace(
            state,
            cue_ball=self._move_ball_to_center(state.cue_ball, cue_center),
            object_balls=[
                ball
                for ball in state.object_balls
                if not (isinstance(ball.number, int) and ball.number in potted_ball_numbers)
            ],
        )

        return ShotOutcome(
            action=action,
            next_state=next_state,
            success_prob=self._success_prob(route, physics),
            potted_ball_numbers=potted_ball_numbers,
            cue_ball_center=cue_center,
            risk_flags=list(route.risk_flags),
            notes=self._notes(route, physics, potted_ball_numbers),
            metadata={
                "schema_version": self.schema_version,
                "source": "route_candidate_approximation",
                "route_class": self._route_class(route),
                "position_score": self._position_score(route),
                "physics_model": physics.get("model"),
            },
        )

    @staticmethod
    def _physics(route: RouteCandidate) -> dict[str, Any]:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        physics = metadata.get("physics")
        return dict(physics) if isinstance(physics, dict) else {}

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
    def _cue_landing_point(route: RouteCandidate) -> Optional[list[int]]:
        if route.cue_landing_point is not None and len(route.cue_landing_point) >= 2:
            return [int(route.cue_landing_point[0]), int(route.cue_landing_point[1])]
        for segment in route.route_segments or []:
            if segment.get("type") != "cue_after_contact":
                continue
            points = segment.get("points")
            if isinstance(points, list) and points:
                point = points[-1]
                if isinstance(point, list) and len(point) >= 2:
                    return [int(point[0]), int(point[1])]
        return None

    def _next_cue_center(self, state: PlannerState, route: RouteCandidate) -> Point:
        point = self._cue_landing_point(route)
        if point is None:
            return state.cue_ball.center
        return self._clamp_to_table((float(point[0]), float(point[1])), state.table_roi, state.cue_ball.radius)

    def _potted_ball_numbers(self, route: RouteCandidate, physics: dict[str, Any]) -> list[int]:
        if self._route_class(route) != "potting_route":
            return []
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        number = metadata.get("potted_ball_number", route.target_ball_number)
        if not isinstance(number, int):
            return []

        object_speed = self._float_value(physics.get("object_speed"), default=0.5)
        energy_margin = self._float_value(physics.get("object_energy_margin"), default=0.0)
        pocket_speed_risk = self._float_value(physics.get("pocket_speed_risk"), default=0.0)
        if route.success_prob < 0.2 or object_speed < 0.05 or energy_margin < -0.35 or pocket_speed_risk > 0.95:
            return []
        return [number]

    def _success_prob(self, route: RouteCandidate, physics: dict[str, Any]) -> float:
        success = float(route.success_prob)
        energy_margin = self._float_value(physics.get("energy_margin"), default=0.0)
        pocket_speed_risk = self._float_value(physics.get("pocket_speed_risk"), default=0.0)
        rail_error = self._float_value(physics.get("rail_error_px"), default=0.0)
        success += max(-0.08, min(0.06, energy_margin * 0.08))
        success -= min(0.12, pocket_speed_risk * 0.08)
        success -= min(0.08, rail_error / 500.0)
        return max(0.01, min(0.99, success))

    @staticmethod
    def _position_score(route: RouteCandidate) -> Optional[dict[str, Any]]:
        position_play = route.position_play if isinstance(route.position_play, dict) else {}
        score = position_play.get("score")
        return dict(score) if isinstance(score, dict) else None

    @staticmethod
    def _move_ball_to_center(ball: PlannerBall, center: Point) -> PlannerBall:
        return replace(ball, x=center[0] - ball.w / 2.0, y=center[1] - ball.h / 2.0)

    @staticmethod
    def _clamp_to_table(point: Point, table_roi: tuple[float, float, float, float], margin: float) -> Point:
        x, y, w, h = table_roi
        return (
            max(x + margin, min(x + w - margin, point[0])),
            max(y + margin, min(y + h - margin, point[1])),
        )

    @staticmethod
    def _float_value(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _notes(
        self,
        route: RouteCandidate,
        physics: dict[str, Any],
        potted_ball_numbers: list[int],
    ) -> list[str]:
        notes = ["以 RouteCandidate 的落點、走位與 physics metadata 估算結果。"]
        if potted_ball_numbers:
            notes.append(f"預估進球：{potted_ball_numbers[0]} 號球。")
        elif self._route_class(route) == "potting_route":
            notes.append("此近似模型未判定目標球穩定進袋。")
        if physics.get("model") is not None:
            notes.append(f"physics_model={physics.get('model')}")
        return notes
