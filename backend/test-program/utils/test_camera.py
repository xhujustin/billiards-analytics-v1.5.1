"""診斷攝像頭可用性"""

import cv2


def test_camera():
    print("=" * 60)
    print("📷 攝像頭診斷工具")
    print("=" * 60)

    # 列舉所有可用的攝像頭
    print("\n🔍 掃描攝像頭設備...\n")

    backends = {
        cv2.CAP_DSHOW: "DSHOW (Windows Direct Show)",
        cv2.CAP_MSMF: "MSMF (Windows Media Foundation)",
        cv2.CAP_ANY: "ANY (Auto-detect)",
    }

    available_devices = []

    for device_id in range(5):
        print(f"\n--- 設備 {device_id} ---")
        for backend_id, backend_name in backends.items():
            cap = None
            try:
                print(f"  嘗試 {backend_name}...", end=" ")
                cap = cv2.VideoCapture(device_id, backend_id)

                if not cap.isOpened():
                    print("✗ 無法開啟")
                    cap.release()
                    continue

                # 嘗試讀取
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("✗ 無法讀取幀")
                    cap.release()
                    continue

                # 成功
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                print(f"✅ 成功! ({width}x{height}@{fps}fps)")
                available_devices.append(
                    {"id": device_id, "backend": backend_name, "resolution": f"{width}x{height}", "fps": fps}
                )
                cap.release()
                # break

            except Exception as e:
                print(f"✗ 異常: {e}")
                try:
                    if cap is None:
                        continue
                    cap.release()
                except Exception:
                    pass

    # 總結
    print("\n" + "=" * 60)
    print("📊 掃描結果")
    print("=" * 60)
    if available_devices:
        print(f"\n✅ 找到 {len(available_devices)} 個可用攝像頭:")
        for dev in available_devices:
            print(f"  - 設備 {dev['id']}: {dev['backend']} ({dev['resolution']}@{dev['fps']}fps)")
    else:
        print("\n❌ 沒有找到可用的攝像頭!")
        print("\n可能的原因:")
        print("  1. 沒有連接攝像頭")
        print("  2. 攝像頭被其他應用程序佔用")
        print("  3. 攝像頭驅動程序未安裝或損壞")
        print("  4. 權限不足")


if __name__ == "__main__":
    test_camera()
