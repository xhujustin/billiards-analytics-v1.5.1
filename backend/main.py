import asyncio
import json
import os

# ✅ 性能監控
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Annotated, Any, Optional

import config
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
import cv2
import numpy as np
import uvicorn
from calibration.calibration import Calibrator
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from tracking.tracking_engine import PoolTracker
from streaming.mjpeg_streamer import DualMJPEGManager
from core.session_manager import session_manager, Role, SessionState
from core.error_codes import (
    ERR_INVALID_ARGUMENT, ERR_NOT_FOUND, ERR_FORBIDDEN, ERR_SESSION_EXPIRED,
    ERR_STREAM_UNAVAILABLE, ERR_INTERNAL, create_error_response
)
from core.performance_monitor import PerformanceMonitor
from calibration.aruco_detector import ArucoDetector
from calibration.projector_renderer import ProjectorRenderer, ProjectorMode
from calibration.projector_overlay import ProjectorOverlay

try:
    if hasattr(cv2, "setLogLevel") and hasattr(cv2, "LOG_LEVEL_ERROR"):
        cv2.setLogLevel(cv2.LOG_LEVEL_ERROR)
    elif hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass

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

# 註冊 API 路由
from api.replay_api import router as replay_router
app.include_router(replay_router)

from api.thumbnail_api import router as thumbnail_router
app.include_router(thumbnail_router)

from api.calibration_api import router as calibration_router
app.include_router(calibration_router)

from api.camera_api import router as camera_router
app.include_router(camera_router)

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

# 影像處理器 (降噪、亮度調整等)
from core.image_processor import ImageProcessor
image_processor: Optional[ImageProcessor] = None
try:
    image_processor = ImageProcessor()
    print(f"✅ Image Processor initialized (Denoise: {image_processor.denoise_enabled}, Method: {image_processor.denoise_method})")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize Image Processor: {e}")
    image_processor = None


# 全局攝像頭設備管理
camera_state: dict[str, Any] = {
    "selected_device_id": 0,  # 預設使用裝置 0
    "available_devices": [],  # 列出所有可用的攝像頭
    "current_cap": None,  # 當前的 cv2.VideoCapture 實例
    "needs_switch": False,  # 標記是否需要切換攝像頭
    "new_device_id": 0,  # 新的設備 ID
    "is_switching": False,  # 標記是否正在切換中
    "last_frame_time": 0.0,  # ✅ 追蹤最新畫面時間戳
    "last_good_backend": cv2.CAP_DSHOW,  # 上次成功的後端，重連優先
    "last_good_profile": None,  # 上次成功的解析度/FPS
    "reconnect_backoff_sec": 0.2,  # 重連回退秒數（動態）
}
system_state: dict[str, Any] = {
    "is_analyzing": False,  # 預設不開啟 YOLO，只送純影像
    "yolo_skip_frames": 2,  # ✅ 每 3 幀執行一次 YOLO（加速）
}

practice_tracking_state: dict[str, Any] = {
    "is_attempt_in_progress": False,
    "last_white_pos": None,
    "last_colors_pos": [],
    "last_target_pos": None,
    "last_cue_radius": 0.0,
    "last_target_radius": 0.0,
    "still_frames": 0,
    "attempt_frames": 0,
    "cue_missing_frames": 0,
    "target_missing_frames": 0,
    "cue_in_hole_frames": 0,
    "target_in_hole_frames": 0,
    "cue_was_in_hole": False,
    "target_was_in_hole": False,
    "start_motion_frames": 0,
    "cue_ball_potted": False,
    "target_ball_potted": False,
}

practice_runtime_state: dict[str, Any] = {
    "boost_enabled": False,
    "prev_yolo_skip_frames": 2,
    "prev_is_analyzing": False,
}

NORMAL_RUNTIME_FPS_CAP = 30


def _is_high_fps_mode_active() -> bool:
    practice_state = game_manager.get_practice_state()
    if practice_state and practice_state.get("is_active"):
        return True
    game_state = game_manager.get_game_state()
    if game_state and game_state.get("is_active"):
        return True
    return False


def _apply_runtime_fps_cap() -> None:
    if mjpeg_manager is None:
        return
    mjpeg_manager.set_max_fps(0 if _is_high_fps_mode_active() else NORMAL_RUNTIME_FPS_CAP)



# 線程池用於異步攝像頭切換（不阻塞 WebSocket）
executor = ThreadPoolExecutor(max_workers=6)  # ✅ 增加到 6 個工作線程

# MJPEG 串流管理器 - 簡單可靠的 HTTP 視頻流
try:
    mjpeg_manager = DualMJPEGManager(quality=70, max_fps=NORMAL_RUNTIME_FPS_CAP)
    print("✅ MJPEG Stream Manager initialized")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize MJPEG: {e}")
    mjpeg_manager = None

# 投影機獨立渲染器
try:
    projector_renderer = ProjectorRenderer()
    print("✅ Projector Renderer initialized")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize Projector Renderer: {e}")
    projector_renderer = None

# ArUco 檢測器
try:
    aruco_detector = ArucoDetector()
    print("✅ ArUco Detector initialized")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize ArUco Detector: {e}")
    aruco_detector = None

# 投影疊加器
try:
    projector_overlay = ProjectorOverlay()
    print("✅ Projector Overlay initialized")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize Projector Overlay: {e}")
    projector_overlay = None

# 校正狀態
calibration_state: dict[str, Any] = {
    "is_calibrating": False,
    "detected_corners": None,
    "corner_offsets": {
        "top-left": {"x": -300, "y": -300},
        "top-right": {"x": 300, "y": -300},
        "bottom-right": {"x": 300, "y": 300},
        "bottom-left": {"x": -300, "y": 300}
    }
}

# ✅ 啟動攝像頭並開始幀循環（用於 burn-in 串流）
camera_capture_thread = None
camera_running = threading.Event()
camera_thread_lock = threading.Lock()

# ✅ 全域效能監控器 (用於 API 查詢)
global_perf_monitor: Optional[PerformanceMonitor] = None

# 遊戲模式管理器
from tracking.game_manager import GameManager
from streaming.recording_manager import RecordingManager
import os

game_manager = GameManager()
_apply_runtime_fps_cap()
# 使用專案根目錄的 recordings 資料夾
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
recording_manager = RecordingManager(
    recordings_dir=os.path.join(project_root, "recordings"),
    db_path=os.path.join(os.path.dirname(__file__), "data", "recordings.db")
)


COLOR_CALIBRATION_MODES: dict[str, list[str]] = {
    "pool": ["Yellow", "Blue", "Red", "Purple", "Orange", "Green", "Brown", "Black", "White"],
    "snooker": ["Red", "Yellow", "Green", "Brown", "Blue", "Pink", "Black", "White"],
}


def _normalize_hsv_triplet(values: Any, field_name: str) -> list[int]:
    if not isinstance(values, list) or len(values) != 3:
        raise HTTPException(status_code=400, detail=f"{field_name} must be [H,S,V]")
    h = int(values[0])
    s = int(values[1])
    v = int(values[2])
    if h < 0 or h > 180 or s < 0 or s > 255 or v < 0 or v > 255:
        raise HTTPException(status_code=400, detail=f"{field_name} out of range")
    return [h, s, v]


color_calibration_state: dict[str, Any] = {
    "profile_id": None,
    "profile_name": None,
    "mode": None,
    "applied_at": None,
}

def _sanitize_color_mappings(mode: str, mappings: Any) -> dict[str, Any]:
    if not isinstance(mappings, dict):
        raise HTTPException(status_code=400, detail="mappings must be object")
    allowed = set(COLOR_CALIBRATION_MODES.get(mode, []))
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")

    cleaned: dict[str, Any] = {}
    for sys_color, cfg in mappings.items():
        if sys_color not in allowed:
            continue
        if not isinstance(cfg, dict):
            continue

        hsv_lower = cfg.get("hsv_lower")
        hsv_upper = cfg.get("hsv_upper")
        if hsv_lower is None or hsv_upper is None:
            continue

        lower = _normalize_hsv_triplet(hsv_lower, f"{sys_color}.hsv_lower")
        upper = _normalize_hsv_triplet(hsv_upper, f"{sys_color}.hsv_upper")
        cleaned[sys_color] = {
            "actual_label": str(cfg.get("actual_label", "")).strip(),
            "hsv_lower": lower,
            "hsv_upper": upper,
        }
    return cleaned
# 初始化校正 API 模組 (在所有變數定義後)
try:
    import api.calibration_api as calib_api
    import sys
    calib_api.init_calibration_api(sys.modules[__name__])
    print("✅ Calibration API initialized")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize Calibration API: {e}")

# Camera API initialization moved to after switch_camera_background definition


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
    consecutive_misses = 0
    for i in range(10):  # 最多檢查 10 個設備
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                devices.append({"id": i, "name": f"Camera {i}"})
                consecutive_misses = 0
            else:
                consecutive_misses += 1
            cap.release()
        else:
            consecutive_misses += 1

        # 連續 miss 代表已越過有效裝置範圍，提早停止避免 out-of-range 警告
        if consecutive_misses >= 3:
            break
    return devices


def open_camera(device_id: int):
    """開啟指定攝像頭：確保能持續讀取幀。"""
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
        camera_state["reconnect_backoff_sec"] = 0.2
        return cap_video

    # 先關閉舊設備（縮短等待避免切換阻塞）
    if camera_state["current_cap"] is not None:
        try:
            print("   Releasing previous camera...")
            camera_state["current_cap"].release()
            time.sleep(0.05)
        except Exception as e:
            print(f"   ⚠️  Could not release previous camera: {e}")

    default_profile = (config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS)
    cached_profile = camera_state.get("last_good_profile")
    cached_backend = camera_state.get("last_good_backend", cv2.CAP_DSHOW)

    # 優先嘗試上次成功配置，重連通常可在第一輪就成功
    resolutions = []
    for profile in [cached_profile, default_profile, (1920, 1080, 50), (1280, 720, 30), (1024, 576, 30), (640, 480, 30), (800, 600, 30)]:
        if profile and profile not in resolutions:
            resolutions.append(profile)

    backends = []
    for backend in [cached_backend, cv2.CAP_DSHOW]:
        if backend not in backends:
            backends.append(backend)

    cap: Optional[Any] = None
    for backend in backends:
        for width, height, fps in resolutions:
            cap_candidate: Optional[Any] = None
            try:
                print(f"Device {device_id}: trying backend={backend}, {width}x{height}@{fps}...", end=" ")
                cap_candidate = cv2.VideoCapture(device_id, backend)
                if not cap_candidate.isOpened():
                    print("Cannot open")
                    cap_candidate.release()
                    continue

                # 盡可能限制底層阻塞時間（後端不支援時忽略）
                try:
                    cap_candidate.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 600)
                    cap_candidate.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 400)
                except Exception:
                    pass

                # FOURCC 優先順序: YUYV (未壓縮) -> MJPEG (硬體壓縮) -> YUY2
                fourcc_attempts = [
                    ("YUYV", cv2.VideoWriter_fourcc(*"YUYV"), "未壓縮格式"),
                    ("MJPG", cv2.VideoWriter_fourcc(*"MJPG"), "MJPEG 壓縮"),
                    ("YUY2", cv2.VideoWriter_fourcc(*"YUY2"), "YUV 格式"),
                ]

                selected_format = None
                for format_name, fourcc, description in fourcc_attempts:
                    try:
                        cap_candidate.set(cv2.CAP_PROP_FOURCC, fourcc)
                        time.sleep(0.02)
                        test_ret, test_frame = cap_candidate.read()
                        if test_ret and test_frame is not None:
                            actual_fourcc = int(cap_candidate.get(cv2.CAP_PROP_FOURCC))
                            actual_format = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
                            selected_format = {
                                "requested": format_name,
                                "actual": actual_format,
                                "description": description,
                                "is_compressed": format_name == "MJPG",
                            }
                            print(f"   FOURCC: {actual_format} ({description})", end=" ")
                            break
                    except Exception:
                        continue

                if selected_format is None:
                    selected_format = {
                        "requested": "DEFAULT",
                        "actual": "UNKNOWN",
                        "description": "系統預設",
                        "is_compressed": True,
                    }
                    print("   FOURCC: DEFAULT", end=" ")

                camera_state["fourcc_info"] = selected_format

                cap_candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap_candidate.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap_candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap_candidate.set(cv2.CAP_PROP_FPS, fps)

                # 快速暖機驗證：縮短固定等待，降低重連延遲
                time.sleep(0.05)
                print("   Verifying frames...", end=" ")
                success_count = 0
                quick_frames = 8
                for _ in range(quick_frames):
                    ret, frame = cap_candidate.read()
                    if ret and frame is not None:
                        success_count += 1
                    time.sleep(0.003)

                if success_count < 3:
                    print(f"✗ Low success ({success_count}/{quick_frames})")
                    cap_candidate.release()
                    continue

                actual_width = int(cap_candidate.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap_candidate.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = cap_candidate.get(cv2.CAP_PROP_FPS)

                print(f"OK ({actual_width}x{actual_height}@{actual_fps}fps)")
                cap = cap_candidate
                camera_state["last_good_backend"] = backend
                camera_state["last_good_profile"] = (width, height, fps)
                break

            except Exception as exc:
                print(f"Exception: {exc}")
                if cap_candidate is not None:
                    try:
                        cap_candidate.release()
                    except Exception:
                        pass

        if cap is not None:
            break

    if cap is None:
        camera_state["current_cap"] = None
        print(f"CRITICAL: Failed to open camera device {device_id} after trying all backends and resolutions.")
        return None

    print(f"✅ Camera {device_id} opened successfully.")
    camera_state["reconnect_backoff_sec"] = 0.2
    camera_state["current_cap"] = cap
    camera_state["selected_device_id"] = device_id
    return cap
def reopen_camera_with_fallback(preferred_device_id: int) -> Optional[Any]:
    """
    重連策略：
    1) 先嘗試原本 device_id
    2) 再重新枚舉目前存在的相機並逐一嘗試（處理 USB 拔插後 id 改變）
    """
    candidate_ids: list[int] = [preferred_device_id]

    try:
        devices = enumerate_camera_devices()
        for dev in devices:
            dev_id = int(dev.get("id", -1))
            if dev_id >= 0 and dev_id not in candidate_ids:
                candidate_ids.append(dev_id)
    except Exception as e:
        print(f"⚠️ Camera re-enumeration failed: {e}")

    # 最後保底：嘗試常見低編號裝置
    for fallback_id in [0, 1, 2, 3]:
        if fallback_id not in candidate_ids:
            candidate_ids.append(fallback_id)

    for dev_id in candidate_ids:
        cap = open_camera(dev_id)
        if cap is not None:
            if dev_id != preferred_device_id:
                print(f"✅ Camera reconnected with fallback device id={dev_id} (preferred={preferred_device_id})")
            return cap

    return None

def safe_release_capture(cap: Optional[Any]) -> None:
    """安全釋放 VideoCapture，避免重複的 try/except。"""
    if cap is None:
        return
    try:
        cap.release()
    except Exception:
        pass


def read_frame_with_looped_video_source(cap: Any) -> tuple[bool, Optional[Any]]:
    """
    讀取一幀；若使用影片來源且到達結尾，嘗試回到第 0 幀再讀一次。
    """
    ret, frame = cap.read()

    if getattr(config, "VIDEO_SOURCE", "") and (not ret or frame is None):
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if getattr(config, "LOOP_VIDEO_SOURCE", True) and total_frames > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
        except Exception:
            pass

    return ret, frame

def switch_camera_background(device_id: int):
    """在後台線程中切換攝像頭，完成後設置 is_switching=False"""
    try:
        print(f"Background: Starting camera switch from {camera_state['selected_device_id']} to {device_id}")
        open_camera(device_id)
        print(f"Background: Camera switch to device {device_id} completed")
    except Exception as e:
        print(f"Background: Camera switch failed: {e}")
    finally:
        camera_state["is_switching"] = False


def ensure_camera_capture_started():
    """按需啟動攝像頭擷取執行緒，避免應用啟動時阻塞。"""
    global camera_capture_thread

    with camera_thread_lock:
        if camera_capture_thread is not None and camera_capture_thread.is_alive():
            return

        print("🚀 Lazy starting camera capture thread for burn-in stream...")
        camera_capture_thread = threading.Thread(target=camera_capture_loop, daemon=True)
        camera_capture_thread.start()
# ==================== API Initialization (Delayed) ====================
# 初始化相機 API 模組 (必須在 switch_camera_background 定義後)
try:
    import api.camera_api as cam_api
    import sys
    cam_api.init_camera_api(sys.modules[__name__])
    print("✅ Camera API initialized (Delayed)")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize Camera API: {e}")

# 初始化 Replay API (注入 recording_manager)
try:
    import api.replay_api as replay_api_module
    import sys
    replay_api_module.init_replay_api(sys.modules[__name__])
    print("✅ Replay API initialized (with RecordingManager)")
except Exception as e:
    print(f"⚠️  Warning: Failed to initialize Replay API: {e}")


def transform_route_segments_for_ar(data_packet: dict[str, Any]) -> list[dict[str, Any]]:
    """將 multi_plan 的分段路線轉成投影機座標。"""
    if calibrator is None or not calibrator.has_homography():
        return []

    multi_plan = data_packet.get("multi_plan")
    if not isinstance(multi_plan, dict):
        return []

    best_route = multi_plan.get("best_route")
    if not isinstance(best_route, dict):
        return []

    raw_segments = best_route.get("route_segments") or []
    if not isinstance(raw_segments, list):
        return []

    transformed_segments: list[dict[str, Any]] = []
    for segment in raw_segments:
        if not isinstance(segment, dict):
            continue

        raw_points = segment.get("points") or []
        if not isinstance(raw_points, list) or len(raw_points) <= 1:
            continue

        points = calibrator.transform_points(raw_points)
        if not points or len(points) <= 1:
            continue

        transformed_segments.append(
            {
                "type": segment.get("type", "unknown"),
                "points": points,
                "color": segment.get("color"),
            }
        )

    return transformed_segments


def _select_route_in_plan(plan: dict[str, Any], route_id: str) -> dict[str, Any]:
    routes = plan.get("routes")
    if not isinstance(routes, list):
        return plan

    selected_route = next(
        (route for route in routes if isinstance(route, dict) and route.get("id") == route_id),
        None,
    )
    if selected_route is None:
        return plan

    return {**plan, "best_route": selected_route, "selected_route_id": route_id}


def _sanitize_stroke_override(raw: Any) -> dict[str, str]:
    raw = raw if isinstance(raw, dict) else {}
    tip = str(raw.get("tip", "center")).strip().lower()
    power = str(raw.get("power", "medium")).strip().lower()
    if tip not in {"center", "top", "draw", "low", "left", "right", "top_left", "top_right", "draw_left", "draw_right"}:
        tip = "center"
    if power not in {"low", "medium", "medium_high", "high"}:
        power = "medium"
    return {"tip": tip, "power": power}


def _sanitize_pattern_layout(raw: Any) -> dict[str, Any] | None:
    """清理球型練習前端傳入的固定球位與投影路線。
    
    支援兩種座標空間：
    - 'relative': 0~1 相對座標（新版，後端負責校正轉換）
    - 'pixel': 投影機像素座標 0~1920/1080（舊版就地相容）
    """
    if not isinstance(raw, dict):
        return None

    coordinate_space = str(raw.get("coordinate_space", "pixel")).strip().lower()
    is_relative = (coordinate_space == "relative")

    def point_relative(raw_point: Any) -> list[float] | None:
        """0~1 相對座標驗證與別釜，保持浮點數（後端再轉換）。"""
        if not isinstance(raw_point, (list, tuple)) or len(raw_point) < 2:
            return None
        try:
            x = max(0.0, min(1.0, float(raw_point[0])))
            y = max(0.0, min(1.0, float(raw_point[1])))
            return [x, y]
        except (TypeError, ValueError):
            return None

    def point_pixel(raw_point: Any) -> list[int] | None:
        """0~1920/1080 像素座標驗證與別釜。"""
        if not isinstance(raw_point, (list, tuple)) or len(raw_point) < 2:
            return None
        try:
            x = max(0, min(1920, int(round(float(raw_point[0])))))
            y = max(0, min(1080, int(round(float(raw_point[1])))))
            return [x, y]
        except (TypeError, ValueError):
            return None

    point = point_relative if is_relative else point_pixel

    balls: list[dict[str, Any]] = []
    for raw_ball in raw.get("balls", []):
        if not isinstance(raw_ball, dict):
            continue
        ball_point = point([raw_ball.get("x"), raw_ball.get("y")])
        if not ball_point:
            continue
        ball_type = str(raw_ball.get("type", "object")).strip()
        if ball_type not in {"cue", "object", "object2"}:
            ball_type = "object"
        balls.append(
            {
                "x": ball_point[0],
                "y": ball_point[1],
                "r": max(8, min(60, int(raw_ball.get("r", 24) or 24))),
                "type": ball_type,
                "label": str(raw_ball.get("label", ""))[:20],
            }
        )

    route_segments: list[dict[str, Any]] = []
    allowed_segment_types = {
        "cue_to_contact",
        "object_to_pocket",
        "object_to_rail",
        "combo_transfer",
        "cue_after_contact",
        "object_after_contact",
    }
    for raw_segment in raw.get("route_segments", []):
        if not isinstance(raw_segment, dict):
            continue
        segment_type = str(raw_segment.get("type", "")).strip()
        if segment_type not in allowed_segment_types:
            continue
        segment_points = [p for p in (point(item) for item in raw_segment.get("points", [])) if p]
        if len(segment_points) < 2:
            continue
        route_segments.append({"type": segment_type, "points": segment_points[:6]})

    landing = point(raw.get("cue_landing_point"))
    ghost_balls: list[dict[str, Any]] = []
    for raw_ghost in raw.get("ghost_balls", []):
        if not isinstance(raw_ghost, dict):
            continue
        ghost_point = point([raw_ghost.get("x"), raw_ghost.get("y")])
        if not ghost_point:
            continue
        if is_relative:
            ghost_radius = 24
        else:
            ghost_radius = max(8, min(80, int(round(float(raw_ghost.get("r", 24) or 24)))))
        ghost_balls.append({"x": ghost_point[0], "y": ghost_point[1], "r": ghost_radius})
    stroke = _sanitize_stroke_override(raw.get("stroke"))
    raw_guides = raw.get("guide_options") if isinstance(raw.get("guide_options"), dict) else {}
    guide_options = {
        "cue_laser_enabled": bool(raw_guides.get("cue_laser_enabled", True)),
        "ball_guides_enabled": bool(raw_guides.get("ball_guides_enabled", True)),
    }

    return {
        "balls": balls[:4],
        "route_segments": route_segments[:6],
        "cue_landing_point": landing,
        "ghost_balls": ghost_balls[:3],
        "stroke": stroke,
        "guide_options": guide_options,
        "coordinate_space": "relative" if is_relative else "pixel",
        "projector_space": {"width": 1920, "height": 1080},
    }


def _apply_pattern_practice_projection(pattern_layout: dict[str, Any] | None):
    """將球型練習設定同步到投影機。
    
    前端傳相對座標(0~1)時，先映射到相機的 table_roi，再走 homography。
    這樣球型練習投影會與一般練習 AR 使用同一套校正矩陣。
    """
    if not pattern_layout:
        if tracker is not None and hasattr(tracker, "set_manual_projected_artifacts"):
            tracker.set_manual_projected_artifacts(None)
        if projector_renderer is not None:
            projector_renderer.update_ar_data(
                {
                    "setup_balls": [],
                    "cue_landing_point": None,
                    "cue_laser_lines": [],
                }
            )
        return

    if projector_renderer is None:
        return

    # 座標轉換函數：相對(0~1) → 相機桌面座標 → homography → 投影機絕對像素座標
    is_relative = (pattern_layout.get("coordinate_space") == "relative")
    guide_options = pattern_layout.get("guide_options") if isinstance(pattern_layout.get("guide_options"), dict) else {}
    ball_guides_enabled = bool(guide_options.get("ball_guides_enabled", True))

    DEFAULT_BOUNDS = {"x": 0, "y": 0, "width": 1920, "height": 1080}

    def get_table_roi() -> list[int] | None:
        data_packet = latest_analysis_data.get("data")
        if isinstance(data_packet, dict):
            roi = data_packet.get("table_roi")
            if isinstance(roi, (list, tuple)) and len(roi) >= 4:
                try:
                    return [int(float(roi[0])), int(float(roi[1])), int(float(roi[2])), int(float(roi[3]))]
                except (TypeError, ValueError):
                    pass

        if tracker is not None:
            roi = getattr(tracker, "table_roi", None)
            if isinstance(roi, (list, tuple)) and len(roi) >= 4:
                try:
                    return [int(float(roi[0])), int(float(roi[1])), int(float(roi[2])), int(float(roi[3]))]
                except (TypeError, ValueError):
                    pass
        return None

    table_roi = get_table_roi()

    def get_camera_ball_radius() -> int:
        if table_roi:
            _, _, tw, _ = table_roi
            return max(8, min(36, int(round(tw * 0.026 / 2.0))))
        return 14

    def get_projector_ball_radius() -> int:
        camera_radius = get_camera_ball_radius()
        if calibrator is not None and calibrator.has_homography() and table_roi:
            tx, ty, tw, th = table_roi
            cx = tx + tw * 0.5
            cy = ty + th * 0.5
            transformed = calibrator.transform_points(
                [
                    [cx, cy],
                    [cx + camera_radius, cy],
                    [cx, cy + camera_radius],
                ]
            )
            if transformed and len(transformed) == 3:
                px, py = transformed[0]
                rx = ((transformed[1][0] - px) ** 2 + (transformed[1][1] - py) ** 2) ** 0.5
                ry = ((transformed[2][0] - px) ** 2 + (transformed[2][1] - py) ** 2) ** 0.5
                projected_radius = int(round((rx + ry) / 2.0))
                return max(14, min(56, projected_radius))

        bounds = DEFAULT_BOUNDS
        if calibrator is not None and calibrator.projection_bounds:
            bounds = calibrator.projection_bounds
        return max(14, min(56, int(round(float(bounds["width"]) * 0.026 / 2.0))))

    def get_camera_boundary_inset() -> int:
        return max(10, int(round(get_camera_ball_radius() * 1.45)))

    def get_projector_boundary_inset() -> int:
        return max(16, int(round(get_projector_ball_radius() * 1.45)))

    def to_proj(rx: float, ry: float) -> list[int]:
        """0~1 相對座標 → 投影機絕對座標（優先套用相機校正）。"""
        table_rx = max(0.0, min(1.0, rx))
        table_ry = max(0.0, min(1.0, ry))
        if calibrator is not None and calibrator.has_homography() and table_roi:
            tx, ty, tw, th = table_roi
            inset = get_camera_boundary_inset()
            inner_w = max(1, tw - inset * 2)
            inner_h = max(1, th - inset * 2)
            camera_point = [[tx + inset + table_rx * inner_w, ty + inset + table_ry * inner_h]]
            transformed = calibrator.transform_points(camera_point)
            if transformed:
                return [int(transformed[0][0]), int(transformed[0][1])]

        bounds = DEFAULT_BOUNDS
        if calibrator is not None and calibrator.projection_bounds:
            bounds = calibrator.projection_bounds
        inset = get_projector_boundary_inset()
        inner_w = max(1, int(bounds["width"]) - inset * 2)
        inner_h = max(1, int(bounds["height"]) - inset * 2)
        x = int(bounds["x"] + inset + table_rx * inner_w)
        y = int(bounds["y"] + inset + table_ry * inner_h)
        return [x, y]

    def to_camera(rx: float, ry: float) -> list[int] | None:
        """0~1 相對座標 → 相機全圖座標，供 YOLO 偽影過濾使用。"""
        if not table_roi:
            return None
        table_rx = max(0.0, min(1.0, rx))
        table_ry = max(0.0, min(1.0, ry))
        tx, ty, tw, th = table_roi
        inset = get_camera_boundary_inset()
        inner_w = max(1, tw - inset * 2)
        inner_h = max(1, th - inset * 2)
        return [int(tx + inset + table_rx * inner_w), int(ty + inset + table_ry * inner_h)]

    def convert_point(pt: list) -> list[int]:
        """依座標空間轉換單點。"""
        if is_relative:
            return to_proj(float(pt[0]), float(pt[1]))
        # 舊版像素座標，直接使用
        return [int(pt[0]), int(pt[1])]

    def convert_camera_point(pt: list) -> list[int] | None:
        if is_relative:
            return to_camera(float(pt[0]), float(pt[1]))
        return [int(pt[0]), int(pt[1])]

    # 轉換球位
    projector_ball_radius = get_projector_ball_radius()
    proj_balls: list[dict[str, Any]] = []
    for ball in pattern_layout.get("balls", []):
        px, py = convert_point([ball["x"], ball["y"]])
        proj_balls.append({
            "x": px,
            "y": py,
            "r": projector_ball_radius,
            "type": ball.get("type", "object"),
            "label": ball.get("label", ""),
        })

    # 轉換路線線段
    proj_segments: list[dict[str, Any]] = []
    camera_artifacts: dict[str, list[Any]] = {"segments": [], "points": [], "protected_points": []}
    if ball_guides_enabled:
        for seg in pattern_layout.get("route_segments", []):
            converted_pts = [convert_point(p) for p in seg.get("points", [])]
            if len(converted_pts) >= 2:
                proj_segments.append({"type": seg.get("type", ""), "points": converted_pts})

            camera_pts = [p for p in (convert_camera_point(p) for p in seg.get("points", [])) if p]
            if len(camera_pts) >= 2:
                seg_type = str(seg.get("type", ""))
                for idx in range(len(camera_pts) - 1):
                    camera_artifacts["segments"].append((seg_type, tuple(camera_pts[idx]), tuple(camera_pts[idx + 1])))

    proj_ghost_balls: list[dict[str, Any]] = []
    if ball_guides_enabled:
        for ghost in pattern_layout.get("ghost_balls", []):
            if not isinstance(ghost, dict):
                continue
            gx, gy = convert_point([ghost.get("x"), ghost.get("y")])
            proj_ghost_balls.append({"x": gx, "y": gy, "r": projector_ball_radius})
            camera_ghost = convert_camera_point([ghost.get("x"), ghost.get("y")])
            if camera_ghost:
                camera_artifacts["points"].append(("ghost_ball", tuple(camera_ghost)))

    # 轉換母球落點
    raw_landing = pattern_layout.get("cue_landing_point")
    proj_landing = convert_point(raw_landing) if raw_landing and ball_guides_enabled else None

    for ball in pattern_layout.get("balls", []):
        if not isinstance(ball, dict):
            continue
        camera_ball = convert_camera_point([ball.get("x"), ball.get("y")])
        if camera_ball:
            camera_artifacts["protected_points"].append((str(ball.get("type", "ball")), tuple(camera_ball)))

    if tracker is not None and hasattr(tracker, "set_manual_projected_artifacts"):
        tracker.set_manual_projected_artifacts(camera_artifacts)

    projector_renderer.set_mode(ProjectorMode.PRACTICE)
    projector_renderer.update_ar_data(
        {
            "trajectories": [],
            "route_segments": proj_segments,
            "balls": [],
            "aim_lines": [],
            "ghost_balls": proj_ghost_balls,
            "setup_balls": proj_balls,
            "cue_landing_point": proj_landing,
            "cue_laser_lines": [],
        }
    )


def set_route_planner_runtime(enabled: bool, rule_profile: str = "practice"):
    """切換即時多球規劃；關閉時同步清掉舊 metadata 與 AR 投影路線。"""
    if tracker is not None:
        tracker.set_route_planner_enabled(enabled)
        tracker.set_route_rule_profile(rule_profile)
        if not enabled:
            tracker.set_selected_route_id(None)
            if hasattr(tracker, "set_route_stroke_override"):
                tracker.set_route_stroke_override(None)

    if not enabled:
        if tracker is not None and hasattr(tracker, "set_manual_projected_artifacts"):
            tracker.set_manual_projected_artifacts(None)
        latest_analysis_data["multi_plan"] = None
        latest_analysis_data["planner_error"] = None
        latest_analysis_data["ar_route_segments"] = []

        data_packet = latest_analysis_data.get("data")
        if isinstance(data_packet, dict):
            data_packet["multi_plan"] = None

        if projector_renderer is not None:
            projector_renderer.update_ar_data(
                {
                    "route_segments": [],
                    "trajectories": [],
                    "aim_lines": [],
                    "ghost_balls": [],
                    "setup_balls": [],
                    "cue_landing_point": None,
                    "cue_laser_lines": [],
                }
            )


try:
    import api.calibration_api as calib_api
    calib_api.set_route_planner_runtime = set_route_planner_runtime
except Exception:
    pass



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
    cap = reopen_camera_with_fallback(camera_state["selected_device_id"])
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
            # 清空相機緩衝區 - 丟棄舊幀以降低延遲
            # 根據曝光時間動態調整策略
            exposure = cap.get(cv2.CAP_PROP_EXPOSURE)
            
            # 曝光時間越長,清空次數越少 (避免額外延遲)
            if exposure >= 0:  # 自動曝光或高曝光
                grab_count = 1  # 只清空1幀
            elif exposure >= -5:  # 中等曝光
                grab_count = 2
            else:  # 低曝光 (快速)
                grab_count = 3
            
            for _ in range(grab_count):
                cap.grab()  # grab() 比 read() 快,只抓取不解碼

            # 讀取最新的幀（影片來源時自動處理迴圈）
            ret, frame = read_frame_with_looped_video_source(cap)

            if not ret or frame is None:
                # ✅ 處理切換狀態：如果是正在切換，則等待切換完成，不要嘗試重開舊相機
                if camera_state.get("is_switching", False):
                    # print("🔄 Camera loop: Switching in progress, waiting...") # 減少 log
                    time.sleep(0.1)
                    # 如果切換完成了，且有新的 cap，就更新
                    if not camera_state.get("is_switching", False):
                        if camera_state["current_cap"] is not None:
                            cap = camera_state["current_cap"]
                            print(f"✅ Camera loop: Picked up new camera {camera_state['selected_device_id']}")
                    continue

                print("⚠️ Failed to read frame, attempting to reopen camera...")
                safe_release_capture(cap)

                backoff = float(camera_state.get("reconnect_backoff_sec", 0.2))
                time.sleep(backoff)
                cap = reopen_camera_with_fallback(camera_state["selected_device_id"])
                if cap is None:
                    print("❌ Failed to reopen camera")
                    camera_state["reconnect_backoff_sec"] = min(backoff * 1.8, 2.5)
                    continue

                camera_state["reconnect_backoff_sec"] = 0.2
                continue

            frame_count += 1
            camera_state["last_frame_time"] = time.time()
            
            # 延遲診斷: 記錄相機讀取時間
            camera_read_time = time.time() - frame_start
            
            # ==================== 統一影像處理管線 (方案 A) ====================
            # 在此處理後,YOLO 和前端串流都使用相同的處理後影像
            process_start = time.time()
            if image_processor:
                frame = image_processor.process_frame(frame)
            process_time = time.time() - process_start
            # ================================================================
            
            # 每120幀顯示一次延遲診斷
            # if frame_count % 120 == 0:
            #     # 獲取相機實際參數
            #     actual_fps = cap.get(cv2.CAP_PROP_FPS)
            #     actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            #     actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            #     print(f" Latency: Camera={camera_read_time*1000:.1f}ms, Process={process_time*1000:.1f}ms | "
            #           f"Actual: {actual_width}x{actual_height}@{actual_fps:.1f}fps")

            # ✅ 優化 1: ThreadPool 非阻塞 YOLO 推論
            if system_state["is_analyzing"] and tracker is not None:
                # ✅ 獲取 YOLO 推論結果
                if yolo_future and yolo_future.done():
                    try:
                        processed_frame, data = yolo_future.result(timeout=0)
                        cached_overlay = processed_frame.copy()
                        latest_analysis_data["data"] = data
                        
                        # AR 座標轉換與投影機資料同步
                        ar_paths = []
                        ar_route_segments = []
                        ar_balls = []
                        ar_aim_lines = []
                        ar_ghost_balls = []
                        ar_cue_laser_lines = []
                        
                        if calibrator is not None and calibrator.has_homography():
                            try:
                                # 1. 優先轉換新版多球分段路線；沒有時才使用舊版單一路徑。
                                ar_route_segments = transform_route_segments_for_ar(data)
                                if not ar_route_segments and data.get("prediction"):
                                    raw_paths = data["prediction"]["paths"]
                                    if raw_paths:
                                        ar_paths = calibrator.transform_points(raw_paths)
                                
                                # 2. 轉換球位 (含母球，使用中心點座標)
                                white_b = data.get("white_ball")
                                if white_b:
                                    cx_w = white_b[0] + white_b[2] // 2
                                    cy_w = white_b[1] + white_b[3] // 2
                                    pt_w = calibrator.transform_points([[cx_w, cy_w]])
                                    if pt_w:
                                        ar_balls.append({
                                            "x": pt_w[0][0], "y": pt_w[0][1],
                                            "type": "cue", "number": 0
                                        })
                                
                                for ball in data.get("balls", []):
                                    cx = ball["x"] + ball["w"] // 2
                                    cy = ball["y"] + ball["h"] // 2
                                    pt = calibrator.transform_points([[cx, cy]])
                                    if pt:
                                        ar_balls.append({
                                            "x": pt[0][0], "y": pt[0][1],
                                            "type": "solid",
                                            "number": ball.get("number")
                                        })

                                cue_laser_line = data.get("cue_laser_line")
                                if isinstance(cue_laser_line, list) and len(cue_laser_line) >= 2:
                                    pts = calibrator.transform_points(cue_laser_line[:2])
                                    if pts and len(pts) == 2:
                                        ar_cue_laser_lines.append({"points": pts})
                                    if len(cue_laser_line) >= 4:
                                        reverse_pts = calibrator.transform_points(cue_laser_line[2:4])
                                        if reverse_pts and len(reverse_pts) == 2:
                                            ar_cue_laser_lines.append({"points": reverse_pts})
                                        
                                # 3. 轉換瞄準輔助線與幽靈球
                                if "aim_assist" in data and data["aim_assist"]:
                                    aim = data["aim_assist"]
                                    if "cue_to_target" in aim:
                                        pts = calibrator.transform_points(aim["cue_to_target"])
                                        if pts and len(pts) == 2:
                                            ar_aim_lines.append({"start": pts[0], "end": pts[1], "type": "cue_to_target"})
                                    if "target_to_hole" in aim:
                                        pts = calibrator.transform_points(aim["target_to_hole"])
                                        if pts and len(pts) == 2:
                                            ar_aim_lines.append({"start": pts[0], "end": pts[1], "type": "target_to_hole"})
                                    if "separation_line" in aim and aim["separation_line"]:
                                        pts = calibrator.transform_points(aim["separation_line"])
                                        if pts and len(pts) == 2:
                                            ar_aim_lines.append({"start": pts[0], "end": pts[1], "type": "separation_line"})
                                    if "ghost_ball" in aim:
                                        gb = aim["ghost_ball"]
                                        pts = calibrator.transform_points([[gb["cx"], gb["cy"]]])
                                        if pts:
                                            # 對投影機來說，幽靈球的繪製半徑可以視尺寸調整
                                            ar_ghost_balls.append({"x": pts[0][0], "y": pts[0][1], "r": gb["r"]})

                                if not ar_ghost_balls and ar_route_segments:
                                    cue_segment = next(
                                        (
                                            segment
                                            for segment in ar_route_segments
                                            if segment.get("type") == "cue_to_contact"
                                            and len(segment.get("points", [])) >= 2
                                        ),
                                        None,
                                    )
                                    if cue_segment:
                                        ghost_center = cue_segment["points"][-1]
                                        ghost_radius = 18
                                        if white_b:
                                            ghost_radius = max(8, int(min(white_b[2], white_b[3]) / 2))
                                        ar_ghost_balls.append(
                                            {
                                                "x": int(ghost_center[0]),
                                                "y": int(ghost_center[1]),
                                                "r": ghost_radius,
                                            }
                                        )
                            except Exception as e:
                                print(f"⚠️ AR transform error: {e}")
                                
                        last_ar_paths = ar_paths
                        
                        # 更新投影機追蹤資料；球型練習使用手動設定的固定投影，不被相機迴圈覆蓋。
                        p_state_for_projector = game_manager.get_practice_state()
                        pattern_projection_active = (
                            p_state_for_projector
                            and p_state_for_projector.get("is_active")
                            and p_state_for_projector.get("mode") == "practice_pattern"
                            and p_state_for_projector.get("pattern_layout")
                        )
                        cue_laser_projection_enabled = False
                        if pattern_projection_active:
                            active_layout = p_state_for_projector.get("pattern_layout")
                            active_guides = active_layout.get("guide_options", {}) if isinstance(active_layout, dict) else {}
                            cue_laser_projection_enabled = bool(active_guides.get("cue_laser_enabled", True))
                        elif p_state_for_projector and p_state_for_projector.get("is_active"):
                            active_guides = p_state_for_projector.get("guide_options", {})
                            active_guides = active_guides if isinstance(active_guides, dict) else {}
                            cue_laser_projection_enabled = bool(active_guides.get("cue_laser_enabled", True))
                        if projector_renderer is not None and not pattern_projection_active:
                            projector_renderer.update_ar_data({
                                "trajectories": [ar_paths] if ar_paths and not ar_route_segments else [],
                                "route_segments": ar_route_segments,
                                "balls": ar_balls,
                                "aim_lines": ar_aim_lines,
                                "ghost_balls": ar_ghost_balls,
                                "setup_balls": [],
                                "cue_landing_point": None,
                                "cue_laser_lines": ar_cue_laser_lines if cue_laser_projection_enabled else [],
                                "allow_legacy_aim_lines": False,
                                "allow_legacy_trajectories": False
                            })
                        elif projector_renderer is not None and pattern_projection_active:
                            projector_renderer.update_ar_data({
                                "cue_laser_lines": ar_cue_laser_lines if cue_laser_projection_enabled else [],
                                "allow_legacy_aim_lines": False,
                                "allow_legacy_trajectories": False
                            })
                        
                        # --- 單球練習狀態追蹤自動化 ---
                        try:
                            p_state = game_manager.get_practice_state()
                            if p_state and p_state.get("is_active") and p_state.get("mode") == "practice_single":
                                import math

                                movement_threshold = 3.0
                                tracking_match_radius = 80.0
                                hole_radius = 52.0  # 由你的洞口參數調整
                                hole_inner_margin = 4.0
                                missing_confirm_frames = 3
                                in_hole_confirm_frames = 2

                                current_white = data.get("white_ball")
                                current_balls = data.get("balls", [])
                                holes = data.get("holes", []) or []

                                white_pos = None
                                white_radius = 0.0
                                if current_white:
                                    white_pos = (
                                        current_white[0] + current_white[2] // 2,
                                        current_white[1] + current_white[3] // 2,
                                    )
                                    white_radius = max(1.0, min(current_white[2], current_white[3]) / 2.0)

                                current_colors = [
                                    {
                                        "pos": (b["x"] + b["w"] // 2, b["y"] + b["h"] // 2),
                                        "r": max(1.0, min(b["w"], b["h"]) / 2.0),
                                    }
                                    for b in current_balls
                                ]
                                current_colors_pos = [c["pos"] for c in current_colors]

                                def dist(a, b):
                                    return math.hypot(a[0] - b[0], a[1] - b[1])

                                def fully_in_hole(ball_pos, ball_radius):
                                    if ball_pos is None or ball_radius <= 0 or not holes:
                                        return False
                                    for hole in holes:
                                        effective = hole_radius - ball_radius - hole_inner_margin
                                        if effective > 0 and dist(ball_pos, (hole[0], hole[1])) <= effective:
                                            return True
                                    return False

                                def near_hole(ball_pos):
                                    if ball_pos is None or not holes:
                                        return False
                                    return any(
                                        dist(ball_pos, (hole[0], hole[1])) <= (hole_radius + 8.0)
                                        for hole in holes
                                    )

                                white_moved = False
                                if white_pos and practice_tracking_state["last_white_pos"]:
                                    white_moved = dist(white_pos, practice_tracking_state["last_white_pos"]) > movement_threshold

                                color_moved = False
                                if practice_tracking_state["last_colors_pos"] and current_colors_pos:
                                    for pos in current_colors_pos:
                                        nearest_prev = min(
                                            dist(pos, prev) for prev in practice_tracking_state["last_colors_pos"]
                                        )
                                        if nearest_prev > movement_threshold:
                                            color_moved = True
                                            break
                                color_disappeared = (
                                    len(practice_tracking_state["last_colors_pos"]) > 0
                                    and len(current_colors_pos) < len(practice_tracking_state["last_colors_pos"])
                                )

                                # 放寬啟動條件：子球移動或短暫消失都可視為有碰撞
                                if white_moved and (color_moved or color_disappeared):
                                    practice_tracking_state["start_motion_frames"] += 1
                                else:
                                    practice_tracking_state["start_motion_frames"] = 0

                                if (
                                    not practice_tracking_state["is_attempt_in_progress"]
                                    and practice_tracking_state["start_motion_frames"] >= 1
                                    and white_pos
                                    and (current_colors or practice_tracking_state["last_target_pos"])
                                ):
                                    if current_colors:
                                        target = min(current_colors, key=lambda c: dist(c["pos"], white_pos))
                                        target_pos = target["pos"]
                                        target_r = target["r"]
                                    else:
                                        target_pos = practice_tracking_state["last_target_pos"]
                                        target_r = practice_tracking_state["last_target_radius"]
                                    practice_tracking_state["is_attempt_in_progress"] = True
                                    practice_tracking_state["still_frames"] = 0
                                    practice_tracking_state["attempt_frames"] = 0
                                    practice_tracking_state["cue_missing_frames"] = 0
                                    practice_tracking_state["target_missing_frames"] = 0
                                    practice_tracking_state["cue_in_hole_frames"] = 0
                                    practice_tracking_state["target_in_hole_frames"] = 0
                                    practice_tracking_state["cue_was_in_hole"] = False
                                    practice_tracking_state["target_was_in_hole"] = False
                                    practice_tracking_state["cue_ball_potted"] = False
                                    practice_tracking_state["target_ball_potted"] = False
                                    practice_tracking_state["start_motion_frames"] = 0
                                    practice_tracking_state["last_target_pos"] = target_pos
                                    practice_tracking_state["last_target_radius"] = target_r
                                    practice_tracking_state["last_cue_radius"] = white_radius
                                    print("🎯 Practice Auto-Detection: Attempt Started")

                                if practice_tracking_state["is_attempt_in_progress"]:
                                    tracked_target = None
                                    tracked_target_radius = practice_tracking_state["last_target_radius"]
                                    last_target_pos = practice_tracking_state["last_target_pos"]

                                    if last_target_pos and current_colors:
                                        candidate = min(current_colors, key=lambda c: dist(c["pos"], last_target_pos))
                                        if dist(candidate["pos"], last_target_pos) <= tracking_match_radius:
                                            tracked_target = candidate["pos"]
                                            tracked_target_radius = candidate["r"]

                                    target_moved = False
                                    any_moved = white_moved
                                    if tracked_target and last_target_pos:
                                        target_moved = dist(tracked_target, last_target_pos) > movement_threshold
                                        any_moved = any_moved or target_moved

                                    if not any_moved:
                                        practice_tracking_state["still_frames"] += 1
                                    else:
                                        practice_tracking_state["still_frames"] = 0

                                    # 子球：完全進洞 or 近洞後連續消失
                                    if tracked_target:
                                        practice_tracking_state["last_target_pos"] = tracked_target
                                        practice_tracking_state["last_target_radius"] = tracked_target_radius
                                        if fully_in_hole(tracked_target, tracked_target_radius):
                                            practice_tracking_state["target_in_hole_frames"] += 1
                                            practice_tracking_state["target_was_in_hole"] = True
                                        else:
                                            practice_tracking_state["target_in_hole_frames"] = 0
                                        practice_tracking_state["target_missing_frames"] = 0
                                    else:
                                        practice_tracking_state["target_missing_frames"] += 1
                                        last_pos = practice_tracking_state["last_target_pos"]
                                        if last_pos and near_hole(last_pos):
                                            practice_tracking_state["target_was_in_hole"] = True

                                    if (
                                        practice_tracking_state["target_in_hole_frames"] >= in_hole_confirm_frames
                                        or (
                                            practice_tracking_state["target_missing_frames"] >= missing_confirm_frames
                                            and practice_tracking_state["target_was_in_hole"]
                                        )
                                    ):
                                        practice_tracking_state["target_ball_potted"] = True

                                    # 母球：完全進洞 or 近洞後連續消失（犯規）
                                    if white_pos:
                                        practice_tracking_state["last_cue_radius"] = white_radius
                                        if fully_in_hole(white_pos, white_radius):
                                            practice_tracking_state["cue_in_hole_frames"] += 1
                                            practice_tracking_state["cue_was_in_hole"] = True
                                        else:
                                            practice_tracking_state["cue_in_hole_frames"] = 0
                                        practice_tracking_state["cue_missing_frames"] = 0
                                    else:
                                        practice_tracking_state["cue_missing_frames"] += 1
                                        last_white = practice_tracking_state["last_white_pos"]
                                        if last_white and near_hole(last_white):
                                            practice_tracking_state["cue_was_in_hole"] = True

                                    if (
                                        practice_tracking_state["cue_in_hole_frames"] >= in_hole_confirm_frames
                                        or (
                                            practice_tracking_state["cue_missing_frames"] >= missing_confirm_frames
                                            and practice_tracking_state["cue_was_in_hole"]
                                        )
                                    ):
                                        practice_tracking_state["cue_ball_potted"] = True

                                    practice_tracking_state["attempt_frames"] += 1
                                    if (
                                        practice_tracking_state["still_frames"] >= 8
                                        or practice_tracking_state["attempt_frames"] >= 180
                                    ):
                                        # 分開規則：子球進且母球不進才成功
                                        success = (
                                            practice_tracking_state["target_ball_potted"]
                                            and not practice_tracking_state["cue_ball_potted"]
                                        )
                                        target_potted = practice_tracking_state["target_ball_potted"]
                                        cue_potted = practice_tracking_state["cue_ball_potted"]
                                        game_manager.record_practice_attempt(success)
                                        print(
                                            f"🎯 Practice Auto-Detection: Attempt Ended, "
                                            f"success={success}, target_potted={target_potted}, cue_potted={cue_potted}"
                                        )

                                        practice_tracking_state["is_attempt_in_progress"] = False
                                        practice_tracking_state["still_frames"] = 0
                                        practice_tracking_state["attempt_frames"] = 0
                                        practice_tracking_state["cue_missing_frames"] = 0
                                        practice_tracking_state["target_missing_frames"] = 0
                                        practice_tracking_state["cue_in_hole_frames"] = 0
                                        practice_tracking_state["target_in_hole_frames"] = 0
                                        practice_tracking_state["cue_was_in_hole"] = False
                                        practice_tracking_state["target_was_in_hole"] = False
                                        practice_tracking_state["cue_ball_potted"] = False
                                        practice_tracking_state["target_ball_potted"] = False
                                        practice_tracking_state["last_target_pos"] = None

                                practice_tracking_state["last_white_pos"] = white_pos
                                practice_tracking_state["last_colors_pos"] = current_colors_pos
                        except Exception as e:
                            print(f"⚠️ Practice tracking error: {e}")
                        # -------------------------
                        
                        # 更新低頻分析數據
                        latest_analysis_data["data"] = data  # ✅ 修正: 使用 data 而非 data_packet
                        latest_analysis_data["ar_paths"] = ar_paths
                        latest_analysis_data["ar_route_segments"] = ar_route_segments
                        latest_analysis_data["multi_plan"] = data.get("multi_plan")
                        latest_analysis_data["planner_error"] = data.get("multi_plan", {}).get("error") if isinstance(data.get("multi_plan"), dict) else None
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

                        # 投影流：使用獨立渲染器 (1920×1080)
                        if projector_renderer is not None:
                            projector_frame = projector_renderer.render()
                            mjpeg_manager.update_projector(projector_frame)
                    except Exception as e:
                        print(f"⚠️ MJPEG frame update error: {e}")
            elif mjpeg_manager is not None:
                # 未啟用訂閱者檢查,總是編碼
                try:
                    monitor_frame = cv2.resize(display_frame, (1280, 720))
                    mjpeg_manager.update_monitor(monitor_frame)
                    
                    # 投影流：使用獨立渲染器
                    if projector_renderer is not None:
                        projector_frame = projector_renderer.render()
                        mjpeg_manager.update_projector(projector_frame)
                except Exception as e:
                    print(f"⚠️ MJPEG frame update error: {e}")
            
            # ✅ 錄影功能：寫入幀到錄影檔
            if recording_manager.is_recording:
                try:
                    # 使用 1080p 進行錄影
                    recording_frame = cv2.resize(display_frame, (1920, 1080))
                    recording_manager.write_frame(recording_frame)
                except Exception as e:
                    print(f"⚠️ Recording frame write error: {e}")

            # 🖼️ 顯示相機即時畫面 (YOLO 輸入畫面)
            cv2.imshow('YOLO Input Frame', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("🛑 User pressed 'q', stopping camera...")
                camera_running.clear()

            # ✅ 優化 3: 效能監控與智能幀率控制
            frame_time = time.time() - frame_start
            perf_monitor.record_frame(frame_time)
            
            # 每 30 幀輸出一次效能統計
            #if frame_count % 30 == 0:
            #    stats = perf_monitor.get_stats()
            #    print(f"📊 Performance: FPS={stats['current_fps']:.1f}, Latency={stats['avg_latency_ms']:.1f}ms")
            
            # 練習/遊玩模式取消 30 FPS 上限，其餘模式維持原有限速。
            if not _is_high_fps_mode_active():
                target_time = 1.0 / NORMAL_RUNTIME_FPS_CAP
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
        safe_release_capture(cap)


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


def _is_expected_websocket_close(exc: Exception) -> bool:
    if isinstance(exc, WebSocketDisconnect):
        return True
    message = str(exc).lower()
    expected_markers = (
        "socket.send() raised exception",
        "websocket is not connected",
        "after sending 'websocket.close'",
        "cannot call \"send\" once a close message has been sent",
        "connection reset",
        "broken pipe",
    )
    return any(marker in message for marker in expected_markers)


def _raise_as_websocket_disconnect(exc: Exception) -> None:
    if isinstance(exc, WebSocketDisconnect):
        raise exc
    raise WebSocketDisconnect(code=1006) from exc


async def _safe_websocket_send_text(websocket: WebSocket, payload: str) -> None:
    try:
        await websocket.send_text(payload)
    except Exception as exc:
        if _is_expected_websocket_close(exc):
            _raise_as_websocket_disconnect(exc)
        raise


async def _safe_websocket_send_bytes(websocket: WebSocket, payload: bytes) -> None:
    try:
        await websocket.send_bytes(payload)
    except Exception as exc:
        if _is_expected_websocket_close(exc):
            _raise_as_websocket_disconnect(exc)
        raise


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
    await _safe_websocket_send_text(websocket, json.dumps(envelope))


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
    except WebSocketDisconnect:
        print(f"👋 Heartbeat disconnected: {connection_id}")
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
                ar_route_segments = latest_analysis_data.get("ar_route_segments", [])
                multi_plan_payload = latest_analysis_data.get("multi_plan") or data_packet.get("multi_plan")
                
                # 構造 metadata payload
                metadata_payload = {
                    "frame_id": metadata_counter,
                    "ts_backend": int(current_time * 1000),
                    "detected_count": len(data_packet.get("balls", [])),
                    "tracking_state": "active" if system_state["is_analyzing"] else "idle",
                    "detections": data_packet.get("balls", []),
                    "prediction": data_packet.get("prediction"),
                    "multi_plan": multi_plan_payload,
                    "ar_paths": ar_paths,
                    "ar_route_segments": ar_route_segments,
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

                if multi_plan_payload:
                    await send_ws_envelope(
                        websocket,
                        "planner.update",
                        multi_plan_payload,
                        session_id,
                        session.stream_id,
                    )
                elif latest_analysis_data.get("planner_error"):
                    await send_ws_envelope(
                        websocket,
                        "planner.error",
                        {"error": latest_analysis_data.get("planner_error")},
                        session_id,
                        session.stream_id,
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
    "ar_route_segments": [],
    "multi_plan": None,
    "planner_error": None,
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
                "ar_route_segments": latest_analysis_data.get("ar_route_segments", []),
                "multi_plan": latest_analysis_data.get("multi_plan"),
                "planner_error": latest_analysis_data.get("planner_error"),
                "status": latest_analysis_data.get("status", "Idle"),
                "is_analyzing": system_state["is_analyzing"],
                "timestamp": time.time(),
                "mjpeg_stats": mjpeg_manager.get_stats() if mjpeg_manager else None,
            }
            await _safe_websocket_send_text(websocket, json.dumps(payload))

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

    # 優先復用現有相機，避免每個 WS 連線都重新開啟硬體
    cap = camera_state.get("current_cap")
    if cap is None or not cap.isOpened():
        cap = reopen_camera_with_fallback(camera_state["selected_device_id"])
    if cap is None:
        print("❌ Failed to open camera on WebSocket connect")
        await _safe_websocket_send_text(
            websocket,
            json.dumps({"status": "error", "message": "Failed to open camera device"}),
        )
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
        last_ar_route_segments: list[Any] = []

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
                    await _safe_websocket_send_text(
                        websocket,
                        json.dumps(
                            {
                                "status": "error",
                                "message": f"Failed to switch to camera {camera_state['new_device_id']}",
                            }
                        )
                    )
                    break

            # ✅ 嘗試讀取幀（影片來源時自動處理迴圈）
            ret, frame = read_frame_with_looped_video_source(cap)

            if not ret or frame is None:
                if failure_count >= max_failures:
                    print(f"🔁 Reopening camera after {failure_count} failures")
                    safe_release_capture(cap)

                    # 重新開啟
                    cap = reopen_camera_with_fallback(camera_state["selected_device_id"])
                    if cap is not None:
                        print("   ✅ Camera reopened")
                        failure_count = 0
                    else:
                        print("❌ Failed to reopen camera")
                        await _safe_websocket_send_text(
                            websocket,
                            json.dumps({"status": "error", "message": "Camera unavailable"}),
                        )
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
            ar_route_segments: list[Any] = []
            if used_cached:
                ar_paths = list(last_ar_paths)
                ar_route_segments = list(last_ar_route_segments)
            else:
                try:
                    ar_route_segments = transform_route_segments_for_ar(data_packet)
                    if not ar_route_segments and data_packet.get("prediction") and calibrator is not None:
                        raw_paths = data_packet["prediction"]["paths"]
                        ar_paths = calibrator.transform_points(raw_paths)
                except Exception:
                    pass

            if not used_cached and system_state["is_analyzing"] and tracker is not None and not skip_yolo:
                last_processed_frame = processed_frame.copy()
                last_data_packet = data_packet
                last_ar_paths = ar_paths
                last_ar_route_segments = ar_route_segments

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
            latest_analysis_data["ar_route_segments"] = ar_route_segments
            latest_analysis_data["multi_plan"] = data_packet.get("multi_plan")
            latest_analysis_data["planner_error"] = data_packet.get("multi_plan", {}).get("error") if isinstance(data_packet.get("multi_plan"), dict) else None
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
                "ar_route_segments": ar_route_segments,
                "multi_plan": data_packet.get("multi_plan"),
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
                await _safe_websocket_send_text(websocket, json.dumps(payload))
                if image_buffer is not None:
                    await _safe_websocket_send_bytes(websocket, image_buffer)
            except WebSocketDisconnect:
                print("👋 Client disconnected during send")
                break
            except Exception as e:
                print(f"❌ WebSocket send error: {e}")
                break

            websocket_elapsed = time.time() - websocket_start
            record_perf("websocket", websocket_elapsed)

            if not _is_high_fps_mode_active():
                await asyncio.sleep(1.0 / NORMAL_RUNTIME_FPS_CAP)
    except WebSocketDisconnect:
        print("👋 Client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
    finally:
        if cap is not None:
            safe_release_capture(cap)
        print("📴 Video endpoint closed")


@app.post("/api/control/toggle")
async def toggle_analysis():
    ensure_camera_capture_started()
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



@app.get("/api/color-calibration/profiles")
async def list_color_calibration_profiles(mode: str = Query("pool")):
    mode = mode.lower().strip()
    if mode not in COLOR_CALIBRATION_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")

    profiles = recording_manager.db.list_color_calibration_profiles(mode)
    return {
        "mode": mode,
        "system_colors": COLOR_CALIBRATION_MODES[mode],
        "profiles": profiles,
    }


@app.post("/api/color-calibration/profiles")
async def create_color_calibration_profile(request: dict = Body(...)):
    mode = str(request.get("mode", "pool")).lower().strip()
    name = str(request.get("name", "")).strip()

    if mode not in COLOR_CALIBRATION_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")
    if not name:
        raise HTTPException(status_code=400, detail="Missing profile name")

    try:
        profile = recording_manager.db.create_color_calibration_profile(mode, name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Create profile failed: {e}")

    return {"status": "success", "profile": profile}


@app.get("/api/color-calibration/profiles/{profile_id}")
async def get_color_calibration_profile(profile_id: int):
    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "profile": profile,
        "system_colors": COLOR_CALIBRATION_MODES.get(profile.get("mode", "pool"), COLOR_CALIBRATION_MODES["pool"]),
    }


@app.put("/api/color-calibration/profiles/{profile_id}/mappings")
async def update_color_calibration_profile(profile_id: int, request: dict = Body(...)):
    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    mode = profile.get("mode", "pool")
    mappings = _sanitize_color_mappings(mode, request.get("mappings", {}))
    ok = recording_manager.db.update_color_calibration_profile(profile_id, mappings)
    if not ok:
        raise HTTPException(status_code=500, detail="Update mappings failed")

    updated = recording_manager.db.get_color_calibration_profile(profile_id)
    return {"status": "success", "profile": updated}


@app.post("/api/color-calibration/apply")
async def apply_color_calibration(request: dict = Body(...)):
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    set_route_planner_runtime(False, "practice")

    profile_id = request.get("profile_id")
    if profile_id is None:
        raise HTTPException(status_code=400, detail="Missing profile_id")

    profile = recording_manager.db.get_color_calibration_profile(int(profile_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    mode = profile.get("mode", "pool")
    mappings = _sanitize_color_mappings(mode, profile.get("mappings", {}))
    apply_result = tracker.apply_color_calibration(mode, mappings)

    color_calibration_state["profile_id"] = profile.get("id")
    color_calibration_state["profile_name"] = profile.get("name")
    color_calibration_state["mode"] = mode
    color_calibration_state["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "status": "success",
        "profile_id": profile.get("id"),
        "mode": mode,
        "applied": apply_result.get("applied", 0),
    }


@app.post("/api/color-calibration/sample-hsv")
async def sample_color_hsv(request: dict = Body(...)):
    set_route_planner_runtime(False, "practice")
    if mjpeg_manager is None:
        raise HTTPException(status_code=503, detail="MJPEG manager not initialized")

    x = int(request.get("x", -1))
    y = int(request.get("y", -1))
    region_size = int(request.get("region_size", 14))
    region_size = max(3, min(60, region_size))

    frame = None
    lock = getattr(mjpeg_manager.monitor, "_frame_lock", None)
    if lock is not None:
        with lock:
            raw = getattr(mjpeg_manager.monitor, "_current_raw_frame", None)
            frame = raw.copy() if raw is not None else None

    if frame is None:
        raise HTTPException(status_code=404, detail="No camera frame available")

    h, w = frame.shape[:2]
    if x < 0 or y < 0 or x >= w or y >= h:
        raise HTTPException(status_code=400, detail=f"Point out of range: ({x},{y}) not in {w}x{h}")

    half = region_size // 2
    x0 = max(0, x - half)
    y0 = max(0, y - half)
    x1 = min(w, x + half + 1)
    y1 = min(h, y + half + 1)

    roi = frame[y0:y1, x0:x1]
    if roi.size == 0:
        raise HTTPException(status_code=400, detail="Invalid sample ROI")

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = cv2.split(hsv)

    sat_mask = s_ch >= 20
    val_mask = v_ch >= 25
    valid = sat_mask & val_mask
    if np.count_nonzero(valid) < 12:
        valid = np.ones_like(h_ch, dtype=bool)

    h_vals = h_ch[valid].astype(np.float32)
    s_vals = s_ch[valid].astype(np.float32)
    v_vals = v_ch[valid].astype(np.float32)

    h_med = int(np.median(h_vals))
    s_med = int(np.median(s_vals))
    v_med = int(np.median(v_vals))

    h_tol = int(request.get("h_tol", 8))
    s_tol = int(request.get("s_tol", 40))
    v_tol = int(request.get("v_tol", 40))

    h_tol = max(2, min(40, h_tol))
    s_tol = max(10, min(120, s_tol))
    v_tol = max(10, min(120, v_tol))

    h_low = max(0, h_med - h_tol)
    h_up = min(180, h_med + h_tol)
    s_low = max(0, s_med - s_tol)
    s_up = min(255, s_med + s_tol)
    v_low = max(0, v_med - v_tol)
    v_up = min(255, v_med + v_tol)

    return {
        "status": "success",
        "point": {"x": x, "y": y},
        "roi": {"x": x0, "y": y0, "w": int(x1 - x0), "h": int(y1 - y0)},
        "hsv_center": [h_med, s_med, v_med],
        "hsv_lower": [h_low, s_low, v_low],
        "hsv_upper": [h_up, s_up, v_up],
        "frame_size": {"width": w, "height": h},
    }
@app.get("/api/color-calibration/state")
async def get_color_calibration_state():
    return {
        "status": "success",
        "state": color_calibration_state,
    }


@app.post("/api/color-calibration/reset")
async def reset_color_calibration():
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    set_route_planner_runtime(False, "practice")

    tracker.reset_color_calibration()
    color_calibration_state["profile_id"] = None
    color_calibration_state["profile_name"] = None
    color_calibration_state["mode"] = None
    color_calibration_state["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "status": "success",
        "message": "Color calibration reset to default templates",
        "state": color_calibration_state,
    }


@app.get("/api/color-calibration/auto-scan")
async def auto_scan_color_rois(mode: str = Query("pool")):
    set_route_planner_runtime(False, "practice")
    mode = mode.lower().strip()
    if mode not in COLOR_CALIBRATION_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")

    if mjpeg_manager is None:
        raise HTTPException(status_code=503, detail="MJPEG manager not initialized")

    frame = None
    lock = getattr(mjpeg_manager.monitor, "_frame_lock", None)
    if lock is not None:
        with lock:
            raw = getattr(mjpeg_manager.monitor, "_current_raw_frame", None)
            frame = raw.copy() if raw is not None else None

    if frame is None:
        raise HTTPException(status_code=404, detail="No camera frame available")

    data = latest_analysis_data.get("data", {}) if isinstance(latest_analysis_data, dict) else {}
    balls = data.get("balls", []) if isinstance(data, dict) else []
    if not isinstance(balls, list) or len(balls) == 0:
        raise HTTPException(status_code=404, detail="No YOLO balls available, please enable analyzing and keep balls visible")

    h_img, w_img = frame.shape[:2]

    def _roi_hsv_stats(img, x0, y0, x1, y1):
        roi = img[y0:y1, x0:x1]
        if roi.size == 0:
            return None

        roi_h, roi_w = roi.shape[:2]
        center = (roi_w // 2, roi_h // 2)
        # 用內縮圓圈當作遮罩，排除桌邊布色
        radius = int(min(roi_w, roi_h) * 0.45)
        
        y_grid, x_grid = np.ogrid[:roi_h, :roi_w]
        dist_from_center = np.sqrt((x_grid - center[0])**2 + (y_grid - center[1])**2)
        circle_mask = dist_from_center <= radius

        bgr_pixels = roi[circle_mask].reshape((-1, 3)).astype(np.float32)
        if len(bgr_pixels) < 10:
            return None

        # 使用 K-Means (K=3) 來分離基礎底色、高光(反光斑)與陰影，因為簡單平均(Mean)會混入黑白極端值。
        # 且在 HSV 空間上對 Hue 做直接平均會有 0/180 環邊界錯誤 (例如橘紅加粉紅被平均掉)，故在 BGR 空間做集群
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(bgr_pixels, min(3, len(bgr_pixels)), None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # 找出佔比最大的群集，視為「主色」(Dominant Color)
        counts = np.bincount(labels.flatten())
        dominant_bgr = centers[np.argmax(counts)]

        # 轉換這個主色回 HSV
        dominant_bgr_uint8 = np.uint8([[dominant_bgr]])
        dominant_hsv = cv2.cvtColor(dominant_bgr_uint8, cv2.COLOR_BGR2HSV)[0, 0]
        
        h_dom, s_dom, v_dom = int(dominant_hsv[0]), int(dominant_hsv[1]), int(dominant_hsv[2])

        h_tol, s_tol, v_tol = 8, 40, 40
        h_low = max(0, h_dom - h_tol)
        h_up = min(180, h_dom + h_tol)
        s_low = max(0, s_dom - s_tol)
        s_up = min(255, s_dom + s_tol)
        v_low = max(0, v_dom - v_tol)
        v_up = min(255, v_dom + v_tol)

        return {
            "hsv_center": [h_dom, s_dom, v_dom],
            "hsv_lower": [h_low, s_low, v_low],
            "hsv_upper": [h_up, s_up, v_up],
            "rgb_center": [int(dominant_bgr[2]), int(dominant_bgr[1]), int(dominant_bgr[0])], # R, G, B
        }

    scanned = []
    for i, b in enumerate(balls):
        if not isinstance(b, dict):
            continue
        x = int(b.get("x", 0))
        y = int(b.get("y", 0))
        w = int(b.get("w", 0))
        h = int(b.get("h", 0))
        if w <= 2 or h <= 2:
            continue

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(w_img, x + w)
        y1 = min(h_img, y + h)
        if x1 <= x0 or y1 <= y0:
            continue

        # 內縮 ROI，減少桌布與邊緣干擾
        pad_x = max(1, int((x1 - x0) * 0.12))
        pad_y = max(1, int((y1 - y0) * 0.12))
        rx0 = min(max(0, x0 + pad_x), w_img - 1)
        ry0 = min(max(0, y0 + pad_y), h_img - 1)
        rx1 = max(rx0 + 1, min(w_img, x1 - pad_x))
        ry1 = max(ry0 + 1, min(h_img, y1 - pad_y))

        stats = _roi_hsv_stats(frame, rx0, ry0, rx1, ry1)
        if stats is None:
            continue

        scanned.append({
            "index": i,
            "bbox": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0},
            "roi": {"x": rx0, "y": ry0, "w": rx1 - rx0, "h": ry1 - ry0},
            "detected_number": b.get("number"),
            "detected_label": b.get("label") or b.get("ball_color"),
            **stats,
        })

    if len(scanned) == 0:
        raise HTTPException(status_code=404, detail="No valid ball ROI from current YOLO result")

    # 穩定排序：由左到右、由上到下
    scanned.sort(key=lambda it: (it["bbox"]["x"], it["bbox"]["y"]))

    return {
        "status": "success",
        "mode": mode,
        "system_colors": COLOR_CALIBRATION_MODES[mode],
        "count": len(scanned),
        "scans": scanned,
        "frame_size": {"width": w_img, "height": h_img},
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

    ensure_camera_capture_started()

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

    ensure_camera_capture_started()

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

    ensure_camera_capture_started()

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
    """應用啟動時初始化（採用按需啟動攝像頭執行緒）。"""
    print("✅ App started. Camera capture thread will start on first stream request.")


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
            set_route_planner_runtime(False, "9ball")
            
            if "error" in result:
                print(f"❌ Game start failed: {result['error']}")
                return create_error_response(ERR_INVALID_ARGUMENT, result["error"])
            
            print(f"✅ Game started successfully: {result}")
            _apply_runtime_fps_cap()
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
        set_route_planner_runtime(False, "practice")
        _apply_runtime_fps_cap()
        return JSONResponse({"status": "game_ended"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/practice/start")
async def start_practice(request: Annotated[dict, Body(...)]):
    """開始練習"""
    mode = request.get("mode", "single")
    pattern = request.get("pattern")
    player_name = request.get("player_name")
    pattern_layout = _sanitize_pattern_layout(request.get("pattern_layout")) if mode == "pattern" else None
    raw_guides = request.get("guide_options") if isinstance(request.get("guide_options"), dict) else {}
    guide_options = {
        "cue_laser_enabled": bool(raw_guides.get("cue_laser_enabled", True)),
    }
    
    try:
        result = game_manager.start_practice(mode, pattern, player_name, pattern_layout, guide_options)
        # 一般練習需要最新 YOLO 狀態供自動偵測與多球規劃使用；球型練習維持原本流程。
        if mode == 'single':
            _apply_pattern_practice_projection(None)
            if tracker is not None and hasattr(tracker, "set_cue_laser_only"):
                tracker.set_cue_laser_only(False)
            if not practice_runtime_state["boost_enabled"]:
                practice_runtime_state["prev_yolo_skip_frames"] = system_state.get("yolo_skip_frames", 2)
                practice_runtime_state["prev_is_analyzing"] = system_state.get("is_analyzing", False)
            system_state["yolo_skip_frames"] = 1
            system_state["is_analyzing"] = True
            practice_runtime_state["boost_enabled"] = True
            set_route_planner_runtime(True, "practice")
        else:
            set_route_planner_runtime(False, "practice")
            guide_options = pattern_layout.get("guide_options", {}) if isinstance(pattern_layout, dict) else {}
            cue_laser_enabled = bool(guide_options.get("cue_laser_enabled", True))
            if tracker is not None and hasattr(tracker, "set_cue_laser_only"):
                tracker.set_cue_laser_only(cue_laser_enabled)
            if not practice_runtime_state["boost_enabled"]:
                practice_runtime_state["prev_yolo_skip_frames"] = system_state.get("yolo_skip_frames", 2)
                practice_runtime_state["prev_is_analyzing"] = system_state.get("is_analyzing", False)
            system_state["yolo_skip_frames"] = 1
            system_state["is_analyzing"] = cue_laser_enabled
            practice_runtime_state["boost_enabled"] = True
            _apply_pattern_practice_projection(pattern_layout)
        # 單球練習模式啟用進球輔助線
        if tracker and mode == 'single':
            tracker.set_aim_assist(True)
        # 切換投影機至練習模式
        if projector_renderer is not None and mode != "pattern":
            projector_renderer.set_mode(ProjectorMode.PRACTICE)
        _apply_runtime_fps_cap()
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


@app.post("/api/practice/pattern-guides")
async def update_pattern_guides(request: Annotated[dict, Body(...)]):
    """練習中即時切換球型練習投影指引。"""
    raw_guides = request.get("guide_options") if isinstance(request.get("guide_options"), dict) else {}
    guide_options = {
        "cue_laser_enabled": bool(raw_guides.get("cue_laser_enabled", True)),
        "ball_guides_enabled": bool(raw_guides.get("ball_guides_enabled", True)),
    }

    try:
        result = game_manager.update_pattern_guide_options(guide_options)
        if result.get("error"):
            return create_error_response(ERR_INVALID_ARGUMENT, result["error"])

        cue_laser_enabled = bool(guide_options.get("cue_laser_enabled", True))
        if tracker is not None and hasattr(tracker, "set_cue_laser_only"):
            tracker.set_cue_laser_only(cue_laser_enabled)

        if practice_runtime_state["boost_enabled"]:
            system_state["is_analyzing"] = cue_laser_enabled

        if projector_renderer is not None and not cue_laser_enabled:
            projector_renderer.update_ar_data({
                "cue_laser_lines": [],
                "allow_legacy_aim_lines": False,
                "allow_legacy_trajectories": False,
            })

        _apply_pattern_practice_projection(result.get("pattern_layout"))
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/practice/guides")
async def update_practice_guides(request: Annotated[dict, Body(...)]):
    """練習中即時切換共用投影指引。"""
    raw_guides = request.get("guide_options") if isinstance(request.get("guide_options"), dict) else {}
    guide_options = {
        "cue_laser_enabled": bool(raw_guides.get("cue_laser_enabled", True)),
    }
    if "ball_guides_enabled" in raw_guides:
        guide_options["ball_guides_enabled"] = bool(raw_guides.get("ball_guides_enabled", True))

    try:
        result = game_manager.update_practice_guide_options(guide_options)
        if result.get("error"):
            return create_error_response(ERR_INVALID_ARGUMENT, result["error"])

        cue_laser_enabled = bool(result.get("guide_options", {}).get("cue_laser_enabled", True))
        active_state = game_manager.get_practice_state()
        active_mode = active_state.get("mode") if isinstance(active_state, dict) else None
        if active_mode == "practice_pattern":
            if tracker is not None and hasattr(tracker, "set_cue_laser_only"):
                tracker.set_cue_laser_only(cue_laser_enabled)
            if practice_runtime_state["boost_enabled"]:
                system_state["is_analyzing"] = cue_laser_enabled

        if projector_renderer is not None and not cue_laser_enabled:
            projector_renderer.update_ar_data({"cue_laser_lines": []})

        pattern_layout = result.get("pattern_layout")
        if isinstance(pattern_layout, dict):
            _apply_pattern_practice_projection(pattern_layout)

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
        # Restore sampling settings after practice
        if practice_runtime_state["boost_enabled"]:
            system_state["yolo_skip_frames"] = practice_runtime_state["prev_yolo_skip_frames"]
            system_state["is_analyzing"] = practice_runtime_state["prev_is_analyzing"]
            practice_runtime_state["boost_enabled"] = False
        # 停用進球輔助線
        if tracker:
            tracker.set_aim_assist(False)
            if hasattr(tracker, "set_cue_laser_only"):
                tracker.set_cue_laser_only(False)
        set_route_planner_runtime(False, "practice")
        # 切換投影機回待機模式
        if projector_renderer is not None:
            projector_renderer.set_mode(ProjectorMode.IDLE)
        _apply_runtime_fps_cap()
        return JSONResponse({"status": "practice_ended"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/planner/plan")
async def planner_plan(request: Annotated[dict, Body(...)]):
    """
    多球路徑規劃（單次查詢）
    """
    if tracker is None:
        return create_error_response(ERR_INTERNAL, "Tracker unavailable")

    practice_state = game_manager.get_practice_state()
    if not (
        practice_state
        and practice_state.get("is_active")
        and practice_state.get("mode") == "practice_single"
    ):
        return create_error_response(ERR_INVALID_ARGUMENT, "Planner is only available in single practice mode")

    rule_profile = str(request.get("rule_profile", "practice"))
    if rule_profile not in ("practice", "9ball"):
        return create_error_response(ERR_INVALID_ARGUMENT, "rule_profile must be practice or 9ball")

    top_n = int(request.get("top_n", 5))
    max_bounces = int(request.get("max_bounces", 3))
    combo_depth = int(request.get("combo_depth", 2))

    runtime_packet = latest_analysis_data.get("data", {})
    if not isinstance(runtime_packet, dict) or not runtime_packet:
        return create_error_response(ERR_INVALID_ARGUMENT, "No analysis data available")

    target_ball_number = request.get("target_ball_number")
    if target_ball_number is None and rule_profile == "9ball":
        g_state = game_manager.get_game_state()
        if g_state and isinstance(g_state.get("target_ball"), int):
            target_ball_number = g_state["target_ball"]

    tracker.set_route_rule_profile(rule_profile)
    tracker.configure_route_planner(top_n=top_n, max_bounces=max_bounces, combo_depth=combo_depth)
    if "stroke" in request and hasattr(tracker, "set_route_stroke_override"):
        tracker.set_route_stroke_override(_sanitize_stroke_override(request.get("stroke")))

    plan = tracker.plan_routes_from_packet(
        runtime_packet,
        rule_profile=rule_profile,
        top_n=top_n,
        target_ball_number=target_ball_number if isinstance(target_ball_number, int) else None,
        max_bounces=max_bounces,
        combo_depth=combo_depth,
    )
    if plan is None:
        return create_error_response(ERR_INVALID_ARGUMENT, "Insufficient state for route planning")

    latest_analysis_data["multi_plan"] = plan
    latest_analysis_data["planner_error"] = plan.get("error")
    latest_analysis_data["ar_route_segments"] = transform_route_segments_for_ar(
        {**runtime_packet, "multi_plan": plan}
    )

    return JSONResponse(
        {
            "status": "success",
            "multi_plan": plan,
            "input": {
                "rule_profile": rule_profile,
                "top_n": top_n,
                "max_bounces": max_bounces,
                "combo_depth": combo_depth,
                "target_ball_number": target_ball_number,
            },
        }
    )


@app.post("/api/planner/disable")
async def planner_disable():
    """關閉即時多球路徑規劃並清空舊 AR/metadata 路線。"""
    set_route_planner_runtime(False, "practice")
    return JSONResponse({"status": "success", "enabled": False})


@app.post("/api/planner/select-route")
async def planner_select_route(request: Annotated[dict, Body(...)]):
    """切換目前顯示的進球線路。"""
    route_id = str(request.get("route_id", "")).strip()
    if not route_id:
        return create_error_response(ERR_INVALID_ARGUMENT, "Missing route_id")

    current_plan = latest_analysis_data.get("multi_plan")
    if not isinstance(current_plan, dict):
        return create_error_response(ERR_INVALID_ARGUMENT, "No planner state available")

    updated_plan = _select_route_in_plan(current_plan, route_id)
    best_route = updated_plan.get("best_route")
    if not isinstance(best_route, dict) or best_route.get("id") != route_id:
        return create_error_response(ERR_NOT_FOUND, "Route not found")

    if tracker is not None:
        tracker.set_selected_route_id(route_id)

    latest_analysis_data["multi_plan"] = updated_plan
    data_packet = latest_analysis_data.get("data")
    if isinstance(data_packet, dict):
        data_packet["multi_plan"] = updated_plan
        if hasattr(tracker, "_legacy_prediction_from_best_route"):
            data_packet["prediction"] = tracker._legacy_prediction_from_best_route(best_route) if tracker is not None else data_packet.get("prediction")
        if tracker is not None and hasattr(tracker, "_aim_assist_from_route"):
            white_ball = data_packet.get("white_ball")
            route_aim = tracker._aim_assist_from_route(best_route, white_ball) if isinstance(white_ball, list) else None
            if route_aim:
                data_packet["aim_assist"] = route_aim
                latest_analysis_data["aim_assist"] = route_aim

    latest_analysis_data["ar_route_segments"] = transform_route_segments_for_ar(
        {**(data_packet if isinstance(data_packet, dict) else {}), "multi_plan": updated_plan}
    )

    return JSONResponse({"status": "success", "multi_plan": updated_plan})


@app.post("/api/planner/stroke")
async def planner_stroke(request: Annotated[dict, Body(...)]):
    """設定手動桿法並用目前球桌狀態重新規劃母球行徑與落點。"""
    if tracker is None:
        return create_error_response(ERR_INTERNAL, "Tracker unavailable")

    practice_state = game_manager.get_practice_state()
    if not (
        practice_state
        and practice_state.get("is_active")
        and practice_state.get("mode") == "practice_single"
    ):
        return create_error_response(ERR_INVALID_ARGUMENT, "Stroke control is only available in single practice mode")

    stroke = _sanitize_stroke_override(request.get("stroke") or request)
    tracker.set_route_stroke_override(stroke)

    runtime_packet = latest_analysis_data.get("data", {})
    if not isinstance(runtime_packet, dict) or not runtime_packet:
        return create_error_response(ERR_INVALID_ARGUMENT, "No analysis data available")

    plan = tracker.plan_routes_from_packet(runtime_packet)
    if plan is None:
        return create_error_response(ERR_INVALID_ARGUMENT, "Insufficient state for route planning")

    latest_analysis_data["multi_plan"] = plan
    latest_analysis_data["planner_error"] = plan.get("error")
    data_packet = latest_analysis_data.get("data")
    if isinstance(data_packet, dict):
        data_packet["multi_plan"] = plan
        best_route = plan.get("best_route")
        if isinstance(best_route, dict) and hasattr(tracker, "_legacy_prediction_from_best_route"):
            data_packet["prediction"] = tracker._legacy_prediction_from_best_route(best_route)
        if isinstance(best_route, dict) and hasattr(tracker, "_aim_assist_from_route"):
            white_ball = data_packet.get("white_ball")
            route_aim = tracker._aim_assist_from_route(best_route, white_ball) if isinstance(white_ball, list) else None
            if route_aim:
                data_packet["aim_assist"] = route_aim
                latest_analysis_data["aim_assist"] = route_aim

    latest_analysis_data["ar_route_segments"] = transform_route_segments_for_ar(
        {**(runtime_packet if isinstance(runtime_packet, dict) else {}), "multi_plan": plan}
    )

    return JSONResponse({"status": "success", "stroke": stroke, "multi_plan": plan})


@app.get("/api/planner/state")
async def planner_state():
    if not isinstance(latest_analysis_data, dict):
        return create_error_response(ERR_INTERNAL, "Planner state unavailable")

    return JSONResponse(
        {
            "status": "success",
            "multi_plan": latest_analysis_data.get("multi_plan"),
            "planner_error": latest_analysis_data.get("planner_error"),
            "timestamp": latest_analysis_data.get("timestamp", 0),
        }
    )



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
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        use_colors=False,
        access_log=False,
    )

# ================== Recording APIs ==================

@app.post("/api/recording/start")
async def start_recording(request: Annotated[dict, Body(...)]):
    """開始錄影"""
    game_type = request.get("game_type")
    players = request.get("players", [])
    
    try:
        game_id = await run_in_threadpool(
            recording_manager.start_recording,
            game_type,
            players
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
        result = await run_in_threadpool(
            recording_manager.stop_recording,
            final_score,
            winner,
            total_rounds
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
        await run_in_threadpool(recording_manager.log_event, event_type, data)
        return JSONResponse({"status": "logged"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/recordings")
async def get_recordings():
    """獲取錄影列表"""
    try:
        recordings = await run_in_threadpool(recording_manager.get_recordings_list)
        return JSONResponse({"recordings": recordings})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.get("/api/recording/{game_id}/metadata")
async def get_recording_metadata(game_id: str):
    """獲取特定錄影的元資料"""
    metadata = await run_in_threadpool(recording_manager.get_recording_metadata, game_id)
    
    if metadata:
        return JSONResponse(metadata)
    return create_error_response(ERR_NOT_FOUND, "Recording not found")


@app.get("/api/recording/{game_id}/events")
async def get_recording_events(game_id: str):
    """獲取錄影的事件日誌"""
    try:
        events = await run_in_threadpool(recording_manager.get_recording_events, game_id)
        return JSONResponse({"events": events})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))
# ==================== 錄影相關 API (已移至 api/replay_api.py 模組) ====================

# ==================== 投影機校正 API (已移至 api/calibration_api.py 模組) ====================




































