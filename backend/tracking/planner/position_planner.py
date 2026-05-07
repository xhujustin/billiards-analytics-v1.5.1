from __future__ import annotations

import math
from typing import Any, Optional

from .models import PlannerBall, PlannerState, PocketGeometry, RouteCandidate


class PositionPlanner:
    schema_version = "position_play.v1"

    def plan(
        self,
        state: PlannerState,
        route: RouteCandidate,
        rule_profile: str = "practice",
        target_ball_number: Optional[int] = None,
    ) -> dict[str, Any]:
        next_ball = self._next_ball(state, route, rule_profile, target_ball_number)
        expected_point = self._expected_point(route)
        preferred_pocket = self._preferred_pocket(state, next_ball) if next_ball else None
        target_zone = self._target_zone(state, next_ball, preferred_pocket, route)
        avoid_zones = self._avoid_zones(state, route, next_ball)
        stroke_advice = self._stroke_advice(route)
        score = self._score(route, expected_point, target_zone, avoid_zones)

        return {
            "schema_version": self.schema_version,
            "next_ball": self._next_ball_payload(next_ball, preferred_pocket),
            "cue_ball_after_contact": {
                "expected_point": expected_point,
                "target_zone": target_zone,
                "avoid_zones": avoid_zones,
            },
            "stroke_advice": stroke_advice,
            "score": score,
        }

    @staticmethod
    def _expected_point(route: RouteCandidate) -> Optional[list[int]]:
        if route.cue_landing_point is not None:
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

    @staticmethod
    def _route_class(route: RouteCandidate) -> str:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        route_class = metadata.get("route_class")
        if isinstance(route_class, str) and route_class:
            return route_class
        if route.route_type in {"safe_escape", "contact_only", "kick_escape"}:
            return route.route_type
        return "potting_route"

    def _next_ball(
        self,
        state: PlannerState,
        route: RouteCandidate,
        rule_profile: str,
        target_ball_number: Optional[int],
    ) -> Optional[PlannerBall]:
        current = route.target_ball_number
        numbered = sorted(
            (ball for ball in state.object_balls if isinstance(ball.number, int) and ball.number > 0),
            key=lambda ball: int(ball.number or 0),
        )
        if not numbered:
            return None

        if rule_profile == "9ball":
            floor = current if isinstance(current, int) else target_ball_number
            for ball in numbered:
                if isinstance(floor, int) and ball.number == floor:
                    continue
                if not isinstance(floor, int) or int(ball.number or 0) > floor:
                    return ball
            return None

        for ball in numbered:
            if ball.number != current:
                return ball
        return None

    @staticmethod
    def _preferred_pocket(state: PlannerState, ball: Optional[PlannerBall]) -> Optional[PocketGeometry]:
        if ball is None or not state.pockets:
            return None
        center = ball.center
        return min(
            state.pockets,
            key=lambda pocket: math.hypot(center[0] - pocket.center[0], center[1] - pocket.center[1]),
        )

    def _target_zone(
        self,
        state: PlannerState,
        ball: Optional[PlannerBall],
        pocket: Optional[PocketGeometry],
        route: RouteCandidate,
    ) -> Optional[dict[str, Any]]:
        if ball is None:
            return None
        if pocket is None:
            center = ball.center
        else:
            ball_center = ball.center
            dx = pocket.center[0] - ball_center[0]
            dy = pocket.center[1] - ball_center[1]
            dist = math.hypot(dx, dy)
            if dist <= 1e-6:
                center = ball_center
            else:
                leave_distance = max(state.table_ball_radius_px * 4.0, 44.0)
                center = (
                    ball_center[0] - dx / dist * leave_distance,
                    ball_center[1] - dy / dist * leave_distance,
                )
        center = self._clamp_to_table(center, state.table_roi, state.cue_ball.radius * 1.6)
        radius = max(36.0, min(72.0, state.table_ball_radius_px * (4.4 - min(route.cut_angle, 70.0) / 70.0)))
        return {
            "center": self._round_point(center),
            "radius": round(radius, 2),
            "label": "下一球走位目標區",
        }

    def _avoid_zones(
        self,
        state: PlannerState,
        route: RouteCandidate,
        next_ball: Optional[PlannerBall],
    ) -> list[dict[str, Any]]:
        zones: list[dict[str, Any]] = []
        protected = {
            route.target_ball_number,
            route.first_contact_ball_number,
            next_ball.number if next_ball is not None else None,
        }
        for ball in state.object_balls:
            if ball.number in protected:
                continue
            zones.append(
                {
                    "type": "object_ball",
                    "number": ball.number,
                    "center": self._round_point(ball.center),
                    "radius": round(max(ball.radius * 2.25, state.table_ball_radius_px * 2.25), 2),
                }
            )
        for pocket in state.pockets:
            zones.append(
                {
                    "type": "pocket_scratch",
                    "pocket_id": pocket.id,
                    "center": self._round_point(pocket.center),
                    "radius": round(max(pocket.capture_radius, state.table_ball_radius_px * 2.4), 2),
                }
            )
        return zones

    @staticmethod
    def _next_ball_payload(
        ball: Optional[PlannerBall],
        pocket: Optional[PocketGeometry],
    ) -> Optional[dict[str, Any]]:
        if ball is None:
            return None
        return {
            "number": ball.number,
            "center": [round(float(ball.center[0]), 2), round(float(ball.center[1]), 2)],
            "preferred_pocket_id": pocket.id if pocket is not None else None,
        }

    @staticmethod
    def _stroke_advice(route: RouteCandidate) -> dict[str, Any]:
        physics = {}
        if isinstance(route.metadata, dict) and isinstance(route.metadata.get("physics"), dict):
            physics = route.metadata["physics"]
        return {
            "speed": route.stroke_hint.power,
            "english": route.stroke_hint.spin,
            "cue_tip": {
                "x": round(float(physics.get("side_spin_bias", 0.0) or 0.0), 3),
                "y": round(float(physics.get("draw_spin_bias", 0.0) or 0.0) - float(physics.get("top_spin_bias", 0.0) or 0.0), 3),
            },
            "stroke_type": route.stroke_hint.type,
            "reason": route.stroke_hint.rationale,
        }

    def _score(
        self,
        route: RouteCandidate,
        expected_point: Optional[list[int]],
        target_zone: Optional[dict[str, Any]],
        avoid_zones: list[dict[str, Any]],
    ) -> dict[str, float]:
        shape_quality = max(0.0, min(1.0, route.success_prob))
        if expected_point is not None and target_zone is not None:
            center = target_zone.get("center")
            radius = float(target_zone.get("radius", 1.0) or 1.0)
            if isinstance(center, list) and len(center) >= 2:
                distance = math.hypot(expected_point[0] - center[0], expected_point[1] - center[1])
                shape_quality = max(0.0, min(1.0, 1.0 - distance / max(radius * 3.2, 1.0)))
        risk = min(0.95, max(0.0, 1.0 - route.success_prob + len(route.risk_flags) * 0.04 + min(len(avoid_zones), 8) * 0.01))
        position_success = max(0.01, min(0.99, route.success_prob * 0.58 + shape_quality * 0.34 - risk * 0.12))
        return {
            "position_success_prob": round(position_success, 4),
            "shape_quality": round(shape_quality, 4),
            "risk": round(risk, 4),
        }

    @staticmethod
    def _round_point(point: tuple[float, float]) -> list[int]:
        return [int(round(point[0])), int(round(point[1]))]

    @staticmethod
    def _clamp_to_table(
        point: tuple[float, float],
        table_roi: tuple[float, float, float, float],
        margin: float,
    ) -> tuple[float, float]:
        x, y, w, h = table_roi
        return (
            max(x + margin, min(x + w - margin, point[0])),
            max(y + margin, min(y + h - margin, point[1])),
        )
