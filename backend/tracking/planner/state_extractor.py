from __future__ import annotations

from typing import Any, Optional

from .models import PlannerBall, PlannerState


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class StateExtractor:
    @staticmethod
    def from_runtime_packet(packet: dict[str, Any]) -> Optional[PlannerState]:
        white = packet.get("white_ball")
        balls = packet.get("balls", [])
        holes = packet.get("holes", [])
        table_roi = packet.get("table_roi")

        if not isinstance(white, list) or len(white) < 4:
            return None
        if not isinstance(balls, list) or len(balls) == 0:
            return None
        if not isinstance(holes, list) or len(holes) == 0:
            return None
        if not isinstance(table_roi, list) or len(table_roi) != 4:
            return None

        cue_w = max(1.0, _safe_float(white[2], 18.0))
        cue_h = max(1.0, _safe_float(white[3], 18.0))
        cue_ball = PlannerBall(
            x=_safe_float(white[0]),
            y=_safe_float(white[1]),
            w=cue_w,
            h=cue_h,
            radius=max(1.0, min(cue_w, cue_h) / 2.0),
            number=0,
            color="White",
            style="Cue",
            conf=1.0,
        )

        object_balls: list[PlannerBall] = []
        for b in balls:
            if not isinstance(b, dict):
                continue
            x = _safe_float(b.get("x"))
            y = _safe_float(b.get("y"))
            w = max(1.0, _safe_float(b.get("w"), 18.0))
            h = max(1.0, _safe_float(b.get("h"), 18.0))
            radius = max(1.0, _safe_float(b.get("radius"), min(w, h) / 2.0))
            num_raw = b.get("number")
            number = int(num_raw) if isinstance(num_raw, int) or (isinstance(num_raw, float) and num_raw.is_integer()) else None
            object_balls.append(
                PlannerBall(
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    radius=radius,
                    number=number,
                    color=str(b.get("color", "Unknown")),
                    style=str(b.get("style", "Unknown")),
                    conf=_safe_float(b.get("conf"), 0.0),
                )
            )

        if not object_balls:
            return None

        normalized_holes: list[tuple[float, float]] = []
        for hxy in holes:
            if isinstance(hxy, list) and len(hxy) >= 2:
                normalized_holes.append((_safe_float(hxy[0]), _safe_float(hxy[1])))

        if not normalized_holes:
            return None

        x, y, w, h = table_roi
        return PlannerState(
            cue_ball=cue_ball,
            object_balls=object_balls,
            holes=normalized_holes,
            table_roi=(
                _safe_float(x),
                _safe_float(y),
                max(1.0, _safe_float(w)),
                max(1.0, _safe_float(h)),
            ),
        )
