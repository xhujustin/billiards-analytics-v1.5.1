"""
測試 tracking_engine.py 功能的診斷腳本
"""
import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tracking.tracking_engine import PoolTracker
import config

def _create_tracker():
    try:
        return PoolTracker(model_path=config.MODEL_PATH)
    except Exception as e:
        pytest.skip(f"PoolTracker 初始化失敗: {e}")

@pytest.fixture
def tracker():
    return _create_tracker()

def test_tracker_init(tracker):
    """測試 tracker 初始化"""
    assert tracker is not None
    assert tracker.conf_thr >= 0.0
    assert tracker.iou_thr >= 0.0

def test_table_detection(tracker):
    """測試球桌檢測"""
    # 創建測試影像（綠色背景）
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # 繪製綠色區域模擬球桌
    cv2.rectangle(test_frame, (100, 100), (1100, 600), (50, 180, 50), -1)

    try:
        success, roi = tracker.detect_table(test_frame)
        assert isinstance(success, bool)
    except Exception as e:
        pytest.fail(f"球桌檢測錯誤: {e}")

def test_table_detection_repairs_partial_hsv_roi_with_pockets():
    """啟動時 HSV 只抓到半桌時，應改用袋口幾何估算完整 ROI。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.hsv_lower = np.array([90, 50, 50], dtype=np.uint8)
    tracker.hsv_upper = np.array([130, 255, 255], dtype=np.uint8)
    tracker.current_table_color = "blue"
    tracker.table_roi = None
    tracker.table_roi_raw = None
    tracker.table_roi_points = None
    tracker.table_roi_adjustment = {"left": 0, "top": 0, "right": 0, "bottom": 0}
    tracker.table_roi_status = "uninitialized"
    tracker.holes = []
    tracker.hole_bboxes = []
    tracker.table_rects = []

    hsv_frame = np.full((720, 1280, 3), (0, 0, 210), dtype=np.uint8)
    # 左半邊落在目前 HSV，右半邊刻意偏紫藍，模擬啟動時只抓到半桌。
    cv2.rectangle(hsv_frame, (100, 100), (610, 600), (110, 140, 190), -1)
    cv2.rectangle(hsv_frame, (610, 100), (1100, 600), (140, 140, 190), -1)
    frame = cv2.cvtColor(hsv_frame, cv2.COLOR_HSV2BGR)
    for point in [(100, 100), (610, 100), (1100, 100), (100, 600), (610, 600), (1100, 600)]:
        cv2.circle(frame, point, 32, (0, 0, 0), -1)

    success, roi = tracker.detect_table(frame)

    assert success is True
    assert roi is not None
    assert tracker.table_roi_status == "hsv_pocket_expand"
    assert roi[2] > 760

def test_manual_roi_saved_in_monitor_space_scales_to_camera_frame():
    """舊版 1280x720 手動 ROI 載入 1920x1080 相機時，應自動縮放。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi_points = [[64, 24], [1139, 30], [1141, 543], [58, 540]]
    tracker.table_roi_raw = [58, 24, 1083, 519]
    tracker.table_roi = [58, 24, 1083, 519]
    tracker.table_roi_adjustment = {"left": 0, "top": 0, "right": 0, "bottom": 0}
    tracker.table_roi_status = "manual_polygon"
    tracker.table_rects = [tracker.table_roi]
    tracker.holes = []
    tracker.hole_bboxes = []

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    tracker._sync_manual_table_roi_to_frame(frame)

    assert tracker.table_roi_status == "manual_polygon_scaled"
    assert tracker.table_roi == [87, 36, 1625, 778]
    assert tracker.table_roi_points == [[96, 36], [1708, 45], [1712, 814], [87, 810]]

def test_pocket_centers_are_clamped_inside_table_roi():
    """洞口中心需留在 ROI 內，但不可被硬推離實際偵測位置。"""
    tracker = PoolTracker.__new__(PoolTracker)
    table_roi = [100, 100, 1000, 500]
    holes = [[96, 96], [1104, 604], [600, 98], [600, 602]]

    clamped = tracker._clamp_holes_to_table_roi(holes, table_roi)

    assert clamped == [
        [100, 100],
        [1100, 600],
        [600, 100],
        [600, 600],
    ]

def test_manual_roi_holes_refine_to_dark_pocket_centers():
    """手動 ROI 也要用畫面黑洞微調，避免角袋只停在固定幾何 offset。"""
    tracker = PoolTracker.__new__(PoolTracker)
    table_roi = [50, 30, 980, 460]
    frame = np.full((540, 1100, 3), (210, 160, 80), dtype=np.uint8)
    cv2.rectangle(frame, (50, 30), (1030, 490), (210, 170, 80), -1)
    cv2.circle(frame, (88, 52), 20, (0, 0, 0), -1)
    cv2.circle(frame, (1000, 52), 20, (0, 0, 0), -1)
    cv2.circle(frame, (540, 48), 20, (0, 0, 0), -1)
    cv2.circle(frame, (88, 460), 20, (0, 0, 0), -1)
    cv2.circle(frame, (1000, 460), 20, (0, 0, 0), -1)
    cv2.circle(frame, (540, 462), 20, (0, 0, 0), -1)

    holes = tracker._estimate_holes_for_table_roi(table_roi, frame)

    assert len(holes) == 6
    assert abs(holes[0][0] - 88) <= 3
    assert abs(holes[0][1] - 52) <= 3
    assert abs(holes[2][0] - 1000) <= 3
    assert abs(holes[2][1] - 52) <= 3


def test_duplicate_ball_number_resolution_clears_weaker_candidate(monkeypatch):
    """同一球號重複時，保留較可靠候選，較弱候選不再帶錯號進 planner。"""
    monkeypatch.setattr(config, "BALL_NUMBER_DUPLICATE_RESOLUTION_ENABLED", True, raising=False)
    tracker = PoolTracker.__new__(PoolTracker)
    strong_debug = {
        "template_margin": 0.18,
        "label_signal_strength": 0.9,
        "style_signal_strength": 1.0,
    }
    weak_debug = {
        "template_margin": 0.02,
        "label_signal_strength": 0.45,
        "style_signal_strength": 0.0,
    }
    color_balls = [
        [100, 100, 20, 20, 10, 0.92, {"label": "Blue", "style": "Solid", "color_ratio": 0.95, "debug": strong_debug}, 2],
        [300, 100, 20, 20, 10, 0.84, {"label": "Blue", "style": "Solid", "color_ratio": 0.55, "white_ratio": 0.25, "debug": weak_debug}, 2],
    ]

    tracker._resolve_duplicate_ball_numbers(color_balls)

    assert color_balls[0][7] == 2
    assert color_balls[1][7] is None
    assert color_balls[1][6]["debug"]["duplicate_number_resolution"]["applied"] is True


def test_yolo_inference(tracker):
    """測試 YOLO 推論"""
    # 創建測試影像
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(test_frame, (100, 100), (1100, 600), (50, 180, 50), -1)

    try:
        # 先檢測球桌
        tracker.detect_table(test_frame)

        # 執行完整處理
        processed_frame, data_packet = tracker.process_frame(test_frame)

        assert processed_frame is not None
        assert isinstance(data_packet, dict)
        assert "status" in data_packet
    except Exception as e:
        pytest.fail(f"YOLO 推論錯誤: {e}")


def test_second_pass_runs_when_ball_recall_low_even_if_cue_found(monkeypatch):
    """一般完整辨識若球數不足，即使 first-pass 已看到球桿也要補跑高解析 second-pass。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.temporal_frame_id = 0
    tracker.conf_thr = 0.08
    tracker.iou_thr = 0.50
    tracker.infer_device = "cpu"
    tracker.use_half = False
    tracker.cue_laser_only = False

    monkeypatch.setattr(config, "SECOND_PASS_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_MIN_OBJECTS", 4, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_MIN_BALLS", 9, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_SKIP_WHEN_CUE_FOUND", True, raising=False)
    monkeypatch.setattr(config, "CUE_LASER_ONLY_DISABLE_SECOND_PASS", True, raising=False)

    class FakeBox:
        def __init__(self, cls_id):
            self.xyxy = [np.array([10, 10, 30, 30], dtype=np.float32)]
            self.conf = [0.90]
            self.cls = [cls_id]

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        names = {0: "cue", 1: "color-ball", 2: "white-ball"}

        def __init__(self):
            self.calls = []

        def predict(self, *args, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return [FakeResult([FakeBox(0), FakeBox(1), FakeBox(1), FakeBox(2)])]
            return [FakeResult([FakeBox(0)] + [FakeBox(1) for _ in range(8)] + [FakeBox(2)])]

    tracker.model = FakeModel()
    monkeypatch.setattr(tracker, "_analyze_balls", lambda results, roi_img, offset: {"status": "analyzing"})
    monkeypatch.setattr(tracker, "_draw_annotations", lambda frame, data: None)

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    _, data = tracker.process_frame(frame)

    assert data["status"] == "analyzing"
    assert len(tracker.model.calls) == 2
    assert tracker.model.calls[1]["imgsz"] == config.SECOND_PASS_IMG_SIZE


def test_second_pass_stays_disabled_in_cue_laser_only(monkeypatch):
    """球型練習 cue-laser-only 模式維持單次推論，避免補強球數拖慢雷射線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.temporal_frame_id = 0
    tracker.conf_thr = 0.08
    tracker.iou_thr = 0.50
    tracker.infer_device = "cpu"
    tracker.use_half = False
    tracker.cue_laser_only = True

    monkeypatch.setattr(config, "SECOND_PASS_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_MIN_BALLS", 9, raising=False)
    monkeypatch.setattr(config, "CUE_LASER_ONLY_DISABLE_SECOND_PASS", True, raising=False)

    class FakeResult:
        boxes = []

    class FakeModel:
        names = {}

        def __init__(self):
            self.calls = []

        def predict(self, *args, **kwargs):
            self.calls.append(kwargs)
            return [FakeResult()]

    tracker.model = FakeModel()
    monkeypatch.setattr(tracker, "_analyze_balls", lambda results, roi_img, offset: {"status": "analyzing"})
    monkeypatch.setattr(tracker, "_draw_annotations", lambda frame, data: None)

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    tracker.process_frame(frame)

    assert len(tracker.model.calls) == 1


def test_second_pass_cooldown_prevents_every_frame_rerun(monkeypatch):
    """低檢出狀態不應每幀補跑 second-pass，避免偵測結果長時間落後畫面。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.temporal_frame_id = 0
    tracker.conf_thr = 0.08
    tracker.iou_thr = 0.50
    tracker.infer_device = "cpu"
    tracker.use_half = False
    tracker.cue_laser_only = False

    monkeypatch.setattr(config, "SECOND_PASS_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_MIN_OBJECTS", 4, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_MIN_BALLS", 0, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_SKIP_WHEN_CUE_FOUND", False, raising=False)
    monkeypatch.setattr(config, "CUE_LASER_ONLY_DISABLE_SECOND_PASS", True, raising=False)
    monkeypatch.setattr(config, "SECOND_PASS_COOLDOWN_FRAMES", 4, raising=False)

    class FakeBox:
        def __init__(self, cls_id):
            self.xyxy = [np.array([10, 10, 30, 30], dtype=np.float32)]
            self.conf = [0.90]
            self.cls = [cls_id]

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        names = {1: "color-ball"}

        def __init__(self):
            self.calls = []

        def predict(self, *args, **kwargs):
            self.calls.append(kwargs)
            return [FakeResult([FakeBox(1), FakeBox(1)])]

    tracker.model = FakeModel()
    monkeypatch.setattr(tracker, "_analyze_balls", lambda results, roi_img, offset: {"status": "analyzing"})
    monkeypatch.setattr(tracker, "_draw_annotations", lambda frame, data: None)

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    tracker.process_frame(frame)
    tracker.process_frame(frame)

    assert len(tracker.model.calls) == 3
    assert tracker.model.calls[1]["imgsz"] == config.SECOND_PASS_IMG_SIZE
    assert tracker.model.calls[2]["imgsz"] == config.IMG_SIZE

def test_camera_read():
    """測試攝影機讀取"""
    print("\n" + "=" * 60)
    print("測試 4: 攝影機讀取")
    print("=" * 60)

    try:
        camera_device = getattr(config, "CAMERA_DEVICE", 0)
        cap = cv2.VideoCapture(camera_device)
        if not cap.isOpened():
            pytest.skip(f"無法開啟攝影機: {camera_device}")

        ret, frame = cap.read()
        if not ret or frame is None:
            cap.release()
            pytest.skip("無法讀取攝影機影像")

        cap.release()
        assert frame is not None
    except Exception as e:
        pytest.fail(f"攝影機錯誤: {e}")

def test_hsv_color_detection(tracker):
    """測試 HSV 顏色檢測"""
    print("\n" + "=" * 60)
    print("測試 5: HSV 顏色檢測")
    print("=" * 60)

    # 創建黃色球影像
    yellow_ball = np.zeros((50, 50, 3), dtype=np.uint8)
    cv2.circle(yellow_ball, (25, 25), 20, (0, 220, 255), -1)  # 黃色 BGR

    try:
        color_info = tracker._detect_ball_color_hsv(yellow_ball, [0, 0, 50, 50])
        ball_num = tracker._classify_ball_number(color_info)
        assert color_info.get("label") in {"Yellow", "Unknown"}
        assert ball_num in {1, 9, None}
    except Exception as e:
        pytest.fail(f"HSV 檢測錯誤: {e}")


def test_projected_artifact_filter_uses_last_route(tracker):
    """投影路線/落點不應被當成球或球桿。"""
    tracker.route_planner_enabled = True
    tracker.route_planner.last_plan = {
        "best_route": {
            "cue_landing_point": [500, 300],
            "metadata": {"ghost_ball": [420, 260]},
            "route_segments": [
                {"type": "cue_to_contact", "points": [[100, 100], [420, 260]]},
                {"type": "object_after_contact", "points": [[430, 270], [520, 310]]},
                {"type": "cue_after_contact", "points": [[420, 260], [500, 300]]},
            ],
        }
    }

    artifacts = tracker._current_projected_artifacts()

    assert tracker._is_projected_ball_artifact(488, 288, 24, 24, artifacts) is True
    assert tracker._is_projected_ball_artifact(418, 258, 24, 24, artifacts) is False
    assert tracker._is_projected_ball_artifact(700, 500, 24, 24, artifacts) is False
    assert tracker._is_projected_cue_artifact(180, 166, 140, 18, artifacts) is True
    assert tracker._is_projected_cue_artifact(250, 400, 140, 18, artifacts) is False


def test_cue_axis_cache_holds_short_missing_frames(monkeypatch):
    """球桿短暫漏檢時應沿用可信軸線，避免雷射線閃爍。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 10

    monkeypatch.setattr(config, "CUE_AXIS_CACHE_MAX_MISSING_FRAMES", 2, raising=False)
    tracker._smooth_cue_axis([100.0, 100.0, 200.0, 100.0], (1.0, 0.0))

    tracker.temporal_frame_id = 11
    tracker.cue_axis_missing_frames = 1
    assert tracker._cached_cue_axis_result() == [[100, 100], [200, 100], [1.0, 0.0]]

    tracker.temporal_frame_id = 13
    tracker.cue_axis_missing_frames = 3
    assert tracker._cached_cue_axis_result() is None


def test_cue_axis_normal_deadband_suppresses_small_vertical_jitter(monkeypatch):
    """方向穩定時，垂直球桿的小幅中心抖動不應讓雷射線上下微飄。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    monkeypatch.setattr(config, "CUE_AXIS_NORMAL_DEADBAND_PX", 3.0, raising=False)
    tracker._smooth_cue_axis([100.0, 100.0, 300.0, 100.0], (1.0, 0.0))

    tracker.temporal_frame_id = 2
    smoothed = tracker._smooth_cue_axis([100.0, 102.0, 300.0, 102.0], (1.0, 0.0))

    center_y = (smoothed[1] + smoothed[3]) / 2.0
    assert abs(center_y - 100.0) <= 0.25


def test_cue_axis_fast_converges_on_real_center_shift(monkeypatch):
    """球桿中心明顯移動時，雷射線應快速收斂到新軸線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    monkeypatch.setattr(config, "CUE_AXIS_NORMAL_DEADBAND_PX", 3.0, raising=False)
    monkeypatch.setattr(config, "CUE_AXIS_FAST_CONVERGE_SHIFT_PX", 14.0, raising=False)
    monkeypatch.setattr(config, "CUE_AXIS_LASER_ONLY_SMOOTH_ALPHA", 0.62, raising=False)
    monkeypatch.setattr(config, "CUE_AXIS_LASER_ONLY_FAST_CONVERGE_ALPHA", 0.26, raising=False)
    tracker._smooth_cue_axis([100.0, 100.0, 300.0, 100.0], (1.0, 0.0))

    tracker.temporal_frame_id = 2
    smoothed = tracker._smooth_cue_axis([100.0, 140.0, 300.0, 140.0], (1.0, 0.0))

    center_y = (smoothed[1] + smoothed[3]) / 2.0
    assert center_y >= 124.0


def test_cue_axis_prefers_wood_mask_over_projected_edges():
    """長球桿 bbox 內有投影線時，軸線應跟隨木色球桿而非桌邊/綠線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)  # 藍色桌布
    cv2.line(frame, (0, 70), (680, 70), (0, 255, 0), 3, cv2.LINE_AA)
    cv2.line(frame, (20, 92), (630, 248), (70, 175, 225), 8, cv2.LINE_AA)
    cv2.line(frame, (20, 92), (630, 248), (105, 215, 250), 2, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_line(frame, [0, 45, 650, 230], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert 0.16 <= slope <= 0.36


def test_cue_axis_rejects_large_overlay_only_bbox():
    """cue-laser-only 的長 bbox 若只有投影/桌邊邊緣，不應用 Canny 硬生雷射線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (0, 70), (680, 70), (0, 255, 0), 3, cv2.LINE_AA)
    cv2.rectangle(frame, (0, 45), (650, 275), (0, 255, 0), 2)

    cue_axis = tracker._estimate_cue_axis_line(frame, [0, 45, 650, 230], (0, 0), apply_smoothing=False)

    assert cue_axis is None


def test_cue_axis_uses_narrow_cue_band_when_hand_color_is_similar():
    """手部顏色接近球桿時，軸線應鎖定窄球桿帶而非手掌寬面中心。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (40, 104), (640, 224), (70, 175, 225), 8, cv2.LINE_AA)
    cv2.line(frame, (40, 104), (640, 224), (105, 215, 250), 2, cv2.LINE_AA)
    cv2.ellipse(frame, (230, 165), (82, 50), 11, 0, 360, (80, 170, 220), -1, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_line(frame, [0, 55, 680, 210], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    expected_y_at_x = 96.0 + (float(ax) * 0.20)
    line_mid_offset = abs(float(ay) - expected_y_at_x)
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert 0.14 <= slope <= 0.28
    assert line_mid_offset <= 14.0


def test_cue_axis_keeps_direction_when_hand_touches_cue():
    """手掌貼到球桿形成大色塊時，方向仍應由最長直線球桿決定。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (38, 112), (660, 205), (70, 175, 225), 9, cv2.LINE_AA)
    cv2.line(frame, (38, 112), (660, 205), (105, 215, 250), 2, cv2.LINE_AA)
    cv2.ellipse(frame, (285, 158), (118, 54), 8, 0, 360, (78, 168, 218), -1, cv2.LINE_AA)
    cv2.circle(frame, (210, 145), 34, (70, 165, 218), -1, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_line(frame, [0, 65, 690, 170], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert 0.10 <= slope <= 0.20


def test_cue_axis_uses_visible_rear_segment_when_front_hand_occludes_cue():
    """手遮住球桿前半段時，應用後半段可見桿身延伸，不讓手掌中心推偏。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (42, 118), (665, 212), (70, 175, 225), 9, cv2.LINE_AA)
    cv2.line(frame, (42, 118), (665, 212), (105, 215, 250), 2, cv2.LINE_AA)
    cv2.ellipse(frame, (445, 184), (105, 62), 8, 0, 360, (62, 155, 220), -1, cv2.LINE_AA)
    cv2.circle(frame, (510, 194), 38, (58, 150, 218), -1, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_line(frame, [0, 70, 690, 175], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    expected_y_at_x = 112.0 + (float(ax) * 0.151)
    line_offset = abs(float(ay) - expected_y_at_x)
    assert 0.10 <= slope <= 0.20
    assert line_offset <= 18.0


def test_cue_axis_selects_diagonal_roi_with_more_cue_pixels():
    """大正方形 bbox 內應先選球桿色像素較多的對角線 ROI，再估算軸線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 380, 380]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((380, 380, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (45, 58), (335, 325), (70, 175, 225), 8, cv2.LINE_AA)
    cv2.line(frame, (45, 58), (335, 325), (105, 215, 250), 2, cv2.LINE_AA)
    cv2.ellipse(frame, (225, 170), (55, 42), -42, 0, 360, (82, 168, 218), -1, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_line(frame, [25, 25, 320, 320], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert 0.72 <= slope <= 1.05


def test_analyze_keeps_large_diagonal_cue_bbox_over_45_degrees(monkeypatch):
    """超過 45 度時 axis-aligned cue bbox 會變大，不應先用面積規則誤殺。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.model = type("Model", (), {"names": {0: "cue"}})()
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1
    tracker.route_planner_enabled = False
    tracker.aim_assist_enabled = False
    tracker.holes = []
    monkeypatch.setattr(tracker, "_current_projected_artifacts", lambda: {"segments": [], "points": [], "protected_points": []})

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (430, 42), (245, 330), (70, 175, 225), 8, cv2.LINE_AA)
    cv2.line(frame, (430, 42), (245, 330), (105, 215, 250), 2, cv2.LINE_AA)

    class FakeBox:
        xyxy = [np.array([220, 20, 455, 350], dtype=np.float32)]
        conf = [0.90]
        cls = [0]

    class FakeResult:
        boxes = [FakeBox()]

    data = tracker._analyze_balls([FakeResult()], frame, (0, 0))

    assert data["cue_axis"] is not None
    ax, ay = data["cue_axis"][0]
    bx, by = data["cue_axis"][1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert slope > 1.0


def test_analyze_uses_segmentation_mask_for_cue_axis(monkeypatch):
    """segmentation 模型有 cue mask 時，應優先用 mask 像素估球桿軸線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.model = type("Model", (), {"names": {0: "cue"}})()
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1
    tracker.route_planner_enabled = False
    tracker.aim_assist_enabled = False
    tracker.holes = []
    monkeypatch.setattr(tracker, "_current_projected_artifacts", lambda: {"segments": [], "points": [], "protected_points": []})

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    mask = np.zeros((360, 700), dtype=np.float32)
    cv2.line(mask, (80, 92), (630, 250), 1.0, 9, cv2.LINE_AA)

    class FakeBox:
        xyxy = [np.array([40, 40, 660, 310], dtype=np.float32)]
        conf = [0.90]
        cls = [0]

    class FakeMasks:
        data = [mask]

    class FakeResult:
        boxes = [FakeBox()]
        masks = FakeMasks()

    data = tracker._analyze_balls([FakeResult()], frame, (0, 0))

    assert data["cue_axis"] is not None
    ax, ay = data["cue_axis"][0]
    bx, by = data["cue_axis"][1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert 0.20 <= slope <= 0.36


def test_analyze_recenters_edge_biased_cue_mask_with_image_axis(monkeypatch):
    """cue mask 只吃到桿身上緣時，最終雷射線仍應回到影像中的球桿中心。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.model = type("Model", (), {"names": {0: "cue"}})()
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1
    tracker.route_planner_enabled = False
    tracker.aim_assist_enabled = False
    tracker.holes = []
    monkeypatch.setattr(tracker, "_current_projected_artifacts", lambda: {"segments": [], "points": [], "protected_points": []})

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (60, 118), (640, 205), (70, 175, 225), 16, cv2.LINE_AA)
    cv2.line(frame, (60, 118), (640, 205), (105, 215, 250), 3, cv2.LINE_AA)

    mask = np.zeros((360, 700), dtype=np.float32)
    cv2.line(mask, (60, 108), (640, 195), 1.0, 4, cv2.LINE_AA)

    class FakeBox:
        xyxy = [np.array([40, 85, 660, 235], dtype=np.float32)]
        conf = [0.91]
        cls = [0]

    class FakeMasks:
        data = [mask]

    class FakeResult:
        boxes = [FakeBox()]
        masks = FakeMasks()

    data = tracker._analyze_balls([FakeResult()], frame, (0, 0))

    assert data["cue_axis"] is not None
    ax, ay = data["cue_axis"][0]
    bx, by = data["cue_axis"][1]
    left_x = min(float(ax), float(bx))
    left_y = float(ay) if float(ax) <= float(bx) else float(by)
    expected_y = 109.0 + left_x * ((205.0 - 118.0) / (640.0 - 60.0))
    assert abs(left_y - expected_y) <= 7.0


def test_cue_axis_from_mask_uses_ransac_for_asymmetric_mask():
    """cue mask 局部變粗或外凸時，RANSAC 應鎖定最細長主軸。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    mask = np.zeros((260, 700), dtype=np.uint8)
    cv2.line(mask, (60, 105), (640, 205), 255, 8, cv2.LINE_AA)
    cv2.ellipse(mask, (345, 183), (78, 30), 10, 0, 360, 255, -1, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_from_mask(mask, [40, 70, 620, 170], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    ref_x = min(float(ax), float(bx))
    ref_y = float(ay) if float(ax) <= float(bx) else float(by)
    expected_y_at_x = 94.7 + (ref_x * 0.172)
    line_offset = abs(ref_y - expected_y_at_x)
    assert 0.14 <= slope <= 0.22
    assert line_offset <= 12.0


def test_cue_axis_from_mask_recenters_ransac_edge_line():
    """RANSAC 若抓到桿身上/下緣，最終仍應用 mask 橫截面中點回到中心線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    mask = np.zeros((220, 620), dtype=np.uint8)
    cv2.line(mask, (40, 102), (580, 142), 255, 16, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_from_mask(mask, [30, 80, 570, 90], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    left_x = min(float(ax), float(bx))
    left_y = float(ay) if float(ax) <= float(bx) else float(by)
    expected_y = 99.0 + left_x * ((142.0 - 102.0) / (580.0 - 40.0))
    assert abs(left_y - expected_y) <= 5.0


def test_analyze_uses_segmentation_mask_for_ball_geometry(monkeypatch):
    """segmentation 模型有球 mask 時，白球位置與半徑應優先由 mask 決定。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.model = type("Model", (), {"names": {0: "white-ball"}})()
    tracker.table_roi = [0, 0, 400, 260]
    tracker.cue_laser_only = False
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1
    tracker.route_planner_enabled = False
    tracker.aim_assist_enabled = False
    tracker.holes = []
    monkeypatch.setattr(tracker, "_current_projected_artifacts", lambda: {"segments": [], "points": [], "protected_points": []})

    frame = np.zeros((260, 400, 3), dtype=np.uint8)
    mask = np.zeros((260, 400), dtype=np.float32)
    cv2.circle(mask, (120, 130), 16, 1.0, -1, cv2.LINE_AA)

    class FakeBox:
        xyxy = [np.array([70, 80, 180, 190], dtype=np.float32)]
        conf = [0.92]
        cls = [0]

    class FakeMasks:
        data = [mask]

    class FakeResult:
        boxes = [FakeBox()]
        masks = FakeMasks()

    data = tracker._analyze_balls([FakeResult()], frame, (0, 0))

    assert data["white_ball"] is not None
    x, y, w, h = data["white_ball"]
    assert 103 <= x <= 106
    assert 113 <= y <= 116
    assert 31 <= w <= 35
    assert 31 <= h <= 35


def test_analyze_prefers_segmentation_polygon_for_ball_geometry(monkeypatch):
    """masks.xy 與 masks.data 不一致時，球框應使用 polygon 座標貼回球上。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.model = type("Model", (), {"names": {0: "white-ball"}})()
    tracker.table_roi = [0, 0, 400, 260]
    tracker.cue_laser_only = False
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1
    tracker.route_planner_enabled = False
    tracker.aim_assist_enabled = False
    tracker.holes = []
    monkeypatch.setattr(tracker, "_current_projected_artifacts", lambda: {"segments": [], "points": [], "protected_points": []})

    frame = np.zeros((260, 400, 3), dtype=np.uint8)
    stale_data_mask = np.zeros((260, 400), dtype=np.float32)
    cv2.circle(stale_data_mask, (245, 70), 16, 1.0, -1, cv2.LINE_AA)
    polygon = cv2.ellipse2Poly((122, 134), (17, 17), 0, 0, 360, 12).astype(np.float32)

    class FakeBox:
        xyxy = [np.array([70, 80, 180, 190], dtype=np.float32)]
        conf = [0.92]
        cls = [0]

    class FakeMasks:
        data = [stale_data_mask]
        xy = [polygon]

    class FakeResult:
        boxes = [FakeBox()]
        masks = FakeMasks()

    data = tracker._analyze_balls([FakeResult()], frame, (0, 0))

    assert data["white_ball"] is not None
    x, y, w, h = data["white_ball"]
    assert 119 <= x + (w / 2.0) <= 125
    assert 131 <= y + (h / 2.0) <= 137
    assert 32 <= w <= 38
    assert 32 <= h <= 38


def test_analyze_uses_image_fallback_when_yolo_misses_white_ball(monkeypatch):
    """YOLO 漏掉白球時，影像 fallback 應補回 white_ball 讓 planner 可取得母球。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.model = type("Model", (), {"names": {0: "color-ball"}})()
    tracker.table_roi = [0, 0, 420, 260]
    tracker.cue_laser_only = False
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1
    tracker.temporal_color_cache = []
    tracker.temporal_ball_geometry_cache = []
    tracker.route_planner_enabled = False
    tracker.aim_assist_enabled = False
    tracker.holes = []
    tracker.hsv_lower = np.array([90, 50, 50], dtype=np.uint8)
    tracker.hsv_upper = np.array([130, 255, 255], dtype=np.uint8)
    tracker.COLOR_TO_NUM = {"Yellow": (1, 9)}
    monkeypatch.setattr(tracker, "_current_projected_artifacts", lambda: {"segments": [], "points": [], "protected_points": []})
    monkeypatch.setattr(tracker, "_detect_ball_color_hsv", lambda *_args, **_kwargs: {
        "label": "Yellow",
        "style": "Solid",
        "white_ratio": 0.02,
        "black_ratio": 0.02,
        "dark_ratio": 0.02,
        "color_ratio": 0.90,
    })
    monkeypatch.setattr(tracker, "_classify_ball_number", lambda _color_info: 1)

    frame = np.zeros((260, 420, 3), dtype=np.uint8)
    frame[:] = (190, 145, 80)
    cv2.circle(frame, (150, 130), 17, (235, 235, 230), -1, cv2.LINE_AA)
    cv2.circle(frame, (290, 130), 16, (20, 210, 245), -1, cv2.LINE_AA)

    class FakeBox:
        xyxy = [np.array([274, 114, 306, 146], dtype=np.float32)]
        conf = [0.91]
        cls = [0]

    class FakeResult:
        boxes = [FakeBox()]

    data = tracker._analyze_balls([FakeResult()], frame, (0, 0))

    assert data["white_ball"] is not None
    x, y, w, h = data["white_ball"]
    assert 130 <= x <= 155
    assert 112 <= y <= 138
    assert 24 <= w <= 42
    assert 24 <= h <= 42
    assert data["balls"][0]["number"] == 1


def test_analyze_retries_white_fallback_after_overlap_suppression(monkeypatch):
    """白球候選若被 overlap suppress 清空，輸出前仍需再嘗試影像 fallback。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.model = type("Model", (), {"names": {0: "white-ball", 1: "color-ball"}})()
    tracker.table_roi = [0, 0, 420, 260]
    tracker.cue_laser_only = False
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1
    tracker.temporal_color_cache = []
    tracker.temporal_ball_geometry_cache = []
    tracker.route_planner_enabled = False
    tracker.aim_assist_enabled = False
    tracker.holes = []
    tracker.hsv_lower = np.array([90, 50, 50], dtype=np.uint8)
    tracker.hsv_upper = np.array([130, 255, 255], dtype=np.uint8)
    tracker.COLOR_TO_NUM = {"Yellow": (1, 9)}
    monkeypatch.setattr(tracker, "_current_projected_artifacts", lambda: {"segments": [], "points": [], "protected_points": []})
    monkeypatch.setattr(tracker, "_detect_ball_color_hsv", lambda *_args, **_kwargs: {
        "label": "Yellow",
        "style": "Solid",
        "white_ratio": 0.02,
        "black_ratio": 0.02,
        "dark_ratio": 0.02,
        "color_ratio": 0.90,
    })
    monkeypatch.setattr(tracker, "_classify_ball_number", lambda _color_info: 1)
    monkeypatch.setattr(tracker, "_suppress_white_candidates_overlapping_color_balls", lambda _white, _color: [])
    monkeypatch.setattr(tracker, "_is_projected_ball_artifact", lambda x, *_args: 130 <= int(x) <= 155)

    frame = np.zeros((260, 420, 3), dtype=np.uint8)
    frame[:] = (190, 145, 80)
    cv2.circle(frame, (150, 130), 17, (235, 235, 230), -1, cv2.LINE_AA)
    cv2.circle(frame, (290, 130), 16, (20, 210, 245), -1, cv2.LINE_AA)

    class FakeWhiteBox:
        xyxy = [np.array([134, 114, 166, 146], dtype=np.float32)]
        conf = [0.30]
        cls = [0]

    class FakeColorBox:
        xyxy = [np.array([274, 114, 306, 146], dtype=np.float32)]
        conf = [0.91]
        cls = [1]

    class FakeResult:
        boxes = [FakeWhiteBox(), FakeColorBox()]

    data = tracker._analyze_balls([FakeResult()], frame, (0, 0))

    assert data["white_ball"] is not None
    x, y, w, h = data["white_ball"]
    assert 130 <= x <= 155
    assert 112 <= y <= 138
    assert 24 <= w <= 42
    assert 24 <= h <= 42


def test_ball_mask_geometry_uses_area_radius_when_mask_has_tail():
    """球 mask 有細長外伸雜點時，半徑不應被最小外接圓撐大。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 400, 260]

    mask = np.zeros((260, 400), dtype=np.uint8)
    cv2.circle(mask, (120, 130), 16, 255, -1, cv2.LINE_AA)
    cv2.line(mask, (136, 130), (178, 130), 255, 2, cv2.LINE_AA)

    geom = tracker._refine_ball_geometry_from_mask(mask, [95, 105, 90, 50])

    assert geom is not None
    assert 30 <= geom["w"] <= 40
    assert 30 <= geom["h"] <= 40
    assert geom["radius"] <= 20
    assert geom["debug"]["min_enclosing_radius"] > geom["radius"]


def test_ball_mask_geometry_uses_bbox_to_select_near_component():
    """同一 mask crop 內有相鄰球時，應用 bbox 中心挑附近的 segmentation 元件。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 420, 260]

    mask = np.zeros((260, 420), dtype=np.uint8)
    cv2.circle(mask, (122, 130), 16, 255, -1, cv2.LINE_AA)
    cv2.circle(mask, (166, 130), 20, 255, -1, cv2.LINE_AA)

    geom = tracker._refine_ball_geometry_from_mask(mask, [106, 114, 32, 32])

    assert geom is not None
    cx = geom["x"] + (geom["w"] / 2.0)
    cy = geom["y"] + (geom["h"] / 2.0)
    assert 119 <= cx <= 125
    assert 127 <= cy <= 133
    assert geom["radius"] <= 18
    assert geom["debug"]["contour_center_distance"] <= 4.0


def test_ball_geometry_temporal_smoothing_stabilizes_color_ball(monkeypatch):
    """同一顆子球跨幀中心/半徑小幅跳動時，輸出應被時序平滑穩住。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.temporal_frame_id = 1
    tracker.temporal_ball_geometry_cache = []

    monkeypatch.setattr(config, "BALL_GEOMETRY_TEMPORAL_SMOOTH_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "BALL_GEOMETRY_TEMPORAL_MATCH_DIST", 30.0, raising=False)
    monkeypatch.setattr(config, "BALL_GEOMETRY_TEMPORAL_ALPHA", 0.70, raising=False)
    monkeypatch.setattr(config, "BALL_GEOMETRY_TEMPORAL_MAX_AGE", 8, raising=False)
    monkeypatch.setattr(config, "COLOR_DEBUG_ENABLED", True, raising=False)

    first = [[100, 100, 32, 32, 16, 0.91, {"label": "Yellow", "style": "Solid"}, 1]]
    _, smoothed_first = tracker._smooth_ball_geometry_temporal([], first)
    assert smoothed_first[0][:5] == [100, 100, 32, 32, 16]

    tracker.temporal_frame_id = 2
    second = [[101, 98, 42, 42, 21, 0.90, {"label": "Yellow", "style": "Solid"}, 1]]
    _, smoothed_second = tracker._smooth_ball_geometry_temporal([], second)

    ball = smoothed_second[0]
    assert ball[4] < 21
    assert ball[2] == ball[3] == ball[4] * 2
    assert 16 <= ball[4] <= 19
    assert ball[6]["geometry_temporal_debug"]["matched"] is True


def test_cue_axis_ignores_white_hand_cloth_on_long_bbox():
    """白布只應視為遮擋物，不應把長球桿 bbox 的木色軸線吃掉。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (40, 104), (640, 224), (70, 175, 225), 8, cv2.LINE_AA)
    cv2.line(frame, (40, 104), (640, 224), (105, 215, 250), 2, cv2.LINE_AA)
    cv2.ellipse(frame, (230, 165), (68, 42), 11, 0, 360, (245, 245, 245), -1, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_line(frame, [0, 55, 680, 210], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert 0.14 <= slope <= 0.28


def test_cue_axis_ignores_yellow_hand_cloth_on_long_bbox():
    """黃布不應被當成球桿主體，仍要保留木色球桿雷射線。"""
    tracker = PoolTracker.__new__(PoolTracker)
    tracker.table_roi = [0, 0, 700, 360]
    tracker.cue_laser_only = True
    tracker.cue_axis_cache = None
    tracker.cue_axis_missing_frames = 0
    tracker.temporal_frame_id = 1

    frame = np.zeros((360, 700, 3), dtype=np.uint8)
    frame[:] = (190, 140, 90)
    cv2.line(frame, (40, 104), (640, 224), (70, 175, 225), 8, cv2.LINE_AA)
    cv2.line(frame, (40, 104), (640, 224), (105, 215, 250), 2, cv2.LINE_AA)
    cv2.ellipse(frame, (230, 165), (68, 42), 11, 0, 360, (0, 230, 255), -1, cv2.LINE_AA)

    cue_axis = tracker._estimate_cue_axis_line(frame, [0, 55, 680, 210], (0, 0), apply_smoothing=False)

    assert cue_axis is not None
    ax, ay = cue_axis[0]
    bx, by = cue_axis[1]
    slope = abs((by - ay) / max(1, abs(bx - ax)))
    assert 0.14 <= slope <= 0.28

if __name__ == "__main__":
    print("\n🔧 開始診斷測試...\n")

    # 測試 1: 初始化
    tracker_instance = _create_tracker()
    test_tracker_init(tracker_instance)
    if not tracker_instance:
        print("\n❌ 初始化失敗，無法繼續測試")
        exit(1)

    # 測試 2: 球桌檢測
    test_table_detection(tracker_instance)

    # 測試 3: YOLO 推論
    test_yolo_inference(tracker)

    # 測試 4: 攝影機
    test_camera_read()

    # 測試 5: HSV 顏色檢測
    test_hsv_color_detection(tracker)

    print("\n" + "=" * 60)
    print("✅ 所有測試完成")
    print("=" * 60)
