from __future__ import annotations

import math
from typing import Iterable

from .models import PlannerBall, PocketGeometry, Point


class PhysicsValidator:
    def __init__(self, clearance_scale: float = 1.08, min_clearance_px: float = 2.0):
        self.clearance_scale = clearance_scale
        self.min_clearance_px = min_clearance_px

    @staticmethod
    def distance(a: Point, b: Point) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    @staticmethod
    def _point_to_segment_distance(p: Point, a: Point, b: Point) -> float:
        ax, ay = a
        bx, by = b
        px, py = p
        abx, aby = bx - ax, by - ay
        apx, apy = px - ax, py - ay
        denom = abx * abx + aby * aby
        if denom <= 1e-9:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
        cx = ax + abx * t
        cy = ay + aby * t
        return math.hypot(px - cx, py - cy)

    def is_path_clear(
        self,
        p1: Point,
        p2: Point,
        blockers: Iterable[PlannerBall],
        ignore_ball_numbers: set[int],
        safety_radius: float,
        ignored_ball_centers: Iterable[Point] | None = None,
    ) -> bool:
        ignored_centers = tuple(ignored_ball_centers or ())
        moving_radius = max(1.0, safety_radius)
        sweep_radius = max(self.min_clearance_px, moving_radius * self.clearance_scale)
        for ball in blockers:
            if self._should_ignore_blocker(ball, ignore_ball_numbers, ignored_centers):
                continue
            d = self._point_to_segment_distance(ball.center, p1, p2)
            blocker_radius = max(1.0, ball.radius)
            min_gap = sweep_radius + (blocker_radius * self.clearance_scale) + self.min_clearance_px
            if d < min_gap:
                return False
        return True

    def _should_ignore_blocker(
        self,
        ball: PlannerBall,
        ignore_ball_numbers: set[int],
        ignored_ball_centers: tuple[Point, ...],
    ) -> bool:
        if ignored_ball_centers:
            same_ball_tolerance = max(3.0, ball.radius * 0.35)
            return any(self.distance(ball.center, center) <= same_ball_tolerance for center in ignored_ball_centers)
        return ball.number is not None and ball.number in ignore_ball_numbers

    def point_in_table(self, p: Point, table_roi: tuple[float, float, float, float], margin: float = 20.0) -> bool:
        x, y, w, h = table_roi
        return (x + margin) <= p[0] <= (x + w - margin) and (y + margin) <= p[1] <= (y + h - margin)

    def ball_center_in_table(
        self,
        p: Point,
        table_roi: tuple[float, float, float, float],
        ball_radius: float,
        cushion_margin: float = 20.0,
    ) -> bool:
        return self.point_in_table(p, table_roi, margin=max(cushion_margin, ball_radius + 4.0))

    def point_on_rail_segment(
        self,
        p: Point,
        rail_segment: tuple[Point, Point],
        tolerance: float = 6.0,
    ) -> bool:
        (x1, y1), (x2, y2) = rail_segment
        if abs(x1 - x2) <= 1e-6:
            if abs(p[0] - x1) > tolerance:
                return False
            return min(y1, y2) - tolerance <= p[1] <= max(y1, y2) + tolerance
        if abs(y1 - y2) <= 1e-6:
            if abs(p[1] - y1) > tolerance:
                return False
            return min(x1, x2) - tolerance <= p[0] <= max(x1, x2) + tolerance
        return self._point_to_segment_distance(p, rail_segment[0], rail_segment[1]) <= tolerance

    def can_pocket_ball(
        self,
        from_point: Point,
        pocket: PocketGeometry,
        ball_radius: float,
        target_point: Point | None = None,
    ) -> bool:
        target = target_point or pocket.center
        mouth_a, mouth_b = pocket.mouth_segment
        target_dist = self.distance(from_point, target)
        normal = pocket.approach_normal
        if target_dist > 1e-6 and (abs(normal[0]) > 0.0 or abs(normal[1]) > 0.0):
            target_dir = ((target[0] - from_point[0]) / target_dist, (target[1] - from_point[1]) / target_dist)
            approach = target_dir[0] * normal[0] + target_dir[1] * normal[1]
            if approach < 0.12:
                return False

        # 檢查進袋線是否通過袋口入口區，而不是要求球目前就靠近袋口。
        line_dist = self._point_to_segment_distance(target, from_point, target)
        if line_dist > 1e-6:
            return False

        mouth_len = self.distance(mouth_a, mouth_b)
        if mouth_len > 1e-6:
            mouth_acceptance = max(ball_radius * 1.8, pocket.capture_radius * 1.2)
            target_mouth_offset = self._point_to_segment_distance(target, mouth_a, mouth_b)
            if target_mouth_offset <= mouth_acceptance:
                return True

            mouth_mid = ((mouth_a[0] + mouth_b[0]) / 2.0, (mouth_a[1] + mouth_b[1]) / 2.0)
            mouth_offset = self._point_to_segment_distance(mouth_mid, from_point, target)
            if mouth_offset > mouth_acceptance:
                return False

        return True
