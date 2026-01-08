#!/usr/bin/env python3
"""性能測試 - 監控 API 回應時間和 Event Loop 延遲"""

import time
from concurrent.futures import ThreadPoolExecutor

import requests

# API 端點
HEALTH_API = "http://localhost:8001/health"
PERF_API = "http://localhost:8001/api/performance"
YOLO_SKIP_API = "http://localhost:8001/api/control/yolo-skip"


def test_api_response_time():
    """測試 API 回應時間"""
    print("\n" + "=" * 70)
    print("🧪 API 回應時間測試")
    print("=" * 70)

    # 健康檢查 API
    print("\n📊 健康檢查 API (Health Check):")
    times = []
    for i in range(10):
        start = time.time()
        try:
            res = requests.get(HEALTH_API, timeout=5)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            status = "✅" if res.status_code == 200 else "❌"
            print(f"  {status} Request #{i + 1}: {elapsed:.2f}ms")
        except Exception as e:
            print(f"  ❌ Request #{i + 1}: Failed - {e}")

    if times:
        print("\n  統計:")
        print(f"    - 平均: {sum(times) / len(times):.2f}ms")
        print(f"    - 最小: {min(times):.2f}ms")
        print(f"    - 最大: {max(times):.2f}ms")


def test_performance_monitoring():
    """測試性能監控 API"""
    print("\n" + "=" * 70)
    print("📈 性能監控數據")
    print("=" * 70)

    try:
        res = requests.get(PERF_API, timeout=5)
        data = res.json()

        print("\n性能指標:")
        print(f"  📊 總幀數: {data.get('total_frames', 0)}")
        print(f"  ⏱️  平均 YOLO 耗時: {data.get('avg_yolo_ms', 0):.2f}ms")
        print(f"  ⏱️  平均編碼耗時: {data.get('avg_encode_ms', 0):.2f}ms")
        print(f"  ⏱️  平均 WebSocket 耗時: {data.get('avg_websocket_ms', 0):.2f}ms")
        print(f"  ⏱️  總耗時: {data.get('total_time', 0):.2f}s")

        # 診斷
        print("\n⚠️  診斷:")
        yolo_ms = data.get("avg_yolo_ms", 0)
        encode_ms = data.get("avg_encode_ms", 0)
        ws_ms = data.get("avg_websocket_ms", 0)

        if yolo_ms > 300:
            print(f"  🔴 YOLO 耗時過長 ({yolo_ms:.0f}ms)：")
            print("     考慮: 降低解析度或減少推論頻率")
        else:
            print(f"  🟢 YOLO 耗時正常 ({yolo_ms:.0f}ms)")

        if encode_ms > 50:
            print(f"  🔴 影像編碼耗時過長 ({encode_ms:.0f}ms)：")
            print("     考慮: 降低 JPEG 質量")
        else:
            print(f"  🟢 影像編碼耗時正常 ({encode_ms:.0f}ms)")

        if ws_ms > 30:
            print(f"  🟡 WebSocket 耗時較長 ({ws_ms:.0f}ms)：")
            print("     可能是: 網路延遲或前端處理緩慢")
        else:
            print(f"  🟢 WebSocket 耗時正常 ({ws_ms:.0f}ms)")

    except Exception as e:
        print(f"❌ 無法連接到性能 API: {e}")


def test_yolo_skip_setting():
    """測試動態調整 YOLO 跳幀"""
    print("\n" + "=" * 70)
    print("⚙️  YOLO 跳幀設置測試")
    print("=" * 70)

    for skip in [0, 1, 2, 5]:
        try:
            res = requests.post(YOLO_SKIP_API, json={"skip_frames": skip}, timeout=5)
            data = res.json()
            if data.get("status") == "success":
                freq = data.get("inference_frequency", "unknown")
                print(f"  ✅ skip_frames={skip} (執行頻率: {freq})")
            else:
                print(f"  ❌ skip_frames={skip} failed: {data}")
        except Exception as e:
            print(f"  ❌ skip_frames={skip} error: {e}")


def stress_test():
    """併發 API 請求壓力測試"""
    print("\n" + "=" * 70)
    print("💪 併發壓力測試 (10 個同時請求)")
    print("=" * 70)

    def make_request():
        try:
            start = time.time()
            requests.get(HEALTH_API, timeout=5)
            return (time.time() - start) * 1000
        except Exception:
            return None

    executor = ThreadPoolExecutor(max_workers=10)
    times = []
    for _ in range(10):
        t = executor.submit(make_request).result()
        if t:
            times.append(t)

    if times:
        print("\n  結果:")
        print(f"    - 平均: {sum(times) / len(times):.2f}ms")
        print(f"    - 最大: {max(times):.2f}ms")
        print(f"    - 成功率: {len(times)}/10")

        if max(times) < 100:
            print("  ✅ Event Loop 響應正常（無阻塞跡象）")
        else:
            print("  ⚠️  Event Loop 可能有輕微阻塞")


if __name__ == "__main__":
    print("\n🔬 撞球分析系統 - 性能測試套件")
    print("=" * 70)
    print("⚠️  確保後端正在運行: python backend/main.py")

    try:
        # 檢查連接
        requests.get(HEALTH_API, timeout=2)
    except Exception:
        print("❌ 無法連接到後端 (http://localhost:8001)")
        print("   請先啟動: python backend/main.py")
        exit(1)

    test_api_response_time()
    test_performance_monitoring()
    test_yolo_skip_setting()
    stress_test()

    print("\n" + "=" * 70)
    print("✅ 測試完成")
    print("=" * 70)
    print("\n💡 建議:")
    print("  1. 監控平均耗時，看是否有明顯改善")
    print("  2. 使用 /api/performance API 實時檢查性能")
    print("  3. 根據診斷調整配置參數")
    print("  4. 每次改變都要測試來驗證效果")
    print("\n" + "=" * 70)
