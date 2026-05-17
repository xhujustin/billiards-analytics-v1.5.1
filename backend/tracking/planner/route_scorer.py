from __future__ import annotations

import math
from typing import Any, Optional

from .models import RouteCandidate


class RouteScorer:
    original_score_weight = 0.70
    position_score_weight = 0.30
    _POSITION_BLEND_WEIGHTS = {
        "practice": (0.60, 0.40),
        "9ball": (0.65, 0.35),
    }

    def score(
        self,
        route: RouteCandidate,
        rule_profile: str,
        target_ball_number: Optional[int],
    ) -> RouteCandidate:
        base = route.success_prob
        risk_penalty = 0.0
        bonus = 0.0
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        route.metadata = metadata
        physics = metadata.get("physics") if isinstance(metadata.get("physics"), dict) else {}

        if route.cut_angle > 55:
            risk_penalty += 0.16
            self._append_risk_flag(route, "high_cut_angle")
        if route.route_type == "bank":
            risk_penalty += 0.10
        if route.route_type == "combo":
            risk_penalty += 0.14
            transfer_angle = float(metadata.get("combo_transfer_angle", 0.0) or 0.0)
            second_cushion_clearance = float(metadata.get("second_cushion_clearance", 999.0) or 999.0)
            if transfer_angle > 45:
                risk_penalty += 0.18
                self._append_risk_flag(route, "thin_combo_transfer")
            elif transfer_angle > 32:
                risk_penalty += 0.08
            if second_cushion_clearance < 10:
                risk_penalty += 0.16
                self._append_risk_flag(route, "combo_second_ball_near_cushion")
            elif second_cushion_clearance < 18:
                risk_penalty += 0.08
        if route.route_type in {"kick", "kick_escape", "safe_escape", "contact_only"}:
            risk_penalty += 0.18
            self._append_risk_flag(route, "kick_escape")
            if route.route_type in {"kick_escape", "contact_only"}:
                risk_penalty += 0.08
                self._append_risk_flag(route, "contact_only")
            if route.route_type == "safe_escape":
                safety_score = float(metadata.get("safety_score", 0.0) or 0.0)
                bonus += min(0.08, safety_score * 0.08)

        energy_margin = float(physics.get("energy_margin", 0.0) or 0.0)
        if energy_margin < -0.18:
            risk_penalty += 0.14
            self._append_risk_flag(route, "insufficient_power_margin")
        elif energy_margin < -0.06:
            risk_penalty += 0.06

        rail_error = float(physics.get("rail_error_px", 0.0) or 0.0)
        if rail_error > 42:
            risk_penalty += 0.16
            self._append_risk_flag(route, "high_rail_error")
        elif rail_error > 28:
            risk_penalty += 0.08

        object_energy_margin = float(physics.get("object_energy_margin", 0.0) or 0.0)
        if object_energy_margin < -0.18:
            risk_penalty += 0.12
            self._append_risk_flag(route, "object_lacks_energy")
        elif object_energy_margin < -0.08:
            risk_penalty += 0.05

        throw_error = float(physics.get("throw_error_px", 0.0) or 0.0)
        if throw_error > 5.5:
            risk_penalty += 0.11
            self._append_risk_flag(route, "collision_throw_error")
        elif throw_error > 3.2:
            risk_penalty += 0.05

        pocket_speed_risk = float(physics.get("pocket_speed_risk", 0.0) or 0.0)
        if pocket_speed_risk > 0.22:
            risk_penalty += 0.10
            self._append_risk_flag(route, "poor_pocket_speed")
        elif pocket_speed_risk > 0.12:
            risk_penalty += 0.04

        line_tolerance = float(physics.get("line_tolerance_px", 99.0) or 99.0)
        if line_tolerance < 5.0:
            risk_penalty += 0.10
            self._append_risk_flag(route, "low_line_tolerance")
        elif line_tolerance < 8.0:
            risk_penalty += 0.04

        if target_ball_number is not None:
            if route.first_contact_ball_number != target_ball_number:
                risk_penalty += 0.72
                self._append_risk_flag(route, "wrong_first_contact")
            else:
                bonus += 0.14

        if rule_profile == "9ball":
            if target_ball_number is not None and route.first_contact_ball_number != target_ball_number:
                self._append_risk_flag(route, "foul_target_ball")
        else:
            # practice 模式保留球型多樣性，但不應覆蓋指定目標球。
            if route.route_type in {"bank", "combo"}:
                bonus += 0.06

        score = max(0.0, min(1.0, base + bonus - risk_penalty))
        if route.route_type == "combo":
            score = min(score, 0.62)
        if route.route_type in {"kick_escape", "safe_escape", "contact_only"}:
            score = min(score, 0.36)
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

    def blend_position_play_score(
        self,
        route: RouteCandidate,
        rule_profile: Optional[str] = None,
        scoring_mode: Optional[str] = None,
    ) -> RouteCandidate:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        route.metadata = metadata

        position_play = route.position_play if isinstance(route.position_play, dict) else None
        if position_play is None:
            return route

        original_score = self._clamp_score(metadata.get("pre_position_score", route.score))
        if "pre_position_score" not in metadata:
            metadata["pre_position_score"] = round(original_score, 4)

        original_weight, position_weight, resolved_mode = self._position_blend_weights(
            rule_profile=rule_profile,
            scoring_mode=scoring_mode,
        )
        position_score = self._position_score(position_play)
        self._apply_position_risk_flags(route, position_play)

        blended_score = (
            original_score * original_weight
            + position_score * position_weight
        )
        score = self._clamp_score(blended_score)
        route.score = score
        route.success_prob = max(0.01, min(0.99, score))
        self._set_difficulty(route, score)
        metadata["position_score_component"] = round(position_score, 4)
        metadata["position_score_weight"] = position_weight
        metadata["score_breakdown"] = {
            "scoring_mode": resolved_mode,
            "rule_profile": rule_profile,
            "pot_score": round(original_score, 4),
            "pot_weight": original_weight,
            "position_score": round(position_score, 4),
            "position_weight": position_weight,
            "final_score": round(score, 4),
        }
        return route

    @staticmethod
    def estimate_base_success(cut_angle: float, distance: float, bounces: int, combo_depth: int) -> float:
        angle_factor = max(0.15, 1.0 - (cut_angle / 100.0))
        dist_factor = max(0.2, 1.0 - (distance / 2800.0))
        bounce_factor = math.pow(0.86, bounces)
        combo_factor = math.pow(0.82, max(0, combo_depth - 1))
        return max(0.03, min(0.95, angle_factor * dist_factor * bounce_factor * combo_factor))

    @staticmethod
    def _set_difficulty(route: RouteCandidate, score: float) -> None:
        difficulty = int(round(max(0.0, min(100.0, (1.0 - score) * 100.0))))
        if difficulty < 35:
            level = "easy"
        elif difficulty < 70:
            level = "medium"
        else:
            level = "hard"
        route.difficulty = difficulty
        route.difficulty_level = level

    @classmethod
    def _position_score(cls, position_play: dict[str, Any]) -> float:
        score = position_play.get("score")
        if not isinstance(score, dict):
            return 0.5
        shape_quality = cls._clamp_score(score.get("shape_quality", 0.5))
        position_success = cls._clamp_score(score.get("position_success_prob", 0.5))
        risk = cls._clamp_score(score.get("risk", 0.5))
        return cls._clamp_score(shape_quality * 0.45 + position_success * 0.45 + (1.0 - risk) * 0.10)

    @classmethod
    def _apply_position_risk_flags(cls, route: RouteCandidate, position_play: dict[str, Any]) -> None:
        score = position_play.get("score")
        if not isinstance(score, dict):
            return

        shape_quality = cls._clamp_score(score.get("shape_quality", 0.5))
        position_success = cls._clamp_score(score.get("position_success_prob", 0.5))
        risk = cls._clamp_score(score.get("risk", 0.0))
        if shape_quality < 0.35 or position_success < 0.35 or risk > 0.68:
            cls._append_risk_flag(route, "poor_position")

        if position_play.get("next_ball") is None:
            cls._append_risk_flag(route, "next_ball_missing")

        cue_after_contact = position_play.get("cue_ball_after_contact")
        if not isinstance(cue_after_contact, dict):
            return
        expected_point = cue_after_contact.get("expected_point")
        avoid_zones = cue_after_contact.get("avoid_zones")
        expected_xy = cls._as_point(expected_point)
        if expected_xy is None or not isinstance(avoid_zones, list):
            return

        for zone in avoid_zones:
            if not isinstance(zone, dict) or zone.get("type") != "pocket_scratch":
                continue
            center = zone.get("center")
            center_xy = cls._as_point(center)
            if center_xy is None:
                continue
            radius = max(0.0, float(zone.get("radius", 0.0) or 0.0))
            distance = math.hypot(expected_xy[0] - center_xy[0], expected_xy[1] - center_xy[1])
            if radius > 0.0 and distance <= radius * 1.15:
                cls._append_risk_flag(route, "cue_landing_near_pocket")
                break

    @classmethod
    def _position_blend_weights(
        cls,
        rule_profile: Optional[str] = None,
        scoring_mode: Optional[str] = None,
    ) -> tuple[float, float, str]:
        mode = scoring_mode or rule_profile or "default"
        weights = cls._POSITION_BLEND_WEIGHTS.get(mode)
        if weights is None:
            weights = (cls.original_score_weight, cls.position_score_weight)
        return weights[0], weights[1], mode

    @staticmethod
    def _append_risk_flag(route: RouteCandidate, flag: str) -> None:
        if flag not in route.risk_flags:
            route.risk_flags.append(flag)

    @staticmethod
    def _is_point(value: Any) -> bool:
        return isinstance(value, (list, tuple)) and len(value) >= 2

    @staticmethod
    def _as_point(value: Any) -> Optional[tuple[float, float]]:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        try:
            return (float(value[0]), float(value[1]))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clamp_score(value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.0
        return max(0.0, min(1.0, parsed))
