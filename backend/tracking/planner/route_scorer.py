from __future__ import annotations

import math
from typing import Optional

from .models import RouteCandidate


class RouteScorer:
    def score(
        self,
        route: RouteCandidate,
        rule_profile: str,
        target_ball_number: Optional[int],
    ) -> RouteCandidate:
        base = route.success_prob
        risk_penalty = 0.0
        bonus = 0.0

        if route.cut_angle > 55:
            risk_penalty += 0.16
            route.risk_flags.append("high_cut_angle")
        if route.route_type == "bank":
            risk_penalty += 0.10
        if route.route_type == "combo":
            risk_penalty += 0.14
        if route.route_type == "kick":
            risk_penalty += 0.18
            route.risk_flags.append("kick_escape")

        if target_ball_number is not None:
            if route.first_contact_ball_number != target_ball_number:
                risk_penalty += 0.72
                route.risk_flags.append("wrong_first_contact")
            else:
                bonus += 0.14

        if rule_profile == "9ball":
            if target_ball_number is not None and route.first_contact_ball_number != target_ball_number:
                route.risk_flags.append("foul_target_ball")
        else:
            # practice 模式保留球型多樣性，但不應覆蓋指定目標球。
            if route.route_type in {"bank", "combo"}:
                bonus += 0.06

        score = max(0.0, min(1.0, base + bonus - risk_penalty))
        difficulty = int(round(max(0.0, min(100.0, (1.0 - score) * 100.0))))

        if difficulty < 35:
            level = "easy"
        elif difficulty < 70:
            level = "medium"
        else:
            level = "hard"

        route.score = score
        route.difficulty = difficulty
        route.difficulty_level = level
        route.success_prob = max(0.01, min(0.99, score))
        return route

    @staticmethod
    def estimate_base_success(cut_angle: float, distance: float, bounces: int, combo_depth: int) -> float:
        angle_factor = max(0.15, 1.0 - (cut_angle / 100.0))
        dist_factor = max(0.2, 1.0 - (distance / 2800.0))
        bounce_factor = math.pow(0.86, bounces)
        combo_factor = math.pow(0.82, max(0, combo_depth - 1))
        return max(0.03, min(0.95, angle_factor * dist_factor * bounce_factor * combo_factor))
