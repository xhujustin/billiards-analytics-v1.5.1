#!/usr/bin/env python3
"""性能測試 - 監控 API 回應時間和 Event Loop 延遲"""

import time
from concurrent.futures import ThreadPoolExecutor

import requests

# API 端點
HEALTH_API = "http://localhost:8001/health"
PERF_API = "http://localhost:8001/api/performance/stats"
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
        print(f"  📊 目前 FPS: {data.get('current_fps', 0):.2f}")
        print(f"  ⏱️  平均幀延遲: {data.get('avg_latency_ms', 0):.2f}ms")
        print(f"  🧩 診斷啟用: {data.get('diagnostics_enabled', False)}")

        # 診斷
        print("\n⚠️  診斷:")
        stage_latency = data.get("stage_latency_ms") or {}
        ranked_stages = sorted(
            (
                (
                    name,
                    values.get("avg_ms", 0),
                    values.get("last_ms", 0),
                    values.get("samples", 0),
                    values.get("stale_frames", 0),
                )
                for name, values in stage_latency.items()
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        if ranked_stages:
            print("  分段耗時排行:")
            for name, avg_ms, last_ms, samples, stale_frames in ranked_stages[:10]:
                stale_text = f", stale={stale_frames}f" if stale_frames else ""
                print(
                    f"    - {name}: avg={avg_ms:.2f}ms, "
                    f"last={last_ms:.2f}ms, samples={samples}{stale_text}"
                )
        else:
            print("  尚無分段耗時資料；請確認 burn-in 串流已啟動。")

        yolo_ms = stage_latency.get("yolo_result", {}).get("avg_ms", 0)
        read_ms = stage_latency.get("camera_read", {}).get("avg_ms", 0)
        grab_ms = stage_latency.get("camera_grab", {}).get("avg_ms", 0)
        projector_ms = stage_latency.get("projector_render_update", {}).get("avg_ms", 0)
        recording_ms = stage_latency.get("recording_enqueue", {}).get("avg_ms", 0)
        sleep_ms = stage_latency.get("fps_cap_sleep", {}).get("avg_ms", 0)

        if yolo_ms > 300:
            print(f"  🔴 YOLO 耗時過長 ({yolo_ms:.0f}ms)：")
            print("     考慮: 降低解析度或減少推論頻率")
        elif yolo_ms > 0:
            print(f"  🟢 YOLO 耗時正常 ({yolo_ms:.0f}ms)")

        if read_ms + grab_ms > 20:
            print(f"  🟡 相機讀取/清緩衝偏慢 ({read_ms + grab_ms:.0f}ms)：")
            print("     可能是 USB 相機、曝光、backend 或 buffer flush 在等待")

        if projector_ms > 20:
            print(f"  🟡 投影更新偏慢 ({projector_ms:.0f}ms)：")
            print("     可考慮投影流降頻或只在有投影訂閱者時 render")

        if recording_ms > 20:
            print(f"  🟡 錄影入列偏慢 ({recording_ms:.0f}ms)：")
            print("     可檢查 frame copy 成本或錄影 queue 是否經常滿載")

        if sleep_ms > 5:
            print(f"  ℹ️  FPS 上限 sleep 約 {sleep_ms:.0f}ms：")
            print("     CPU/GPU 低但 FPS 被限制時，這是正常現象")

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
