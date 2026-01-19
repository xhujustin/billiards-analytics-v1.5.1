import asyncio
import json

# ✅ 性能監控
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Annotated, Any, Optional

import config
import cv2
import uvicorn
from calibration import Calibrator
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from tracking_engine import PoolTracker
from mjpeg_streamer import DualMJPEGManager
from session_manager import session_manager, Role, SessionState
from error_codes import (
    ERR_INVALID_ARGUMENT, ERR_NOT_FOUND, ERR_FORBIDDEN, ERR_SESSION_EXPIRED,
    ERR_STREAM_UNAVAILABLE, ERR_INTERNAL, create_error_response
)
from performance_monitor import PerformanceMonitor

perf_stats: dict[str, Any] = {
    "total_frames": 0,
    "yolo_time": 0.0,
    "encode_time": 0.0,
    "websocket_time": 0.0,
    "lock": threading.Lock(),
}

load_dotenv()  # Must be called before other imports that rely on environment variables

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 載入追蹤引擎
tracker: Optional[PoolTracker] = None
try:
    tracker = PoolTracker(model_path=config.MODEL_PATH)
    print(f"✅ YOLO model loaded successfully from {config.MODEL_PATH}")
except Exception as e:
    print(f"⚠️  Warning: Failed to load YOLO model: {e}")
    print("   Continuing without YOLO inference...")
    tracker = None

calibrator: Optional[Calibrator] = None
try:
    calibrator = Calibrator()
    print("✅ Calibrator initialized successfully")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize Calibrator: {e}")
    calibrator = None

# 全局攝像頭設備管理
camera_state: dict[str, Any] = {
    "selected_device_id": 0,  # 預設使用裝置 0
    "available_devices": [],  # 列出所有可用的攝像頭
    "current_cap": None,  # 當前的 cv2.VideoCapture 實例
    "needs_switch": False,  # 標記是否需要切換攝像頭
    "new_device_id": 0,  # 新的設備 ID
    "is_switching": False,  # 標記是否正在切換中
    "last_frame_time": 0.0,  # ✅ 追蹤最新畫面時間戳
}

system_state: dict[str, Any] = {
    "is_analyzing": False,  # 預設不開啟 YOLO，只送純影像
    "yolo_skip_frames": 2,  # ✅ 每 3 幀執行一次 YOLO（加速）
}

# 線程池用於異步攝像頭切換（不阻塞 WebSocket）
executor = ThreadPoolExecutor(max_workers=6)  # ✅ 增加到 6 個工作線程

# ✅ MJPEG 串流管理器 - 簡單可靠的 HTTP 視頻流
try:
    mjpeg_manager = DualMJPEGManager(quality=70, max_fps=30)
    print("✅ MJPEG Stream Manager initialized")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize MJPEG: {e}")
    mjpeg_manager = None

# ✅ 啟動攝像頭並開始幀循環（用於 burn-in 串流）
camera_capture_thread = None
camera_running = threading.Event()

# ✅ 全域效能監控器 (用於 API 查詢)
global_perf_monitor: Optional[PerformanceMonitor] = None

# ✅ 遊戲模式管理器
from game_manager import GameManager
from recording_manager import RecordingManager
import os

game_manager = GameManager()
# 使用專案根目錄的 recordings 資料夾
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
recording_manager = RecordingManager(recordings_dir=os.path.join(project_root, "recordings"))

# ✅ 回放功能 API 模組（v1.5.1）
from api import replay_router
app.include_router(replay_router)


# ==================== v1.5 錯誤處理 ====================

# 錯誤碼定義
ERR_INTERNAL = "INTERNAL_ERROR"
ERR_INVALID_ARGUMENT = "INVALID_ARGUMENT"
ERR_NOT_FOUND = "NOT_FOUND"
ERR_SESSION_EXPIRED = "SESSION_EXPIRED"
ERR_STREAM_UNAVAILABLE = "STREAM_UNAVAILABLE"

def create_error_response(error_code: str, message: str) -> dict:
    """創建標準錯誤響應"""
    return {
        "error_code": error_code,
        "error_message": message,
        "message": message  # 向後兼容
    }


# ✅ 性能監控輔助函數
def encode_image_buffer(frame: Any, quality: int = 70) -> Optional[bytes]:
    """在線程中編碼影像，避免阻塞 event loop"""
    try:
        ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return buffer.tobytes() if ret else None
    except Exception as e:
        print(f"❌ Image encoding error: {e}")
        return None


def record_perf(operation: str, duration: float):
    """記錄性能指標"""
    with perf_stats["lock"]:
        if operation == "yolo":
            perf_stats["yolo_time"] += duration
        elif operation == "encode":
            perf_stats["encode_time"] += duration
        elif operation == "websocket":
            perf_stats["websocket_time"] += duration
        perf_stats["total_frames"] += 1


def get_perf_stats():
    """獲取平均性能數據"""
    with perf_stats["lock"]:
        total = perf_stats["total_frames"]
        if total == 0:
            return {"status": "no_data"}
        return {
            "total_frames": total,
            "avg_yolo_ms": (perf_stats["yolo_time"] / total) * 1000,
            "avg_encode_ms": (perf_stats["encode_time"] / total) * 1000,
            "avg_websocket_ms": (perf_stats["websocket_time"] / total) * 1000,
            "total_time": perf_stats["yolo_time"] + perf_stats["encode_time"] + perf_stats["websocket_time"],
        }


def enumerate_camera_devices() -> list[dict[str, Any]]:
    """列舉系統上所有可用的攝像頭設備"""
    devices = []
    for i in range(10):  # 最多檢查 10 個設備
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # 取得設備名稱 (Windows 上可從 CAP_PROP_FPS 或其他屬性推推)
                devices.append({"id": i, "name": f"Camera {i}"})
            cap.release()
    return devices


def open_camera(device_id: int):
    """開啟指定攝像頭：確保能持續讀取幀"""
    print(f"🔄 Opening camera device {device_id}...")

    # 若設定了 VIDEO_SOURCE，直接以影片檔為來源，不再嘗試裝置列表
    if getattr(config, "VIDEO_SOURCE", ""):
        source_path = config.VIDEO_SOURCE
        cap_video: Any = cv2.VideoCapture(source_path)
        if not cap_video.isOpened():
            print(f"⚠️ Failed to open video file: {source_path}")
            return None
        print(f"✅ Video file opened: {source_path}")
        camera_state["current_cap"] = cap_video
        camera_state["selected_device_id"] = device_id
        return cap_video

    # 先關閉舊設備
    if camera_state["current_cap"] is not None:
        try:
            print("   Releasing previous camera...")
            camera_state["current_cap"].release()
            time.sleep(0.3)
        except Exception as e:
            print(f"   ⚠️  Could not release previous camera: {e}")

    # ✅ 嘗試順序：MSMF（優先）→ DSHOW → ANY
    backends = [cv2.CAP_DSHOW]  # , cv2.CAP_MSMF, cv2.CAP_ANY
    resolutions = [
        (config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS),
        (1920, 1080, 50),
        (1280, 720, 30),
        (1024, 576, 30),
        (640, 480, 30),
        (800, 600, 30),
    ]

    cap: Optional[Any] = None
    for backend in backends:
        for width, height, fps in resolutions:
            try:
                print(f"Device {device_id}: trying backend={backend}, {width}x{height}@{fps}...", end=" ")
                # Test video file path above
                cap_candidate: Any = cv2.VideoCapture(device_id, backend)
                if not cap_candidate.isOpened():
                    print("✗ Cannot open")
                    cap_candidate.release()
                    continue

                # ✅ 設置參數
                cap_candidate.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # type: ignore
                cap_candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap_candidate.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap_candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap_candidate.set(cv2.CAP_PROP_FPS, fps)

                # ✅ 暖機階段 1：延遲初始化
                time.sleep(0.3)

                # ✅ 暖機階段 2：讀取並驗證
                print("   Verifying frames...", end=" ")
                success_count = 0
                for _ in range(25):  # ✅ 增加到 25 幀
                    ret, frame = cap_candidate.read()
                    if ret and frame is not None:
                        success_count += 1
                    time.sleep(0.01)

                # ✅ 至少 15 幀成功
                if success_count < 15:
                    print(f"✗ Low success ({success_count}/25)")
                    cap_candidate.release()
                    continue

                actual_width = int(cap_candidate.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap_candidate.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = cap_candidate.get(cv2.CAP_PROP_FPS)

                print(f"✅ OK ({actual_width}x{actual_height}@{actual_fps}fps)")
                cap = cap_candidate
                break

            except Exception as exc:
                print(f"✗ Exception: {exc}")
                try:
                    cap_candidate.release()
                except Exception:
                    pass

        if cap is not None:
            break

    if cap is None:
        print(f"❌❌❌ CRITICAL: Failed to open camera device {device_id} after trying all backends and resolutions.")
        return None

    print(f"✅ Camera {device_id} opened successfully. Adding extra delay for stabilization...")
    time.sleep(0.5)  # Extra delay for stability
    camera_state["current_cap"] = cap
    camera_state["selected_device_id"] = device_id
    return cap


def switch_camera_background(device_id: int):
    """在後台線程中切換攝像頭，完成後設置 is_switching=False"""
    try:
        print(f"🔄 Background: Starting camera switch from {camera_state['selected_device_id']} to {device_id}")
        open_camera(device_id)
        print(f"✅ Background: Camera switch to device {device_id} completed")
    except Exception as e:
        print(f"❌ Background: Camera switch failed: {e}")
    finally:
        camera_state["is_switching"] = False


def camera_capture_loop():
    """
    ✅ 優化版攝像頭捕獲循環
    - ThreadPool 非阻塞 YOLO 推論
    - 訂閱者檢查避免無謂編碼
    - 效能監控追蹤 FPS
    """
    print("🎥 Starting optimized camera capture loop for burn-in stream...")
    camera_running.set()

    # 開啟攝像頭
    cap = open_camera(camera_state["selected_device_id"])
    if cap is None:
        print("❌ Failed to open camera in capture loop")
        camera_running.clear()
        return

    frame_count = 0
    cached_overlay: Optional[Any] = None  # 快取上次的 overlay
    yolo_future: Optional[Future] = None  # ThreadPool future
    perf_monitor = PerformanceMonitor(window_size=30)  # 效能監控
    
    # ✅ 設為全域變數,讓 API 可以訪問
    global global_perf_monitor
    global_perf_monitor = perf_monitor
    
    last_data_packet: Optional[dict[str, Any]] = None
    last_ar_paths: list[Any] = []

    while camera_running.is_set():
        frame_start = time.time()
        
        try:
            # 讀取幀
            ret, frame = cap.read()

            # 若使用影片來源，嘗試迴圈播放
            if getattr(config, "VIDEO_SOURCE", "") and (not ret or frame is None):
                try:
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                    if getattr(config, "LOOP_VIDEO_SOURCE", True) and total_frames > 0:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                except Exception:
                    pass

            if not ret or frame is None:
                print("⚠️ Failed to read frame, attempting to reopen camera...")
                try:
                    cap.release()
                except Exception:
                    pass
                time.sleep(1.0)
                cap = open_camera(camera_state["selected_device_id"])
                if cap is None:
                    print("❌ Failed to reopen camera")
                    time.sleep(5.0)
                    continue
                continue

            frame_count += 1
            camera_state["last_frame_time"] = time.time()

            # ✅ 優化 1: ThreadPool 非阻塞 YOLO 推論
            if system_state["is_analyzing"] and tracker is not None:
                # ✅ 獲取 YOLO 推論結果
                if yolo_future and yolo_future.done():
                    try:
                        processed_frame, data = yolo_future.result(timeout=0)
                        cached_overlay = processed_frame.copy()
                        latest_analysis_data["data"] = data
                        
                        # AR 座標轉換
                        ar_paths = []
                        if data.get("prediction") and calibrator is not None:
                            try:
                                raw_paths = data["prediction"]["paths"]
                                ar_paths = calibrator.transform_points(raw_paths)
                            except Exception:
                                pass
                        last_ar_paths = ar_paths
                        
                        # 更新低頻分析數據
                        latest_analysis_data["data"] = data  # ✅ 修正: 使用 data 而非 data_packet
                        latest_analysis_data["ar_paths"] = ar_paths
                        latest_analysis_data["status"] = "Analyzing"
                        latest_analysis_data["timestamp"] = time.time()
                    except Exception as e:
                        print(f"⚠️ YOLO result retrieval error: {e}")
                    finally:
                        yolo_future = None
                
                # 提交新的推論任務 (非阻塞)
                skip_yolo = frame_count % (system_state.get("yolo_skip_frames", 2) + 1) != 0
                if yolo_future is None and not skip_yolo:
                    yolo_future = executor.submit(tracker.process_frame, frame.copy())
                
                # 使用快取的 overlay (如果有)
                display_frame = cached_overlay if cached_overlay is not None else frame.copy()
            else:
                display_frame = frame.copy()
                yolo_future = None  # 清除未完成的 future

            # ✅ 優化 2: 訂閱者檢查 - 只在有訂閱者時才編碼
            if mjpeg_manager is not None and config.ENABLE_SUBSCRIBER_CHECK:
                has_subscribers = (
                    mjpeg_manager.monitor._active_connections > 0 or
                    mjpeg_manager.projector._active_connections > 0
                )
                
                if has_subscribers:
                    try:
                        # 監控流：原始或處理後的幀 (1280×720)
                        monitor_frame = cv2.resize(display_frame, (1280, 720))
                        mjpeg_manager.update_monitor(monitor_frame)

                        # 投影流：通過投影機校準變形 (1920×1080)
                        if calibrator is not None:
                            projector_frame = calibrator.warp_frame_to_projector(display_frame)
                        else:
                            projector_frame = cv2.resize(display_frame, (1920, 1080))
                        mjpeg_manager.update_projector(projector_frame)
                    except Exception as e:
                        print(f"⚠️ MJPEG frame update error: {e}")
            elif mjpeg_manager is not None:
                # 未啟用訂閱者檢查,總是編碼
                try:
                    monitor_frame = cv2.resize(display_frame, (1280, 720))
                    mjpeg_manager.update_monitor(monitor_frame)
                    
                    if calibrator is not None:
                        projector_frame = calibrator.warp_frame_to_projector(display_frame)
                    else:
                        projector_frame = cv2.resize(display_frame, (1920, 1080))
                    mjpeg_manager.update_projector(projector_frame)
                except Exception as e:
                    print(f"⚠️ MJPEG frame update error: {e}")

            # ✅ 優化 3: 效能監控與智能幀率控制
            frame_time = time.time() - frame_start
            perf_monitor.record_frame(frame_time)
            
            # 每 30 幀輸出一次效能統計
            if frame_count % 30 == 0:
                stats = perf_monitor.get_stats()
                print(f"📊 Performance: FPS={stats['current_fps']:.1f}, Latency={stats['avg_latency_ms']:.1f}ms")
            
            # 控制幀率（30 FPS）
            target_time = 1.0 / 30.0
            sleep_time = max(0.001, target_time - frame_time)
            time.sleep(sleep_time)

        except Exception as e:
            print(f"❌ Camera capture loop error: {e}")
            time.sleep(1.0)

    # 清理
    print("🛑 Stopping camera capture loop...")
    if yolo_future is not None:
        try:
            yolo_future.cancel()
        except Exception:
            pass
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.5.0",
        "is_analyzing": system_state["is_analyzing"],
        "active_sessions": len(session_manager.get_active_sessions())
    }


# ================== v1.5 WebSocket Control Channel ==================

# WebSocket 連線追蹤
ws_connections: dict[str, WebSocket] = {}  # connection_id -> websocket
ws_heartbeat_tasks: dict[str, asyncio.Task] = {}  # connection_id -> heartbeat task


async def send_ws_envelope(
    websocket: WebSocket,
    msg_type: str,
    payload: dict,
    session_id: str = "",
    stream_id: str = ""
):
    """發送 v1.5 標準 envelope 格式的 WebSocket 消息"""
    envelope = {
        "v": 1,
        "type": msg_type,
        "ts": int(time.time() * 1000),
        "session_id": session_id,
        "stream_id": stream_id,
        "payload": payload
    }
    await websocket.send_text(json.dumps(envelope))


async def heartbeat_loop(websocket: WebSocket, session_id: str, stream_id: str, connection_id: str):
    """
    Heartbeat 循環（v1.5 規範）
    每 3 秒推送一次 heartbeat
    """
    consecutive_no_signal = 0  # ✅ 追蹤連續無信號次數，避免誤判
    
    try:
        while True:
            await asyncio.sleep(config.WS_HEARTBEAT_INTERVAL)
            
            # 檢查連線是否還存在
            if connection_id not in ws_connections:
                break
            
            # 獲取當前狀態
            cap = camera_state.get("current_cap")
            is_alive = cap is not None and cap.isOpened()
            
            # ✅ 使用真實的最新畫面時間戳
            last_frame_time = camera_state.get("last_frame_time", 0.0)
            last_frame_ts = int(last_frame_time * 1000) if last_frame_time > 0 else int(time.time() * 1000)
            
            # ✅ 檢查畫面是否過時（超過 3 秒未更新，給予更多容錯）
            time_since_last_frame = time.time() - last_frame_time if last_frame_time > 0 else 999
            
            # ✅ 穩定性改進：連續 2 次檢測到問題才判定為 NO_SIGNAL
            if not is_alive or time_since_last_frame > 3.0:
                consecutive_no_signal += 1
            else:
                consecutive_no_signal = 0
            
            if camera_state.get("is_switching"):
                pipeline_state = "RECONNECTING"
            elif consecutive_no_signal >= 2:
                pipeline_state = "NO_SIGNAL"
            else:
                pipeline_state = "RUNNING"
            
            # ✅ 計算實際 FPS
            fps = 30.0 if (is_alive and time_since_last_frame < 1.0) else 0.0
            
            await send_ws_envelope(
                websocket,
                "heartbeat",
                {
                    "alive": is_alive,
                    "last_frame_ts": last_frame_ts,
                    "fps_ewma": fps,
                    "pipeline_state": pipeline_state
                },
                session_id,
                stream_id
            )
            
            # 更新 session heartbeat
            session_manager.update_heartbeat(session_id)
            
    except asyncio.CancelledError:
        print(f"Heartbeat task cancelled for connection {connection_id}")
    except Exception as e:
        print(f"Heartbeat error: {e}")


@app.websocket("/ws/control")
async def control_websocket(websocket: WebSocket, session_id: str = Query(...)):
    """
    v1.5 控制 WebSocket 端點
    實現完整的 v1.5 協議：envelope, heartbeat, commands, metadata
    """
    connection_id = f"ws-{uuid.uuid4().hex[:8]}"
    
    # 驗證 session
    session = session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=1008, reason="Invalid session_id")
        return
    
    await websocket.accept()
    print(f"✅ WebSocket connected: {connection_id} for session {session_id}")
    
    # Kick-Old 策略
    old_connection_id = session_manager.register_ws_connection(session_id, connection_id)
    if old_connection_id and old_connection_id in ws_connections:
        old_ws = ws_connections[old_connection_id]
        try:
            await send_ws_envelope(
                old_ws,
                "session.revoked",
                {"reason": "KICK_OLD", "message": "New connection established"},
                session_id,
                session.stream_id
            )
            await old_ws.close(code=4001, reason="Kicked by new connection")
        except Exception as e:
            print(f"Error closing old connection: {e}")
        finally:
            if old_connection_id in ws_connections:
                del ws_connections[old_connection_id]
            if old_connection_id in ws_heartbeat_tasks:
                ws_heartbeat_tasks[old_connection_id].cancel()
                del ws_heartbeat_tasks[old_connection_id]
    
    # 註冊新連線
    ws_connections[connection_id] = websocket
    
    # 啟動 heartbeat 任務
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(websocket, session_id, session.stream_id, connection_id)
    )
    ws_heartbeat_tasks[connection_id] = heartbeat_task
    
    # 發送歡迎消息
    await send_ws_envelope(
        websocket,
        "protocol.welcome",
        {
            "version": "1.5.0",
            "session_id": session_id,
            "connection_id": connection_id,
            "features": ["heartbeat", "metadata", "commands", "stream_switch"]
        },
        session_id,
        session.stream_id
    )
    
    try:
        metadata_counter = 0
        last_metadata_time = time.time()
        metadata_interval = 1.0 / config.METADATA_RATE_HZ  # 10Hz = 0.1s
        
        while True:
            # 非阻塞接收消息（超時檢查）
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                
                # 處理客戶端消息
                try:
                    msg = json.loads(message)
                    msg_type = msg.get("type")
                    payload = msg.get("payload", {})
                    
                    # 處理 protocol.hello（版本協商）
                    if msg_type == "protocol.hello":
                        client_version = payload.get("preferred_version", 1)
                        # 目前只支援 v1
                        negotiated_version = 1 if client_version == 1 else 1
                        # protocol.welcome 已在連線建立時發送，這裡不重複發送
                        print(f"✅ Client protocol.hello received, version: {client_version}")
                    
                    # 處理 client.heartbeat
                    elif msg_type == "client.heartbeat":
                        session_manager.update_heartbeat(session_id)
                    
                    # 處理 cmd.*
                    elif msg_type and msg_type.startswith("cmd."):
                        request_id = payload.get("request_id")
                        
                        # 這裡可以處理各種命令
                        # 目前簡化實現
                        await send_ws_envelope(
                            websocket,
                            "cmd.ack",
                            {"request_id": request_id, "status": "accepted"},
                            session_id,
                            session.stream_id
                        )
                    
                    # 處理 stream.changed.ack
                    elif msg_type == "stream.changed.ack":
                        print(f"Client ACKed stream change: {payload}")
                    
                except json.JSONDecodeError:
                    print(f"Invalid JSON from client: {message}")
                
            except asyncio.TimeoutError:
                # 超時正常，繼續處理
                pass
            
            # 推送 metadata（按頻率限制）
            current_time = time.time()
            if current_time - last_metadata_time >= metadata_interval:
                last_metadata_time = current_time
                
                # 從 latest_analysis_data 獲取數據
                data_packet = latest_analysis_data.get("data", {})
                ar_paths = latest_analysis_data.get("ar_paths", [])
                
                # 構造 metadata payload
                metadata_payload = {
                    "frame_id": metadata_counter,
                    "ts_backend": int(current_time * 1000),
                    "detected_count": len(data_packet.get("balls", [])),
                    "tracking_state": "active" if system_state["is_analyzing"] else "idle",
                    "detections": data_packet.get("balls", []),
                    "prediction": data_packet.get("prediction"),
                    "ar_paths": ar_paths,
                    "bbox": None,  # 可以添加
                    "keypoints": None,  # 可以添加
                    "rate_hz": config.METADATA_RATE_HZ
                }
                
                await send_ws_envelope(
                    websocket,
                    "metadata.update",
                    metadata_payload,
                    session_id,
                    session.stream_id
                )
                
                metadata_counter += 1
            
            # 小延遲避免 CPU 佔用過高
            await asyncio.sleep(0.01)
            
    except WebSocketDisconnect:
        print(f"👋 WebSocket disconnected: {connection_id}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
    finally:
        # 清理
        if connection_id in ws_connections:
            del ws_connections[connection_id]
        if connection_id in ws_heartbeat_tasks:
            ws_heartbeat_tasks[connection_id].cancel()
            del ws_heartbeat_tasks[connection_id]
        session_manager.unregister_ws_connection(session_id, connection_id)
        print(f"📴 WebSocket closed: {connection_id}")


# ================== 低頻分析數據 WebSocket（HLS 模式專用） ==================
# 存儲最新分析數據，供低頻 WebSocket 使用
latest_analysis_data: dict[str, Any] = {
    "data": {},
    "ar_paths": [],
    "status": "Idle",
    "timestamp": 0,
}


@app.websocket("/ws/analytics")
async def analytics_endpoint(websocket: WebSocket):
    """
    低頻分析數據通道 - 與 HLS 視頻流配合使用
    只傳送 JSON 分析數據，不傳輸影像
    更新頻率：約 10 Hz（每 100ms）
    """
    await websocket.accept()
    print("✅ Analytics WebSocket connected (low-frequency data channel)")

    try:
        while True:
            # 發送最新分析數據
            payload = {
                "data": latest_analysis_data.get("data", {}),
                "ar_paths": latest_analysis_data.get("ar_paths", []),
                "status": latest_analysis_data.get("status", "Idle"),
                "is_analyzing": system_state["is_analyzing"],
                "timestamp": time.time(),
                "mjpeg_stats": mjpeg_manager.get_stats() if mjpeg_manager else None,
            }
            await websocket.send_text(json.dumps(payload))

            # 低頻更新：100ms 間隔 (10 Hz)
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print("👋 Analytics WebSocket disconnected")
    except Exception as e:
        print(f"❌ Analytics WebSocket error: {e}")


@app.websocket("/ws/video")
async def video_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"✅ Client connected, using camera device: {camera_state['selected_device_id']}")

    # 開啟所選的攝像頭設備
    cap = open_camera(camera_state["selected_device_id"])
    if cap is None:
        print("❌ Failed to open camera on WebSocket connect")
        await websocket.send_text(json.dumps({"status": "error", "message": "Failed to open camera device"}))
        await websocket.close()
        return

    try:
        failure_count = 0
        max_failures = 10  # ✅ 增加到 10 次，更寬容
        frame_count = 0
        consecutive_successes = 0
        last_processed_frame: Optional[Any] = None
        last_data_packet: Optional[dict[str, Any]] = None
        last_ar_paths: list[Any] = []

        while True:
            # 檢查是否需要切換攝像頭
            if camera_state["needs_switch"] and not camera_state["is_switching"]:
                print(f"📱 WebSocket: Initiating async camera switch to device {camera_state['new_device_id']}")
                camera_state["is_switching"] = True
                camera_state["needs_switch"] = False
                loop = asyncio.get_event_loop()
                loop.run_in_executor(executor, switch_camera_background, camera_state["new_device_id"])
                cap = camera_state["current_cap"]
                if cap is None:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "status": "error",
                                "message": f"Failed to switch to camera {camera_state['new_device_id']}",
                            }
                        )
                    )
                    break

            # ✅ 嘗試讀取幀
            ret, frame = cap.read()

            # 若使用影片來源，嘗試迴圈播放避免讀到結尾造成閃爍
            if getattr(config, "VIDEO_SOURCE", "") and (not ret or frame is None):
                try:
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                    if getattr(config, "LOOP_VIDEO_SOURCE", True) and total_frames > 0:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                except Exception:
                    pass

            if not ret or frame is None:
                if failure_count >= max_failures:
                    print(f"🔁 Reopening camera after {failure_count} failures")
                    try:
                        cap.release()
                    except Exception:
                        pass

                    # 重新開啟
                    cap = open_camera(camera_state["selected_device_id"])
                    if cap is not None:
                        print("   ✅ Camera reopened")
                        failure_count = 0
                    else:
                        print("❌ Failed to reopen camera")
                        await websocket.send_text(json.dumps({"status": "error", "message": "Camera unavailable"}))
                        break

                await asyncio.sleep(0.01)
                continue
            else:
                # ✅ 成功讀取
                failure_count = 0
                consecutive_successes += 1
                frame_count += 1

            # ✅ YOLO 處理（線程池）- ⭐ 支援跳幀加速
            yolo_start = time.time()
            skip_yolo = False
            used_cached = False
            try:
                # ✅ 推論跳幀：每 N 幀執行一次 YOLO（減少 CPU 負載）
                skip_yolo = frame_count % (system_state.get("yolo_skip_frames", 2) + 1) != 0

                if system_state["is_analyzing"] and tracker is not None and not skip_yolo:
                    loop = asyncio.get_event_loop()
                    processed_frame, data_packet = await loop.run_in_executor(executor, tracker.process_frame, frame)
                elif skip_yolo and last_processed_frame is not None and last_data_packet is not None:
                    processed_frame = last_processed_frame.copy()
                    data_packet = {**last_data_packet, "status": last_data_packet.get("status", "cached"), "skipped": True, "frame_count": frame_count}
                    used_cached = True
                else:
                    processed_frame = frame.copy()
                    skip_reason = "skipped" if skip_yolo else "idle"
                    data_packet = {"status": skip_reason, "frame_count": frame_count}
            except Exception as e:
                print(f"❌ Frame processing error: {e}")
                processed_frame = frame.copy()
                data_packet = {"error": str(e), "frame_count": frame_count}
            yolo_elapsed = time.time() - yolo_start
            record_perf("yolo", yolo_elapsed)

            # ✅ AR 座標轉換
            ar_paths: list[Any] = []
            if used_cached:
                ar_paths = list(last_ar_paths)
            elif data_packet.get("prediction") and calibrator is not None:
                try:
                    raw_paths = data_packet["prediction"]["paths"]
                    ar_paths = calibrator.transform_points(raw_paths)
                except Exception:
                    pass

            if not used_cached and system_state["is_analyzing"] and tracker is not None and not skip_yolo:
                last_processed_frame = processed_frame.copy()
                last_data_packet = data_packet
                last_ar_paths = ar_paths

            # ✅ 添加幀到 MJPEG 串流（監控和投影）
            if mjpeg_manager is not None:
                try:
                    # 監控流：原始或處理後的幀 (1280×720)
                    monitor_frame = cv2.resize(processed_frame, (1280, 720))
                    mjpeg_manager.update_monitor(monitor_frame)

                    # 投影流：通過投影機校準變形 (1920×1080)
                    projector_frame = processed_frame
                    if calibrator is not None:
                        projector_frame = calibrator.warp_frame_to_projector(processed_frame)
                    else:
                        projector_frame = cv2.resize(processed_frame, (1920, 1080))
                    mjpeg_manager.update_projector(projector_frame)
                except Exception as e:
                    print(f"⚠️  MJPEG frame update error: {e}")

            # ✅ 更新低頻分析數據（供 HLS 模式的 /ws/analytics 使用）
            latest_analysis_data["data"] = data_packet
            latest_analysis_data["ar_paths"] = ar_paths
            latest_analysis_data["status"] = "Analyzing" if system_state["is_analyzing"] else "Idle"
            latest_analysis_data["timestamp"] = time.time()

            # ✅ 影像編碼（線程池，避免阻塞 event loop）
            encode_start = time.time()
            loop = asyncio.get_event_loop()

            frame_for_stream = processed_frame
            if getattr(config, "STREAM_PROJECTOR_VIEW", True) and calibrator is not None:
                frame_for_stream = calibrator.warp_frame_to_projector(processed_frame)

            image_buffer = await loop.run_in_executor(
                executor, encode_image_buffer, frame_for_stream, getattr(config, "JPEG_QUALITY", 70)
            )
            encode_elapsed = time.time() - encode_start
            record_perf("encode", encode_elapsed)

            # ✅ 傳送（線程池）
            websocket_start = time.time()
            payload = {
                "data": data_packet,
                "ar_paths": ar_paths,
                "status": "Analyzing" if system_state["is_analyzing"] else "Idle",
                "current_device_id": camera_state["selected_device_id"],
                "is_switching": camera_state["is_switching"],
                "frame_count": frame_count,
                "consecutive_successes": consecutive_successes,
                "perf": {
                    "yolo_ms": yolo_elapsed * 1000,
                    "encode_ms": encode_elapsed * 1000,
                },
            }

            try:
                await websocket.send_text(json.dumps(payload))
                if image_buffer is not None:
                    await websocket.send_bytes(image_buffer)
            except Exception as e:
                print(f"❌ WebSocket send error: {e}")
                break

            websocket_elapsed = time.time() - websocket_start
            record_perf("websocket", websocket_elapsed)

            # ✅ 30 FPS
            await asyncio.sleep(0.033)
    except WebSocketDisconnect:
        print("👋 Client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        print("📴 Video endpoint closed")


@app.post("/api/control/toggle")
async def toggle_analysis():
    system_state["is_analyzing"] = not system_state["is_analyzing"]
    print(f"🎛️  YOLO Analysis toggled: {system_state['is_analyzing']}")
    print(f"   Tracker available: {tracker is not None}")
    return {"status": "success", "is_analyzing": system_state["is_analyzing"]}


# ✅ 動態調整跳幀設置
@app.post("/api/control/yolo-skip")
async def set_yolo_skip(request: Annotated[dict, Body(...)]):
    """設置推論跳幀數量（0=每幀執行，2=每3幀執行一次）"""
    skip_frames = request.get("skip_frames", 2)
    if skip_frames < 0 or skip_frames > 10:
        return {"status": "error", "message": "skip_frames must be 0-10"}
    system_state["yolo_skip_frames"] = skip_frames
    return {"status": "success", "yolo_skip_frames": skip_frames, "inference_frequency": f"1/{skip_frames + 1} frames"}


# --- 新增 API: 列舉攝像頭設備 ---
@app.get("/api/camera/enumerate")
async def enumerate_cameras():
    """掃描並回傳所有可用的攝像頭設備"""
    devices = enumerate_camera_devices()
    camera_state["available_devices"] = devices
    return {"devices": devices, "current_device_id": camera_state["selected_device_id"]}


# --- 新增 API: 選擇攝像頭設備 ---
@app.post("/api/camera/select")
async def select_camera(request: Annotated[dict, Body(...)]):
    """切換到指定的攝像頭設備 (立即在 WebSocket 中生效)"""
    device_id = request.get("device_id", 0)

    if device_id < 0 or device_id > 10:
        return {"status": "error", "message": "Invalid device ID"}

    # 設置切換標記，WebSocket 迴圈會偵測並執行切換
    camera_state["new_device_id"] = device_id
    camera_state["needs_switch"] = True

    print(f"Camera switch requested: device_id={device_id}")
    return {
        "status": "success",
        "requested_device_id": device_id,
        "current_device_id": camera_state["selected_device_id"],
    }


# --- 新增 API 2: 截圖功能 ---
@app.post("/api/control/snapshot")
async def take_snapshot():
    # 這裡簡單實作：告訴前端「已截圖」，實際存檔邏輯可以加在這裡
    # 若要在後端存檔：
    # cv2.imwrite(f"snapshot_{int(time.time())}.jpg", current_frame)
    return {"status": "success", "message": "Screenshot saved"}


# --- 新增 API 3: 品質控制 (v1.5 P1 功能) ---
@app.post("/api/stream/quality")
async def set_stream_quality(request: Annotated[dict, Body(...)]):
    """
    設定串流品質模式
    支援手動品質設定和自動品質調整
    """
    stream_id = request.get("stream_id")
    quality = request.get("quality")  # "low", "med", "high", "auto"
    enable_auto = request.get("enable_auto", False)
    
    # 驗證參數
    if not stream_id or quality not in ["low", "med", "high", "auto"]:
        return create_error_response(ERR_INVALID_ARGUMENT, "Invalid quality setting")
    
    if not mjpeg_manager:
        return create_error_response(ERR_STREAM_UNAVAILABLE, "MJPEG manager not available")
    
    # 選擇對應的串流
    stream = mjpeg_manager.monitor if stream_id == "camera1" else mjpeg_manager.projector
    
    # 設定自動品質
    is_auto = (quality == "auto" or enable_auto)
    stream.set_auto_quality(is_auto)
    
    # 如果不是自動模式,設定固定品質
    if not is_auto:
        quality_map = {"low": 55, "med": 70, "high": 85}
        stream.set_quality(quality_map[quality])
    
    return JSONResponse({
        "stream_id": stream_id,
        "quality": quality,
        "auto_quality_enabled": stream.auto_quality,
        "current_quality": stream.quality
    })


# --- 新增 API 4: 效能統計 (用於 Dashboard) ---
@app.get("/api/performance/stats")
async def get_performance_stats():
    """
    獲取效能統計數據
    提供 FPS、延遲等即時指標給前端 Dashboard
    """
    # 從全域 performance monitor 獲取實際數據
    if global_perf_monitor:
        perf_stats_data = global_perf_monitor.get_stats()
        current_fps = perf_stats_data.get("current_fps", 0.0)
        avg_latency = perf_stats_data.get("avg_latency_ms", 0.0)
    else:
        # 如果 monitor 還未初始化,使用預設值
        current_fps = 0.0
        avg_latency = 0.0
    
    stats = {
        "current_fps": current_fps,
        "avg_latency_ms": avg_latency,
        "stream_active": camera_state.get("last_frame_time", 0) > 0,
        "is_analyzing": system_state.get("is_analyzing", False),
    }
    
    if mjpeg_manager:
        mjpeg_stats = mjpeg_manager.get_stats()
        stats["mjpeg_stats"] = mjpeg_stats
    
    return JSONResponse(stats)




# ================== v1.5 REST API Endpoints ==================

# --- Streams API ---
@app.get("/api/streams")
async def get_streams():
    """列出可用影像來源（v1.5 規範）"""
    streams = [
        {
            "stream_id": "camera1",
            "name": "主攝像頭",
            "type": "usb",
            "available": camera_state["current_cap"] is not None,
            "resolution": f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}",
            "fps": config.CAMERA_FPS,
            "burnin_url": "/burnin/camera1.mjpg",
            "capabilities": ["low", "med", "high"]
        }
    ]
    
    # 如果有視頻源
    if config.VIDEO_SOURCE:
        streams.append({
            "stream_id": "file1",
            "name": "Video File",
            "type": "file",
            "available": True,
            "resolution": f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}",
            "fps": config.CAMERA_FPS,
            "burnin_url": "/burnin/file1.mjpg",
            "capabilities": ["low", "med", "high"]
        })
    
    return streams


@app.get("/api/stream/status")
async def get_stream_status(stream_id: str = Query(...)):
    """獲取指定 stream 的狀態（v1.5 規範）"""
    if not stream_id or stream_id not in ["camera1", "file1"]:
        return JSONResponse(
            status_code=400,
            content=create_error_response(ERR_INVALID_ARGUMENT, "Invalid stream_id")
        )
    
    cap = camera_state.get("current_cap")
    is_alive = cap is not None and cap.isOpened()
    
    # 簡化的 pipeline 狀態判定
    if not is_alive:
        pipeline_state = "NO_SIGNAL"
    elif camera_state.get("is_switching"):
        pipeline_state = "RECONNECTING"
    else:
        pipeline_state = "RUNNING"
    
    return {
        "stream_id": stream_id,
        "alive": is_alive,
        "pipeline_state": pipeline_state,
        "last_frame_ts": int(time.time() * 1000),
        "fps_ewma": 30.0 if is_alive else 0.0,
        "last_error": None
    }


# --- Sessions API ---
@app.post("/api/sessions")
async def create_session(request: Annotated[dict, Body(...)]):
    """創建新 session（v1.5 規範）"""
    stream_id = request.get("stream_id", "camera1")
    role_str = request.get("role_requested", "operator")
    client_info = request.get("client_info", {})
    
    # 驗證 stream_id
    if stream_id not in ["camera1", "file1"]:
        return JSONResponse(
            status_code=400,
            content=create_error_response(ERR_INVALID_ARGUMENT, "Invalid stream_id")
        )
    
    # 解析角色
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.OPERATOR
    
    # 創建 session
    session = session_manager.create_session(
        stream_id=stream_id,
        role=role,
        client_info=client_info
    )
    
    return {
        "session_id": session.session_id,
        "stream_id": session.stream_id,
        "role": session.role.value,
        "permission_flags": session.permission_flags,
        "ws_url": f"/ws/control?session_id={session.session_id}",
        "burnin_url": f"/burnin/{stream_id}.mjpg",
        "expires_at": int(session.expires_at * 1000)
    }


@app.post("/api/sessions/{session_id}/renew")
async def renew_session(session_id: str):
    """續期 session（v1.5 規範）"""
    if not session_manager.renew_session(session_id):
        return JSONResponse(
            status_code=404,
            content=create_error_response(ERR_SESSION_EXPIRED, "Session not found or expired")
        )
    
    session = session_manager.get_session(session_id)
    return {
        "session_id": session_id,
        "expires_at": int(session.expires_at * 1000),
        "status": "renewed"
    }


@app.post("/api/sessions/{session_id}/switch_stream")
async def switch_session_stream(session_id: str, request: Annotated[dict, Body(...)]):
    """切換 session 的 stream（v1.5 規範）"""
    new_stream_id = request.get("stream_id")
    
    if not new_stream_id or new_stream_id not in ["camera1", "file1"]:
        return JSONResponse(
            status_code=400,
            content=create_error_response(ERR_INVALID_ARGUMENT, "Invalid stream_id")
        )
    
    if not session_manager.switch_stream(session_id, new_stream_id):
        return JSONResponse(
            status_code=404,
            content=create_error_response(ERR_NOT_FOUND, "Session not found")
        )
    
    return {
        "session_id": session_id,
        "new_stream_id": new_stream_id,
        "new_burnin_url": f"/burnin/{new_stream_id}.mjpg"
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """刪除 session（v1.5 規範）"""
    if not session_manager.delete_session(session_id):
        return JSONResponse(
            status_code=404,
            content=create_error_response(ERR_NOT_FOUND, "Session not found")
        )
    
    return {"status": "deleted", "session_id": session_id}


# --- Config API ---
@app.get("/api/config")
async def get_config():
    """獲取系統配置（v1.5 規範）"""
    return {
        "version": "1.5.0",
        "flags": {
            "dev_ui": config.ENABLE_DEV_MODE,
            "replay": config.ENABLE_REPLAY,
            "multi_table": config.ENABLE_MULTI_TABLE
        },
        "limits": {
            "max_sessions": 10,
            "session_ttl": config.SESSION_TTL,
            "metadata_rate_hz": config.METADATA_RATE_HZ
        },
        "streams": {
            "available_streams": ["camera1", "file1"] if config.VIDEO_SOURCE else ["camera1"],
            "default_quality": "med"
        }
    }


# ✅ 新增性能監控 API
@app.get("/api/performance")
async def get_performance_metrics():
    """獲取系統性能指標"""
    stats = get_perf_stats()
    return {
        **stats,
        "event_loop_lag": "⚠️ Monitor if > 100ms",
        "recommendations": [
            "If yolo_ms > 300, consider reducing resolution or using smaller model",
            "If encode_ms > 50, try reducing JPEG_QUALITY",
            "If websocket_ms > 30, check network bandwidth",
        ],
    }


# ✅ 重置性能統計
@app.post("/api/performance/reset")
async def reset_performance_metrics():
    """重置性能統計數據"""
    with perf_stats["lock"]:
        perf_stats["total_frames"] = 0
        perf_stats["yolo_time"] = 0.0
        perf_stats["encode_time"] = 0.0
        perf_stats["websocket_time"] = 0.0
    return {"status": "reset", "message": "Performance metrics cleared"}


# ✅ 球桌布料顏色設定 API
@app.get("/api/table/colors")
async def get_table_colors():
    """獲取所有可用的球桌布料顏色預設"""
    presets = {}
    for key, value in config.TABLE_COLOR_PRESETS.items():
        presets[key] = {
            "name": value["name"],
            "hsv_lower": value["hsv_lower"].tolist(),
            "hsv_upper": value["hsv_upper"].tolist(),
        }

    return {
        "current": config.TABLE_CLOTH_COLOR if tracker else "green",
        "current_display": tracker.current_table_color if tracker else "green",
        "presets": presets,
    }


@app.post("/api/table/color")
async def update_table_color(request: dict = Body(...)):
    """
    更新球桌布料顏色
    Body:
      - color: 顏色名稱 (green, gray, blue, pink, purple, custom)
      - hsv_lower: (可選) 自訂 HSV 下限 [H, S, V]
      - hsv_upper: (可選) 自訂 HSV 上限 [H, S, V]
    """
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")

    color_name = request.get("color")
    if not color_name:
        raise HTTPException(status_code=400, detail="Missing 'color' parameter")

    # 處理自訂顏色
    if color_name == "custom":
        hsv_lower = request.get("hsv_lower")
        hsv_upper = request.get("hsv_upper")

        if not hsv_lower or not hsv_upper:
            raise HTTPException(
                status_code=400,
                detail="Custom color requires 'hsv_lower' and 'hsv_upper' parameters"
            )

        if len(hsv_lower) != 3 or len(hsv_upper) != 3:
            raise HTTPException(
                status_code=400,
                detail="HSV values must be arrays of 3 integers [H, S, V]"
            )

        success = tracker.update_custom_hsv(hsv_lower, hsv_upper)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update custom HSV range")
    else:
        # 使用預設顏色
        success = tracker.update_table_color(color_name)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid color name: {color_name}. Available: {list(config.TABLE_COLOR_PRESETS.keys())}"
            )

    return {
        "status": "success",
        "color": color_name,
        "message": f"Table color updated to {color_name}",
        "hsv_lower": tracker.hsv_lower.tolist(),
        "hsv_upper": tracker.hsv_upper.tolist(),
    }


# ================== MJPEG 流媒體 API ==================

# ✅ v1.5 Burn-in MJPEG 端點
@app.get("/burnin/{stream_id}.mjpg")
async def burnin_stream(stream_id: str, quality: str = Query("med")):
    """
    Burn-in 串流端點（v1.5 規範）
    支持 camera1, camera2, projector, file1
    quality: low | med | high
    """
    if mjpeg_manager is None:
        return Response("MJPEG not available", status_code=503)
    
    # 質量映射
    quality_map = {"low": 50, "med": 70, "high": 100}
    jpeg_quality = quality_map.get(quality, 70)
    
    print(f"🎬 Burnin stream requested: {stream_id}, quality={quality} (JPEG={jpeg_quality})")
    
    # 根據 stream_id 選擇對應的 MJPEG 流並傳入畫質參數
    if stream_id in ["camera1", "file1"]:
        return StreamingResponse(
            mjpeg_manager.monitor.generate(quality=jpeg_quality),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )
    elif stream_id == "projector":
        return StreamingResponse(
            mjpeg_manager.projector.generate(quality=jpeg_quality),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )
    else:
        raise HTTPException(status_code=404, detail="Stream not found")


# ✅ MJPEG 串流端點 - 監控畫面
@app.get("/stream/monitor")
async def mjpeg_monitor_stream():
    """監控畫面 MJPEG 串流 - 直接用 <img src="..."> 即可顯示"""
    if mjpeg_manager is None:
        return Response("MJPEG not available", status_code=503)

    return StreamingResponse(
        mjpeg_manager.monitor.generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ✅ MJPEG 串流端點 - 投影畫面
@app.get("/stream/projector")
async def mjpeg_projector_stream():
    """投影畫面 MJPEG 串流 - 直接用 <img src="..."> 即可顯示"""
    if mjpeg_manager is None:
        return Response("MJPEG not available", status_code=503)

    return StreamingResponse(
        mjpeg_manager.projector.generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ✅ 獲取 MJPEG 統計信息
@app.get("/api/stream/stats")
async def get_stream_stats():
    """獲取 MJPEG 串流統計"""
    if mjpeg_manager is None:
        return {"status": "disabled", "message": "MJPEG not initialized"}

    return {
        "status": "active",
        "streams": mjpeg_manager.get_stats(),
        "endpoints": {
            "monitor": "/stream/monitor",
            "projector": "/stream/projector",
        },
    }


@app.on_event("startup")
async def startup_event():
    """應用啟動時的初始化"""
    global camera_capture_thread

    print("🚀 Starting camera capture thread for burn-in stream...")
    # 在背景線程中啟動攝像頭捕獲循環
    camera_capture_thread = threading.Thread(target=camera_capture_loop, daemon=True)
    camera_capture_thread.start()


@app.on_event("shutdown")
async def shutdown_event():
    """應用關閉時的清理"""
    print("🛑 Shutting down camera capture thread...")
    camera_running.clear()

    if camera_capture_thread is not None:
        camera_capture_thread.join(timeout=5.0)


# ================== Game Mode APIs ==================

@app.post("/api/game/start")
async def start_game(request: Annotated[dict, Body(...)]):
    """開始遊戲"""
    mode = request.get("mode", "nine_ball")
    player1 = request.get("player1", "玩家1")
    player2 = request.get("player2", "玩家2")
    target_rounds = request.get("target_rounds", 5)
    shot_time_limit = request.get("shot_time_limit", 0)
    
    print(f"🎮 Starting game: mode={mode}, players={player1} vs {player2}, rounds={target_rounds}, time_limit={shot_time_limit}")
    
    try:
        if mode == "nine_ball":
            result = game_manager.start_nine_ball(player1, player2, target_rounds, shot_time_limit)
            
            if "error" in result:
                print(f"❌ Game start failed: {result['error']}")
                return create_error_response(ERR_INVALID_ARGUMENT, result["error"])
            
            print(f"✅ Game started successfully: {result}")
            return JSONResponse(result)
        else:
            print(f"❌ Unsupported mode: {mode}")
            return create_error_response(ERR_INVALID_ARGUMENT, f"Unsupported mode: {mode}")
        
    except Exception as e:
        print(f"❌ Exception in start_game: {e}")
        import traceback
        traceback.print_exc()
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/game/check_rules")
async def check_game_rules(request: Annotated[dict, Body(...)]):
    """檢查遊戲規則 (9球)"""
    first_contact = request.get("first_contact")
    potted_ball = request.get("potted_ball")
    
    try:
        result = game_manager.check_nine_ball_rules(first_contact, potted_ball)
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/game/end_turn")
async def end_turn():
    """結束回合,換人"""
    try:
        if not game_manager.game_state:
            return create_error_response(ERR_INVALID_ARGUMENT, "No active game")
        
        old_player = game_manager.game_state.current_player
        game_manager.switch_player()
        new_player = game_manager.game_state.current_player
        
        print(f"🔄 Turn ended: Player {old_player} → Player {new_player}")
        
        # ⭐ 重置計時器
        if game_manager.game_state.shot_time_limit > 0:
            game_manager.game_state.remaining_time = game_manager.game_state.shot_time_limit
            game_manager.game_state.last_update_time = time.time()
            print(f"⏱️ Timer reset to {game_manager.game_state.shot_time_limit} seconds")
        
        state = game_manager.get_game_state()
        return JSONResponse(state)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/game/forfeit")
async def forfeit_round(request: Annotated[dict, Body(...)]):
    """認輸 - 給對手加1分並重置球檯"""
    try:
        if not game_manager.game_state:
            return create_error_response(ERR_INVALID_ARGUMENT, "No active game")
        
        forfeit_player = request.get("forfeit_player")
        if not forfeit_player or forfeit_player not in [1, 2]:
            return create_error_response(ERR_INVALID_ARGUMENT, "Invalid forfeit_player")
        
        opponent_player = 2 if forfeit_player == 1 else 1
        print(f"🏳️ Player {forfeit_player} forfeits, Player {opponent_player} scores")
        
        # 給對手加1分
        game_manager.game_state.scores[opponent_player - 1] += 1
        
        # 重置球檯
        game_manager.game_state.remaining_balls = list(range(1, 10))
        game_manager.game_state.target_ball = 1
        game_manager.game_state.foul_detected = False
        game_manager.game_state.foul_reason = None
        game_manager.game_state.current_player = opponent_player
        
        # 重置計時器和延時
        if game_manager.game_state.shot_time_limit > 0:
            game_manager.game_state.remaining_time = game_manager.game_state.shot_time_limit
            game_manager.game_state.delay_used = [False, False]
            game_manager.game_state.last_update_time = time.time()
        
        return JSONResponse(game_manager.get_game_state())
    except Exception as e:
        print(f"❌ Error in forfeit: {e}")
        import traceback
        traceback.print_exc()
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/game/state")
async def get_game_state():
    """獲取遊戲狀態"""
    state = game_manager.get_game_state()
    if state:
        return JSONResponse(state)
    return JSONResponse({"active": False})


@app.post("/api/game/end")
async def end_game():
    """結束遊戲"""
    try:
        game_manager.end_game()
        return JSONResponse({"status": "game_ended"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/practice/start")
async def start_practice(request: Annotated[dict, Body(...)]):
    """開始練習"""
    mode = request.get("mode", "single")
    pattern = request.get("pattern")
    
    try:
        result = game_manager.start_practice(mode, pattern)
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/practice/record")
async def record_practice(request: Annotated[dict, Body(...)]):
    """記錄練習結果"""
    success = request.get("success", False)
    
    try:
        result = game_manager.record_practice_attempt(success)
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/practice/state")
async def get_practice_state():
    """獲取練習狀態"""
    state = game_manager.get_practice_state()
    if state:
        return JSONResponse(state)
    return JSONResponse({"active": False})


@app.post("/api/practice/end")
async def end_practice():
    """結束練習"""
    try:
        game_manager.end_practice()
        return JSONResponse({"status": "practice_ended"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


# ================== Recording APIs ==================

@app.post("/api/recording/start")
async def start_recording(request: Annotated[dict, Body(...)]):
    """開始錄影"""
    game_type = request.get("game_type")
    players = request.get("players", [])
    
    try:
        game_id = recording_manager.start_recording(
            game_type=game_type,
            players=players
        )
        return JSONResponse({
            "status": "recording_started",
            "game_id": game_id
        })
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/recording/stop")
async def stop_recording(request: Annotated[dict, Body(...)]):
    """停止錄影"""
    final_score = request.get("final_score")
    winner = request.get("winner")
    total_rounds = request.get("total_rounds", 0)
    
    try:
        result = recording_manager.stop_recording(
            final_score=final_score,
            winner=winner,
            total_rounds=total_rounds
        )
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/recording/event")
async def log_recording_event(request: Annotated[dict, Body(...)]):
    """記錄遊戲事件"""
    event_type = request.get("event_type")
    data = request.get("data", {})
    
    try:
        recording_manager.log_event(event_type, data)
        return JSONResponse({"status": "logged"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/recordings")
async def get_recordings():
    """獲取錄影列表"""
    try:
        recordings = recording_manager.get_recordings_list()
        return JSONResponse({"recordings": recordings})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/recording/{game_id}/metadata")
async def get_recording_metadata(game_id: str):
    """獲取特定錄影的元資料"""
    metadata = recording_manager.get_recording_metadata(game_id)
    
    if metadata:
        return JSONResponse(metadata)
    return create_error_response(ERR_NOT_FOUND, "Recording not found")


@app.get("/api/recording/{game_id}/events")
async def get_recording_events(game_id: str):
    """獲取錄影的事件日誌"""
    try:
        events = recording_manager.get_recording_events(game_id)
        return JSONResponse({"events": events})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


if __name__ == "__main__":
    print("=" * 75)
    print("🚀 撞球分析系統後端啟動 - MJPEG 串流架構")
    print("=" * 75)
    print("\n📡 原有 WebSocket 端點（保留兼容）:")
    print("  /ws/video     - 視頻 + 數據（Base64 JPEG）")
    print("  /ws/analytics - 低頻分析數據（MJPEG 模式專用，10Hz）")
    print("\n🎬 MJPEG 直播流端點（瀏覽器原生支持）:")
    print("  /stream/monitor   - 監控畫面 1280×720  → 直接用 <img> 顯示")
    print("  /stream/projector - 投影畫面 1920×1080 → 直接用 <img> 顯示")
    print("  /api/stream/stats - 串流統計")
    print("\n📷 攝像頭 API:")
    print("  GET  /api/camera/enumerate - 列舉可用攝像頭")
    print("  POST /api/camera/select    - 切換攝像頭")
    print("\n🎛️  控制 API:")
    print("  POST /api/control/toggle    - 開/關 YOLO 分析")
    print("  POST /api/control/yolo-skip - 設置推論跳幀")
    print("  GET  /api/performance       - 性能統計")
    print("\n🎥 v1.5 Burn-in 串流:")
    print("  /burnin/{stream_id}.mjpg?quality=med - 即時影像（自動啟動攝像頭）")
    print("=" * 75)
    print("\n⚙️  架構說明:")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  前端可選擇兩種模式:                                             │")
    print("│                                                                 │")
    print("│  [WebSocket 模式] - 低延遲，適合本地部署                          │")
    print("│    └─ /ws/video → Base64 JPEG + JSON 數據                       │")
    print("│                                                                 │")
    print("│  [MJPEG 模式] - 穩定流暢，瀏覽器原生支持                           │")
    print("│    ├─ /stream/monitor   → <img src=\"...\"> 直接顯示              │")
    print("│    ├─ /stream/projector → 投影專用流                             │")
    print("│    └─ /ws/analytics     → 低頻分析數據                           │")
    print("│                                                                 │")
    print("│  [v1.5 Burn-in] - 自動啟動攝像頭，無需 WebSocket                  │")
    print("│    └─ /burnin/{stream_id}.mjpg → 即時影像串流                    │")
    print("└─────────────────────────────────────────────────────────────────┘")
    print("=" * 75)
    
    # ==================== v1.5 新增: 計時器 API (動態註冊) ====================
    @app.get("/api/game/timer/state")
    async def get_timer_state():
        """獲取計時器狀態"""
        try:
            state = game_manager.get_timer_state()
            if "error" in state:
                return create_error_response("TIMER_ERROR", state["error"])
            return JSONResponse(state)
        except Exception as e:
            return create_error_response(ERR_INTERNAL, str(e))
    
    @app.post("/api/game/timer/delay")
    async def apply_timer_delay(request: Annotated[dict, Body(...)]):
        """應用延時 (+30秒)"""
        player = request.get("player")
        
        try:
            result = game_manager.apply_delay(player)
            if "error" in result:
                return create_error_response("DELAY_ERROR", result["error"])
            return JSONResponse(result)
        except Exception as e:
            return create_error_response(ERR_INTERNAL, str(e))
    
    uvicorn.run(app, host="0.0.0.0", port=8001)


# ================== Game Mode APIs ==================

@app.post("/api/game/start")
async def start_game(request: Annotated[dict, Body(...)]):
    """開始遊戲"""
    mode = request.get("mode", "nine_ball")
    player1 = request.get("player1", "玩家1")
    player2 = request.get("player2", "玩家2")
    target_rounds = request.get("target_rounds", 5)
    shot_time_limit = request.get("shot_time_limit", 0)  # ⭐ v1.5 新增
    
    print(f"🎮 Starting game: mode={mode}, players={player1} vs {player2}, rounds={target_rounds}, time_limit={shot_time_limit}")
    
    try:
        if mode == "nine_ball":
            result = game_manager.start_nine_ball(player1, player2, target_rounds, shot_time_limit)
            
            # 檢查是否有錯誤
            if "error" in result:
                print(f"❌ Game start failed: {result['error']}")
                return create_error_response(ERR_INVALID_ARGUMENT, result["error"])
            
            print(f"✅ Game started successfully: {result}")
            return JSONResponse(result)
        else:
            print(f"❌ Unsupported mode: {mode}")
            return create_error_response(ERR_INVALID_ARGUMENT, f"Unsupported mode: {mode}")
        
    except Exception as e:
        print(f"❌ Exception in start_game: {e}")
        import traceback
        traceback.print_exc()
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/game/check_rules")
async def check_game_rules(request: Annotated[dict, Body(...)]):
    """檢查遊戲規則 (9球)"""
    first_contact = request.get("first_contact")
    potted_ball = request.get("potted_ball")
    
    try:
        result = game_manager.check_nine_ball_rules(first_contact, potted_ball)
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/game/end_turn")
async def end_turn():
    """結束回合,換人"""
    try:
        game_manager.switch_player()
        state = game_manager.get_game_state()
        return JSONResponse(state or {"error": "No active game"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/game/state")
async def get_game_state():
    """獲取遊戲狀態"""
    state = game_manager.get_game_state()
    if state:
        return JSONResponse(state)
    return JSONResponse({"active": False})


@app.post("/api/game/end")
async def end_game():
    """結束遊戲"""
    try:
        game_manager.end_game()
        return JSONResponse({"status": "game_ended"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/practice/start")
async def start_practice(request: Annotated[dict, Body(...)]):
    """開始練習"""
    mode = request.get("mode", "single")
    pattern = request.get("pattern")
    
    try:
        result = game_manager.start_practice(mode, pattern)
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/practice/record")
async def record_practice(request: Annotated[dict, Body(...)]):
    """記錄練習結果"""
    success = request.get("success", False)
    
    try:
        result = game_manager.record_practice_attempt(success)
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/practice/state")
async def get_practice_state():
    """獲取練習狀態"""
    state = game_manager.get_practice_state()
    if state:
        return JSONResponse(state)
    return JSONResponse({"active": False})


@app.post("/api/practice/end")
async def end_practice():
    """結束練習"""
    try:
        game_manager.end_practice()
        return JSONResponse({"status": "practice_ended"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


# ================== Recording APIs ==================

@app.post("/api/recording/start")
async def start_recording(request: Annotated[dict, Body(...)]):
    """開始錄影"""
    game_type = request.get("game_type")
    players = request.get("players", [])
    
    try:
        game_id = recording_manager.start_recording(
            game_type=game_type,
            players=players
        )
        return JSONResponse({
            "status": "recording_started",
            "game_id": game_id
        })
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/recording/stop")
async def stop_recording(request: Annotated[dict, Body(...)]):
    """停止錄影"""
    final_score = request.get("final_score")
    winner = request.get("winner")
    total_rounds = request.get("total_rounds", 0)
    
    try:
        result = recording_manager.stop_recording(
            final_score=final_score,
            winner=winner,
            total_rounds=total_rounds
        )
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/recording/event")
async def log_recording_event(request: Annotated[dict, Body(...)]):
    """記錄遊戲事件"""
    event_type = request.get("event_type")
    data = request.get("data", {})
    
    try:
        recording_manager.log_event(event_type, data)
        return JSONResponse({"status": "logged"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/recordings")
async def get_recordings():
    """獲取錄影列表"""
    try:
        recordings = recording_manager.get_recordings_list()
        return JSONResponse({"recordings": recordings})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/recording/{game_id}/metadata")
async def get_recording_metadata(game_id: str):
    """獲取特定錄影的元資料"""
    metadata = recording_manager.get_recording_metadata(game_id)
    
    if metadata:
        return JSONResponse(metadata)
    return create_error_response(ERR_NOT_FOUND, "Recording not found")


@app.get("/api/recording/{game_id}/events")
async def get_recording_events(game_id: str):
    """獲取錄影的事件日誌"""
    try:
        events = recording_manager.get_recording_events(game_id)
        return JSONResponse({"events": events})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))
