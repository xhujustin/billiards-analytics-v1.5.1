from __future__ import annotations

import math
from typing import Iterable

from .models import PlannerBall, Point


class PhysicsValidator:
    def __init__(self, clearance_scale: float = 1.15):
        self.clearance_scale = clearance_scale

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
    ) -> bool:
        threshold = max(4.0, safety_radius * self.clearance_scale)
        for ball in blockers:
            if ball.number is not None and ball.number in ignore_ball_numbers:
                continue
            d = self._point_to_segment_distance(ball.center, p1, p2)
            min_gap = threshold + max(2.0, ball.radius * 0.85)
            if d < min_gap:
                return False
        return True

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
