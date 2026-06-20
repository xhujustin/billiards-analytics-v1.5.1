from __future__ import annotations

import json
import time
from typing import Any, Optional

from .candidate_generator import CandidateGenerator
from .lookahead_planner import LookaheadPlanner
from .models import MultiRoutePlan, PlannerState
from .physics_validator import PhysicsValidator
from .position_planner import PositionPlanner
from .route_scorer import RouteScorer
from .shot_simulator import ShotSimulator
from .state_extractor import StateExtractor
from .state_evaluator import StateEvaluator


class RoutePlanner:
    def __init__(
        self,
        shot_simulator: Optional[ShotSimulator] = None,
        state_evaluator: Optional[StateEvaluator] = None,
    ):
        self.validator = PhysicsValidator()
        self.generator = CandidateGenerator(self.validator)
        self.scorer = RouteScorer()
        self.position_planner = PositionPlanner()
        self.shot_simulator = shot_simulator or ShotSimulator()
        self.state_evaluator = state_evaluator or StateEvaluator()
        self.lookahead_planner = LookaheadPlanner(
            simulator=self.shot_simulator,
            evaluator=self.state_evaluator,
            score_weight=0.25,
        )
        self.lookahead_enabled = False
        self.lookahead_ply = 2
        self.lookahead_candidate_count = 5
        self.lookahead_next_top_n = 3
        self.lookahead_score_weight = 0.25
        self.last_plan: Optional[dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self._held_target_number: Optional[int] = None
        self._held_target_miss_frames = 0
        self._target_hold_max_frames = 5
        self._route_switch_margin = 0.12
        self._state_hash_quant_px = 16
        self._last_state_hash: Optional[tuple[Any, ...]] = None
        self._last_state_hash_plan: Optional[dict[str, Any]] = None

    def plan(
        self,
        state: PlannerState,
        rule_profile: str = "practice",
        top_n: int = 5,
        target_ball_number: Optional[int] = None,
        max_bounces: int = 2,
        combo_depth: int = 2,
        selected_route_id: Optional[str] = None,
        stroke_override: Optional[dict[str, Any]] = None,
        lookahead_enabled: Optional[bool] = None,
        lookahead_ply: int = 2,
        lookahead_candidate_count: int = 5,
        lookahead_next_top_n: int = 3,
        lookahead_score_weight: float = 0.25,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        top_n = max(1, min(10, int(top_n)))
        resolved_lookahead_enabled = self.lookahead_enabled if lookahead_enabled is None else bool(lookahead_enabled)
        lookahead_ply = max(1, min(2, int(lookahead_ply or self.lookahead_ply)))
        lookahead_candidate_count = max(1, min(10, int(lookahead_candidate_count or self.lookahead_candidate_count)))
        lookahead_next_top_n = max(1, min(5, int(lookahead_next_top_n or self.lookahead_next_top_n)))
        lookahead_score_weight = max(0.0, min(0.75, float(lookahead_score_weight)))
        try:
            if target_ball_number is None:
                target_ball_number = self._resolve_target_ball_number(state)
            else:
                self._held_target_number = target_ball_number
                self._held_target_miss_frames = 0

            state_hash = self._state_hash(
                state,
                rule_profile=rule_profile,
                target_ball_number=target_ball_number,
                max_bounces=max_bounces,
                combo_depth=combo_depth,
                stroke_override=stroke_override,
                lookahead_enabled=resolved_lookahead_enabled,
                lookahead_ply=lookahead_ply,
                lookahead_candidate_count=lookahead_candidate_count,
                lookahead_next_top_n=lookahead_next_top_n,
                lookahead_score_weight=lookahead_score_weight,
            )
            if selected_route_id is None:
                cached_plan = self._cached_plan_for_state(state_hash, t0)
                if cached_plan is not None:
                    return cached_plan

            candidates = self.generator.generate(
                state,
                max_bounces=max_bounces,
                combo_depth=combo_depth,
                stroke_override=stroke_override,
            )
            if not candidates:
                held_plan = self._held_last_plan(t0, "NO_POTTING_ROUTE_HELD")
                if held_plan is not None:
                    self._store_state_cache(state_hash, held_plan)
                    return held_plan
                plan = MultiRoutePlan(
                    rule_profile=rule_profile,
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                    routes=[],
                    coach_notes=["目前沒有可行進球線，建議先調整母球站位或改走解球。"],
                    fallback_used=False,
                    error="NO_POTTING_ROUTE",
                ).to_dict()
                self._attach_rule_state(plan, state, target_ball_number, state_hash)
                self.last_plan = plan
                self.last_error = "NO_POTTING_ROUTE"
                self._store_state_cache(state_hash, plan)
                return plan

            # 先套用目標球規則再排序，避免可行但較難的 1 號球被粗篩提前排除。
            scored = [
                self.scorer.score(c, rule_profile=rule_profile, target_ball_number=target_ball_number)
                for c in candidates
            ]
            all_scored = list(scored)

            legal_target_routes = []
            if target_ball_number is not None:
                legal_target_routes = [
                    route for route in scored if route.first_contact_ball_number == target_ball_number
                ]
                if legal_target_routes:
                    scored = legal_target_routes
                else:
                    held_plan = self._held_last_plan(t0, "TARGET_TEMPORARILY_MISSING")
                    if held_plan is not None:
                        self._store_state_cache(state_hash, held_plan)
                        return held_plan
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
                    self._attach_rule_state(plan, state, target_ball_number, state_hash)
                    self.last_plan = plan
                    self.last_error = "TARGET_BLOCKED_NO_LEGAL_ROUTE"
                    self._store_state_cache(state_hash, plan)
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
            if rule_profile == "practice" and len(final_routes) < top_n:
                final_routes = self._backfill_practice_teaching_routes(
                    final_routes,
                    all_scored,
                    top_n,
                )
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
                self._attach_rule_state(plan, state, target_ball_number, state_hash)
                self.last_plan = plan
                self.last_error = error_code
                self._store_state_cache(state_hash, plan)
                return plan

            selected_route = None
            if selected_route_id:
                selected_route = next((route for route in deduped if route.id == selected_route_id), None)
                if selected_route is None:
                    selected_route = self._match_previous_selected_route(deduped)

            self._attach_position_play(
                state,
                final_routes,
                rule_profile=rule_profile,
                target_ball_number=target_ball_number,
            )
            self._apply_position_play_scores(final_routes, rule_profile=rule_profile)
            final_routes.sort(key=lambda route: route.score, reverse=True)
            if resolved_lookahead_enabled:
                self._attach_lookahead(
                    state,
                    final_routes[:lookahead_candidate_count],
                    rule_profile=rule_profile,
                    target_ball_number=target_ball_number,
                    max_bounces=max_bounces,
                    combo_depth=combo_depth,
                    lookahead_ply=lookahead_ply,
                    lookahead_next_top_n=lookahead_next_top_n,
                    lookahead_score_weight=lookahead_score_weight,
                )
                final_routes.sort(key=lambda route: route.score, reverse=True)
            if selected_route_id is None:
                selected_route = self._stable_previous_route(final_routes, deduped)
                if selected_route is not None and selected_route.id != final_routes[0].id:
                    final_routes = self._promote_route(final_routes, selected_route, top_n)
                else:
                    near_pocket_route = self._near_pocket_attack_route(final_routes)
                    if near_pocket_route is not None and near_pocket_route.id != final_routes[0].id:
                        final_routes = self._promote_route(final_routes, near_pocket_route, top_n)
            coach_notes = self._build_coach_notes(final_routes, rule_profile)
            plan = MultiRoutePlan(
                rule_profile=rule_profile,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                routes=final_routes,
                coach_notes=coach_notes,
                fallback_used=False,
            ).to_dict()
            if selected_route is not None:
                if selected_route.position_play is None and self._route_class(selected_route) == "potting_route":
                    selected_route.position_play = self.position_planner.plan(
                        state,
                        selected_route,
                        rule_profile=rule_profile,
                        target_ball_number=target_ball_number,
                    )
                self.scorer.blend_position_play_score(
                    selected_route,
                    rule_profile=rule_profile,
                    scoring_mode=rule_profile,
                )
                plan["best_route"] = selected_route.to_dict()
                plan["selected_route_id"] = selected_route.id
            self._attach_rule_state(plan, state, target_ball_number, state_hash)
            self.last_plan = plan
            self.last_error = None
            self._store_state_cache(state_hash, plan)
            best_route = plan.get("best_route")
            if isinstance(best_route, dict) and isinstance(best_route.get("target_ball_number"), int):
                self._held_target_number = best_route["target_ball_number"]
                self._held_target_miss_frames = 0
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
        stroke_override: Optional[dict[str, Any]] = None,
        lookahead_enabled: Optional[bool] = None,
        lookahead_ply: int = 2,
        lookahead_candidate_count: int = 5,
        lookahead_next_top_n: int = 3,
        lookahead_score_weight: float = 0.25,
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
            stroke_override=stroke_override,
            lookahead_enabled=lookahead_enabled,
            lookahead_ply=lookahead_ply,
            lookahead_candidate_count=lookahead_candidate_count,
            lookahead_next_top_n=lookahead_next_top_n,
            lookahead_score_weight=lookahead_score_weight,
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
        if isinstance(route, dict):
            metadata = route.get("metadata") if isinstance(route.get("metadata"), dict) else {}
            route_type = route.get("route_type")
        else:
            metadata = route.metadata if isinstance(route.metadata, dict) else {}
            route_type = route.route_type
        route_class = metadata.get("route_class")
        if isinstance(route_class, str) and route_class:
            return route_class
        if route_type in {"safe_escape", "contact_only", "kick_escape"}:
            return "contact_only" if route_type == "kick_escape" else route_type
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

    @classmethod
    def _backfill_practice_teaching_routes(
        cls,
        selected_routes: list[Any],
        all_routes: list[Any],
        top_n: int,
    ) -> list[Any]:
        """practice 模式保留教學候選，避免 Top-N 只剩單一合法目標球路線。"""
        selected = list(selected_routes)
        selected_ids = {route.id for route in selected}
        selected_keys = {cls._diversity_key(route) for route in selected}
        pool = cls._dedupe_routes(sorted(all_routes, key=lambda route: route.score, reverse=True))

        for route in pool:
            if len(selected) >= top_n:
                break
            if route.id in selected_ids:
                continue
            key = cls._diversity_key(route)
            if key in selected_keys:
                continue
            metadata = route.metadata if isinstance(route.metadata, dict) else {}
            route.metadata = metadata
            metadata["practice_teaching_alternative"] = True
            metadata.setdefault("strategy_label", route.route_type)
            selected.append(route)
            selected_ids.add(route.id)
            selected_keys.add(key)

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

    def _resolve_target_ball_number(self, state: PlannerState) -> Optional[int]:
        default_target = self._default_target_ball_number(state)
        numbers = {
            ball.number
            for ball in state.object_balls
            if isinstance(ball.number, int) and ball.number > 0
        }
        held = self._held_target_number

        if held is None:
            self._held_target_number = default_target
            self._held_target_miss_frames = 0
            return default_target

        if held in numbers:
            if default_target is not None and default_target < held:
                self._held_target_number = default_target
                self._held_target_miss_frames = 0
                return default_target
            self._held_target_miss_frames = 0
            return held

        if default_target is None and self._held_target_miss_frames < self._target_hold_max_frames:
            self._held_target_miss_frames += 1
            return held

        if default_target is not None and held < default_target and self._held_target_miss_frames < self._target_hold_max_frames:
            self._held_target_miss_frames += 1
            return held

        self._held_target_number = default_target
        self._held_target_miss_frames = 0
        return default_target

    def _held_last_plan(self, t0: float, error: str) -> Optional[dict[str, Any]]:
        if self._held_target_miss_frames <= 0 or self._held_target_miss_frames > self._target_hold_max_frames:
            return None
        if not isinstance(self.last_plan, dict) or not isinstance(self.last_plan.get("best_route"), dict):
            return None
        plan = dict(self.last_plan)
        plan["latency_ms"] = round(float((time.perf_counter() - t0) * 1000.0), 2)
        plan["error"] = error
        notes = list(plan.get("coach_notes") or [])
        notes.insert(0, "目標球偵測短暫不穩，暫時沿用上一條路線避免畫面跳動。")
        plan["coach_notes"] = notes[:4]
        plan["hysteresis_hold"] = True
        self.last_plan = plan
        self.last_error = error
        return plan

    def _stable_previous_route(self, final_routes: list[Any], deduped: list[Any]) -> Optional[Any]:
        if not final_routes or not isinstance(self.last_plan, dict):
            return None
        prev = self.last_plan.get("best_route")
        if not isinstance(prev, dict):
            return None
        prev_id = prev.get("id")
        prev_target = prev.get("target_ball_number")
        if not prev_id or prev_target != final_routes[0].target_ball_number:
            return None

        candidate = next((route for route in deduped if route.id == prev_id), None)
        if candidate is None:
            return None

        current_best = final_routes[0]
        if current_best.id == candidate.id:
            return None
        score_gap = float(current_best.score) - float(candidate.score)
        if score_gap <= self._route_switch_margin:
            return candidate
        return None

    def _match_previous_selected_route(self, routes: list[Any]) -> Optional[Any]:
        if not isinstance(self.last_plan, dict):
            return None
        prev = self.last_plan.get("best_route")
        if not isinstance(prev, dict):
            return None
        previous_intent = self._route_intent_key(prev)
        for route in routes:
            if self._route_intent_key(route) == previous_intent:
                return route
        return None

    @classmethod
    def _route_intent_key(cls, route: Any) -> tuple[Any, ...]:
        if isinstance(route, dict):
            metadata = route.get("metadata") if isinstance(route.get("metadata"), dict) else {}
            return (
                cls._route_class(route),
                route.get("route_type"),
                route.get("target_ball_number"),
                route.get("first_contact_ball_number"),
                metadata.get("combo_second_ball_number"),
                metadata.get("target_pocket_id"),
                metadata.get("rail"),
                metadata.get("kick_bounces"),
                cls._route_terminal_bucket(route),
            )

        metadata = route.metadata if isinstance(getattr(route, "metadata", None), dict) else {}
        return (
            cls._route_class(route),
            getattr(route, "route_type", None),
            getattr(route, "target_ball_number", None),
            getattr(route, "first_contact_ball_number", None),
            metadata.get("combo_second_ball_number"),
            metadata.get("target_pocket_id"),
            metadata.get("rail"),
            metadata.get("kick_bounces"),
            cls._route_terminal_bucket(route),
        )

    @staticmethod
    def _route_terminal_bucket(route: Any) -> Optional[tuple[int, int]]:
        path_points = route.get("path_points") if isinstance(route, dict) else getattr(route, "path_points", None)
        if isinstance(path_points, list) and path_points:
            point = path_points[-1]
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                try:
                    return (round(float(point[0]) / 24.0), round(float(point[1]) / 24.0))
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _promote_route(routes: list[Any], route: Any, top_n: int) -> list[Any]:
        promoted = [route]
        seen = {route.id}
        for item in routes:
            if item.id in seen:
                continue
            promoted.append(item)
            seen.add(item.id)
            if len(promoted) >= top_n:
                break
        return promoted

    @staticmethod
    def _near_pocket_attack_route(routes: list[Any]) -> Optional[Any]:
        direct_routes = []
        for route in routes:
            if route.route_type not in {"straight", "cut"}:
                continue
            metadata = route.metadata if isinstance(route.metadata, dict) else {}
            if metadata.get("route_class") != "potting_route":
                continue
            try:
                object_to_pocket = float(metadata.get("object_to_pocket_distance"))
            except (TypeError, ValueError):
                continue
            direct_routes.append((object_to_pocket, route))

        if len(direct_routes) < 2:
            return None

        direct_routes.sort(key=lambda item: item[0])
        nearest_distance, nearest_route = direct_routes[0]
        current_best_distance = next(
            (distance for distance, route in direct_routes if route.id == routes[0].id),
            None,
        )
        if current_best_distance is None:
            return None
        if nearest_route.id == routes[0].id:
            return None
        if nearest_distance > 120.0:
            return None
        if current_best_distance < nearest_distance * 1.8:
            return None
        if float(nearest_route.cut_angle) > 75.0:
            return None

        metadata = nearest_route.metadata if isinstance(nearest_route.metadata, dict) else {}
        nearest_route.metadata = metadata
        metadata["near_pocket_attack_promoted"] = True
        metadata["near_pocket_reason"] = "short_direct_pocket_available"
        return nearest_route

    def _attach_position_play(
        self,
        state: PlannerState,
        routes: list[Any],
        rule_profile: str,
        target_ball_number: Optional[int],
    ) -> None:
        for route in routes:
            if self._route_class(route) != "potting_route":
                route.position_play = None
                continue
            route.position_play = self.position_planner.plan(
                state,
                route,
                rule_profile=rule_profile,
                target_ball_number=target_ball_number,
            )

    def _apply_position_play_scores(self, routes: list[Any], rule_profile: str) -> None:
        for route in routes:
            self.scorer.blend_position_play_score(
                route,
                rule_profile=rule_profile,
                scoring_mode=rule_profile,
            )

    def _attach_lookahead(
        self,
        state: PlannerState,
        routes: list[Any],
        rule_profile: str,
        target_ball_number: Optional[int],
        max_bounces: int,
        combo_depth: int,
        lookahead_ply: int,
        lookahead_next_top_n: int,
        lookahead_score_weight: float,
    ) -> None:
        self.lookahead_planner.depth = lookahead_ply
        self.lookahead_planner.evaluate_routes(
            state,
            routes,
            rule_profile=rule_profile,
            target_ball_number=target_ball_number,
            next_top_n=lookahead_next_top_n,
            score_weight=lookahead_score_weight,
            next_route_provider=lambda next_state, next_rule_profile, next_target, next_top_n: self._lookahead_next_routes(
                next_state,
                next_rule_profile,
                next_target,
                next_top_n,
                max_bounces=max_bounces,
                combo_depth=combo_depth,
            ),
        )

    def _lookahead_next_routes(
        self,
        state: PlannerState,
        rule_profile: str,
        target_ball_number: Optional[int],
        top_n: int,
        max_bounces: int,
        combo_depth: int,
    ) -> list[Any]:
        if not isinstance(state, PlannerState):
            return []
        candidates = self.generator.generate(
            state,
            max_bounces=max_bounces,
            combo_depth=combo_depth,
            stroke_override=None,
        )
        scored = [
            self.scorer.score(route, rule_profile=rule_profile, target_ball_number=target_ball_number)
            for route in candidates
        ]
        if target_ball_number is not None:
            legal = [route for route in scored if route.first_contact_ball_number == target_ball_number]
            if legal:
                scored = legal
        scored.sort(key=lambda route: route.score, reverse=True)
        deduped = self._dedupe_routes(scored)
        routes = self._select_diverse_routes(deduped, top_n)
        self._attach_position_play(
            state,
            routes,
            rule_profile=rule_profile,
            target_ball_number=target_ball_number,
        )
        self._apply_position_play_scores(routes, rule_profile=rule_profile)
        routes.sort(key=lambda route: route.score, reverse=True)
        return routes[:top_n]

    def _cached_plan_for_state(self, state_hash: tuple[Any, ...], t0: float) -> Optional[dict[str, Any]]:
        if state_hash != self._last_state_hash or not isinstance(self._last_state_hash_plan, dict):
            return None
        plan = dict(self._last_state_hash_plan)
        plan["latency_ms"] = round(float((time.perf_counter() - t0) * 1000.0), 2)
        plan["state_hash_reused"] = True
        self.last_plan = plan
        self.last_error = plan.get("error")
        return plan

    def _store_state_cache(self, state_hash: tuple[Any, ...], plan: dict[str, Any]) -> None:
        self._last_state_hash = state_hash
        self._last_state_hash_plan = dict(plan)

    def _state_hash(
        self,
        state: PlannerState,
        rule_profile: str,
        target_ball_number: Optional[int],
        max_bounces: int,
        combo_depth: int,
        stroke_override: Optional[dict[str, Any]] = None,
        lookahead_enabled: bool = False,
        lookahead_ply: int = 2,
        lookahead_candidate_count: int = 5,
        lookahead_next_top_n: int = 3,
        lookahead_score_weight: float = 0.25,
    ) -> tuple[Any, ...]:
        q = max(4, int(self._state_hash_quant_px))

        def quant(value: float) -> int:
            return int(float(value) // q)

        cue = (
            quant(state.cue_ball.center[0]),
            quant(state.cue_ball.center[1]),
            quant(state.cue_ball.radius),
        )
        balls = tuple(
            sorted(
                (
                    int(ball.number) if isinstance(ball.number, int) else -1,
                    quant(ball.center[0]),
                    quant(ball.center[1]),
                    quant(ball.radius),
                )
                for ball in state.object_balls
            )
        )
        table = tuple(quant(value) for value in state.table_roi)
        return (
            rule_profile,
            target_ball_number,
            int(max_bounces),
            int(combo_depth),
            self._stroke_override_signature(stroke_override),
            (
                bool(lookahead_enabled),
                int(lookahead_ply),
                int(lookahead_candidate_count),
                int(lookahead_next_top_n),
                round(float(lookahead_score_weight), 3),
            ),
            cue,
            balls,
            table,
        )

    @staticmethod
    def _stroke_override_signature(stroke_override: Optional[dict[str, Any]]) -> tuple[str, str, str, str, str]:
        if not isinstance(stroke_override, dict):
            return ("auto", "auto", "auto", "auto", "auto")
        return (
            str(stroke_override.get("tip", "center")),
            str(stroke_override.get("power", "medium")),
            str(stroke_override.get("power_percent", "auto")),
            str(stroke_override.get("tip_x", "auto")),
            str(stroke_override.get("tip_y", "auto")),
        )

    @staticmethod
    def _rule_state(state: PlannerState, target_ball_number: Optional[int]) -> dict[str, Any]:
        remaining = sorted(
            {
                int(ball.number)
                for ball in state.object_balls
                if isinstance(ball.number, int) and ball.number > 0
            }
        )
        return {
            "remaining_ball_numbers": remaining,
            "legal_target_ball_number": target_ball_number,
            "first_contact_required": target_ball_number,
        }

    def _attach_rule_state(
        self,
        plan: dict[str, Any],
        state: PlannerState,
        target_ball_number: Optional[int],
        state_hash: Optional[tuple[Any, ...]] = None,
    ) -> None:
        plan["rule_state"] = self._rule_state(state, target_ball_number)
        if state_hash is not None:
            plan["state_signature"] = self._state_signature(state_hash)

    @staticmethod
    def _state_signature(state_hash: tuple[Any, ...]) -> str:
        return json.dumps(state_hash, ensure_ascii=True, separators=(",", ":"), default=str)

    @staticmethod
    def _default_target_ball_number(state: PlannerState) -> Optional[int]:
        numbers = [
            ball.number
            for ball in state.object_balls
            if isinstance(ball.number, int) and ball.number > 0
        ]
        return min(numbers) if numbers else None
