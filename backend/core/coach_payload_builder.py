from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any


class CoachPayloadBuilder:
    """Build the stable coach.context.v1 payload shared by coach APIs."""

    SCHEMA_VERSION = "coach.context.v1"

    def __init__(self) -> None:
        self._latest_payload: dict[str, Any] | None = None

    def build(
        self,
        *,
        request_type: str,
        message: str | None = None,
        intent: str | None = None,
        response_mode: str | None = None,
        runtime_packet: dict[str, Any] | None = None,
        semantic_context: dict[str, Any] | None = None,
        multi_plan: Any = None,
        ai_coach: Any = None,
        system_status: dict[str, Any] | None = None,
        shot_event: dict[str, Any] | None = None,
        ui_context: dict[str, Any] | None = None,
        analytics_context: dict[str, Any] | None = None,
        provided_context: dict[str, Any] | None = None,
        frame_id: int | None = None,
        ts_backend: int | None = None,
    ) -> dict[str, Any]:
        runtime_packet = runtime_packet if isinstance(runtime_packet, dict) else {}
        semantic_context = semantic_context if isinstance(semantic_context, dict) else {}
        system_status = system_status if isinstance(system_status, dict) else {}
        shot_event = shot_event if isinstance(shot_event, dict) else {}
        ui_context = ui_context if isinstance(ui_context, dict) else {}
        analytics_context = analytics_context if isinstance(analytics_context, dict) else {}
        multi_plan = self._resolve_multi_plan(multi_plan, runtime_packet, provided_context)
        best_route = self._extract_best_route(multi_plan)
        position_play = self._extract_position_play(best_route, multi_plan)
        table_state = self._build_table_state(runtime_packet, semantic_context)

        request_payload = {
            "type": request_type,
            "message": message,
            "intent": intent,
            "response_mode": response_mode,
            "frame_id": frame_id if frame_id is not None else runtime_packet.get("frame_count"),
            "ts_backend": ts_backend,
            "provided_context_keys": sorted(provided_context.keys()) if isinstance(provided_context, dict) else [],
        }

        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "request": self._json_safe(request_payload),
            "table_state": self._json_safe(table_state),
            "semantic_context": self._json_safe(semantic_context),
            "system_status": self._json_safe(system_status),
            "shot_event": self._json_safe(shot_event),
            "ui_context": self._json_safe(ui_context),
            "analytics_context": self._json_safe(analytics_context),
            "runtime": {
                "balls": self._json_safe(runtime_packet.get("balls", [])),
                "table": self._json_safe(self._build_runtime_table(runtime_packet, semantic_context)),
            },
            "planner": {
                "result": self._json_safe(multi_plan),
                "best_route": self._json_safe(best_route),
                "position_play": self._json_safe(position_play),
            },
            "debug": {
                "signature": "",
                "raw_detections": self._json_safe(runtime_packet.get("balls", [])),
                "packet_status": runtime_packet.get("status"),
                "built_at": datetime.now().isoformat(),
            },
        }
        if ai_coach is not None:
            payload["ai_coach"] = self._json_safe(ai_coach)

        signature = self.signature(payload)
        payload["debug"]["signature"] = signature

        # Compatibility aliases for older AI Coach prompts that read context.* directly.
        payload["intent"] = intent
        payload["table_context_available"] = bool(
            semantic_context.get("valid") and semantic_context.get("stable")
        )
        payload["balls"] = payload["runtime"]["balls"]
        payload["multi_plan"] = payload["planner"]["result"]

        self._latest_payload = deepcopy(payload)
        return deepcopy(payload)

    def latest(self) -> dict[str, Any] | None:
        return deepcopy(self._latest_payload) if isinstance(self._latest_payload, dict) else None

    def signature(self, payload: dict[str, Any]) -> str:
        stable_payload = {
            "schema_version": payload.get("schema_version"),
            "request": {
                "type": (payload.get("request") or {}).get("type"),
                "intent": (payload.get("request") or {}).get("intent"),
                "response_mode": (payload.get("request") or {}).get("response_mode"),
            },
            "table_state": payload.get("table_state"),
            "semantic_context": self._semantic_signature_part(payload.get("semantic_context")),
            "planner": self._planner_signature_part(payload.get("planner")),
            "system_status": self._system_status_signature_part(payload.get("system_status")),
            "shot_event": self._shot_event_signature_part(payload.get("shot_event")),
        }
        encoded = json.dumps(
            stable_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _build_table_state(self, runtime_packet: dict[str, Any], semantic_context: dict[str, Any]) -> dict[str, Any]:
        return {
            "coordinate_space": semantic_context.get("coordinate_space") or "original_camera_frame",
            "table": semantic_context.get("table"),
            "cue_ball": semantic_context.get("cue_ball"),
            "balls": semantic_context.get("balls") if semantic_context.get("balls") is not None else runtime_packet.get("balls", []),
            "runtime_table": self._build_runtime_table(runtime_packet, semantic_context),
            "runtime_white_ball": runtime_packet.get("white_ball"),
            "status": runtime_packet.get("status"),
            "frame_count": runtime_packet.get("frame_count"),
        }

    def _build_runtime_table(self, runtime_packet: dict[str, Any], semantic_context: dict[str, Any]) -> dict[str, Any]:
        table_payload = {}
        if isinstance(semantic_context.get("table"), dict):
            table_payload.update(semantic_context["table"])
        for key in ("table_roi", "table_polygon", "table_color", "roi_points"):
            if runtime_packet.get(key) is not None:
                table_payload[key] = runtime_packet.get(key)
        return table_payload

    def _resolve_multi_plan(self, multi_plan: Any, runtime_packet: dict[str, Any], provided_context: dict[str, Any] | None) -> Any:
        if multi_plan is not None:
            return multi_plan
        return runtime_packet.get("multi_plan")

    def _extract_best_route(self, multi_plan: Any) -> Any:
        if not isinstance(multi_plan, dict):
            return None
        for key in ("best_route", "best_plan", "best"):
            value = multi_plan.get(key)
            if isinstance(value, dict):
                return value
        return None

    def _extract_position_play(self, best_route: Any, multi_plan: Any) -> Any:
        if isinstance(best_route, dict):
            for key in ("position_play", "position", "shape_play"):
                value = best_route.get(key)
                if isinstance(value, dict):
                    return value
            metadata = best_route.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("position_play"), dict):
                return metadata.get("position_play")
        if isinstance(multi_plan, dict) and isinstance(multi_plan.get("position_play"), dict):
            return multi_plan.get("position_play")
        return None

    def _semantic_signature_part(self, semantic_context: Any) -> dict[str, Any]:
        if not isinstance(semantic_context, dict):
            return {}
        balls = []
        for ball in semantic_context.get("balls", []) or []:
            if not isinstance(ball, dict):
                continue
            nearest_pocket = ball.get("nearest_pocket") if isinstance(ball.get("nearest_pocket"), dict) else {}
            balls.append(
                {
                    "id": ball.get("id"),
                    "number": ball.get("number"),
                    "center": self._round_point(ball.get("center")),
                    "nearest_pocket": nearest_pocket.get("name"),
                    "path_clear": nearest_pocket.get("path_clear"),
                    "cue_path_clear": ball.get("cue_path_clear"),
                }
            )
        cue_ball = semantic_context.get("cue_ball") if isinstance(semantic_context.get("cue_ball"), dict) else {}
        return {
            "valid": semantic_context.get("valid"),
            "stable": semantic_context.get("stable"),
            "stable_ball_count": semantic_context.get("stable_ball_count"),
            "cue_center": self._round_point(cue_ball.get("center")),
            "balls": balls,
            "rules": semantic_context.get("rules"),
        }

    def _planner_signature_part(self, planner: Any) -> dict[str, Any]:
        if not isinstance(planner, dict):
            return {}
        best_route = planner.get("best_route") if isinstance(planner.get("best_route"), dict) else {}
        success_prob = best_route.get("success_prob")
        try:
            success_prob = round(float(success_prob), 2) if success_prob is not None else None
        except (TypeError, ValueError):
            success_prob = None
        return {
            "route_type": best_route.get("route_type"),
            "target_ball_number": best_route.get("target_ball_number"),
            "success_prob": success_prob,
            "position_play": planner.get("position_play"),
        }

    def _system_status_signature_part(self, system_status: Any) -> dict[str, Any]:
        if not isinstance(system_status, dict):
            return {}
        fps = system_status.get("fps")
        try:
            fps = round(float(fps), 1) if fps is not None else None
        except (TypeError, ValueError):
            fps = None
        return {
            "yolo_status": system_status.get("yolo_status"),
            "fps": fps,
            "roi_status": system_status.get("roi_status"),
            "balls_outside_roi": system_status.get("balls_outside_roi"),
            "lighting_status": system_status.get("lighting_status"),
        }

    def _shot_event_signature_part(self, shot_event: Any) -> dict[str, Any]:
        if not isinstance(shot_event, dict):
            return {}
        return {
            "event_id": shot_event.get("event_id"),
            "pocket_result": shot_event.get("pocket_result"),
            "first_contact": shot_event.get("first_contact"),
            "potted_balls": shot_event.get("potted_balls"),
            "cue_ball_potted": shot_event.get("cue_ball_potted"),
        }

    def _round_point(self, point: Any, grid: float = 12.0) -> list[float] | None:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        try:
            return [
                round(float(point[0]) / grid) * grid,
                round(float(point[1]) / grid) * grid,
            ]
        except (TypeError, ValueError):
            return None

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if hasattr(value, "tolist"):
            try:
                return self._json_safe(value.tolist())
            except Exception:
                pass
        return str(value)
