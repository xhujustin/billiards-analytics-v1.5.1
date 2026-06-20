"""
投影機獨立渲染器
負責投影機畫面的獨立渲染,不依賴相機畫面
支援多種模式: 待機、校正、遊戲、練習
"""

import json
import cv2
import config
import math
import numpy as np
import time
from enum import Enum
from typing import Optional, Dict, Any, List

class ProjectorMode(Enum):
    """投影機模式"""
    IDLE = "idle"              # 待機 (純黑)
    CALIBRATION = "calibration"  # 校正模式 (ArUco 標記)
    DETECTION = "detection"    # 啟動辨識模式 (球外框)
    GAME = "game"              # 遊戲模式 (AR 疊加)
    PRACTICE = "practice"      # 練習模式 (球外框 + 球形)

class ProjectorRenderer:
    """投影機獨立渲染器"""

    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.mode = ProjectorMode.IDLE  # 預設顯示待機畫面
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

        # 校正模式狀態 (縮小偏移使標記更集中)
        self.calibration_offsets = {
            "top-left": {"x": -280, "y": -280},
            "top-right": {"x": 280, "y": -280},
            "bottom-right": {"x": 280, "y": 280},
            "bottom-left": {"x": -280, "y": 280}
        }

        # AR 疊加資料
        self.ar_data = {
            "trajectories": [],  # 軌跡路徑
            "route_segments": [],  # 多球規劃分段路線
            "balls": [],         # 球位
            "aim_lines": [],      # 瞄準線
            "ghost_balls": [],    # 幽靈球
            "setup_balls": [],    # 球型練習固定球位
            "cue_landing_point": None,
            "cue_landing_zone": None,
            "position_play": None,
            "cue_laser_lines": [],  # 球桿雷射線
            "allow_legacy_aim_lines": False,
            "allow_legacy_trajectories": False,
            "ar_source": "live_yolo",
            "ar_timestamp": 0.0,
            "cue_laser_source": "live_yolo",
            "cue_laser_timestamp": 0.0,
            "table_polygon": [],
            "projector_status": "idle",
            "game_timer": {
                "enabled": False,
                "shot_time_limit": 0,
                "remaining_time": 0,
                "current_player": 1,
                "updated_at": 0.0,
            },
        }

        self._idle_frame_cache: Optional[np.ndarray] = None
        self._idle_frame_cache_key: Optional[tuple[int, int]] = None
        self._calibration_frame_cache: Optional[np.ndarray] = None
        self._calibration_frame_cache_key: Optional[str] = None
        self._setup_balls_layer_cache: Optional[np.ndarray] = None
        self._setup_balls_mask_cache: Optional[np.ndarray] = None
        self._setup_balls_cache_key: Optional[str] = None
        self._static_ar_frame_cache: Optional[np.ndarray] = None
        self._static_ar_frame_cache_key: Optional[str] = None
        self._static_ar_cache_drawn = False
        self._timer_layer_cache: Optional[np.ndarray] = None
        self._timer_mask_cache: Optional[np.ndarray] = None
        self._timer_cache_key: Optional[str] = None
        self._text_size_cache: dict[tuple[str, int, float, int], tuple[int, int]] = {}
        self._render_stage_timings: dict[str, float] = {}
        self._last_render_stage_timings: dict[str, float] = {}
        self._last_render_stats: dict[str, Any] = {}
        self._cache_stats: dict[str, int] = {
            "idle_hits": 0,
            "idle_misses": 0,
            "calibration_hits": 0,
            "calibration_misses": 0,
            "setup_balls_hits": 0,
            "setup_balls_misses": 0,
            "static_ar_hits": 0,
            "static_ar_misses": 0,
            "timer_hits": 0,
            "timer_misses": 0,
        }

    def set_mode(self, mode: ProjectorMode):
        """切換投影機模式"""
        self.mode = mode
        print(f"Projector mode: {mode.value}")

    def render(self) -> np.ndarray:
        """
        根據當前模式渲染投影機畫面

        Returns:
            1920×1080 BGR 影像
        """
        self._render_stage_timings = {}
        render_start = time.perf_counter()
        if self.mode == ProjectorMode.IDLE:
            mode_name = "idle"
            frame = self._render_idle()
        elif self.mode == ProjectorMode.CALIBRATION:
            mode_name = "calibration"
            frame = self._render_calibration()
        elif self.mode == ProjectorMode.DETECTION:
            mode_name = "detection"
            frame = self._render_detection()
        elif self.mode == ProjectorMode.GAME:
            mode_name = "game"
            frame = self._render_game()
        elif self.mode == ProjectorMode.PRACTICE:
            mode_name = "practice"
            frame = self._render_practice()
        else:
            mode_name = "idle"
            frame = self._render_idle()
        self._record_stage(f"projector_render_{mode_name}", time.perf_counter() - render_start)
        self._last_render_stage_timings = dict(self._render_stage_timings)
        self._last_render_stats = {
            "mode": mode_name,
            "width": self.width,
            "height": self.height,
            "stage_latency_ms": {
                name: round(duration * 1000.0, 3)
                for name, duration in self._last_render_stage_timings.items()
            },
            "cache": dict(self._cache_stats),
        }
        return frame

    def get_last_stage_timings(self) -> dict[str, float]:
        """回傳最近一次 render 的分段耗時（秒），供主效能監控記錄。"""
        return dict(self._last_render_stage_timings)

    def get_render_stats(self) -> dict[str, Any]:
        """回傳最近一次 render 的快取與分段診斷資料。"""
        return dict(self._last_render_stats)

    def _record_stage(self, name: str, duration: float) -> None:
        self._render_stage_timings[name] = self._render_stage_timings.get(name, 0.0) + duration

    def _fingerprint(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))

    def _frame_shape_key(self) -> tuple[int, int]:
        return (self.width, self.height)

    def _get_text_size(self, text: str, font: int, scale: float, thickness: int) -> tuple[int, int]:
        key = (text, font, float(scale), int(thickness))
        cached = self._text_size_cache.get(key)
        if cached is not None:
            return cached
        size = cv2.getTextSize(text, font, scale, thickness)[0]
        self._text_size_cache[key] = size
        return size

    def _render_idle(self) -> np.ndarray:
        """待機模式: 純黑畫面"""
        cache_key = self._frame_shape_key()
        if self._idle_frame_cache is not None and self._idle_frame_cache_key == cache_key:
            self._cache_stats["idle_hits"] += 1
            return self._idle_frame_cache.copy()
        self._cache_stats["idle_misses"] += 1

        build_start = time.perf_counter()
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # 顯示提示文字
        text = "NCUT Billiards Analytics System V1.5.2"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = self._get_text_size(text, font, 1.5, 3)
        text_x = (self.width - text_size[0]) // 2
        text_y = (self.height + text_size[1]) // 2
        cv2.putText(frame, text, (text_x, text_y), font, 1.5, (50, 50, 50), 3)

        self._idle_frame_cache = frame
        self._idle_frame_cache_key = cache_key
        self._record_stage("projector_idle_cache_build", time.perf_counter() - build_start)
        return frame.copy()

    def _render_calibration(self) -> np.ndarray:
        """校正模式: ArUco 標記圖案"""
        cache_key = self._fingerprint({
            "size": self._frame_shape_key(),
            "offsets": self.calibration_offsets,
        })
        if self._calibration_frame_cache is not None and self._calibration_frame_cache_key == cache_key:
            self._cache_stats["calibration_hits"] += 1
            return self._calibration_frame_cache.copy()
        self._cache_stats["calibration_misses"] += 1

        build_start = time.perf_counter()
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # 標記大小（縮小，但仍維持相機端每 bit 足夠像素數以利解碼）
        marker_size = 140
        # 白色邊框寬度＝靜默區(quiet zone)。投影到亮檯布 + 相機輕微失焦時，
        # 太薄的白邊會被吃掉、標記黑外圈與檯面糊在一起導致偵測失敗，
        # 故取約 2 個 bit 寬（140/6≈23px → 44px）確保方形輪廓可被分離。
        border_width = 44
        center_x = self.width // 2
        center_y = self.height // 2

        markers_config = [
            (0, "top-left"),
            (1, "top-right"),
            (2, "bottom-right"),
            (3, "bottom-left")
        ]

        position_labels = {
            "top-left": "TL",
            "top-right": "TR",
            "bottom-right": "BR",
            "bottom-left": "BL"
        }

        for marker_id, corner_key in markers_config:
            offset = self.calibration_offsets.get(corner_key, {"x": 0, "y": 0})

            # 計算標記位置（包含邊框）
            total_size = marker_size + border_width * 2
            x = center_x + offset["x"] - total_size // 2
            y = center_y + offset["y"] - total_size // 2

            # 繪製白色背景邊框（增強對比度）
            cv2.rectangle(frame,
                         (x, y),
                         (x + total_size, y + total_size),
                         (255, 255, 255),
                         -1)  # 填充白色

            # 產生 ArUco 標記
            marker = cv2.aruco.generateImageMarker(
                self.aruco_dict,
                marker_id,
                marker_size
            )
            marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)

            # 將標記放在白色背景中心
            marker_x = x + border_width
            marker_y = y + border_width

            # 放置標記
            if 0 <= marker_x < self.width - marker_size and 0 <= marker_y < self.height - marker_size:
                frame[marker_y:marker_y+marker_size, marker_x:marker_x+marker_size] = marker_bgr

            # 繪製位置標籤（黑色，放在白色背景上更清晰）
            label = position_labels[corner_key]
            label_pos = (x + total_size // 2 - 20, y + total_size + 35)
            cv2.putText(frame, label, label_pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)

        self._calibration_frame_cache = frame
        self._calibration_frame_cache_key = cache_key
        self._record_stage("projector_calibration_cache_build", time.perf_counter() - build_start)
        return frame.copy()

    def _render_detection(self) -> np.ndarray:
        """啟動辨識模式: 單純投影球的外框"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # 繪製球位外框 (不填充)
        balls = self.ar_data.get("balls")
        if not isinstance(balls, list):
            balls = []
        for ball in balls:
            if not isinstance(ball, dict):
                continue
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            ball_type = ball.get("type", "unknown")
            color = (255, 255, 255) if ball_type == "cue" else (0, 255, 0)
            cv2.circle(frame, (x, y), 20, color, 2, cv2.LINE_AA)
            if ball.get("number"):
                cv2.putText(frame, str(ball["number"]), (x - 8, y + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return frame

    def _dynamic_ar_is_fresh(self) -> bool:
        source = str(self.ar_data.get("ar_source", "live_yolo"))
        if source == "pattern_static":
            return True

        if source in {"planner_plan", "planner_select_route", "planner_stroke"}:
            max_age_ms = int(
                getattr(
                    config,
                    "PROJECTOR_MANUAL_ROUTE_HOLD_MS",
                    getattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", 5000),
                )
            )
        else:
            max_age_ms = int(getattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", getattr(config, "PROJECTOR_AR_METADATA_MAX_AGE_MS", 160)))
        if max_age_ms <= 0:
            return True

        timestamp = self.ar_data.get("ar_timestamp")
        if not isinstance(timestamp, (int, float)) or timestamp <= 0:
            return False
        return (time.time() - timestamp) * 1000.0 <= max_age_ms

    def _cue_laser_is_fresh(self) -> bool:
        source = str(self.ar_data.get("cue_laser_source", self.ar_data.get("ar_source", "live_yolo")))
        if source == "pattern_static":
            return True

        max_age_ms = int(getattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", getattr(config, "PROJECTOR_AR_METADATA_MAX_AGE_MS", 160)))
        if max_age_ms <= 0:
            return True

        timestamp = self.ar_data.get("cue_laser_timestamp", self.ar_data.get("ar_timestamp"))
        if not isinstance(timestamp, (int, float)) or timestamp <= 0:
            return False
        return (time.time() - timestamp) * 1000.0 <= max_age_ms

    def _draw_zone_marker(
        self,
        frame: np.ndarray,
        zone: Any,
        color: tuple[int, int, int],
        label: str,
        filled: bool = False,
    ) -> bool:
        if not isinstance(zone, dict):
            return False
        center = zone.get("center")
        if not isinstance(center, (list, tuple)) or len(center) < 2:
            return False
        try:
            cx = int(round(float(center[0])))
            cy = int(round(float(center[1])))
            radius = int(round(float(zone.get("radius", 24) or 24)))
        except (TypeError, ValueError):
            return False
        radius = max(8, min(180, radius))
        if filled:
            roi_start = time.perf_counter()
            pad = radius + 4
            x1 = max(0, cx - pad)
            y1 = max(0, cy - pad)
            x2 = min(self.width, cx + pad + 1)
            y2 = min(self.height, cy + pad + 1)
            if x1 < x2 and y1 < y2:
                roi = frame[y1:y2, x1:x2]
                overlay = roi.copy()
                cv2.circle(overlay, (cx - x1, cy - y1), radius, color, -1, cv2.LINE_AA)
                cv2.addWeighted(overlay, 0.18, roi, 0.82, 0, roi)
            self._record_stage("projector_zone_marker_roi_blend", time.perf_counter() - roi_start)
        cv2.circle(frame, (cx, cy), radius, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), radius, color, 3, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 4, color, -1, cv2.LINE_AA)
        if label:
            cv2.putText(
                frame,
                label,
                (cx + radius + 8, cy + 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                4,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                label,
                (cx + radius + 8, cy + 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
        return True

    def _draw_cue_laser_elements(self, frame: np.ndarray) -> bool:
        """繪製即時球桿雷射線，避免被靜態 AR 快取鎖住。"""
        if not self._cue_laser_is_fresh():
            return False

        cue_laser_lines = self.ar_data.get("cue_laser_lines")
        if not isinstance(cue_laser_lines, list):
            cue_laser_lines = []

        def draw_cue_laser(points: List[Any]):
            if len(points) <= 1:
                return
            clean_points = []
            for point in points:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    clean_points.append((int(point[0]), int(point[1])))
            if len(clean_points) <= 1:
                return

            for idx in range(len(clean_points) - 1):
                start = clean_points[idx]
                end = clean_points[idx + 1]
                cv2.line(frame, start, end, (0, 0, 120), 13, cv2.LINE_AA)
                cv2.line(frame, start, end, (0, 30, 255), 7, cv2.LINE_AA)
                cv2.line(frame, start, end, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, clean_points[-1], 7, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, clean_points[-1], 12, (0, 30, 255), 2, cv2.LINE_AA)

        drawn = False
        laser_start = time.perf_counter()
        for laser in cue_laser_lines:
            if isinstance(laser, dict):
                laser_points = laser.get("points")
                if isinstance(laser_points, list):
                    draw_cue_laser(laser_points)
                    drawn = True
        self._record_stage("projector_cue_laser", time.perf_counter() - laser_start)
        return drawn

    def _draw_empty_status(self, frame: np.ndarray, mode_label: str) -> bool:
        """在非 idle 模式無可見 AR 時顯示淡色狀態，避免投影端看起來像斷訊。"""
        if not bool(getattr(config, "PROJECTOR_SHOW_EMPTY_STATUS", True)):
            return False

        status = str(self.ar_data.get("projector_status") or "waiting_for_route")
        messages = {
            "waiting_for_route": "PROJECTOR ACTIVE - NO ROUTE",
            "waiting_for_analysis": "PROJECTOR ACTIVE - WAITING",
            "idle": "PROJECTOR ACTIVE",
        }
        text = messages.get(status, "PROJECTOR ACTIVE")
        subtext = "Need white ball / route / cue laser"
        if status == "waiting_for_analysis":
            subtext = "Waiting for analysis data"

        frame[:, :] = (12, 12, 12)
        polygon = self._get_table_polygon()
        if polygon:
            pts = np.array(polygon[:4], np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(frame, [pts], (24, 24, 24), cv2.LINE_AA)
            cv2.polylines(frame, [pts], True, (110, 110, 110), 4, cv2.LINE_AA)
            for point in polygon[:4]:
                cv2.circle(frame, point, 9, (150, 150, 150), -1, cv2.LINE_AA)

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.82
        thickness = 2
        text_size = self._get_text_size(text, font, scale, thickness)
        sub_size = self._get_text_size(subtext, font, 0.58, 1)
        x = max(24, (self.width - max(text_size[0], sub_size[0])) // 2)
        y = max(72, self.height - 132)
        cv2.putText(frame, text, (x, y), font, scale, (185, 185, 185), thickness, cv2.LINE_AA)
        cv2.putText(frame, subtext, (x, y + 36), font, 0.58, (135, 135, 135), 1, cv2.LINE_AA)
        self._record_stage(f"projector_empty_status_{mode_label}", 0.0)
        return True

    def _static_ar_cache_key(self, dynamic_fresh: bool) -> str:
        return self._fingerprint({
            "size": self._frame_shape_key(),
            "dynamic_fresh": dynamic_fresh,
            "route_segments": self.ar_data.get("route_segments"),
            "trajectories": self.ar_data.get("trajectories"),
            "aim_lines": self.ar_data.get("aim_lines"),
            "ghost_balls": self.ar_data.get("ghost_balls"),
            "balls": self.ar_data.get("balls"),
            "cue_landing_point": self.ar_data.get("cue_landing_point"),
            "cue_landing_zone": self.ar_data.get("cue_landing_zone"),
            "position_play": self.ar_data.get("position_play"),
            "table_polygon": self.ar_data.get("table_polygon"),
            "allow_legacy_aim_lines": self.ar_data.get("allow_legacy_aim_lines", False),
            "allow_legacy_trajectories": self.ar_data.get("allow_legacy_trajectories", False),
        })

    def _draw_cached_static_ar_elements(self, frame: np.ndarray) -> bool:
        dynamic_fresh = self._dynamic_ar_is_fresh()
        if not bool(getattr(config, "PROJECTOR_RENDER_CACHE_ENABLED", False)):
            static_start = time.perf_counter()
            drawn = self._draw_static_ar_elements(frame, dynamic_fresh)
            self._record_stage("projector_static_ar_uncached", time.perf_counter() - static_start)
            return drawn

        cache_key = self._static_ar_cache_key(dynamic_fresh)
        if self._static_ar_frame_cache is not None and self._static_ar_frame_cache_key == cache_key:
            self._cache_stats["static_ar_hits"] += 1
            frame[:] = self._static_ar_frame_cache
            return self._static_ar_cache_drawn

        self._cache_stats["static_ar_misses"] += 1
        build_start = time.perf_counter()
        static_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        drawn = self._draw_static_ar_elements(static_frame, dynamic_fresh)
        self._static_ar_frame_cache = static_frame
        self._static_ar_frame_cache_key = cache_key
        self._static_ar_cache_drawn = drawn
        frame[:] = static_frame
        self._record_stage("projector_static_ar_cache_build", time.perf_counter() - build_start)
        return drawn

    def _draw_position_play(self, frame: np.ndarray) -> None:
        position_play = self.ar_data.get("position_play")
        if not isinstance(position_play, dict):
            return

        cue_after = position_play.get("cue_ball_after_contact")
        if not isinstance(cue_after, dict):
            return

        self._draw_zone_marker(frame, cue_after.get("target_zone"), (40, 210, 255), "TARGET", filled=True)
        if bool(getattr(config, "PROJECTOR_SHOW_POSITION_AVOID_ZONES", True)):
            max_avoid_zones = max(0, int(getattr(config, "PROJECTOR_MAX_AVOID_ZONES", 3)))
            show_pocket_avoid = bool(getattr(config, "PROJECTOR_SHOW_POCKET_AVOID_ZONES", False))
            drawn_avoid_zones = 0
            for zone in cue_after.get("avoid_zones", []) or []:
                if not isinstance(zone, dict):
                    continue
                if zone.get("type") == "pocket_scratch" and not show_pocket_avoid:
                    continue
                if max_avoid_zones > 0 and drawn_avoid_zones >= max_avoid_zones:
                    break
                self._draw_zone_marker(frame, zone, (0, 0, 255), "AVOID")
                drawn_avoid_zones += 1

        next_ball = position_play.get("next_ball")
        if isinstance(next_ball, dict):
            center = next_ball.get("center")
            if isinstance(center, (list, tuple)) and len(center) >= 2:
                try:
                    nx = int(round(float(center[0])))
                    ny = int(round(float(center[1])))
                except (TypeError, ValueError):
                    return
                cv2.circle(frame, (nx, ny), 20, (0, 220, 255), 3, cv2.LINE_AA)
                cv2.circle(frame, (nx, ny), 5, (0, 220, 255), -1, cv2.LINE_AA)
                number = next_ball.get("number")
                label = f"NEXT {number}" if number is not None else "NEXT"
                cv2.putText(frame, label, (nx + 24, ny - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(frame, label, (nx + 24, ny - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 2, cv2.LINE_AA)

    def _draw_lookahead_position_play(self, frame: np.ndarray) -> bool:
        lookahead = self.ar_data.get("lookahead")
        if not isinstance(lookahead, dict):
            return False

        next_routes = lookahead.get("next_routes")
        if not isinstance(next_routes, list) or not next_routes:
            return False

        next_route = next_routes[0]
        if not isinstance(next_route, dict):
            return False

        drawn = False
        for segment in next_route.get("route_segments", []) or []:
            if not isinstance(segment, dict):
                continue
            points = segment.get("points", [])
            if not isinstance(points, list) or len(points) <= 1:
                continue
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], False, (180, 120, 255), 2, cv2.LINE_AA)
            drawn = True

        landing = next_route.get("cue_landing_point")
        if isinstance(landing, (list, tuple)) and len(landing) >= 2:
            try:
                lx = int(round(float(landing[0])))
                ly = int(round(float(landing[1])))
            except (TypeError, ValueError):
                lx = ly = None
            if lx is not None and ly is not None:
                cv2.circle(frame, (lx, ly), 14, (180, 120, 255), 2, cv2.LINE_AA)
                cv2.line(frame, (lx - 10, ly), (lx + 10, ly), (180, 120, 255), 2, cv2.LINE_AA)
                cv2.line(frame, (lx, ly - 10), (lx, ly + 10), (180, 120, 255), 2, cv2.LINE_AA)
                target = next_route.get("target_ball_number")
                label = f"2P NEXT {target}" if target is not None else "2P NEXT"
                cv2.putText(frame, label, (lx + 18, ly - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(frame, label, (lx + 18, ly - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 120, 255), 2, cv2.LINE_AA)
                drawn = True

        zone = next_route.get("cue_target_zone") or next_route.get("cue_landing_zone")
        drawn = self._draw_zone_marker(frame, zone, (180, 120, 255), "2P", filled=True) or drawn
        return drawn

    def _draw_static_ar_elements(self, frame: np.ndarray, dynamic_fresh: bool) -> bool:
        """繪製可快取的 AR 元素，不包含即時球桿雷射線。"""
        if not dynamic_fresh:
            return False

        route_segments = self.ar_data.get("route_segments")
        if not isinstance(route_segments, list):
            route_segments = []
        segment_colors = {
            "cue_to_contact": (255, 255, 255),       # 母球到撞點
            "object_to_pocket": (80, 220, 75),       # 目標球進洞線
            "object_to_rail": (80, 220, 75),         # 目標球反彈線
            "combo_transfer": (0, 220, 255),         # 組合球傳遞
            "cue_after_contact": (255, 220, 0),      # 母球碰撞後走位
            "object_after_contact": (80, 220, 75),   # 子球接觸後走位
        }

        ar_start = time.perf_counter()
        drawn = False
        if route_segments:
            for segment in route_segments:
                points = segment.get("points", []) if isinstance(segment, dict) else []
                if not isinstance(points, list):
                    points = []
                if len(points) <= 1:
                    continue

                segment_type = segment.get("type", "") if isinstance(segment, dict) else ""
                color = segment_colors.get(segment_type, (255, 255, 0))
                drawn = self._draw_polyline_avoiding_balls(frame, points, color, 4) or drawn

                if segment_type == "cue_after_contact":
                    pts = np.array(points, np.int32).reshape((-1, 1, 2))
                    cv2.circle(frame, tuple(pts[-1][0]), 10, color, 2, cv2.LINE_AA)
        elif self.ar_data.get("allow_legacy_trajectories", False):

            # 舊版 fallback：只畫單一路徑，避免破壞既有流程。
            trajectories = self.ar_data.get("trajectories")
            if not isinstance(trajectories, list):
                trajectories = []
            for trajectory in trajectories:
                if not isinstance(trajectory, list):
                    continue
                if len(trajectory) > 1:
                    drawn = self._draw_polyline_avoiding_balls(frame, trajectory, (0, 255, 0), 3) or drawn

        # 新版 route_segments 已包含瞄準與擊後路線；只有 fallback 時才畫舊瞄準線。
        if not route_segments and self.ar_data.get("allow_legacy_aim_lines", False):
            aim_lines = self.ar_data.get("aim_lines")
            if not isinstance(aim_lines, list):
                aim_lines = []
            for aim_line in aim_lines:
                if not isinstance(aim_line, dict):
                    continue
                start = tuple(aim_line["start"])
                end = tuple(aim_line["end"])
                ltype = aim_line.get("type", "")
                if ltype == "cue_to_target":
                    color = (255, 255, 255)  # 白色
                elif ltype == "target_to_hole":
                    color = (0, 255, 255)  # 黃色
                elif ltype == "separation_line":
                    color = (255, 105, 180)  #亮粉/紫色
                else:
                    color = (255, 255, 0)
                drawn = self._draw_polyline_avoiding_balls(frame, [start, end], color, 3) or drawn

        # 繪製幽靈球
        ghost_balls = self.ar_data.get("ghost_balls")
        if not isinstance(ghost_balls, list):
            ghost_balls = []
        for gb in ghost_balls:
            if not isinstance(gb, dict):
                continue
            gx, gy, gr = gb["x"], gb["y"], gb["r"]
            cv2.circle(frame, (gx, gy), gr, (255, 255, 255), 2, cv2.LINE_AA)
            drawn = True

        landing = self.ar_data.get("cue_landing_point")
        if isinstance(landing, (list, tuple)) and len(landing) >= 2:
            lx, ly = int(landing[0]), int(landing[1])
            cv2.circle(frame, (lx, ly), 18, (255, 220, 0), 2, cv2.LINE_AA)
            cv2.line(frame, (lx - 14, ly), (lx + 14, ly), (255, 220, 0), 2, cv2.LINE_AA)
            cv2.line(frame, (lx, ly - 14), (lx, ly + 14), (255, 220, 0), 2, cv2.LINE_AA)
            drawn = True

        drawn = self._draw_zone_marker(frame, self.ar_data.get("cue_landing_zone"), (255, 220, 0), "LAND") or drawn
        self._draw_position_play(frame)
        drawn = self._draw_lookahead_position_play(frame) or drawn

        self._record_stage("projector_static_ar_draw", time.perf_counter() - ar_start)
        return drawn

    def _line_avoidance_zones(self) -> list[tuple[float, float, float]]:
        balls = self.ar_data.get("balls")
        if not isinstance(balls, list):
            return []

        default_radius = float(getattr(config, "PROJECTOR_LINE_BALL_CLEARANCE_RADIUS", 34))
        zones: list[tuple[float, float, float]] = []
        for ball in balls:
            if not isinstance(ball, dict):
                continue
            try:
                x = float(ball.get("x"))
                y = float(ball.get("y"))
                radius = float(ball.get("r", default_radius) or default_radius)
            except (TypeError, ValueError):
                continue
            zones.append((x, y, max(0.0, radius)))
        return zones

    @staticmethod
    def _segment_visible_intervals(
        p0: tuple[float, float],
        p1: tuple[float, float],
        zones: list[tuple[float, float, float]],
    ) -> list[tuple[float, float]]:
        blocked: list[tuple[float, float]] = []
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        a = dx * dx + dy * dy
        if a <= 1e-6:
            return []

        for cx, cy, radius in zones:
            if radius <= 0:
                continue
            fx = p0[0] - cx
            fy = p0[1] - cy
            b = 2.0 * (fx * dx + fy * dy)
            c = fx * fx + fy * fy - radius * radius
            discriminant = b * b - 4.0 * a * c
            if discriminant < 0:
                if c <= 0:
                    blocked.append((0.0, 1.0))
                continue

            root = math.sqrt(discriminant)
            t0 = (-b - root) / (2.0 * a)
            t1 = (-b + root) / (2.0 * a)
            start = max(0.0, min(t0, t1))
            end = min(1.0, max(t0, t1))
            if end > 0.0 and start < 1.0 and end > start:
                blocked.append((start, end))

        if not blocked:
            return [(0.0, 1.0)]

        blocked.sort()
        merged: list[tuple[float, float]] = []
        for start, end in blocked:
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))

        visible: list[tuple[float, float]] = []
        cursor = 0.0
        for start, end in merged:
            if start > cursor:
                visible.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < 1.0:
            visible.append((cursor, 1.0))
        return [(start, end) for start, end in visible if end - start > 0.01]

    def _draw_polyline_avoiding_balls(
        self,
        frame: np.ndarray,
        points: list,
        color: tuple[int, int, int],
        thickness: int,
    ) -> bool:
        zones = self._line_avoidance_zones()
        clean_points: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                clean_points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue

        drawn = False
        for p0, p1 in zip(clean_points, clean_points[1:]):
            for start, end in self._segment_visible_intervals(p0, p1, zones):
                sx = p0[0] + (p1[0] - p0[0]) * start
                sy = p0[1] + (p1[1] - p0[1]) * start
                ex = p0[0] + (p1[0] - p0[0]) * end
                ey = p0[1] + (p1[1] - p0[1]) * end
                cv2.line(
                    frame,
                    (int(round(sx)), int(round(sy))),
                    (int(round(ex)), int(round(ey))),
                    color,
                    thickness,
                    cv2.LINE_AA,
                )
                drawn = True
        return drawn

    def _draw_ar_elements(self, frame: np.ndarray) -> bool:
        """繪製共用的 AR 元素 (軌跡、瞄準線、幽靈球)。"""
        static_drawn = self._draw_cached_static_ar_elements(frame)
        cue_laser_drawn = self._draw_cue_laser_elements(frame)
        return static_drawn or cue_laser_drawn

    def _build_setup_balls_layer(self) -> None:
        """繪製球型練習設定球位。"""
        cache_key = self._fingerprint({
            "size": self._frame_shape_key(),
            "setup_balls": self.ar_data.get("setup_balls"),
        })
        if (
            bool(getattr(config, "PROJECTOR_RENDER_CACHE_ENABLED", False))
            and
            self._setup_balls_layer_cache is not None
            and self._setup_balls_mask_cache is not None
            and self._setup_balls_cache_key == cache_key
        ):
            self._cache_stats["setup_balls_hits"] += 1
            return

        self._cache_stats["setup_balls_misses"] += 1
        build_start = time.perf_counter()
        layer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        setup_balls = self.ar_data.get("setup_balls")
        if not isinstance(setup_balls, list):
            setup_balls = []
        for ball in setup_balls:
            if not isinstance(ball, dict):
                continue
            x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
            radius = int(ball.get("r", 24))
            ball_type = ball.get("type", "object")
            label = str(ball.get("label", ""))
            color = (255, 255, 255) if ball_type == "cue" else (80, 220, 75)
            if ball_type == "object2":
                color = (0, 220, 255)

            cv2.circle(layer, (x, y), radius, color, 3, cv2.LINE_AA)
            cv2.circle(layer, (x, y), max(4, radius // 4), color, -1, cv2.LINE_AA)
            if label and label.isascii():
                cv2.putText(
                    layer,
                    label,
                    (x - radius, y - radius - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                    cv2.LINE_AA,
                )
        self._setup_balls_layer_cache = layer
        self._setup_balls_mask_cache = np.any(layer != 0, axis=2)
        self._setup_balls_cache_key = cache_key
        self._record_stage("projector_setup_balls_cache_build", time.perf_counter() - build_start)

    def _draw_setup_balls(self, frame: np.ndarray):
        """套用快取的球型練習設定球位圖層。"""
        self._build_setup_balls_layer()
        if self._setup_balls_layer_cache is None or self._setup_balls_mask_cache is None:
            return
        compose_start = time.perf_counter()
        frame[self._setup_balls_mask_cache] = self._setup_balls_layer_cache[self._setup_balls_mask_cache]
        self._record_stage("projector_setup_balls_compose", time.perf_counter() - compose_start)

    def _has_setup_balls(self) -> bool:
        setup_balls = self.ar_data.get("setup_balls")
        return isinstance(setup_balls, list) and any(isinstance(ball, dict) for ball in setup_balls)

    def _has_enabled_game_timer(self) -> bool:
        timer = self.ar_data.get("game_timer")
        return isinstance(timer, dict) and bool(timer.get("enabled", False))

    def _get_table_polygon(self) -> list[tuple[int, int]]:
        polygon = self.ar_data.get("table_polygon")
        if not isinstance(polygon, list):
            polygon = []
        clean: list[tuple[int, int]] = []
        for point in polygon:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                try:
                    x = max(0, min(self.width - 1, int(round(float(point[0])))))
                    y = max(0, min(self.height - 1, int(round(float(point[1])))))
                    clean.append((x, y))
                except (TypeError, ValueError):
                    continue
        return clean if len(clean) >= 4 else []

    def _draw_table_warning_frame(self, frame: np.ndarray, color: tuple[int, int, int], thickness: int, pulse: float):
        """沿 homography 後的球桌四邊形畫警示框與燈點。"""
        polygon = self._get_table_polygon()
        if not polygon:
            return

        pts = np.array(polygon[:4], np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], True, color, thickness + 6, cv2.LINE_AA)
        cv2.polylines(frame, [pts], True, color, max(2, thickness), cv2.LINE_AA)

        dot_radius = 14 + int(9 * pulse)
        spacing = 240.0
        for idx, start in enumerate(polygon[:4]):
            end = polygon[(idx + 1) % 4]
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            steps = max(1, int(length // spacing))
            for step in range(steps + 1):
                t = step / max(1, steps)
                x = int(round(start[0] + (end[0] - start[0]) * t))
                y = int(round(start[1] + (end[1] - start[1]) * t))
                cv2.circle(frame, (x, y), dot_radius, color, -1, cv2.LINE_AA)
                cv2.circle(frame, (x, y), dot_radius + 8, color, 2, cv2.LINE_AA)

    def _draw_seven_segment_digit(
        self,
        frame: np.ndarray,
        digit: str,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int],
        thickness: int,
    ):
        """繪製閉合七段數字，避免 OpenCV 字型的 0 筆畫缺角。"""
        segment_map = {
            "0": ("a", "b", "c", "d", "e", "f"),
            "1": ("b", "c"),
            "2": ("a", "b", "g", "e", "d"),
            "3": ("a", "b", "g", "c", "d"),
            "4": ("f", "g", "b", "c"),
            "5": ("a", "f", "g", "c", "d"),
            "6": ("a", "f", "g", "e", "c", "d"),
            "7": ("a", "b", "c"),
            "8": ("a", "b", "c", "d", "e", "f", "g"),
            "9": ("a", "b", "c", "d", "f", "g"),
        }
        active = segment_map.get(digit)
        if not active:
            return

        pad = thickness // 2
        left = x + pad
        right = x + width - pad
        top = y + pad
        mid = y + height // 2
        bottom = y + height - pad
        segments = {
            "a": ((left, top), (right, top)),
            "b": ((right, top), (right, mid)),
            "c": ((right, mid), (right, bottom)),
            "d": ((left, bottom), (right, bottom)),
            "e": ((left, mid), (left, bottom)),
            "f": ((left, top), (left, mid)),
            "g": ((left, mid), (right, mid)),
        }
        for key in active:
            start, end = segments[key]
            cv2.line(frame, start, end, (0, 0, 0), thickness + 12, cv2.LINE_AA)
            cv2.line(frame, start, end, color, thickness, cv2.LINE_AA)

    def _draw_countdown_digits(self, frame: np.ndarray, text: str, y: int, color: tuple[int, int, int]):
        digit_width = 108
        digit_height = 168
        digit_gap = 34
        thickness = 18
        total_width = len(text) * digit_width + max(0, len(text) - 1) * digit_gap
        x = (self.width - total_width) // 2
        for digit in text:
            self._draw_seven_segment_digit(frame, digit, x, y, digit_width, digit_height, color, thickness)
            x += digit_width + digit_gap

    def _game_timer_cache_key(self) -> Optional[str]:
        timer = self.ar_data.get("game_timer")
        if not isinstance(timer, dict) or not timer.get("enabled", False):
            return None
        bucket = int(time.time() * 15.0)
        return self._fingerprint({
            "size": self._frame_shape_key(),
            "timer": timer,
            "bucket_15fps": bucket,
            "table_polygon": self.ar_data.get("table_polygon"),
        })

    def _draw_cached_game_timer(self, frame: np.ndarray):
        cache_key = self._game_timer_cache_key()
        if cache_key is None:
            return
        if not bool(getattr(config, "PROJECTOR_RENDER_CACHE_ENABLED", False)):
            timer_start = time.perf_counter()
            self._draw_game_timer(frame)
            self._record_stage("projector_game_timer_uncached", time.perf_counter() - timer_start)
            return

        if (
            self._timer_layer_cache is not None
            and self._timer_mask_cache is not None
            and self._timer_cache_key == cache_key
        ):
            self._cache_stats["timer_hits"] += 1
        else:
            self._cache_stats["timer_misses"] += 1
            build_start = time.perf_counter()
            sentinel = np.full((self.height, self.width, 3), (1, 2, 3), dtype=np.uint8)
            self._draw_game_timer(sentinel)
            self._timer_layer_cache = sentinel
            self._timer_mask_cache = np.any(sentinel != (1, 2, 3), axis=2)
            self._timer_cache_key = cache_key
            self._record_stage("projector_game_timer_cache_build", time.perf_counter() - build_start)

        if self._timer_layer_cache is None or self._timer_mask_cache is None:
            return
        compose_start = time.perf_counter()
        frame[self._timer_mask_cache] = self._timer_layer_cache[self._timer_mask_cache]
        self._record_stage("projector_game_timer_compose", time.perf_counter() - compose_start)

    def _draw_game_timer(self, frame: np.ndarray):
        """在球桌投影上繪製出手倒數與低時間呼吸警示。"""
        timer = self.ar_data.get("game_timer")
        if not isinstance(timer, dict) or not timer.get("enabled", False):
            return

        try:
            shot_limit = int(timer.get("shot_time_limit", 0) or 0)
            base_remaining = float(timer.get("remaining_time", 0) or 0)
            updated_at = float(timer.get("updated_at", 0.0) or 0.0)
            current_player = int(timer.get("current_player", 1) or 1)
            foul_detected = bool(timer.get("foul_detected", False))
        except (TypeError, ValueError):
            return

        font = cv2.FONT_HERSHEY_SIMPLEX
        pulse = (math.sin(time.time() * 2.0) + 1.0) / 2.0

        if shot_limit > 0:
            elapsed = max(0.0, time.time() - updated_at) if updated_at > 0 else 0.0
            remaining = max(0, int(round(base_remaining - elapsed)))
            is_warning = 11 <= remaining <= 20
            is_danger = remaining <= 10

            color = (255, 255, 255)
            if is_warning:
                color = (0, 220, 255)
            if is_danger:
                flash_on = pulse >= 0.48
                color = (0, 0, 255) if flash_on else (0, 0, 80)

            if is_warning or is_danger:
                glow_color = color
                line_thickness = 5 if is_warning else 6 + int(6 * pulse)
                self._draw_table_warning_frame(frame, glow_color, line_thickness, pulse)

            header_y = 92
            header_scale = 1.75
            header_thickness = 4
            p1_color = (255, 255, 255) if current_player == 1 else (85, 85, 85)
            p2_color = (255, 255, 255) if current_player == 2 else (85, 85, 85)
            time_color = color
            if current_player == 1:
                p1_color = color
            elif current_player == 2:
                p2_color = color

            parts = [("P1", p1_color), ("TIME", time_color), ("P2", p2_color)]
            widths = [self._get_text_size(text, font, header_scale, header_thickness)[0] for text, _ in parts]
            gap = 70
            total_width = sum(widths) + gap * 2
            x = (self.width - total_width) // 2
            for idx, (text, part_color) in enumerate(parts):
                if (idx == 0 and current_player == 1) or (idx == 2 and current_player == 2):
                    cv2.rectangle(
                        frame,
                        (x - 22, header_y - 58),
                        (x + widths[idx] + 22, header_y + 18),
                        (0, 0, 0),
                        -1,
                        cv2.LINE_AA,
                    )
                    cv2.rectangle(
                        frame,
                        (x - 22, header_y - 58),
                        (x + widths[idx] + 22, header_y + 18),
                        part_color,
                        3,
                        cv2.LINE_AA,
                    )
                cv2.putText(frame, text, (x, header_y), font, header_scale, (0, 0, 0), header_thickness + 4, cv2.LINE_AA)
                cv2.putText(frame, text, (x, header_y), font, header_scale, part_color, header_thickness, cv2.LINE_AA)
                x += widths[idx] + gap

            countdown = f"{remaining:02d}"
            self._draw_countdown_digits(frame, countdown, 116, color)

        if foul_detected:
            free_ball = "FREE BALL"
            free_scale = 2.3
            free_thickness = 6
            free_size = self._get_text_size(free_ball, font, free_scale, free_thickness)
            free_x = (self.width - free_size[0]) // 2
            free_y = 360 if shot_limit > 0 else 160
            cv2.rectangle(
                frame,
                (free_x - 36, free_y - free_size[1] - 24),
                (free_x + free_size[0] + 36, free_y + 26),
                (0, 0, 0),
                -1,
                cv2.LINE_AA,
            )
            cv2.rectangle(
                frame,
                (free_x - 36, free_y - free_size[1] - 24),
                (free_x + free_size[0] + 36, free_y + 26),
                (0, 0, 255),
                4,
                cv2.LINE_AA,
            )
            cv2.putText(frame, free_ball, (free_x, free_y), font, free_scale, (0, 0, 0), free_thickness + 5, cv2.LINE_AA)
            cv2.putText(frame, free_ball, (free_x, free_y), font, free_scale, (0, 0, 255), free_thickness, cv2.LINE_AA)

    def _render_game(self) -> np.ndarray:
        """遊戲模式: AR 疊加 (軌跡、球位、輔助線)"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        dynamic_drawn = self._draw_ar_elements(frame)
        self._draw_cached_game_timer(frame)

        # 繪製黑色遮罩，挖空輔助線經過球體的區段
        if dynamic_drawn and self._dynamic_ar_is_fresh():
            balls = self.ar_data.get("balls")
            if not isinstance(balls, list):
                balls = []
            for ball in balls:
                if not isinstance(ball, dict):
                    continue
                x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
                cv2.circle(frame, (x, y), 30, (0, 0, 0), -1, cv2.LINE_AA)

        if not dynamic_drawn and not self._has_enabled_game_timer():
            self._draw_empty_status(frame, "game")

        return frame

    def _render_practice(self) -> np.ndarray:
        """練習模式: 球外框 + 球形 + 輔助線"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        dynamic_drawn = self._draw_ar_elements(frame)

        # 繪製黑色遮罩，挖空輔助線經過球體的區段，確保投影機光線不打在球上
        if dynamic_drawn and self._dynamic_ar_is_fresh():
            balls = self.ar_data.get("balls")
            if not isinstance(balls, list):
                balls = []
            for ball in balls:
                if not isinstance(ball, dict):
                    continue
                x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
                cv2.circle(frame, (x, y), 30, (0, 0, 0), -1, cv2.LINE_AA)

        self._draw_setup_balls(frame)
        if not dynamic_drawn and not self._has_setup_balls():
            self._draw_empty_status(frame, "practice")

        return frame

    def update_calibration_offsets(self, offsets: Dict):
        """更新校正模式的標記偏移"""
        self.calibration_offsets.update(offsets)

    def update_ar_data(self, ar_data: Dict):
        """更新 AR 疊加資料"""
        self.ar_data.update(ar_data)
