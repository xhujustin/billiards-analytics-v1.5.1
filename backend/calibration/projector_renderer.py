"""
投影機獨立渲染器
負責投影機畫面的獨立渲染,不依賴相機畫面
支援多種模式: 待機、校正、遊戲、練習
"""

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
            "game_timer": {
                "enabled": False,
                "shot_time_limit": 0,
                "remaining_time": 0,
                "current_player": 1,
                "updated_at": 0.0,
            },
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
        if self.mode == ProjectorMode.IDLE:
            return self._render_idle()
        elif self.mode == ProjectorMode.CALIBRATION:
            return self._render_calibration()
        elif self.mode == ProjectorMode.DETECTION:
            return self._render_detection()
        elif self.mode == ProjectorMode.GAME:
            return self._render_game()
        elif self.mode == ProjectorMode.PRACTICE:
            return self._render_practice()
        else:
            return self._render_idle()

    def _render_idle(self) -> np.ndarray:
        """待機模式: 純黑畫面"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # 顯示提示文字
        text = "NCUT Billiards Analytics System V1.5.2"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 1.5, 3)[0]
        text_x = (self.width - text_size[0]) // 2
        text_y = (self.height + text_size[1]) // 2
        cv2.putText(frame, text, (text_x, text_y), font, 1.5, (50, 50, 50), 3)

        return frame

    def _render_calibration(self) -> np.ndarray:
        """校正模式: ArUco 標記圖案"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # 縮小標記大小
        marker_size = 100
        # 白色邊框寬度（保持對比度）
        border_width = 10
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

        return frame

    def _render_detection(self) -> np.ndarray:
        """啟動辨識模式: 單純投影球的外框"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # 繪製球位外框 (不填充)
        for ball in self.ar_data.get("balls", []):
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

        max_age_ms = int(getattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", getattr(config, "PROJECTOR_AR_METADATA_MAX_AGE_MS", 160)))
        if max_age_ms <= 0:
            return True

        timestamp = self.ar_data.get("ar_timestamp")
        if not isinstance(timestamp, (int, float)) or timestamp <= 0:
            return False
        return (time.time() - float(timestamp)) * 1000.0 <= max_age_ms

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
        return (time.time() - float(timestamp)) * 1000.0 <= max_age_ms

    def _draw_zone_marker(
        self,
        frame: np.ndarray,
        zone: Any,
        color: tuple[int, int, int],
        label: str,
        filled: bool = False,
    ) -> None:
        if not isinstance(zone, dict):
            return
        center = zone.get("center")
        if not isinstance(center, (list, tuple)) or len(center) < 2:
            return
        try:
            cx = int(round(float(center[0])))
            cy = int(round(float(center[1])))
            radius = int(round(float(zone.get("radius", 24) or 24)))
        except (TypeError, ValueError):
            return
        radius = max(8, min(180, radius))
        if filled:
            overlay = frame.copy()
            cv2.circle(overlay, (cx, cy), radius, color, -1, cv2.LINE_AA)
            cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
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

    def _draw_position_play(self, frame: np.ndarray) -> None:
        position_play = self.ar_data.get("position_play")
        if not isinstance(position_play, dict):
            return

        cue_after = position_play.get("cue_ball_after_contact")
        if not isinstance(cue_after, dict):
            return

        self._draw_zone_marker(frame, cue_after.get("target_zone"), (40, 210, 255), "TARGET", filled=True)
        for zone in cue_after.get("avoid_zones", []) or []:
            self._draw_zone_marker(frame, zone, (0, 0, 255), "AVOID")

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

    def _draw_ar_elements(self, frame: np.ndarray) -> bool:
        """繪製共用的 AR 元素 (軌跡、瞄準線、幽靈球)"""
        dynamic_fresh = self._dynamic_ar_is_fresh()
        cue_laser_fresh = self._cue_laser_is_fresh()
        if not dynamic_fresh and not cue_laser_fresh:
            return False

        route_segments = self.ar_data.get("route_segments", []) or []
        segment_colors = {
            "cue_to_contact": (255, 255, 255),       # 母球到撞點
            "object_to_pocket": (80, 220, 75),       # 目標球進洞線
            "object_to_rail": (80, 220, 75),         # 目標球反彈線
            "combo_transfer": (0, 220, 255),         # 組合球傳遞
            "cue_after_contact": (255, 220, 0),      # 母球碰撞後走位
            "object_after_contact": (80, 220, 75),   # 子球接觸後走位
        }

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

        # 新版多球規劃優先：分段畫出母球、目標球、反彈、擊球後走位。
        if cue_laser_fresh:
            for laser in self.ar_data.get("cue_laser_lines", []) or []:
                if isinstance(laser, dict):
                    draw_cue_laser(laser.get("points", []) or [])

        if not dynamic_fresh:
            return cue_laser_fresh

        if route_segments:
            for segment in route_segments:
                points = segment.get("points", []) if isinstance(segment, dict) else []
                if len(points) <= 1:
                    continue

                segment_type = segment.get("type", "") if isinstance(segment, dict) else ""
                color = segment_colors.get(segment_type, (255, 255, 0))
                pts = np.array(points, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], False, color, 4, cv2.LINE_AA)

                if segment_type == "cue_after_contact":
                    cv2.circle(frame, tuple(pts[-1][0]), 10, color, 2, cv2.LINE_AA)
        elif self.ar_data.get("allow_legacy_trajectories", False):

            # 舊版 fallback：只畫單一路徑，避免破壞既有流程。
            for trajectory in self.ar_data.get("trajectories", []):
                if len(trajectory) > 1:
                    pts = np.array(trajectory, np.int32).reshape((-1, 1, 2))
                    cv2.polylines(frame, [pts], False, (0, 255, 0), 3, cv2.LINE_AA)

        # 新版 route_segments 已包含瞄準與擊後路線；只有 fallback 時才畫舊瞄準線。
        if not route_segments and self.ar_data.get("allow_legacy_aim_lines", False):
            for aim_line in self.ar_data.get("aim_lines", []):
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
                cv2.line(frame, start, end, color, 3, cv2.LINE_AA)

        # 繪製幽靈球
        for gb in self.ar_data.get("ghost_balls", []):
            gx, gy, gr = gb["x"], gb["y"], gb["r"]
            cv2.circle(frame, (gx, gy), gr, (255, 255, 255), 2, cv2.LINE_AA)

        landing = self.ar_data.get("cue_landing_point")
        if isinstance(landing, (list, tuple)) and len(landing) >= 2:
            lx, ly = int(landing[0]), int(landing[1])
            cv2.circle(frame, (lx, ly), 18, (255, 220, 0), 2, cv2.LINE_AA)
            cv2.line(frame, (lx - 14, ly), (lx + 14, ly), (255, 220, 0), 2, cv2.LINE_AA)
            cv2.line(frame, (lx, ly - 14), (lx, ly + 14), (255, 220, 0), 2, cv2.LINE_AA)

        self._draw_zone_marker(frame, self.ar_data.get("cue_landing_zone"), (255, 220, 0), "LAND")
        self._draw_position_play(frame)

        return True

    def _draw_setup_balls(self, frame: np.ndarray):
        """繪製球型練習設定球位。"""
        setup_balls = self.ar_data.get("setup_balls", []) or []
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

            cv2.circle(frame, (x, y), radius, color, 3, cv2.LINE_AA)
            cv2.circle(frame, (x, y), max(4, radius // 4), color, -1, cv2.LINE_AA)
            if label and label.isascii():
                cv2.putText(
                    frame,
                    label,
                    (x - radius, y - radius - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                    cv2.LINE_AA,
                )

    def _get_table_polygon(self) -> list[tuple[int, int]]:
        polygon = self.ar_data.get("table_polygon", []) or []
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
            widths = [cv2.getTextSize(text, font, header_scale, header_thickness)[0][0] for text, _ in parts]
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
            free_size = cv2.getTextSize(free_ball, font, free_scale, free_thickness)[0]
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
        self._draw_game_timer(frame)

        # 繪製黑色遮罩，挖空輔助線經過球體的區段
        if dynamic_drawn and self._dynamic_ar_is_fresh():
            for ball in self.ar_data.get("balls", []):
                x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
                cv2.circle(frame, (x, y), 30, (0, 0, 0), -1, cv2.LINE_AA)

        return frame

    def _render_practice(self) -> np.ndarray:
        """練習模式: 球外框 + 球形 + 輔助線"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        dynamic_drawn = self._draw_ar_elements(frame)

        # 繪製黑色遮罩，挖空輔助線經過球體的區段，確保投影機光線不打在球上
        if dynamic_drawn and self._dynamic_ar_is_fresh():
            for ball in self.ar_data.get("balls", []):
                x, y = int(ball.get("x", 0)), int(ball.get("y", 0))
                cv2.circle(frame, (x, y), 30, (0, 0, 0), -1, cv2.LINE_AA)

        self._draw_setup_balls(frame)

        return frame

    def update_calibration_offsets(self, offsets: Dict):
        """更新校正模式的標記偏移"""
        self.calibration_offsets.update(offsets)

    def update_ar_data(self, ar_data: Dict):
        """更新 AR 疊加資料"""
        self.ar_data.update(ar_data)
