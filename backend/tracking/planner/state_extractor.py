from __future__ import annotations

import statistics
from typing import Any, Optional

from .models import PlannerBall, PlannerState, PocketGeometry


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class StateExtractor:
    @staticmethod
    def _build_pockets(
        holes: list[tuple[float, float]],
        table_roi: tuple[float, float, float, float],
        ball_radius: float,
    ) -> tuple[list[PocketGeometry], dict[str, tuple[tuple[float, float], tuple[float, float]]]]:
        x, y, w, h = table_roi
        left = x + ball_radius + 8.0
        right = x + w - ball_radius - 8.0
        top = y + ball_radius + 8.0
        bottom = y + h - ball_radius - 8.0
        center_x = x + (w / 2.0)
        center_y = y + (h / 2.0)
        mouth_half = max(ball_radius * 1.45, 22.0)
        capture_radius = max(ball_radius * 1.2, 14.0)

        pockets: list[PocketGeometry] = []
        for idx, (hx, hy) in enumerate(holes):
            if hx <= x + (w * 0.2):
                side_x = left
                normal_x = -1.0
            elif hx >= x + (w * 0.8):
                side_x = right
                normal_x = 1.0
            else:
                side_x = center_x
                normal_x = 0.0

            if hy <= y + (h * 0.2):
                side_y = top
                normal_y = -1.0
            elif hy >= y + (h * 0.8):
                side_y = bottom
                normal_y = 1.0
            else:
                side_y = center_y
                normal_y = 0.0

            if abs(normal_x) > 0.0 and abs(normal_y) == 0.0:
                mouth = ((side_x, side_y - mouth_half), (side_x, side_y + mouth_half))
            elif abs(normal_y) > 0.0 and abs(normal_x) == 0.0:
                mouth = ((side_x - mouth_half, side_y), (side_x + mouth_half, side_y))
            else:
                mouth = (
                    (side_x - (mouth_half * normal_y), side_y - (mouth_half * normal_x)),
                    (side_x + (mouth_half * normal_y), side_y + (mouth_half * normal_x)),
                )

            pockets.append(
                PocketGeometry(
                    id=f"pocket-{idx}",
                    center=(hx, hy),
                    mouth_segment=mouth,
                    capture_radius=capture_radius,
                    approach_normal=(normal_x, normal_y),
                )
            )

        rail_margin = max(ball_radius * 3.0, 34.0)
        rail_segments = {
            "top": ((left + rail_margin, top), (right - rail_margin, top)),
            "bottom": ((left + rail_margin, bottom), (right - rail_margin, bottom)),
            "left": ((left, top + rail_margin), (left, bottom - rail_margin)),
            "right": ((right, top + rail_margin), (right, bottom - rail_margin)),
        }
        return pockets, rail_segments

    @staticmethod
    def _normalized_ball_radius(
        raw_radius: float,
        table_ball_radius_px: float,
        clamp_ratio: float = 0.12,
    ) -> float:
        lower = table_ball_radius_px * (1.0 - clamp_ratio)
        upper = table_ball_radius_px * (1.0 + clamp_ratio)
        return max(lower, min(upper, raw_radius))

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

        tx, ty, tw, th = table_roi
        table_w = max(1.0, _safe_float(tw))
        table_h = max(1.0, _safe_float(th))
        cue_w = max(1.0, _safe_float(white[2], 18.0))
        cue_h = max(1.0, _safe_float(white[3], 18.0))
        cue_radius_raw = max(1.0, min(cue_w, cue_h) / 2.0)

        raw_object_radii: list[float] = []
        for b in balls:
            if not isinstance(b, dict):
                continue
            bw = max(1.0, _safe_float(b.get("w"), 18.0))
            bh = max(1.0, _safe_float(b.get("h"), 18.0))
            raw_radius = max(1.0, _safe_float(b.get("radius"), min(bw, bh) / 2.0))
            raw_object_radii.append(raw_radius)

        if raw_object_radii:
            table_ball_radius_px = float(statistics.median(raw_object_radii))
            radius_source = "object_median"
        elif cue_radius_raw > 0.0:
            table_ball_radius_px = cue_radius_raw
            radius_source = "cue_fallback"
        else:
            table_ball_radius_px = max(10.0, min(table_w, table_h) * 0.032)
            radius_source = "table_default"

        table_ball_radius_px = max(8.0, table_ball_radius_px)
        cue_ball = PlannerBall(
            x=_safe_float(white[0]),
            y=_safe_float(white[1]),
            w=cue_w,
            h=cue_h,
            radius_px_raw=cue_radius_raw,
            radius_px=StateExtractor._normalized_ball_radius(cue_radius_raw, table_ball_radius_px),
            radius_source=radius_source,
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
            radius_raw = max(1.0, _safe_float(b.get("radius"), min(w, h) / 2.0))
            num_raw = b.get("number")
            number = int(num_raw) if isinstance(num_raw, int) or (isinstance(num_raw, float) and num_raw.is_integer()) else None
            object_balls.append(
                PlannerBall(
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    radius_px_raw=radius_raw,
                    radius_px=StateExtractor._normalized_ball_radius(radius_raw, table_ball_radius_px),
                    radius_source=radius_source,
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

        pockets, rail_segments = StateExtractor._build_pockets(
            normalized_holes,
            (_safe_float(tx), _safe_float(ty), table_w, table_h),
            table_ball_radius_px,
        )
        return PlannerState(
            cue_ball=cue_ball,
            object_balls=object_balls,
            holes=normalized_holes,
            pockets=pockets,
            table_roi=(
                _safe_float(tx),
                _safe_float(ty),
                table_w,
                table_h,
            ),
            table_ball_radius_px=table_ball_radius_px,
            rail_segments=rail_segments,
        )
