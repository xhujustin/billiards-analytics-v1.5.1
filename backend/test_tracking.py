"""
測試 tracking_engine.py 功能的診斷腳本
"""
import cv2
import numpy as np
from tracking_engine import PoolTracker
import config

def test_tracker_init():
    """測試 tracker 初始化"""
    print("=" * 60)
    print("測試 1: PoolTracker 初始化")
    print("=" * 60)

    try:
        tracker = PoolTracker(model_path=config.MODEL_PATH)
        print(f"✅ PoolTracker 初始化成功")
        print(f"   Model path: {config.MODEL_PATH}")
        print(f"   Conf threshold: {tracker.conf_thr}")
        print(f"   IOU threshold: {tracker.iou_thr}")
        return tracker
    except Exception as e:
        print(f"❌ PoolTracker 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_table_detection(tracker):
    """測試球桌檢測"""
    print("\n" + "=" * 60)
    print("測試 2: 球桌檢測")
    print("=" * 60)

    # 創建測試影像（綠色背景）
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # 繪製綠色區域模擬球桌
    cv2.rectangle(test_frame, (100, 100), (1100, 600), (50, 180, 50), -1)

    try:
        success, roi = tracker.detect_table(test_frame)
        if success:
            print(f"✅ 球桌檢測成功")
            print(f"   ROI: {tracker.table_roi}")
            print(f"   Holes: {len(tracker.holes)} 個球袋")
        else:
            print(f"❌ 球桌檢測失敗")
        return success
    except Exception as e:
        print(f"❌ 球桌檢測錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_yolo_inference(tracker):
    """測試 YOLO 推論"""
    print("\n" + "=" * 60)
    print("測試 3: YOLO 推論")
    print("=" * 60)

    # 創建測試影像
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(test_frame, (100, 100), (1100, 600), (50, 180, 50), -1)

    try:
        # 先檢測球桌
        tracker.detect_table(test_frame)

        # 執行完整處理
        processed_frame, data_packet = tracker.process_frame(test_frame)

        print(f"✅ process_frame 執行成功")
        print(f"   Status: {data_packet.get('status', 'unknown')}")
        print(f"   Detected balls: {len(data_packet.get('balls', []))}")
        print(f"   White ball: {data_packet.get('white_ball', 'None')}")
        print(f"   Prediction: {data_packet.get('prediction', 'None')}")

        return True
    except Exception as e:
        print(f"❌ YOLO 推論錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_read():
    """測試攝影機讀取"""
    print("\n" + "=" * 60)
    print("測試 4: 攝影機讀取")
    print("=" * 60)

    try:
        cap = cv2.VideoCapture(config.CAMERA_DEVICE)
        if not cap.isOpened():
            print(f"❌ 無法開啟攝影機: {config.CAMERA_DEVICE}")
            return False

        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"❌ 無法讀取影像")
            cap.release()
            return False

        print(f"✅ 攝影機讀取成功")
        print(f"   Device: {config.CAMERA_DEVICE}")
        print(f"   Frame shape: {frame.shape}")
        print(f"   Frame dtype: {frame.dtype}")

        cap.release()
        return True
    except Exception as e:
        print(f"❌ 攝影機錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

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
        print(f"✅ HSV 顏色檢測成功")
        print(f"   Label: {color_info.get('label', 'Unknown')}")
        print(f"   Style: {color_info.get('style', 'Unknown')}")
        print(f"   Hue: {color_info.get('hue', 'None')}")

        ball_num = tracker._classify_ball_number(color_info)
        print(f"   Ball number: {ball_num}")

        return True
    except Exception as e:
        print(f"❌ HSV 檢測錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

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
