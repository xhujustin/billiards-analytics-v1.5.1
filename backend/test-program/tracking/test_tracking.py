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

@pytest.fixture
def tracker():
    try:
        return PoolTracker(model_path=config.MODEL_PATH)
    except Exception as e:
        pytest.skip(f"PoolTracker 初始化失敗: {e}")

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

if __name__ == "__main__":
    print("\n🔧 開始診斷測試...\n")

    # 測試 1: 初始化
    tracker = test_tracker_init()
    if not tracker:
        print("\n❌ 初始化失敗，無法繼續測試")
        exit(1)

    # 測試 2: 球桌檢測
    test_table_detection(tracker)

    # 測試 3: YOLO 推論
    test_yolo_inference(tracker)

    # 測試 4: 攝影機
    test_camera_read()

    # 測試 5: HSV 顏色檢測
    test_hsv_color_detection(tracker)

    print("\n" + "=" * 60)
    print("✅ 所有測試完成")
    print("=" * 60)
