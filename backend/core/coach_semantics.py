from __future__ import annotations

import math
from collections import deque
from datetime import datetime
from typing import Any, Optional

from backend.tracking.planner.models import PlannerBall, PlannerState
from backend.tracking.planner.physics_validator import PhysicsValidator
from backend.tracking.planner.state_extractor import StateExtractor


# Must match TrackingEngine._estimate_default_holes(): left-top, left-bottom,
# right-top, right-bottom, top-middle, bottom-middle in original camera frame.
POCKET_NAMES = ["top_left", "bottom_left", "top_right", "bottom_right", "top_middle", "bottom_middle"]
TABLE_DEPENDENT_KEYWORDS = ("局勢", "下一桿", "怎麼打", "分析", "路線", "進哪顆", "母球", "走位", "解球")
GENERAL_RULE_KEYWORDS = ("規則", "犯規", "九號球", "開球", "洗袋", "怎麼算")
NINE_BALL_COLOR_STYLE_NUMBERS = {
    ("yellow", "solid"): 1,
    ("yellow", "unknown"): 1,
    ("orange", "unknown"): 1,
    ("blue", "solid"): 2,
    ("red", "solid"): 3,
    ("purple", "solid"): 4,
    ("orange", "solid"): 5,
    ("green", "solid"): 6,
    ("brown", "solid"): 7,
    ("black", "solid"): 8,
    ("yellow", "stripe"): 9,
}


def classify_coach_intent(message: str) -> str:
    """Classify whether a chat request needs the current table context."""
    text = str(message or "").strip()
    if any(keyword in text for keyword in GENERAL_RULE_KEYWORDS):
        return "general_rule"
    if any(keyword in text for keyword in TABLE_DEPENDENT_KEYWORDS):
        return "table_dependent"
    return "table_dependent"


class CoachSemanticAdapter:
    """Build deterministic geometry semantics for the remote AI Coach service."""

    def __init__(self, stable_frames: int = 5, stable_max_shift: float = 18.0, min_balls: int = 1) -> None:
        self.validator = PhysicsValidator()
        self.stable_frames = max(2, int(stable_frames))
        self.stable_max_shift = max(1.0, float(stable_max_shift))
        self.min_balls = max(0, int(min_balls))
        self._history: deque[dict[str, Any]] = deque(maxlen=self.stable_frames)
        self._latest_context: Optional[dict[str, Any]] = None
        self._last_unstable_reason: Optional[str] = "NO_SNAPSHOT"

    def update(self, packet: dict[str, Any], multi_plan: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Build context and update stability history."""
        context = self.build_context(packet, multi_plan)
        if not context.get("valid"):
            self._history.clear()
            self._latest_context = context
            self._last_unstable_reason = str(context.get("reason") or "INVALID_CONTEXT")
            return context

        signature = self._signature(context)
        self._history.append(signature)
        stable, reason = self._is_history_stable()
        context["stable"] = stable
        context["unstable_reason"] = None if stable else reason
        context["snapshot_at"] = datetime.now().isoformat()

        self._latest_context = context
        self._last_unstable_reason = context["unstable_reason"]
        return context

    def latest(self) -> Optional[dict[str, Any]]:
        """Return the latest semantic context."""
        return dict(self._latest_context) if isinstance(self._latest_context, dict) else None

    def state(self) -> dict[str, Any]:
        """Return stable snapshot status for API diagnostics."""
        latest = self._latest_context if isinstance(self._latest_context, dict) else {}
        return {
            "stable": bool(latest.get("stable", False)),
            "stable_ball_count": len(latest.get("balls", [])) if isinstance(latest.get("balls"), list) else 0,
            "last_snapshot_at": latest.get("snapshot_at"),
            "last_unstable_reason": self._last_unstable_reason,
        }

    def build_context(self, packet: dict[str, Any], multi_plan: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Convert a runtime YOLO packet into the standard AI Coach semantic JSON."""
        if not isinstance(packet, dict):
            return self._invalid("NO_RUNTIME_PACKET")

        reason = self._precheck_reason(packet)
        if reason is not None:
            return self._invalid(reason, packet)

        state = StateExtractor.from_runtime_packet(packet)
        if state is None:
            return self._invalid("STATE_EXTRACTOR_FAILED", packet)

        numbered_object_balls = [
            (ball, number)
            for ball in state.object_balls
            for number in [self._nine_ball_number(ball)]
            if isinstance(number, int) and number > 0
        ]
        if not numbered_object_balls:
            return self._invalid("NO_LEGAL_TARGET_BALLS", packet)

        legal_target_number = min(number for _, number in numbered_object_balls)
        cue = self._ball_payload(state.cue_ball, role="cue", ball_id="cue_ball")
        balls = [
            self._object_ball_payload(ball, state, legal_target_number, resolved_number=number)
            for ball, number in numbered_object_balls
        ]
        table = self._table_payload(state)
        return {
            "valid": True,
            "stable": False,
            "unstable_reason": "INSUFFICIENT_STABLE_FRAMES",
            "coordinate_space": "original_camera_frame",
            "table_context_available": True,
            "table": table,
            "cue_ball": cue,
            "balls": balls,
            "rules": {
                "game": "nine_ball",
                "legal_target_number": legal_target_number,
                "legal_target_id": f"ball-{legal_target_number}",
                "legal_target_policy": "The cue ball must contact the lowest numbered object ball first.",
            },
            "summary": self._summary(cue, balls),
            "multi_plan": multi_plan if isinstance(multi_plan, dict) else packet.get("multi_plan"),
            "raw_debug": {
                "runtime_status": packet.get("status"),
                "ball_count": len(balls),
            },
        }

    def is_path_clear(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        blockers: list[PlannerBall],
        ignore_numbers: set[int],
        safety_radius: float,
    ) -> bool:
        """Proxy to PhysicsValidator for tests and integration code."""
        return self.validator.is_path_clear(
            p1,
            p2,
            blockers,
            ignore_ball_numbers=ignore_numbers,
            safety_radius=safety_radius,
        )

    def _object_ball_payload(
        self,
        ball: PlannerBall,
        state: PlannerState,
        legal_target_number: int,
        resolved_number: int,
    ) -> dict[str, Any]:
        """Convert one numbered object ball into AI Coach semantics."""
        base = self._ball_payload(ball, role="object", ball_id=f"ball-{resolved_number}", resolved_number=resolved_number)
        blockers = [other for other in state.object_balls if other is not ball]

        pocket_options = []
        for idx, pocket in enumerate(state.pockets):
            blocked_by = self._blocked_by(
                ball.center,
                pocket.center,
                blockers,
                ignore_numbers={resolved_number},
                safety_radius=ball.radius,
            )
            distance_px = self.validator.distance(ball.center, pocket.center)
            pocket_options.append(
                {
                    "name": self._pocket_name(idx),
                    "center": [round(pocket.center[0], 1), round(pocket.center[1], 1)],
                    "distance_px": round(distance_px, 1),
                    "distance_label": self._distance_label(distance_px, state),
                    "path_clear": len(blocked_by) == 0,
                    "blocked_by": blocked_by,
                }
            )
        pocket_options.sort(key=lambda option: (not option["path_clear"], option["distance_px"]))

        cue_blocked_by = self._blocked_by(
            state.cue_ball.center,
            ball.center,
            blockers,
            ignore_numbers={resolved_number},
            safety_radius=state.cue_ball.radius,
        )
        cue_distance = self.validator.distance(state.cue_ball.center, ball.center)
        nearest = pocket_options[0] if pocket_options else None

        base.update(
            {
                "is_legal_target": resolved_number == legal_target_number,
                "raw_detected_number": ball.number,
                "number_source": self._number_source(ball, resolved_number),
                "semantic_location": self._semantic_location(ball.center, state, nearest),
                "nearest_pocket": nearest,
                "pocket_options": pocket_options[:6],
                "cue_distance_px": round(cue_distance, 1),
                "cue_path_clear": len(cue_blocked_by) == 0,
                "cue_blocked_by": cue_blocked_by,
            }
        )
        return base

    def _ball_payload(
        self,
        ball: PlannerBall,
        role: str,
        ball_id: str,
        resolved_number: Optional[int] = None,
    ) -> dict[str, Any]:
        """Build common ball fields in original camera coordinates."""
        return {
            "id": ball_id,
            "role": role,
            "number": resolved_number if resolved_number is not None else ball.number,
            "color": ball.color,
            "style": ball.style,
            "center": [round(ball.center[0], 1), round(ball.center[1], 1)],
            "bbox_xywh": [round(ball.x, 1), round(ball.y, 1), round(ball.w, 1), round(ball.h, 1)],
            "bbox_semantics": "bbox_xywh_top_left",
            "radius": round(ball.radius, 1),
            "confidence": round(float(ball.conf), 3),
        }

    def _nine_ball_number(self, ball: PlannerBall) -> Optional[int]:
        """Resolve number by nine-ball color/style first, then raw detector number.

        This protects the coach from detector number noise. In nine-ball, a
        yellow solid is the 1-ball even if an upstream label briefly reports 4.
        """
        color = str(ball.color or "").strip().lower()
        style = str(ball.style or "").strip().lower()
        mapped = NINE_BALL_COLOR_STYLE_NUMBERS.get((color, style))
        if mapped is not None:
            return mapped
        if isinstance(ball.number, int) and ball.number > 0:
            return ball.number
        return None

    def _number_source(self, ball: PlannerBall, resolved_number: int) -> str:
        """Report whether number came from color/style or raw detector number."""
        color = str(ball.color or "").strip().lower()
        style = str(ball.style or "").strip().lower()
        mapped = NINE_BALL_COLOR_STYLE_NUMBERS.get((color, style))
        return "color_style" if mapped == resolved_number else "detector_number"

    def _table_payload(self, state: PlannerState) -> dict[str, Any]:
        """Build table bounds and pocket references."""
        tx, ty, tw, th = state.table_roi
        return {
            "coordinate_space": "original_camera_frame",
            "bbox_xywh": [round(tx, 1), round(ty, 1), round(tw, 1), round(th, 1)],
            "bounds": {
                "left": round(tx, 1),
                "top": round(ty, 1),
                "right": round(tx + tw, 1),
                "bottom": round(ty + th, 1),
            },
            "ball_radius_px": round(state.table_ball_radius_px, 1),
            "pockets": [
                {
                    "name": self._pocket_name(idx),
                    "center": [round(pocket.center[0], 1), round(pocket.center[1], 1)],
                    "capture_radius": round(pocket.capture_radius, 1),
                }
                for idx, pocket in enumerate(state.pockets)
            ],
        }

    def _blocked_by(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        blockers: list[PlannerBall],
        ignore_numbers: set[int],
        safety_radius: float,
    ) -> list[dict[str, Any]]:
        """Find balls close enough to block the line segment from p1 to p2."""
        blocked = []
        moving_radius = max(1.0, safety_radius)
        sweep_radius = max(self.validator.min_clearance_px, moving_radius * self.validator.clearance_scale)
        for ball in blockers:
            number = self._nine_ball_number(ball)
            if number is not None and number in ignore_numbers:
                continue
            distance = self.validator._point_to_segment_distance(ball.center, p1, p2)
            min_gap = sweep_radius + (max(1.0, ball.radius) * self.validator.clearance_scale) + self.validator.min_clearance_px
            if distance < min_gap:
                blocked.append(
                    {
                        "id": f"ball-{number}" if number is not None else self._ball_id(ball),
                        "number": number,
                        "distance_to_line_px": round(distance, 1),
                    }
                )
        return blocked

    def _semantic_location(self, center: tuple[float, float], state: PlannerState, nearest: Optional[dict[str, Any]]) -> str:
        """Describe location relative to table bounds and nearest pocket."""
        tx, ty, tw, th = state.table_roi
        rel_x = (center[0] - tx) / max(1.0, tw)
        rel_y = (center[1] - ty) / max(1.0, th)
        horizontal = "left" if rel_x < 0.33 else "center" if rel_x < 0.66 else "right"
        vertical = "top" if rel_y < 0.33 else "middle" if rel_y < 0.66 else "bottom"
        if nearest:
            return f"{vertical}_{horizontal}, {nearest['distance_label']} {nearest['name']}, {nearest['distance_px']}px"
        return f"{vertical}_{horizontal}"

    def _distance_label(self, distance: float, state: PlannerState) -> str:
        """Bucket pocket distance by table short side."""
        short_side = min(state.table_roi[2], state.table_roi[3])
        if distance <= short_side * 0.08:
            return "very_close_to"
        if distance <= short_side * 0.18:
            return "close_to"
        if distance <= short_side * 0.36:
            return "mid_distance_to"
        return "far_from"

    def _summary(self, cue: dict[str, Any], balls: list[dict[str, Any]]) -> str:
        """Create a compact summary for diagnostics."""
        legal = next((ball for ball in balls if ball.get("is_legal_target")), None)
        legal_text = f"legal target {legal.get('number')}" if isinstance(legal, dict) else "no legal target"
        clear = [
            ball
            for ball in balls
            if ball.get("cue_path_clear")
            and isinstance(ball.get("nearest_pocket"), dict)
            and ball["nearest_pocket"].get("path_clear")
        ]
        return f"{len(balls)} object balls, {legal_text}, {len(clear)} clear routes"

    def _signature(self, context: dict[str, Any]) -> dict[str, Any]:
        """Build a stable position signature."""
        balls = [context.get("cue_ball")] + list(context.get("balls") or [])
        points = []
        for ball in balls:
            if not isinstance(ball, dict) or not isinstance(ball.get("center"), list):
                continue
            points.append((str(ball.get("id")), float(ball["center"][0]), float(ball["center"][1])))
        points.sort(key=lambda item: item[0])
        return {"count": len(points), "points": points}

    def _is_history_stable(self) -> tuple[bool, str]:
        """Check whether the recent semantic snapshots are stable."""
        if len(self._history) < self.stable_frames:
            return False, "INSUFFICIENT_STABLE_FRAMES"
        counts = {item["count"] for item in self._history}
        if len(counts) != 1:
            return False, "BALL_COUNT_CHANGED"
        if min(counts or {0}) < self.min_balls:
            return False, "NO_OBJECT_BALLS"

        first = self._history[0]["points"]
        for sample in list(self._history)[1:]:
            points = sample["points"]
            if [p[0] for p in points] != [p[0] for p in first]:
                return False, "BALL_ID_CHANGED"
            for base, current in zip(first, points):
                if math.hypot(base[1] - current[1], base[2] - current[2]) > self.stable_max_shift:
                    return False, "BALLS_MOVING"
        return True, ""

    def _precheck_reason(self, packet: dict[str, Any]) -> Optional[str]:
        """Validate runtime packet fields needed for geometry semantics."""
        if not isinstance(packet.get("white_ball"), list) or len(packet.get("white_ball") or []) < 4:
            return "NO_CUE_BALL"
        if not isinstance(packet.get("balls"), list) or len(packet.get("balls") or []) == 0:
            return "NO_OBJECT_BALLS"
        if not isinstance(packet.get("table_roi"), list) or len(packet.get("table_roi") or []) != 4:
            return "NO_TABLE_OR_POCKETS"
        holes = packet.get("holes")
        if not isinstance(holes, list) or len(holes) == 0:
            return "NO_TABLE_OR_POCKETS"
        return None

    def _invalid(self, reason: str, packet: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Return a standard invalid semantic context."""
        return {
            "valid": False,
            "stable": False,
            "reason": reason,
            "unstable_reason": reason,
            "table_context_available": False,
            "coordinate_space": "original_camera_frame",
            "raw_debug": {
                "runtime_status": packet.get("status") if isinstance(packet, dict) else None,
            },
            "snapshot_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _ball_id(ball: PlannerBall) -> str:
        """Build a fallback id for unnumbered balls."""
        if ball.number is not None:
            return f"ball-{ball.number}"
        label = ball.color.lower().replace(" ", "-")
        return f"ball-{label}-{round(ball.center[0])}-{round(ball.center[1])}"

    @staticmethod
    def _pocket_name(index: int) -> str:
        """Return a stable pocket name."""
        return POCKET_NAMES[index] if index < len(POCKET_NAMES) else f"pocket_{index}"
