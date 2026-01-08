"""
測試球桌檢測功能
"""
import cv2
import numpy as np
from tracking_engine import PoolTracker
import config

def main():
    print("=" * 60)
    print("測試球桌檢測")
    print("=" * 60)

    # 初始化 tracker
    try:
        tracker = PoolTracker(model_path=config.MODEL_PATH)
        print(f"✅ PoolTracker 初始化成功\n")
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        return

    # 嘗試從攝影機讀取
    print("嘗試從攝影機讀取...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ 無法開啟攝影機，使用測試影像\n")
        # 創建測試影像（綠色區域）
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(frame, (100, 100), (1100, 600), (50, 180, 50), -1)
    else:
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            print("❌ 無法讀取影像，使用測試影像\n")
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.rectangle(frame, (100, 100), (1100, 600), (50, 180, 50), -1)
        else:
            print(f"✅ 成功讀取攝影機影像 {frame.shape}\n")

    # 執行球桌檢測
    print("\n" + "=" * 60)
    print("執行檢測...")
    print("=" * 60 + "\n")

    success, roi = tracker.detect_table(frame)

    print("\n" + "=" * 60)
    if success:
        print("✅ 球桌檢測成功！")
        print(f"   ROI: {tracker.table_roi}")
        print(f"   球袋數量: {len(tracker.holes)}")
        print(f"   球袋位置: {tracker.holes}")
    else:
        print("❌ 球桌檢測失敗")
    print("=" * 60)

if __name__ == "__main__":
    main()
