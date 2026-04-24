from __future__ import annotations

import itertools
import math
from typing import Optional

from .models import PlannerBall, PlannerState, PocketGeometry, RouteCandidate
from .physics_validator import PhysicsValidator
from .route_scorer import RouteScorer
from .stroke_recommender import StrokeRecommender


def _to_int_point(p: tuple[float, float]) -> list[int]:
    return [int(round(p[0])), int(round(p[1]))]


def _segment(kind: str, points: list[tuple[float, float]], color: str) -> dict:
    return {
        "type": kind,
        "points": [_to_int_point(p) for p in points],
        "color": color,
    }


def _landing_zone(point: tuple[float, float], radius: int = 34) -> dict:
    return {
        "center": _to_int_point(point),
        "radius": radius,
        "label": "預計母球落點",
    }


def _near_any_hole(
    point: tuple[float, float],
    holes: list[tuple[float, float]],
    min_clearance: float = 90.0,
) -> bool:
    return any(math.hypot(point[0] - hole[0], point[1] - hole[1]) < min_clearance for hole in holes)


def _rail_sequences(max_bounces: int) -> list[tuple[str, ...]]:
    rails = ("top", "bottom", "left", "right")
    sequences: list[tuple[str, ...]] = []
    for rail_count in range(1, max(1, max_bounces) + 1):
        for seq in itertools.product(rails, repeat=rail_count):
            if any(seq[i] == seq[i - 1] for i in range(1, len(seq))):
                continue
            sequences.append(seq)
    return sequences


def _effective_rail_segments(
    left: float,
    right: float,
    top: float,
    bottom: float,
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    return {
        "top": ((left, top), (right, top)),
        "bottom": ((left, bottom), (right, bottom)),
        "left": ((left, top), (left, bottom)),
        "right": ((right, top), (right, bottom)),
    }


class CandidateGenerator:
    def __init__(self, validator: PhysicsValidator):
        self.validator = validator
        self.stroke_recommender = StrokeRecommender()

    def generate(
        self,
        state: PlannerState,
        max_bounces: int = 2,
        combo_depth: int = 2,
    ) -> list[RouteCandidate]:
        candidates: list[RouteCandidate] = []

        for obj in state.object_balls:
            candidates.extend(self._gen_direct_and_cut(state, obj))
            if max_bounces > 0:
                candidates.extend(self._gen_bank(state, obj))
                candidates.extend(self._gen_kick(state, obj, max_bounces=max_bounces))
                candidates.extend(self._gen_kick_escape(state, obj, max_bounces=max_bounces))

        if combo_depth >= 2:
            candidates.extend(self._gen_combo(state))

        return candidates

    def _gen_direct_and_cut(self, state: PlannerState, obj: PlannerBall) -> list[RouteCandidate]:
        results: list[RouteCandidate] = []
        cue_center = state.cue_ball.center
        obj_center = obj.center

        for pocket in state.pockets:
            hole = pocket.center
            # 子球目標方向
            dir_x = hole[0] - obj_center[0]
            dir_y = hole[1] - obj_center[1]
            dist_obj_hole = math.hypot(dir_x, dir_y)
            if dist_obj_hole < 1e-6:
                continue
            n_x = dir_x / dist_obj_hole
            n_y = dir_y / dist_obj_hole

            ghost_dist = obj.radius + state.cue_ball.radius
            ghost = (obj_center[0] - n_x * ghost_dist, obj_center[1] - n_y * ghost_dist)

            if not self.validator.ball_center_in_table(ghost, state.table_roi, state.cue_ball.radius):
                continue

            v_cue_ghost = (ghost[0] - cue_center[0], ghost[1] - cue_center[1])
            v_obj_hole = (hole[0] - obj_center[0], hole[1] - obj_center[1])
            cue_dist = math.hypot(v_cue_ghost[0], v_cue_ghost[1])
            if cue_dist < 1e-6:
                continue
            dot = v_cue_ghost[0] * v_obj_hole[0] + v_cue_ghost[1] * v_obj_hole[1]
            cos_ang = max(-1.0, min(1.0, dot / (cue_dist * max(1e-6, dist_obj_hole))))
            cut_angle = math.degrees(math.acos(cos_ang))
            if cut_angle > 84:
                continue

            ignore = {0}
            if obj.number is not None:
                ignore.add(obj.number)
            if not self.validator.is_path_clear(cue_center, ghost, state.object_balls, ignore, state.cue_ball.radius):
                continue
            if not self.validator.can_pocket_ball(obj_center, pocket, obj.radius):
                continue
            if not self.validator.is_path_clear(obj_center, hole, state.object_balls, ignore, obj.radius):
                continue

            route_type = "straight" if cut_angle <= 12 else "cut"
            total_distance = cue_dist + dist_obj_hole
            base_success = RouteScorer.estimate_base_success(cut_angle, total_distance, bounces=0, combo_depth=1)
            stroke = self.stroke_recommender.recommend(route_type, cut_angle, total_distance)
            route_id = f"{route_type}-{obj.number}-{int(hole[0])}-{int(hole[1])}"
            cue_leave = self._estimate_cue_leave(cue_center, ghost, (n_x, n_y), state.table_roi)

            results.append(
                RouteCandidate(
                    id=route_id,
                    route_type=route_type,
                    target_ball_number=obj.number,
                    first_contact_ball_number=obj.number,
                    score=base_success,
                    difficulty=0,
                    difficulty_level="medium",
                    success_prob=base_success,
                    cut_angle=cut_angle,
                    total_distance=total_distance,
                    path_points=[
                        _to_int_point(cue_center),
                        _to_int_point(ghost),
                        _to_int_point(obj_center),
                        _to_int_point(hole),
                    ],
                    route_segments=[
                        _segment("cue_to_contact", [cue_center, ghost], "white"),
                        _segment("object_to_pocket", [obj_center, hole], "green"),
                        _segment("cue_after_contact", [ghost, cue_leave], "cyan"),
                    ],
                    cue_landing_point=_to_int_point(cue_leave),
                    cue_landing_zone=_landing_zone(cue_leave),
                    nodes=["cue_contact", "object_contact", "pocket"],
                    stroke_hint=stroke,
                    metadata={
                        "ghost_ball": _to_int_point(ghost),
                        "route_class": "potting_route",
                        "strategy_label": "直接進攻",
                        "potted_ball_number": obj.number,
                    },
                )
            )
        return results

    def _gen_bank(self, state: PlannerState, obj: PlannerBall) -> list[RouteCandidate]:
        results: list[RouteCandidate] = []
        obj_center = obj.center

        rails = ["top", "bottom", "left", "right"]
        for pocket in state.pockets:
            hole = pocket.center
            for rail in rails:
                rail_segment = state.rail_segments.get(rail)
                if rail_segment is None:
                    continue
                bank_point = self._compute_bank_point(obj_center, hole, rail, state)
                if bank_point is None:
                    continue
                if not self.validator.point_on_rail_segment(bank_point, rail_segment):
                    continue
                if not self.validator.ball_center_in_table(bank_point, state.table_roi, obj.radius, cushion_margin=8.0):
                    continue
                if _near_any_hole(bank_point, state.holes, min_clearance=max(90.0, obj.radius * 6.0)):
                    continue
                if self.validator.distance(bank_point, hole) < max(70.0, obj.radius * 5.0):
                    continue
                if self.validator.distance(bank_point, obj_center) < max(50.0, obj.radius * 4.0):
                    continue

                ignore = {0}
                if obj.number is not None:
                    ignore.add(obj.number)
                if not self.validator.is_path_clear(obj_center, bank_point, state.object_balls, ignore, obj.radius):
                    continue
                if not self.validator.can_pocket_ball(bank_point, pocket, obj.radius):
                    continue
                if not self.validator.is_path_clear(bank_point, hole, state.object_balls, ignore, obj.radius):
                    continue

                cue_center = state.cue_ball.center
                v_obj_bank = (bank_point[0] - obj_center[0], bank_point[1] - obj_center[1])
                obj_bank_len = math.hypot(*v_obj_bank)
                if obj_bank_len < 1e-6:
                    continue
                n_x = v_obj_bank[0] / obj_bank_len
                n_y = v_obj_bank[1] / obj_bank_len
                ghost_dist = obj.radius + state.cue_ball.radius
                ghost = (obj_center[0] - n_x * ghost_dist, obj_center[1] - n_y * ghost_dist)

                if not self.validator.ball_center_in_table(ghost, state.table_roi, state.cue_ball.radius):
                    continue
                if not self.validator.is_path_clear(cue_center, ghost, state.object_balls, ignore, state.cue_ball.radius):
                    continue

                v_cue_ghost = (ghost[0] - cue_center[0], ghost[1] - cue_center[1])
                dot = v_cue_ghost[0] * v_obj_bank[0] + v_cue_ghost[1] * v_obj_bank[1]
                den = max(1e-6, math.hypot(*v_cue_ghost) * math.hypot(*v_obj_bank))
                cut_angle = math.degrees(math.acos(max(-1.0, min(1.0, dot / den))))
                if cut_angle > 84:
                    continue
                total_distance = (
                    self.validator.distance(cue_center, ghost)
                    + self.validator.distance(obj_center, bank_point)
                    + self.validator.distance(bank_point, hole)
                )
                base_success = RouteScorer.estimate_base_success(cut_angle, total_distance, bounces=1, combo_depth=1)
                stroke = self.stroke_recommender.recommend("bank", cut_angle, total_distance)
                route_id = f"bank-{obj.number}-{rail}-{int(hole[0])}-{int(hole[1])}"
                cue_leave = self._estimate_cue_leave(cue_center, ghost, v_obj_bank, state.table_roi)
                results.append(
                    RouteCandidate(
                        id=route_id,
                        route_type="bank",
                        target_ball_number=obj.number,
                        first_contact_ball_number=obj.number,
                        score=base_success,
                        difficulty=0,
                        difficulty_level="hard",
                        success_prob=base_success,
                        cut_angle=cut_angle,
                        total_distance=total_distance,
                        path_points=[
                            _to_int_point(cue_center),
                            _to_int_point(ghost),
                            _to_int_point(obj_center),
                            _to_int_point(bank_point),
                            _to_int_point(hole),
                        ],
                        route_segments=[
                            _segment("cue_to_contact", [cue_center, ghost], "white"),
                            _segment("object_to_rail", [obj_center, bank_point], "green"),
                            _segment("object_to_pocket", [bank_point, hole], "green"),
                            _segment("cue_after_contact", [ghost, cue_leave], "cyan"),
                        ],
                        cue_landing_point=_to_int_point(cue_leave),
                        cue_landing_zone=_landing_zone(cue_leave),
                        nodes=["cue_contact", "object_contact", "rail", "pocket"],
                        stroke_hint=stroke,
                        metadata={
                            "rail": rail,
                            "ghost_ball": _to_int_point(ghost),
                            "route_class": "potting_route",
                            "strategy_label": "翻袋進攻",
                            "potted_ball_number": obj.number,
                        },
                    )
                )
        return results

    def _compute_bank_point(
        self,
        obj_center: tuple[float, float],
        hole: tuple[float, float],
        rail: str,
        state: PlannerState,
    ) -> Optional[tuple[float, float]]:
        tx, ty, tw, th = state.table_roi
        ball_radius = state.table_ball_radius_px
        left = tx + 24.0 + ball_radius
        right = tx + tw - 24.0 - ball_radius
        top = ty + 24.0 + ball_radius
        bottom = ty + th - 24.0 - ball_radius
        ox, oy = obj_center
        hx, hy = hole

        if rail == "top":
            mhx, mhy = hx, 2 * top - hy
            y_bank = top
            if abs(mhy - oy) < 1e-6:
                return None
            t = (y_bank - oy) / (mhy - oy)
            x_bank = ox + t * (mhx - ox)
            return (x_bank, y_bank)
        if rail == "bottom":
            mhx, mhy = hx, 2 * bottom - hy
            y_bank = bottom
            if abs(mhy - oy) < 1e-6:
                return None
            t = (y_bank - oy) / (mhy - oy)
            x_bank = ox + t * (mhx - ox)
            return (x_bank, y_bank)
        if rail == "left":
            mhx, mhy = 2 * left - hx, hy
            x_bank = left
            if abs(mhx - ox) < 1e-6:
                return None
            t = (x_bank - ox) / (mhx - ox)
            y_bank = oy + t * (mhy - oy)
            return (x_bank, y_bank)
        mhx, mhy = 2 * right - hx, hy
        x_bank = right
        if abs(mhx - ox) < 1e-6:
            return None
        t = (x_bank - ox) / (mhx - ox)
        y_bank = oy + t * (mhy - oy)
        return (x_bank, y_bank)

    def _mirror_point(
        self,
        point: tuple[float, float],
        rail: str,
        left: float,
        right: float,
        top: float,
        bottom: float,
    ) -> tuple[float, float]:
        x, y = point
        if rail == "top":
            return (x, 2 * top - y)
        if rail == "bottom":
            return (x, 2 * bottom - y)
        if rail == "left":
            return (2 * left - x, y)
        return (2 * right - x, y)

    def _intersect_with_rail(
        self,
        start: tuple[float, float],
        target: tuple[float, float],
        rail: str,
        left: float,
        right: float,
        top: float,
        bottom: float,
    ) -> Optional[tuple[float, float]]:
        sx, sy = start
        tx, ty = target

        if rail in {"top", "bottom"}:
            y_rail = top if rail == "top" else bottom
            if abs(ty - sy) < 1e-6:
                return None
            t = (y_rail - sy) / (ty - sy)
            if not 0.0 < t < 1.0:
                return None
            x = sx + t * (tx - sx)
            if not left <= x <= right:
                return None
            return (x, y_rail)

        x_rail = left if rail == "left" else right
        if abs(tx - sx) < 1e-6:
            return None
        t = (x_rail - sx) / (tx - sx)
        if not 0.0 < t < 1.0:
            return None
        y = sy + t * (ty - sy)
        if not top <= y <= bottom:
            return None
        return (x_rail, y)

    def _compute_multi_rail_points(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        rails: tuple[str, ...],
        left: float,
        right: float,
        top: float,
        bottom: float,
    ) -> Optional[list[tuple[float, float]]]:
        bounce_points: list[tuple[float, float]] = []
        current_start = start

        for idx, rail in enumerate(rails):
            mirrored_target = end
            for rem in reversed(rails[idx:]):
                mirrored_target = self._mirror_point(mirrored_target, rem, left, right, top, bottom)
            bounce = self._intersect_with_rail(current_start, mirrored_target, rail, left, right, top, bottom)
            if bounce is None:
                return None
            bounce_points.append(bounce)
            current_start = bounce

        return bounce_points

    def _gen_combo(self, state: PlannerState) -> list[RouteCandidate]:
        results: list[RouteCandidate] = []
        cue_center = state.cue_ball.center

        for first in state.object_balls:
            for second in state.object_balls:
                if second is first:
                    continue
                first_c = first.center
                second_c = second.center
                if self.validator.distance(first_c, second_c) < (first.radius + second.radius) * 1.8:
                    continue

                ignore = {0}
                if first.number is not None:
                    ignore.add(first.number)
                if second.number is not None:
                    ignore.add(second.number)

                for pocket in state.pockets:
                    hole = pocket.center
                    if not self.validator.is_path_clear(second_c, hole, state.object_balls, ignore, second.radius):
                        continue
                    if not self.validator.can_pocket_ball(second_c, pocket, second.radius):
                        continue

                    second_to_hole = (hole[0] - second_c[0], hole[1] - second_c[1])
                    second_to_hole_len = math.hypot(*second_to_hole)
                    if second_to_hole_len < 1e-6:
                        continue
                    first_to_second = (second_c[0] - first_c[0], second_c[1] - first_c[1])
                    first_to_second_len = math.hypot(*first_to_second)
                    if first_to_second_len < 1e-6:
                        continue
                    transfer_den = max(1e-6, first_to_second_len * second_to_hole_len)
                    transfer_dot = first_to_second[0] * second_to_hole[0] + first_to_second[1] * second_to_hole[1]
                    combo_transfer_angle = math.degrees(math.acos(max(-1.0, min(1.0, transfer_dot / transfer_den))))
                    if combo_transfer_angle > 58:
                        continue

                    second_cushion_clearance = self._edge_clearance(second_c, state.table_roi) - second.radius
                    if second_cushion_clearance < max(6.0, second.radius * 0.35) and combo_transfer_angle > 28:
                        continue

                    second_dir = (
                        second_to_hole[0] / second_to_hole_len,
                        second_to_hole[1] / second_to_hole_len,
                    )
                    second_ghost_dist = first.radius + second.radius
                    second_ghost = (
                        second_c[0] - second_dir[0] * second_ghost_dist,
                        second_c[1] - second_dir[1] * second_ghost_dist,
                    )

                    if not self.validator.ball_center_in_table(second_ghost, state.table_roi, first.radius):
                        continue
                    if not self.validator.is_path_clear(first_c, second_ghost, state.object_balls, ignore, first.radius):
                        continue

                    first_to_second_ghost = (second_ghost[0] - first_c[0], second_ghost[1] - first_c[1])
                    first_to_second_len = math.hypot(*first_to_second_ghost)
                    if first_to_second_len < 1e-6:
                        continue
                    n_x = first_to_second_ghost[0] / first_to_second_len
                    n_y = first_to_second_ghost[1] / first_to_second_len
                    ghost_dist = first.radius + state.cue_ball.radius
                    ghost = (first_c[0] - n_x * ghost_dist, first_c[1] - n_y * ghost_dist)

                    if not self.validator.ball_center_in_table(ghost, state.table_roi, state.cue_ball.radius):
                        continue
                    if not self.validator.is_path_clear(cue_center, ghost, state.object_balls, ignore, state.cue_ball.radius):
                        continue

                    v1 = (ghost[0] - cue_center[0], ghost[1] - cue_center[1])
                    dot = v1[0] * first_to_second_ghost[0] + v1[1] * first_to_second_ghost[1]
                    den = max(1e-6, math.hypot(*v1) * math.hypot(*first_to_second_ghost))
                    cut_angle = math.degrees(math.acos(max(-1.0, min(1.0, dot / den))))
                    if cut_angle > 78:
                        continue
                    total_distance = (
                        self.validator.distance(cue_center, ghost)
                        + self.validator.distance(first_c, second_ghost)
                        + self.validator.distance(second_c, hole)
                    )
                    base_success = RouteScorer.estimate_base_success(cut_angle, total_distance, bounces=0, combo_depth=2)
                    stroke = self.stroke_recommender.recommend("combo", cut_angle, total_distance)
                    route_id = f"combo-{first.number}-{second.number}-{int(hole[0])}-{int(hole[1])}"
                    cue_leave = self._estimate_cue_leave(cue_center, ghost, first_to_second_ghost, state.table_roi)
                    results.append(
                        RouteCandidate(
                            id=route_id,
                            route_type="combo",
                            target_ball_number=first.number,
                            first_contact_ball_number=first.number,
                            score=base_success,
                            difficulty=0,
                            difficulty_level="hard",
                            success_prob=base_success,
                            cut_angle=cut_angle,
                            total_distance=total_distance,
                            path_points=[
                                _to_int_point(cue_center),
                                _to_int_point(ghost),
                                _to_int_point(first_c),
                                _to_int_point(second_ghost),
                                _to_int_point(second_c),
                                _to_int_point(hole),
                            ],
                            route_segments=[
                                _segment("cue_to_contact", [cue_center, ghost], "white"),
                                _segment("combo_transfer", [first_c, second_ghost], "yellow"),
                                _segment("object_to_pocket", [second_c, hole], "green"),
                                _segment("cue_after_contact", [ghost, cue_leave], "cyan"),
                            ],
                            cue_landing_point=_to_int_point(cue_leave),
                            cue_landing_zone=_landing_zone(cue_leave),
                            nodes=["cue_contact", "object_contact", "object_contact", "pocket"],
                            stroke_hint=stroke,
                            metadata={
                                "combo_depth": 2,
                                "ghost_ball": _to_int_point(ghost),
                                "combo_second_ball_number": second.number,
                                "combo_second_ghost": _to_int_point(second_ghost),
                                "potted_ball_number": second.number,
                                "route_class": "potting_route",
                                "strategy_label": "組合進攻",
                                "combo_transfer_angle": round(combo_transfer_angle, 2),
                                "second_cushion_clearance": round(second_cushion_clearance, 2),
                            },
                        )
                    )
        return results

    def _gen_kick(self, state: PlannerState, obj: PlannerBall, max_bounces: int = 1) -> list[RouteCandidate]:
        results: list[RouteCandidate] = []
        tx, ty, tw, th = state.table_roi
        left = tx + 24.0 + state.cue_ball.radius
        right = tx + tw - 24.0 - state.cue_ball.radius
        top = ty + 24.0 + state.cue_ball.radius
        bottom = ty + th - 24.0 - state.cue_ball.radius
        effective_rails = _effective_rail_segments(left, right, top, bottom)
        cue_center = state.cue_ball.center
        obj_center = obj.center

        for pocket in state.pockets:
            hole = pocket.center
            dir_x = hole[0] - obj_center[0]
            dir_y = hole[1] - obj_center[1]
            dist_obj_hole = math.hypot(dir_x, dir_y)
            if dist_obj_hole < 1e-6:
                continue
            n_x = dir_x / dist_obj_hole
            n_y = dir_y / dist_obj_hole

            ghost_dist = obj.radius + state.cue_ball.radius
            ghost = (obj_center[0] - n_x * ghost_dist, obj_center[1] - n_y * ghost_dist)
            if not self.validator.ball_center_in_table(ghost, state.table_roi, state.cue_ball.radius):
                continue

            ignore = {0}
            if obj.number is not None:
                ignore.add(obj.number)

            # 直線已可打時，不需要再保留 kick 當重複候選。
            if self.validator.is_path_clear(cue_center, ghost, state.object_balls, ignore, state.cue_ball.radius):
                continue
            if not self.validator.can_pocket_ball(obj_center, pocket, obj.radius):
                continue
            if not self.validator.is_path_clear(obj_center, hole, state.object_balls, ignore, obj.radius):
                continue

            for rail_sequence in _rail_sequences(max_bounces):
                bounce_points = self._compute_multi_rail_points(
                    cue_center,
                    ghost,
                    rail_sequence,
                    left,
                    right,
                    top,
                    bottom,
                )
                if bounce_points is None:
                    continue
                if any(
                    not self.validator.point_on_rail_segment(
                        point,
                        effective_rails.get(rail_sequence[idx], ((0.0, 0.0), (0.0, 0.0))),
                    )
                    for idx, point in enumerate(bounce_points)
                ):
                    continue
                if any(
                    _near_any_hole(point, state.holes, min_clearance=max(70.0, state.cue_ball.radius * 4.5))
                    for point in bounce_points
                ):
                    continue

                kick_points = [cue_center, *bounce_points, ghost]
                leg_invalid = False
                for idx in range(len(kick_points) - 1):
                    p1 = kick_points[idx]
                    p2 = kick_points[idx + 1]
                    if self.validator.distance(p1, p2) < max(70.0, state.cue_ball.radius * 5.0):
                        leg_invalid = True
                        break
                    if not self.validator.is_path_clear(p1, p2, state.object_balls, ignore, state.cue_ball.radius):
                        leg_invalid = True
                        break
                if leg_invalid:
                    continue

                final_leg = (ghost[0] - bounce_points[-1][0], ghost[1] - bounce_points[-1][1])
                incoming = (
                    bounce_points[-1][0] - kick_points[-3][0],
                    bounce_points[-1][1] - kick_points[-3][1],
                ) if len(kick_points) >= 3 else (bounce_points[-1][0] - cue_center[0], bounce_points[-1][1] - cue_center[1])
                if math.hypot(*incoming) < 1e-6 or math.hypot(*final_leg) < 1e-6:
                    continue

                den = max(1e-6, math.hypot(*incoming) * math.hypot(*final_leg))
                dot = incoming[0] * final_leg[0] + incoming[1] * final_leg[1]
                cue_rail_angle = math.degrees(math.acos(max(-1.0, min(1.0, dot / den))))
                if cue_rail_angle > 110:
                    continue

                object_dir = (hole[0] - obj_center[0], hole[1] - obj_center[1])
                v_cue_ghost = (ghost[0] - bounce_points[-1][0], ghost[1] - bounce_points[-1][1])
                contact_den = max(1e-6, math.hypot(*v_cue_ghost) * math.hypot(*object_dir))
                contact_dot = v_cue_ghost[0] * object_dir[0] + v_cue_ghost[1] * object_dir[1]
                cut_angle = math.degrees(math.acos(max(-1.0, min(1.0, contact_dot / contact_den))))
                if cut_angle > 84:
                    continue

                total_distance = sum(
                    self.validator.distance(kick_points[idx], kick_points[idx + 1])
                    for idx in range(len(kick_points) - 1)
                ) + self.validator.distance(obj_center, hole)
                bounces = len(bounce_points)
                rail_label = "-".join(rail_sequence)
                base_success = RouteScorer.estimate_base_success(cut_angle, total_distance, bounces=bounces, combo_depth=1)
                stroke = self.stroke_recommender.recommend("kick", cut_angle, total_distance)
                route_id = f"kick-{obj.number}-{rail_label}-{int(hole[0])}-{int(hole[1])}"
                cue_leave = self._estimate_cue_leave(bounce_points[-1], ghost, object_dir, state.table_roi)

                results.append(
                    RouteCandidate(
                        id=route_id,
                        route_type="kick",
                        target_ball_number=obj.number,
                        first_contact_ball_number=obj.number,
                        score=base_success,
                        difficulty=0,
                        difficulty_level="hard",
                        success_prob=base_success,
                        cut_angle=cut_angle,
                        total_distance=total_distance,
                        path_points=[
                            *[_to_int_point(point) for point in kick_points],
                            _to_int_point(obj_center),
                            _to_int_point(hole),
                        ],
                        route_segments=[
                            _segment("cue_to_contact", kick_points, "white"),
                            _segment("object_to_pocket", [obj_center, hole], "green"),
                            _segment("cue_after_contact", [ghost, cue_leave], "cyan"),
                        ],
                        cue_landing_point=_to_int_point(cue_leave),
                        cue_landing_zone=_landing_zone(cue_leave),
                        nodes=["cue_contact", *["rail" for _ in bounce_points], "object_contact", "pocket"],
                        stroke_hint=stroke,
                        metadata={
                            "ghost_ball": _to_int_point(ghost),
                            "rail": rail_label,
                            "escape": True,
                            "route_class": "potting_route",
                            "strategy_label": "顆星進攻",
                            "potted_ball_number": obj.number,
                            "kick_bounces": bounces,
                        },
                    )
                )
        return results

    def _gen_kick_escape(self, state: PlannerState, obj: PlannerBall, max_bounces: int = 1) -> list[RouteCandidate]:
        results: list[RouteCandidate] = []
        tx, ty, tw, th = state.table_roi
        left = tx + 24.0 + state.cue_ball.radius
        right = tx + tw - 24.0 - state.cue_ball.radius
        top = ty + 24.0 + state.cue_ball.radius
        bottom = ty + th - 24.0 - state.cue_ball.radius
        effective_rails = _effective_rail_segments(left, right, top, bottom)
        cue_center = state.cue_ball.center
        obj_center = obj.center

        ignore = {0}
        if obj.number is not None:
            ignore.add(obj.number)

        if self.validator.is_path_clear(cue_center, obj_center, state.object_balls, ignore, state.cue_ball.radius):
            return results

        contact_radius = obj.radius + state.cue_ball.radius
        sample_dirs = [
            (math.cos(math.radians(deg)), math.sin(math.radians(deg)))
            for deg in range(0, 360, 15)
        ]

        for d_x, d_y in sample_dirs:
            contact = (
                obj_center[0] - d_x * contact_radius,
                obj_center[1] - d_y * contact_radius,
            )
            if not self.validator.ball_center_in_table(contact, state.table_roi, state.cue_ball.radius):
                continue

            for rail_sequence in _rail_sequences(max_bounces):
                bounce_points = self._compute_multi_rail_points(
                    cue_center,
                    contact,
                    rail_sequence,
                    left,
                    right,
                    top,
                    bottom,
                )
                if bounce_points is None:
                    continue
                if any(
                    not self.validator.point_on_rail_segment(
                        point,
                        effective_rails.get(rail_sequence[idx], ((0.0, 0.0), (0.0, 0.0))),
                    )
                    for idx, point in enumerate(bounce_points)
                ):
                    continue
                if any(
                    _near_any_hole(point, state.holes, min_clearance=max(95.0, state.cue_ball.radius * 6.0))
                    for point in bounce_points
                ):
                    continue

                kick_points = [cue_center, *bounce_points, contact]
                leg_invalid = False
                for idx in range(len(kick_points) - 1):
                    p1 = kick_points[idx]
                    p2 = kick_points[idx + 1]
                    if self.validator.distance(p1, p2) < max(70.0, state.cue_ball.radius * 5.0):
                        leg_invalid = True
                        break
                    # 解球只要求第一碰合法目標球；最後一腿允許進入目標球接觸區。
                    leg_ignore = set(ignore)
                    if idx == len(kick_points) - 2 and obj.number is not None:
                        leg_ignore.add(obj.number)
                    if not self.validator.is_path_clear(p1, p2, state.object_balls, leg_ignore, state.cue_ball.radius * 0.6):
                        leg_invalid = True
                        break
                if leg_invalid:
                    continue

                final_leg = (contact[0] - kick_points[-2][0], contact[1] - kick_points[-2][1])
                final_len = max(1e-6, math.hypot(*final_leg))
                final_unit = (final_leg[0] / final_len, final_leg[1] / final_len)
                impact_alignment = final_unit[0] * d_x + final_unit[1] * d_y
                if impact_alignment < 0.22:
                    continue

                total_distance = sum(
                    self.validator.distance(kick_points[idx], kick_points[idx + 1])
                    for idx in range(len(kick_points) - 1)
                )
                bounces = len(bounce_points)
                base_success = min(
                    0.42,
                    RouteScorer.estimate_base_success(35.0, total_distance, bounces=bounces, combo_depth=1) * 0.58,
                )
                rail_label = "-".join(rail_sequence)
                cue_leave, cue_leave_model = self._estimate_cue_leave(
                    bounce_points[-1],
                    contact,
                    (d_x, d_y),
                    state.table_roi,
                    return_model=True,
                )
                object_leave = self._estimate_object_leave(contact, obj_center, state.table_roi)
                safety_score = self._estimate_safety_score(cue_leave, object_leave, state)
                if cue_leave_model == "stop_zone":
                    safety_score *= 0.72
                route_type = "safe_escape" if safety_score >= 0.62 else "contact_only"
                base_success = min(0.42, base_success * (0.88 + safety_score * 0.22))
                stroke = self.stroke_recommender.recommend(route_type, 35.0, total_distance)
                route_id = f"{route_type}-{obj.number}-{rail_label}-{int(contact[0])}-{int(contact[1])}"

                results.append(
                    RouteCandidate(
                        id=route_id,
                        route_type=route_type,
                        target_ball_number=obj.number,
                        first_contact_ball_number=obj.number,
                        score=base_success,
                        difficulty=0,
                        difficulty_level="hard",
                        success_prob=base_success,
                        cut_angle=35.0,
                        total_distance=total_distance,
                        path_points=[
                            *[_to_int_point(point) for point in kick_points],
                            _to_int_point(obj_center),
                            _to_int_point(object_leave),
                        ],
                        route_segments=[
                            _segment("cue_to_contact", kick_points, "white"),
                            _segment("object_after_contact", [obj_center, object_leave], "green"),
                            _segment("cue_after_contact", [contact, cue_leave], "cyan"),
                        ],
                        cue_landing_point=_to_int_point(cue_leave),
                        cue_landing_zone=_landing_zone(cue_leave),
                        nodes=["cue_contact", *["rail" for _ in bounce_points], "object_contact"],
                        stroke_hint=stroke,
                        metadata={
                            "ghost_ball": _to_int_point(contact),
                            "rail": rail_label,
                            "escape": True,
                            "base_route_type": "kick_escape",
                            "route_class": route_type,
                            "strategy_label": "安全解球" if route_type == "safe_escape" else "合法碰球",
                            "contact_only": route_type == "contact_only",
                            "cue_leave_model": cue_leave_model,
                            "impact_alignment": round(impact_alignment, 3),
                            "safety_score": round(safety_score, 3),
                            "kick_bounces": bounces,
                        },
                    )
                )

        return results

    def _estimate_object_leave(
        self,
        contact_point: tuple[float, float],
        obj_center: tuple[float, float],
        table_roi: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        direction = (obj_center[0] - contact_point[0], obj_center[1] - contact_point[1])
        length = max(1e-6, math.hypot(*direction))
        unit = (direction[0] / length, direction[1] / length)
        end = (obj_center[0] + unit[0] * 145.0, obj_center[1] + unit[1] * 145.0)
        return self._clamp_to_table(end, table_roi)

    def _estimate_safety_score(
        self,
        cue_leave: tuple[float, float],
        object_leave: tuple[float, float],
        state: PlannerState,
    ) -> float:
        object_to_pocket = min((self.validator.distance(object_leave, hole) for hole in state.holes), default=0.0)
        cue_to_object = self.validator.distance(cue_leave, object_leave)
        rail_clearance = self._edge_clearance(object_leave, state.table_roi)
        score = (
            min(1.0, cue_to_object / 420.0) * 0.48
            + min(1.0, object_to_pocket / 520.0) * 0.34
            + min(1.0, max(0.0, rail_clearance) / 150.0) * 0.18
        )
        return max(0.0, min(1.0, score))

    def _estimate_cue_leave(
        self,
        cue_start: tuple[float, float],
        contact_point: tuple[float, float],
        object_dir: tuple[float, float],
        table_roi: tuple[float, float, float, float],
        return_model: bool = False,
    ) -> tuple[float, float] | tuple[tuple[float, float], str]:
        incoming = (contact_point[0] - cue_start[0], contact_point[1] - cue_start[1])
        in_len = max(1e-6, math.hypot(*incoming))
        in_unit = (incoming[0] / in_len, incoming[1] / in_len)
        obj_len = max(1e-6, math.hypot(*object_dir))
        obj_unit = (object_dir[0] / obj_len, object_dir[1] / obj_len)
        dot = in_unit[0] * obj_unit[0] + in_unit[1] * obj_unit[1]
        tangent = (in_unit[0] - dot * obj_unit[0], in_unit[1] - dot * obj_unit[1])
        tan_len = math.hypot(*tangent)
        if tan_len < 0.18:
            # 近滿球時母球沒有可信切線行進段；落點只標在接觸點外側短停球區。
            end = (
                contact_point[0] - obj_unit[0] * 48.0,
                contact_point[1] - obj_unit[1] * 48.0,
            )
            result = self._clamp_to_table(end, table_roi)
            return (result, "stop_zone") if return_model else result

        tangent = (tangent[0] / tan_len, tangent[1] / tan_len)
        # 避免簡化模型把母球落點畫到穿過目標球的方向。
        if tangent[0] * obj_unit[0] + tangent[1] * obj_unit[1] > 0.22:
            end = (
                contact_point[0] - obj_unit[0] * 48.0,
                contact_point[1] - obj_unit[1] * 48.0,
            )
            result = self._clamp_to_table(end, table_roi)
            return (result, "stop_zone") if return_model else result

        travel = 95.0 + min(90.0, tan_len * 130.0)
        end = (contact_point[0] + tangent[0] * travel, contact_point[1] + tangent[1] * travel)
        result = self._clamp_to_table(end, table_roi)
        return (result, "tangent") if return_model else result

    @staticmethod
    def _edge_clearance(
        point: tuple[float, float],
        table_roi: tuple[float, float, float, float],
    ) -> float:
        x, y, w, h = table_roi
        return min(point[0] - x, (x + w) - point[0], point[1] - y, (y + h) - point[1])

    @staticmethod
    def _clamp_to_table(
        point: tuple[float, float],
        table_roi: tuple[float, float, float, float],
        margin: float = 24.0,
    ) -> tuple[float, float]:
        x, y, w, h = table_roi
        return (
            max(x + margin, min(x + w - margin, point[0])),
            max(y + margin, min(y + h - margin, point[1])),
        )
