from __future__ import annotations

import time
from typing import Any, Optional

from .candidate_generator import CandidateGenerator
from .models import MultiRoutePlan, PlannerState
from .physics_validator import PhysicsValidator
from .route_scorer import RouteScorer
from .state_extractor import StateExtractor


class RoutePlanner:
    def __init__(self):
        self.validator = PhysicsValidator()
        self.generator = CandidateGenerator(self.validator)
        self.scorer = RouteScorer()
        self.last_plan: Optional[dict[str, Any]] = None
        self.last_error: Optional[str] = None

    def plan(
        self,
        state: PlannerState,
        rule_profile: str = "practice",
        top_n: int = 5,
        target_ball_number: Optional[int] = None,
        max_bounces: int = 2,
        combo_depth: int = 2,
        selected_route_id: Optional[str] = None,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        top_n = max(1, min(10, int(top_n)))
        try:
            if target_ball_number is None:
                target_ball_number = self._default_target_ball_number(state)

            candidates = self.generator.generate(state, max_bounces=max_bounces, combo_depth=combo_depth)
            if not candidates:
                plan = MultiRoutePlan(
                    rule_profile=rule_profile,
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                    routes=[],
                    coach_notes=["目前沒有可行進球線，建議先調整母球站位或改走解球。"],
                    fallback_used=False,
                    error="NO_POTTING_ROUTE",
                ).to_dict()
                self.last_plan = plan
                self.last_error = "NO_POTTING_ROUTE"
                return plan

            # 先套用目標球規則再排序，避免可行但較難的 1 號球被粗篩提前排除。
            scored = [
                self.scorer.score(c, rule_profile=rule_profile, target_ball_number=target_ball_number)
                for c in candidates
            ]

            legal_target_routes = []
            if target_ball_number is not None:
                legal_target_routes = [
                    route for route in scored if route.first_contact_ball_number == target_ball_number
                ]
                if legal_target_routes:
                    scored = legal_target_routes
                else:
                    plan = MultiRoutePlan(
                        rule_profile=rule_profile,
                        latency_ms=(time.perf_counter() - t0) * 1000.0,
                        routes=[],
                        coach_notes=[
                            f"{target_ball_number} 號球目前被擋住，找不到合法首碰路線。",
                            "請考慮解球：一庫 kick、調整母球位置，或先處理遮擋球型。",
                        ],
                        fallback_used=False,
                        error="TARGET_BLOCKED_NO_LEGAL_ROUTE",
                    ).to_dict()
                    self.last_plan = plan
                    self.last_error = "TARGET_BLOCKED_NO_LEGAL_ROUTE"
                    return plan

            scored.sort(key=lambda c: c.score, reverse=True)
            deduped = self._dedupe_routes(scored)
            playable_potting = [
                route
                for route in deduped
                if self._route_class(route) == "potting_route"
                and route.success_prob >= 0.35
                and route.cut_angle <= 70
            ]
            escape_routes = [
                route
                for route in deduped
                if self._route_class(route) in {"safe_escape", "contact_only"}
            ]
            if playable_potting:
                deduped = playable_potting + escape_routes

            final_routes = self._select_diverse_routes(deduped, top_n)
            if not final_routes:
                error_code = "NO_POTTING_ROUTE"
                coach_notes = [
                    "目前沒有可接受的進球線。",
                    "請考慮解球、調整母球位置，或降低進攻難度後再重算。",
                ]
                escape_routes = [
                    route
                    for route in scored
                    if self._route_class(route) in {"safe_escape", "contact_only"}
                    or route.route_type == "kick"
                ]
                if escape_routes:
                    error_code = "ONLY_ESCAPE_ROUTE_AVAILABLE"
                    coach_notes = [
                        "目前沒有穩定進球線，只剩解球路線可考慮。",
                        "建議優先使用 kick escape 或先做安全球。",
                    ]
                plan = MultiRoutePlan(
                    rule_profile=rule_profile,
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                    routes=[],
                    coach_notes=coach_notes,
                    fallback_used=False,
                    error=error_code,
                ).to_dict()
                self.last_plan = plan
                self.last_error = error_code
                return plan

            selected_route = None
            if selected_route_id:
                selected_route = next((route for route in deduped if route.id == selected_route_id), None)

            coach_notes = self._build_coach_notes(final_routes, rule_profile)
            plan = MultiRoutePlan(
                rule_profile=rule_profile,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                routes=final_routes,
                coach_notes=coach_notes,
                fallback_used=False,
            ).to_dict()
            if selected_route is not None:
                plan["best_route"] = selected_route.to_dict()
                plan["selected_route_id"] = selected_route_id
            self.last_plan = plan
            self.last_error = None
            return plan
        except Exception as e:
            plan = MultiRoutePlan(
                rule_profile=rule_profile,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                routes=[],
                coach_notes=["規劃器發生錯誤，已切回舊版單路徑模式。"],
                fallback_used=True,
                error=str(e),
            ).to_dict()
            self.last_plan = plan
            self.last_error = str(e)
            return plan

    def plan_from_runtime_packet(
        self,
        packet: dict[str, Any],
        rule_profile: str = "practice",
        top_n: int = 5,
        target_ball_number: Optional[int] = None,
        max_bounces: int = 2,
        combo_depth: int = 2,
        selected_route_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        state = StateExtractor.from_runtime_packet(packet)
        if state is None:
            self.last_error = "INSUFFICIENT_STATE"
            return None
        return self.plan(
            state,
            rule_profile=rule_profile,
            top_n=top_n,
            target_ball_number=target_ball_number,
            max_bounces=max_bounces,
            combo_depth=combo_depth,
            selected_route_id=selected_route_id,
        )

    @staticmethod
    def _round_point(point: Any, step: int = 28) -> tuple[int, int]:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return (0, 0)
        return (
            int(round(float(point[0]) / step) * step),
            int(round(float(point[1]) / step) * step),
        )

    @classmethod
    def _geometry_signature(cls, route: Any) -> tuple[Any, ...]:
        segments = []
        for segment in getattr(route, "route_segments", []) or []:
            if not isinstance(segment, dict):
                continue
            points = tuple(cls._round_point(point) for point in segment.get("points", []))
            segments.append((segment.get("type"), points))
        return tuple(segments)

    @staticmethod
    def _route_signature(route: Any) -> tuple[Any, ...]:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        if route.route_type == "combo":
            return (
                "combo",
                route.first_contact_ball_number,
                metadata.get("combo_second_ball_number"),
                RoutePlanner._geometry_signature(route),
            )
        if route.route_type == "bank":
            return (
                "bank",
                route.first_contact_ball_number,
                metadata.get("rail"),
                RoutePlanner._geometry_signature(route),
            )
        if route.route_type in {"kick_escape", "safe_escape", "contact_only"}:
            return (
                route.route_type,
                route.first_contact_ball_number,
                metadata.get("rail"),
                metadata.get("kick_bounces"),
            )
        return (
            route.route_type,
            route.first_contact_ball_number,
            RoutePlanner._geometry_signature(route),
        )

    @classmethod
    def _dedupe_routes(cls, routes: list[Any]) -> list[Any]:
        seen: set[tuple[Any, ...]] = set()
        result = []
        for route in routes:
            signature = cls._route_signature(route)
            if signature in seen:
                continue
            seen.add(signature)
            result.append(route)
        return result

    @staticmethod
    def _route_class(route: Any) -> str:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        route_class = metadata.get("route_class")
        if isinstance(route_class, str) and route_class:
            return route_class
        if route.route_type in {"safe_escape", "contact_only", "kick_escape"}:
            return "contact_only" if route.route_type == "kick_escape" else route.route_type
        return "potting_route"

    @classmethod
    def _diversity_key(cls, route: Any) -> tuple[Any, ...]:
        metadata = route.metadata if isinstance(route.metadata, dict) else {}
        route_class = cls._route_class(route)
        if route_class in {"safe_escape", "contact_only"}:
            return (route_class, route.first_contact_ball_number, metadata.get("rail"), metadata.get("kick_bounces"))
        if route.route_type == "combo":
            return (route_class, route.route_type, route.first_contact_ball_number, metadata.get("combo_second_ball_number"))
        if route.route_type in {"bank", "kick"}:
            return (route_class, route.route_type, route.first_contact_ball_number, metadata.get("rail"))
        return (route_class, route.route_type, route.first_contact_ball_number)

    @classmethod
    def _select_diverse_routes(cls, routes: list[Any], top_n: int) -> list[Any]:
        if not routes:
            return []

        selected: list[Any] = [routes[0]]
        selected_ids = {routes[0].id}
        selected_keys = {cls._diversity_key(routes[0])}
        class_limits = {"safe_escape": 2, "contact_only": 1}
        class_counts: dict[str, int] = {cls._route_class(routes[0]): 1}

        for route in routes[1:]:
            if len(selected) >= top_n:
                break
            route_class = cls._route_class(route)
            if class_counts.get(route_class, 0) >= class_limits.get(route_class, top_n):
                continue
            key = cls._diversity_key(route)
            if key in selected_keys:
                continue
            selected.append(route)
            selected_ids.add(route.id)
            selected_keys.add(key)
            class_counts[route_class] = class_counts.get(route_class, 0) + 1

        for route in routes:
            if len(selected) >= top_n:
                break
            if route.id in selected_ids:
                continue
            route_class = cls._route_class(route)
            if class_counts.get(route_class, 0) >= class_limits.get(route_class, top_n):
                continue
            selected.append(route)
            selected_ids.add(route.id)
            class_counts[route_class] = class_counts.get(route_class, 0) + 1

        return selected

    @staticmethod
    def _build_coach_notes(routes: list[Any], rule_profile: str) -> list[str]:
        if not routes:
            return ["目前沒有可行建議。"]
        best = routes[0]
        notes = [
            f"最佳路線：{best.route_type}，成功率 {round(best.success_prob * 100)}%，難度 {best.difficulty_level}。",
            f"建議桿法：{best.stroke_hint.type} / {best.stroke_hint.spin} / 力道 {best.stroke_hint.power}。",
        ]
        if rule_profile == "9ball":
            notes.append("9-ball 模式會優先檢查首碰合法球，避免犯規。")
        else:
            notes.append("practice 模式會以桌面最小球號作為第一目標，並保留教學性球型供訓練。")
        return notes

    @staticmethod
    def _default_target_ball_number(state: PlannerState) -> Optional[int]:
        numbers = [
            ball.number
            for ball in state.object_balls
            if isinstance(ball.number, int) and ball.number > 0
        ]
        return min(numbers) if numbers else None
