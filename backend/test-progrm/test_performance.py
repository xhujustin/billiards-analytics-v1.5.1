import sys
import threading
import time

import requests

# 嘗試匯入 websocket-client，若無則提示安裝
try:
    import websocket
except ImportError:
    print("❌ 缺少 websocket-client 套件")
    print("請執行: pip install websocket-client")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8001"
WS_URL = "ws://127.0.0.1:8001/ws/video"


def on_message(ws, message):
    # 接收到影像資料，不做處理，僅消耗頻寬模擬真實情況
    pass


def on_error(ws, error):
    print(f"⚠️ WebSocket Error: {error}")


def on_close(ws, close_status_code, close_msg):
    print("ℹ️ WebSocket Closed")


def on_open(ws):
    print("✅ WebSocket Connected")


def run_ws():
    # 啟動 WebSocket 連線
    ws = websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.run_forever()


def test_api_latency():
    print("\n⏱️  開始測試 API 回應延遲 (Health Check)...")
    latencies = []
    for i in range(10):
        start = time.time()
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=2)
            latency_ms = (time.time() - start) * 1000
            latencies.append(latency_ms)
            print(f"   Request {i + 1}: {latency_ms:.2f} ms | Status: {resp.status_code}")
        except requests.exceptions.Timeout:
            print(f"   Request {i + 1}: ❌ Timeout (>2000ms)")
            latencies.append(2000)
        except Exception as e:
            print(f"   Request {i + 1}: ❌ Error {e}")

        time.sleep(0.5)

    avg = sum(latencies) / len(latencies) if latencies else 0
    print(f"\n📊 平均延遲: {avg:.2f} ms")

    if avg < 100:
        print("✅ 測試通過：API 回應迅速，Event Loop 未被阻塞。")
    else:
        print("❌ 測試失敗：API 回應緩慢，Event Loop 可能被 YOLO 阻塞。")


if __name__ == "__main__":
    print("=" * 50)
    print("   Billiards Analytics - Performance Test")
    print("=" * 50)

    # 1. 檢查伺服器是否活著
    try:
        requests.get(f"{BASE_URL}/health")
    except requests.exceptions.RequestException as err:
        print(f"❌ 無法連接到後端 ({BASE_URL})")
        print(f"請先確認後端已啟動: python main.py | 詳細錯誤: {err}")
        sys.exit(1)

    # 2. 啟動 WebSocket (模擬前端接收影像)
    print("1️⃣  啟動 WebSocket 客戶端...")
    t = threading.Thread(target=run_ws)
    t.daemon = True
    t.start()
    time.sleep(2)

    # 3. 開啟 YOLO 分析 (增加 CPU 負載)
    print("2️⃣  開啟 YOLO 分析模式...")
    try:
        # 先確認狀態
        res = requests.get(f"{BASE_URL}/health").json()
        if not res.get("is_analyzing"):
            requests.post(f"{BASE_URL}/api/control/toggle")
            print("   已發送開啟指令")
        else:
            print("   分析模式已開啟")
    except Exception as e:
        print(f"   設定失敗: {e}")

    time.sleep(2)  # 等待 YOLO 模型熱身

    # 4. 測試延遲
    test_api_latency()

    print("\n測試結束。")
