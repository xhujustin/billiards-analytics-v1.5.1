"""
Enhanced Pool Tracker with Full Physics Simulation
整合 poolShotPredictor.py 的完整邏輯
遵照 v1.5 技術文檔規範
"""

import math
import sys
import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

import config
import cv2
import numpy as np
import time  # ✅ 添加 time 模組
from ultralytics import YOLO
import torch
from .planner import RoutePlanner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CueAxis = List[List[float]]

class PoolTracker:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = config.MODEL_PATH

        # --- 1. 初始化 YOLO 模型 ---
        print(f"✅ Loading YOLO model from: {model_path}")
        self.model = YOLO(model_path)
        self.infer_device, self.use_half = self._resolve_inference_device()
        try:
            self.model.to(self.infer_device)
        except Exception as e:
            print(f"⚠️  Failed to move YOLO model to {self.infer_device}: {e}")
            self.infer_device = "cpu"
            self.use_half = False
        try:
            cuda_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
            print(
                "🚀 YOLO inference device: "
                f"{self.infer_device}, half={self.use_half}, "
                f"torch={torch.__version__}, torch_cuda={torch.version.cuda}, "
                f"cuda_available={torch.cuda.is_available()}, gpu={cuda_name}"
            )
        except Exception as e:
            print(f"🚀 YOLO inference device: {self.infer_device}, half={self.use_half} (CUDA info unavailable: {e})")

        # --- 2. 系統參數 ---
        self.conf_thr = config.CONF_THR
        self.iou_thr = config.IOU_THR
        self.hsv_lower = np.array(config.HSV_LOWER)
        self.hsv_upper = np.array(config.HSV_UPPER)
        self.current_table_color = config.TABLE_CLOTH_COLOR

        # --- 3. 狀態變數 ---
        self.table_roi: Optional[List[int]] = None  # [x, y, w, h]
        self.table_roi_raw: Optional[List[int]] = None
        self.table_roi_adjustment: Dict[str, int] = {"left": 0, "top": 0, "right": 0, "bottom": 0}
        self.table_roi_points: Optional[List[List[int]]] = None
        self.table_roi_status = "uninitialized"
        self.holes: List[List[int]] = []  # 球袋位置（全圖座標）
        self.hole_bboxes: List[List[int]] = []  # 球袋碰撞箱 [x1,y1,x2,y2]
        self.table_rects: List[List[int]] = []  # 球桌邊界

        # 擊球預測狀態
        self.last_point_history: List[List[int]] = []
        self.radius_mean: List[int] = []
        self.shot_points: List[List[int]] = []
        self.possibility: List[Optional[Dict]] = []
        self.prediction_mode = True
        self.aim_assist_enabled = False  # 進球輔助線（練習模式啟用）
        self.route_planner = RoutePlanner()
        self.route_planner_enabled = False
        self.route_rule_profile = "practice"
        self.route_top_n = 5
        self.route_max_bounces = 3
        self.route_combo_depth = 2
        self.route_target_ball_number: Optional[int] = None
        self.selected_route_id: Optional[str] = None
        self.route_stroke_override: Optional[Dict[str, Any]] = None
        self._route_plan_missing_frames = 0
        self._route_plan_hold_max_frames = 8

        # --- 4. 顏色映射 (從 poolShotPredictor.py) ---
        self.COLOR_TO_NUM = {
            "Yellow": (1, 9),
            "Blue": (2, 10),
            "Red": (3, 11),
            "Purple": (4, 12),
            "Orange": (5, 13),
            "Green": (6, 14),
            "Brown": (7, 15),
        }

        self.COLORS_BGR = {
            "Yellow": (0, 220, 255),
            "Blue": (255, 120, 0),
            "Red": (0, 0, 230),
            "Purple": (180, 0, 180),
            "Orange": (0, 140, 255),
            "Green": (0, 180, 0),
            "Brown": (30, 60, 120),
            "Black": (0, 0, 0),
            "White": (255, 255, 255),
            "Unknown": (160, 160, 160),
        }
        self.COLOR_LAB = {}
        for _name in ["Yellow", "Blue", "Red", "Purple", "Orange", "Green", "Brown"]:
            _bgr = np.uint8([[self.COLORS_BGR[_name]]])
            _lab = cv2.cvtColor(_bgr, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
            self.COLOR_LAB[_name] = _lab
        self.COLOR_HUE_CENTER = {
            "Yellow": 28.0,
            "Blue": 105.0,   # 標準台球藍球 Hue 約 100~112
            "Red": 0.0,
            "Purple": 142.0, # 收到更靠藍紫邊，避免吃黑球
            "Orange": 17.0,
            "Green": 60.0,
            "Brown": 12.0,
        }
        self.COLOR_SAT_REF = {
            "Yellow": 165.0,
            "Blue": 150.0,
            "Red": 155.0,
            "Purple": 140.0,
            "Orange": 165.0,
            "Green": 145.0,
            "Brown": 125.0,
        }
        self.COLOR_VAL_REF = {
            "Yellow": 220.0,
            "Blue": 180.0,   # 藍球實際亮度偏低，拉低 val ref
            "Red": 200.0,
            "Purple": 165.0, # 紫球偏暗
            "Orange": 220.0,
            "Green": 180.0,
            "Brown": 150.0,
        }
        self.DEFAULT_COLOR_HUE_CENTER = dict(self.COLOR_HUE_CENTER)
        self.DEFAULT_COLOR_SAT_REF = dict(self.COLOR_SAT_REF)
        self.DEFAULT_COLOR_VAL_REF = dict(self.COLOR_VAL_REF)
        self.DEFAULT_COLOR_LAB = {k: v.copy() for k, v in self.COLOR_LAB.items()}

        # 顏色時序平滑狀態（跨幀投票）
        self.temporal_frame_id = 0
        self.temporal_color_cache: List[Dict[str, Any]] = []
        self.temporal_ball_geometry_cache: List[Dict[str, Any]] = []
        self.manual_projected_artifacts: Dict[str, List[Any]] = {
            "segments": [],
            "points": [],
            "protected_points": [],
        }
        self._scaled_overlay_cache_key: Optional[str] = None
        self._scaled_overlay_layer_cache: Optional[np.ndarray] = None
        self._scaled_overlay_mask_cache: Optional[np.ndarray] = None
        self._scaled_overlay_cache_hits = 0
        self._scaled_overlay_cache_misses = 0
        self.cue_axis_cache: Optional[Dict[str, Any]] = None
        self.cue_axis_missing_frames = 0
        self.cue_laser_only = False
        self._load_table_roi_adjustment()
        self._load_table_roi_polygon()

    def _resolve_inference_device(self) -> Tuple[Any, bool]:
        requested_device = str(getattr(config, "YOLO_DEVICE", "auto")).strip().lower()
        requested_half = str(getattr(config, "YOLO_HALF", "auto")).strip().lower()

        cuda_available = False
        try:
            cuda_available = torch.cuda.is_available()
        except Exception:
            cuda_available = False

        if requested_device in ("", "auto"):
            device: Any = "cuda:0" if cuda_available else "cpu"
        elif requested_device in ("cuda", "gpu"):
            device = "cuda:0" if cuda_available else "cpu"
            if not cuda_available:
                print("⚠️  YOLO_DEVICE=cuda was requested, but torch.cuda.is_available() is false. Falling back to CPU.")
        elif requested_device.isdigit():
            device = f"cuda:{requested_device}" if cuda_available else "cpu"
            if not cuda_available:
                print(f"⚠️  YOLO_DEVICE={requested_device} was requested, but CUDA is unavailable. Falling back to CPU.")
        else:
            device = requested_device

        if requested_half in ("true", "1", "yes", "y", "on"):
            use_half = str(device).startswith("cuda")
        elif requested_half in ("false", "0", "no", "n", "off"):
            use_half = False
        else:
            use_half = str(device).startswith("cuda")

        return device, use_half

    # ==================== 球桌顏色設定 ====================
    def _load_table_roi_adjustment(self) -> None:
        path = Path(getattr(config, "TABLE_ROI_ADJUSTMENT_PATH", PROJECT_ROOT / "runtime" / "table_roi_adjustment.json"))
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return
        if isinstance(data, dict):
            self.set_table_roi_adjustment(data, persist=False)

    def _save_table_roi_adjustment(self) -> None:
        path = Path(getattr(config, "TABLE_ROI_ADJUSTMENT_PATH", PROJECT_ROOT / "runtime" / "table_roi_adjustment.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(self.table_roi_adjustment, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def set_table_roi_adjustment(self, adjustment: Dict[str, Any], persist: bool = True) -> Dict[str, int]:
        next_adjustment: Dict[str, int] = {}
        for key in ("left", "top", "right", "bottom"):
            try:
                value = int(round(float(adjustment.get(key, 0))))
            except (TypeError, ValueError):
                value = 0
            next_adjustment[key] = max(-400, min(400, value))
        self.table_roi_adjustment = next_adjustment

        if self.table_roi_raw is not None and hasattr(self, "_last_frame_shape"):
            self.table_roi = self._apply_table_roi_adjustment(self.table_roi_raw)
            self.table_rects = [self.table_roi]
            x, y, w, h = self.table_roi
            self.holes = self._estimate_default_holes(x, y, w, h)
            self._update_hole_bboxes(self.table_roi)

        if persist:
            self._save_table_roi_adjustment()
        return dict(self.table_roi_adjustment)

    def reset_table_roi_adjustment(self) -> Dict[str, int]:
        return self.set_table_roi_adjustment({"left": 0, "top": 0, "right": 0, "bottom": 0})

    def _load_table_roi_polygon(self) -> None:
        path = Path(getattr(config, "TABLE_ROI_POLYGON_PATH", PROJECT_ROOT / "runtime" / "table_roi_polygon.json"))
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return
        points = data.get("points") if isinstance(data, dict) else data
        try:
            self.set_table_roi_polygon(points, persist=False)
        except ValueError:
            return

    def _save_table_roi_polygon(self) -> None:
        path = Path(getattr(config, "TABLE_ROI_POLYGON_PATH", PROJECT_ROOT / "runtime" / "table_roi_polygon.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump({"points": self.table_roi_points}, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def _normalize_table_roi_points(self, points: Any) -> List[List[int]]:
        if not isinstance(points, (list, tuple)) or len(points) != 4:
            raise ValueError("table ROI polygon requires exactly 4 points")

        normalized: List[List[int]] = []
        for point in points:
            if isinstance(point, dict):
                raw_x = point.get("x")
                raw_y = point.get("y")
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                raw_x, raw_y = point[0], point[1]
            else:
                raise ValueError("invalid table ROI point")
            try:
                x = int(round(float(raw_x)))
                y = int(round(float(raw_y)))
            except (TypeError, ValueError):
                raise ValueError("invalid table ROI point coordinate")
            normalized.append([max(0, x), max(0, y)])

        return normalized

    def _table_roi_from_points(self, points: List[List[int]]) -> List[int]:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        rect = [x0, y0, max(2, x1 - x0), max(2, y1 - y0)]
        if hasattr(self, "_last_frame_shape"):
            return self._clamp_table_roi(rect, self._last_frame_shape)
        return rect

    def set_table_roi_polygon(self, points: Any, persist: bool = True) -> List[List[int]]:
        normalized = self._normalize_table_roi_points(points)
        self.table_roi_points = normalized
        self.table_roi_raw = self._table_roi_from_points(normalized)
        self.table_roi = list(self.table_roi_raw)
        self.table_roi_status = "manual_polygon"
        self.table_rects = [self.table_roi]
        x, y, w, h = self.table_roi
        self.holes = self._estimate_default_holes(x, y, w, h)
        self._update_hole_bboxes(self.table_roi)

        if persist:
            self._save_table_roi_polygon()
        return [list(point) for point in normalized]

    def _sync_manual_table_roi_to_frame(self, frame: np.ndarray) -> None:
        """將舊版 1280x720 監控座標的手動 ROI 映射到目前相機原始解析度。"""
        if self.table_roi_status != "manual_polygon" or not self.table_roi_points:
            return

        frame_h, frame_w = frame.shape[:2]
        if frame_w <= 0 or frame_h <= 0:
            return

        try:
            xs = [int(point[0]) for point in self.table_roi_points]
            ys = [int(point[1]) for point in self.table_roi_points]
        except (TypeError, ValueError, IndexError):
            return

        saved_w = max(xs) - min(xs)
        saved_h = max(ys) - min(ys)
        if saved_w <= 0 or saved_h <= 0:
            return

        looks_like_monitor_space = (
            frame_w >= 1500
            and frame_h >= 900
            and max(xs) <= 1300
            and max(ys) <= 760
            and saved_w / max(1, frame_w) < 0.72
            and saved_w / 1280.0 > 0.70
            and saved_h / 720.0 > 0.55
        )
        if not looks_like_monitor_space:
            self._last_frame_shape = frame.shape[:2]
            self.table_roi_raw = self._table_roi_from_points(self.table_roi_points)
            self.table_roi = list(self.table_roi_raw)
            self.table_rects = [self.table_roi]
            return

        scale_x = frame_w / 1280.0
        scale_y = frame_h / 720.0
        scaled_points = [
            [int(round(point[0] * scale_x)), int(round(point[1] * scale_y))]
            for point in self.table_roi_points
        ]
        self._last_frame_shape = frame.shape[:2]
        self.table_roi_points = scaled_points
        self.table_roi_raw = self._table_roi_from_points(scaled_points)
        self.table_roi = list(self.table_roi_raw)
        self.table_roi_status = "manual_polygon_scaled"
        self.table_rects = [self.table_roi]
        x, y, w, h = self.table_roi
        self.holes = self._estimate_default_holes(x, y, w, h)
        self._update_hole_bboxes(self.table_roi)
        print(f"?? Scaled manual table ROI from 1280x720 monitor space to {frame_w}x{frame_h}: {self.table_roi}")

    def reset_table_roi_polygon(self) -> None:
        self.table_roi_points = None
        self.table_roi = None
        self.table_roi_raw = None
        self.table_roi_status = "polygon_reset"
        self.table_rects = []
        self.holes = []
        self.hole_bboxes = []
        path = Path(getattr(config, "TABLE_ROI_POLYGON_PATH", PROJECT_ROOT / "runtime" / "table_roi_polygon.json"))
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def _apply_table_roi_adjustment(self, raw_rect: List[int]) -> List[int]:
        left = int(self.table_roi_adjustment.get("left", 0))
        top = int(self.table_roi_adjustment.get("top", 0))
        right = int(self.table_roi_adjustment.get("right", 0))
        bottom = int(self.table_roi_adjustment.get("bottom", 0))
        x, y, w, h = [int(v) for v in raw_rect[:4]]
        return self._clamp_table_roi([x + left, y + top, w + right - left, h + bottom - top], self._last_frame_shape)

    def _commit_table_roi(self, frame: np.ndarray, raw_rect: List[int], status: str) -> List[int]:
        self._last_frame_shape = frame.shape[:2]
        self.table_roi_points = None
        self.table_roi_raw = self._clamp_table_roi(raw_rect, frame.shape[:2])
        self.table_roi = self._apply_table_roi_adjustment(self.table_roi_raw)
        self.table_roi_status = status
        self.table_rects = [self.table_roi]
        x, y, w, h = self.table_roi
        approx_holes = self._estimate_default_holes(x, y, w, h)
        self.holes = self._refine_holes_from_dark_regions(frame, approx_holes, self.table_roi)
        self._update_hole_bboxes(self.table_roi)
        return self.table_roi

    def update_table_color(self, color_name: str) -> bool:
        """
        更新球桌布料顏色設定
        color_name: 顏色名稱 (green, gray, blue, pink, purple, custom)
        返回: 成功與否
        """
        if color_name not in config.TABLE_COLOR_PRESETS:
            print(f"⚠️  Invalid color name: {color_name}")
            return False

        color_preset = config.TABLE_COLOR_PRESETS[color_name]
        self.hsv_lower = np.asarray(color_preset["hsv_lower"], dtype=np.uint8).copy()
        self.hsv_upper = np.asarray(color_preset["hsv_upper"], dtype=np.uint8).copy()
        self.current_table_color = color_name

        # 清除之前偵測到的球桌區域，強制重新偵測
        self.table_roi = None
        self.table_roi_raw = None
        self.table_roi_points = None
        self.table_roi_status = "color_changed"
        self.holes = []
        self.hole_bboxes = []
        self.table_rects = []

        print(f"✅ Table color updated to: {color_preset['name']} ({color_name})")
        print(f"   HSV_LOWER: {self.hsv_lower}, HSV_UPPER: {self.hsv_upper}")
        return True

    def update_custom_hsv(self, hsv_lower: List[int], hsv_upper: List[int]) -> bool:
        """
        更新自訂 HSV 範圍
        hsv_lower: HSV 下限 [H, S, V]
        hsv_upper: HSV 上限 [H, S, V]
        返回: 成功與否
        """
        try:
            self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
            self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)
            self.current_table_color = "custom"

            # 清除之前偵測到的球桌區域，強制重新偵測
            self.table_roi = None
            self.table_roi_raw = None
            self.table_roi_points = None
            self.table_roi_status = "custom_color_changed"
            self.holes = []
            self.hole_bboxes = []
            self.table_rects = []

            print(f"✅ Custom HSV range updated")
            print(f"   HSV_LOWER: {self.hsv_lower}, HSV_UPPER: {self.hsv_upper}")
            return True
        except Exception as e:
            print(f"⚠️  Failed to update custom HSV: {e}")
            return False

    def _hue_center_from_range(self, h_low: int, h_high: int) -> float:
        """從 HSV Hue 區間推估中心值（支援紅色跨 180 wrap）。"""
        h_low = max(0, min(180, int(h_low)))
        h_high = max(0, min(180, int(h_high)))
        if h_low <= h_high:
            return float((h_low + h_high) / 2.0)
        span = ((h_high + 180) - h_low) / 2.0
        return float((h_low + span) % 180)

    def apply_color_calibration(self, mode: str, mappings: Dict[str, Any]) -> Dict[str, Any]:
        """套用顏色校正設定檔到分類模板。"""
        self.COLOR_HUE_CENTER = dict(self.DEFAULT_COLOR_HUE_CENTER)
        self.COLOR_SAT_REF = dict(self.DEFAULT_COLOR_SAT_REF)
        self.COLOR_VAL_REF = dict(self.DEFAULT_COLOR_VAL_REF)
        self.COLOR_LAB = {k: v.copy() for k, v in self.DEFAULT_COLOR_LAB.items()}

        if not mappings:
            return {"applied": 0, "mode": mode}

        applied = 0
        for sys_color, cfg in mappings.items():
            if not isinstance(cfg, dict):
                continue

            if sys_color not in self.COLOR_HUE_CENTER and sys_color not in ["Black", "White"]:
                continue

            hsv_lower = cfg.get("hsv_lower")
            hsv_upper = cfg.get("hsv_upper")
            if not (isinstance(hsv_lower, list) and isinstance(hsv_upper, list) and len(hsv_lower) == 3 and len(hsv_upper) == 3):
                continue

            try:
                lower = [int(v) for v in hsv_lower]
                upper = [int(v) for v in hsv_upper]
            except (TypeError, ValueError):
                continue

            if lower == [0, 0, 0] and upper == [0, 0, 0]:
                continue

            h_span = (upper[0] - lower[0]) if lower[0] <= upper[0] else (upper[0] + 180 - lower[0])
            s_span = upper[1] - lower[1]
            v_span = upper[2] - lower[2]
            if h_span >= 170 and s_span >= 240 and v_span >= 240:
                continue

            s_ref = float(max(0, min(255, (lower[1] + upper[1]) / 2.0)))
            v_ref = int(max(0, min(255, (lower[2] + upper[2]) / 2.0)))

            self.COLOR_SAT_REF[sys_color] = s_ref
            self.COLOR_VAL_REF[sys_color] = float(v_ref)

            if sys_color not in ["Black", "White"]:
                h_center = self._hue_center_from_range(lower[0], upper[0])
                self.COLOR_HUE_CENTER[sys_color] = h_center

                hsv_pixel = np.uint8([[[int(h_center), int(s_ref), v_ref]]])
                bgr_pixel = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)
                lab_pixel = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
                self.COLOR_LAB[sys_color] = lab_pixel

            applied += 1

        print(f"✅ Applied color calibration: mode={mode}, count={applied}")
        return {"applied": applied, "mode": mode}

    def reset_color_calibration(self) -> None:
        """回復系統預設顏色模板。"""
        self.COLOR_HUE_CENTER = dict(self.DEFAULT_COLOR_HUE_CENTER)
        self.COLOR_SAT_REF = dict(self.DEFAULT_COLOR_SAT_REF)
        self.COLOR_VAL_REF = dict(self.DEFAULT_COLOR_VAL_REF)
        self.COLOR_LAB = {k: v.copy() for k, v in self.DEFAULT_COLOR_LAB.items()}
        print("✅ Color calibration reset to defaults")

    # ==================== 進球輔助線控制 ====================
    def set_aim_assist(self, enabled: bool):
        """啟用/停用進球輔助線"""
        self.aim_assist_enabled = enabled
        print(f"{'✅ Aim assist enabled' if enabled else '⛔ Aim assist disabled'}")

    def set_route_rule_profile(self, profile: str):
        if profile not in {"9ball", "practice"}:
            profile = "practice"
        self.route_rule_profile = profile
        print(f"✅ Route rule profile set to: {self.route_rule_profile}")

    def set_route_target_ball_number(self, target_ball_number: Optional[int]):
        """設定即時路徑規劃優先鎖定的目標球號。"""
        self.route_target_ball_number = target_ball_number if isinstance(target_ball_number, int) else None

    def set_route_planner_enabled(self, enabled: bool):
        """控制是否在即時追蹤流程中自動產生多球路徑規劃。"""
        self.route_planner_enabled = bool(enabled)
        if not self.route_planner_enabled:
            self._route_plan_missing_frames = 0
        print(f"{'✅ Route planner enabled' if enabled else '⛔ Route planner disabled'}")

    def configure_route_planner(self, top_n: int = 5, max_bounces: int = 3, combo_depth: int = 2):
        self.route_top_n = max(1, min(10, int(top_n)))
        self.route_max_bounces = max(0, min(3, int(max_bounces)))
        self.route_combo_depth = max(1, min(3, int(combo_depth)))

    def set_selected_route_id(self, route_id: Optional[str]):
        self.selected_route_id = route_id or None

    def set_route_stroke_override(self, stroke: Optional[Dict[str, Any]]):
        if not isinstance(stroke, dict):
            self.route_stroke_override = None
            return
        tip = str(stroke.get("tip", "center")).strip().lower()
        power = str(stroke.get("power", "medium")).strip().lower()
        power_percent = None
        tip_x = None
        tip_y = None
        try:
            if stroke.get("power_percent") is not None:
                power_percent = max(1.0, min(100.0, float(stroke.get("power_percent"))))
        except (TypeError, ValueError):
            power_percent = None
        try:
            if stroke.get("tip_x") is not None:
                tip_x = max(-1.0, min(1.0, float(stroke.get("tip_x"))))
            if stroke.get("tip_y") is not None:
                tip_y = max(-1.0, min(1.0, float(stroke.get("tip_y"))))
        except (TypeError, ValueError):
            tip_x = None
            tip_y = None
        if tip not in {"center", "top", "draw", "low", "left", "right", "top_left", "top_right", "draw_left", "draw_right"}:
            tip = "center"
        if power_percent is not None:
            if power_percent <= 25:
                power = "low"
            elif power_percent <= 50:
                power = "medium"
            elif power_percent <= 75:
                power = "medium_high"
            else:
                power = "high"
        if power not in {"low", "medium", "medium_high", "high"}:
            power = "medium"
        self.route_stroke_override = {"tip": tip, "power": power}
        if power_percent is not None:
            self.route_stroke_override["power_percent"] = round(power_percent)
        if tip_x is not None and tip_y is not None:
            self.route_stroke_override["tip_x"] = round(tip_x, 3)
            self.route_stroke_override["tip_y"] = round(tip_y, 3)

    def plan_routes_from_packet(
        self,
        packet: Dict[str, Any],
        rule_profile: Optional[str] = None,
        top_n: Optional[int] = None,
        target_ball_number: Optional[int] = None,
        max_bounces: Optional[int] = None,
        combo_depth: Optional[int] = None,
        lookahead_enabled: Optional[bool] = None,
        lookahead_ply: int = 2,
        lookahead_candidate_count: int = 5,
        lookahead_next_top_n: int = 3,
        lookahead_score_weight: float = 0.25,
    ) -> Optional[Dict[str, Any]]:
        return self.route_planner.plan_from_runtime_packet(
            packet,
            rule_profile=rule_profile or self.route_rule_profile,
            top_n=top_n if top_n is not None else self.route_top_n,
            target_ball_number=target_ball_number,
            max_bounces=max_bounces if max_bounces is not None else self.route_max_bounces,
            combo_depth=combo_depth if combo_depth is not None else self.route_combo_depth,
            selected_route_id=self.selected_route_id,
            stroke_override=self.route_stroke_override,
            lookahead_enabled=lookahead_enabled,
            lookahead_ply=lookahead_ply,
            lookahead_candidate_count=lookahead_candidate_count,
            lookahead_next_top_n=lookahead_next_top_n,
            lookahead_score_weight=lookahead_score_weight,
        )

    # ==================== 球桌偵測 ====================
    def detect_table(self, frame: np.ndarray) -> Tuple[bool, Optional[List[int]]]:
        """
        使用 HSV 綠色檢測找出球桌區域
        返回: (成功與否, 球桌bbox [x,y,w,h])
        """
        print(f"🔍 Detecting table... Frame shape: {frame.shape}")
        print(f"   HSV_LOWER: {self.hsv_lower}, HSV_UPPER: {self.hsv_upper}")
        print(f"   TABLE_MIN_AREA: {config.TABLE_MIN_AREA}")

        hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_img, self.hsv_lower, self.hsv_upper)

        # 計算綠色像素比例
        green_pixels = np.count_nonzero(mask)
        total_pixels = mask.size
        green_ratio = green_pixels / total_pixels
        print(f"   Green pixels: {green_pixels} / {total_pixels} ({green_ratio*100:.2f}%)")

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        print(f"   Found {len(contours)} contours")

        max_area = 0.0
        best_rect = None
        all_areas = []

        for contour in contours:
            area = cv2.contourArea(contour)
            all_areas.append(area)
            if area > config.TABLE_MIN_AREA:
                if area > max_area:
                    max_area = area
                    best_rect = cv2.boundingRect(contour)

        if all_areas:
            all_areas.sort(reverse=True)
            print(f"   Top 3 areas: {all_areas[:3]}")
            print(f"   Max area: {max_area}, Min required: {config.TABLE_MIN_AREA}")

        if best_rect:
            x, y, w, h = best_rect
            x, y, w, h = self._refine_table_roi_from_mask(mask, [x, y, w, h])
            roi_rect, roi_status = self._repair_partial_table_roi(frame, [x, y, w, h], "hsv")
            x, y, w, h = self._commit_table_roi(frame, roi_rect, roi_status)

            print(f"✅ Table detected: x={x}, y={y}, w={w}, h={h}")
            return True, [x, y, w, h]

        # 次級策略：放寬當前 HSV 與遍歷其他桌布色預設
        candidate_ranges: List[Tuple[str, np.ndarray, np.ndarray]] = []
        h0, s0, v0 = [int(v) for v in self.hsv_lower]
        h1, s1, v1 = [int(v) for v in self.hsv_upper]
        relaxed_lower = np.array([max(0, h0 - 12), max(10, s0 - 35), max(10, v0 - 35)], dtype=np.uint8)
        relaxed_upper = np.array([min(180, h1 + 12), min(255, s1 + 35), min(255, v1 + 35)], dtype=np.uint8)
        candidate_ranges.append(("relaxed-current", relaxed_lower, relaxed_upper))

        for preset_name, preset in config.TABLE_COLOR_PRESETS.items():
            if preset_name in (self.current_table_color, "custom"):
                continue
            candidate_ranges.append((
                f"preset-{preset_name}",
                np.array(preset["hsv_lower"], dtype=np.uint8),
                np.array(preset["hsv_upper"], dtype=np.uint8),
            ))

        best_alt_rect = None
        best_alt_area = 0.0
        best_alt_mask = None
        best_alt_source = ""
        alt_min_area = max(8000.0, float(config.TABLE_MIN_AREA) * 0.55)

        for source_name, low, high in candidate_ranges:
            alt_mask = cv2.inRange(hsv_img, low, high)
            alt_mask = cv2.morphologyEx(alt_mask, cv2.MORPH_OPEN, kernel)
            alt_contours, _ = cv2.findContours(alt_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            for contour in alt_contours:
                area = cv2.contourArea(contour)
                if area > alt_min_area and area > best_alt_area:
                    best_alt_area = area
                    best_alt_rect = cv2.boundingRect(contour)
                    best_alt_mask = alt_mask
                    best_alt_source = source_name

        if best_alt_rect is not None and best_alt_mask is not None:
            x, y, w, h = best_alt_rect
            x, y, w, h = self._refine_table_roi_from_mask(best_alt_mask, [x, y, w, h])
            roi_rect, roi_status = self._repair_partial_table_roi(
                frame,
                [x, y, w, h],
                best_alt_source or "hsv_fallback",
            )
            if isinstance(best_alt_source, str) and best_alt_source.startswith("preset-"):
                preset_name = best_alt_source.replace("preset-", "", 1)
                preset = config.TABLE_COLOR_PRESETS.get(preset_name)
                if preset is not None:
                    self.current_table_color = preset_name
                    self.hsv_lower = np.array(preset["hsv_lower"], dtype=np.uint8)
                    self.hsv_upper = np.array(preset["hsv_upper"], dtype=np.uint8)

            x, y, w, h = self._commit_table_roi(frame, roi_rect, roi_status)

            print(f"✅ Table detected by fallback mask ({best_alt_source}): x={x}, y={y}, w={w}, h={h}")
            return True, [x, y, w, h]

        # 備用方案：如果找不到綠色區域，使用整個畫面
        print(f"⚠️  No green table found, using entire frame as fallback")
        h, w = frame.shape[:2]
        pocket_rect = self._estimate_table_roi_from_dark_pockets(frame)
        if pocket_rect is not None:
            x, y, w_table, h_table = pocket_rect
        else:
            margin_x = max(24, int(w * 0.055))
            margin_y = max(18, int(h * 0.045))
            x, y = margin_x, margin_y
            w_table = max(120, w - 2 * margin_x)
            h_table = max(80, int(h * 0.72))

        x, y, w_table, h_table = self._commit_table_roi(frame, [x, y, w_table, h_table], "geometry_fallback")

        print(f"🔄 Using fallback table: x={x}, y={y}, w={w_table}, h={h_table}")
        return True, [x, y, w_table, h_table]

    def _repair_partial_table_roi(self, frame: np.ndarray, rect: List[int], status: str) -> Tuple[List[int], str]:
        """啟動時 HSV 只抓到局部球桌時，改用袋口幾何補回完整 ROI。"""
        hsv_rect = self._clamp_table_roi(rect, frame.shape[:2])
        pocket_rect = self._estimate_table_roi_from_dark_pockets(frame)
        if pocket_rect is None:
            return hsv_rect, status

        _, _, hsv_w, hsv_h = hsv_rect
        _, _, pocket_w, pocket_h = pocket_rect
        hsv_area = max(1, hsv_w * hsv_h)
        pocket_area = max(1, pocket_w * pocket_h)

        width_gain = pocket_w / max(1, hsv_w)
        height_gain = pocket_h / max(1, hsv_h)
        area_gain = pocket_area / hsv_area
        _, frame_w = frame.shape[:2]
        hsv_width_ratio = hsv_w / max(1, frame_w)

        partial_hsv = (
            (width_gain >= 1.22 and area_gain >= 1.30)
            or (height_gain >= 1.22 and area_gain >= 1.30)
            or (hsv_width_ratio < 0.58 and pocket_w >= frame_w * 0.60)
        )
        if not partial_hsv:
            return hsv_rect, status

        print(
            "?? HSV table ROI looks partial; using pocket geometry "
            f"({hsv_rect} -> {pocket_rect}, area_gain={area_gain:.2f})"
        )
        return pocket_rect, f"{status}_pocket_expand"

    def _clamp_table_roi(self, rect: List[int], frame_shape: Tuple[int, int]) -> List[int]:
        """Clamp table ROI to frame bounds and keep a visible rectangle."""
        H, W = frame_shape[:2]
        x, y, w, h = [int(round(v)) for v in rect[:4]]
        x = max(0, min(W - 2, x))
        y = max(0, min(H - 2, y))
        w = max(2, min(W - x - 1, w))
        h = max(2, min(H - y - 1, h))
        return [x, y, w, h]

    def _estimate_table_roi_from_dark_pockets(self, frame: np.ndarray) -> Optional[List[int]]:
        """Estimate table ROI from large dark pocket/rail regions when cloth HSV fails."""
        H, W = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        dark_mask = cv2.inRange(hsv, np.array([0, 0, 0], dtype=np.uint8), np.array([180, 255, 72], dtype=np.uint8))
        kernel = np.ones((5, 5), np.uint8)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        centers: List[Tuple[float, float]] = []
        min_area = max(80.0, float(W * H) * 0.00018)
        max_area = float(W * H) * 0.06
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w < 8 or h < 8:
                continue
            cx = x + w / 2.0
            cy = y + h / 2.0
            if cy < H * 0.08 or cy > H * 0.88:
                continue
            centers.append((cx, cy))

        if len(centers) < 4:
            return None

        xs = [point[0] for point in centers]
        ys = [point[1] for point in centers]
        left = int(max(0, min(xs)))
        right = int(min(W - 1, max(xs)))
        top = int(max(0, min(ys)))
        bottom = int(min(H - 1, max(ys)))

        width = right - left
        height = bottom - top
        if width < W * 0.45 or height < H * 0.35:
            return None

        pad_x = max(18, int(width * 0.045))
        pad_y = max(18, int(height * 0.075))
        return self._clamp_table_roi(
            [left + pad_x, top + pad_y, width - 2 * pad_x, height - 2 * pad_y],
            (H, W),
        )



    def _refine_table_roi_from_mask(self, mask: np.ndarray, rect: List[int]) -> List[int]:
        """Refine table ROI by mask density projections to reduce outer-frame bias."""
        x, y, w, h = rect
        H, W = mask.shape[:2]

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(W, x + w)
        y1 = min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            return self._clamp_table_roi(rect, mask.shape[:2])

        roi = mask[y0:y1, x0:x1]
        if roi.size == 0:
            return self._clamp_table_roi(rect, mask.shape[:2])

        cols = np.count_nonzero(roi > 0, axis=0)
        rows = np.count_nonzero(roi > 0, axis=1)

        col_thresh = max(8, int(roi.shape[0] * 0.35))
        row_thresh = max(8, int(roi.shape[1] * 0.35))

        col_idx = np.where(cols > col_thresh)[0]
        row_idx = np.where(rows > row_thresh)[0]

        if len(col_idx) < 2 or len(row_idx) < 2:
            return self._clamp_table_roi(rect, mask.shape[:2])

        nx0 = x0 + int(col_idx[0])
        nx1 = x0 + int(col_idx[-1])
        ny0 = y0 + int(row_idx[0])
        ny1 = y0 + int(row_idx[-1])

        # keep a tiny inner margin to avoid including rail highlights
        inner = 2
        nx0 = min(max(0, nx0 + inner), W - 1)
        ny0 = min(max(0, ny0 + inner), H - 1)
        nx1 = max(min(W - 1, nx1 - inner), nx0 + 1)
        ny1 = max(min(H - 1, ny1 - inner), ny0 + 1)

        nw = nx1 - nx0
        nh = ny1 - ny0

        if nw < 120 or nh < 80:
            return self._clamp_table_roi(rect, mask.shape[:2])

        return self._clamp_table_roi([nx0, ny0, nw, nh], mask.shape[:2])

    def _estimate_default_holes(self, x: int, y: int, w: int, h: int) -> List[List[int]]:
        """Estimate six pocket centers from table geometry."""
        corner_offset = max(18, int(min(w, h) * 0.03))
        mid_offset = max(15, int(min(w, h) * 0.025))
        return [
            [x + corner_offset, y + corner_offset],
            [x + corner_offset, y + h - corner_offset],
            [x + w - corner_offset, y + corner_offset],
            [x + w - corner_offset, y + h - corner_offset],
            [x + w // 2, y + mid_offset],
            [x + w // 2, y + h - mid_offset],
        ]

    def _refine_holes_from_dark_regions(
        self,
        frame: np.ndarray,
        approx_holes: List[List[int]],
        table_roi: Optional[List[int]],
    ) -> List[List[int]]:
        """Refine pocket centers by local dark-region detection around estimated holes."""
        if table_roi is None:
            return approx_holes

        tx, ty, tw, th = table_roi
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        dark_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 80]))

        refined: List[List[int]] = []
        search_radius = max(24, int(min(tw, th) * 0.08))

        for hx, hy in approx_holes:
            x0 = max(tx, hx - search_radius)
            y0 = max(ty, hy - search_radius)
            x1 = min(tx + tw, hx + search_radius)
            y1 = min(ty + th, hy + search_radius)

            patch = dark_mask[y0:y1, x0:x1]
            if patch.size == 0:
                refined.append([hx, hy])
                continue

            contours, _ = cv2.findContours(patch, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_center = None
            best_score = -1.0

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 20:
                    continue

                peri = cv2.arcLength(cnt, True)
                circularity = (4.0 * math.pi * area / (peri * peri)) if peri > 1e-6 else 0.0
                m = cv2.moments(cnt)
                if m["m00"] <= 1e-6:
                    continue

                cx = int(m["m10"] / m["m00"]) + x0
                cy = int(m["m01"] / m["m00"]) + y0
                proximity = max(0.0, 1.0 - (math.hypot(cx - hx, cy - hy) / (search_radius + 1e-6)))
                score = (0.55 * proximity) + (0.30 * min(1.0, area / 500.0)) + (0.15 * circularity)

                if score > best_score:
                    best_score = score
                    best_center = [cx, cy]

            refined.append(best_center if best_center is not None else [hx, hy])

        return refined

    def _update_hole_bboxes(self, table_roi: Optional[List[int]]):
        """Update pocket collision boxes from pocket centers with adaptive radius."""
        if table_roi is None:
            self.hole_bboxes = []
            return

        _, _, tw, th = table_roi
        radius = max(14, int(min(tw, th) * 0.02))
        self.hole_bboxes = []
        for cx, cy in self.holes:
            self.hole_bboxes.append([cx - radius, cy - radius, cx + radius, cy + radius])


    def _is_ball_in_pocket_capture_zone(self, x: int, y: int, w: int, h: int) -> bool:
        """Return True when an object ball center enters pocket capture area."""
        if not self.holes or not self.table_roi:
            return False

        cx = x + w / 2.0
        cy = y + h / 2.0
        ball_r = max(1.0, min(w, h) / 2.0)

        _, _, tw, th = self.table_roi
        pocket_r = max(26.0, min(tw, th) * 0.06)
        capture_r = pocket_r + ball_r * 0.8

        for hx, hy in self.holes:
            if math.hypot(cx - hx, cy - hy) <= capture_r:
                return True
        return False

    def _is_pocket_false_positive_candidate(self, x: int, y: int, w: int, h: int, color_info: Dict[str, Any]) -> bool:
        """過濾袋口核心區域內的黑色/未知假球偵測。"""
        if not bool(getattr(config, "POCKET_FALSE_POSITIVE_FILTER_ENABLED", True)):
            return False
        if not self.holes or not self.table_roi:
            return False

        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        ball_r = max(1.0, min(w, h) / 2.0)

        _, _, tw, th = self.table_roi
        pocket_r = max(26.0, min(tw, th) * 0.06)
        core_ratio = float(getattr(config, "POCKET_FALSE_POSITIVE_CORE_RATIO", 0.62))
        core_r = max(12.0, pocket_r * core_ratio)

        near_pocket_core = False
        for hx, hy in self.holes:
            if math.hypot(cx - hx, cy - hy) <= (core_r + ball_r * 0.45):
                near_pocket_core = True
                break

        if not near_pocket_core:
            return False

        label = str(color_info.get("label", "Unknown"))
        dark_ratio_value = color_info.get("dark_ratio")
        if dark_ratio_value is None:
            dark_ratio_value = color_info.get("black_ratio", 0.0)
        dark_ratio = float(dark_ratio_value or 0.0)
        white_ratio = float(color_info.get("white_ratio") or 0.0)

        if label in ("Black", "Unknown"):
            return True
        return dark_ratio >= 0.45 and white_ratio <= 0.25

    def _suppress_duplicate_balls(self, balls: List[List[Any]], conf_idx: int) -> List[List[Any]]:
        """以球心距離抑制同顆球重複框，保留高信心候選。"""
        if not balls:
            return balls

        dedup_ratio = float(getattr(config, "BALL_DUPLICATE_CENTER_RATIO", 0.72))
        sorted_balls = sorted(balls, key=lambda b: float(b[conf_idx]), reverse=True)
        kept: List[List[Any]] = []

        for cand in sorted_balls:
            cx = float(cand[0]) + (float(cand[2]) / 2.0)
            cy = float(cand[1]) + (float(cand[3]) / 2.0)
            cr = max(1.0, min(float(cand[2]), float(cand[3])) / 2.0)

            is_dup = False
            for k in kept:
                kx = float(k[0]) + (float(k[2]) / 2.0)
                ky = float(k[1]) + (float(k[3]) / 2.0)
                kr = max(1.0, min(float(k[2]), float(k[3])) / 2.0)
                if math.hypot(cx - kx, cy - ky) <= (max(cr, kr) * dedup_ratio):
                    is_dup = True
                    break

            if not is_dup:
                kept.append(cand)

        return kept

    def _suppress_cue_tip_white_candidates(
        self,
        white_balls: List[List[Any]],
        cue_bbox: Optional[List[int]],
        cue_axis: Optional[CueAxis],
    ) -> List[List[Any]]:
        """移除貼近 cue 軸線的白球候選，避免白色桿頭被當母球。"""
        if not white_balls or not cue_bbox or len(cue_bbox) < 4 or not cue_axis or len(cue_axis) < 2:
            return white_balls
        if not bool(getattr(config, "CUE_TIP_WHITE_SUPPRESS_ENABLED", True)):
            return white_balls

        axis_a = cue_axis[0]
        axis_b = cue_axis[1]
        if not isinstance(axis_a, (list, tuple)) or not isinstance(axis_b, (list, tuple)) or len(axis_a) < 2 or len(axis_b) < 2:
            return white_balls

        cx, cy, cw, ch = [float(v) for v in cue_bbox[:4]]
        pad_ratio = max(0.0, float(getattr(config, "CUE_TIP_WHITE_SUPPRESS_PAD_RATIO", 0.20)))
        pad = max(2.0, min(cw, ch) * pad_ratio)
        left = cx - pad
        top = cy - pad
        right = cx + cw + pad
        bottom = cy + ch + pad
        ax, ay = float(axis_a[0]), float(axis_a[1])
        bx, by = float(axis_b[0]), float(axis_b[1])
        abx, aby = bx - ax, by - ay
        axis_len2 = (abx * abx) + (aby * aby)
        if axis_len2 <= 1e-6:
            return white_balls
        axis_dist_ratio = max(0.1, float(getattr(config, "CUE_TIP_WHITE_AXIS_DISTANCE_RATIO", 0.72)))
        endpoint_margin = max(0.0, float(getattr(config, "CUE_TIP_WHITE_AXIS_ENDPOINT_MARGIN_RATIO", 0.08)))

        filtered: List[List[Any]] = []
        for ball in white_balls:
            if len(ball) < 4:
                filtered.append(ball)
                continue
            bx, by, bw, bh = [float(v) for v in ball[:4]]
            geometry_debug = ball[5] if len(ball) > 5 and isinstance(ball[5], dict) else {}
            mask_center = geometry_debug.get("mask_center") if isinstance(geometry_debug, dict) else None
            if isinstance(mask_center, (list, tuple)) and len(mask_center) >= 2:
                try:
                    bcx = float(mask_center[0])
                    bcy = float(mask_center[1])
                except (TypeError, ValueError):
                    bcx = bx + bw / 2.0
                    bcy = by + bh / 2.0
            else:
                bcx = bx + bw / 2.0
                bcy = by + bh / 2.0
            if not (left <= bcx <= right and top <= bcy <= bottom):
                filtered.append(ball)
                continue

            t = ((bcx - ax) * abx + (bcy - ay) * aby) / axis_len2
            clamped_t = max(0.0, min(1.0, t))
            nearest_x = ax + (abx * clamped_t)
            nearest_y = ay + (aby * clamped_t)
            ball_r = max(1.0, min(bw, bh) / 2.0)
            distance_to_axis = math.hypot(bcx - nearest_x, bcy - nearest_y)
            on_cue_body = -endpoint_margin <= t <= (1.0 + endpoint_margin)

            mask_bbox = geometry_debug.get("mask_bbox") if isinstance(geometry_debug, dict) else None
            mask_looks_like_strip = False
            if isinstance(mask_bbox, (list, tuple)) and len(mask_bbox) >= 4:
                try:
                    mbw = max(1.0, float(mask_bbox[2]))
                    mbh = max(1.0, float(mask_bbox[3]))
                    mask_aspect = mbw / mbh
                    mask_looks_like_strip = mask_aspect >= 1.75 or mask_aspect <= 0.57
                except (TypeError, ValueError):
                    mask_looks_like_strip = False

            axis_threshold = max(3.0, ball_r * axis_dist_ratio)
            if mask_looks_like_strip:
                axis_threshold = max(axis_threshold, ball_r * 1.05)
            if on_cue_body and distance_to_axis <= axis_threshold:
                continue
            filtered.append(ball)
        return filtered

    @staticmethod
    def _point_to_segment_distance(p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        ax, ay = a
        bx, by = b
        px, py = p
        abx, aby = bx - ax, by - ay
        denom = abx * abx + aby * aby
        if denom <= 1e-9:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
        cx = ax + abx * t
        cy = ay + aby * t
        return math.hypot(px - cx, py - cy)

    def _current_projected_artifacts(self) -> Dict[str, List[Any]]:
        """回傳上一幀投影路線在相機座標的線段/點，用於避免 YOLO 把投影吃回偵測。"""
        artifacts: Dict[str, List[Any]] = {"segments": [], "points": [], "protected_points": []}
        manual = self.manual_projected_artifacts if isinstance(self.manual_projected_artifacts, dict) else {}
        for key in artifacts:
            artifacts[key].extend(manual.get(key, []) or [])

        if not self.route_planner_enabled:
            return artifacts

        plan = self.route_planner.last_plan if self.route_planner is not None else None
        if not isinstance(plan, dict):
            return artifacts
        route = plan.get("best_route")
        if not isinstance(route, dict):
            return artifacts

        for segment in route.get("route_segments", []) or []:
            if not isinstance(segment, dict):
                continue
            segment_type = str(segment.get("type", ""))
            if segment_type not in {"cue_to_contact", "object_to_pocket", "object_to_rail", "object_after_contact", "combo_transfer", "cue_after_contact"}:
                continue
            points = segment.get("points", [])
            if not isinstance(points, list):
                continue
            clean_points: List[Tuple[float, float]] = []
            for point in points:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    clean_points.append((float(point[0]), float(point[1])))
            for idx in range(len(clean_points) - 1):
                artifacts["segments"].append((segment_type, clean_points[idx], clean_points[idx + 1]))
            if segment_type in {"cue_after_contact", "object_after_contact"} and clean_points:
                artifacts["points"].append((segment_type, clean_points[-1]))

        landing = route.get("cue_landing_point")
        if isinstance(landing, list) and len(landing) >= 2:
            artifacts["points"].append(("cue_landing_point", (float(landing[0]), float(landing[1]))))
        metadata = route.get("metadata", {}) if isinstance(route.get("metadata"), dict) else {}
        ghost = metadata.get("ghost_ball")
        if isinstance(ghost, list) and len(ghost) >= 2:
            artifacts["points"].append(("ghost_ball", (float(ghost[0]), float(ghost[1]))))
        for segment in route.get("route_segments", []) or []:
            if not isinstance(segment, dict):
                continue
            segment_type = str(segment.get("type", ""))
            if segment_type not in {"object_to_pocket", "object_to_rail", "object_after_contact", "combo_transfer"}:
                continue
            points = segment.get("points", [])
            if isinstance(points, list) and points:
                first = points[0]
                if isinstance(first, (list, tuple)) and len(first) >= 2:
                    artifacts["protected_points"].append(("target_ball", (float(first[0]), float(first[1]))))
                    break
        return artifacts

    def set_manual_projected_artifacts(self, artifacts: Optional[Dict[str, List[Any]]]) -> None:
        """設定手動投影偽影遮罩；座標必須是相機全圖座標。"""
        clean: Dict[str, List[Any]] = {"segments": [], "points": [], "protected_points": []}
        if isinstance(artifacts, dict):
            for key in clean:
                items = artifacts.get(key, []) or []
                if isinstance(items, list):
                    clean[key] = items[:40]
        self.manual_projected_artifacts = clean

    def set_cue_laser_only(self, enabled: bool) -> None:
        """球型練習用：只解析球桿雷射線，跳過彩球後處理。"""
        enabled = bool(enabled)
        if self.cue_laser_only != enabled:
            self.cue_axis_cache = None
            self.cue_axis_missing_frames = 0
        self.cue_laser_only = enabled

    def _is_projected_ball_artifact(self, x: int, y: int, w: int, h: int, artifacts: Dict[str, List[Any]]) -> bool:
        if not artifacts:
            return False
        cx = float(x) + float(w) / 2.0
        cy = float(y) + float(h) / 2.0
        radius = max(4.0, min(float(w), float(h)) / 2.0)

        for _, point in artifacts.get("protected_points", []):
            if math.hypot(cx - point[0], cy - point[1]) <= max(26.0, radius * 2.2):
                return False

        for point_type, point in artifacts.get("points", []):
            if point_type == "ghost_ball":
                near_protected = any(
                    math.hypot(point[0] - protected[0], point[1] - protected[1]) <= max(34.0, radius * 2.5)
                    for _, protected in artifacts.get("protected_points", [])
                )
                if near_protected:
                    continue
            threshold = max(14.0, radius * 1.25)
            if point_type == "cue_landing_point":
                threshold = max(18.0, radius * 1.45)
            elif point_type == "ghost_ball":
                threshold = max(16.0, radius * 1.35)
            if math.hypot(cx - point[0], cy - point[1]) <= threshold:
                return True

        for segment_type, a, b in artifacts.get("segments", []):
            if segment_type not in {"cue_to_contact", "cue_laser", "cue_after_contact", "object_to_pocket", "object_to_rail", "combo_transfer", "object_after_contact"}:
                continue
            near_protected = any(
                math.hypot(cx - protected[0], cy - protected[1]) <= max(30.0, radius * 2.2)
                for _, protected in artifacts.get("protected_points", [])
            )
            if near_protected:
                continue
            threshold = max(10.0, radius * 0.95)
            if segment_type in {"cue_to_contact", "cue_laser"}:
                threshold = max(14.0, radius * 1.3)
            if self._point_to_segment_distance((cx, cy), a, b) <= threshold:
                return True
        return False

    def _is_projected_cue_artifact(self, x: int, y: int, w: int, h: int, artifacts: Dict[str, List[Any]]) -> bool:
        if not artifacts:
            return False
        cx = float(x) + float(w) / 2.0
        cy = float(y) + float(h) / 2.0
        long_side = max(float(w), float(h))
        short_side = max(1.0, min(float(w), float(h)))
        if long_side < 35.0 or (long_side / short_side) < 2.2:
            return False
        threshold = max(12.0, short_side * 1.4)
        for segment_type, a, b in artifacts.get("segments", []):
            if segment_type != "cue_to_contact":
                continue
            if self._point_to_segment_distance((cx, cy), a, b) <= threshold:
                return True
        return False

    def _is_cue_bbox_likely_table_edge(self, x: int, y: int, w: int, h: int) -> bool:
        """過濾 YOLO 將庫邊/桌緣誤判成 cue 的大框。"""
        if not self.table_roi:
            return False
        tx, ty, tw, th = [float(v) for v in self.table_roi]
        cx = float(x) + float(w) / 2.0
        cy = float(y) + float(h) / 2.0
        long_side = max(float(w), float(h))
        short_side = max(1.0, min(float(w), float(h)))
        aspect = long_side / short_side
        area_ratio = (float(w) * float(h)) / max(1.0, tw * th)
        edge_margin = max(24.0, min(tw, th) * 0.075)

        if area_ratio > 0.18:
            return True

        near_horizontal_rail = (cy <= ty + edge_margin or cy >= ty + th - edge_margin) and float(w) > float(h) * 2.4
        if near_horizontal_rail and (float(w) > tw * 0.22 or aspect > 4.0):
            return True

        near_vertical_rail = (cx <= tx + edge_margin or cx >= tx + tw - edge_margin) and float(h) > float(w) * 2.4
        if near_vertical_rail and (float(h) > th * 0.22 or aspect > 4.0):
            return True

        return False

    def _estimate_cue_axis_line(
        self,
        roi_img: np.ndarray,
        cue_bbox: List[int],
        offset: Tuple[int, int],
        apply_smoothing: bool = True,
    ) -> Optional[CueAxis]:
        """從球桿 bbox 內的邊緣點用 PCA 估算球桿自身長軸。"""
        if roi_img is None or not cue_bbox or len(cue_bbox) < 4:
            return None

        x, y, w, h = cue_bbox[:4]
        pad = max(6, int(round(max(w, h) * 0.08)))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(roi_img.shape[1], x + w + pad)
        y1 = min(roi_img.shape[0], y + h + pad)
        if x1 <= x0 or y1 <= y0:
            return None

        crop = roi_img[y0:y1, x0:x1]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        bbox_long = max(float(w), float(h))
        bbox_short = max(1.0, min(float(w), float(h)))
        bbox_aspect_ratio = bbox_long / bbox_short
        large_cue_bbox = bbox_long > (min(roi_img.shape[:2]) * 0.45) or bbox_aspect_ratio > 5.5
        square_like_cue_bbox = large_cue_bbox and bbox_aspect_ratio <= 2.2

        def select_elongated_component(mask: np.ndarray, sat: Optional[np.ndarray] = None, val: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
            """從大 bbox 裡挑出最像球桿的細長連通元件。"""
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
            best_points = None
            best_score = 0.0
            min_axis_len = max(45.0, min(float(max(w, h)) * 0.18, 180.0))
            for label_idx in range(1, num_labels):
                area = int(stats[label_idx, cv2.CC_STAT_AREA])
                if area < 35:
                    continue
                comp_ys, comp_xs = np.nonzero(labels == label_idx)
                if len(comp_xs) < 24:
                    continue
                points = np.column_stack((comp_xs.astype(np.float32), comp_ys.astype(np.float32)))
                mean = points.mean(axis=0)
                centered = points - mean
                cov = np.cov(centered, rowvar=False)
                eigvals, _ = np.linalg.eigh(cov)
                major = math.sqrt(max(float(eigvals[1]), 1e-6)) * 4.0
                minor = math.sqrt(max(float(eigvals[0]), 1e-6)) * 4.0
                elongation = major / max(1.0, minor)
                if major < min_axis_len or elongation < 3.2:
                    continue
                fill_ratio = area / max(1.0, major * max(1.0, minor))
                color_score = 1.0
                if sat is not None and val is not None:
                    comp_sat = float(np.median(sat[comp_ys, comp_xs]))
                    comp_val = float(np.median(val[comp_ys, comp_xs]))
                    sat_score = 1.0 - min(1.0, max(0.0, comp_sat - 65.0) / 95.0)
                    val_score = min(1.0, max(0.0, comp_val - 70.0) / 120.0)
                    color_score = max(0.35, 0.55 + sat_score * 0.30 + val_score * 0.15)
                score = major * elongation * min(1.0, fill_ratio * 2.5) * color_score
                if score > best_score:
                    best_score = score
                    best_points = points
            return best_points

        def select_elongated_mask_points(mask: np.ndarray) -> Optional[np.ndarray]:
            """連通元件被高光切斷時，改用整體球桿色像素估長軸。"""
            ys, xs = np.nonzero(mask)
            if len(xs) < 70:
                return None
            points = np.column_stack((xs.astype(np.float32), ys.astype(np.float32)))
            mean = points.mean(axis=0)
            centered = points - mean
            cov = np.cov(centered, rowvar=False)
            eigvals, _ = np.linalg.eigh(cov)
            major = math.sqrt(max(float(eigvals[1]), 1e-6)) * 4.0
            minor = math.sqrt(max(float(eigvals[0]), 1e-6)) * 4.0
            if major < max(65.0, float(max(w, h)) * 0.22):
                return None
            if (major / max(1.0, minor)) < 5.0:
                return None
            return points

        def dominant_diagonal_roi_mask(mask: np.ndarray) -> Optional[np.ndarray]:
            """大 bbox 只保留球桿色像素較多的對角線帶，避免背景/手部把中心線拉偏。"""
            crop_h, crop_w = mask.shape[:2]
            if crop_w < 24 or crop_h < 24:
                return None

            y_grid, x_grid = np.mgrid[0:crop_h, 0:crop_w].astype(np.float32)
            w1 = float(max(1, crop_w - 1))
            h1 = float(max(1, crop_h - 1))
            band_half_width = max(6.0, min(22.0, min(crop_w, crop_h) * 0.075))

            # 左上 -> 右下
            diag_a_dist = np.abs((h1 * x_grid) - (w1 * y_grid)) / math.hypot(h1, w1)
            # 右上 -> 左下
            diag_b_dist = np.abs((h1 * (w1 - x_grid)) - (w1 * y_grid)) / math.hypot(h1, w1)
            diag_a = diag_a_dist <= band_half_width
            diag_b = diag_b_dist <= band_half_width

            cue_pixels = mask > 0
            count_a = int(np.count_nonzero(cue_pixels & diag_a))
            count_b = int(np.count_nonzero(cue_pixels & diag_b))
            best_count = max(count_a, count_b)
            if best_count < max(36, int(min(crop_w, crop_h) * 0.18)):
                return None

            other_count = max(1, min(count_a, count_b))
            if best_count / other_count < 1.18:
                return None

            selected = diag_a if count_a >= count_b else diag_b
            return selected.astype(np.uint8) * 255

        def dominant_straight_line_points(mask: np.ndarray, hand_mask: Optional[np.ndarray]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            """從球桿色遮罩找最可信的長直線方向，避免手掌寬面先污染 PCA 方向。"""
            if mask is None or mask.size == 0:
                return None
            mask_points_y, mask_points_x = np.nonzero(mask)
            if len(mask_points_x) < 80:
                return None

            edge_img = cv2.Canny(mask, 40, 120)
            line_img = cv2.bitwise_or(edge_img, mask)
            min_line_len = max(42, int(min(float(max(w, h)) * 0.17, 180.0)))
            lines = cv2.HoughLinesP(
                line_img,
                1,
                np.pi / 180.0,
                threshold=18,
                minLineLength=min_line_len,
                maxLineGap=max(18, int(max(w, h) * 0.055)),
            )
            if lines is None:
                return None

            points = np.column_stack((mask_points_x.astype(np.float32), mask_points_y.astype(np.float32)))
            best_score = 0.0
            best_direction = None
            best_points = None
            for raw_line in lines[:, 0, :]:
                x_a, y_a, x_b, y_b = [float(v) for v in raw_line]
                dx = x_b - x_a
                dy = y_b - y_a
                length = math.hypot(dx, dy)
                if length < min_line_len:
                    continue
                ux = dx / length
                uy = dy / length
                normal = np.array([-uy, ux], dtype=np.float32)
                direction = np.array([ux, uy], dtype=np.float32)
                anchor = np.array([x_a, y_a], dtype=np.float32)
                rel = points - anchor
                along = rel @ direction
                dist = np.abs(rel @ normal)
                support_mask = (
                    (along >= -10.0)
                    & (along <= length + 10.0)
                    & (dist <= max(4.5, min(10.0, float(max(w, h)) * 0.014)))
                )
                support = int(np.count_nonzero(support_mask))
                if support < 24:
                    continue
                hand_penalty = 1.0
                if hand_mask is not None:
                    xs = np.clip(np.rint(points[support_mask, 0]).astype(np.int32), 0, hand_mask.shape[1] - 1)
                    ys = np.clip(np.rint(points[support_mask, 1]).astype(np.int32), 0, hand_mask.shape[0] - 1)
                    hand_ratio = int(np.count_nonzero(hand_mask[ys, xs])) / max(1, support)
                    hand_penalty = max(0.12, 1.0 - hand_ratio * 3.2)
                score = length * min(1.0, support / 48.0) * hand_penalty
                if score > best_score:
                    best_score = score
                    best_direction = direction
                    best_points = points[support_mask]

            if best_direction is None or best_points is None or len(best_points) < 24:
                return None
            return best_direction, best_points

        fit_points = None
        used_color_mask = False
        hand_block_mask = None
        preferred_direction = None
        preferred_line_points = None
        if len(crop.shape) == 3:
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            h_ch, s_ch, v_ch = cv2.split(hsv)
            hand_near_mask = (
                (v_ch > 85)
                & (s_ch > 55)
                & (
                    (h_ch <= 18)
                    | ((h_ch >= 19) & (h_ch <= 33) & (s_ch > 82))
                )
            )
            skin_mask = (
                (v_ch > 85)
                & (s_ch > 170)
                & (
                    (h_ch <= 17)
                    | ((h_ch >= 18) & (h_ch <= 30) & (s_ch > 205))
                )
            )
            tan_wood_mask = (
                (v_ch > 82)
                & (h_ch >= 8)
                & (h_ch <= 48)
                & (s_ch >= 28)
                & (s_ch <= 215)
            )
            pale_tip_mask = (v_ch > 95) & (s_ch < 90)
            low_sat_wood_mask = (
                (v_ch > 90)
                & (h_ch <= 62)
                & (s_ch < 115)
            )
            projected_overlay_mask = (
                ((h_ch >= 50) & (h_ch <= 78) & (s_ch > 130))
                | ((h_ch <= 7) & (s_ch > 145))
                | ((h_ch >= 20) & (h_ch <= 36) & (s_ch > 180))
            )
            cue_color_base = (
                ~((h_ch >= 82) & (h_ch <= 132) & (s_ch > 45))
                & ~projected_overlay_mask
                & ~skin_mask
            )
            wood_body_mask = (tan_wood_mask & cue_color_base).astype(np.uint8) * 255
            wood_assist_mask = ((pale_tip_mask | low_sat_wood_mask) & cue_color_base).astype(np.uint8) * 255
            kernel = np.ones((3, 3), np.uint8)
            hand_block_mask = cv2.dilate(hand_near_mask.astype(np.uint8) * 255, kernel, iterations=2) > 0
            wood_body_mask = cv2.morphologyEx(wood_body_mask, cv2.MORPH_OPEN, kernel, iterations=1)
            wood_body_mask = cv2.morphologyEx(wood_body_mask, cv2.MORPH_CLOSE, kernel)
            wood_assist_mask = cv2.morphologyEx(wood_assist_mask, cv2.MORPH_OPEN, kernel, iterations=1)
            wood_assist_mask = cv2.morphologyEx(wood_assist_mask, cv2.MORPH_CLOSE, kernel)
            wood_or_tip_mask = wood_body_mask
            if not (self.cue_laser_only and large_cue_bbox):
                wood_or_tip_mask = cv2.bitwise_or(wood_body_mask, wood_assist_mask)
            diagonal_roi = dominant_diagonal_roi_mask(wood_or_tip_mask) if square_like_cue_bbox else None
            if diagonal_roi is not None:
                wood_or_tip_mask = cv2.bitwise_and(wood_or_tip_mask, diagonal_roi)
            preferred_line = dominant_straight_line_points(wood_or_tip_mask, hand_block_mask)
            if preferred_line is not None:
                preferred_direction, preferred_line_points = preferred_line
            fit_points = select_elongated_component(wood_or_tip_mask, s_ch, v_ch)
            if fit_points is None:
                fit_points = select_elongated_mask_points(wood_or_tip_mask)
            if preferred_line_points is not None:
                fit_points = preferred_line_points
            used_color_mask = fit_points is not None

        edges = cv2.Canny(gray, 50, 120)
        if fit_points is None and not (self.cue_laser_only and large_cue_bbox):
            fit_points = select_elongated_component(edges)
        if fit_points is None and not (self.cue_laser_only and large_cue_bbox):
            ys, xs = np.nonzero(edges)
            if len(xs) >= 18:
                fit_points = np.column_stack((xs.astype(np.float32), ys.astype(np.float32)))

        best_line = None
        if fit_points is not None and len(fit_points) >= 18:
            points = fit_points
            if preferred_direction is not None:
                direction = preferred_direction.astype(np.float32)
            else:
                mean = points.mean(axis=0)
                centered = points - mean
                cov = np.cov(centered, rowvar=False)
                eigvals, eigvecs = np.linalg.eigh(cov)
                direction = eigvecs[:, int(np.argmax(eigvals))]
            norm = float(np.linalg.norm(direction))
            if norm > 1e-6:
                direction = direction / norm
                normal = np.array([-direction[1], direction[0]], dtype=np.float32)
                dir_projection = points @ direction
                normal_projection = points @ normal
                low = float(np.percentile(dir_projection, 4))
                high = float(np.percentile(dir_projection, 96))
                min_line_span = max(16.0, max(w, h) * (0.20 if used_color_mask else 0.35))
                if (high - low) >= min_line_span:
                    central_mask = (dir_projection >= low) & (dir_projection <= high)
                    central_normals = normal_projection[central_mask]
                    if used_color_mask and len(central_normals) >= 24:
                        n_min = float(np.percentile(central_normals, 2))
                        n_max = float(np.percentile(central_normals, 98))
                        normal_span = max(1.0, n_max - n_min)
                        bin_width = 4.0
                        bin_count = max(8, min(80, int(math.ceil(normal_span / bin_width))))
                        _, edges = np.histogram(central_normals, bins=bin_count, range=(n_min, n_max))
                        band_half_width = max(4.5, min(14.0, float(max(w, h)) * 0.018))
                        best_band_score = 0.0
                        best_band_center = float(np.median(central_normals))
                        best_band_mask = None
                        hand_point_mask = None
                        if hand_block_mask is not None:
                            point_xs = np.clip(np.rint(points[:, 0]).astype(np.int32), 0, hand_block_mask.shape[1] - 1)
                            point_ys = np.clip(np.rint(points[:, 1]).astype(np.int32), 0, hand_block_mask.shape[0] - 1)
                            hand_point_mask = hand_block_mask[point_ys, point_xs]
                        for edge_idx in range(len(edges) - 1):
                            band_center = float((edges[edge_idx] + edges[edge_idx + 1]) / 2.0)
                            candidate_mask = central_mask & (np.abs(normal_projection - band_center) <= band_half_width)
                            band_count = int(np.count_nonzero(candidate_mask))
                            if band_count < 12:
                                continue
                            candidate_dir = dir_projection[candidate_mask]
                            dir_span = float(np.percentile(candidate_dir, 95) - np.percentile(candidate_dir, 5))
                            hand_penalty = 1.0
                            if hand_point_mask is not None and hand_point_mask.shape[0] == candidate_mask.shape[0]:
                                hand_overlap = int(np.count_nonzero(candidate_mask & hand_point_mask))
                                hand_ratio = hand_overlap / max(1, band_count)
                                hand_penalty = max(0.18, 1.0 - hand_ratio * 2.8)
                            score = dir_span * min(1.0, band_count / 36.0) * hand_penalty
                            if score > best_band_score:
                                best_band_score = score
                                best_band_center = band_center
                                best_band_mask = candidate_mask
                        peak_center = best_band_center
                        band_mask = best_band_mask if best_band_mask is not None else (
                            central_mask & (np.abs(normal_projection - peak_center) <= band_half_width)
                        )
                        if int(np.count_nonzero(band_mask)) >= 18:
                            final_band_mask = band_mask
                            if hand_point_mask is not None and hand_point_mask.shape[0] == band_mask.shape[0]:
                                visible_band_mask = band_mask & ~hand_point_mask
                                if int(np.count_nonzero(visible_band_mask)) >= 18:
                                    visible_dir = dir_projection[visible_band_mask]
                                    visible_span = float(np.percentile(visible_dir, 95) - np.percentile(visible_dir, 5))
                                    if visible_span >= max(35.0, min_line_span * 0.35):
                                        final_band_mask = visible_band_mask
                            band_dir_projection = dir_projection[final_band_mask]
                            band_normal_projection = normal_projection[final_band_mask]
                            band_low = float(np.percentile(band_dir_projection, 3))
                            band_high = float(np.percentile(band_dir_projection, 97))
                            min_final_span = max(35.0, min_line_span * (0.35 if final_band_mask is not band_mask else 1.0))
                            if (band_high - band_low) >= min_final_span:
                                low = band_low
                                high = band_high
                                normal_center = float(np.median(band_normal_projection))
                            else:
                                normal_center = peak_center
                        else:
                            normal_center = peak_center
                    elif len(central_normals) >= 8:
                        n_low = float(np.percentile(central_normals, 8))
                        n_high = float(np.percentile(central_normals, 92))
                        normal_center = (n_low + n_high) / 2.0
                    else:
                        normal_center = float(np.median(normal_projection))
                    a_local = direction * low + normal * normal_center
                    b_local = direction * high + normal * normal_center
                    best_line = [
                        float(a_local[0] + x0 + offset[0]),
                        float(a_local[1] + y0 + offset[1]),
                        float(b_local[0] + x0 + offset[0]),
                        float(b_local[1] + y0 + offset[1]),
                    ]

        bbox_cx = float(x + offset[0]) + float(w) / 2.0
        bbox_cy = float(y + offset[1]) + float(h) / 2.0
        if best_line is None:
            if self._is_cue_bbox_likely_table_edge(x + offset[0], y + offset[1], w, h):
                return None
            bbox_aspect = max(float(w), float(h)) / max(1.0, min(float(w), float(h)))
            if bbox_aspect < 3.4:
                return None
            half_len = max(12.0, max(float(w), float(h)) / 2.0)
            if w >= h:
                best_line = [bbox_cx - half_len, bbox_cy, bbox_cx + half_len, bbox_cy]
            else:
                best_line = [bbox_cx, bbox_cy - half_len, bbox_cx, bbox_cy + half_len]

        ax, ay, bx, by = best_line
        dx = bx - ax
        dy = by - ay
        length = math.hypot(dx, dy)
        if length < 12.0:
            return None

        ux = dx / length
        uy = dy / length
        if apply_smoothing:
            best_line = self._smooth_cue_axis(best_line, (ux, uy))
        ax, ay, bx, by = best_line
        dx = bx - ax
        dy = by - ay
        length = math.hypot(dx, dy)
        if length < 12.0:
            return None
        ux = dx / length
        uy = dy / length
        return [[int(round(ax)), int(round(ay))], [int(round(bx)), int(round(by))], [float(ux), float(uy)]]

    def _extract_result_mask(self, result: Any, mask_idx: int, target_shape: Tuple[int, int]) -> Optional[np.ndarray]:
        """從 Ultralytics segmentation result 取出單一 mask，回傳 ROI 尺寸的 uint8 mask。"""
        if not bool(getattr(config, "CUE_SEGMENTATION_MASK_ENABLED", True)):
            return None
        masks = getattr(result, "masks", None)
        if masks is None:
            return None

        target_h, target_w = int(target_shape[0]), int(target_shape[1])
        if target_h <= 0 or target_w <= 0:
            return None

        try:
            polygons = getattr(masks, "xy", None)
            if polygons is not None and 0 <= mask_idx < len(polygons):
                polygon = np.asarray(polygons[mask_idx], dtype=np.float32)
                if polygon.ndim == 2 and polygon.shape[0] >= 3 and polygon.shape[1] >= 2:
                    points = np.rint(polygon[:, :2]).astype(np.int32)
                    points[:, 0] = np.clip(points[:, 0], 0, target_w - 1)
                    points[:, 1] = np.clip(points[:, 1], 0, target_h - 1)
                    mask_img = np.zeros((target_h, target_w), dtype=np.uint8)
                    cv2.fillPoly(mask_img, [points], 255)
                    if int(np.count_nonzero(mask_img)) > 0:
                        return mask_img
        except Exception:
            pass

        data = getattr(masks, "data", None)
        if data is None:
            return None
        try:
            if mask_idx < 0 or mask_idx >= len(data):
                return None
            mask = data[mask_idx]
            if hasattr(mask, "detach"):
                mask = mask.detach().cpu().numpy()
            else:
                mask = np.asarray(mask)
            if mask.ndim != 2:
                return None
            if mask.shape[:2] != (target_h, target_w):
                mask = cv2.resize(mask.astype(np.float32), (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            return (mask > 0.5).astype(np.uint8) * 255
        except Exception:
            return None

    def _estimate_cue_axis_from_mask(
        self,
        mask: np.ndarray,
        cue_bbox: List[int],
        offset: Tuple[int, int],
        apply_smoothing: bool = True,
    ) -> Optional[CueAxis]:
        """優先使用 YOLO segmentation mask 直接估球桿中心線。"""
        if mask is None or mask.size == 0 or not cue_bbox or len(cue_bbox) < 4:
            return None

        x, y, w, h = [int(v) for v in cue_bbox[:4]]
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(mask.shape[1], x + max(1, w))
        y1 = min(mask.shape[0], y + max(1, h))
        if x1 <= x0 or y1 <= y0:
            return None

        crop_mask = mask[y0:y1, x0:x1]
        if crop_mask.size == 0:
            return None
        kernel = np.ones((3, 3), np.uint8)
        crop_mask = cv2.morphologyEx(crop_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        crop_mask = cv2.morphologyEx(crop_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(crop_mask, 8)
        if num_labels <= 1:
            return None
        best_label = max(range(1, num_labels), key=lambda idx: int(stats[idx, cv2.CC_STAT_AREA]))
        if int(stats[best_label, cv2.CC_STAT_AREA]) < 32:
            return None

        ys, xs = np.nonzero(labels == best_label)
        if len(xs) < 24:
            return None
        points = np.column_stack((xs.astype(np.float32), ys.astype(np.float32)))
        ransac_line = self._fit_cue_axis_ransac(points, [x0, y0, x1 - x0, y1 - y0], offset)
        if ransac_line is not None:
            ax, ay, bx, by = ransac_line
            length = math.hypot(bx - ax, by - ay)
            if length >= 12.0:
                ux = (bx - ax) / length
                uy = (by - ay) / length
                centered_line = self._center_cue_axis_from_mask_sections(points, (ux, uy), [x0, y0, x1 - x0, y1 - y0], offset)
                if centered_line is not None:
                    ransac_line = centered_line
                    ax, ay, bx, by = ransac_line
                    length = math.hypot(bx - ax, by - ay)
                    if length < 12.0:
                        return None
                    ux = (bx - ax) / length
                    uy = (by - ay) / length
                if apply_smoothing:
                    ransac_line = self._smooth_cue_axis(ransac_line, (ux, uy))
                    ax, ay, bx, by = ransac_line
                    length = math.hypot(bx - ax, by - ay)
                    if length < 12.0:
                        return None
                    ux = (bx - ax) / length
                    uy = (by - ay) / length
                return [[int(round(ax)), int(round(ay))], [int(round(bx)), int(round(by))], [float(ux), float(uy)]]

        mean = points.mean(axis=0)
        centered = points - mean
        cov = np.cov(centered, rowvar=False)
        eigvals, eigvecs = np.linalg.eigh(cov)
        direction = eigvecs[:, int(np.argmax(eigvals))]
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-6:
            return None
        direction = direction / norm
        normal = np.array([-direction[1], direction[0]], dtype=np.float32)
        dir_projection = points @ direction
        normal_projection = points @ normal
        low = float(np.percentile(dir_projection, 2))
        high = float(np.percentile(dir_projection, 98))
        if (high - low) < max(18.0, max(float(w), float(h)) * 0.18):
            return None

        center_points = []
        span = high - low
        bin_count = max(8, min(28, int(span / 24.0)))
        bin_edges = np.linspace(low, high, bin_count + 1)
        for idx in range(bin_count):
            seg_low = float(bin_edges[idx])
            seg_high = float(bin_edges[idx + 1])
            seg_mask = (dir_projection >= seg_low) & (dir_projection <= seg_high)
            seg_count = int(np.count_nonzero(seg_mask))
            if seg_count < 6:
                continue
            seg_dir = float(np.median(dir_projection[seg_mask]))
            seg_normal = float(np.median(normal_projection[seg_mask]))
            center_points.append(direction * seg_dir + normal * seg_normal)

        if len(center_points) >= 4:
            centers = np.asarray(center_points, dtype=np.float32)
            center_mean = centers.mean(axis=0)
            center_cov = np.cov(centers - center_mean, rowvar=False)
            center_eigvals, center_eigvecs = np.linalg.eigh(center_cov)
            center_direction = center_eigvecs[:, int(np.argmax(center_eigvals))]
            center_norm = float(np.linalg.norm(center_direction))
            if center_norm > 1e-6:
                center_direction = center_direction / center_norm
                if float(center_direction @ direction) < 0:
                    center_direction = -center_direction
                direction = center_direction
                normal = np.array([-direction[1], direction[0]], dtype=np.float32)
                center_dir_projection = centers @ direction
                center_normal_projection = centers @ normal
                low = float(np.percentile(center_dir_projection, 2))
                high = float(np.percentile(center_dir_projection, 98))
                normal_center = float(np.median(center_normal_projection))
            else:
                normal_center = float(np.median(normal_projection))
        else:
            normal_center = float(np.median(normal_projection))
        a_local = direction * low + normal * normal_center
        b_local = direction * high + normal * normal_center
        line = [
            float(a_local[0] + x0 + offset[0]),
            float(a_local[1] + y0 + offset[1]),
            float(b_local[0] + x0 + offset[0]),
            float(b_local[1] + y0 + offset[1]),
        ]
        ax, ay, bx, by = line
        length = math.hypot(bx - ax, by - ay)
        if length < 12.0:
            return None
        ux = (bx - ax) / length
        uy = (by - ay) / length
        if apply_smoothing:
            line = self._smooth_cue_axis(line, (ux, uy))
            ax, ay, bx, by = line
            length = math.hypot(bx - ax, by - ay)
            if length < 12.0:
                return None
            ux = (bx - ax) / length
            uy = (by - ay) / length
        return [[int(round(ax)), int(round(ay))], [int(round(bx)), int(round(by))], [float(ux), float(uy)]]

    def _center_cue_axis_from_mask_sections(
        self,
        points: np.ndarray,
        direction: Tuple[float, float],
        local_bbox: List[int],
        offset: Tuple[int, int],
    ) -> Optional[List[float]]:
        """用 mask 橫截面上下邊界中點校正 RANSAC 可能選到的上/下緣。"""
        if points is None or len(points) < 36:
            return None
        ux, uy = float(direction[0]), float(direction[1])
        norm = math.hypot(ux, uy)
        if norm <= 1e-6:
            return None
        direction_vec = np.array([ux / norm, uy / norm], dtype=np.float32)
        normal = np.array([-direction_vec[1], direction_vec[0]], dtype=np.float32)

        dir_projection = points @ direction_vec
        normal_projection = points @ normal
        low = float(np.percentile(dir_projection, 3))
        high = float(np.percentile(dir_projection, 97))
        span = high - low
        if span < max(18.0, max(float(local_bbox[2]), float(local_bbox[3])) * 0.16):
            return None

        center_points = []
        bin_count = max(8, min(32, int(span / 20.0)))
        edges = np.linspace(low, high, bin_count + 1)
        for idx in range(bin_count):
            seg_mask = (dir_projection >= float(edges[idx])) & (dir_projection <= float(edges[idx + 1]))
            seg_count = int(np.count_nonzero(seg_mask))
            if seg_count < 6:
                continue
            seg_normals = normal_projection[seg_mask]
            n_low = float(np.percentile(seg_normals, 12))
            n_high = float(np.percentile(seg_normals, 88))
            width = n_high - n_low
            if width < 2.0 or width > max(36.0, min(float(local_bbox[2]), float(local_bbox[3])) * 0.50):
                continue
            seg_dir = float(np.median(dir_projection[seg_mask]))
            seg_normal_center = (n_low + n_high) / 2.0
            center_points.append(direction_vec * seg_dir + normal * seg_normal_center)

        if len(center_points) < 4:
            return None

        centers = np.asarray(center_points, dtype=np.float32)
        center_dir = centers @ direction_vec
        center_normal = centers @ normal
        c_low = float(np.percentile(center_dir, 3))
        c_high = float(np.percentile(center_dir, 97))
        c_normal = float(np.median(center_normal))
        if (c_high - c_low) < max(18.0, span * 0.45):
            return None

        x0, y0 = float(local_bbox[0]), float(local_bbox[1])
        a_local = direction_vec * c_low + normal * c_normal
        b_local = direction_vec * c_high + normal * c_normal
        return [
            float(a_local[0] + x0 + offset[0]),
            float(a_local[1] + y0 + offset[1]),
            float(b_local[0] + x0 + offset[0]),
            float(b_local[1] + y0 + offset[1]),
        ]

    def _fit_cue_axis_ransac(
        self,
        points: np.ndarray,
        local_bbox: List[int],
        offset: Tuple[int, int],
    ) -> Optional[List[float]]:
        """用 RANSAC 從候選 cue 像素中找最長、最細的主軸線。"""
        if points is None or len(points) < 36:
            return None

        x0, y0, w, h = [float(v) for v in local_bbox[:4]]
        bbox_long = max(w, h)
        min_span = max(28.0, bbox_long * 0.18)
        dist_thr = max(2.2, min(6.0, bbox_long * 0.012))
        sample_points = points
        if len(sample_points) > 420:
            step = max(1, len(sample_points) // 420)
            sample_points = sample_points[::step]

        candidates: List[np.ndarray] = []
        mean = points.mean(axis=0)
        centered = points - mean
        try:
            cov = np.cov(centered, rowvar=False)
            eigvals, eigvecs = np.linalg.eigh(cov)
            pca_dir = eigvecs[:, int(np.argmax(eigvals))].astype(np.float32)
            if float(np.linalg.norm(pca_dir)) > 1e-6:
                candidates.append(pca_dir / float(np.linalg.norm(pca_dir)))
        except Exception:
            pass

        # 角度掃描比隨機抽樣穩定，對細長球桿 mask 的離群凸塊更可控。
        for deg in range(0, 180, 4):
            rad = math.radians(float(deg))
            candidates.append(np.array([math.cos(rad), math.sin(rad)], dtype=np.float32))

        best_score = 0.0
        best_payload = None
        for direction in candidates:
            norm = float(np.linalg.norm(direction))
            if norm <= 1e-6:
                continue
            direction = direction / norm
            normal = np.array([-direction[1], direction[0]], dtype=np.float32)
            dir_projection = sample_points @ direction
            normal_projection = sample_points @ normal

            n_low = float(np.percentile(normal_projection, 5))
            n_high = float(np.percentile(normal_projection, 95))
            if n_high <= n_low:
                continue
            bin_width = max(2.5, dist_thr * 0.9)
            bin_count = max(6, min(80, int(math.ceil((n_high - n_low) / bin_width))))
            _, edges = np.histogram(normal_projection, bins=bin_count, range=(n_low, n_high))

            for idx in range(len(edges) - 1):
                center = float((edges[idx] + edges[idx + 1]) / 2.0)
                inlier_mask = np.abs(normal_projection - center) <= dist_thr
                inlier_count = int(np.count_nonzero(inlier_mask))
                if inlier_count < 18:
                    continue
                inlier_dir = dir_projection[inlier_mask]
                low = float(np.percentile(inlier_dir, 2))
                high = float(np.percentile(inlier_dir, 98))
                span = high - low
                if span < min_span:
                    continue
                density = min(1.0, inlier_count / max(24.0, span * 0.20))
                thinness = 1.0 / max(1.0, float(np.std(normal_projection[inlier_mask])) + 0.5)
                score = span * density * (0.75 + thinness)
                if score > best_score:
                    best_score = score
                    best_payload = (direction.copy(), center, low, high)

        if best_payload is None:
            return None

        direction, normal_center, low, high = best_payload
        normal = np.array([-direction[1], direction[0]], dtype=np.float32)
        a_local = direction * float(low) + normal * float(normal_center)
        b_local = direction * float(high) + normal * float(normal_center)
        return [
            float(a_local[0] + x0 + offset[0]),
            float(a_local[1] + y0 + offset[1]),
            float(b_local[0] + x0 + offset[0]),
            float(b_local[1] + y0 + offset[1]),
        ]

    def _recenter_cue_axis_with_image_axis(
        self,
        mask_axis: Optional[CueAxis],
        image_axis: Optional[CueAxis],
    ) -> Optional[CueAxis]:
        """保留 segmentation mask 的方向，但用影像桿身軸線修正平行偏移。"""
        if not mask_axis or not image_axis or len(mask_axis) < 3 or len(image_axis) < 3:
            return mask_axis

        try:
            ma, mb, md = mask_axis[0], mask_axis[1], mask_axis[2]
            ia, ib, idv = image_axis[0], image_axis[1], image_axis[2]
            mux, muy = float(md[0]), float(md[1])
            iux, iuy = float(idv[0]), float(idv[1])
            m_norm = math.hypot(mux, muy)
            i_norm = math.hypot(iux, iuy)
            if m_norm <= 1e-6 or i_norm <= 1e-6:
                return mask_axis
            mux, muy = mux / m_norm, muy / m_norm
            iux, iuy = iux / i_norm, iuy / i_norm
            if (mux * iux + muy * iuy) < 0:
                iux, iuy = -iux, -iuy

            direction_dot = abs(mux * iux + muy * iuy)
            if direction_dot < 0.92:
                return mask_axis

            max_len = math.hypot(float(mb[0]) - float(ma[0]), float(mb[1]) - float(ma[1]))
            img_len = math.hypot(float(ib[0]) - float(ia[0]), float(ib[1]) - float(ia[1]))
            if max_len < 12.0 or img_len < max(18.0, max_len * 0.35):
                return mask_axis

            mcx = (float(ma[0]) + float(mb[0])) / 2.0
            mcy = (float(ma[1]) + float(mb[1])) / 2.0
            icx = (float(ia[0]) + float(ib[0])) / 2.0
            icy = (float(ia[1]) + float(ib[1])) / 2.0
            nx, ny = -muy, mux
            normal_shift = ((icx - mcx) * nx) + ((icy - mcy) * ny)
            if abs(normal_shift) < 2.0:
                return mask_axis
            if abs(normal_shift) > max(28.0, min(max_len, img_len) * 0.18):
                return mask_axis

            recentered = [
                float(ma[0]) + nx * normal_shift,
                float(ma[1]) + ny * normal_shift,
                float(mb[0]) + nx * normal_shift,
                float(mb[1]) + ny * normal_shift,
            ]
            return [
                [int(round(recentered[0])), int(round(recentered[1]))],
                [int(round(recentered[2])), int(round(recentered[3]))],
                [float(mux), float(muy)],
            ]
        except Exception:
            return mask_axis

    def _refine_ball_geometry_from_mask(self, mask: np.ndarray, bbox: List[int]) -> Optional[Dict[str, Any]]:
        """使用 segmentation mask 估球的局部 bbox、中心與半徑。"""
        if mask is None or mask.size == 0 or not bbox or len(bbox) < 4:
            return None

        x, y, w, h = [int(v) for v in bbox[:4]]
        pad = max(3, int(round(max(w, h) * 0.10)))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(mask.shape[1], x + max(1, w) + pad)
        y1 = min(mask.shape[0], y + max(1, h) + pad)
        if x1 <= x0 or y1 <= y0:
            return None

        crop_mask = mask[y0:y1, x0:x1]
        if crop_mask.size == 0:
            return None
        kernel = np.ones((3, 3), np.uint8)
        crop_mask = cv2.morphologyEx(crop_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        crop_mask = cv2.morphologyEx(crop_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(crop_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        bbox_cx_local = float(x) + (float(w) / 2.0) - float(x0)
        bbox_cy_local = float(y) + (float(h) / 2.0) - float(y0)
        contour_payloads = []
        for candidate in contours:
            candidate_area = float(cv2.contourArea(candidate))
            if candidate_area < 20.0:
                continue
            moments = cv2.moments(candidate)
            if abs(float(moments.get("m00", 0.0))) > 1e-6:
                ccx = float(moments["m10"] / moments["m00"])
                ccy = float(moments["m01"] / moments["m00"])
            else:
                (ccx, ccy), _ = cv2.minEnclosingCircle(candidate)
            center_dist = math.hypot(ccx - bbox_cx_local, ccy - bbox_cy_local)
            score = candidate_area / (1.0 + center_dist * 0.35)
            contour_payloads.append((score, center_dist, candidate_area, candidate))
        if not contour_payloads:
            return None
        _, contour_center_dist, area, contour = max(contour_payloads, key=lambda item: item[0])
        area = float(cv2.contourArea(contour))
        if area < 20.0:
            return None
        (cx_local, cy_local), radius = cv2.minEnclosingCircle(contour)
        if radius < 3.0:
            return None
        bx, by, bw, bh = cv2.boundingRect(contour)
        mask_cx = float(x0 + cx_local)
        mask_cy = float(y0 + cy_local)
        bbox_cx = float(x) + (float(w) / 2.0)
        bbox_cy = float(y) + (float(h) / 2.0)
        base_radius = max(3.0, min(float(w), float(h)) / 2.0)
        max_center_shift = max(2.0, min(base_radius * 0.42, 8.0))
        center_dx = mask_cx - bbox_cx
        center_dy = mask_cy - bbox_cy
        center_shift = math.hypot(center_dx, center_dy)
        if center_shift > max_center_shift:
            scale = max_center_shift / max(center_shift, 1e-6)
            mask_cx = bbox_cx + center_dx * scale
            mask_cy = bbox_cy + center_dy * scale
        cx = (bbox_cx * 0.35) + (mask_cx * 0.65)
        cy = (bbox_cy * 0.35) + (mask_cy * 0.65)
        area_radius = math.sqrt(area / math.pi)
        blended_radius = (base_radius * 0.40) + (area_radius * 0.60)
        max_radius = max(base_radius * 1.15, area_radius * 1.28)
        if self.table_roi:
            table_short = float(min(self.table_roi[2], self.table_roi[3]))
            max_radius = min(max_radius, max(8.0, table_short * 0.060))
        robust_radius = min(float(radius), blended_radius * 1.08, area_radius * 1.15, max_radius)
        r = int(round(max(3.0, robust_radius)))
        return {
            "x": int(round(cx - r)),
            "y": int(round(cy - r)),
            "w": int(round(r * 2)),
            "h": int(round(r * 2)),
            "cx": cx,
            "cy": cy,
            "radius": r,
            "source": "segmentation_mask",
            "debug": {
                "mask_area": area,
                "mask_bbox": [int(x0 + bx), int(y0 + by), int(bw), int(bh)],
                "min_enclosing_radius": float(radius),
                "area_radius": float(area_radius),
                "bbox_radius": float(base_radius),
                "bbox_center": [float(bbox_cx), float(bbox_cy)],
                "mask_center": [float(x0 + cx_local), float(y0 + cy_local)],
                "contour_center_distance": float(contour_center_dist),
                "circle_bbox": [int(round(cx - r)), int(round(cy - r)), int(round(r * 2)), int(round(r * 2))],
            },
        }

    def _smooth_cue_axis_result(self, cue_axis: Optional[CueAxis]) -> Optional[CueAxis]:
        if not cue_axis or len(cue_axis) < 3:
            return cue_axis
        a, b, direction = cue_axis[0], cue_axis[1], cue_axis[2]
        if len(a) < 2 or len(b) < 2 or len(direction) < 2:
            return cue_axis
        smoothed = self._smooth_cue_axis(
            [float(a[0]), float(a[1]), float(b[0]), float(b[1])],
            (float(direction[0]), float(direction[1])),
        )
        ax, ay, bx, by = smoothed
        dx = bx - ax
        dy = by - ay
        length = math.hypot(dx, dy)
        if length < 12.0:
            return cue_axis
        return [
            [int(round(ax)), int(round(ay))],
            [int(round(bx)), int(round(by))],
            [float(dx / length), float(dy / length)],
        ]

    def _cached_cue_axis_result(self) -> Optional[CueAxis]:
        """短暫漏檢 cue 時沿用上一條可信軸線，避免雷射投影閃爍。"""
        cache = self.cue_axis_cache if isinstance(self.cue_axis_cache, dict) else None
        if not cache:
            return None

        max_missing = max(0, int(getattr(config, "CUE_AXIS_CACHE_MAX_MISSING_FRAMES", 5)))
        last_frame = int(cache.get("last_frame", 0))
        age = int(self.temporal_frame_id) - last_frame
        missing_frames = max(self.cue_axis_missing_frames, age)
        if missing_frames <= 0 or missing_frames > max_missing:
            return None

        cx = float(cache.get("cx", 0.0))
        cy = float(cache.get("cy", 0.0))
        half_len = float(cache.get("half_len", 0.0))
        ux = float(cache.get("ux", 0.0))
        uy = float(cache.get("uy", 0.0))
        norm = math.hypot(ux, uy)
        if half_len < 6.0 or norm <= 1e-6:
            return None
        ux /= norm
        uy /= norm
        ax = cx - ux * half_len
        ay = cy - uy * half_len
        bx = cx + ux * half_len
        by = cy + uy * half_len
        return [
            [int(round(ax)), int(round(ay))],
            [int(round(bx)), int(round(by))],
            [float(ux), float(uy)],
        ]

    def _score_cue_axis_candidate(self, cue_axis: CueAxis, conf: float) -> float:
        a, b = cue_axis[0], cue_axis[1]
        cx = (float(a[0]) + float(b[0])) / 2.0
        cy = (float(a[1]) + float(b[1])) / 2.0
        length = math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))
        score = float(conf) * 220.0 + min(160.0, length * 0.18)

        cache = self.cue_axis_cache if isinstance(self.cue_axis_cache, dict) else None
        if cache and (int(self.temporal_frame_id) - int(cache.get("last_frame", 0))) <= 6:
            prev_cx = float(cache.get("cx", cx))
            prev_cy = float(cache.get("cy", cy))
            shift = math.hypot(cx - prev_cx, cy - prev_cy)
            prev_ux = float(cache.get("ux", cue_axis[2][0]))
            prev_uy = float(cache.get("uy", cue_axis[2][1]))
            dot = abs(float(cue_axis[2][0]) * prev_ux + float(cue_axis[2][1]) * prev_uy)
            score += max(0.0, 70.0 - shift * 0.9)
            score += dot * 45.0
            if shift > 95.0 and conf < 0.75:
                score -= 130.0
        return score

    def _smooth_cue_axis(self, line: List[float], direction: Tuple[float, float]) -> List[float]:
        """平滑球桿軸線，降低 bbox/邊緣點造成的左右飄。"""
        ax, ay, bx, by = [float(v) for v in line]
        ux, uy = float(direction[0]), float(direction[1])
        cx = (ax + bx) / 2.0
        cy = (ay + by) / 2.0
        half_len = max(1.0, math.hypot(bx - ax, by - ay) / 2.0)

        cache = self.cue_axis_cache if isinstance(self.cue_axis_cache, dict) else None
        center_shift = 0.0
        reset_threshold = 0.0
        if cache and (int(self.temporal_frame_id) - int(cache.get("last_frame", 0))) > 6:
            cache = None
        if cache:
            prev_cx = float(cache.get("cx", cx))
            prev_cy = float(cache.get("cy", cy))
            center_shift = math.hypot(cx - prev_cx, cy - prev_cy)
            reset_ratio = float(getattr(config, "CUE_AXIS_RESET_SHIFT_RATIO", 0.62))
            reset_min = float(getattr(config, "CUE_AXIS_RESET_SHIFT_MIN", 32.0))
            reset_max = float(getattr(config, "CUE_AXIS_RESET_SHIFT_MAX", 140.0))
            reset_threshold = max(reset_min, min(reset_max, half_len * reset_ratio))
            if center_shift > reset_threshold:
                cache = None

        if cache:
            prev_ux = float(cache.get("ux", ux))
            prev_uy = float(cache.get("uy", uy))
            if (ux * prev_ux + uy * prev_uy) < 0:
                ux, uy = -ux, -uy
                ax, ay, bx, by = bx, by, ax, ay
                cx = (ax + bx) / 2.0
                cy = (ay + by) / 2.0

            prev_norm = math.hypot(prev_ux, prev_uy)
            if prev_norm > 1e-6:
                prev_ux /= prev_norm
                prev_uy /= prev_norm
                prev_cx = float(cache.get("cx", cx))
                prev_cy = float(cache.get("cy", cy))
                nx, ny = -prev_uy, prev_ux
                rel_x = cx - prev_cx
                rel_y = cy - prev_cy
                along_shift = (rel_x * prev_ux) + (rel_y * prev_uy)
                normal_shift = (rel_x * nx) + (rel_y * ny)
                normal_deadband = max(0.0, float(getattr(config, "CUE_AXIS_NORMAL_DEADBAND_PX", 3.0)))
                fast_shift = max(normal_deadband * 2.0, float(getattr(config, "CUE_AXIS_FAST_CONVERGE_SHIFT_PX", 14.0)))
                fast_end = max(fast_shift + 1.0, (reset_threshold or (fast_shift * 3.0)) * 0.75)
                fast_factor = max(0.0, min(1.0, (center_shift - fast_shift) / max(1.0, fast_end - fast_shift)))
                if abs(normal_shift) <= normal_deadband:
                    normal_shift = 0.0
                else:
                    normal_response = 0.42 + (0.46 * fast_factor)
                    normal_shift = math.copysign((abs(normal_shift) - normal_deadband) * normal_response, normal_shift)
                cx = prev_cx + prev_ux * along_shift + nx * normal_shift
                cy = prev_cy + prev_uy * along_shift + ny * normal_shift

            default_alpha = 0.78 if self.cue_laser_only else 0.68
            alpha = float(
                getattr(
                    config,
                    "CUE_AXIS_LASER_ONLY_SMOOTH_ALPHA" if self.cue_laser_only else "CUE_AXIS_SMOOTH_ALPHA",
                    default_alpha,
                )
            )
            alpha = max(0.0, min(0.92, alpha))
            fast_shift = max(
                float(getattr(config, "CUE_AXIS_NORMAL_DEADBAND_PX", 3.0)) * 2.0,
                float(getattr(config, "CUE_AXIS_FAST_CONVERGE_SHIFT_PX", 14.0)),
            )
            if center_shift > fast_shift:
                fast_alpha_name = (
                    "CUE_AXIS_LASER_ONLY_FAST_CONVERGE_ALPHA"
                    if self.cue_laser_only
                    else "CUE_AXIS_FAST_CONVERGE_ALPHA"
                )
                fast_alpha_default = 0.26 if self.cue_laser_only else 0.34
                fast_alpha = max(0.0, min(alpha, float(getattr(config, fast_alpha_name, fast_alpha_default))))
                fast_end = max(fast_shift + 1.0, (reset_threshold or (fast_shift * 3.0)) * 0.75)
                fast_factor = max(0.0, min(1.0, (center_shift - fast_shift) / max(1.0, fast_end - fast_shift)))
                alpha = alpha * (1.0 - fast_factor) + fast_alpha * fast_factor
            cx = float(cache.get("cx", cx)) * alpha + cx * (1.0 - alpha)
            cy = float(cache.get("cy", cy)) * alpha + cy * (1.0 - alpha)
            half_len = float(cache.get("half_len", half_len)) * 0.42 + half_len * 0.58
            ux = prev_ux * alpha + ux * (1.0 - alpha)
            uy = prev_uy * alpha + uy * (1.0 - alpha)
            norm = math.hypot(ux, uy)
            if norm > 1e-6:
                ux /= norm
                uy /= norm

        self.cue_axis_cache = {
            "cx": cx,
            "cy": cy,
            "half_len": half_len,
            "ux": ux,
            "uy": uy,
            "last_frame": int(self.temporal_frame_id),
        }
        self.cue_axis_missing_frames = 0
        return [cx - ux * half_len, cy - uy * half_len, cx + ux * half_len, cy + uy * half_len]

    def _estimate_cue_laser_line(self, cue_axis: Optional[CueAxis]) -> Optional[List[List[int]]]:
        """由球桿自身長軸延伸雷射線，不綁母球位置。"""
        if not cue_axis or len(cue_axis) < 3:
            return None

        a = cue_axis[0]
        b = cue_axis[1]
        direction = cue_axis[2]
        if len(a) < 2 or len(b) < 2 or len(direction) < 2:
            return None

        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        ux, uy = float(direction[0]), float(direction[1])
        table_w = float(self.table_roi[2]) if self.table_roi else 900.0
        extension = max(table_w * 1.1, 620.0)

        start = [int(round(bx)), int(round(by))]
        end = [int(round(bx + ux * extension)), int(round(by + uy * extension))]

        # 同時輸出反向候選，前端/投影端可看見球桿兩端方向；實機確認後再縮成單向。
        reverse_start = [int(round(ax)), int(round(ay))]
        reverse_end = [int(round(ax - ux * extension)), int(round(ay - uy * extension))]
        return [start, end, reverse_start, reverse_end]

    # ==================== 主處理函式 ====================
    def process_frame(self, frame: np.ndarray, draw_annotations: bool = True) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        每幀處理主邏輯：
        1. 偵測球桌（首次）
        2. 裁切 ROI
        3. YOLO 推論
        4. 解析球體並進行物理預測
        5. 繪製結果
        """
        self.temporal_frame_id += 1
        self._sync_manual_table_roi_to_frame(frame)
        # 1. 檢查球桌
        if not self.table_roi:
            success, _ = self.detect_table(frame)
            if not success:
                print("⚠️  Table not detected, scanning...")
                return frame, {"status": "scanning_table"}
            else:
                print(f"✅ Table detected: {self.table_roi}")

        # 2. 裁切 ROI
        masked_frame = frame

        assert self.table_roi is not None
        tx, ty, tw, th = self.table_roi
        roi_img = masked_frame[ty:ty+th, tx:tx+tw].copy()

        # 3. YOLO 推論
        results = self.model.predict(
            roi_img,
            imgsz=config.IMG_SIZE,
            conf=self.conf_thr,
            iou=self.iou_thr,
            device=self.infer_device,
            half=self.use_half,
            verbose=False,
            stream=False
        )

        # Low-recall fallback: rerun YOLO with larger image size and lower threshold.
        second_pass_allowed = not (
            self.cue_laser_only
            and bool(getattr(config, "CUE_LASER_ONLY_DISABLE_SECOND_PASS", True))
        )
        if config.SECOND_PASS_ENABLED and second_pass_allowed:
            first_det_count = self._count_result_boxes(results)
            first_ball_count = self._count_result_boxes(results, labels={"white-ball", "color-ball"})
            min_ball_count = max(0, int(getattr(config, "SECOND_PASS_MIN_BALLS", 0)))
            ball_recall_low = min_ball_count > 0 and first_ball_count < min_ball_count
            skip_second_pass = (
                bool(getattr(config, "SECOND_PASS_SKIP_WHEN_CUE_FOUND", True))
                and self._result_has_label(results, "cue")
                and not ball_recall_low
            )
            if (first_det_count < config.SECOND_PASS_MIN_OBJECTS or ball_recall_low) and not skip_second_pass:
                second_results = self.model.predict(
                    roi_img,
                    imgsz=config.SECOND_PASS_IMG_SIZE,
                    conf=config.SECOND_PASS_CONF_THR,
                    iou=config.SECOND_PASS_IOU_THR,
                    device=self.infer_device,
                    half=self.use_half,
                    verbose=False,
                    stream=False
                )
                second_det_count = self._count_result_boxes(second_results)
                second_ball_count = self._count_result_boxes(second_results, labels={"white-ball", "color-ball"})
                if second_det_count > first_det_count or second_ball_count > first_ball_count:
                    print(
                        "🔁 Second-pass YOLO applied "
                        f"({first_det_count} -> {second_det_count}, balls {first_ball_count} -> {second_ball_count}, "
                        f"imgsz={config.SECOND_PASS_IMG_SIZE}, conf={config.SECOND_PASS_CONF_THR})"
                    )
                    results = second_results

        # 4. 解析球體
        data_packet = self._analyze_balls(results, roi_img, offset=(tx, ty))

        # 5. 繪製到原圖。none 模式直接回傳輸入 frame，避免額外 overlay copy。
        annotation_mode = str(getattr(config, "TRACKER_ANNOTATION_MODE", "full")).strip().lower()
        if draw_annotations and bool(getattr(config, "TRACKER_DRAW_ANNOTATIONS", True)) and annotation_mode != "none":
            final_frame = frame.copy()
            self._draw_annotations(final_frame, data_packet)
        else:
            final_frame = frame

        return final_frame, data_packet

    def render_annotations(self, frame: np.ndarray, data_packet: Dict[str, Any]) -> np.ndarray:
        """把最新 metadata 畫到指定 frame；用於主串流非阻塞合成 overlay。"""
        annotation_mode = str(getattr(config, "TRACKER_ANNOTATION_MODE", "full")).strip().lower()
        source_timestamp = data_packet.get("_source_timestamp") if isinstance(data_packet, dict) else None
        max_age_ms = int(getattr(config, "LAST_GOOD_OVERLAY_HOLD_MS", getattr(config, "OVERLAY_METADATA_MAX_AGE_MS", 120)))
        if max_age_ms > 0 and isinstance(source_timestamp, (int, float)):
            if (time.time() - float(source_timestamp)) * 1000.0 > max_age_ms:
                return frame

        if (
            annotation_mode == "none"
            or not bool(getattr(config, "TRACKER_DRAW_ANNOTATIONS", True))
            or not isinstance(data_packet, dict)
        ):
            return frame

        annotated = frame.copy()
        self._draw_annotations(annotated, data_packet)
        return annotated

    def render_annotations_scaled(
        self,
        frame: np.ndarray,
        data_packet: Dict[str, Any],
        output_size: Tuple[int, int],
    ) -> np.ndarray:
        """先縮放影像與 metadata，再在輸出尺寸上繪圖，降低 monitor overlay 成本。"""
        output_w, output_h = output_size
        source_h, source_w = frame.shape[:2]
        if source_w <= 0 or source_h <= 0:
            return frame

        scaled_frame = cv2.resize(frame, (output_w, output_h))
        if not isinstance(data_packet, dict):
            return scaled_frame

        annotation_mode = str(getattr(config, "TRACKER_ANNOTATION_MODE", "full")).strip().lower()
        if (
            annotation_mode == "none"
            or not bool(getattr(config, "TRACKER_DRAW_ANNOTATIONS", True))
        ):
            return scaled_frame

        scale_x = output_w / float(source_w)
        scale_y = output_h / float(source_h)
        if not bool(getattr(config, "MONITOR_OVERLAY_CACHE_ENABLED", False)):
            scaled_packet = self._scale_annotation_packet(data_packet, scale_x, scale_y)
            self._draw_annotations(scaled_frame, scaled_packet)
            return scaled_frame

        cache_key = self._scaled_overlay_cache_key_for(
            data_packet,
            annotation_mode,
            source_w,
            source_h,
            output_w,
            output_h,
        )
        if (
            self._scaled_overlay_layer_cache is not None
            and self._scaled_overlay_mask_cache is not None
            and self._scaled_overlay_cache_key == cache_key
        ):
            self._scaled_overlay_cache_hits += 1
            scaled_frame[self._scaled_overlay_mask_cache] = self._scaled_overlay_layer_cache[self._scaled_overlay_mask_cache]
            return scaled_frame

        self._scaled_overlay_cache_misses += 1
        scaled_packet = self._scale_annotation_packet(data_packet, scale_x, scale_y)
        sentinel = np.full((output_h, output_w, 3), (1, 2, 3), dtype=np.uint8)
        self._draw_annotations(sentinel, scaled_packet)
        self._scaled_overlay_layer_cache = sentinel
        self._scaled_overlay_mask_cache = np.any(sentinel != (1, 2, 3), axis=2)
        self._scaled_overlay_cache_key = cache_key
        scaled_frame[self._scaled_overlay_mask_cache] = self._scaled_overlay_layer_cache[self._scaled_overlay_mask_cache]
        return scaled_frame

    def _scaled_overlay_cache_key_for(
        self,
        data_packet: Dict[str, Any],
        annotation_mode: str,
        source_w: int,
        source_h: int,
        output_w: int,
        output_h: int,
    ) -> str:
        source_id = data_packet.get("_source_frame_id")
        source_timestamp = data_packet.get("_source_timestamp")
        if source_id is not None or source_timestamp is not None:
            return json.dumps(
                {
                    "mode": annotation_mode,
                    "source": [source_w, source_h],
                    "output": [output_w, output_h],
                    "source_id": source_id,
                    "source_timestamp": source_timestamp,
                },
                sort_keys=True,
                default=str,
                separators=(",", ":"),
            )

        return json.dumps(
            {
                "mode": annotation_mode,
                "source": [source_w, source_h],
                "output": [output_w, output_h],
                "table_roi": data_packet.get("table_roi"),
                "white_ball": data_packet.get("white_ball"),
                "balls": data_packet.get("balls"),
                "cue": data_packet.get("cue"),
                "multi_plan": data_packet.get("multi_plan"),
                "prediction": data_packet.get("prediction"),
                "aim_assist": data_packet.get("aim_assist"),
            },
            sort_keys=True,
            ensure_ascii=True,
            default=str,
            separators=(",", ":"),
        )

    def get_monitor_overlay_cache_stats(self) -> Dict[str, Any]:
        """回傳 monitor overlay 圖層快取狀態，供效能診斷 API 使用。"""
        return {
            "hits": self._scaled_overlay_cache_hits,
            "misses": self._scaled_overlay_cache_misses,
            "has_layer": self._scaled_overlay_layer_cache is not None,
            "has_mask": self._scaled_overlay_mask_cache is not None,
        }

    def _scale_annotation_packet(self, data: Dict[str, Any], scale_x: float, scale_y: float) -> Dict[str, Any]:
        scaled = dict(data)

        def scale_bbox(bbox: Any):
            if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
                return bbox
            try:
                return [
                    int(round(float(bbox[0]) * scale_x)),
                    int(round(float(bbox[1]) * scale_y)),
                    int(round(float(bbox[2]) * scale_x)),
                    int(round(float(bbox[3]) * scale_y)),
                ]
            except (TypeError, ValueError):
                return bbox

        def scale_point(point: Any):
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return point
            try:
                return [int(round(float(point[0]) * scale_x)), int(round(float(point[1]) * scale_y))]
            except (TypeError, ValueError):
                return point

        def scale_route(route: Any):
            if not isinstance(route, dict):
                return route
            next_route = dict(route)
            segments = []
            for segment in route.get("route_segments", []) or []:
                if not isinstance(segment, dict):
                    continue
                next_segment = dict(segment)
                next_segment["points"] = [scale_point(point) for point in segment.get("points", []) or []]
                segments.append(next_segment)
            next_route["route_segments"] = segments
            if isinstance(route.get("cue_landing_point"), (list, tuple)):
                next_route["cue_landing_point"] = scale_point(route.get("cue_landing_point"))
            zone = route.get("cue_landing_zone")
            if isinstance(zone, dict):
                next_zone = dict(zone)
                if isinstance(zone.get("center"), (list, tuple)):
                    next_zone["center"] = scale_point(zone.get("center"))
                try:
                    next_zone["radius"] = int(round(float(zone.get("radius", 34)) * ((scale_x + scale_y) / 2.0)))
                except (TypeError, ValueError):
                    pass
                next_route["cue_landing_zone"] = next_zone
            position_play = route.get("position_play")
            if isinstance(position_play, dict):
                next_position_play = dict(position_play)
                next_ball = position_play.get("next_ball")
                if isinstance(next_ball, dict):
                    next_next_ball = dict(next_ball)
                    if isinstance(next_ball.get("center"), (list, tuple)):
                        next_next_ball["center"] = scale_point(next_ball.get("center"))
                    next_position_play["next_ball"] = next_next_ball
                cue_after = position_play.get("cue_ball_after_contact")
                if isinstance(cue_after, dict):
                    next_cue_after = dict(cue_after)
                    if isinstance(cue_after.get("expected_point"), (list, tuple)):
                        next_cue_after["expected_point"] = scale_point(cue_after.get("expected_point"))

                    def scale_zone(zone: Any):
                        if not isinstance(zone, dict):
                            return zone
                        next_zone = dict(zone)
                        if isinstance(zone.get("center"), (list, tuple)):
                            next_zone["center"] = scale_point(zone.get("center"))
                        try:
                            next_zone["radius"] = int(round(float(zone.get("radius", 24)) * ((scale_x + scale_y) / 2.0)))
                        except (TypeError, ValueError):
                            pass
                        return next_zone

                    next_cue_after["target_zone"] = scale_zone(cue_after.get("target_zone"))
                    next_cue_after["avoid_zones"] = [scale_zone(zone) for zone in cue_after.get("avoid_zones", []) or []]
                    next_position_play["cue_ball_after_contact"] = next_cue_after
                next_route["position_play"] = next_position_play
            return next_route

        scaled["white_ball"] = scale_bbox(data.get("white_ball"))
        scaled["cue"] = scale_bbox(data.get("cue"))
        cue_laser_line = data.get("cue_laser_line")
        if isinstance(cue_laser_line, list):
            scaled["cue_laser_line"] = [scale_point(point) for point in cue_laser_line]
        cue_axis = data.get("cue_axis")
        if isinstance(cue_axis, (list, tuple)) and len(cue_axis) >= 3:
            scaled["cue_axis"] = [scale_point(cue_axis[0]), scale_point(cue_axis[1]), cue_axis[2]]
        scaled["table_roi"] = scale_bbox(data.get("table_roi"))
        scaled["table_roi_raw"] = scale_bbox(data.get("table_roi_raw"))
        scaled["table_roi_points"] = [scale_point(point) for point in data.get("table_roi_points", []) or []]
        scaled["holes"] = [scale_point(point) for point in data.get("holes", []) or []]
        scaled["raw_yolo_boxes"] = []
        for raw_box in data.get("raw_yolo_boxes", []) or []:
            if not isinstance(raw_box, dict):
                continue
            next_box = dict(raw_box)
            try:
                next_box["x"] = int(round(float(raw_box.get("x", 0)) * scale_x))
                next_box["y"] = int(round(float(raw_box.get("y", 0)) * scale_y))
                next_box["w"] = int(round(float(raw_box.get("w", 0)) * scale_x))
                next_box["h"] = int(round(float(raw_box.get("h", 0)) * scale_y))
            except (TypeError, ValueError):
                pass
            scaled["raw_yolo_boxes"].append(next_box)
        scaled["balls"] = []
        for ball in data.get("balls", []) or []:
            if not isinstance(ball, dict):
                continue
            next_ball = dict(ball)
            try:
                next_ball["x"] = int(round(float(ball.get("x", 0)) * scale_x))
                next_ball["y"] = int(round(float(ball.get("y", 0)) * scale_y))
                next_ball["w"] = int(round(float(ball.get("w", 0)) * scale_x))
                next_ball["h"] = int(round(float(ball.get("h", 0)) * scale_y))
                next_ball["radius"] = max(1, int(round(float(ball.get("radius", 0)) * ((scale_x + scale_y) / 2.0))))
            except (TypeError, ValueError):
                pass
            scaled["balls"].append(next_ball)

        multi_plan = data.get("multi_plan")
        if isinstance(multi_plan, dict):
            next_plan = dict(multi_plan)
            if isinstance(multi_plan.get("best_route"), dict):
                next_plan["best_route"] = scale_route(multi_plan.get("best_route"))
            routes = []
            for route in multi_plan.get("routes", []) or []:
                routes.append(scale_route(route))
            if routes:
                next_plan["routes"] = routes
            scaled["multi_plan"] = next_plan

        prediction = data.get("prediction")
        if isinstance(prediction, dict):
            next_prediction = dict(prediction)
            next_prediction["paths"] = [scale_point(point) for point in prediction.get("paths", []) or []]
            scaled["prediction"] = next_prediction

        aim_assist = data.get("aim_assist")
        if isinstance(aim_assist, dict):
            next_aim = dict(aim_assist)
            for key in ("cue_to_target", "target_to_hole", "separation_line"):
                raw_points = aim_assist.get(key)
                if isinstance(raw_points, list):
                    next_aim[key] = [scale_point(point) for point in raw_points]
            ghost = aim_assist.get("ghost_ball")
            if isinstance(ghost, dict):
                next_ghost = dict(ghost)
                if "cx" in ghost and "cy" in ghost:
                    point = scale_point([ghost.get("cx"), ghost.get("cy")])
                    next_ghost["cx"], next_ghost["cy"] = point[0], point[1]
                try:
                    next_ghost["r"] = int(round(float(ghost.get("r", 0)) * ((scale_x + scale_y) / 2.0)))
                except (TypeError, ValueError):
                    pass
                next_aim["ghost_ball"] = next_ghost
            scaled["aim_assist"] = next_aim

        return scaled

    def _count_result_boxes(self, results, labels: Optional[set[str]] = None) -> int:
        total = 0
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            if labels is None:
                total += len(boxes)
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                if self.model.names[cls_id] in labels:
                    total += 1
        return total

    def _result_has_label(self, results, label_name: str) -> bool:
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if label_name == "cue" and conf < float(getattr(config, "CUE_CONF_THR", 0.35)):
                    continue
                if self.model.names[cls_id] == label_name:
                    return True
        return False

    def _majority_vote(self, values: List[str], min_stable: int, fallback: str) -> str:
        counts: Dict[str, int] = {}
        for v in values:
            if not v:
                continue
            counts[v] = counts.get(v, 0) + 1

        if not counts:
            return fallback

        best_label = fallback
        best_count = 0
        for k, c in counts.items():
            if c > best_count:
                best_count = c
                best_label = k

        if best_count >= min_stable:
            return best_label
        return fallback

    def _style_signal_strength(self, color_info: Dict[str, Any], style: str) -> float:
        """估計目前 style 觀測的可信度，供跨幀鎖定切換使用。"""
        debug = color_info.get("debug") or {}
        white_ratio = float(color_info.get("white_ratio", 0.0))
        center_white_ratio = float(debug.get("center_white_ratio", 0.0))
        core_main_ratio = float(debug.get("core_main_ratio", 0.0))
        mid_main_ratio = float(debug.get("mid_main_ratio", 0.0))
        outer_white_ratio = float(debug.get("outer_white_ratio", 0.0))
        core_white_ratio = float(debug.get("core_white_ratio", 0.0))

        if style == "Stripe":
            if center_white_ratio >= 0.52 and white_ratio >= 0.16:
                return 1.0
            if outer_white_ratio >= 0.30 and white_ratio >= 0.18:
                return 1.0
            if outer_white_ratio >= 0.24 and white_ratio >= 0.14:
                return 0.85
            if white_ratio >= 0.18 and (outer_white_ratio - core_white_ratio) >= 0.08:
                return 0.7
            return 0.35

        if style == "Solid":
            if white_ratio <= 0.12 and core_main_ratio >= 0.48 and mid_main_ratio >= 0.38:
                return 1.0
            if white_ratio <= 0.18 and core_main_ratio >= 0.38 and mid_main_ratio >= 0.30:
                return 0.82
            if white_ratio <= 0.22 and core_main_ratio >= 0.32:
                return 0.65
            return 0.3

        return 0.0

    def _label_signal_strength(self, color_info: Dict[str, Any]) -> float:
        """估計目前顏色分類的可信度，供跨幀 label lock 使用。"""
        label = str(color_info.get("label", "Unknown"))
        if label not in self.COLOR_TO_NUM:
            return 0.0

        score = color_info.get("template_score")
        if score is None:
            score_f = 0.72
        else:
            try:
                score_f = float(score)
            except (TypeError, ValueError):
                score_f = 0.72

        base = max(0.0, min(1.0, 1.0 - (score_f / 0.72)))
        hue = color_info.get("hue")
        if hue is None:
            hue_f = -1.0
        else:
            try:
                hue_f = float(hue)
            except (TypeError, ValueError):
                hue_f = -1.0

        if hue_f >= 0 and label in self.COLOR_HUE_CENTER:
            hue_diff = self._circular_hue_diff(hue_f, self.COLOR_HUE_CENTER[label])
            hue_bonus = max(0.0, 1.0 - (hue_diff / 34.0))
            base = max(base, hue_bonus * 0.85)

        return float(max(0.0, min(1.0, base)))

    @staticmethod
    def _style_lock_threshold(style: str) -> float:
        if style == "Stripe":
            return 0.68
        if style == "Solid":
            return 0.92
        return 1.0

    def _smooth_color_info_temporal(self, cx: float, cy: float, color_info: Dict[str, Any]) -> Dict[str, Any]:
        """以位置近鄰匹配歷史樣本，對 color/style 做短時窗平滑。"""
        if not bool(getattr(config, "COLOR_TEMPORAL_SMOOTH_ENABLED", True)):
            return color_info

        window = max(2, int(getattr(config, "COLOR_TEMPORAL_WINDOW", 4)))
        match_dist = float(getattr(config, "COLOR_TEMPORAL_MATCH_DIST", 28.0))
        min_stable = max(1, int(getattr(config, "COLOR_TEMPORAL_MIN_STABLE", 2)))
        max_age = max(window * 2, 6)

        # 清除過舊快取
        self.temporal_color_cache = [
            item for item in self.temporal_color_cache
            if (self.temporal_frame_id - int(item.get("last_frame", 0))) <= max_age
        ]

        label_raw = str(color_info.get("label", "Unknown"))
        style_raw = str(color_info.get("style", "Unknown"))
        style_strength_raw = self._style_signal_strength(color_info, style_raw)
        label_strength_raw = self._label_signal_strength(color_info)

        best_idx = -1
        best_d = float("inf")
        for i, item in enumerate(self.temporal_color_cache):
            d = math.hypot(float(item.get("x", 0.0)) - float(cx), float(item.get("y", 0.0)) - float(cy))
            if d < best_d and d <= match_dist:
                best_d = d
                best_idx = i

        if best_idx < 0:
            initial_lock = None
            initial_lock_label = None
            if style_raw in ("Solid", "Stripe") and style_strength_raw >= self._style_lock_threshold(style_raw):
                initial_lock = style_raw
                initial_lock_label = label_raw if label_raw in self.COLOR_TO_NUM else None

            hist = {
                "x": float(cx),
                "y": float(cy),
                "labels": [label_raw],
                "styles": [style_raw],
                "last_frame": int(self.temporal_frame_id),
                "label_lock": label_raw if label_raw in self.COLOR_TO_NUM and label_strength_raw >= 0.60 else None,
                "style_lock": initial_lock,
                "style_lock_label": initial_lock_label,
                "label_switch_candidate": None,
                "label_switch_hits": 0,
                "switch_candidate": None,
                "switch_hits": 0,
            }
            self.temporal_color_cache.append(hist)
            if config.COLOR_DEBUG_ENABLED:
                color_info["temporal_debug"] = {
                    "matched": False,
                    "distance": None,
                    "history_len": 1,
                    "label_raw": label_raw,
                    "style_raw": style_raw,
                    "label_smoothed": label_raw,
                    "style_smoothed": style_raw,
                    "label_lock": hist.get("label_lock"),
                    "label_switch_candidate": None,
                    "label_switch_hits": 0,
                    "style_lock": hist.get("style_lock"),
                    "switch_candidate": None,
                    "switch_hits": 0,
                    "style_signal_strength": float(style_strength_raw),
                    "label_signal_strength": float(label_strength_raw),
                }
            return color_info

        hist = self.temporal_color_cache[best_idx]
        hist["x"] = float(cx)
        hist["y"] = float(cy)
        hist["last_frame"] = int(self.temporal_frame_id)

        labels = list(hist.get("labels", []))
        styles = list(hist.get("styles", []))
        labels.append(label_raw)
        styles.append(style_raw)
        if len(labels) > window:
            labels = labels[-window:]
        if len(styles) > window:
            styles = styles[-window:]
        hist["labels"] = labels
        hist["styles"] = styles

        smoothed_label = self._majority_vote(labels, min_stable, label_raw)
        smoothed_style = self._majority_vote(styles, min_stable, style_raw)

        # 避免 Unknown 壓過有效分類
        if label_raw != "Unknown" and smoothed_label == "Unknown":
            smoothed_label = label_raw
        if style_raw != "Unknown" and smoothed_style == "Unknown":
            smoothed_style = style_raw

        label_lock = hist.get("label_lock")
        if label_lock not in self.COLOR_TO_NUM and label_raw in self.COLOR_TO_NUM and label_strength_raw >= 0.60:
            label_lock = label_raw
            hist["label_lock"] = label_lock
            hist["label_switch_candidate"] = None
            hist["label_switch_hits"] = 0

        if label_lock in self.COLOR_TO_NUM:
            if label_raw == label_lock or label_raw == "Unknown":
                hist["label_switch_candidate"] = None
                hist["label_switch_hits"] = 0
            elif label_raw in self.COLOR_TO_NUM:
                same_label_candidate = hist.get("label_switch_candidate") == label_raw
                hist["label_switch_candidate"] = label_raw
                hist["label_switch_hits"] = int(hist.get("label_switch_hits", 0)) + 1 if same_label_candidate else 1

                switch_hits_needed = 4 if {str(label_lock), label_raw} == {"Blue", "Purple"} else 3
                allow_label_switch = label_strength_raw >= (0.82 if {str(label_lock), label_raw} == {"Blue", "Purple"} else 0.72)

                if allow_label_switch and int(hist.get("label_switch_hits", 0)) >= switch_hits_needed:
                    label_lock = label_raw
                    hist["label_lock"] = label_lock
                    hist["label_switch_candidate"] = None
                    hist["label_switch_hits"] = 0

            if label_lock in self.COLOR_TO_NUM:
                smoothed_label = str(label_lock)

        tracked_label = smoothed_label if smoothed_label in self.COLOR_TO_NUM else None
        locked_style = hist.get("style_lock")
        locked_label = hist.get("style_lock_label")

        if tracked_label and locked_label and tracked_label != locked_label:
            locked_style = None
            locked_label = None
            hist["style_lock"] = None
            hist["style_lock_label"] = None
            hist["switch_candidate"] = None
            hist["switch_hits"] = 0

        resolved_style = smoothed_style
        if resolved_style not in ("Solid", "Stripe") and style_raw in ("Solid", "Stripe"):
            resolved_style = style_raw

        if tracked_label:
            if locked_style not in ("Solid", "Stripe"):
                if resolved_style in ("Solid", "Stripe"):
                    if style_strength_raw >= self._style_lock_threshold(resolved_style):
                        locked_style = resolved_style
                        locked_label = tracked_label
                        hist["style_lock"] = locked_style
                        hist["style_lock_label"] = locked_label
                        hist["switch_candidate"] = None
                        hist["switch_hits"] = 0
            else:
                if style_raw == locked_style or style_raw == "Unknown":
                    hist["switch_candidate"] = None
                    hist["switch_hits"] = 0
                elif style_raw in ("Solid", "Stripe"):
                    same_candidate = hist.get("switch_candidate") == style_raw
                    hist["switch_candidate"] = style_raw
                    hist["switch_hits"] = int(hist.get("switch_hits", 0)) + 1 if same_candidate else 1

                    if locked_style == "Stripe" and style_raw == "Solid":
                        allow_switch = style_strength_raw >= 0.95
                        switch_hits_needed = 5
                    else:
                        allow_switch = style_strength_raw >= 0.80
                        switch_hits_needed = 2

                    if allow_switch and int(hist.get("switch_hits", 0)) >= switch_hits_needed:
                        locked_style = style_raw
                        locked_label = tracked_label
                        hist["style_lock"] = locked_style
                        hist["style_lock_label"] = locked_label
                        hist["switch_candidate"] = None
                        hist["switch_hits"] = 0

                if locked_style in ("Solid", "Stripe"):
                    resolved_style = str(locked_style)

        color_info["label"] = smoothed_label
        color_info["style"] = resolved_style

        if config.COLOR_DEBUG_ENABLED:
            color_info["temporal_debug"] = {
                "matched": True,
                "distance": float(best_d),
                "history_len": len(labels),
                "label_raw": label_raw,
                "style_raw": style_raw,
                "label_smoothed": smoothed_label,
                "style_smoothed": resolved_style,
                "label_lock": hist.get("label_lock"),
                "label_switch_candidate": hist.get("label_switch_candidate"),
                "label_switch_hits": int(hist.get("label_switch_hits", 0)),
                "style_lock": hist.get("style_lock"),
                "switch_candidate": hist.get("switch_candidate"),
                "switch_hits": int(hist.get("switch_hits", 0)),
                "style_signal_strength": float(style_strength_raw),
                "label_signal_strength": float(label_strength_raw),
            }

        return color_info

    def _smooth_ball_geometry_temporal(self, white_balls: List[List[Any]], color_balls: List[List[Any]]) -> Tuple[List[List[Any]], List[List[Any]]]:
        """對球心與半徑做短時序平滑，降低 segmentation 輪廓造成的大小/位置浮動。"""
        if not bool(getattr(config, "BALL_GEOMETRY_TEMPORAL_SMOOTH_ENABLED", True)):
            return white_balls, color_balls

        if not hasattr(self, "temporal_ball_geometry_cache"):
            self.temporal_ball_geometry_cache = []

        match_dist = max(4.0, float(getattr(config, "BALL_GEOMETRY_TEMPORAL_MATCH_DIST", 24.0)))
        alpha = float(getattr(config, "BALL_GEOMETRY_TEMPORAL_ALPHA", 0.68))
        alpha = max(0.0, min(0.92, alpha))
        max_age = max(2, int(getattr(config, "BALL_GEOMETRY_TEMPORAL_MAX_AGE", 8)))
        frame_id = int(getattr(self, "temporal_frame_id", 0))

        self.temporal_ball_geometry_cache = [
            item for item in self.temporal_ball_geometry_cache
            if (frame_id - int(item.get("last_frame", 0))) <= max_age
        ]
        used_cache: set = set()

        def smooth_one(ball: List[Any], kind: str) -> List[Any]:
            if len(ball) < 4:
                return ball
            x, y, w, h = [float(v) for v in ball[:4]]
            cx = x + (w / 2.0)
            cy = y + (h / 2.0)
            radius = max(1.0, min(w, h) / 2.0)
            number = ball[7] if kind == "color" and len(ball) > 7 else None

            best_idx = -1
            best_d = float("inf")
            for idx, item in enumerate(self.temporal_ball_geometry_cache):
                if idx in used_cache or item.get("kind") != kind:
                    continue
                cached_number = item.get("number")
                d = math.hypot(float(item.get("cx", 0.0)) - cx, float(item.get("cy", 0.0)) - cy)
                if kind == "color" and number is not None and cached_number is not None and number != cached_number:
                    same_color_family = {int(number), int(cached_number)} in ({1, 9}, {2, 10}, {3, 11}, {4, 12}, {5, 13}, {6, 14}, {7, 15})
                    close_jump = d <= max(8.0, match_dist * 0.55)
                    if not (same_color_family or close_jump):
                        continue
                if d < best_d and d <= match_dist:
                    best_d = d
                    best_idx = idx

            matched = best_idx >= 0
            if matched:
                item = self.temporal_ball_geometry_cache[best_idx]
                used_cache.add(best_idx)
                prev_r = float(item.get("radius", radius))
                radius_jump_ratio = abs(radius - prev_r) / max(1.0, prev_r)
                if best_d > max(match_dist * 0.72, prev_r * 1.35) or radius_jump_ratio > 0.45:
                    matched = False

            if matched:
                item = self.temporal_ball_geometry_cache[best_idx]
                cx_s = float(item.get("cx", cx)) * alpha + cx * (1.0 - alpha)
                cy_s = float(item.get("cy", cy)) * alpha + cy * (1.0 - alpha)
                r_s = float(item.get("radius", radius)) * alpha + radius * (1.0 - alpha)
                hits = int(item.get("hits", 1)) + 1
                item.update({
                    "cx": cx_s,
                    "cy": cy_s,
                    "radius": r_s,
                    "last_frame": frame_id,
                    "number": number,
                    "hits": hits,
                })
            else:
                cx_s, cy_s, r_s = cx, cy, radius
                hits = 1
                self.temporal_ball_geometry_cache.append({
                    "kind": kind,
                    "number": number,
                    "cx": cx_s,
                    "cy": cy_s,
                    "radius": r_s,
                    "last_frame": frame_id,
                    "hits": hits,
                })

            r_i = max(1, int(round(r_s)))
            ball[0] = int(round(cx_s - r_i))
            ball[1] = int(round(cy_s - r_i))
            ball[2] = int(round(r_i * 2))
            ball[3] = int(round(r_i * 2))
            if kind == "color" and len(ball) > 4:
                ball[4] = r_i
            if config.COLOR_DEBUG_ENABLED and kind == "color" and len(ball) > 6 and isinstance(ball[6], dict):
                ball[6]["geometry_temporal_debug"] = {
                    "matched": bool(matched),
                    "distance": float(best_d) if matched else None,
                    "hits": int(hits),
                    "raw_center": [float(cx), float(cy)],
                    "raw_radius": float(radius),
                    "smoothed_center": [float(cx_s), float(cy_s)],
                    "smoothed_radius": float(r_s),
                }
            return ball

        return (
            [smooth_one(ball, "white") for ball in white_balls],
            [smooth_one(ball, "color") for ball in color_balls],
        )

    # ==================== 球體解析 ====================
    def _analyze_balls(self, results, roi_img: np.ndarray, offset: Tuple[int, int]) -> Dict[str, Any]:
        """
        整合 poolShotPredictor.py 的 machinelearning() 邏輯
        """
        tx, ty = offset
        white_balls: List[List] = []
        color_balls: List[List] = []
        cue_pos: Optional[List[int]] = None
        cue_center: Optional[Tuple[int, int]] = None
        cue_axis: Optional[CueAxis] = None
        cue_candidates: List[Dict[str, Any]] = []
        raw_yolo_boxes: List[Dict[str, Any]] = []
        projected_artifacts = self._current_projected_artifacts()

        # 收集所有球體
        for r in results:
            boxes = r.boxes
            for box_idx, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                w, h = x2 - x1, y2 - y1
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = self.model.names[cls_id]
                if label == "cue" and conf < float(getattr(config, "CUE_CONF_THR", 0.35)):
                    continue
                gx_raw, gy_raw = x1 + tx, y1 + ty
                if label in {"white-ball", "color-ball", "cue"}:
                    raw_yolo_boxes.append({
                        "x": gx_raw,
                        "y": gy_raw,
                        "w": w,
                        "h": h,
                        "label": label,
                        "conf": conf,
                    })

                if self.cue_laser_only and label != "cue":
                    continue

                geom_info = None
                result_mask = self._extract_result_mask(r, box_idx, roi_img.shape[:2])
                if label in ["white-ball", "color-ball"]:
                    geom_info = self._refine_ball_geometry_from_mask(result_mask, [x1, y1, w, h])
                    if geom_info is None:
                        geom_info = self._refine_ball_geometry_local(roi_img, [x1, y1, w, h])
                    x1 = int(geom_info.get("x", x1))
                    y1 = int(geom_info.get("y", y1))
                    w = int(geom_info.get("w", w))
                    h = int(geom_info.get("h", h))

                # 轉換為全圖座標
                gx, gy = x1 + tx, y1 + ty

                # 計算長寬比，排除細長物體 (如球桿)
                aspect_ratio = float(w) / max(1, h)
                is_round = 0.50 < aspect_ratio < 1.90

                # 基於球桌大小合理濾除異常過大/過小的 BBox (假陽性背景)
                is_valid_size = True
                if label in ["white-ball", "color-ball"]:
                    table_min_dim = min(roi_img.shape[:2]) if roi_img is not None else 640
                    if table_min_dim > 0:
                        max_allowed = table_min_dim * 0.15 # 最大不超過球桌短邊 15%
                        min_allowed = max(5.0, table_min_dim * 0.012) # 最小不低於 1.2%
                        if max(w, h) > max_allowed or min(w, h) < min_allowed:
                            is_valid_size = False

                # 若不是球桿，且形狀不圓或大小不合理，則過濾掉
                if label != "cue" and not (is_round and is_valid_size):
                    continue

                if label == "white-ball":
                    if self._is_projected_ball_artifact(gx, gy, w, h, projected_artifacts):
                        continue
                    white_balls.append([gx, gy, w, h, conf, geom_info.get("debug") if isinstance(geom_info, dict) else None])
                elif label == "color-ball":
                    if self.cue_laser_only:
                        continue
                    if self._is_projected_ball_artifact(gx, gy, w, h, projected_artifacts):
                        continue
                    radius = int(geom_info.get("radius", max(1, min(w, h) // 2))) if geom_info else max(1, min(w, h) // 2)
                    # 執行 HSV 顏色檢測
                    color_info = self._detect_ball_color_hsv(roi_img, [x1, y1, w, h])
                    if config.COLOR_DEBUG_ENABLED and geom_info and geom_info.get("debug"):
                        color_info["geometry_debug"] = geom_info.get("debug")

                    # 顏色/樣式跨幀平滑（僅平滑分類結果，不影響球位置）
                    color_info = self._smooth_color_info_temporal(gx + (w / 2.0), gy + (h / 2.0), color_info)

                    # 若 HSV 判定為極白，將其視為白球（同時需要符合圓形）
                    if color_info["label"] == "White":
                        if self._is_projected_ball_artifact(gx, gy, w, h, projected_artifacts):
                            continue
                        white_balls.append([gx, gy, w, h, conf, geom_info.get("debug") if isinstance(geom_info, dict) else None])
                    else:
                        ball_num = self._classify_ball_number(color_info)
                                                # 過濾袋口誤檢與已進袋殘留框
                        if self._is_ball_in_pocket_capture_zone(gx, gy, w, h):
                            continue
                        if self._is_pocket_false_positive_candidate(gx, gy, w, h, color_info):
                            continue
                        color_balls.append([gx, gy, w, h, radius, conf, color_info, ball_num])
                elif label == "cue":
                    if self._is_projected_cue_artifact(gx, gy, w, h, projected_artifacts):
                        continue
                    mask_axis = self._estimate_cue_axis_from_mask(
                        result_mask,
                        [x1, y1, w, h],
                        offset,
                        apply_smoothing=False,
                    )
                    image_axis = self._estimate_cue_axis_line(
                        roi_img,
                        [x1, y1, w, h],
                        offset,
                        apply_smoothing=False,
                    )
                    if mask_axis is not None and image_axis is not None:
                        candidate_axis = self._recenter_cue_axis_with_image_axis(mask_axis, image_axis)
                        axis_source = "segmentation_mask_recentered"
                    else:
                        candidate_axis = mask_axis if mask_axis is not None else image_axis
                        axis_source = "segmentation_mask" if mask_axis is not None else "bbox_roi"
                    if candidate_axis is None:
                        continue
                    cue_candidates.append({
                        "bbox": [gx, gy, w, h],
                        "center": (gx + w // 2, gy + h // 2),
                        "axis": candidate_axis,
                        "score": self._score_cue_axis_candidate(candidate_axis, conf),
                        "axis_source": axis_source,
                    })

        if cue_candidates:
            best_cue = max(cue_candidates, key=lambda item: float(item.get("score", 0.0)))
            cue_pos = best_cue["bbox"]
            cue_center = best_cue["center"]
            cue_axis = self._smooth_cue_axis_result(best_cue["axis"])
            self.cue_axis_missing_frames = 0
        else:
            self.cue_axis_missing_frames += 1
            cue_axis = self._cached_cue_axis_result()

        # 先做候選去重，避免同顆球重複標註
        white_balls = self._suppress_cue_tip_white_candidates(white_balls, cue_pos, cue_axis)
        white_balls = self._suppress_duplicate_balls(white_balls, conf_idx=4)
        color_balls = self._suppress_duplicate_balls(color_balls, conf_idx=5)
        white_balls, color_balls = self._smooth_ball_geometry_temporal(white_balls, color_balls)

        # 選擇主要白球（信心度最高）
        white_primary: Optional[List[int]] = None
        if white_balls:
            white_balls.sort(key=lambda t: t[4], reverse=True)
            x, y, w, h = white_balls[0][:4]
            white_primary = [x, y, w, h]

        if white_primary and color_balls:
            # 白球優先：移除與白球重疊的彩球框，避免白球被疊色
            wx, wy, ww, wh = white_primary
            wcx, wcy = wx + ww / 2.0, wy + wh / 2.0
            wr = max(1.0, min(ww, wh) / 2.0)
            overlap_ratio = float(getattr(config, "WHITE_OVERLAP_SUPPRESS_RATIO", 0.88))
            filtered_colors: List[List[Any]] = []
            for ball in color_balls:
                bx, by, bw, bh = ball[0], ball[1], ball[2], ball[3]
                bcx, bcy = bx + (bw / 2.0), by + (bh / 2.0)
                br = max(1.0, min(bw, bh) / 2.0)
                if math.hypot(bcx - wcx, bcy - wcy) <= (max(wr, br) * overlap_ratio):
                    continue
                filtered_colors.append(ball)
            color_balls = filtered_colors

        if not white_primary:
            # YOLO 完全沒抓到白球（可能因模糊或亮度異常），啟動傳統影像處理備案
            white_primary = self._fallback_find_white_ball(roi_img, offset, color_balls)
            
            # 若 fallback 找到白球，檢查它是否混進了 color_balls 並將其剔除
            if white_primary:
                filtered_fallback = self._suppress_cue_tip_white_candidates([[*white_primary, 1.0]], cue_pos, cue_axis)
                if not filtered_fallback:
                    white_primary = None
                else:
                    wx, wy, ww, wh = white_primary
                    white_cx, white_cy = wx + ww // 2, wy + wh // 2
                    for i in range(len(color_balls) - 1, -1, -1):
                        ball = color_balls[i]
                        bx, by, bw, bh = ball[0], ball[1], ball[2], ball[3]
                        bcx, bcy = bx + bw // 2, by + bh // 2
                        if math.hypot(white_cx - bcx, white_cy - bcy) < max(ww, wh):
                            color_balls.pop(i)

        # 選擇主要彩球
        color_primary: Optional[List] = None
        if color_balls:
            if cue_center:
                # 若有球桿，選擇離球桿最近的彩球
                def dist2(ball):
                    bx, by, bw, bh = ball[0], ball[1], ball[2], ball[3]
                    cx, cy = bx + bw // 2, by + bh // 2
                    return (cx - cue_center[0])**2 + (cy - cue_center[1])**2
                color_balls.sort(key=dist2)
            else:
                # 否則選信心度最高
                color_balls.sort(key=lambda t: t[5], reverse=True)

            color_primary = color_balls[0]

        # 執行多球路徑規劃（主路徑）+ 舊版單路徑預測（fallback）
        prediction_result = None
        multi_plan = None
        aim_assist_data = None
        if self.route_planner_enabled:
            if white_primary and color_balls and self.holes and self.table_roi:
                multi_plan = self._generate_multi_plan(white_primary, color_balls)
                if multi_plan is None:
                    multi_plan = self._held_realtime_multi_plan("INSUFFICIENT_STATE_HELD")
                else:
                    self._route_plan_missing_frames = 0
            else:
                multi_plan = self._held_realtime_multi_plan("DETECTION_TEMPORARILY_MISSING")

            if multi_plan and multi_plan.get("best_route"):
                prediction_result = self._legacy_prediction_from_best_route(multi_plan["best_route"])
        elif not self.route_planner_enabled and white_primary and color_primary and cue_pos:
            shot_point = self._find_shot_point(cue_pos, white_primary)
            prediction_result = self._pool_shot_prediction(shot_point, white_primary, color_primary)

        # 瞄準輔助線：
        # - planner 啟用時，只在 best_route 存在時提供 route 對應 ghost ball
        # - planner 無路線時，避免殘留舊 aim_assist/白線
        if self.route_planner_enabled:
            if (
                self.aim_assist_enabled
                and white_primary
                and isinstance(multi_plan, dict)
                and isinstance(multi_plan.get("best_route"), dict)
            ):
                aim_assist_data = self._aim_assist_from_route(multi_plan["best_route"], white_primary)
            else:
                aim_assist_data = None
        elif self.aim_assist_enabled and white_primary and color_balls:
            preferred_target_number = None
            if isinstance(multi_plan, dict):
                best_route = multi_plan.get("best_route")
                if isinstance(best_route, dict):
                    preferred_target_number = best_route.get("target_ball_number")

            # 選擇離白球最近的彩球作為目標
            white_cx = white_primary[0] + white_primary[2] // 2
            white_cy = white_primary[1] + white_primary[3] // 2

            best_ball = None
            if isinstance(preferred_target_number, int):
                for ball in color_balls:
                    if ball[7] == preferred_target_number:
                        best_ball = ball
                        break

            if best_ball is None:
                best_dist = float('inf')
                for ball in color_balls:
                    bx, by, bw, bh = ball[0], ball[1], ball[2], ball[3]
                    bcx, bcy = bx + bw // 2, by + bh // 2
                    d = math.hypot(bcx - white_cx, bcy - white_cy)
                    if d < best_dist:
                        best_dist = d
                        best_ball = ball

            if best_ball:
                target_dict = {
                    'x': best_ball[0], 'y': best_ball[1],
                    'w': best_ball[2], 'h': best_ball[3],
                    'radius': best_ball[4]
                }
                white_dict = {
                    'x': white_primary[0], 'y': white_primary[1],
                    'w': white_primary[2], 'h': white_primary[3]
                }
                try:
                    aim_assist_data = self._calculate_aim_assist(white_dict, target_dict)
                except Exception as e:
                    print(f"⚠️ Aim assist calculation error: {e}")
                    aim_assist_data = None

        cue_laser_line = self._estimate_cue_laser_line(cue_axis)

        # 構造回傳數據包（遵照 v1.5 規範）
        return {
            "timestamp": time.time(),
            "status": "analyzing",
            "white_ball": white_primary,
            "balls": [
                {
                    "x": ball[0],
                    "y": ball[1],
                    "w": ball[2],
                    "h": ball[3],
                    "radius": ball[4],
                    "conf": ball[5],
                    "color": ball[6].get("label", "Unknown"),
                    "style": ball[6].get("style", "Unknown"),
                    "number": ball[7],
                    "white_ratio": float(ball[6].get("white_ratio", 0.0)),
                    "dark_ratio": float(ball[6].get("dark_ratio", ball[6].get("black_ratio", 0.0))),
                    "color_ratio": float(ball[6].get("color_ratio", 0.0)),
                    "color_debug": ball[6].get("debug") if config.COLOR_DEBUG_ENABLED else None,
                    "geometry_debug": ball[6].get("geometry_debug") if config.COLOR_DEBUG_ENABLED else None,
                    "geometry_temporal_debug": ball[6].get("geometry_temporal_debug") if config.COLOR_DEBUG_ENABLED else None,
                    "temporal_debug": ball[6].get("temporal_debug") if config.COLOR_DEBUG_ENABLED else None,
                }
                for ball in color_balls
            ],
            "cue": cue_pos,
            "cue_axis": cue_axis,
            "cue_laser_line": cue_laser_line,
            "raw_yolo_boxes": raw_yolo_boxes,
            "cue_laser_only": self.cue_laser_only,
            "prediction": prediction_result,
            "multi_plan": multi_plan,
            "aim_assist": aim_assist_data,
            "table_roi": self.table_roi,
            "table_roi_raw": getattr(self, "table_roi_raw", None),
            "table_roi_adjustment": dict(getattr(self, "table_roi_adjustment", {"left": 0, "top": 0, "right": 0, "bottom": 0})),
            "table_roi_points": getattr(self, "table_roi_points", None),
            "table_roi_status": getattr(self, "table_roi_status", "unknown"),
            "holes": self.holes,
        }

    def _held_realtime_multi_plan(self, reason: str) -> Optional[Dict[str, Any]]:
        plan = self.route_planner.last_plan if self.route_planner is not None else None
        if not isinstance(plan, dict) or not isinstance(plan.get("best_route"), dict):
            return None
        if self._route_plan_missing_frames >= self._route_plan_hold_max_frames:
            return None

        self._route_plan_missing_frames += 1
        held_plan = dict(plan)
        notes = list(held_plan.get("coach_notes") or [])
        notes.insert(0, "偵測短暫不穩，暫時沿用上一條路線避免畫面閃爍。")
        held_plan["coach_notes"] = notes[:4]
        held_plan["error"] = reason
        held_plan["hysteresis_hold"] = True
        held_plan["realtime_hold_frames"] = self._route_plan_missing_frames
        self.route_planner.last_plan = held_plan
        return held_plan

    def _generate_multi_plan(self, white_primary: List[int], color_balls: List[List[Any]]) -> Optional[Dict[str, Any]]:
        runtime_packet = {
            "white_ball": white_primary,
            "balls": [
                {
                    "x": ball[0],
                    "y": ball[1],
                    "w": ball[2],
                    "h": ball[3],
                    "radius": ball[4],
                    "conf": ball[5],
                    "color": ball[6].get("label", "Unknown"),
                    "style": ball[6].get("style", "Unknown"),
                    "number": ball[7],
                }
                for ball in color_balls
            ],
            "holes": self.holes,
            "table_roi": self.table_roi,
        }
        return self.route_planner.plan_from_runtime_packet(
            runtime_packet,
            rule_profile=self.route_rule_profile,
            top_n=self.route_top_n,
            target_ball_number=self.route_target_ball_number,
            max_bounces=self.route_max_bounces,
            combo_depth=self.route_combo_depth,
            selected_route_id=self.selected_route_id,
            stroke_override=self.route_stroke_override,
        )

    def _legacy_prediction_from_best_route(self, best_route: Dict[str, Any]) -> Dict[str, Any]:
        path_points = best_route.get("path_points", [])
        target_no = best_route.get("target_ball_number")
        route_type = best_route.get("route_type", "unknown")
        success_prob = float(best_route.get("success_prob", 0.0))
        return {
            "prediction": success_prob >= 0.45,
            "paths": path_points,
            "color": (80, 145, 75),
            "collision_point": path_points[1] if len(path_points) > 1 else [],
            "ball_color": "MultiPlan",
            "ball_number": target_no,
            "ball_color_meta": {
                "label": route_type,
                "style": "planned",
                "success_prob": success_prob,
            },
        }

    def _fallback_find_white_ball(self, roi_img: np.ndarray, offset: Tuple[int, int], color_balls: List[List]) -> Optional[List[int]]:
        """
        當 YOLO 沒抓到白球時的傳統影像處理備案。
        利用白球高亮度、低飽和度的特性在球桌 ROI 內尋找。
        """
        hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        Hc, Sc, Vc = cv2.split(hsv)
        
        # 尋找高亮度、低飽和度的區域
        white_mask = np.zeros_like(Sc, dtype=np.uint8)
        white_mask[(Sc < 55) & (Vc > 140)] = 255
        
        # 排除已確認為彩色的球，避免將彩球的高光點誤認為白球
        # 注意：我們不排除 "Unknown" 的球，因為它可能就是被 YOLO 誤判的白球
        for ball in color_balls:
            if ball[6].get("label", "Unknown") != "Unknown":
                bx, by, bw, bh = ball[0] - offset[0], ball[1] - offset[1], ball[2], ball[3]
                cv2.rectangle(white_mask, (bx - 5, by - 5), (bx + bw + 5, by + bh + 5), 0, -1)
            
        # 形態學操作清除雜訊
        kernel = np.ones((5, 5), np.uint8)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)
        
        # 找輪廓
        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_rect = None
        best_area = 0
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 40 < area < 2000: # 合理的球體面積
                x, y, w, h = cv2.boundingRect(cnt)
                # 檢查長寬比 (白球應該近似圓形)
                aspect_ratio = float(w) / max(1, h)
                # 檢查飽滿度 (實際面積 / 邊界框面積，圓形約為 0.78，對角線球桿會非常低)
                bounding_area = w * h
                extent = float(area) / max(1, bounding_area)
                
                if 0.65 < aspect_ratio < 1.55 and extent > 0.55:
                    if area > best_area:
                        best_area = area
                        best_rect = [x + offset[0], y + offset[1], w, h]
                        
        if best_rect:
            # print(f"🔍 Fallback found white ball at: {best_rect}")
            return best_rect
            
        return None

    # ==================== HSV 顏色檢測 (from poolShotPredictor.py) ====================
    def _safe_crop(self, img: np.ndarray, x: int, y: int, w: int, h: int):
        """安全裁切，避免越界"""
        H, W = img.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            return None, (0, 0, 0, 0)
        return img[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0)

    def _refine_ball_geometry_local(self, roi_img: np.ndarray, bbox: List[int]) -> Dict[str, Any]:
        """在 YOLO bbox 內做局部 Hough 圓修正，降低陰影造成的半徑/中心偏差。"""
        x, y, w, h = map(int, bbox)
        result: Dict[str, Any] = {
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "radius": max(1, min(w, h) // 2),
            "refined": False,
        }

        if not config.LOCAL_HOUGH_REFINE_ENABLED:
            return result

        H, W = roi_img.shape[:2]
        base_r = max(4, int(min(w, h) / 2))
        pad = max(2, int(min(w, h) * float(config.LOCAL_HOUGH_PAD_RATIO)))

        ex0, ey0 = max(0, x - pad), max(0, y - pad)
        ex1, ey1 = min(W, x + w + pad), min(H, y + h + pad)
        patch = roi_img[ey0:ey1, ex0:ex1]
        if patch.size == 0:
            return result

        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 1.2)

        min_r = max(3, int(base_r * float(config.LOCAL_HOUGH_MIN_R_SCALE)))
        max_r = max(min_r + 1, int(base_r * float(config.LOCAL_HOUGH_MAX_R_SCALE)))
        min_dist = max(6.0, float(base_r) * 0.8)

        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=float(config.LOCAL_HOUGH_DP),
            minDist=min_dist,
            param1=float(config.LOCAL_HOUGH_PARAM1),
            param2=float(config.LOCAL_HOUGH_PARAM2),
            minRadius=min_r,
            maxRadius=max_r,
        )

        if circles is None or circles.size == 0:
            if config.COLOR_DEBUG_ENABLED:
                result["debug"] = {"refined": False, "reason": "no_circle"}
            return result

        hsv_patch = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        local_cx0 = (x - ex0) + (w / 2.0)
        local_cy0 = (y - ey0) + (h / 2.0)

        best = None
        best_score = float("inf")
        for c in circles[0]:
            cx_c, cy_c, r_c = float(c[0]), float(c[1]), float(c[2])
            if r_c <= 0.0:
                continue

            m = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(m, (int(round(cx_c)), int(round(cy_c))), int(round(r_c)), 255, -1)
            valid_px = int(np.count_nonzero(m == 255))
            if valid_px < 20:
                continue

            sat_med = float(np.median(hsv_patch[:, :, 1][m == 255]))
            val_med = float(np.median(hsv_patch[:, :, 2][m == 255]))
            if sat_med < float(config.LOCAL_HOUGH_MIN_SAT_MEDIAN) or val_med < float(config.LOCAL_HOUGH_MIN_VAL_MEDIAN):
                continue

            center_dist = math.hypot(cx_c - local_cx0, cy_c - local_cy0) / max(1.0, float(base_r))
            radius_diff = abs(r_c - float(base_r)) / max(1.0, float(base_r))
            score = (0.68 * center_dist) + (0.32 * radius_diff)

            if score < best_score:
                best_score = score
                best = (cx_c, cy_c, r_c, sat_med, val_med)

        if best is None:
            if config.COLOR_DEBUG_ENABLED:
                result["debug"] = {"refined": False, "reason": "all_filtered"}
            return result

        cx_b, cy_b, r_b, sat_b, val_b = best
        refined_cx = int(round(ex0 + cx_b))
        refined_cy = int(round(ey0 + cy_b))
        refined_r = max(3, int(round(r_b)))

        nx = max(0, refined_cx - refined_r)
        ny = max(0, refined_cy - refined_r)
        nx2 = min(W, refined_cx + refined_r)
        ny2 = min(H, refined_cy + refined_r)
        nw = max(1, nx2 - nx)
        nh = max(1, ny2 - ny)

        if nw < 6 or nh < 6:
            return result

        result.update({
            "x": int(nx),
            "y": int(ny),
            "w": int(nw),
            "h": int(nh),
            "radius": int(max(1, min(nw, nh) // 2)),
            "refined": True,
        })

        if config.COLOR_DEBUG_ENABLED:
            result["debug"] = {
                "refined": True,
                "orig_bbox": [int(x), int(y), int(w), int(h)],
                "refined_bbox": [int(nx), int(ny), int(nw), int(nh)],
                "score": float(best_score),
                "sat_median": float(sat_b),
                "val_median": float(val_b),
            }

        return result

    def _detect_ball_color_hsv(self, roi_img: np.ndarray, bbox: List[int]) -> Dict[str, Any]:
        """A+B 主色判定：模板比對 + K-means，並以多層半徑與背景環抑制判斷實心/條紋。"""
        x, y, w, h = map(int, bbox)
        patch, (x0, y0, w2, h2) = self._safe_crop(roi_img, x, y, w, h)
        if patch is None or patch.size == 0:
            result = {
                "label": "Unknown",
                "style": "Unknown",
                "hue": None,
                "white_ratio": 0.0,
                "black_ratio": 0.0,
                "dark_ratio": 0.0,
                "color_ratio": 0.0,
            }
            if config.COLOR_DEBUG_ENABLED:
                result["debug"] = {
                    "cx": None,
                    "cy": None,
                    "r": None,
                    "core_r": None,
                    "mid_r": None,
                    "outer_r": None,
                    "mask_pixels": 0,
                    "valid_pixels": 0,
                    "valid_ratio": 0.0,
                    "hsv_median": [None, None, None],
                    "lab_median": [None, None, None],
                    "final_label": "Unknown",
                    "final_style": "Unknown",
                }
            return result

        cx, cy = w2 // 2, h2 // 2
        min_wh = max(2, min(w2, h2))
        base_r = int(0.46 * min_wh)

        center_ratio = float(getattr(config, "COLOR_MASK_CENTER_RATIO", 0.24))
        core_ratio = float(getattr(config, "COLOR_MASK_CORE_RATIO", 0.45))
        mid_ratio = float(getattr(config, "COLOR_MASK_MID_RATIO", 0.65))
        outer_ratio = float(getattr(config, "COLOR_MASK_OUTER_RATIO", 0.85))
        center_ratio = max(0.10, min(center_ratio, 0.34))
        core_ratio = max(0.20, min(core_ratio, 0.85))
        mid_ratio = max(core_ratio + 0.05, min(mid_ratio, 0.92))
        outer_ratio = max(mid_ratio + 0.05, min(outer_ratio, 0.98))

        center_r = max(2, int(center_ratio * min_wh))
        core_r = max(2, int(core_ratio * min_wh))
        mid_r = max(core_r + 1, int(mid_ratio * min_wh))
        outer_r = max(mid_r + 1, int(outer_ratio * min_wh))

        center_mask = np.zeros(patch.shape[:2], dtype=np.uint8)
        core_mask = np.zeros(patch.shape[:2], dtype=np.uint8)
        mid_mask = np.zeros(patch.shape[:2], dtype=np.uint8)
        outer_mask = np.zeros(patch.shape[:2], dtype=np.uint8)
        cv2.circle(center_mask, (cx, cy), center_r, 255, -1)
        cv2.circle(core_mask, (cx, cy), core_r, 255, -1)
        cv2.circle(mid_mask, (cx, cy), mid_r, 255, -1)
        cv2.circle(outer_mask, (cx, cy), outer_r, 255, -1)

        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)
        Hc, Sc, Vc = cv2.split(hsv)

        valid_outer_raw = (outer_mask == 255) & (Vc > 25) & (Vc < 250)
        table_mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        # 避免與桌布同色的球（如藍桌藍球）在核心區域被 table_mask 剔除
        # 因此在 mid_mask 範圍內強迫保留像素，僅在球體邊緣套用 table_mask 過濾
        valid_outer_raw = valid_outer_raw & ((table_mask == 0) | (mid_mask == 255))

        # 局部背景環抑制：估計球外環背景色，排除與背景過近像素
        bg_like = np.zeros_like(valid_outer_raw, dtype=bool)
        bg_like_ratio = 0.0
        bg_hsv = [None, None, None]
        bg_ring_pixels = 0
        bg_like_pixels = 0

        if bool(getattr(config, "COLOR_BG_RING_ENABLED", True)):
            yy, xx = np.indices((h2, w2))
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            ring_in_ratio = float(getattr(config, "COLOR_BG_RING_INNER_RATIO", 1.05))
            ring_out_ratio = float(getattr(config, "COLOR_BG_RING_OUTER_RATIO", 1.30))
            if ring_out_ratio < ring_in_ratio:
                ring_out_ratio = ring_in_ratio + 0.05

            ring_mask = (dist >= (outer_r * ring_in_ratio)) & (dist <= (outer_r * ring_out_ratio))
            ring_valid = ring_mask & (table_mask == 0) & (Vc > 20)
            bg_ring_pixels = int(np.count_nonzero(ring_valid))

            if bg_ring_pixels >= 24:
                bg_h = float(self._circular_hue_mean(Hc[ring_valid]))
                bg_s = float(np.median(Sc[ring_valid]))
                bg_v = float(np.median(Vc[ring_valid]))
                bg_hsv = [bg_h, bg_s, bg_v]

                hue_diff_bg = np.abs(Hc.astype(np.float32) - bg_h)
                hue_diff_bg = np.minimum(hue_diff_bg, 180.0 - hue_diff_bg)

                bg_like = valid_outer_raw & \
                    (hue_diff_bg <= float(getattr(config, "COLOR_BG_HUE_TOL", 10.0))) & \
                    (np.abs(Sc.astype(np.float32) - bg_s) <= float(getattr(config, "COLOR_BG_SAT_TOL", 40.0))) & \
                    (np.abs(Vc.astype(np.float32) - bg_v) <= float(getattr(config, "COLOR_BG_VAL_TOL", 45.0)))

                bg_like_pixels = int(np.count_nonzero(bg_like))
                raw_valid_cnt = int(np.count_nonzero(valid_outer_raw))
                bg_like_ratio = float(bg_like_pixels / max(1, raw_valid_cnt))

        valid_outer = valid_outer_raw & ~bg_like
        if np.count_nonzero(valid_outer) < 36:
            valid_outer = valid_outer_raw
            bg_like = np.zeros_like(valid_outer_raw, dtype=bool)
            bg_like_pixels = 0
            bg_like_ratio = 0.0

        valid_center = valid_outer & (center_mask == 255)
        valid_mid = valid_outer & (mid_mask == 255)
        valid_core = valid_outer & (core_mask == 255)
        valid_outer_ring = valid_outer & (outer_mask == 255) & (mid_mask == 0)

        mask_pixels = int(np.count_nonzero(outer_mask == 255))
        n_valid = int(np.count_nonzero(valid_outer))
        valid_ratio = float(n_valid / max(1, mask_pixels))

        hsv_median = [None, None, None]
        lab_median = [None, None, None]
        if n_valid > 0:
            hsv_median = [
                float(np.median(Hc[valid_outer])),
                float(np.median(Sc[valid_outer])),
                float(np.median(Vc[valid_outer])),
            ]
            lab_pixels = lab[valid_outer].reshape(-1, 3)
            if lab_pixels.size > 0:
                lab_med = np.median(lab_pixels, axis=0)
                lab_median = [float(lab_med[0]), float(lab_med[1]), float(lab_med[2])]

        white_ratio = 0.0
        black_ratio = 0.0
        color_ratio = 0.0

        def _pack_result(
            label: str,
            style: str,
            hue: Optional[float],
            white_ratio_v: float,
            black_ratio_v: float,
            color_ratio_v: float,
            template_score: Optional[float] = None,
            extra_debug: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            result: Dict[str, Any] = {
                "label": label,
                "style": style,
                "hue": float(hue) if hue is not None else None,
                "white_ratio": float(white_ratio_v),
                "black_ratio": float(black_ratio_v),
                "dark_ratio": float(black_ratio_v),
                "color_ratio": float(color_ratio_v),
            }
            if template_score is not None:
                result["template_score"] = float(template_score)

            if config.COLOR_DEBUG_ENABLED:
                debug_payload: Dict[str, Any] = {
                    "cx": int(x + cx),
                    "cy": int(y + cy),
                    "r": int(base_r),
                    "center_r": int(center_r),
                    "core_r": int(core_r),
                    "mid_r": int(mid_r),
                    "outer_r": int(outer_r),
                    "mask_pixels": int(mask_pixels),
                    "valid_pixels": int(n_valid),
                    "valid_ratio": float(valid_ratio),
                    "hsv_median": hsv_median,
                    "lab_median": lab_median,
                    "bg_hsv": bg_hsv,
                    "bg_ring_pixels": int(bg_ring_pixels),
                    "bg_like_pixels": int(bg_like_pixels),
                    "bg_like_ratio": float(bg_like_ratio),
                    "white_ratio": float(white_ratio_v),
                    "dark_ratio": float(black_ratio_v),
                    "color_ratio": float(color_ratio_v),
                    "final_label": label,
                    "final_style": style,
                }
                if template_score is not None:
                    debug_payload["template_score"] = float(template_score)
                if extra_debug:
                    debug_payload.update(extra_debug)
                result["debug"] = debug_payload

                if config.COLOR_DEBUG_PRINT:
                    print(
                        f"[BallDebug] cx={debug_payload['cx']} cy={debug_payload['cy']} "
                        f"r=({debug_payload['core_r']},{debug_payload['mid_r']},{debug_payload['outer_r']}) "
                        f"bg_like={debug_payload['bg_like_ratio']:.3f} "
                        f"valid={debug_payload['valid_pixels']}/{debug_payload['mask_pixels']} "
                        f"white={debug_payload['white_ratio']:.3f} dark={debug_payload['dark_ratio']:.3f} "
                        f"color={debug_payload['color_ratio']:.3f} -> {label}/{style}"
                    )

            return result

        if n_valid < 40:
            return _pack_result("Unknown", "Unknown", None, 0.0, 0.0, 0.0)

        # 依據目前的 Calibration 設定動態調整黑白判定閾值
        white_val_ref = self.COLOR_VAL_REF.get("White", 220.0)
        # 對於黑球，將預設基準拔高，以包容反光與暗部雜訊
        black_val_ref = self.COLOR_VAL_REF.get("Black", 65.0)
        
        white_v_thr = min(150, int(white_val_ref - 50))
        # 允許黑球的最基本容忍度至少涵蓋到 V=100，避免稍亮一點就被當成彩球
        black_v_thr = max(100, int(black_val_ref + 40))

        white_mask = valid_outer & (Sc <= 42) & (Vc >= white_v_thr)
        black_mask = valid_outer & (Vc < black_v_thr)

        color_seed = valid_mid if np.count_nonzero(valid_mid) >= 28 else valid_outer
        color_core = color_seed & ~white_mask & ~black_mask & (Sc >= 40)
        
        # 避免在彩色特徵過少時（如黑球），自動降低 Sc 門檻到 25，導致大量暗部雜訊變成彩色
        # 只有在整體 Vc 偏亮時（不像是黑球）才去降低 Sc 門檻找殘餘淺色
        if np.count_nonzero(color_core) < 24 and float(np.median(Vc[valid_outer])) > black_v_thr:
            color_core = color_seed & ~white_mask & ~black_mask & (Sc >= 25)

        white_ratio = np.count_nonzero(white_mask) / max(1, n_valid)
        black_ratio = np.count_nonzero(black_mask) / max(1, n_valid)
        color_ratio = np.count_nonzero(color_core) / max(1, n_valid)

        if white_ratio > 0.78 and color_ratio < 0.06:
            return _pack_result("White", "Cue", None, white_ratio, black_ratio, color_ratio)
        
        # 放寬黑球判定，避免大片強反光造成的雜訊色干擾 (中位數容忍度 +50，color_ratio 放寬至 0.45)
        if black_ratio > 0.50 and color_ratio < 0.35:
            return _pack_result("Black", "Solid", None, white_ratio, black_ratio, color_ratio)
        if n_valid >= 20 and float(np.median(Vc[valid_outer])) < (black_v_thr + 50) and color_ratio < 0.45:
            return _pack_result("Black", "Solid", None, white_ratio, black_ratio, color_ratio)

        if np.count_nonzero(color_core) < 12:
            return _pack_result("Unknown", "Unknown", None, white_ratio, black_ratio, color_ratio)

        color_name, hue_mean, template_score = self._classify_main_color_ab(Hc, Sc, Vc, lab, color_core)
        if color_name == "Unknown":
            color_name = self._hue_to_name(hue_mean, Vc[color_core]) if hue_mean >= 0 else "Unknown"

        extra_debug: Dict[str, Any] = {}
        if color_name in ["Black", "White", "Unknown"]:
            style = "Unknown" if color_name == "Unknown" else "Solid"
        else:
            main_mask = self._build_main_color_mask(Hc, Sc, Vc, lab, valid_outer, color_name)

            n_center = max(1, np.count_nonzero(valid_center))
            n_core = max(1, np.count_nonzero(valid_core))
            n_mid = max(1, np.count_nonzero(valid_mid))
            n_outer_ring = max(1, np.count_nonzero(valid_outer_ring))

            center_white_ratio = np.count_nonzero(white_mask & valid_center) / n_center
            core_white_ratio = np.count_nonzero(white_mask & valid_core) / n_core
            core_main_ratio = np.count_nonzero(main_mask & valid_core) / n_core
            mid_main_ratio = np.count_nonzero(main_mask & valid_mid) / n_mid
            outer_white_ratio = np.count_nonzero(white_mask & valid_outer_ring) / n_outer_ring
            global_main_ratio = np.count_nonzero(main_mask) / max(1, n_valid)

            extra_debug = {
                "center_white_ratio": float(center_white_ratio),
                "core_white_ratio": float(core_white_ratio),
                "core_main_ratio": float(core_main_ratio),
                "mid_main_ratio": float(mid_main_ratio),
                "outer_white_ratio": float(outer_white_ratio),
                "global_main_ratio": float(global_main_ratio),
            }

            # 9 號這類條紋球在某些角度會呈現「中心白面很大、彩色只剩一圈」，
            # 不能只靠外圈白帶，否則會被誤壓成 1 號實心球。
            if (
                center_white_ratio >= 0.52
                and white_ratio >= 0.16
                and global_main_ratio <= 0.58
            ):
                style = "Stripe"
            elif (
                white_ratio >= 0.30
                and core_white_ratio >= 0.24
                and global_main_ratio <= 0.42
                and core_main_ratio <= 0.42
            ):
                style = "Stripe"
            elif (
                white_ratio >= 0.26
                and core_white_ratio >= 0.18
                and global_main_ratio <= 0.36
            ):
                style = "Stripe"
            elif core_main_ratio >= 0.45 and outer_white_ratio <= 0.20 and white_ratio <= 0.18:
                style = "Solid"
            elif outer_white_ratio >= 0.28 and core_main_ratio >= 0.15 and mid_main_ratio <= 0.48:
                style = "Stripe"
            elif white_ratio >= 0.24 and (outer_white_ratio - core_white_ratio) > 0.10:
                style = "Stripe"
            elif (
                color_name == "Yellow"
                and white_ratio >= 0.12
                and global_main_ratio <= 0.64
                and (center_white_ratio >= 0.28 or outer_white_ratio >= 0.18)
            ):
                style = "Stripe"
            elif (
                color_name == "Yellow"
                and white_ratio >= 0.10
                and global_main_ratio <= 0.72
                and core_main_ratio < 0.58
            ):
                style = "Unknown"
            elif white_ratio <= 0.16 and core_main_ratio >= 0.34 and global_main_ratio >= 0.48:
                style = "Solid"
            else:
                style = "Unknown"

        return _pack_result(color_name, style, hue_mean, white_ratio, black_ratio, color_ratio, template_score, extra_debug)
    def _circular_hue_diff(self, a: float, b: float) -> float:
        d = abs(float(a) - float(b))
        return min(d, 180.0 - d)

    def _circular_hue_mean(self, h: np.ndarray, w: Optional[np.ndarray] = None) -> float:
        if h.size == 0:
            return -1.0
        ang = (h.astype(np.float32) / 180.0) * (2.0 * np.pi)
        if w is None:
            w = np.ones_like(ang, dtype=np.float32)
        else:
            w = w.astype(np.float32)
        s = np.sum(np.sin(ang) * w)
        c = np.sum(np.cos(ang) * w)
        if abs(s) < 1e-6 and abs(c) < 1e-6:
            return float(np.median(h))
        theta = math.atan2(s, c)
        if theta < 0:
            theta += 2.0 * np.pi
        return float((theta / (2.0 * np.pi)) * 180.0)

    def _template_distance(self, name: str, hue: float, sat_med: float, val_med: float, lab_med: np.ndarray) -> float:
        ref_h = self.COLOR_HUE_CENTER.get(name, -1.0)
        ref_s = self.COLOR_SAT_REF.get(name, 140.0)
        ref_v = self.COLOR_VAL_REF.get(name, 180.0)
        ref_lab = self.COLOR_LAB.get(name)
        if ref_h < 0 or ref_lab is None:
            return 999.0

        hue_d = self._circular_hue_diff(hue, ref_h) / 90.0
        sat_d = abs(float(sat_med) - float(ref_s)) / 255.0
        val_d = abs(float(val_med) - float(ref_v)) / 255.0
        lab_d = float(np.linalg.norm(lab_med.astype(np.float32) - ref_lab.astype(np.float32))) / 64.0
        
        # 增加 S 與 V 的權重，降低單純 H 的權重
        return 0.35 * hue_d + 0.20 * sat_d + 0.15 * val_d + 0.30 * lab_d

    def _dominant_cluster_stats(
        self,
        Hf: np.ndarray,
        Sf: np.ndarray,
        Vf: np.ndarray,
        labf: np.ndarray,
    ) -> Tuple[float, float, float, np.ndarray]:
        n = Hf.size
        if n < 20:
            hue = self._circular_hue_mean(Hf, (Sf * Vf) + 1e-3)
            return hue, float(np.median(Sf)), float(np.median(Vf)), np.median(labf, axis=0).astype(np.float32)

        idx = np.arange(n)
        if n > 320:
            step = max(1, n // 320)
            idx = idx[::step]

        feats = np.stack(
            [
                Hf[idx].astype(np.float32) / 180.0,
                Sf[idx].astype(np.float32) / 255.0,
                Vf[idx].astype(np.float32) / 255.0,
            ],
            axis=1,
        ).astype(np.float32)

        K = 3 if feats.shape[0] >= 60 else 2
        K = min(K, feats.shape[0])
        if K <= 1:
            hue = self._circular_hue_mean(Hf, (Sf * Vf) + 1e-3)
            return hue, float(np.median(Sf)), float(np.median(Vf)), np.median(labf, axis=0).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 14, 0.2)
        _ret, labels, _centers = cv2.kmeans(feats, K, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
        labels = labels.reshape(-1)

        best_k = 0
        best_score = -1.0
        for k in range(K):
            sel = labels == k
            if not np.any(sel):
                continue
            sat_k = float(np.median(Sf[idx][sel]))
            val_k = float(np.median(Vf[idx][sel]))
            size_k = float(np.count_nonzero(sel)) / len(labels)
            score = 0.70 * ((sat_k / 255.0) * (val_k / 255.0)) + 0.30 * size_k
            if score > best_score:
                best_score = score
                best_k = k

        center = _centers[best_k]
        d = np.sqrt(
            (Hf / 180.0 - center[0]) ** 2
            + (Sf / 255.0 - center[1]) ** 2
            + (Vf / 255.0 - center[2]) ** 2
        )
        th = float(np.quantile(d, 0.40))
        sel_full = d <= max(0.08, th)
        if np.count_nonzero(sel_full) < 12:
            sel_full = d <= float(np.quantile(d, 0.55))

        hue = self._circular_hue_mean(Hf[sel_full], (Sf[sel_full] * Vf[sel_full]) + 1e-3)
        sat = float(np.median(Sf[sel_full])) if np.any(sel_full) else float(np.median(Sf))
        val = float(np.median(Vf[sel_full])) if np.any(sel_full) else float(np.median(Vf))
        lab_med = np.median(labf[sel_full], axis=0).astype(np.float32) if np.any(sel_full) else np.median(labf, axis=0).astype(np.float32)
        return hue, sat, val, lab_med

    def _classify_main_color_ab(
        self,
        Hc: np.ndarray,
        Sc: np.ndarray,
        Vc: np.ndarray,
        lab: np.ndarray,
        color_core: np.ndarray,
    ) -> Tuple[str, float, float]:
        """
        A: 模板比對（Hue histogram + LAB中位數 + S中位數）
        B: K-means 主彩群（取最主要彩色群）
        回傳 (color_name, hue_mean, score)
        """
        Hf = Hc[color_core].astype(np.float32)
        Sf = Sc[color_core].astype(np.float32)
        Vf = Vc[color_core].astype(np.float32)
        labf = lab[color_core].reshape(-1, 3).astype(np.float32)

        wgt = (Sf / 255.0) * (Vf / 255.0) + 1e-3
        hue_a = self._circular_hue_mean(Hf, wgt)
        sat_a = float(np.median(Sf))
        val_a = float(np.median(Vf))
        lab_a = np.median(labf, axis=0).astype(np.float32)

        hue_b, sat_b, val_b, lab_b = self._dominant_cluster_stats(Hf, Sf, Vf, labf)

        best_name = "Unknown"
        best_score = 999.0
        score_by_name: Dict[str, float] = {}
        for name in self.COLOR_HUE_CENTER.keys():
            score_a = self._template_distance(name, hue_a, sat_a, val_a, lab_a)
            score_b = self._template_distance(name, hue_b, sat_b, val_b, lab_b)
            score = min(0.55 * score_a + 0.45 * score_b, 0.45 * score_a + 0.55 * score_b)
            score_by_name[name] = float(score)
            if score < best_score:
                best_score = score
                best_name = name

        final_hue = float((0.55 * hue_a) + (0.45 * hue_b))
        blue_score = score_by_name.get("Blue", 999.0)
        purple_score = score_by_name.get("Purple", 999.0)
        if best_name == "Blue" and hue_b >= 124.0 and purple_score <= blue_score + 0.08:
            best_name = "Purple"
            best_score = purple_score
        elif best_name == "Purple" and hue_b <= 122.0 and blue_score <= purple_score + 0.05:
            best_name = "Blue"
            best_score = blue_score

        if best_score > 0.72:
            return "Unknown", final_hue, best_score
        return best_name, final_hue, best_score

    def _build_main_color_mask(
        self,
        Hc: np.ndarray,
        Sc: np.ndarray,
        Vc: np.ndarray,
        lab: np.ndarray,
        valid: np.ndarray,
        color_name: str,
    ) -> np.ndarray:
        """建立主色像素遮罩，供實心/條紋判斷使用。"""
        if color_name not in self.COLOR_HUE_CENTER:
            return np.zeros_like(valid, dtype=bool)

        hue_ref = self.COLOR_HUE_CENTER[color_name]
        hue_tol = 12.0 if color_name in ["Yellow", "Orange", "Brown"] else 16.0
        sat_thr = 35

        hue_diff = np.abs(Hc.astype(np.float32) - hue_ref)
        hue_diff = np.minimum(hue_diff, 180.0 - hue_diff)
        hue_ok = hue_diff <= hue_tol

        ref_lab = self.COLOR_LAB[color_name].astype(np.float32)
        lab_diff = np.linalg.norm(lab.astype(np.float32) - ref_lab, axis=2)
        lab_ok = lab_diff <= 34.0

        sat_ok = Sc >= sat_thr
        val_ok = Vc >= 35
        return valid & sat_ok & val_ok & (hue_ok | lab_ok)

    def _lab_to_name(self, lab_pixels: np.ndarray) -> Tuple[str, float]:
        """Map mean LAB to nearest known color. Returns (name, distance)."""
        if lab_pixels is None or lab_pixels.size == 0:
            return "Unknown", 999.0

        mean_lab = np.mean(lab_pixels.reshape(-1, 3), axis=0).astype(np.float32)
        best_name = "Unknown"
        best_dist = 999.0
        for name, ref in self.COLOR_LAB.items():
            d = float(np.linalg.norm(mean_lab - ref))
            if d < best_dist:
                best_dist = d
                best_name = name

        if best_dist > 34.0:
            return "Unknown", best_dist
        return best_name, best_dist

    def _hue_to_name(self, h: float, vc_pixels: np.ndarray) -> str:
        """Hue 值轉顏色名稱（OpenCV HSV: H=0~180），含黃/橘修正與最近色備援。"""
        if h < 0 or h > 180:
            return "Unknown"

        v_med = float(np.median(vc_pixels)) if vc_pixels.size > 0 else 128.0

        # 主規則：先用較寬鬆區間
        if (h <= 8) or (h >= 165):
            return "Red"

        # 黃/橘/棕交界：依亮度修正，避免 1號黃球被判成 5號橘球
        if 8 < h <= 17:
            if v_med > 165:
                return "Yellow"
            return "Brown" if v_med < 110 else "Orange"
        if 17 < h <= 24:
            return "Yellow" if v_med > 145 else "Orange"
        if 24 < h <= 40:
            return "Yellow"
        if 40 < h <= 86:
            return "Green"
        if 86 < h <= 125:
            return "Blue"
        if 125 < h < 160:
            return "Purple"

        # 備援：最近色（避免 Unknown 太多）
        centers = {
            "Red": 0.0,
            "Orange": 16.0,
            "Yellow": 28.0,
            "Green": 60.0,
            "Blue": 108.0,
            "Purple": 145.0,
            "Brown": 12.0,
        }

        def circ_diff(a: float, b: float) -> float:
            d = abs(a - b)
            return min(d, 180.0 - d)

        best_label = "Unknown"
        best_diff = 1e9
        for label, c in centers.items():
            d = circ_diff(h, c)
            if d < best_diff:
                best_diff = d
                best_label = label

        if best_label in ["Brown", "Orange"]:
            return "Brown" if v_med < 120 else "Orange"
        return best_label

    def _classify_ball_number(self, color_info: Dict[str, Any]) -> Optional[int]:
        """根據顏色和條紋/實心分類球號（1-15）。不確定時不硬猜。"""
        label = color_info.get("label", "Unknown")
        style = color_info.get("style", "Unknown")

        if label == "White" or style == "Cue":
            return 0
        if label == "Black":
            return 8

        if label in self.COLOR_TO_NUM:
            solid, stripe = self.COLOR_TO_NUM[label]
            if style == "Stripe":
                return stripe
            if style == "Solid":
                return solid
            if label == "Yellow" and style == "Unknown":
                # 目前 9 號在正視角/旋轉時最常掉成 Yellow Unknown，
                # 先保守映射成 9 號，避免反覆跳成 1 號或無球號。
                return stripe

        # style/label 不穩定時先回傳 None，避免錯號
        return None

    # ==================== 物理預測 (from poolShotPredictor.py) ====================

    def _find_shot_point(self, cue_pos: List[int], white_ball: List[int]) -> List[int]:
        """計算擊球點（球桿接觸白球的位置）"""
        cue_points = []
        whiteBallX = white_ball[0] + white_ball[2] // 2
        whiteBallY = white_ball[1] + white_ball[3] // 2

        self.radius_mean.append((cue_pos[2] // 2 + cue_pos[3] // 2) // 2)
        radius = sum(self.radius_mean) // max(len(self.radius_mean), 1)

        LX = cue_pos[0] + cue_pos[2] // 2
        LY = cue_pos[1] + cue_pos[3] // 2

        for the in range(0, 360):
            sinus, cosinus = self._find_angle(the)
            DX = int(cosinus * radius)
            DY = int(sinus * radius)
            cue_points.append([LX + DX, LY + DY])

        min_gap = 1000000
        shot_point = [LX, LY]
        for cue_point in cue_points:
            gap = math.hypot(whiteBallX - cue_point[0], whiteBallY - cue_point[1])
            if gap < min_gap:
                min_gap = gap
                shot_point = cue_point

        self.shot_points.append(shot_point)
        sumX = sum(p[0] for p in self.shot_points)
        sumY = sum(p[1] for p in self.shot_points)
        return [sumX // len(self.shot_points), sumY // len(self.shot_points)]

    def _find_angle(self, deg: float) -> Tuple[float, float]:
        """計算角度的 sin, cos"""
        theta = math.radians(deg)
        sinus = math.sin(theta)
        cosinus = math.cos(theta)
        if abs(sinus) < 1e-15:
            sinus = 0
        if abs(cosinus) < 1e-15:
            cosinus = 0
        return sinus, cosinus

    def _find_line(self, p1: List[int], p2: List[int]) -> Tuple[float, float]:
        """計算兩點間直線的斜率和截距"""
        x1, y1 = p1
        x2, y2 = p2
        try:
            m = (y2 - y1) / (x2 - x1)
        except ZeroDivisionError:
            m = (y2 - y1) / (x2 - x1 + 1)
        c = y1 - (m * x1)
        return m, c

    def _collision(self, white_ball: List[int], color_ball: List) -> Tuple[bool, List[int]]:
        """檢測白球與彩球碰撞"""
        white_ball_list = []
        color_ball_list = []

        # 白球周圍點
        radius = (white_ball[2] - white_ball[0]) // 2
        LX = white_ball[0] + (white_ball[2] - white_ball[0]) // 2
        LY = white_ball[1] + (white_ball[3] - white_ball[1]) // 2
        for the in range(0, 360):
            sinus, cosinus = self._find_angle(the)
            DX = int(cosinus * radius)
            DY = int(sinus * radius)
            white_ball_list.append([LX + DX, LY + DY])

        # 彩球周圍點
        radius = color_ball[4]
        LX = color_ball[0] + color_ball[2] // 2
        LY = color_ball[1] + color_ball[3] // 2
        for the in range(0, 360):
            sinus, cosinus = self._find_angle(the)
            DX = int(cosinus * radius)
            DY = int(sinus * radius)
            color_ball_list.append([LX + DX, LY + DY])

        # 找交集
        colls_points = []
        for point in white_ball_list:
            if point in color_ball_list:
                colls_points.append(point)

        if len(colls_points) > 0:
            xPoint = sum(p[0] for p in colls_points) // len(colls_points)
            yPoint = sum(p[1] for p in colls_points) // len(colls_points)
            return True, [xPoint, yPoint]

        return False, []

    def _bounce_detection(self, point: List[int], radius: int) -> Tuple[Tuple[int, int, int], bool]:
        """檢測球是否進袋"""
        color = (80, 145, 75)
        in_hole = False

        for hole in self.hole_bboxes:
            p = point[0] - radius
            q = point[1] - radius
            r = point[0] + radius
            s = point[1] + radius
            if p >= hole[0] and q >= hole[1] and r <= hole[2] and s <= hole[3]:
                in_hole = True
                color = (80, 145, 75)
                break

        return color, in_hole

    def _path_line(self, colls_point: List[int], color_ball: List, paths: List[List[int]]) -> Tuple[List[List[int]], Tuple, bool]:
        """計算彩球反彈路徑"""
        color = (80, 145, 75)
        in_hole = False

        color_ball_center = [color_ball[0] + color_ball[2] // 2, color_ball[1] + color_ball[3] // 2]
        m2, c2 = self._find_line(colls_point, color_ball_center)

        if not self.table_rects:
            return paths, color, in_hole

        for rects in self.table_rects:
            if colls_point[0] > color_ball_center[0]:
                xLast = rects[0] + 40
            else:
                xLast = rects[0] + rects[2] - 40

            for i in range(0, 2):  # 最多反彈2次
                x2 = xLast
                y2 = int((m2 * x2) + c2)

                # 邊界限制
                if y2 >= rects[1] + rects[3] - 40:
                    y2 = rects[1] + rects[3] - 40
                    x2 = int((y2 - c2) / m2) if m2 != 0 else x2
                if y2 <= rects[1] + 40:
                    y2 = rects[1] + 40
                    x2 = int((y2 - c2) / m2) if m2 != 0 else x2
                if x2 >= rects[0] + rects[2] - 40:
                    x2 = rects[0] + rects[2] - 40
                    y2 = int((m2 * x2) + c2)
                    xLast = rects[0] + 40
                if x2 <= rects[0] + 40:
                    x2 = rects[0] + 40
                    y2 = int((m2 * x2) + c2)
                    xLast = rects[0] + rects[2] - 40

                paths.append([x2, y2])
                color, in_hole = self._bounce_detection(paths[-1], 6)

                if in_hole:
                    return paths, color, in_hole
                else:
                    m2 = -m2
                    c2 = y2 - (m2 * x2)

        return paths, color, in_hole

    def _pool_shot_prediction(self, shot_point: List[int], white_ball: List[int], color_ball: List) -> Optional[Dict]:
        """完整的撞球預測邏輯"""
        try:
            # 1. 白球射線方程
            m1, c1 = self._find_line(
                shot_point,
                [white_ball[0] + white_ball[2] // 2, white_ball[1] + white_ball[3] // 2]
            )

            points = []
            xLast = color_ball[0] + color_ball[2] // 2
            section = 1 if xLast >= white_ball[0] + white_ball[2] // 2 else -1

            for x in range(white_ball[0] + white_ball[2] // 2, xLast, section):
                y = int((m1 * x) + c1)
                points.append([x, y])

            # 2. 碰撞檢測
            for point in points:
                p = point[0] - white_ball[2] // 2
                q = point[1] - white_ball[3] // 2
                r = point[0] + white_ball[2] // 2
                s = point[1] + white_ball[3] // 2
                box = [p, q, r, s]

                color_ball_point = [
                    color_ball[0],
                    color_ball[1],
                    color_ball[0] + color_ball[2],
                    color_ball[1] + color_ball[3],
                    color_ball[4] if len(color_ball) > 4 else 0
                ]

                colls, colls_point = self._collision(box, color_ball_point)

                if colls:
                    # 3. 計算彩球路徑
                    paths = [[color_ball[0] + color_ball[2] // 2, color_ball[1] + color_ball[3] // 2]]
                    paths, color_result, in_hole = self._path_line(colls_point, color_ball, paths)

                    # 4. 取得彩球顏色資訊
                    ball_color_info = color_ball[6] if len(color_ball) > 6 else {"label": "Unknown", "style": "Unknown"}
                    ball_number = color_ball[7] if len(color_ball) > 7 else None

                    return {
                        "prediction": in_hole,
                        "paths": paths,
                        "color": color_result,
                        "collision_point": colls_point,
                        "ball_color": f"{ball_color_info.get('label', 'Unknown')} - {ball_color_info.get('style', 'Unknown')}",
                        "ball_number": ball_number,
                        "ball_color_meta": ball_color_info,
                    }

        except (TypeError, IndexError, ZeroDivisionError) as e:
            print(f"⚠️ Prediction error: {e}")
            return None

        return None
    
    def _calculate_bank_shot(
        self, 
        ball_pos: List[int],  # [cx, cy]
        ball_velocity: List[float],  # [vx, vy] 速度向量
    ) -> List[List[int]]:
        """
        計算反彈路徑 (最多3次反彈)
        
        Args:
            ball_pos: 球心位置 [cx, cy]
            ball_velocity: 速度向量 [vx, vy]
        
        Returns:
            路徑點列表 [[x1,y1], [x2,y2], [x3,y3], ...]
        """
        if not self.table_roi:
            return [[ball_pos[0], ball_pos[1]]]
        
        # 球桌邊界
        tx, ty, tw, th = self.table_roi
        x1, y1 = tx + 25, ty + 25  # 內縮邊界
        x2, y2 = tx + tw - 25, ty + th - 25
        
        cx, cy = ball_pos
        vx, vy = ball_velocity
        
        # 正規化速度向量
        v_mag = math.sqrt(vx*vx + vy*vy)
        if v_mag == 0:
            return [[cx, cy]]
        vx, vy = vx/v_mag, vy/v_mag
        
        path = [[cx, cy]]
        max_bounces = 3  # 最多3次反彈
        bounce_count = 0
        
        # 當前位置和速度
        curr_x, curr_y = float(cx), float(cy)
        curr_vx, curr_vy = vx, vy
        
        while bounce_count < max_bounces:
            # 計算下一個碰撞點
            t_min = float('inf')
            hit_wall = None
            
            # 上邊界 (y = y1)
            if curr_vy < 0:
                t = (y1 - curr_y) / curr_vy
                if t > 0 and t < t_min:
                    hit_x = curr_x + curr_vx * t
                    if x1 <= hit_x <= x2:
                        t_min = t
                        hit_wall = 'top'
            
            # 下邊界 (y = y2)
            if curr_vy > 0:
                t = (y2 - curr_y) / curr_vy
                if t > 0 and t < t_min:
                    hit_x = curr_x + curr_vx * t
                    if x1 <= hit_x <= x2:
                        t_min = t
                        hit_wall = 'bottom'
            
            # 左邊界 (x = x1)
            if curr_vx < 0:
                t = (x1 - curr_x) / curr_vx
                if t > 0 and t < t_min:
                    hit_y = curr_y + curr_vy * t
                    if y1 <= hit_y <= y2:
                        t_min = t
                        hit_wall = 'left'
            
            # 右邊界 (x = x2)
            if curr_vx > 0:
                t = (x2 - curr_x) / curr_vx
                if t > 0 and t < t_min:
                    hit_y = curr_y + curr_vy * t
                    if y1 <= hit_y <= y2:
                        t_min = t
                        hit_wall = 'right'
            
            if hit_wall is None or t_min == float('inf'):
                # 沒有碰撞,直接延伸一段距離後結束
                extend_dist = 200
                end_x = int(curr_x + curr_vx * extend_dist)
                end_y = int(curr_y + curr_vy * extend_dist)
                # 確保不超出邊界
                end_x = max(x1, min(x2, end_x))
                end_y = max(y1, min(y2, end_y))
                path.append([end_x, end_y])
                break
            
            # 計算碰撞點
            bounce_x = curr_x + curr_vx * t_min
            bounce_y = curr_y + curr_vy * t_min
            path.append([int(bounce_x), int(bounce_y)])
            
            # 更新位置
            curr_x, curr_y = bounce_x, bounce_y
            
            # 反彈: 反轉對應方向的速度
            if hit_wall in ['top', 'bottom']:
                curr_vy = -curr_vy
            else:  # left, right
                curr_vx = -curr_vx
            
            bounce_count += 1
            
            # 添加反彈後的一小段路徑
            extend_dist = 150
            end_x = int(curr_x + curr_vx * extend_dist)
            end_y = int(curr_y + curr_vy * extend_dist)
            # 確保不超出邊界
            end_x = max(x1, min(x2, end_x))
            end_y = max(y1, min(y2, end_y))
            
            if bounce_count < max_bounces:
                # 不是最後一次,繼續計算
                path.append([end_x, end_y])
        
        return path
    
    def _calculate_aim_assist(
        self, 
        white_ball: Dict[str, int], 
        target_ball: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        計算瞄準輔助線 (類似 8 Ball Pool)
        
        Args:
            white_ball: 母球 bbox {x, y, w, h}
            target_ball: 目標球 {x, y, w, h, radius}
        
        Returns:
            {
                "cue_to_target": [[x1,y1], [x2,y2]],  # 母球→撞擊點
                "target_to_hole": [[x1,y1], [x2,y2]], # 目標球→洞口
                "impact_point": [x, y],                # 撞擊點
                "target_hole": [x, y],                 # 目標洞口
                "success_probability": 0.85,           # 成功率
                "cut_angle": 30.0                      # 切球角度 (度)
            }
        """
        if not self.holes:
            return None
        
        # 1. 計算球心
        white_cx = white_ball['x'] + white_ball['w'] // 2
        white_cy = white_ball['y'] + white_ball['h'] // 2
        
        target_cx = target_ball['x'] + target_ball['w'] // 2
        target_cy = target_ball['y'] + target_ball['h'] // 2
        target_r = float(target_ball.get('radius') or (target_ball['w'] // 2))
        
        # 2. 找到最合適的洞口 (切角小於 85 度且距離最近)
        white_to_target_dx = target_cx - white_cx
        white_to_target_dy = target_cy - white_cy
        white_to_target_dist = math.sqrt(
            white_to_target_dx*white_to_target_dx + 
            white_to_target_dy*white_to_target_dy
        )

        if white_to_target_dist == 0:
            return None
            
        best_hole = None
        min_dist = float('inf')
        best_cut_angle = 0.0
        best_hole_dir: Optional[Tuple[float, float]] = None
        best_hole_dist = 0.0
        
        for hole in self.holes:
            hole_dx = hole[0] - target_cx
            hole_dy = hole[1] - target_cy
            hole_dist = math.sqrt(hole_dx*hole_dx + hole_dy*hole_dy)
            
            if hole_dist == 0:
                continue
                
            hole_dir_x = hole_dx / hole_dist
            hole_dir_y = hole_dy / hole_dist
            
            # 計算夾角 (點積 / 模長乘積)
            cos_angle = (
                white_to_target_dx * hole_dir_x + 
                white_to_target_dy * hole_dir_y
            ) / white_to_target_dist
            
            # 防止數值誤差
            cos_angle = max(-1.0, min(1.0, cos_angle))
            cut_angle_deg = math.degrees(math.acos(cos_angle))
            
            # 物理限制: 切球角度必須小於 ~85 度 (大於 90 度代表要打這顆球的背面)
            if cut_angle_deg < 85:
                if hole_dist < min_dist:
                    min_dist = hole_dist
                    best_hole = hole
                    best_cut_angle = cut_angle_deg
                    best_hole_dir = (hole_dir_x, hole_dir_y)
                    best_hole_dist = hole_dist
        
        if not best_hole or best_hole_dir is None:
            return None
        
        # 3. 計算幽靈球 (Ghost Ball) 的中心位置
        # 母球撞擊子球的瞬間，母球中心點會停在子球中心沿反方向退後兩個球半徑的距離
        white_r = float(white_ball.get('w', 20) // 2)
        ghost_dist = target_r + white_r
        ghost_cx = target_cx - best_hole_dir[0] * ghost_dist
        ghost_cy = target_cy - best_hole_dir[1] * ghost_dist
        
        # 4. 計算母球分離角 (Tangent Line)
        # 母球撞擊子球後，會沿著與子球前進方向垂直的切線方向移動（假設無特殊旋轉）
        v_in_x = ghost_cx - white_cx
        v_in_y = ghost_cy - white_cy
        
        # 投影(內積)
        dot_product = v_in_x * best_hole_dir[0] + v_in_y * best_hole_dir[1]
        
        # 扣除平行的分量，剩下的就是切線分量
        v_t_x = v_in_x - dot_product * best_hole_dir[0]
        v_t_y = v_in_y - dot_product * best_hole_dir[1]
        
        v_t_len = math.sqrt(v_t_x**2 + v_t_y**2)
        separation_line = None
        
        if v_t_len > 0.1:  # 避免完全直線沒有分離角
            norm_v_t_x = v_t_x / v_t_len
            norm_v_t_y = v_t_y / v_t_len
            
            # 使用固定長度 (或是依撞擊力道比例) 畫出母球分離路線
            sep_length = 200
            sep_end_x = ghost_cx + norm_v_t_x * sep_length
            sep_end_y = ghost_cy + norm_v_t_y * sep_length
            
            separation_line = [
                [int(ghost_cx), int(ghost_cy)],
                [int(sep_end_x), int(sep_end_y)]
            ]
        
        # 5. 計算成功率 (角度越小越容易進)
        success_prob = max(0.0, (90.0 - best_cut_angle) / 90.0)
        
        return {
            "cue_to_target": [
                [white_cx, white_cy],
                [int(ghost_cx), int(ghost_cy)]
            ],
            "target_to_hole": [
                [target_cx, target_cy],
                best_hole
            ],
            "separation_line": separation_line,
            "impact_point": [int(ghost_cx), int(ghost_cy)],
            "target_hole": best_hole,
            "ghost_ball": {
                "cx": int(ghost_cx),
                "cy": int(ghost_cy),
                "r": int(white_r)
            },
            "success_probability": round(success_prob, 2),
            "cut_angle": round(best_cut_angle, 1)
        }

    def _aim_assist_from_route(self, route: Dict[str, Any], white_primary: List[int]) -> Optional[Dict[str, Any]]:
        metadata = route.get("metadata", {}) if isinstance(route, dict) else {}
        ghost = metadata.get("ghost_ball") if isinstance(metadata, dict) else None
        if not isinstance(ghost, list) or len(ghost) < 2:
            cue_segment = next(
                (
                    segment
                    for segment in route.get("route_segments", [])
                    if isinstance(segment, dict)
                    and segment.get("type") == "cue_to_contact"
                    and len(segment.get("points", [])) >= 2
                ),
                None,
            )
            if not cue_segment:
                return None
            ghost = cue_segment["points"][-1]

        white_r = max(1, min(white_primary[2], white_primary[3]) // 2)
        return {
            "ghost_ball": {
                "cx": int(ghost[0]),
                "cy": int(ghost[1]),
                "r": int(white_r),
            }
        }
    
    def _draw_dotted_line(
        self, 
        img: np.ndarray, 
        pt1: List[int], 
        pt2: List[int],
        color: Tuple[int, int, int],
        thickness: int = 2,
        gap: int = 10
    ):
        """繪製虛線"""
        dist = math.sqrt((pt2[0]-pt1[0])**2 + (pt2[1]-pt1[1])**2)
        pts = []
        for i in np.arange(0, dist, gap):
            r = i / dist
            x = int((1-r)*pt1[0] + r*pt2[0])
            y = int((1-r)*pt1[1] + r*pt2[1])
            pts.append((x, y))
        
        # 繪製虛線段
        for i in range(0, len(pts)-1, 2):
            if i+1 < len(pts):
                cv2.line(img, pts[i], pts[i+1], color, thickness)
    
    def _draw_aim_assist(self, img: np.ndarray, aim_data: Dict[str, Any]):
        """
        繪製瞄準輔助線 (類似 8 Ball Pool)
        
        Args:
            img: 影像
            aim_data: _calculate_aim_assist 回傳的資料
        """
        # 1. 繪製目標球→洞口路徑 (虛線,黃色)
        target_to_hole = aim_data["target_to_hole"]
        self._draw_dotted_line(
            img, 
            target_to_hole[0], 
            target_to_hole[1],
            color=(0, 255, 255),  # 黃色
            thickness=3,
            gap=15
        )
        
        # 2. 繪製母球→撞擊點路徑 (實線,白色)
        cue_to_target = aim_data["cue_to_target"]
        
        # 繪製邊框 (黑色,更粗)
        cv2.line(
            img,
            tuple(cue_to_target[0]),
            tuple(cue_to_target[1]),
            (0, 0, 0),  # 黑色
            thickness=6
        )
        
        # 繪製主線
        cv2.line(
            img,
            tuple(cue_to_target[0]),
            tuple(cue_to_target[1]),
            (255, 255, 255),  # 白色
            thickness=4
        )
        
        # 3. 繪製幽靈球 (取代原本不精準的紅色撞擊點)
        if "ghost_ball" in aim_data:
            self._draw_ghost_ball(img, aim_data)
        
        # 4. 繪製母球分離角路徑 (虛線, 紫/粉色)
        if "separation_line" in aim_data and aim_data["separation_line"]:
            sep_line = aim_data["separation_line"]
            self._draw_dotted_line(
                img,
                sep_line[0],
                sep_line[1],
                color=(255, 105, 180),  # 亮粉/紫色
                thickness=3,
                gap=10
            )
            
        # 5. 繪製目標洞口標記 (綠色圓圈，調小尺寸並避免過度外拓)
        target_hole = aim_data["target_hole"]
        cv2.circle(img, tuple(target_hole), 22, (0, 255, 0), 2)
        cv2.circle(img, tuple(target_hole), 15, (0, 255, 0), 2)
        
        # 5. 顯示成功率和角度
        prob = aim_data["success_probability"]
        angle = aim_data["cut_angle"]
        
        # 根據成功率選擇顏色
        if prob > 0.7:
            prob_color = (0, 255, 0)  # 綠色
        elif prob > 0.4:
            prob_color = (0, 255, 255)  # 黃色
        else:
            prob_color = (0, 0, 255)  # 紅色
        
        # 在母球上方顯示資訊
        white_pos = cue_to_target[0]
        text = f"Success: {int(prob*100)}%"
        cv2.putText(
            img, text,
            (white_pos[0] - 50, white_pos[1] - 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, prob_color, 2
        )
        
        angle_text = f"Angle: {angle:.0f}deg"
        cv2.putText(
            img, angle_text,
            (white_pos[0] - 50, white_pos[1] - 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (255, 255, 255), 2
        )

    # ==================== 繪製結果 ====================
    def _safe_bbox_center_radius(self, bbox: Any) -> Optional[Tuple[Tuple[int, int], int]]:
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            return None
        try:
            x, y, w, h = (int(float(v)) for v in bbox[:4])
        except (TypeError, ValueError):
            return None
        if w <= 0 or h <= 0:
            return None
        return (x + w // 2, y + h // 2), max(2, min(w, h) // 2)

    def _ball_bbox_from_packet(self, ball: Any) -> Optional[List[int]]:
        if not isinstance(ball, dict):
            return None
        try:
            return [
                int(float(ball.get("x", 0))),
                int(float(ball.get("y", 0))),
                int(float(ball.get("w", 0))),
                int(float(ball.get("h", 0))),
            ]
        except (TypeError, ValueError):
            return None

    def _find_tactical_target_ball(self, data: Dict[str, Any], route: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        balls = data.get("balls", [])
        if not isinstance(balls, list) or not balls:
            return None

        target_number = route.get("target_ball_number") if isinstance(route, dict) else None
        if target_number is not None:
            for ball in balls:
                if isinstance(ball, dict) and str(ball.get("number")) == str(target_number):
                    return ball

        prediction = data.get("prediction")
        prediction_number = prediction.get("ball_number") if isinstance(prediction, dict) else None
        if prediction_number is not None:
            for ball in balls:
                if isinstance(ball, dict) and str(ball.get("number")) == str(prediction_number):
                    return ball

        return balls[0] if isinstance(balls[0], dict) else None

    def _annotation_color_from_ball(self, ball: Optional[Dict[str, Any]], fallback: Tuple[int, int, int] = (160, 160, 160)) -> Tuple[int, int, int]:
        if not isinstance(ball, dict):
            return fallback
        color_name = str(ball.get("color") or ball.get("label") or "Unknown")
        return self.COLORS_BGR.get(color_name, fallback)

    def _draw_ball_annotation_ring(
        self,
        img: np.ndarray,
        center: Tuple[int, int],
        radius: int,
        color: Tuple[int, int, int],
        thickness: int = 3,
    ):
        pad = max(0, int(getattr(config, "BALL_ANNOTATION_RADIUS_PADDING", 2)))
        ring_radius = max(1, int(radius) + pad)
        is_black = max(color) <= 32
        outer_color = (255, 255, 255) if is_black else (0, 0, 0)
        cv2.circle(img, center, ring_radius, outer_color, thickness + 3, cv2.LINE_AA)
        cv2.circle(img, center, ring_radius, color, thickness, cv2.LINE_AA)
        cv2.circle(img, center, 3, color, -1, cv2.LINE_AA)

    def _draw_detected_ball_annotation(
        self,
        img: np.ndarray,
        bbox: Any,
        ball: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
        color: Optional[Tuple[int, int, int]] = None,
        thickness: int = 3,
    ):
        parsed = self._safe_bbox_center_radius(bbox)
        if parsed is None:
            return
        center, radius = parsed
        x = int(float(bbox[0]))
        y = int(float(bbox[1]))
        color = color or self._annotation_color_from_ball(ball)
        self._draw_ball_annotation_ring(img, center, radius, color, thickness=thickness)
        if label:
            cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def _route_segment_color(self, segment_type: Any) -> Tuple[int, int, int]:
        segment_colors = {
            "cue_to_contact": (255, 255, 255),
            "object_to_pocket": (80, 220, 75),
            "object_to_rail": (80, 220, 75),
            "object_after_contact": (80, 220, 75),
            "combo_transfer": (0, 220, 255),
            "cue_after_contact": (255, 220, 0),
        }
        return segment_colors.get(str(segment_type), (80, 145, 75))

    def _draw_route_segments(self, img: np.ndarray, route: Dict[str, Any], style: str = "full"):
        route_segments = route.get("route_segments", [])
        if not isinstance(route_segments, list):
            return

        is_tactical = style == "tactical"
        line_thickness = 4
        outline_thickness = 7 if is_tactical else 0
        point_radius = 6 if is_tactical else 7

        for segment in route_segments:
            if not isinstance(segment, dict):
                continue
            points = segment.get("points", [])
            if not isinstance(points, list) or len(points) < 2:
                continue
            color = self._route_segment_color(segment.get("type"))
            for i in range(len(points) - 1):
                try:
                    p1 = tuple(int(float(v)) for v in points[i][:2])
                    p2 = tuple(int(float(v)) for v in points[i + 1][:2])
                except (TypeError, ValueError):
                    continue
                if outline_thickness:
                    cv2.line(img, p1, p2, (0, 0, 0), outline_thickness, cv2.LINE_AA)
                cv2.line(img, p1, p2, color, line_thickness, cv2.LINE_AA)
                cv2.circle(img, p1, point_radius, color, -1, cv2.LINE_AA)
            try:
                last_point = tuple(int(float(v)) for v in points[-1][:2])
            except (TypeError, ValueError):
                continue
            cv2.circle(img, last_point, point_radius, color, -1, cv2.LINE_AA)

    def _cue_landing_marker_from_route(self, route: Dict[str, Any]) -> Optional[Tuple[Tuple[int, int], int]]:
        zone = route.get("cue_landing_zone")
        landing = route.get("cue_landing_point")

        center = None
        radius = 34
        if isinstance(zone, dict):
            raw_center = zone.get("center")
            if isinstance(raw_center, list) and len(raw_center) >= 2:
                try:
                    center = (int(float(raw_center[0])), int(float(raw_center[1])))
                except (TypeError, ValueError):
                    center = None
            try:
                radius = int(zone.get("radius", radius) or radius)
            except (TypeError, ValueError):
                radius = 34
        elif isinstance(landing, list) and len(landing) >= 2:
            try:
                center = (int(float(landing[0])), int(float(landing[1])))
            except (TypeError, ValueError):
                center = None

        if center is None:
            return None

        return center, max(10, min(80, radius))

    def _draw_cue_landing_marker(self, img: np.ndarray, route: Dict[str, Any], show_label: bool = False):
        marker = self._cue_landing_marker_from_route(route)
        if marker is None:
            return

        center, radius = marker
        color = (255, 220, 0)
        cv2.circle(img, center, radius, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.circle(img, center, radius, color, 2, cv2.LINE_AA)
        cv2.circle(img, center, 5, color, -1, cv2.LINE_AA)
        if show_label:
            cv2.putText(
                img,
                "LAND",
                (center[0] + 10, center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

    def _draw_tactical_prediction(self, img: np.ndarray, prediction: Dict[str, Any]):
        paths = prediction.get("paths", []) if isinstance(prediction, dict) else []
        if not isinstance(paths, list) or len(paths) < 2:
            return
        for i in range(len(paths) - 1):
            try:
                p1 = tuple(int(float(v)) for v in paths[i][:2])
                p2 = tuple(int(float(v)) for v in paths[i + 1][:2])
            except (TypeError, ValueError):
                continue
            cv2.line(img, p1, p2, (0, 0, 0), 6, cv2.LINE_AA)
            cv2.line(img, p1, p2, (80, 220, 75), 3, cv2.LINE_AA)

    def _draw_tactical_annotations(self, img: np.ndarray, data: Dict[str, Any]):
        """極簡戰術模式：只畫母球、目標球、路線與母球落點。"""
        multi_plan = data.get("multi_plan")
        best_route = multi_plan.get("best_route") if isinstance(multi_plan, dict) else None
        if not isinstance(best_route, dict):
            best_route = None

        target_ball = self._find_tactical_target_ball(data, best_route)

        if data.get("white_ball"):
            self._draw_detected_ball_annotation(
                img,
                data["white_ball"],
                label=None,
                color=self.COLORS_BGR["White"],
                thickness=3,
            )

        target_bbox = self._ball_bbox_from_packet(target_ball)
        if target_bbox:
            self._draw_detected_ball_annotation(img, target_bbox, ball=target_ball, thickness=3)

        if best_route:
            self._draw_route_segments(img, best_route, style="tactical")
            self._draw_cue_landing_marker(img, best_route)
            return

        prediction = data.get("prediction")
        if isinstance(prediction, dict):
            self._draw_tactical_prediction(img, prediction)

    def _draw_annotations(self, img: np.ndarray, data: Dict[str, Any]):
        """在影像上繪製所有標註"""
        mode = str(getattr(config, "TRACKER_ANNOTATION_MODE", "full")).strip().lower()
        if mode == "none":
            return
        if mode == "tactical":
            self._draw_tactical_annotations(img, data)
            return

        # 1. 繪製球桌框
        table_roi = data.get("table_roi") if isinstance(data, dict) else None
        if not table_roi:
            table_roi = self.table_roi
        if table_roi:
            tx, ty, tw, th = [int(v) for v in table_roi[:4]]
            cv2.rectangle(img, (tx, ty), (tx + tw, ty + th), (0, 255, 0), 2)

        # 2. 繪製球袋
        holes = data.get("holes") if isinstance(data, dict) else None
        if not holes:
            holes = self.holes
        for hole in holes:
            cv2.circle(img, tuple([int(v) for v in hole[:2]]), 15, (255, 0, 0), 2)

        if data.get("cue_laser_only"):
            self._draw_raw_yolo_boxes(img, data.get("raw_yolo_boxes", []))

        # 3. 繪製白球
        if data.get("white_ball"):
            self._draw_detected_ball_annotation(
                img,
                data["white_ball"],
                label="WHITE",
                color=self.COLORS_BGR["White"],
                thickness=3,
            )

        # 4. 繪製彩球（含球號和顏色）
        for ball in data.get("balls", []):
            color_name = ball.get("color", "Unknown")
            ball_num = ball.get("number")
            style = ball.get("style", "Unknown")

            if ball_num is not None:
                label = f"#{ball_num} {color_name[:3]} {style[:3]}"
            else:
                label = f"{color_name[:5]} {style[:3]}"

            bbox = [ball.get("x"), ball.get("y"), ball.get("w"), ball.get("h")]
            self._draw_detected_ball_annotation(img, bbox, ball=ball, label=label, thickness=3)

        # 5. 繪製球桿
        if data.get("cue"):
            x, y, w, h = data["cue"]
            cx, cy = x + w // 2, y + h // 2
            cv2.putText(img, "CUE", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # 6. 優先繪製多球全局規劃路線
        multi_plan = data.get("multi_plan")
        if isinstance(multi_plan, dict):
            best_route = multi_plan.get("best_route")
            if best_route:
                self._draw_multi_route_plan(img, best_route)
                self._draw_route_ghost_ball(img, best_route, data.get("white_ball"))
                return

            error_text = str(multi_plan.get("error") or "NO_ROUTE_FOUND")
            cv2.putText(img, "MULTI PLAN", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            cv2.putText(img, "NO ROUTE", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            cv2.putText(img, str(error_text), (50, 155), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)
            cv2.putText(img, "REPOSITION / KICK / ESCAPE", (50, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 2)
            return

        # 7. 繪製舊版預測路徑
        prediction = data.get("prediction")
        if prediction:
            paths = prediction.get("paths", [])
            in_hole = prediction.get("prediction", False)

            # 繪製路徑線
            if len(paths) > 1:
                for i in range(len(paths) - 1):
                    cv2.line(img, tuple(paths[i]), tuple(paths[i + 1]), (80, 145, 75), 3)
                    cv2.circle(img, tuple(paths[i]), 8, (80, 145, 75), -1)

            # 顯示預測結果
            text = "PREDICTION: IN" if in_hole else "PREDICTION: OUT"
            text_color = (0, 255, 0) if in_hole else (64, 97, 200)
            cv2.putText(img, text, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, text_color, 3)

            # 顯示球號
            if prediction.get("ball_number"):
                ball_text = f"Ball #{prediction['ball_number']}"
                cv2.putText(img, ball_text, (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        
        # 8. 繪製瞄準輔助線
        aim_assist = data.get("aim_assist")
        if aim_assist:
            self._draw_aim_assist(img, aim_assist)

    def _draw_raw_yolo_boxes(self, img: np.ndarray, boxes: Any):
        """cue-laser-only 模式用的輕量 YOLO bbox 標註，不做球色分類。"""
        if not isinstance(boxes, list):
            return

        color_map = {
            "white-ball": (255, 255, 255),
            "color-ball": (0, 220, 255),
            "cue": (0, 255, 0),
        }
        label_map = {
            "white-ball": "WHITE",
            "color-ball": "BALL",
            "cue": "CUE",
        }
        for box in boxes:
            if not isinstance(box, dict):
                continue
            try:
                x = int(box.get("x", 0))
                y = int(box.get("y", 0))
                w = int(box.get("w", 0))
                h = int(box.get("h", 0))
                label = str(box.get("label", ""))
                conf = float(box.get("conf", 0.0))
            except (TypeError, ValueError):
                continue
            if w <= 0 or h <= 0:
                continue
            if label in {"white-ball", "color-ball"}:
                continue
            color = color_map.get(label, (180, 180, 180))
            text = f"{label_map.get(label, label.upper())} {conf:.2f}"
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            cv2.putText(img, text, (x, max(18, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def _draw_ghost_ball_marker(self, img: np.ndarray, center: Tuple[int, int], radius: int):
        if radius <= 0:
            return
        cv2.circle(img, center, radius, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.circle(img, center, 2, (200, 200, 200), -1, cv2.LINE_AA)

    def _draw_ghost_ball(self, img: np.ndarray, aim_data: Dict[str, Any]):
        ghost = aim_data.get("ghost_ball") if isinstance(aim_data, dict) else None
        if not isinstance(ghost, dict):
            return

        gx = int(ghost.get("cx", 0))
        gy = int(ghost.get("cy", 0))
        gr = int(ghost.get("r", 0))
        if gr <= 0:
            return

        self._draw_ghost_ball_marker(img, (gx, gy), gr)

    def _draw_route_ghost_ball(self, img: np.ndarray, route: Dict[str, Any], white_ball: Any):
        if not isinstance(route, dict) or not isinstance(white_ball, list) or len(white_ball) < 4:
            return
        route_aim = self._aim_assist_from_route(route, white_ball)
        if route_aim:
            self._draw_ghost_ball(img, route_aim)

    def _draw_combo_contact_marker(self, img: np.ndarray, route: Dict[str, Any]):
        metadata = route.get("metadata", {}) if isinstance(route.get("metadata"), dict) else {}
        second_ghost = metadata.get("combo_second_ghost")
        if not isinstance(second_ghost, list) or len(second_ghost) < 2:
            return

        cx = int(second_ghost[0])
        cy = int(second_ghost[1])
        cv2.circle(img, (cx, cy), 12, (0, 165, 255), 3, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), 3, (0, 165, 255), -1, cv2.LINE_AA)
        cv2.putText(
            img,
            "C2",
            (cx + 10, cy + 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 165, 255),
            2,
        )

    def _draw_position_zone(
        self,
        img: np.ndarray,
        zone: Any,
        color: Tuple[int, int, int],
        label: str,
        filled: bool = False,
    ):
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
        radius = max(8, min(140, radius))
        if filled:
            h, w = img.shape[:2]
            pad = radius + 4
            x1 = max(0, cx - pad)
            y1 = max(0, cy - pad)
            x2 = min(w, cx + pad + 1)
            y2 = min(h, cy + pad + 1)
            if x1 < x2 and y1 < y2:
                roi = img[y1:y2, x1:x2]
                overlay = roi.copy()
                cv2.circle(overlay, (cx - x1, cy - y1), radius, color, -1, cv2.LINE_AA)
                cv2.addWeighted(overlay, 0.18, roi, 0.82, 0, roi)
        cv2.circle(img, (cx, cy), radius, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), radius, color, 2, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), 4, color, -1, cv2.LINE_AA)
        if label:
            cv2.putText(img, label, (cx + radius + 6, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(img, label, (cx + radius + 6, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

    def _draw_position_play_markers(self, img: np.ndarray, route: Dict[str, Any]):
        position_play = route.get("position_play")
        if not isinstance(position_play, dict):
            return
        cue_after = position_play.get("cue_ball_after_contact")
        if not isinstance(cue_after, dict):
            return

        self._draw_position_zone(img, cue_after.get("target_zone"), (40, 210, 255), "TARGET", filled=True)
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
                self._draw_position_zone(img, zone, (0, 0, 255), "AVOID")
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
                number = next_ball.get("number")
                label = f"NEXT {number}" if number is not None else "NEXT"
                cv2.circle(img, (nx, ny), 18, (0, 220, 255), 3, cv2.LINE_AA)
                cv2.circle(img, (nx, ny), 4, (0, 220, 255), -1, cv2.LINE_AA)
                cv2.putText(img, label, (nx + 22, ny - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(img, label, (nx + 22, ny - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 2, cv2.LINE_AA)

    def _draw_multi_route_plan(self, img: np.ndarray, route: Dict[str, Any]):
        self._draw_route_segments(img, route, style="full")

        route_type = route.get("route_type", "route")
        ball_number = route.get("target_ball_number")
        metadata = route.get("metadata", {}) if isinstance(route.get("metadata"), dict) else {}
        combo_second = metadata.get("combo_second_ball_number")
        ball_label = f"Ball #{ball_number}"
        if route_type == "combo" and combo_second is not None:
            ball_label = f"Ball #{ball_number} -> #{combo_second}"
        success_prob = float(route.get("success_prob", 0.0))
        difficulty = route.get("difficulty", "-")
        cv2.putText(img, "MULTI PLAN", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.putText(
            img,
            f"{ball_label} {route_type} {int(success_prob * 100)}% D:{difficulty}",
            (50, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

        stroke = route.get("stroke_hint", {})
        if isinstance(stroke, dict):
            cv2.putText(
                img,
                f"Stroke: {stroke.get('type', '-')}/{stroke.get('power', '-')}/{stroke.get('spin', '-')}",
                (50, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 220, 0),
                2,
            )

        self._draw_cue_landing_marker(img, route, show_label=True)
        self._draw_position_play_markers(img, route)
        if route.get("route_type") == "combo":
            self._draw_combo_contact_marker(img, route)


