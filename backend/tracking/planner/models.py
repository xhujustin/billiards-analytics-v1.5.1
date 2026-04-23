from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


Point = tuple[float, float]


@dataclass
class PlannerBall:
    x: float
    y: float
    w: float
    h: float
    radius: float
    number: Optional[int]
    color: str
    style: str
    conf: float = 0.0

    @property
    def center(self) -> Point:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)


@dataclass
class PlannerState:
    cue_ball: PlannerBall
    object_balls: list[PlannerBall]
    holes: list[Point]
    table_roi: tuple[float, float, float, float]


@dataclass
class StrokeHint:
    type: str
    power: str
    spin: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "power": self.power,
            "spin": self.spin,
            "rationale": self.rationale,
        }


@dataclass
class RouteCandidate:
    id: str
    route_type: str
    target_ball_number: Optional[int]
    first_contact_ball_number: Optional[int]
    score: float
    difficulty: int
    difficulty_level: str
    success_prob: float
    cut_angle: float
    total_distance: float
    path_points: list[list[int]]
    route_segments: list[dict[str, Any]]
    cue_landing_point: Optional[list[int]]
    cue_landing_zone: Optional[dict[str, Any]]
    nodes: list[str]
    stroke_hint: StrokeHint
    risk_flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "route_type": self.route_type,
            "target_ball_number": self.target_ball_number,
            "first_contact_ball_number": self.first_contact_ball_number,
            "score": round(float(self.score), 4),
            "difficulty": int(self.difficulty),
            "difficulty_level": self.difficulty_level,
            "success_prob": round(float(self.success_prob), 4),
            "cut_angle": round(float(self.cut_angle), 2),
            "total_distance": round(float(self.total_distance), 2),
            "path_points": self.path_points,
            "route_segments": self.route_segments,
            "cue_landing_point": self.cue_landing_point,
            "cue_landing_zone": self.cue_landing_zone,
            "nodes": self.nodes,
            "stroke_hint": self.stroke_hint.to_dict(),
            "risk_flags": self.risk_flags,
            "metadata": self.metadata,
        }


@dataclass
class MultiRoutePlan:
    rule_profile: str
    latency_ms: float
    routes: list[RouteCandidate]
    coach_notes: list[str]
    fallback_used: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        best_route = self.routes[0] if self.routes else None
        return {
            "rule_profile": self.rule_profile,
            "latency_ms": round(float(self.latency_ms), 2),
            "best_route": best_route.to_dict() if best_route else None,
            "routes": [route.to_dict() for route in self.routes],
            "coach_notes": self.coach_notes,
            "fallback_used": self.fallback_used,
            "error": self.error,
        }
