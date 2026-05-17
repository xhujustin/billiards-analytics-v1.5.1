from __future__ import annotations

import math
from typing import Any, Optional

from .models import PlannerBall, PlannerState, Point, PocketGeometry
from .physics_validator import PhysicsValidator


class StateEvaluator:
    """Heuristic table-state evaluator for early planning decisions."""

    _RULE_WEIGHTS = {
        "practice": {
            "attack": 0.46,
            "position": 0.24,
            "safety": 0.12,
            "risk": 0.18,
        },
        "9ball": {
            "attack": 0.42,
            "position": 0.30,
            "safety": 0.10,
            "risk": 0.18,
        },
    }

    def __init__(self, physics_validator: Optional[PhysicsValidator] = None) -> None:
        self.physics = physics_validator or PhysicsValidator()

    @staticmethod
    def evaluate(
        state: PlannerState | dict[str, Any] | Any = None,
        rule_profile: str = "practice",
        target_ball_number: Optional[int] = None,
    ) -> dict[str, Any]:
        return StateEvaluator()._evaluate_state(
            state=state,
            rule_profile=rule_profile,
            target_ball_number=target_ball_number,
        )

    def _evaluate_state(
        self,
        state: PlannerState | dict[str, Any] | Any,
        rule_profile: str,
        target_ball_number: Optional[int],
    ) -> dict[str, Any]:
        cue_ball = self._get_attr(state, "cue_ball")
        object_balls = list(self._get_attr(state, "object_balls", []) or [])
        table_roi = self._get_attr(state, "table_roi", (0.0, 0.0, 0.0, 0.0))
        ball_radius = float(self._get_attr(state, "table_ball_radius_px", 10.0) or 10.0)
        pockets = self._resolve_pockets(state)

        explanation: list[str] = []
        if cue_ball is None:
            return self._empty_result("missing_cue_ball")
        if not object_balls:
            return self._empty_result("no_object_balls")

        resolved_target = self._resolve_target_ball_number(
            object_balls=object_balls,
            rule_profile=rule_profile,
            target_ball_number=target_ball_number,
        )
        target_candidates = self._target_candidates(object_balls, resolved_target)
        if not target_candidates:
            target_candidates = object_balls
            explanation.append("target_ball_not_found")

        attack_detail = self._evaluate_attack(
            cue_ball=cue_ball,
            object_balls=object_balls,
            target_candidates=target_candidates,
            pockets=pockets,
            ball_radius=ball_radius,
        )
        attack_score = attack_detail["score"]
        best_target = attack_detail.get("target_ball")
        explanation.extend(attack_detail["notes"])

        position_detail = self._evaluate_position(
            cue_ball=cue_ball,
            object_balls=object_balls,
            target_ball=best_target,
            target_ball_number=resolved_target,
            table_roi=table_roi,
            pockets=pockets,
            ball_radius=ball_radius,
        )
        position_score = position_detail["score"]
        explanation.extend(position_detail["notes"])

        risk_detail = self._evaluate_risk(
            cue_ball=cue_ball,
            object_balls=object_balls,
            target_ball=best_target,
            table_roi=table_roi,
            pockets=pockets,
            attack_detail=attack_detail,
            ball_radius=ball_radius,
        )
        risk_score = risk_detail["score"]
        explanation.extend(risk_detail["notes"])

        safety_detail = self._evaluate_safety(
            cue_ball=cue_ball,
            object_balls=object_balls,
            target_ball=best_target,
            attack_score=attack_score,
            risk_score=risk_score,
            table_roi=table_roi,
            ball_radius=ball_radius,
        )
        safety_score = safety_detail["score"]
        explanation.extend(safety_detail["notes"])

        weights = self._RULE_WEIGHTS.get(rule_profile, self._RULE_WEIGHTS["practice"])
        state_score = (
            attack_score * weights["attack"]
            + position_score * weights["position"]
            + safety_score * weights["safety"]
            + (1.0 - risk_score) * weights["risk"]
        )

        return {
            "state_score": round(self._clamp01(state_score), 4),
            "attack_score": round(attack_score, 4),
            "position_score": round(position_score, 4),
            "safety_score": round(safety_score, 4),
            "risk_score": round(risk_score, 4),
            "explanation": explanation,
        }

    def _evaluate_attack(
        self,
        cue_ball: PlannerBall,
        object_balls: list[PlannerBall],
        target_candidates: list[PlannerBall],
        pockets: list[PocketGeometry],
        ball_radius: float,
    ) -> dict[str, Any]:
        best: dict[str, Any] = {
            "score": 0.0,
            "target_ball": None,
            "target_pocket": None,
            "blocker_count": 0,
            "cue_distance": 0.0,
            "object_distance": 0.0,
            "notes": [],
        }

        if not pockets:
            best["notes"].append("no_pocket_geometry")
            return best

        for ball in target_candidates:
            for pocket in pockets:
                object_distance = self.physics.distance(ball.center, pocket.center)
                ghost_point = self._ghost_ball_point(ball.center, pocket.center, ball_radius)
                cue_distance = self.physics.distance(cue_ball.center, ghost_point)
                cut_angle = self._cut_angle(cue_ball.center, ball.center, pocket.center)
                blockers = self._shot_blockers(
                    cue_ball=cue_ball,
                    target_ball=ball,
                    pocket=pocket,
                    object_balls=object_balls,
                    ghost_point=ghost_point,
                    ball_radius=ball_radius,
                )

                cue_clear = blockers["cue_path"] == 0
                object_clear = blockers["object_path"] == 0
                if not cue_clear or not object_clear:
                    clear_factor = 0.46 if cue_clear or object_clear else 0.22
                else:
                    clear_factor = 1.0

                distance_factor = self._distance_score(cue_distance + object_distance, ball_radius * 90.0)
                angle_factor = max(0.12, 1.0 - (cut_angle / 95.0))
                direct_bonus = 0.10 if cue_clear and object_clear else 0.0
                score = self._clamp01(distance_factor * 0.42 + angle_factor * 0.34 + clear_factor * 0.24 + direct_bonus)

                if score > best["score"]:
                    best.update(
                        {
                            "score": score,
                            "target_ball": ball,
                            "target_pocket": pocket,
                            "blocker_count": blockers["cue_path"] + blockers["object_path"],
                            "cue_distance": cue_distance,
                            "object_distance": object_distance,
                            "cut_angle": cut_angle,
                            "notes": [
                                f"best_attack_ball={self._ball_label(ball)}",
                                f"best_attack_pocket={pocket.id}",
                            ],
                        }
                    )

        if best["target_ball"] is None:
            best["notes"].append("no_viable_attack")
        elif best["blocker_count"] > 0:
            best["notes"].append(f"attack_blockers={best['blocker_count']}")
        elif best["score"] >= 0.68:
            best["notes"].append("clear_attack_available")

        return best

    def _evaluate_position(
        self,
        cue_ball: PlannerBall,
        object_balls: list[PlannerBall],
        target_ball: Optional[PlannerBall],
        target_ball_number: Optional[int],
        table_roi: tuple[float, float, float, float],
        pockets: list[PocketGeometry],
        ball_radius: float,
    ) -> dict[str, Any]:
        notes: list[str] = []
        center_score = self._table_center_score(cue_ball.center, table_roi)
        cue_rail_penalty = self._rail_pressure(cue_ball.center, table_roi, ball_radius)
        cue_pocket_penalty = self._nearest_pocket_pressure(cue_ball.center, pockets, ball_radius)

        next_ball = self._next_ball(object_balls, target_ball, target_ball_number)
        if target_ball is None:
            next_distance_score = 0.35
            notes.append("position_no_target_ball")
        elif next_ball is None:
            next_distance_score = 0.72
            notes.append("position_no_next_ball")
        else:
            next_distance = self.physics.distance(target_ball.center, next_ball.center)
            next_distance_score = self._distance_score(next_distance, ball_radius * 48.0)
            notes.append(f"next_ball_distance={round(next_distance, 1)}")

        score = self._clamp01(
            center_score * 0.34
            + next_distance_score * 0.46
            + (1.0 - cue_rail_penalty) * 0.12
            + (1.0 - cue_pocket_penalty) * 0.08
        )
        if cue_rail_penalty > 0.55:
            notes.append("cue_ball_near_rail")
        if cue_pocket_penalty > 0.55:
            notes.append("cue_ball_near_pocket")
        return {"score": score, "notes": notes}

    def _evaluate_risk(
        self,
        cue_ball: PlannerBall,
        object_balls: list[PlannerBall],
        target_ball: Optional[PlannerBall],
        table_roi: tuple[float, float, float, float],
        pockets: list[PocketGeometry],
        attack_detail: dict[str, Any],
        ball_radius: float,
    ) -> dict[str, Any]:
        notes: list[str] = []
        rail_risk = self._rail_pressure(cue_ball.center, table_roi, ball_radius)
        pocket_risk = self._nearest_pocket_pressure(cue_ball.center, pockets, ball_radius)
        obstacle_risk = self._clamp01(float(attack_detail.get("blocker_count", 0)) / 3.0)
        density_risk = self._local_density_risk(cue_ball, object_balls, ball_radius)
        angle = float(attack_detail.get("cut_angle", 0.0) or 0.0)
        angle_risk = self._clamp01(max(0.0, angle - 35.0) / 45.0)

        risk = self._clamp01(
            rail_risk * 0.22
            + pocket_risk * 0.22
            + obstacle_risk * 0.28
            + density_risk * 0.16
            + angle_risk * 0.12
        )
        if obstacle_risk > 0.0:
            notes.append("obstacle_risk_on_attack_line")
        if density_risk > 0.55:
            notes.append("crowded_cue_area")
        if target_ball is None:
            notes.append("risk_no_target_ball")
            risk = max(risk, 0.62)
        return {"score": risk, "notes": notes}

    def _evaluate_safety(
        self,
        cue_ball: PlannerBall,
        object_balls: list[PlannerBall],
        target_ball: Optional[PlannerBall],
        attack_score: float,
        risk_score: float,
        table_roi: tuple[float, float, float, float],
        ball_radius: float,
    ) -> dict[str, Any]:
        notes: list[str] = []
        rail_cover = self._rail_pressure(cue_ball.center, table_roi, ball_radius)
        blocker_cover = 0.0
        if target_ball is not None:
            blockers = 0
            for ball in object_balls:
                if ball is target_ball:
                    continue
                distance = self.physics._point_to_segment_distance(ball.center, cue_ball.center, target_ball.center)
                if distance <= max(ball_radius * 3.0, 28.0):
                    blockers += 1
            blocker_cover = self._clamp01(blockers / 3.0)
            if blockers > 0:
                notes.append(f"safety_cover_balls={blockers}")

        defensive_value = (1.0 - attack_score) * 0.36 + risk_score * 0.22 + rail_cover * 0.18 + blocker_cover * 0.24
        score = self._clamp01(defensive_value)
        if score >= 0.62:
            notes.append("safety_option_present")
        return {"score": score, "notes": notes}

    def _shot_blockers(
        self,
        cue_ball: PlannerBall,
        target_ball: PlannerBall,
        pocket: PocketGeometry,
        object_balls: list[PlannerBall],
        ghost_point: Point,
        ball_radius: float,
    ) -> dict[str, int]:
        cue_path = 0
        object_path = 0
        for ball in object_balls:
            if ball is target_ball:
                continue
            cue_gap = self.physics._point_to_segment_distance(ball.center, cue_ball.center, ghost_point)
            if cue_gap <= max(ball_radius * 2.25, ball.radius + ball_radius + 4.0):
                cue_path += 1
            object_gap = self.physics._point_to_segment_distance(ball.center, target_ball.center, pocket.center)
            if object_gap <= max(ball_radius * 2.0, ball.radius + ball_radius + 3.0):
                object_path += 1
        return {"cue_path": cue_path, "object_path": object_path}

    def _resolve_pockets(self, state: PlannerState | dict[str, Any] | Any) -> list[PocketGeometry]:
        pockets = list(self._get_attr(state, "pockets", []) or [])
        if pockets:
            return pockets
        holes = list(self._get_attr(state, "holes", []) or [])
        return [
            PocketGeometry(
                id=f"hole_{idx}",
                center=(float(point[0]), float(point[1])),
                mouth_segment=((float(point[0]), float(point[1])), (float(point[0]), float(point[1]))),
                capture_radius=18.0,
                approach_normal=(0.0, 0.0),
            )
            for idx, point in enumerate(holes)
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ]

    @staticmethod
    def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _resolve_target_ball_number(
        object_balls: list[PlannerBall],
        rule_profile: str,
        target_ball_number: Optional[int],
    ) -> Optional[int]:
        if target_ball_number is not None:
            return target_ball_number
        numbered = [ball.number for ball in object_balls if ball.number is not None]
        if rule_profile == "9ball" and numbered:
            return min(numbered)
        return None

    @staticmethod
    def _target_candidates(object_balls: list[PlannerBall], target_ball_number: Optional[int]) -> list[PlannerBall]:
        if target_ball_number is None:
            return object_balls
        return [ball for ball in object_balls if ball.number == target_ball_number]

    @staticmethod
    def _next_ball(
        object_balls: list[PlannerBall],
        target_ball: Optional[PlannerBall],
        target_ball_number: Optional[int],
    ) -> Optional[PlannerBall]:
        remaining = [ball for ball in object_balls if ball is not target_ball]
        if not remaining:
            return None
        if target_ball_number is not None:
            numbered_after = [
                ball for ball in remaining
                if ball.number is not None and ball.number > target_ball_number
            ]
            if numbered_after:
                return min(numbered_after, key=lambda ball: ball.number or 99)
        if target_ball is None:
            return None
        return min(remaining, key=lambda ball: math.hypot(ball.center[0] - target_ball.center[0], ball.center[1] - target_ball.center[1]))

    @staticmethod
    def _ghost_ball_point(ball_center: Point, pocket_center: Point, ball_radius: float) -> Point:
        vx = ball_center[0] - pocket_center[0]
        vy = ball_center[1] - pocket_center[1]
        length = math.hypot(vx, vy)
        if length <= 1e-6:
            return ball_center
        offset = ball_radius * 2.0
        return (ball_center[0] + vx / length * offset, ball_center[1] + vy / length * offset)

    @staticmethod
    def _cut_angle(cue_center: Point, ball_center: Point, pocket_center: Point) -> float:
        v1 = (cue_center[0] - ball_center[0], cue_center[1] - ball_center[1])
        v2 = (pocket_center[0] - ball_center[0], pocket_center[1] - ball_center[1])
        len1 = math.hypot(v1[0], v1[1])
        len2 = math.hypot(v2[0], v2[1])
        if len1 <= 1e-6 or len2 <= 1e-6:
            return 90.0
        cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)))
        return abs(180.0 - math.degrees(math.acos(cosine)))

    @staticmethod
    def _distance_score(distance: float, reference: float) -> float:
        reference = max(reference, 1.0)
        return max(0.08, min(1.0, 1.0 - (distance / reference)))

    @staticmethod
    def _table_center_score(point: Point, table_roi: tuple[float, float, float, float]) -> float:
        x, y, w, h = table_roi
        if w <= 0.0 or h <= 0.0:
            return 0.5
        center = (x + w / 2.0, y + h / 2.0)
        max_distance = math.hypot(w / 2.0, h / 2.0)
        distance = math.hypot(point[0] - center[0], point[1] - center[1])
        return max(0.0, min(1.0, 1.0 - distance / max(max_distance, 1.0)))

    @staticmethod
    def _rail_pressure(point: Point, table_roi: tuple[float, float, float, float], ball_radius: float) -> float:
        x, y, w, h = table_roi
        if w <= 0.0 or h <= 0.0:
            return 0.0
        distances = [
            abs(point[0] - x),
            abs(point[0] - (x + w)),
            abs(point[1] - y),
            abs(point[1] - (y + h)),
        ]
        nearest = min(distances)
        threshold = max(ball_radius * 3.5, 36.0)
        return max(0.0, min(1.0, 1.0 - nearest / threshold))

    @staticmethod
    def _nearest_pocket_pressure(point: Point, pockets: list[PocketGeometry], ball_radius: float) -> float:
        if not pockets:
            return 0.0
        nearest = min(math.hypot(point[0] - pocket.center[0], point[1] - pocket.center[1]) for pocket in pockets)
        threshold = max(ball_radius * 5.0, 55.0)
        return max(0.0, min(1.0, 1.0 - nearest / threshold))

    def _local_density_risk(self, cue_ball: PlannerBall, object_balls: list[PlannerBall], ball_radius: float) -> float:
        radius = max(ball_radius * 7.0, 80.0)
        nearby = 0
        for ball in object_balls:
            if self.physics.distance(cue_ball.center, ball.center) <= radius:
                nearby += 1
        return self._clamp01(nearby / 5.0)

    @staticmethod
    def _ball_label(ball: PlannerBall) -> str:
        return str(ball.number) if ball.number is not None else "unknown"

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _empty_result(reason: str) -> dict[str, Any]:
        return {
            "state_score": 0.0,
            "attack_score": 0.0,
            "position_score": 0.0,
            "safety_score": 0.0,
            "risk_score": 1.0,
            "explanation": [reason],
        }
