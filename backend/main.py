import asyncio
import atexit
import hashlib
import json
import logging
import math
import os
import re
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

#性能監控
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import Annotated, Any, Optional, cast

APP_STARTED_AT = time.time()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = Path.cwd() / "logs"
RUNTIME_DIR = Path.cwd() / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_LOG_PATH = LOG_DIR / "backend-runtime.log"
try:
    RUNTIME_LOG_FILE = open(RUNTIME_LOG_PATH, "a", encoding="utf-8", errors="replace", buffering=1)
except PermissionError:
    RUNTIME_LOG_PATH = LOG_DIR / f"backend-runtime-{os.getpid()}.log"
    RUNTIME_LOG_FILE = open(RUNTIME_LOG_PATH, "a", encoding="utf-8", errors="replace", buffering=1)
    if sys.__stderr__ is not None:
        sys.__stderr__.write(f"WARNING backend-runtime.log is locked; using {RUNTIME_LOG_PATH}\n")


class TeeStream:
    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file

    def write(self, data: str) -> int:
        try:
            written = self.original.write(data)
        except UnicodeEncodeError:
            encoded = data.encode(getattr(self.original, "encoding", None) or "utf-8", errors="replace")
            self.original.buffer.write(encoded)
            written = len(data)
        self.log_file.write(data)
        return written

    def flush(self) -> None:
        self.original.flush()
        self.log_file.flush()

    def isatty(self) -> bool:
        return self.original.isatty()


sys.stdout = TeeStream(sys.stdout, RUNTIME_LOG_FILE)
sys.stderr = TeeStream(sys.stderr, RUNTIME_LOG_FILE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(RUNTIME_LOG_FILE),
        logging.StreamHandler(sys.__stderr__),
    ],
)
logger = logging.getLogger("billiards.runtime")
logger.info("Backend process starting pid=%s log=%s", os.getpid(), RUNTIME_LOG_PATH)


def close_runtime_log() -> None:
    logger.info("Backend process exiting pid=%s", os.getpid())
    RUNTIME_LOG_FILE.flush()
    RUNTIME_LOG_FILE.close()


atexit.register(close_runtime_log)


def is_tcp_port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False
 
load_dotenv(PROJECT_ROOT / "backend" / ".env")
load_dotenv(PROJECT_ROOT / "mobile-remote.env", override=True)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import config
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
os.environ.setdefault("YOLO_CONFIG_DIR", str(RUNTIME_DIR / "ultralytics"))
Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
import cv2
import numpy as np
import uvicorn
from calibration.calibration import Calibrator
from fastapi import Body, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from starlette.concurrency import run_in_threadpool
from tracking.tracking_engine import PoolTracker
from streaming.mjpeg_streamer import DualMJPEGManager
from core.session_manager import session_manager, Role, SessionState
from core.error_codes import (
    ERR_INVALID_ARGUMENT, ERR_NOT_FOUND, ERR_FORBIDDEN, ERR_SESSION_EXPIRED,
    ERR_STREAM_UNAVAILABLE, ERR_INTERNAL
)
from core.performance_monitor import PerformanceMonitor
from core.coach_bridge import CoachBridge
from core.coach_payload_builder import CoachPayloadBuilder
from core.coach_semantics import CoachSemanticAdapter, classify_coach_intent
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

@asynccontextmanager
async def app_lifespan(_: FastAPI):
    """FastAPI lifespan：啟動按需攝影機與關閉背景資源。"""
    print("✅ App started. Camera capture thread will start on first stream request.")
    logger.info("FastAPI startup complete pid=%s", os.getpid())
    _apply_saved_color_calibration()
    await coach_bridge.start()
    try:
        yield
    finally:
        print("🛑 Shutting down camera capture thread...")
        logger.warning(
            "FastAPI shutdown started pid=%s uptime_sec=%.3f camera_running=%s camera_thread_alive=%s active_threads=%s",
            os.getpid(),
            time.time() - APP_STARTED_AT,
            camera_running.is_set(),
            bool(camera_capture_thread and camera_capture_thread.is_alive()),
            threading.active_count(),
        )
        camera_running.clear()
        await coach_bridge.stop()

        if camera_capture_thread is not None:
            camera_capture_thread.join(timeout=5.0)
        logger.warning("FastAPI shutdown complete pid=%s", os.getpid())


app = FastAPI(lifespan=app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊 API 路由
@app.middleware("http")
async def log_unhandled_http_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled HTTP error path=%s method=%s", request.url.path, request.method)
        raise


from api.replay_api import db as replay_db
from api.replay_api import router as replay_router
app.include_router(replay_router)

from api.auth_api import account_store as auth_account_store
from api.auth_api import router as auth_router
app.include_router(auth_router)

from api.community_api import router as community_router
app.include_router(community_router)

from api.mobile_api import _build_mobile_analytics_v1, router as mobile_router, set_start_friend_game_handler
app.include_router(mobile_router)

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
coach_bridge = CoachBridge(
    enabled=getattr(config, "AI_COACH_ENABLED", False)
    and str(getattr(config, "AI_COACH_MODE", "websocket")).lower() == "websocket",
    ws_url=str(getattr(config, "AI_COACH_WS_URL", "ws://localhost:8010/ws/coach")),
    session_id=str(getattr(config, "AI_COACH_SESSION_ID", "backend_yolo")),
    reconnect_seconds=getattr(config, "AI_COACH_RECONNECT_SECONDS", 3.0),
    request_timeout=getattr(config, "AI_COACH_REQUEST_TIMEOUT_SECONDS", 90.0),
    ping_interval=getattr(config, "AI_COACH_WS_PING_INTERVAL", 0.0),
    ping_timeout=getattr(config, "AI_COACH_WS_PING_TIMEOUT", 0.0),
)
coach_semantics = CoachSemanticAdapter(
    stable_frames=int(getattr(config, "AI_COACH_STABLE_FRAMES", 5)),
    stable_max_shift=getattr(config, "AI_COACH_STABLE_MAX_SHIFT", 18.0),
    min_balls=int(getattr(config, "AI_COACH_MIN_BALLS", 1)),
)
coach_payload_builder = CoachPayloadBuilder()
ai_coach_auto_state: dict[str, Any] = {
    "last_submitted_at": 0.0,
    "last_signature": "",
}


camera_state: dict[str, Any] = {
    "selected_device_id": 0,  # 預設使用裝置 0
    "available_devices": [],  # 列出所有可用的攝像頭
    "current_cap": None,  # 當前的 cv2.VideoCapture 實例
    "needs_switch": False,  # 標記是否需要切換攝像頭
    "new_device_id": 0,  # 新的設備 ID
    "is_switching": False,  # 標記是否正在切換中
    "last_frame_time": 0.0,  # ✅ 追蹤最新畫面時間戳
    "selected_backend": cv2.CAP_DSHOW,
    "last_good_backend": cv2.CAP_DSHOW,  # 上次成功的後端，重連優先
    "last_good_profile": None,  # 上次成功的解析度/FPS
    "reconnect_backoff_sec": 0.2,  # 重連回退秒數（動態）
}
system_state: dict[str, Any] = {
    "is_analyzing": False,  # 預設不開啟 YOLO，只送純影像
    "yolo_skip_frames": 0,  # 每幀執行 YOLO；如需降負載可用 /api/control/yolo-skip 調高
    "yolo_stalled": False,
    "yolo_stalled_at": 0.0,
}

practice_tracking_state: dict[str, Any] = {
    "is_attempt_in_progress": False,
    "cooldown_frames": 0,
    "last_white_pos": None,
    "attempt_start_white_pos": None,
    "last_colors_pos": [],
    "last_colors_snapshot": [],
    "last_target_pos": None,
    "last_target_number": None,
    "last_cue_radius": 0.0,
    "last_target_radius": 0.0,
    "still_frames": 0,
    "attempt_frames": 0,
    "cue_missing_frames": 0,
    "target_missing_frames": 0,
    "cue_in_hole_frames": 0,
    "target_in_hole_frames": 0,
    "target_pocket_approach_frames": 0,
    "target_disappearance_frames": 0,
    "cue_was_in_hole": False,
    "target_was_in_hole": False,
    "start_motion_frames": 0,
    "cue_ball_potted": False,
    "target_ball_potted": False,
}

game_tracking_state: dict[str, Any] = {
    "is_shot_in_progress": False,
    "last_white_pos": None,
    "last_balls": [],
    "shot_start_balls": [],
    "first_contact": None,
    "potted_balls": [],
    "missing_ball_frames": {},
    "disappearance_ball_frames": {},
    "last_cue_radius": 0.0,
    "still_frames": 0,
    "shot_frames": 0,
    "shot_start_white_pos": None,
    "cue_missing_frames": 0,
    "cue_in_hole_frames": 0,
    "cue_was_in_hole": False,
    "cue_ball_potted": False,
    "start_motion_frames": 0,
    "visual_seen_counts": {},
    "visual_missing_counts": {},
    "last_visual_remaining": [],
}
latest_coach_shot_event: dict[str, Any] | None = None
shot_event_counters: dict[str, int] = {}

practice_runtime_state: dict[str, Any] = {
    "boost_enabled": False,
    "prev_yolo_skip_frames": 0,
    "prev_is_analyzing": False,
}

game_runtime_state: dict[str, Any] = {
    "boost_enabled": False,
    "prev_yolo_skip_frames": 0,
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
projector_render_thread = None
projector_render_running = threading.Event()
projector_render_lock = threading.Lock()

# ✅ 全域效能監控器 (用於 API 查詢)
global_perf_monitor: Optional[PerformanceMonitor] = None

# 遊戲模式管理器
from tracking.game_manager import GameManager
from streaming.recording_manager import RecordingManager
import os

game_manager = GameManager()
_apply_runtime_fps_cap()


async def _start_friend_game_from_mobile(player1: str, player2: str) -> dict[str, Any]:
    target_rounds = 5
    shot_time_limit = 0
    raw_options: dict[str, Any] = {}
    result = game_manager.start_nine_ball(player1, player2, target_rounds, shot_time_limit, raw_options)
    if "error" in result:
        return create_error_response(ERR_INVALID_ARGUMENT, result["error"])

    options = result.get("game_options", {}) if isinstance(result.get("game_options"), dict) else {}
    _reset_game_auto_tracking_state()
    if not game_runtime_state["boost_enabled"]:
        game_runtime_state["prev_yolo_skip_frames"] = system_state.get("yolo_skip_frames", 0)
        game_runtime_state["prev_is_analyzing"] = system_state.get("is_analyzing", False)
    needs_analysis = bool(
        options.get("auto_pot_detection", True)
        or options.get("foul_detection", True)
        or options.get("auto_scoring", True)
        or options.get("target_ar_hint_enabled", True)
    )
    system_state["yolo_skip_frames"] = 0
    system_state["is_analyzing"] = needs_analysis
    game_runtime_state["boost_enabled"] = True

    target_ar_enabled = bool(options.get("target_ar_hint_enabled", True))
    set_route_planner_runtime(target_ar_enabled, "9ball")
    if tracker is not None:
        tracker.set_aim_assist(target_ar_enabled)
        if hasattr(tracker, "set_route_target_ball_number"):
            tracker.set_route_target_ball_number(1 if target_ar_enabled else None)
    if projector_renderer is not None:
        projector_renderer.set_mode(
            ProjectorMode.GAME
            if target_ar_enabled or int(shot_time_limit or 0) > 0
            else ProjectorMode.IDLE
        )
    _sync_game_timer_projection()
    _apply_runtime_fps_cap()
    return result


set_start_friend_game_handler(_start_friend_game_from_mobile)

# 使用專案根目錄的 recordings 資料夾
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
recording_manager = RecordingManager(
    recordings_dir=os.path.join(project_root, "recordings"),
    db_path=os.path.join(os.path.dirname(__file__), "data", "recordings.db")
)
shot_event_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ShotAnalytics")
atexit.register(lambda: shot_event_executor.shutdown(wait=False, cancel_futures=False))


COLOR_CALIBRATION_MODES: dict[str, list[str]] = {
    "pool": ["Yellow", "Blue", "Red", "Purple", "Orange", "Green", "Brown", "Black", "White"],
    "snooker": ["Red", "Yellow", "Green", "Brown", "Blue", "Pink", "Black", "White"],
}

COLOR_CALIBRATION_STATE_PATH = RUNTIME_DIR / "color_calibration_state.json"


def _normalize_hsv_triplet(values: Any, field_name: str) -> list[int]:
    if not isinstance(values, list) or len(values) != 3:
        raise HTTPException(status_code=400, detail=f"{field_name} must be [H,S,V]")
    h = int(values[0])
    s = int(values[1])
    v = int(values[2])
    if h < 0 or h > 180 or s < 0 or s > 255 or v < 0 or v > 255:
        raise HTTPException(status_code=400, detail=f"{field_name} out of range")
    return [h, s, v]


def _default_color_calibration_state() -> dict[str, Any]:
    return {
        "profile_id": None,
        "profile_name": None,
        "mode": None,
        "applied_at": None,
    }


def _load_color_calibration_state() -> dict[str, Any]:
    try:
        data = json.loads(COLOR_CALIBRATION_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return _default_color_calibration_state()

    state = _default_color_calibration_state()
    if isinstance(data, dict):
        state.update({
            "profile_id": data.get("profile_id"),
            "profile_name": data.get("profile_name"),
            "mode": data.get("mode"),
            "applied_at": data.get("applied_at"),
        })
    return state


def _save_color_calibration_state() -> None:
    COLOR_CALIBRATION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    COLOR_CALIBRATION_STATE_PATH.write_text(
        json.dumps(color_calibration_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


color_calibration_state: dict[str, Any] = _load_color_calibration_state()


def _apply_saved_color_calibration() -> None:
    if tracker is None:
        print("⚠️  Skipped saved color calibration: tracker not initialized")
        return

    raw_profile_id = color_calibration_state.get("profile_id")
    if raw_profile_id is None:
        return

    try:
        profile_id = raw_profile_id
    except (TypeError, ValueError):
        print(f"⚠️  Skipped saved color calibration: invalid profile_id={raw_profile_id}")
        return

    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        print(f"⚠️  Skipped saved color calibration: profile {profile_id} not found")
        return

    mode = profile.get("mode", "pool")
    mappings = _build_tracker_color_mappings(mode, profile.get("mappings", {}))
    apply_result = tracker.apply_color_calibration(mode, mappings)
    seeded_identity_locks = _seed_manual_identity_locks_from_sample_sets(int(profile.get("id") or 0), profile.get("mappings", {}))

    color_calibration_state["profile_id"] = profile.get("id")
    color_calibration_state["profile_name"] = profile.get("name")
    color_calibration_state["mode"] = mode
    _save_color_calibration_state()

    print(
        "✅ Applied saved ball color calibration "
        f"profile={profile.get('name')} mode={mode} updated={apply_result.get('applied', 0)} "
        f"identity_locks={seeded_identity_locks}"
    )

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


COLOR_PROFILE_RESERVED_KEYS = {"_sample_sets", "_learned_templates", "_validation"}


def _extract_color_profile_assets(mappings: Any) -> dict[str, Any]:
    if not isinstance(mappings, dict):
        return {}
    assets: dict[str, Any] = {}
    for key in COLOR_PROFILE_RESERVED_KEYS:
        value = mappings.get(key)
        if isinstance(value, dict):
            assets[key] = value
    return assets


def _build_tracker_color_mappings(mode: str, mappings: Any) -> dict[str, Any]:
    cleaned = _sanitize_color_mappings(mode, mappings)
    cleaned.update(_extract_color_profile_assets(mappings))
    return cleaned


POOL_NUMBER_TO_COLOR_STYLE: dict[int, tuple[str, str]] = {
    1: ("Yellow", "Solid"),
    2: ("Blue", "Solid"),
    3: ("Red", "Solid"),
    4: ("Purple", "Solid"),
    5: ("Orange", "Solid"),
    6: ("Green", "Solid"),
    7: ("Brown", "Solid"),
    8: ("Black", "Solid"),
    9: ("Yellow", "Stripe"),
    10: ("Blue", "Stripe"),
    11: ("Red", "Stripe"),
    12: ("Purple", "Stripe"),
    13: ("Orange", "Stripe"),
    14: ("Green", "Stripe"),
    15: ("Brown", "Stripe"),
}


def _ball_identity_from_number(number: Any) -> dict[str, Any]:
    try:
        number_i = int(number)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="number must be integer")
    if number_i == 0:
        return {"number": 0, "color": "White", "style": "Cue"}
    if number_i not in POOL_NUMBER_TO_COLOR_STYLE:
        raise HTTPException(status_code=400, detail=f"Unsupported ball number: {number_i}")
    color, style = POOL_NUMBER_TO_COLOR_STYLE[number_i]
    return {"number": number_i, "color": color, "style": style}


MANUAL_IDENTITY_LOCK_TTL_SEC = 600.0
MANUAL_IDENTITY_LOCK_MAX_MISS = 45
manual_ball_identity_locks: list[dict[str, Any]] = []
manual_ball_identity_lock_guard = threading.Lock()


def _ball_bbox_center_radius(ball: Any) -> tuple[float, float, float] | None:
    if not isinstance(ball, dict):
        return None
    try:
        x = float(ball.get("x"))
        y = float(ball.get("y"))
        w = float(ball.get("w"))
        h = float(ball.get("h"))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
        return None
    return x + w / 2.0, y + h / 2.0, max(w, h) / 2.0


def _add_manual_ball_identity_lock(
    *,
    profile_id: int,
    sample_id: str,
    index: int,
    identity: dict[str, Any],
    ball: dict[str, Any],
    source_frame_id: Any,
) -> dict[str, Any] | None:
    center = _ball_bbox_center_radius(ball)
    if center is None:
        return None
    cx, cy, radius = center
    now = time.time()
    lock = {
        "profile_id": int(profile_id),
        "sample_id": str(sample_id),
        "created_at": now,
        "updated_at": now,
        "expires_at": now + MANUAL_IDENTITY_LOCK_TTL_SEC,
        "source_frame_id": source_frame_id,
        "source_index": int(index),
        "cx": float(cx),
        "cy": float(cy),
        "r": float(max(8.0, radius)),
        "miss_count": 0,
        "number": int(identity["number"]),
        "color": str(identity["color"]),
        "style": str(identity["style"]),
    }
    with manual_ball_identity_lock_guard:
        manual_ball_identity_locks[:] = [
            item
            for item in manual_ball_identity_locks
            if not (
                int(item.get("profile_id", -1)) == int(profile_id)
                and int(item.get("number", -1)) == int(identity["number"])
            )
        ]
        manual_ball_identity_locks.append(lock)
    return dict(lock)


def _seed_manual_identity_locks_from_sample_sets(profile_id: int, mappings: Any) -> int:
    if not isinstance(mappings, dict):
        return 0
    sample_sets = mappings.get("_sample_sets")
    if not isinstance(sample_sets, dict):
        return 0

    latest_by_number: dict[int, dict[str, Any]] = {}
    for samples in sample_sets.values():
        if not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            try:
                number = int(sample.get("actual_number"))
            except (TypeError, ValueError):
                continue
            if number <= 0:
                continue
            bbox = sample.get("source_bbox")
            if not isinstance(bbox, list) or len(bbox) < 4:
                continue
            previous = latest_by_number.get(number)
            if previous is None or str(sample.get("captured_at") or "") >= str(previous.get("captured_at") or ""):
                latest_by_number[number] = sample

    seeded = 0
    for number, sample in latest_by_number.items():
        try:
            identity = _ball_identity_from_number(number)
        except HTTPException:
            continue
        bbox = sample.get("source_bbox")
        ball = {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]} if isinstance(bbox, list) else {}
        lock = _add_manual_ball_identity_lock(
            profile_id=profile_id,
            sample_id=str(sample.get("id") or f"seed-{profile_id}-{number}"),
            index=int(sample.get("index") or -1),
            identity=identity,
            ball=ball,
            source_frame_id=sample.get("source_frame_id"),
        )
        if lock is not None:
            seeded += 1
    return seeded


def _remove_manual_ball_identity_locks(
    *,
    profile_id: int,
    sample_ids: set[str] | None = None,
    colors: set[str] | None = None,
    clear_all: bool = False,
) -> int:
    removed = 0
    with manual_ball_identity_lock_guard:
        kept: list[dict[str, Any]] = []
        for lock in manual_ball_identity_locks:
            if int(lock.get("profile_id", -1)) != int(profile_id):
                kept.append(lock)
                continue
            should_remove = clear_all
            if sample_ids is not None and str(lock.get("sample_id")) in sample_ids:
                should_remove = True
            if colors is not None and str(lock.get("color")) in colors:
                should_remove = True
            if should_remove:
                removed += 1
            else:
                kept.append(lock)
        manual_ball_identity_locks[:] = kept
    return removed


def _apply_manual_ball_identity_locks(data_packet: Any) -> None:
    if not isinstance(data_packet, dict):
        return
    balls = data_packet.get("balls")
    if not isinstance(balls, list) or not balls:
        return

    now = time.time()
    with manual_ball_identity_lock_guard:
        active_locks = [
            lock
            for lock in manual_ball_identity_locks
            if float(lock.get("expires_at") or 0.0) > now
            and int(lock.get("miss_count") or 0) < MANUAL_IDENTITY_LOCK_MAX_MISS
        ]
        manual_ball_identity_locks[:] = active_locks

        matched_ball_indexes: set[int] = set()
        matched_lock_ids: set[str] = set()
        for lock in active_locks:
            best_index: int | None = None
            best_distance = 1_000_000.0
            lock_cx = float(lock.get("cx") or 0.0)
            lock_cy = float(lock.get("cy") or 0.0)
            lock_r = max(8.0, float(lock.get("r") or 12.0))
            match_distance = max(70.0, lock_r * 3.0)

            for index, ball in enumerate(balls):
                if index in matched_ball_indexes:
                    continue
                center = _ball_bbox_center_radius(ball)
                if center is None:
                    continue
                cx, cy, radius = center
                distance = math.hypot(cx - lock_cx, cy - lock_cy)
                if distance < best_distance and distance <= max(match_distance, radius * 2.6):
                    best_index = index
                    best_distance = distance

            if best_index is None:
                lock["miss_count"] = int(lock.get("miss_count") or 0) + 1
                continue

            ball = balls[best_index]
            if not isinstance(ball, dict):
                continue
            center = _ball_bbox_center_radius(ball)
            if center is not None:
                lock["cx"], lock["cy"], lock["r"] = float(center[0]), float(center[1]), float(max(8.0, center[2]))
            lock["updated_at"] = now
            lock["expires_at"] = now + MANUAL_IDENTITY_LOCK_TTL_SEC
            lock["miss_count"] = 0
            matched_ball_indexes.add(best_index)
            matched_lock_ids.add(str(lock.get("sample_id")))

            ball["number"] = int(lock["number"])
            ball["color"] = str(lock["color"])
            ball["style"] = str(lock["style"])
            ball["manual_identity_lock"] = {
                "sample_id": str(lock.get("sample_id")),
                "number": int(lock["number"]),
                "color": str(lock["color"]),
                "style": str(lock["style"]),
                "distance": round(float(best_distance), 3),
                "expires_in_sec": round(max(0.0, float(lock.get("expires_at") or now) - now), 3),
            }

        manual_ball_identity_locks[:] = [
            lock
            for lock in manual_ball_identity_locks
            if str(lock.get("sample_id")) in matched_lock_ids
            or int(lock.get("miss_count") or 0) < MANUAL_IDENTITY_LOCK_MAX_MISS
        ]

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

def create_error_response(error_code: str, message: object) -> dict:
    """創建標準錯誤響應"""
    message_text = str(message)
    return {
        "error_code": error_code,
        "error_message": message_text,
        "message": message_text  # 向後兼容
    }


# ✅ 性能監控輔助函數
def encode_image_buffer(frame: Any, quality: int = 70) -> Optional[bytes]:
    """在線程中編碼影像，避免阻塞 event loop"""
    try:
        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
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


CAMERA_BACKENDS: list[tuple[int, str]] = [
    (cv2.CAP_DSHOW, "DSHOW"),
    (cv2.CAP_MSMF, "MSMF"),
    (cv2.CAP_ANY, "ANY"),
]


def get_camera_backend_candidates(preferred_backend: Any = None, include_any: Optional[bool] = None) -> list[tuple[int, str]]:
    """產生相機偵測後端順序；預設避開 CAP_ANY 以免 OpenCV 掃到 obsensor 等不存在來源。"""
    backend_names = {backend_id: name for backend_id, name in CAMERA_BACKENDS}
    selected_backend = normalize_camera_backend(preferred_backend)
    any_enabled = bool(getattr(config, "CAMERA_ENABLE_ANY_BACKEND", False)) if include_any is None else include_any
    cached_backend = selected_backend
    if cached_backend is None:
        cached_backend = normalize_camera_backend(camera_state.get("last_good_backend"))
    if cached_backend is None:
        cached_backend = int(cv2.CAP_DSHOW)
    if cached_backend == cv2.CAP_ANY and selected_backend != cv2.CAP_ANY and not any_enabled:
        cached_backend = cv2.CAP_DSHOW

    ordered_ids: list[int] = [cached_backend, int(cv2.CAP_DSHOW), int(cv2.CAP_MSMF)]
    if selected_backend == cv2.CAP_ANY or any_enabled:
        ordered_ids.append(int(cv2.CAP_ANY))

    candidates: list[tuple[int, str]] = []
    seen: set[int] = set()
    for backend_id in ordered_ids:
        if backend_id in seen:
            continue
        seen.add(backend_id)
        candidates.append((backend_id, backend_names.get(backend_id, str(backend_id))))
    return candidates


def normalize_camera_backend(backend: Any) -> Optional[int]:
    if backend is None or backend == "":
        return None
    if isinstance(backend, int):
        return backend
    if isinstance(backend, str):
        upper_backend = backend.strip().upper()
        for backend_id, name in CAMERA_BACKENDS:
            if upper_backend == name:
                return backend_id
        try:
            return int(upper_backend)
        except ValueError:
            pass
    return None


def enumerate_camera_devices(max_devices: int = 10) -> list[dict[str, Any]]:
    """Probe camera devices through OpenCV instead of trusting OS device order."""
    devices: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    backend_candidates = get_camera_backend_candidates()
    for device_id in range(max_devices):
        for backend, backend_name in backend_candidates:
            cap = cv2.VideoCapture(device_id, backend)
            try:
                if not cap.isOpened():
                    continue
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue
                key = (device_id, backend)
                if key in seen:
                    continue
                seen.add(key)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                devices.append({
                    "id": device_id,
                    "device_id": device_id,
                    "backend": backend,
                    "backend_name": backend_name,
                    "name": f"Camera {device_id} / {backend_name}",
                    "resolution": f"{width}x{height}",
                    "fps": round(float(fps or 0), 2),
                    "readable": True,
                })
            finally:
                cap.release()
    return devices


def open_camera(device_id: int, preferred_backend: Any = None):
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
    selected_backend = normalize_camera_backend(preferred_backend)

    # 優先嘗試上次成功配置，重連通常可在第一輪就成功
    resolutions = []
    for profile in [cached_profile, default_profile, (1920, 1080, 50), (1280, 720, 30), (1024, 576, 30), (640, 480, 30), (800, 600, 30)]:
        if profile and profile not in resolutions:
            resolutions.append(profile)

    backends = get_camera_backend_candidates(selected_backend)

    cap: Optional[Any] = None
    for backend, _backend_name in backends:
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

                cap_candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap_candidate.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap_candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap_candidate.set(cv2.CAP_PROP_FPS, fps)

                fourcc_attempts = get_camera_fourcc_attempts()

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
                camera_state["actual_profile"] = (actual_width, actual_height, actual_fps)

                print(f"OK ({actual_width}x{actual_height}@{actual_fps}fps)")
                cap = cap_candidate
                camera_state["selected_backend"] = backend
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
    camera_state["selected_backend"] = camera_state.get("last_good_backend", cv2.CAP_DSHOW)
    return cap


def camera_backend_name(backend: Any) -> str:
    """將 OpenCV backend id 轉成可讀名稱，供效能診斷輸出。"""
    backend_map = {
        getattr(cv2, "CAP_DSHOW", None): "DSHOW",
        getattr(cv2, "CAP_MSMF", None): "MSMF",
        getattr(cv2, "CAP_ANY", None): "ANY",
        getattr(cv2, "CAP_FFMPEG", None): "FFMPEG",
    }
    return backend_map.get(backend, backend)


def video_writer_fourcc(format_name: str) -> int:
    """取用 OpenCV 動態 FOURCC 函式，避免靜態分析器誤判 cv2 沒有此屬性。"""
    fourcc_func = getattr(cv2, "VideoWriter_fourcc")
    return cast(int, fourcc_func(*format_name))


def get_camera_fourcc_attempts() -> list[tuple[str, int, str]]:
    """依設定產生 FOURCC 嘗試順序，預設優先 MJPG 以降低 USB 未壓縮讀幀延遲。"""
    descriptions = {
        "MJPG": "MJPEG 壓縮",
        "YUY2": "YUV 格式",
        "YUYV": "未壓縮格式",
    }
    attempts: list[tuple[str, int, str]] = []
    raw_priority = str(getattr(config, "CAMERA_FOURCC_PRIORITY", "MJPG,YUY2,YUYV"))
    for item in raw_priority.split(","):
        format_name = item.strip().upper()
        if format_name not in descriptions:
            continue
        if any(existing[0] == format_name for existing in attempts):
            continue
        attempts.append(
            (
                format_name,
                video_writer_fourcc(format_name),
                descriptions[format_name],
            )
        )
    return attempts or [
        ("MJPG", video_writer_fourcc("MJPG"), descriptions["MJPG"]),
        ("YUY2", video_writer_fourcc("YUY2"), descriptions["YUY2"]),
        ("YUYV", video_writer_fourcc("YUYV"), descriptions["YUYV"]),
    ]


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

def switch_camera_background(device_id: int, backend: Any = None):
    """在後台線程中切換攝像頭，完成後設置 is_switching=False"""
    try:
        print(f"Background: Starting camera switch from {camera_state['selected_device_id']} to {device_id}")
        open_camera(device_id, backend)
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
            ensure_projector_render_worker_started()
            return

        print("🚀 Lazy starting camera capture thread for burn-in stream...")
        camera_capture_thread = threading.Thread(target=camera_capture_loop, daemon=True)
        camera_capture_thread.start()
        ensure_projector_render_worker_started()


def ensure_projector_render_worker_started():
    """啟動獨立 projector render worker，避免投影渲染阻塞相機主迴圈。"""
    global projector_render_thread

    if mjpeg_manager is None or projector_renderer is None:
        return

    with projector_render_lock:
        if projector_render_thread is not None and projector_render_thread.is_alive():
            return
        projector_render_running.set()
        projector_render_thread = threading.Thread(target=projector_render_loop, daemon=True)
        projector_render_thread.start()


def projector_render_loop():
    print("🎯 Starting projector render worker...")
    last_render_time = 0.0
    while projector_render_running.is_set():
        try:
            if mjpeg_manager is None or projector_renderer is None:
                time.sleep(0.2)
                continue

            if mjpeg_manager.projector._active_connections <= 0:
                time.sleep(0.05)
                continue

            max_fps = int(getattr(config, "PROJECTOR_RENDER_MAX_FPS", 12))
            interval = 0.0 if max_fps <= 0 else 1.0 / max_fps
            now = time.time()
            if interval > 0 and now - last_render_time < interval:
                time.sleep(max(0.001, interval - (now - last_render_time)))
                continue

            render_start = time.time()
            projector_frame = projector_renderer.render()
            mjpeg_manager.update_projector(projector_frame)
            duration = time.time() - render_start
            last_render_time = time.time()

            if global_perf_monitor is not None:
                for stage_name, stage_duration in projector_renderer.get_last_stage_timings().items():
                    global_perf_monitor.record_stage(
                        stage_name,
                        stage_duration,
                        global_perf_monitor.total_frames,
                    )
                global_perf_monitor.record_stage(
                    "projector_render_worker",
                    duration,
                    global_perf_monitor.total_frames,
                )
        except Exception as e:
            print(f"⚠️ Projector render worker error: {e}")
            time.sleep(0.1)
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


def _transform_point_for_ar(point: Any) -> list[int] | None:
    if calibrator is None or not calibrator.has_homography():
        return None
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        raw_point = [[float(point[0]), float(point[1])]]
    except (TypeError, ValueError):
        return None
    transformed = calibrator.transform_points(raw_point)
    if not transformed:
        return None
    return transformed[0]


def _transform_zone_for_ar(zone: Any) -> dict[str, Any] | None:
    if not isinstance(zone, dict):
        return None

    center = zone.get("center")
    transformed_center = _transform_point_for_ar(center)
    if transformed_center is None or not isinstance(center, (list, tuple)) or len(center) < 2:
        return None

    transformed_zone = dict(zone)
    transformed_zone["center"] = transformed_center

    cx = 0.0
    cy = 0.0
    try:
        cx = float(center[0])
        cy = float(center[1])
        radius = float(zone.get("radius", 0.0) or 0.0)
    except (TypeError, ValueError):
        radius = 0.0

    if radius > 0:
        radius_samples: list[float] = []
        for offset in ((radius, 0.0), (0.0, radius)):
            sample = _transform_point_for_ar([cx + offset[0], cy + offset[1]])
            if sample is None:
                continue
            radius_samples.append(math.hypot(sample[0] - transformed_center[0], sample[1] - transformed_center[1]))
        if radius_samples:
            transformed_zone["radius"] = round(sum(radius_samples) / len(radius_samples))

    return transformed_zone


def _transform_position_play_for_ar(position_play: Any) -> dict[str, Any] | None:
    if not isinstance(position_play, dict):
        return None

    transformed = dict(position_play)
    next_ball = position_play.get("next_ball")
    if isinstance(next_ball, dict):
        transformed_next_ball = dict(next_ball)
        center = _transform_point_for_ar(next_ball.get("center"))
        if center is not None:
            transformed_next_ball["center"] = center
        transformed["next_ball"] = transformed_next_ball

    cue_after = position_play.get("cue_ball_after_contact")
    if isinstance(cue_after, dict):
        transformed_cue_after = dict(cue_after)
        expected_point = _transform_point_for_ar(cue_after.get("expected_point"))
        if expected_point is not None:
            transformed_cue_after["expected_point"] = expected_point

        transformed_cue_after["target_zone"] = _transform_zone_for_ar(cue_after.get("target_zone"))
        transformed_cue_after["avoid_zones"] = [
            transformed_zone
            for zone in cue_after.get("avoid_zones", []) or []
            if (transformed_zone := _transform_zone_for_ar(zone)) is not None
        ]
        transformed["cue_ball_after_contact"] = transformed_cue_after

    return transformed


def _transform_route_summary_for_ar(route: Any) -> dict[str, Any] | None:
    if not isinstance(route, dict):
        return None

    transformed = dict(route)
    transformed_segments: list[dict[str, Any]] = []
    raw_segments = route.get("route_segments") or []
    if isinstance(raw_segments, list):
        for segment in raw_segments:
            if not isinstance(segment, dict):
                continue
            raw_points = segment.get("points") or []
            if not isinstance(raw_points, list) or len(raw_points) <= 1:
                continue
            points = calibrator.transform_points(raw_points) if calibrator is not None else []
            if not points or len(points) <= 1:
                continue
            transformed_segments.append(
                {
                    "type": f"lookahead_{segment.get('type', 'unknown')}",
                    "points": points,
                    "color": segment.get("color"),
                }
            )
    transformed["route_segments"] = transformed_segments
    transformed["cue_landing_point"] = _transform_point_for_ar(route.get("cue_landing_point"))
    transformed["cue_landing_zone"] = _transform_zone_for_ar(route.get("cue_landing_zone"))
    transformed["cue_target_zone"] = _transform_zone_for_ar(route.get("cue_target_zone"))
    return transformed


def _transform_lookahead_for_ar(lookahead: Any) -> dict[str, Any] | None:
    if not isinstance(lookahead, dict):
        return None

    transformed = dict(lookahead)
    next_routes = []
    for route in lookahead.get("next_routes", []) or []:
        transformed_route = _transform_route_summary_for_ar(route)
        if transformed_route is not None:
            next_routes.append(transformed_route)
    transformed["next_routes"] = next_routes
    return transformed


def transform_best_route_for_ar(data_packet: dict[str, Any]) -> dict[str, Any]:
    """將最佳路線、母球落點與 position_play 轉成投影機座標。"""
    payload: dict[str, Any] = {
        "route_segments": transform_route_segments_for_ar(data_packet),
        "cue_landing_point": None,
        "cue_landing_zone": None,
        "position_play": None,
        "lookahead": None,
    }
    if calibrator is None or not calibrator.has_homography():
        return payload

    multi_plan = data_packet.get("multi_plan")
    if not isinstance(multi_plan, dict):
        return payload

    best_route = multi_plan.get("best_route")
    if not isinstance(best_route, dict):
        return payload

    payload["cue_landing_point"] = _transform_point_for_ar(best_route.get("cue_landing_point"))
    payload["cue_landing_zone"] = _transform_zone_for_ar(best_route.get("cue_landing_zone"))
    payload["position_play"] = _transform_position_play_for_ar(best_route.get("position_play"))
    metadata = best_route.get("metadata")
    if isinstance(metadata, dict):
        payload["lookahead"] = _transform_lookahead_for_ar(metadata.get("lookahead"))
    return payload


def _ghost_balls_from_ar_best_route(ar_best_route: dict[str, Any]) -> list[dict[str, Any]]:
    """依目前 AR route 的母球撞擊線重建撞擊點，避免切換路線後沿用舊 ghost ball。"""
    route_segments = ar_best_route.get("route_segments")
    if not isinstance(route_segments, list):
        return []

    for segment in route_segments:
        if not isinstance(segment, dict) or segment.get("type") != "cue_to_contact":
            continue
        points = segment.get("points")
        if not isinstance(points, list) or len(points) < 2:
            continue
        contact_point = points[-1]
        if not isinstance(contact_point, (list, tuple)) or len(contact_point) < 2:
            continue
        try:
            return [{"x": int(contact_point[0]), "y": int(contact_point[1]), "r": 18}]
        except (TypeError, ValueError):
            return []

    return []


def _publish_route_projection(ar_best_route: dict[str, Any], source: str = "planner") -> None:
    if projector_renderer is None or not isinstance(ar_best_route, dict):
        return
    projector_renderer.set_mode(ProjectorMode.PRACTICE)
    projector_renderer.update_ar_data(
        {
            "trajectories": [],
            "route_segments": ar_best_route.get("route_segments", []) or [],
            "aim_lines": [],
            "ghost_balls": _ghost_balls_from_ar_best_route(ar_best_route),
            "cue_landing_point": ar_best_route.get("cue_landing_point"),
            "cue_landing_zone": ar_best_route.get("cue_landing_zone"),
            "position_play": ar_best_route.get("position_play"),
            "lookahead": ar_best_route.get("lookahead"),
            "allow_legacy_aim_lines": False,
            "allow_legacy_trajectories": False,
            "ar_source": source,
            "ar_timestamp": time.time(),
            "projector_status": "planner_route",
        }
    )


_PROJECTOR_MANUAL_ROUTE_SOURCES = {"planner_plan", "planner_select_route", "planner_stroke"}


def _projector_should_hold_manual_route() -> bool:
    """手動 planner 投影不可被下一幀空 live_yolo 結果立即清掉。"""
    if projector_renderer is None:
        return False
    ar_data = getattr(projector_renderer, "ar_data", None)
    if not isinstance(ar_data, dict):
        return False
    if str(ar_data.get("ar_source") or "") not in _PROJECTOR_MANUAL_ROUTE_SOURCES:
        return False
    has_visible_route = bool(
        ar_data.get("route_segments")
        or ar_data.get("trajectories")
        or ar_data.get("aim_lines")
        or ar_data.get("ghost_balls")
        or ar_data.get("cue_landing_point")
        or ar_data.get("cue_landing_zone")
        or ar_data.get("position_play")
        or ar_data.get("lookahead")
    )
    if not has_visible_route:
        return False
    hold_ms = int(
        getattr(
            config,
            "PROJECTOR_MANUAL_ROUTE_HOLD_MS",
            getattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", 5000),
        )
    )
    if hold_ms <= 0:
        return True
    timestamp = ar_data.get("ar_timestamp")
    if not isinstance(timestamp, (int, float)) or timestamp <= 0:
        return False
    return (time.time() - float(timestamp)) * 1000.0 <= hold_ms


def _projector_should_hold_selected_route() -> bool:
    """手動切換路徑後，短暫保護投影避免被下一幀舊 live best route 蓋回去。"""
    if projector_renderer is None:
        return False
    ar_data = getattr(projector_renderer, "ar_data", None)
    if not isinstance(ar_data, dict):
        return False
    if str(ar_data.get("ar_source") or "") != "planner_select_route":
        return False
    if not ar_data.get("route_segments"):
        return False
    hold_ms = int(
        getattr(
            config,
            "PROJECTOR_MANUAL_ROUTE_HOLD_MS",
            getattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", 5000),
        )
    )
    if hold_ms <= 0:
        return True
    timestamp = ar_data.get("ar_timestamp")
    if not isinstance(timestamp, (int, float)) or timestamp <= 0:
        return False
    return (time.time() - float(timestamp)) * 1000.0 <= hold_ms


def transform_table_roi_for_ar(data_packet: dict[str, Any]) -> list[list[int]]:
    """將相機 table_roi 四角轉換為投影機座標，用於貼合球桌的警示框。"""
    if calibrator is None or not calibrator.has_homography():
        return []
    roi = data_packet.get("table_roi")
    if not isinstance(roi, list) or len(roi) < 4:
        return []
    try:
        x, y, w, h = [v for v in roi[:4]]
    except (TypeError, ValueError):
        return []
    if w <= 0 or h <= 0:
        return []
    corners = [
        [x, y],
        [x + w, y],
        [x + w, y + h],
        [x, y + h],
    ]
    points = calibrator.transform_points(corners)
    if not points or len(points) != 4:
        return []
    return points


def _route_terminal_bucket_from_dict(route: dict[str, Any], step: float = 24.0) -> tuple[int, int] | None:
    path_points = route.get("path_points")
    if isinstance(path_points, list) and path_points:
        point = path_points[-1]
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                return (round(float(point[0]) / step), round(float(point[1]) / step))
            except (TypeError, ValueError):
                return None
    return None


def _route_intent_key_from_dict(route: Any) -> tuple[Any, ...] | None:
    if not isinstance(route, dict):
        return None
    metadata = route.get("metadata") if isinstance(route.get("metadata"), dict) else {}
    route_class = metadata.get("route_class")
    route_type = route.get("route_type")
    if not route_class:
        route_class = "contact_only" if route_type in {"safe_escape", "contact_only", "kick_escape"} else "potting_route"
    return (
        route_class,
        route_type,
        route.get("target_ball_number"),
        route.get("first_contact_ball_number"),
        metadata.get("combo_second_ball_number"),
        metadata.get("target_pocket_id"),
        metadata.get("rail"),
        metadata.get("kick_bounces"),
        _route_terminal_bucket_from_dict(route),
    )


def _route_stable_intent_key_from_dict(route: Any) -> tuple[Any, ...] | None:
    key = _route_intent_key_from_dict(route)
    if key is None:
        return None
    return key[:-1]


def _select_route_in_plan(plan: dict[str, Any], route_id: str, route_hint: Any = None) -> dict[str, Any]:
    routes = plan.get("routes")
    if not isinstance(routes, list):
        return plan

    selected_route = next(
        (route for route in routes if isinstance(route, dict) and route.get("id") == route_id),
        None,
    )
    if selected_route is None:
        route_hint_key = _route_intent_key_from_dict(route_hint)
        if route_hint_key is not None:
            selected_route = next(
                (
                    route
                    for route in routes
                    if isinstance(route, dict) and _route_intent_key_from_dict(route) == route_hint_key
                ),
                None,
            )
    if selected_route is None:
        route_hint_key = _route_stable_intent_key_from_dict(route_hint)
        if route_hint_key is not None:
            selected_route = next(
                (
                    route
                    for route in routes
                    if isinstance(route, dict) and _route_stable_intent_key_from_dict(route) == route_hint_key
                ),
                None,
            )
    if selected_route is None:
        return plan

    return {**plan, "best_route": selected_route, "selected_route_id": selected_route.get("id") or route_id}


def _power_bucket_from_percent(power_percent: float) -> str:
    if power_percent <= 25:
        return "low"
    if power_percent <= 50:
        return "medium"
    if power_percent <= 75:
        return "medium_high"
    return "high"


def _sanitize_stroke_override(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    tip = str(raw.get("tip", "center")).strip().lower()
    power = str(raw.get("power", "medium")).strip().lower()
    power_percent: float | None = None
    tip_x: float | None = None
    tip_y: float | None = None
    try:
        if raw.get("power_percent") is not None:
            power_percent = max(1.0, min(100.0, float(raw.get("power_percent"))))
    except (TypeError, ValueError):
        power_percent = None
    try:
        if raw.get("tip_x") is not None:
            tip_x = max(-1.0, min(1.0, float(raw.get("tip_x"))))
        if raw.get("tip_y") is not None:
            tip_y = max(-1.0, min(1.0, float(raw.get("tip_y"))))
    except (TypeError, ValueError):
        tip_x = None
        tip_y = None
    if tip not in {"center", "top", "draw", "low", "left", "right", "top_left", "top_right", "draw_left", "draw_right"}:
        tip = "center"
    if power_percent is not None:
        power = _power_bucket_from_percent(power_percent)
    if power not in {"low", "medium", "medium_high", "high"}:
        power = "medium"
    stroke: dict[str, Any] = {"tip": tip, "power": power}
    if power_percent is not None:
        stroke["power_percent"] = round(power_percent)
    if tip_x is not None and tip_y is not None:
        stroke["tip_x"] = round(tip_x, 3)
        stroke["tip_y"] = round(tip_y, 3)
    return stroke


def _sanitize_lookahead_request(request: dict[str, Any]) -> dict[str, Any]:
    """清理 planner lookahead 參數，避免前端輸入讓規劃成本失控。"""
    def _int_value(key: str, default: int, low: int, high: int) -> int:
        try:
            return max(low, min(high, int(request.get(key, default))))
        except (TypeError, ValueError):
            return default

    def _float_value(key: str, default: float, low: float, high: float) -> float:
        try:
            return max(low, min(high, float(request.get(key, default))))
        except (TypeError, ValueError):
            return default

    return {
        "lookahead_enabled": bool(request.get("lookahead_enabled", False)),
        "lookahead_ply": _int_value("lookahead_ply", 2, 1, 2),
        "lookahead_candidate_count": _int_value("lookahead_candidate_count", 5, 1, 8),
        "lookahead_next_top_n": _int_value("lookahead_next_top_n", 3, 1, 5),
        "lookahead_score_weight": _float_value("lookahead_score_weight", 0.25, 0.0, 0.6),
    }


def _configure_tracker_lookahead(lookahead_options: dict[str, Any]) -> None:
    if tracker is None or not hasattr(tracker, "configure_route_lookahead"):
        return
    tracker.configure_route_lookahead(
        enabled=bool(lookahead_options.get("lookahead_enabled")),
        ply=int(lookahead_options.get("lookahead_ply", 2)),
        candidate_count=int(lookahead_options.get("lookahead_candidate_count", 5)),
        next_top_n=int(lookahead_options.get("lookahead_next_top_n", 3)),
        score_weight=float(lookahead_options.get("lookahead_score_weight", 0.25)),
    )


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
            x = max(0, min(1920, round(float(raw_point[0]))))
            y = max(0, min(1080, round(float(raw_point[1]))))
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
            ghost_radius = max(8, min(80, round(float(raw_ghost.get("r", 24) or 24))))
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
                    "cue_landing_zone": None,
                    "position_play": None,
                    "lookahead": None,
                    "cue_laser_lines": [],
                    "ar_source": "pattern_static",
                    "ar_timestamp": time.time(),
                    "cue_laser_source": "pattern_static",
                    "cue_laser_timestamp": time.time(),
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
                projected_radius = round((rx + ry) / 2.0)
                return max(14, min(56, projected_radius))

        bounds = DEFAULT_BOUNDS
        if calibrator is not None and calibrator.projection_bounds:
            bounds = calibrator.projection_bounds
        return max(14, min(56, round(float(bounds["width"]) * 0.026 / 2.0)))

    def normalize_relative_point(rx: float, ry: float) -> tuple[float, float]:
        table_rx = max(0.0, min(1.0, rx))
        table_ry = max(0.0, min(1.0, ry))
        return table_rx, table_ry

    def to_proj(rx: float, ry: float) -> list[int]:
        """0~1 相對座標 → 投影機絕對座標（優先套用相機校正）。"""
        table_rx, table_ry = normalize_relative_point(rx, ry)
        if calibrator is not None and calibrator.has_homography() and table_roi:
            tx, ty, tw, th = table_roi
            camera_point = [[tx + table_rx * tw, ty + table_ry * th]]
            transformed = calibrator.transform_points(camera_point)
            if transformed:
                return [int(transformed[0][0]), int(transformed[0][1])]

        bounds = DEFAULT_BOUNDS
        if calibrator is not None and calibrator.projection_bounds:
            bounds = calibrator.projection_bounds
        x = int(bounds["x"] + table_rx * int(bounds["width"]))
        y = int(bounds["y"] + table_ry * int(bounds["height"]))
        return [x, y]

    def to_camera(rx: float, ry: float) -> list[int] | None:
        """0~1 相對座標 → 相機全圖座標，供 YOLO 偽影過濾使用。"""
        if not table_roi:
            return None
        table_rx, table_ry = normalize_relative_point(rx, ry)
        tx, ty, tw, th = table_roi
        return [int(tx + table_rx * tw), int(ty + table_ry * th)]

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
            raw_points = seg.get("points", [])
            seg_type = str(seg.get("type", ""))
            converted_pts = [convert_point(p) for p in raw_points]
            if len(converted_pts) >= 2:
                proj_segments.append({"type": seg_type, "points": converted_pts})

            camera_pts = [p for p in (convert_camera_point(p) for p in raw_points) if p]
            if len(camera_pts) >= 2:
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
            "cue_landing_zone": None,
            "position_play": None,
            "lookahead": None,
            "cue_laser_lines": [],
            "ar_source": "pattern_static",
            "ar_timestamp": time.time(),
            "cue_laser_source": "pattern_static",
            "cue_laser_timestamp": time.time(),
        }
    )


def set_route_planner_runtime(enabled: bool, rule_profile: str = "practice"):
    """切換即時多球規劃；關閉時同步清掉舊 metadata 與 AR 投影路線。"""
    if tracker is not None:
        tracker.set_route_planner_enabled(enabled)
        tracker.set_route_rule_profile(rule_profile)
        if not enabled:
            tracker.set_selected_route_id(None)
            if hasattr(tracker, "set_route_target_ball_number"):
                tracker.set_route_target_ball_number(None)
            if hasattr(tracker, "set_route_stroke_override"):
                tracker.set_route_stroke_override(None)

    if not enabled:
        if tracker is not None and hasattr(tracker, "set_manual_projected_artifacts"):
            tracker.set_manual_projected_artifacts(None)
        latest_analysis_data["multi_plan"] = None
        latest_analysis_data["planner_error"] = None
        latest_analysis_data["ar_route_segments"] = []
        latest_analysis_data["ar_best_route"] = {
            "route_segments": [],
            "cue_landing_point": None,
            "cue_landing_zone": None,
            "position_play": None,
            "lookahead": None,
        }

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
                    "cue_landing_zone": None,
                    "position_play": None,
                    "lookahead": None,
                    "cue_laser_lines": [],
                    "ar_source": "live_yolo",
                    "ar_timestamp": time.time(),
                    "cue_laser_source": "live_yolo",
                    "cue_laser_timestamp": time.time(),
                }
            )


def clear_practice_route_guides() -> None:
    """清掉一般練習的舊 planner 路線，但保留即時 planner 繼續為下一桿重算。"""
    reset_practice_route_planner_state()
    latest_analysis_data["multi_plan"] = None
    latest_analysis_data["planner_error"] = None
    latest_analysis_data["ar_route_segments"] = []
    latest_analysis_data["ar_best_route"] = {
        "route_segments": [],
        "cue_landing_point": None,
        "cue_landing_zone": None,
        "position_play": None,
        "lookahead": None,
    }
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
                "cue_landing_point": None,
                "cue_landing_zone": None,
                "position_play": None,
                "lookahead": None,
                "allow_legacy_aim_lines": False,
                "allow_legacy_trajectories": False,
                "ar_source": "practice_shot_result",
                "ar_timestamp": time.time(),
                "projector_status": "waiting_for_route",
            }
        )


def reset_practice_route_planner_state() -> None:
    """重置上一桿的 planner 選線與 hold 快取，但不關閉即時 planner。"""
    if tracker is not None:
        tracker.set_selected_route_id(None)
        if hasattr(tracker, "set_route_target_ball_number"):
            tracker.set_route_target_ball_number(None)
        if hasattr(tracker, "set_route_stroke_override"):
            tracker.set_route_stroke_override(None)
        if hasattr(tracker, "set_route_rule_profile"):
            tracker.set_route_rule_profile("practice")
        if hasattr(tracker, "_route_plan_missing_frames"):
            tracker._route_plan_missing_frames = 0
        route_planner = getattr(tracker, "route_planner", None)
        if route_planner is not None:
            if hasattr(route_planner, "last_plan"):
                route_planner.last_plan = None
            if hasattr(route_planner, "last_error"):
                route_planner.last_error = None
            if hasattr(route_planner, "_last_state_hash"):
                route_planner._last_state_hash = None
            if hasattr(route_planner, "_last_state_hash_plan"):
                route_planner._last_state_hash_plan = None
            if hasattr(route_planner, "_held_target_number"):
                route_planner._held_target_number = None
            if hasattr(route_planner, "_held_target_miss_frames"):
                route_planner._held_target_miss_frames = 0


def restore_live_annotation_mode() -> None:
    """回到即時影像工作流時，恢復完整球號與球桌標註。"""
    config.TRACKER_ANNOTATION_MODE = "full"


def _is_yolo_stalled() -> bool:
    if bool(system_state.get("yolo_stalled")):
        return True
    data_packet = latest_analysis_data.get("data") if isinstance(latest_analysis_data, dict) else None
    return isinstance(data_packet, dict) and data_packet.get("status") == "yolo_stalled"


def ensure_live_analysis_for_coach() -> bool:
    """AI Coach 需要穩定檯面資料；使用期間維持即時辨識與完整 overlay。"""
    restore_live_annotation_mode()
    if _is_yolo_stalled():
        return False
    ensure_camera_capture_started()
    system_state["yolo_skip_frames"] = 0
    system_state["is_analyzing"] = True
    if tracker is not None:
        tracker.set_aim_assist(False)
        if hasattr(tracker, "set_cue_laser_only"):
            tracker.set_cue_laser_only(False)
    return True


def _build_game_timer_projection_data() -> dict[str, Any]:
    """建立投影機遊玩模式倒數計時資料。"""
    state = game_manager.game_state
    if not state or not state.is_active:
        return {
            "enabled": False,
            "shot_time_limit": 0,
            "remaining_time": 0,
            "current_player": 1,
            "foul_detected": False,
            "foul_reason": None,
            "updated_at": time.time(),
        }
    return {
        "enabled": state.shot_time_limit > 0 or state.foul_detected,
        "shot_time_limit": state.shot_time_limit,
        "remaining_time": state.remaining_time,
        "current_player": state.current_player,
        "foul_detected": state.foul_detected,
        "foul_reason": state.foul_reason,
        "updated_at": float(state.last_update_time or time.time()),
    }


def _sync_game_timer_projection() -> None:
    """同步遊玩模式倒數計時到投影端。"""
    if projector_renderer is not None:
        projector_renderer.update_ar_data({"game_timer": _build_game_timer_projection_data()})


def _empty_projector_dynamic_ar_data(ar_source: str = "live_yolo") -> dict[str, Any]:
    """清空即時路線/雷射資料，避免投影端保留上一筆不同幀的 AR guide。"""
    now = time.time()
    return {
        "trajectories": [],
        "route_segments": [],
        "aim_lines": [],
        "ghost_balls": [],
        "cue_landing_point": None,
        "cue_landing_zone": None,
        "position_play": None,
        "lookahead": None,
        "cue_laser_lines": [],
        "allow_legacy_aim_lines": False,
        "allow_legacy_trajectories": False,
        "ar_source": ar_source,
        "ar_timestamp": now,
        "cue_laser_source": ar_source,
        "cue_laser_timestamp": now,
        "projector_status": "waiting_for_route",
    }


try:
    import api.calibration_api as calib_api
    setattr(calib_api, "set_route_planner_runtime", set_route_planner_runtime)
except Exception:
    pass


def _has_drawable_overlay_data(data_packet: Any) -> bool:
    """判斷 metadata 是否值得覆蓋最後一筆可畫標註。"""
    if not isinstance(data_packet, dict):
        return False

    multi_plan = data_packet.get("multi_plan")
    if isinstance(multi_plan, dict) and isinstance(multi_plan.get("best_route"), dict):
        return True

    prediction = data_packet.get("prediction")
    if isinstance(prediction, dict) and len(prediction.get("paths") or []) >= 2:
        return True

    table_roi = data_packet.get("table_roi")
    if isinstance(table_roi, (list, tuple)) and len(table_roi) >= 4:
        return True

    holes = data_packet.get("holes")
    if isinstance(holes, list) and len(holes) > 0:
        return True

    # 外框、白球或子球任一項可畫時，都保留給 overlay renderer 使用。
    return bool(data_packet.get("white_ball")) or bool(data_packet.get("balls"))


def _overlay_metadata_age_ms(data_packet: Any, fallback_timestamp: Any = None) -> float | None:
    """回傳 metadata 對應原始影像的年齡，避免用推論完成時間誤判為新資料。"""
    if isinstance(data_packet, dict) and isinstance(data_packet.get("_source_timestamp"), (int, float)):
        return (time.time() - float(data_packet["_source_timestamp"])) * 1000.0
    if isinstance(fallback_timestamp, (int, float)) and fallback_timestamp > 0:
        return (time.time() - float(fallback_timestamp)) * 1000.0
    return None


def _overlay_metadata_frame_lag(data_packet: Any, current_frame_id: int) -> int | None:
    if not isinstance(data_packet, dict):
        return None
    source_frame_id = data_packet.get("_source_frame_id")
    if not isinstance(source_frame_id, (int, float)):
        return None
    return max(0, int(current_frame_id) - int(source_frame_id))


def _has_projector_dynamic_guides(
    ar_paths: list[Any],
    ar_route_segments: list[Any],
    ar_aim_lines: list[Any],
    ar_ghost_balls: list[Any],
    ar_cue_laser_lines: list[Any],
) -> bool:
    """避免空 YOLO 結果覆蓋上一筆有效 projector AR。"""
    return bool(ar_route_segments or ar_paths or ar_aim_lines or ar_ghost_balls or ar_cue_laser_lines)


def _reset_game_auto_tracking_state() -> None:
    game_tracking_state.update({
        "is_shot_in_progress": False,
        "last_white_pos": None,
        "last_balls": [],
        "shot_start_balls": [],
        "shot_start_white_pos": None,
        "first_contact": None,
        "potted_balls": [],
        "missing_ball_frames": {},
        "disappearance_ball_frames": {},
        "last_cue_radius": 0.0,
        "still_frames": 0,
        "shot_frames": 0,
        "cue_missing_frames": 0,
        "cue_in_hole_frames": 0,
        "cue_was_in_hole": False,
        "cue_ball_potted": False,
        "start_motion_frames": 0,
        "visual_seen_counts": {},
        "visual_missing_counts": {},
        "last_visual_remaining": [],
    })


def _angle_degrees(start: Any, end: Any) -> float | None:
    if not (
        isinstance(start, (list, tuple)) and len(start) >= 2
        and isinstance(end, (list, tuple)) and len(end) >= 2
    ):
        return None
    try:
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
    except (TypeError, ValueError):
        return None
    if abs(dx) < 0.001 and abs(dy) < 0.001:
        return None
    return math.degrees(math.atan2(dy, dx))


def _ideal_angle_from_plan(multi_plan: Any) -> float | None:
    if not isinstance(multi_plan, dict):
        return None
    best_route = multi_plan.get("best_route") if isinstance(multi_plan.get("best_route"), dict) else {}
    segments = best_route.get("route_segments") if isinstance(best_route.get("route_segments"), list) else []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        points = segment.get("points") if isinstance(segment.get("points"), list) else []
        if len(points) >= 2:
            angle = _angle_degrees(points[0], points[1])
            if angle is not None:
                return angle
    points = best_route.get("path_points") if isinstance(best_route.get("path_points"), list) else []
    if len(points) >= 2:
        return _angle_degrees(points[0], points[1])
    return None


def _build_coach_shot_event(
    *,
    result: dict[str, Any],
    start_white: Any,
    end_white: Any,
    shot_frames: int,
    multi_plan: Any,
) -> dict[str, Any]:
    actual_angle = _angle_degrees(start_white, end_white)
    ideal_angle = _ideal_angle_from_plan(multi_plan)
    distance = 0.0
    if isinstance(start_white, (list, tuple)) and isinstance(end_white, (list, tuple)):
        try:
            distance = math.hypot(float(end_white[0]) - float(start_white[0]), float(end_white[1]) - float(start_white[1]))
        except (TypeError, ValueError):
            distance = 0.0
    velocity_change = min(1.0, distance / max(float(shot_frames or 1) * 12.0, 1.0))
    potted_balls = result.get("potted_balls") if isinstance(result.get("potted_balls"), list) else []
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "impact_angle": actual_angle,
        "ideal_angle": ideal_angle,
        "velocity_change": round(velocity_change, 3),
        "pocket_result": "made" if potted_balls else "missed",
        "first_contact": result.get("first_contact"),
        "potted_balls": potted_balls,
        "cue_ball_potted": result.get("cue_ball_potted"),
        "is_foul": result.get("is_foul"),
        "foul_reason": result.get("foul_reason"),
        "ball_diameter": 57.2,
    }


def _normalize_angle_delta(actual_angle: float | None, ideal_angle: float | None) -> float | None:
    if actual_angle is None or ideal_angle is None:
        return None
    delta = float(actual_angle) - float(ideal_angle)
    while delta > 180:
        delta -= 360
    while delta < -180:
        delta += 360
    return delta


def _classify_thickness(actual_angle: float | None, ideal_angle: float | None) -> str:
    delta = _normalize_angle_delta(actual_angle, ideal_angle)
    if delta is None:
        return "unknown"
    if abs(delta) <= 5:
        return "on_line"
    return "too_thick" if delta > 0 else "too_thin"


def _point_payload(point: Any) -> list[float] | None:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        return [round(float(point[0]), 2), round(float(point[1]), 2)]
    except (TypeError, ValueError):
        return None


def _point_distance(a: Any, b: Any) -> float | None:
    pa = _point_payload(a)
    pb = _point_payload(b)
    if pa is None or pb is None:
        return None
    return round(math.hypot(pb[0] - pa[0], pb[1] - pa[1]), 2)


def _best_route_from_plan(multi_plan: Any) -> dict[str, Any]:
    if not isinstance(multi_plan, dict):
        return {}
    best_route = multi_plan.get("best_route") if isinstance(multi_plan.get("best_route"), dict) else {}
    return best_route


def _distance_bucket_from_route(best_route: dict[str, Any]) -> str:
    try:
        distance = float(best_route.get("total_distance"))
    except (TypeError, ValueError):
        return "unknown"
    if distance <= 650:
        return "near"
    if distance <= 1350:
        return "mid"
    return "far"


def _position_success_from_route(best_route: dict[str, Any]) -> float | None:
    position_play = best_route.get("position_play") if isinstance(best_route.get("position_play"), dict) else {}
    score = position_play.get("score") if isinstance(position_play.get("score"), dict) else {}
    value = score.get("position_success_prob")
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _planned_cue_landing_from_route(best_route: dict[str, Any]) -> list[float] | None:
    landing = _point_payload(best_route.get("cue_landing_point"))
    if landing is not None:
        return landing
    position_play = best_route.get("position_play") if isinstance(best_route.get("position_play"), dict) else {}
    cue_after = position_play.get("cue_ball_after_contact") if isinstance(position_play.get("cue_ball_after_contact"), dict) else {}
    return _point_payload(cue_after.get("center"))


def _next_ball_quality_from_route(best_route: dict[str, Any]) -> str | None:
    position_play = best_route.get("position_play") if isinstance(best_route.get("position_play"), dict) else {}
    score = position_play.get("score") if isinstance(position_play.get("score"), dict) else {}
    try:
        value = float(score.get("position_success_prob"))
    except (TypeError, ValueError):
        return None
    if value >= 0.66:
        return "good"
    if value >= 0.42:
        return "ok"
    return "poor"


def _current_recording_game_id() -> str | None:
    current = getattr(recording_manager, "current_recording", None)
    if isinstance(current, dict):
        game_id = current.get("game_id")
        return str(game_id) if game_id else None
    return None


def _next_shot_index(game_id: str | None) -> int:
    key = game_id or "live"
    shot_event_counters[key] = int(shot_event_counters.get(key, 0)) + 1
    return shot_event_counters[key]


def _build_shot_event_record(
    *,
    mode: str,
    result: dict[str, Any],
    player_name: str | None,
    start_white: Any,
    end_white: Any,
    shot_frames: int,
    multi_plan: Any,
    target_ball: int | None = None,
) -> dict[str, Any]:
    coach_event = _build_coach_shot_event(
        result=result,
        start_white=start_white,
        end_white=end_white,
        shot_frames=shot_frames,
        multi_plan=multi_plan,
    )
    best_route = _best_route_from_plan(multi_plan)
    planned_landing = _planned_cue_landing_from_route(best_route)
    actual_landing = _point_payload(end_white)
    return {
        "game_id": _current_recording_game_id(),
        "player_name": player_name,
        "shot_index": _next_shot_index(_current_recording_game_id()),
        "created_at": coach_event.get("timestamp"),
        "mode": mode,
        "target_ball": target_ball or best_route.get("target_ball_number"),
        "first_contact": result.get("first_contact"),
        "potted_balls": result.get("potted_balls") if isinstance(result.get("potted_balls"), list) else [],
        "pocket_result": coach_event.get("pocket_result") or "missed",
        "cue_ball_potted": bool(result.get("cue_ball_potted")),
        "is_foul": bool(result.get("is_foul")),
        "foul_reason": result.get("foul_reason"),
        "impact_angle": coach_event.get("impact_angle"),
        "ideal_angle": coach_event.get("ideal_angle"),
        "thickness_result": _classify_thickness(coach_event.get("impact_angle"), coach_event.get("ideal_angle")),
        "distance_bucket": _distance_bucket_from_route(best_route),
        "difficulty_level": best_route.get("difficulty_level") or "unknown",
        "success_prob": best_route.get("success_prob"),
        "position_success_prob": _position_success_from_route(best_route),
        "planned_cue_landing": planned_landing,
        "actual_cue_landing": actual_landing,
        "cue_landing_error_px": _point_distance(planned_landing, actual_landing),
        "next_ball_quality": _next_ball_quality_from_route(best_route),
        "raw_event_json": {
            "result": result,
            "coach_event": coach_event,
            "best_route": best_route,
            "shot_frames": shot_frames,
        },
    }


def _persist_shot_event_record(event: dict[str, Any]) -> None:
    try:
        recording_manager.db.insert_shot_event(event)
    except Exception as e:
        print(f"⚠️ Shot analytics persist error: {e}")


def _queue_shot_event_record(event: dict[str, Any]) -> None:
    try:
        shot_event_executor.submit(_persist_shot_event_record, event)
    except Exception as e:
        print(f"⚠️ Shot analytics queue error: {e}")


def _ball_center_from_bbox(bbox: list[Any] | tuple[Any, ...] | None) -> tuple[float, float] | None:
    if not bbox or len(bbox) < 4:
        return None
    return (float(bbox[0]) + float(bbox[2]) / 2.0, float(bbox[1]) + float(bbox[3]) / 2.0)


def _extract_tracked_balls(data: dict[str, Any]) -> list[dict[str, Any]]:
    balls: list[dict[str, Any]] = []
    for ball in data.get("balls", []) or []:
        if not isinstance(ball, dict):
            continue
        number = ball.get("number")
        if not isinstance(number, int):
            continue
        center = (
            float(ball.get("x", 0)) + float(ball.get("w", 0)) / 2.0,
            float(ball.get("y", 0)) + float(ball.get("h", 0)) / 2.0,
        )
        balls.append({
            "number": number,
            "pos": center,
            "r": max(1.0, min(float(ball.get("w", 0)), float(ball.get("h", 0))) / 2.0),
        })
    return balls


def _nearest_ball_by_number(balls: list[dict[str, Any]], number: int) -> dict[str, Any] | None:
    for ball in balls:
        if ball.get("number") == number:
            return ball
    return None


def _game_ball_numbers_from_state(g_state: dict[str, Any]) -> set[int]:
    numbers = {
        int(number)
        for number in g_state.get("remaining_balls", [])
        if isinstance(number, int) and 1 <= number <= 9
    }
    target = g_state.get("target_ball")
    if isinstance(target, int) and 1 <= target <= 9:
        numbers.add(target)
    return numbers or set(range(1, 10))


def _filter_game_balls(balls: list[dict[str, Any]], allowed_numbers: set[int]) -> list[dict[str, Any]]:
    return [
        ball
        for ball in balls
        if isinstance(ball.get("number"), int) and int(ball["number"]) in allowed_numbers
    ]


def _select_game_first_contact(
    target_ball: int | None,
    moved_numbers: list[int],
    disappeared_numbers: list[int],
) -> int | None:
    if isinstance(target_ball, int):
        if target_ball in disappeared_numbers:
            return target_ball
        if target_ball in moved_numbers:
            return target_ball
    if moved_numbers:
        return moved_numbers[0]
    if disappeared_numbers:
        return disappeared_numbers[0]
    return None


def _sync_game_remaining_balls_from_vision(data: dict[str, Any]) -> dict[str, Any] | None:
    """以穩定視覺球號修正遊玩模式剩餘球列表。"""
    g_state = game_manager.get_game_state()
    if not g_state or not g_state.get("is_active") or g_state.get("mode") != "nine_ball":
        return None
    if game_tracking_state.get("is_shot_in_progress"):
        return None

    detected_numbers = {
        ball["number"]
        for ball in _extract_tracked_balls(data)
        if isinstance(ball.get("number"), int) and 1 <= ball["number"] <= 9
    }
    if not detected_numbers:
        return None

    seen_counts = dict(game_tracking_state.get("visual_seen_counts") or {})
    missing_counts = dict(game_tracking_state.get("visual_missing_counts") or {})
    for number in range(1, 10):
        if number in detected_numbers:
            seen_counts[number] = seen_counts.get(number, 0) + 1
            missing_counts[number] = 0
        else:
            missing_counts[number] = missing_counts.get(number, 0) + 1
            seen_counts[number] = 0

    current_remaining = [
        number
        for number in g_state.get("remaining_balls", [])
        if isinstance(number, int) and 1 <= number <= 9
    ]
    current_target = g_state.get("target_ball") if isinstance(g_state.get("target_ball"), int) else None
    corrected = set(current_remaining)

    # 連續看見才補回，連續消失才移除，降低單幀漏檢造成 UI 抖動。
    for number in range(1, 10):
        if seen_counts.get(number, 0) >= 2:
            corrected.add(number)
        if missing_counts.get(number, 0) >= 8:
            corrected.discard(number)

    corrected_list = sorted(corrected)
    if not corrected_list:
        return None

    game_tracking_state["visual_seen_counts"] = seen_counts
    game_tracking_state["visual_missing_counts"] = missing_counts
    game_tracking_state["last_visual_remaining"] = corrected_list

    target_missing_confirmed = (
        current_target in current_remaining
        and current_target not in detected_numbers
        and missing_counts.get(current_target, 0) >= 8
    )
    result = game_manager.apply_visual_remaining_balls(
        corrected_list,
        protect_current_target=not target_missing_confirmed,
    )
    if tracker is not None and hasattr(tracker, "set_route_target_ball_number"):
        state = game_manager.get_game_state()
        options = state.get("game_options", {}) if isinstance(state, dict) else {}
        target = state.get("target_ball") if state else None
        tracker.set_route_target_ball_number(target if options.get("target_ar_hint_enabled", True) and isinstance(target, int) else None)
    return result


def _auto_track_game_shot(data: dict[str, Any]) -> dict[str, Any] | None:
    """遊玩模式 9 球自動進球、犯規與計分偵測。"""
    global latest_coach_shot_event
    g_state = game_manager.get_game_state()
    if not g_state or not g_state.get("is_active") or g_state.get("mode") != "nine_ball":
        _reset_game_auto_tracking_state()
        return None

    options = g_state.get("game_options", {}) if isinstance(g_state.get("game_options"), dict) else {}
    if not options.get("auto_pot_detection", True):
        game_tracking_state["last_white_pos"] = _ball_center_from_bbox(data.get("white_ball"))
        game_tracking_state["last_balls"] = _filter_game_balls(
            _extract_tracked_balls(data),
            _game_ball_numbers_from_state(g_state),
        )
        return None

    movement_threshold = 3.0
    tracking_match_radius = 86.0
    hole_radius = 52.0
    hole_inner_margin = 4.0
    missing_confirm_frames = 2
    in_hole_confirm_frames = 2
    pocket_approach_radius = hole_radius + 160.0

    holes = data.get("holes", []) or []
    white_bbox = data.get("white_ball")
    white_pos = _ball_center_from_bbox(white_bbox)
    white_radius = 0.0
    if white_bbox and len(white_bbox) >= 4:
        white_radius = max(1.0, min(float(white_bbox[2]), float(white_bbox[3])) / 2.0)

    target_ball = g_state.get("target_ball") if isinstance(g_state.get("target_ball"), int) else None
    allowed_ball_numbers = _game_ball_numbers_from_state(g_state)
    current_balls = _filter_game_balls(_extract_tracked_balls(data), allowed_ball_numbers)
    previous_balls = list(game_tracking_state.get("last_balls") or [])
    previous_white = game_tracking_state.get("last_white_pos")

    def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def fully_in_hole(ball_pos: tuple[float, float] | None, ball_radius: float) -> bool:
        if ball_pos is None or ball_radius <= 0 or not holes:
            return False
        for hole in holes:
            effective = hole_radius - ball_radius - hole_inner_margin
            if effective > 0 and dist(ball_pos, (float(hole[0]), float(hole[1]))) <= effective:
                return True
        return False

    def near_hole(ball_pos: tuple[float, float] | None) -> bool:
        if ball_pos is None or not holes:
            return False
        return any(dist(ball_pos, (float(hole[0]), float(hole[1]))) <= hole_radius + 8.0 for hole in holes)

    def nearest_hole_distance(ball_pos: tuple[float, float] | None) -> float | None:
        if ball_pos is None or not holes:
            return None
        return min(dist(ball_pos, (float(hole[0]), float(hole[1]))) for hole in holes)

    def is_pocket_disappearance_candidate(ball_pos: tuple[float, float] | None) -> bool:
        if ball_pos is None:
            return False
        hole_distance = nearest_hole_distance(ball_pos)
        if hole_distance is None:
            return False
        return hole_distance <= pocket_approach_radius

    white_moved = bool(white_pos and previous_white and dist(white_pos, previous_white) > movement_threshold)
    moved_numbers: list[int] = []
    for ball in current_balls:
        prev = _nearest_ball_by_number(previous_balls, int(ball["number"]))
        if prev and dist(ball["pos"], prev["pos"]) > movement_threshold:
            moved_numbers.append(int(ball["number"]))

    disappeared_numbers = [
        int(ball["number"])
        for ball in previous_balls
        if _nearest_ball_by_number(current_balls, int(ball["number"])) is None
    ]

    if white_moved:
        game_tracking_state["start_motion_frames"] += 1
    else:
        game_tracking_state["start_motion_frames"] = 0

    if not game_tracking_state["is_shot_in_progress"] and game_tracking_state["start_motion_frames"] >= 1 and white_pos:
        game_tracking_state["is_shot_in_progress"] = True
        game_tracking_state["shot_start_balls"] = previous_balls or current_balls
        game_tracking_state["shot_start_white_pos"] = white_pos
        game_tracking_state["first_contact"] = _select_game_first_contact(target_ball, moved_numbers, disappeared_numbers)
        game_tracking_state["potted_balls"] = []
        game_tracking_state["missing_ball_frames"] = {}
        game_tracking_state["still_frames"] = 0
        game_tracking_state["shot_frames"] = 0
        game_tracking_state["cue_missing_frames"] = 0
        game_tracking_state["cue_in_hole_frames"] = 0
        game_tracking_state["cue_was_in_hole"] = False
        game_tracking_state["cue_ball_potted"] = False
        game_tracking_state["start_motion_frames"] = 0
        print(f"🎮 Game Auto-Detection: Shot Started, first_contact={game_tracking_state['first_contact']}")

    if game_tracking_state["is_shot_in_progress"]:
        any_moved = white_moved or moved_numbers
        game_tracking_state["still_frames"] = 0 if any_moved else game_tracking_state["still_frames"] + 1

        if game_tracking_state.get("first_contact") is None:
            game_tracking_state["first_contact"] = _select_game_first_contact(
                target_ball,
                moved_numbers,
                disappeared_numbers,
            )

        start_balls = list(game_tracking_state.get("shot_start_balls") or [])
        potted_balls = list(game_tracking_state.get("potted_balls") or [])
        missing_ball_frames = dict(game_tracking_state.get("missing_ball_frames") or {})
        disappearance_ball_frames = dict(game_tracking_state.get("disappearance_ball_frames") or {})
        for start_ball in start_balls:
            number = int(start_ball["number"])
            current = _nearest_ball_by_number(current_balls, number)
            if current is None:
                missing_ball_frames[number] = int(missing_ball_frames.get(number, 0)) + 1
                last_known = _nearest_ball_by_number(previous_balls, number) or start_ball
                if is_pocket_disappearance_candidate(last_known.get("pos")):
                    disappearance_ball_frames[number] = int(disappearance_ball_frames.get(number, 0)) + 1
                else:
                    disappearance_ball_frames[number] = 0
                disappearance_potted = disappearance_ball_frames.get(number, 0) >= missing_confirm_frames
                target_missing_potted = number == target_ball and disappearance_potted
                if (near_hole(last_known.get("pos")) or disappearance_potted or target_missing_potted) and number not in potted_balls:
                    potted_balls.append(number)
                    if target_missing_potted:
                        game_tracking_state["first_contact"] = target_ball
            elif fully_in_hole(current.get("pos"), float(current.get("r", 0.0))) and number not in potted_balls:
                missing_ball_frames[number] = 0
                disappearance_ball_frames[number] = 0
                potted_balls.append(number)
            else:
                missing_ball_frames[number] = 0
                disappearance_ball_frames[number] = 0
        game_tracking_state["potted_balls"] = potted_balls
        game_tracking_state["missing_ball_frames"] = missing_ball_frames
        game_tracking_state["disappearance_ball_frames"] = disappearance_ball_frames

        if white_pos:
            game_tracking_state["last_cue_radius"] = white_radius
            if fully_in_hole(white_pos, white_radius):
                game_tracking_state["cue_in_hole_frames"] += 1
                game_tracking_state["cue_was_in_hole"] = True
            else:
                game_tracking_state["cue_in_hole_frames"] = 0
            game_tracking_state["cue_missing_frames"] = 0
        else:
            game_tracking_state["cue_missing_frames"] += 1
            if near_hole(previous_white) or is_pocket_disappearance_candidate(previous_white):
                game_tracking_state["cue_was_in_hole"] = True

        if (
            game_tracking_state["cue_in_hole_frames"] >= in_hole_confirm_frames
            or (
                game_tracking_state["cue_missing_frames"] >= missing_confirm_frames
                and game_tracking_state["cue_was_in_hole"]
            )
        ):
            game_tracking_state["cue_ball_potted"] = True

        game_tracking_state["shot_frames"] += 1
        if game_tracking_state["still_frames"] >= 8 or game_tracking_state["shot_frames"] >= 180:
            start_white = game_tracking_state.get("shot_start_white_pos")
            end_white = white_pos or game_tracking_state.get("last_white_pos")
            shot_frames = int(game_tracking_state.get("shot_frames") or 0)
            pre_result_state = game_manager.get_game_state() or {}
            player_names = pre_result_state.get("players") if isinstance(pre_result_state.get("players"), list) else []
            current_player = int(pre_result_state.get("current_player") or 1)
            player_name = (
                str(player_names[current_player - 1])
                if 0 <= current_player - 1 < len(player_names)
                else None
            )
            target_ball = pre_result_state.get("target_ball") if isinstance(pre_result_state.get("target_ball"), int) else None
            shot_multi_plan = latest_analysis_data.get("multi_plan") or data.get("multi_plan")
            result = game_manager.apply_auto_shot_result(
                first_contact=game_tracking_state.get("first_contact"),
                potted_balls=list(game_tracking_state.get("potted_balls") or []),
                cue_ball_potted=bool(game_tracking_state.get("cue_ball_potted")),
            )
            latest_coach_shot_event = _build_coach_shot_event(
                result=result,
                start_white=start_white,
                end_white=end_white,
                shot_frames=shot_frames,
                multi_plan=shot_multi_plan,
            )
            _queue_shot_event_record(
                _build_shot_event_record(
                    mode="nine_ball",
                    result=result,
                    player_name=player_name,
                    start_white=start_white,
                    end_white=end_white,
                    shot_frames=shot_frames,
                    multi_plan=shot_multi_plan,
                    target_ball=target_ball,
                )
            )
            _sync_game_timer_projection()
            print(f"🎮 Game Auto-Detection: Shot Ended, result={result}")
            _reset_game_auto_tracking_state()
            if tracker is not None and hasattr(tracker, "set_route_target_ball_number"):
                refreshed = game_manager.get_game_state()
                target = refreshed.get("target_ball") if refreshed else None
                tracker.set_route_target_ball_number(target if isinstance(target, int) else None)
            return result

    game_tracking_state["last_white_pos"] = white_pos
    game_tracking_state["last_balls"] = current_balls
    return None


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
    yolo_future: Optional[Future] = None  # ThreadPool future
    yolo_future_frame_id = 0
    yolo_future_frame_timestamp = 0.0
    yolo_future_frame_size: tuple[int, int] = (0, 0)
    yolo_future_submitted_at = 0.0
    yolo_future_timeout_logged_at = 0.0
    perf_monitor = PerformanceMonitor(window_size=30)  # 效能監控
    
    # ✅ 設為全域變數,讓 API 可以訪問
    global global_perf_monitor
    global_perf_monitor = perf_monitor
    
    last_data_packet: Optional[dict[str, Any]] = None
    last_ar_paths: list[Any] = []
    cached_exposure = 0.0
    exposure_cache_frames = max(1, int(getattr(config, "CAMERA_EXPOSURE_CACHE_FRAMES", 30)))

    while camera_running.is_set():
        frame_start = time.time()
        stage_timings: dict[str, float] = {}
        
        try:
            # 清空相機緩衝區 - 丟棄舊幀以降低延遲
            # 根據曝光時間動態調整策略
            if frame_count % exposure_cache_frames == 0:
                exposure_start = time.time()
                cached_exposure = cap.get(cv2.CAP_PROP_EXPOSURE)
                stage_timings["camera_exposure_get"] = time.time() - exposure_start
            exposure = cached_exposure
            
            # 曝光時間越長,清空次數越少 (避免額外延遲)
            configured_grab_count = int(getattr(config, "CAMERA_GRAB_FLUSH_FRAMES", -1))
            if configured_grab_count >= 0:
                grab_count = configured_grab_count
            elif exposure >= 0:  # 自動曝光或高曝光
                grab_count = 1  # 只清空1幀
            elif exposure >= -5:  # 中等曝光
                grab_count = 2
            else:  # 低曝光 (快速)
                grab_count = 3
            
            grab_start = time.time()
            for _ in range(grab_count):
                cap.grab()  # grab() 比 read() 快,只抓取不解碼
            stage_timings["camera_grab"] = time.time() - grab_start

            # 讀取最新的幀（影片來源時自動處理迴圈）
            read_start = time.time()
            ret, frame = read_frame_with_looped_video_source(cap)
            stage_timings["camera_read"] = time.time() - read_start

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
            camera_state["frame_count"] = frame_count
            
            # ==================== 統一影像處理管線 (方案 A) ====================
            # 在此處理後,YOLO 和前端串流都使用相同的處理後影像
            process_start = time.time()
            if image_processor:
                frame = image_processor.process_frame(frame)
            stage_timings["image_process"] = time.time() - process_start
            # ================================================================
            
            # ✅ 優化 1: ThreadPool 非阻塞 YOLO 推論
            if system_state["is_analyzing"] and tracker is not None:
                if yolo_future is not None and not yolo_future.done():
                    timeout_ms = int(getattr(config, "YOLO_FUTURE_TIMEOUT_MS", 2500))
                    hard_timeout_ms = int(getattr(config, "YOLO_FUTURE_HARD_TIMEOUT_MS", 30000))
                    future_age_ms = (
                        (time.time() - yolo_future_submitted_at) * 1000.0
                        if yolo_future_submitted_at > 0
                        else 0.0
                    )
                    if hard_timeout_ms > 0 and future_age_ms > hard_timeout_ms:
                        print(
                            f"⛔ YOLO future stalled after {future_age_ms:.0f}ms; "
                            "disabling analysis until backend restart"
                        )
                        latest_analysis_data["data"] = {
                            "status": "yolo_stalled",
                            "message": "YOLO inference stalled; restart backend before enabling analysis again.",
                            "stalled_after_ms": int(future_age_ms),
                            "source_frame_id": yolo_future_frame_id,
                        }
                        latest_analysis_data["status"] = "YOLO stalled"
                        latest_analysis_data["timestamp"] = time.time()
                        latest_analysis_data["planner_error"] = "YOLO inference stalled"
                        system_state["yolo_stalled"] = True
                        system_state["yolo_stalled_at"] = time.time()
                        system_state["is_analyzing"] = False
                    elif timeout_ms > 0 and future_age_ms > timeout_ms:
                        now = time.time()
                        if now - yolo_future_timeout_logged_at >= 5.0:
                            print(
                                f"⚠️ YOLO future is still running after {future_age_ms:.0f}ms; "
                                "waiting instead of resubmitting"
                            )
                            yolo_future_timeout_logged_at = now

                # ✅ 獲取 YOLO 推論結果
                if yolo_future and yolo_future.done():
                    yolo_result_start = time.time()
                    try:
                        _, data = yolo_future.result(timeout=0)
                        if isinstance(data, dict):
                            data["_source_frame_id"] = yolo_future_frame_id
                            data["_source_timestamp"] = yolo_future_frame_timestamp or time.time()
                            if yolo_future_frame_size[0] > 0 and yolo_future_frame_size[1] > 0:
                                data["_source_img_w"] = yolo_future_frame_size[0]
                                data["_source_img_h"] = yolo_future_frame_size[1]
                            _apply_manual_ball_identity_locks(data)
                        latest_analysis_data["data"] = data
                        if _has_drawable_overlay_data(data):
                            latest_analysis_data["overlay_data"] = data
                            latest_analysis_data["overlay_timestamp"] = time.time()
                        
                        # AR 座標轉換與投影機資料同步
                        ar_paths = []
                        ar_route_segments = []
                        ar_balls = []
                        ar_aim_lines = []
                        ar_ghost_balls = []
                        ar_cue_laser_lines = []
                        ar_table_polygon = []
                        ar_best_route = {
                            "route_segments": [],
                            "cue_landing_point": None,
                            "cue_landing_zone": None,
                            "position_play": None,
                            "lookahead": None,
                        }
                        
                        if calibrator is not None and calibrator.has_homography():
                            try:
                                ar_table_polygon = transform_table_roi_for_ar(data)
                                # 1. 優先轉換新版多球分段路線；沒有時才使用舊版單一路徑。
                                ar_best_route = transform_best_route_for_ar(data)
                                ar_route_segments = ar_best_route.get("route_segments", []) or []
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
                            isinstance(p_state_for_projector, dict)
                            and p_state_for_projector.get("is_active")
                            and p_state_for_projector.get("mode") in {"practice_pattern", "practice_accuracy"}
                            and p_state_for_projector.get("pattern_layout")
                        )
                        cue_laser_projection_enabled = False
                        if pattern_projection_active and isinstance(p_state_for_projector, dict):
                            active_layout = p_state_for_projector.get("pattern_layout")
                            active_guides_raw = active_layout.get("guide_options", {}) if isinstance(active_layout, dict) else {}
                            active_guides = active_guides_raw if isinstance(active_guides_raw, dict) else {}
                            cue_laser_projection_enabled = bool(active_guides.get("cue_laser_enabled", True))
                        elif isinstance(p_state_for_projector, dict) and p_state_for_projector.get("is_active"):
                            active_guides = p_state_for_projector.get("guide_options", {})
                            active_guides = active_guides if isinstance(active_guides, dict) else {}
                            cue_laser_projection_enabled = bool(active_guides.get("cue_laser_enabled", True))
                        has_projector_guides = _has_projector_dynamic_guides(
                            ar_paths,
                            ar_route_segments,
                            ar_aim_lines,
                            ar_ghost_balls,
                            ar_cue_laser_lines if cue_laser_projection_enabled else [],
                        )
                        if projector_renderer is not None and not pattern_projection_active and has_projector_guides:
                            if _projector_should_hold_selected_route():
                                projector_renderer.update_ar_data({
                                    "balls": ar_balls,
                                    "cue_laser_lines": ar_cue_laser_lines if cue_laser_projection_enabled else [],
                                    "cue_laser_source": "live_yolo",
                                    "cue_laser_timestamp": data.get("_source_timestamp", time.time()),
                                    "game_timer": _build_game_timer_projection_data(),
                                    "table_polygon": ar_table_polygon,
                                    "projector_status": "planner_route",
                                })
                            elif _projector_should_hold_manual_route() and not ar_route_segments:
                                projector_renderer.update_ar_data({
                                    "balls": ar_balls,
                                    "cue_laser_lines": ar_cue_laser_lines if cue_laser_projection_enabled else [],
                                    "cue_laser_source": "live_yolo",
                                    "cue_laser_timestamp": data.get("_source_timestamp", time.time()),
                                    "ar_timestamp": time.time(),
                                    "game_timer": _build_game_timer_projection_data(),
                                    "table_polygon": ar_table_polygon,
                                    "projector_status": "planner_route",
                                })
                            else:
                                projector_renderer.update_ar_data({
                                    "trajectories": [ar_paths] if ar_paths and not ar_route_segments else [],
                                    "route_segments": ar_route_segments,
                                    "balls": ar_balls,
                                    "aim_lines": ar_aim_lines,
                                    "ghost_balls": ar_ghost_balls,
                                    "setup_balls": [],
                                    "cue_landing_point": ar_best_route.get("cue_landing_point"),
                                    "cue_landing_zone": ar_best_route.get("cue_landing_zone"),
                                    "position_play": ar_best_route.get("position_play"),
                                    "lookahead": ar_best_route.get("lookahead"),
                                    "cue_laser_lines": ar_cue_laser_lines if cue_laser_projection_enabled else [],
                                    "allow_legacy_aim_lines": False,
                                    "allow_legacy_trajectories": False,
                                    "ar_source": "live_yolo",
                                    "ar_timestamp": data.get("_source_timestamp", time.time()),
                                    "cue_laser_source": "live_yolo",
                                    "cue_laser_timestamp": data.get("_source_timestamp", time.time()),
                                    "game_timer": _build_game_timer_projection_data(),
                                    "table_polygon": ar_table_polygon,
                                })
                        elif projector_renderer is not None and not pattern_projection_active and ar_table_polygon:
                            if _projector_should_hold_manual_route():
                                projector_renderer.update_ar_data({
                                    "table_polygon": ar_table_polygon,
                                    "game_timer": _build_game_timer_projection_data(),
                                    "ar_timestamp": time.time(),
                                    "projector_status": "planner_route",
                                })
                            else:
                                clear_payload = _empty_projector_dynamic_ar_data("live_yolo")
                                clear_payload.update({
                                    "table_polygon": ar_table_polygon,
                                    "game_timer": _build_game_timer_projection_data(),
                                    "ar_timestamp": data.get("_source_timestamp", time.time()),
                                    "cue_laser_timestamp": data.get("_source_timestamp", time.time()),
                                    "projector_status": "waiting_for_route",
                                })
                                projector_renderer.update_ar_data(clear_payload)
                        elif projector_renderer is not None and pattern_projection_active:
                            if cue_laser_projection_enabled and not ar_cue_laser_lines:
                                pass
                            else:
                                projector_renderer.update_ar_data({
                                    "cue_laser_lines": ar_cue_laser_lines if cue_laser_projection_enabled else [],
                                    "allow_legacy_aim_lines": False,
                                    "allow_legacy_trajectories": False,
                                    "cue_laser_source": "live_yolo",
                                    "cue_laser_timestamp": data.get("_source_timestamp", time.time()),
                                })
                        elif projector_renderer is not None and not pattern_projection_active:
                            if _projector_should_hold_manual_route():
                                projector_renderer.update_ar_data({
                                    "game_timer": _build_game_timer_projection_data(),
                                    "ar_timestamp": time.time(),
                                    "projector_status": "planner_route",
                                })
                            else:
                                clear_payload = _empty_projector_dynamic_ar_data("live_yolo")
                                clear_payload.update({
                                    "game_timer": _build_game_timer_projection_data(),
                                    "projector_status": "waiting_for_analysis",
                                })
                                projector_renderer.update_ar_data(clear_payload)
                        
                        # --- 單球練習狀態追蹤自動化 ---
                        try:
                            p_state = game_manager.get_practice_state()
                            practice_mode = str(p_state.get("mode") or "") if isinstance(p_state, dict) else ""
                            if p_state and p_state.get("is_active") and practice_mode in {"practice_single", "practice_pattern", "practice_accuracy"}:
                                import math

                                movement_threshold = 3.0
                                tracking_match_radius = 80.0
                                hole_radius = 52.0  # 由你的洞口參數調整
                                hole_inner_margin = 4.0
                                missing_confirm_frames = 2
                                in_hole_confirm_frames = 2
                                pocket_capture_confirm_frames = 2
                                pocket_approach_radius = hole_radius + 160.0
                                pocket_approach_min_delta = 0.5

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

                                def planner_target_number():
                                    multi_plan = latest_analysis_data.get("multi_plan")
                                    if not isinstance(multi_plan, dict):
                                        multi_plan = data.get("multi_plan") if isinstance(data.get("multi_plan"), dict) else None
                                    best_route = multi_plan.get("best_route") if isinstance(multi_plan, dict) else None
                                    if isinstance(best_route, dict) and isinstance(best_route.get("target_ball_number"), int):
                                        return int(best_route["target_ball_number"])
                                    return None

                                current_colors = []
                                for b in current_balls:
                                    if not isinstance(b, dict):
                                        continue
                                    current_colors.append(
                                        {
                                            "pos": (b["x"] + b["w"] // 2, b["y"] + b["h"] // 2),
                                            "r": max(1.0, min(b["w"], b["h"]) / 2.0),
                                            "number": b.get("number") if isinstance(b.get("number"), int) else None,
                                        }
                                    )
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

                                def in_pocket_capture_zone(ball_pos, ball_radius):
                                    if ball_pos is None or ball_radius <= 0 or not holes:
                                        return False
                                    capture_radius = hole_radius + max(8.0, ball_radius * 0.8)
                                    return any(
                                        dist(ball_pos, (hole[0], hole[1])) <= capture_radius
                                        for hole in holes
                                    )

                                def nearest_hole_distance(ball_pos):
                                    if ball_pos is None or not holes:
                                        return None
                                    return min(dist(ball_pos, (hole[0], hole[1])) for hole in holes)

                                def is_pocket_disappearance_candidate(ball_pos):
                                    if ball_pos is None:
                                        return False
                                    hole_distance = nearest_hole_distance(ball_pos)
                                    if hole_distance is None:
                                        # 桌洞偶發漏檢時，不要讓「目標球連續消失」完全無法計次。
                                        return True
                                    return hole_distance <= pocket_approach_radius

                                def find_missing_previous_target(planned_number=None):
                                    previous_colors = practice_tracking_state.get("last_colors_snapshot") or []
                                    if not previous_colors or len(current_colors) >= len(previous_colors):
                                        return None

                                    missing_candidates = []
                                    current_numbers = {
                                        c.get("number") for c in current_colors
                                        if isinstance(c.get("number"), int)
                                    }
                                    for previous in previous_colors:
                                        previous_number = previous.get("number")
                                        if isinstance(planned_number, int) and previous_number != planned_number:
                                            continue
                                        if isinstance(previous_number, int):
                                            if previous_number not in current_numbers:
                                                missing_candidates.append(previous)
                                            continue

                                        previous_pos = previous.get("pos")
                                        if previous_pos and not any(
                                            dist(c["pos"], previous_pos) <= tracking_match_radius
                                            for c in current_colors
                                        ):
                                            missing_candidates.append(previous)

                                    if not missing_candidates:
                                        return None

                                    near_hole_missing = [
                                        c for c in missing_candidates
                                        if is_pocket_disappearance_candidate(c.get("pos"))
                                    ]
                                    candidates = near_hole_missing or missing_candidates
                                    if white_pos:
                                        return min(candidates, key=lambda c: dist(c.get("pos"), white_pos))
                                    return min(
                                        candidates,
                                        key=lambda c: nearest_hole_distance(c.get("pos")) or float("inf"),
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

                                if practice_tracking_state["cooldown_frames"] > 0:
                                    practice_tracking_state["cooldown_frames"] -= 1

                                # 放寬啟動條件：白球漏檢時，子球移動或短暫消失也可視為一桿開始。
                                shot_motion_detected = color_moved or color_disappeared or (white_moved and current_colors)
                                if shot_motion_detected and practice_tracking_state["cooldown_frames"] <= 0:
                                    practice_tracking_state["start_motion_frames"] += 1
                                else:
                                    practice_tracking_state["start_motion_frames"] = 0

                                if (
                                    not practice_tracking_state["is_attempt_in_progress"]
                                    and practice_tracking_state["start_motion_frames"] >= 1
                                    and (
                                        current_colors
                                        or practice_tracking_state["last_target_pos"]
                                        or practice_tracking_state.get("last_colors_snapshot")
                                    )
                                ):
                                    planned_target_number = planner_target_number()
                                    missing_target = find_missing_previous_target(planned_target_number)
                                    target_started_missing_near_hole = False
                                    target_number = None
                                    if missing_target:
                                        target_pos = missing_target["pos"]
                                        target_r = missing_target["r"]
                                        target_number = missing_target.get("number")
                                        target_started_missing_near_hole = is_pocket_disappearance_candidate(target_pos)
                                    elif current_colors:
                                        numbered_targets = [
                                            c for c in current_colors
                                            if planned_target_number is not None and c.get("number") == planned_target_number
                                        ]
                                        if numbered_targets:
                                            target = numbered_targets[0]
                                        elif white_pos:
                                            target = min(current_colors, key=lambda c: dist(c["pos"], white_pos))
                                        else:
                                            target = min(
                                                current_colors,
                                                key=lambda c: nearest_hole_distance(c["pos"]) or float("inf"),
                                            )
                                        target_pos = target["pos"]
                                        target_r = target["r"]
                                        target_number = target.get("number")
                                    else:
                                        target_pos = practice_tracking_state["last_target_pos"]
                                        target_r = practice_tracking_state["last_target_radius"]
                                        target_number = practice_tracking_state.get("last_target_number")
                                    practice_tracking_state["is_attempt_in_progress"] = True
                                    practice_tracking_state["still_frames"] = 0
                                    practice_tracking_state["attempt_frames"] = 0
                                    practice_tracking_state["cue_missing_frames"] = 0
                                    practice_tracking_state["target_missing_frames"] = 0
                                    practice_tracking_state["cue_in_hole_frames"] = 0
                                    practice_tracking_state["target_in_hole_frames"] = 0
                                    practice_tracking_state["target_pocket_approach_frames"] = 0
                                    practice_tracking_state["target_disappearance_frames"] = 0
                                    practice_tracking_state["cue_was_in_hole"] = False
                                    practice_tracking_state["target_was_in_hole"] = False
                                    practice_tracking_state["cue_ball_potted"] = False
                                    practice_tracking_state["target_ball_potted"] = False
                                    practice_tracking_state["start_motion_frames"] = 0
                                    practice_tracking_state["attempt_start_white_pos"] = white_pos
                                    practice_tracking_state["last_target_pos"] = target_pos
                                    practice_tracking_state["last_target_radius"] = target_r
                                    practice_tracking_state["last_target_number"] = target_number
                                    practice_tracking_state["last_cue_radius"] = white_radius
                                    if target_started_missing_near_hole:
                                        practice_tracking_state["target_missing_frames"] = 1
                                        practice_tracking_state["target_disappearance_frames"] = 1
                                        practice_tracking_state["target_was_in_hole"] = True
                                    reset_practice_route_planner_state()
                                    print("🎯 Practice Auto-Detection: Attempt Started")

                                if practice_tracking_state["is_attempt_in_progress"]:
                                    tracked_target = None
                                    tracked_target_radius = practice_tracking_state["last_target_radius"]
                                    tracked_target_number = practice_tracking_state.get("last_target_number")
                                    last_target_pos = practice_tracking_state["last_target_pos"]

                                    if isinstance(tracked_target_number, int):
                                        numbered_candidate = next(
                                            (
                                                c for c in current_colors
                                                if c.get("number") == tracked_target_number
                                            ),
                                            None,
                                        )
                                        if numbered_candidate:
                                            tracked_target = numbered_candidate["pos"]
                                            tracked_target_radius = numbered_candidate["r"]
                                    current_has_numbered_balls = any(
                                        isinstance(c.get("number"), int) for c in current_colors
                                    )
                                    can_fallback_to_nearest = (
                                        not isinstance(tracked_target_number, int)
                                        or not current_has_numbered_balls
                                    )
                                    if tracked_target is None and can_fallback_to_nearest and last_target_pos and current_colors:
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
                                        previous_hole_distance = nearest_hole_distance(last_target_pos)
                                        current_hole_distance = nearest_hole_distance(tracked_target)
                                        practice_tracking_state["last_target_pos"] = tracked_target
                                        practice_tracking_state["last_target_radius"] = tracked_target_radius
                                        if (
                                            target_moved
                                            and previous_hole_distance is not None
                                            and current_hole_distance is not None
                                            and current_hole_distance <= pocket_approach_radius
                                            and current_hole_distance <= previous_hole_distance - pocket_approach_min_delta
                                        ):
                                            practice_tracking_state["target_pocket_approach_frames"] += 1
                                        elif (
                                            target_moved
                                            and previous_hole_distance is not None
                                            and current_hole_distance is not None
                                            and current_hole_distance > previous_hole_distance - pocket_approach_min_delta
                                        ):
                                            practice_tracking_state["target_pocket_approach_frames"] = 0
                                        elif current_hole_distance is not None and current_hole_distance > pocket_approach_radius:
                                            practice_tracking_state["target_pocket_approach_frames"] = 0
                                        target_in_capture_zone = (
                                            in_pocket_capture_zone(tracked_target, tracked_target_radius)
                                            and practice_tracking_state["target_pocket_approach_frames"] >= 1
                                        )
                                        if fully_in_hole(tracked_target, tracked_target_radius) or target_in_capture_zone:
                                            practice_tracking_state["target_in_hole_frames"] += 1
                                            practice_tracking_state["target_was_in_hole"] = True
                                        else:
                                            practice_tracking_state["target_in_hole_frames"] = 0
                                        practice_tracking_state["target_missing_frames"] = 0
                                        practice_tracking_state["target_disappearance_frames"] = 0
                                    else:
                                        practice_tracking_state["target_missing_frames"] += 1
                                        last_pos = practice_tracking_state["last_target_pos"]
                                        if (
                                            last_pos
                                            and (
                                                near_hole(last_pos)
                                                or is_pocket_disappearance_candidate(last_pos)
                                                or practice_tracking_state["target_pocket_approach_frames"] >= 1
                                            )
                                        ):
                                            practice_tracking_state["target_disappearance_frames"] += 1
                                            practice_tracking_state["target_was_in_hole"] = True

                                    if (
                                        practice_tracking_state["target_in_hole_frames"] >= in_hole_confirm_frames
                                        or (
                                            practice_tracking_state["target_in_hole_frames"] >= pocket_capture_confirm_frames
                                            and practice_tracking_state["target_was_in_hole"]
                                        )
                                        or (
                                            practice_tracking_state["target_missing_frames"] >= missing_confirm_frames
                                            and practice_tracking_state["target_was_in_hole"]
                                        )
                                        or practice_tracking_state["target_disappearance_frames"] >= missing_confirm_frames
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
                                        or (
                                            practice_tracking_state["target_ball_potted"]
                                            and (
                                                practice_tracking_state["target_in_hole_frames"] >= in_hole_confirm_frames
                                                or practice_tracking_state["target_missing_frames"] >= missing_confirm_frames
                                                or practice_tracking_state["still_frames"] >= 2
                                            )
                                        )
                                        or practice_tracking_state["attempt_frames"] >= 180
                                    ):
                                        # 分開規則：子球進且母球不進才成功
                                        success = (
                                            practice_tracking_state["target_ball_potted"]
                                            and not practice_tracking_state["cue_ball_potted"]
                                        )
                                        target_potted = practice_tracking_state["target_ball_potted"]
                                        cue_potted = practice_tracking_state["cue_ball_potted"]
                                        practice_result = game_manager.record_practice_attempt(success)
                                        practice_state = game_manager.get_practice_state() or {}
                                        practice_player = practice_state.get("player_name") if isinstance(practice_state, dict) else None
                                        practice_mode = str(practice_state.get("mode") or "practice_single") if isinstance(practice_state, dict) else "practice_single"
                                        potted_number = practice_tracking_state.get("last_target_number")
                                        potted_balls = [potted_number] if target_potted and isinstance(potted_number, int) else ([1] if target_potted else [])
                                        practice_event_result = {
                                            "first_contact": None,
                                            "potted_balls": potted_balls,
                                            "cue_ball_potted": cue_potted,
                                            "is_foul": cue_potted,
                                            "foul_reason": "母球進袋" if cue_potted else None,
                                            "practice_result": practice_result,
                                        }
                                        _queue_shot_event_record(
                                            _build_shot_event_record(
                                                mode=practice_mode,
                                                result=practice_event_result,
                                                player_name=str(practice_player) if practice_player else None,
                                                start_white=practice_tracking_state.get("attempt_start_white_pos"),
                                                end_white=white_pos or practice_tracking_state.get("last_white_pos"),
                                                shot_frames=int(practice_tracking_state.get("attempt_frames") or 0),
                                                multi_plan=latest_analysis_data.get("multi_plan") or data.get("multi_plan"),
                                            )
                                        )
                                        print(
                                            f"🎯 Practice Auto-Detection: Attempt Ended, "
                                            f"success={success}, target_potted={target_potted}, cue_potted={cue_potted}"
                                        )
                                        if target_potted:
                                            clear_practice_route_guides()
                                            data["multi_plan"] = None

                                        practice_tracking_state["is_attempt_in_progress"] = False
                                        practice_tracking_state["cooldown_frames"] = 20
                                        practice_tracking_state["still_frames"] = 0
                                        practice_tracking_state["attempt_frames"] = 0
                                        practice_tracking_state["cue_missing_frames"] = 0
                                        practice_tracking_state["target_missing_frames"] = 0
                                        practice_tracking_state["cue_in_hole_frames"] = 0
                                        practice_tracking_state["target_in_hole_frames"] = 0
                                        practice_tracking_state["target_pocket_approach_frames"] = 0
                                        practice_tracking_state["target_disappearance_frames"] = 0
                                        practice_tracking_state["cue_was_in_hole"] = False
                                        practice_tracking_state["target_was_in_hole"] = False
                                        practice_tracking_state["cue_ball_potted"] = False
                                        practice_tracking_state["target_ball_potted"] = False
                                        practice_tracking_state["attempt_start_white_pos"] = None
                                        practice_tracking_state["last_target_pos"] = None
                                        practice_tracking_state["last_target_number"] = None

                                practice_tracking_state["last_white_pos"] = white_pos
                                practice_tracking_state["last_colors_pos"] = current_colors_pos
                                practice_tracking_state["last_colors_snapshot"] = current_colors
                        except Exception as e:
                            print(f"⚠️ Practice tracking error: {e}")
                        # -------------------------

                        # --- 遊玩模式自動進球 / 犯規 / 計分 ---
                        try:
                            visual_sync_result = _sync_game_remaining_balls_from_vision(data)
                            if visual_sync_result:
                                data["game_visual_remaining"] = visual_sync_result
                            auto_game_result = _auto_track_game_shot(data)
                            if auto_game_result:
                                data["game_auto_result"] = auto_game_result
                        except Exception as e:
                            print(f"⚠️ Game tracking error: {e}")
                        # -------------------------
                        
                        # 更新低頻分析數據
                        latest_analysis_data["data"] = data  # ✅ 修正: 使用 data 而非 data_packet
                        latest_analysis_data["ar_paths"] = ar_paths
                        latest_analysis_data["ar_route_segments"] = ar_route_segments
                        latest_analysis_data["ar_best_route"] = ar_best_route
                        latest_analysis_data["multi_plan"] = data.get("multi_plan")
                        latest_analysis_data["planner_error"] = data.get("multi_plan", {}).get("error") if isinstance(data.get("multi_plan"), dict) else None
                        latest_analysis_data["status"] = "Analyzing"
                        latest_analysis_data["timestamp"] = time.time()
                        _submit_ai_coach_analysis(data, frame_count)
                    except Exception as e:
                        print(f"⚠️ YOLO result retrieval error: {e}")
                    finally:
                        stage_timings["yolo_result"] = time.time() - yolo_result_start
                        yolo_future = None
                        yolo_future_submitted_at = 0.0
                        yolo_future_timeout_logged_at = 0.0
                
                # 提交新的推論任務 (非阻塞)
                skip_yolo = frame_count % (system_state.get("yolo_skip_frames", 0) + 1) != 0
                if yolo_future is None and not skip_yolo:
                    yolo_submit_start = time.time()
                    yolo_future = executor.submit(tracker.process_frame, frame.copy(), False)
                    yolo_future_frame_id = frame_count
                    yolo_future_frame_timestamp = camera_state.get("last_frame_time", time.time())
                    yolo_future_frame_size = (int(frame.shape[1]), int(frame.shape[0]))
                    yolo_future_submitted_at = time.time()
                    yolo_future_timeout_logged_at = 0.0
                    stage_timings["yolo_submit"] = time.time() - yolo_submit_start
                
                annotation_mode = str(getattr(config, "TRACKER_ANNOTATION_MODE", "full")).strip().lower()
                monitor_uses_overlay = (
                    getattr(config, "MONITOR_STREAM_USE_YOLO_OVERLAY", False)
                    and annotation_mode != "none"
                )

                overlay_metadata = latest_analysis_data.get("overlay_data")
                latest_metadata = overlay_metadata or latest_analysis_data.get("data")
                metadata_age_ms = None
                overlay_timestamp = latest_analysis_data.get("overlay_timestamp") if latest_metadata is overlay_metadata else None
                metadata_age_ms = _overlay_metadata_age_ms(latest_metadata, overlay_timestamp)
                metadata_frame_lag = _overlay_metadata_frame_lag(latest_metadata, frame_count)
                max_overlay_age_ms = int(getattr(config, "OVERLAY_METADATA_MAX_AGE_MS", 350))
                max_overlay_frame_lag = int(getattr(config, "MONITOR_OVERLAY_MAX_FRAME_LAG", 12))
                overlay_metadata_fresh = (
                    metadata_age_ms is not None
                    and (max_overlay_age_ms <= 0 or metadata_age_ms <= max_overlay_age_ms)
                    and (
                        metadata_frame_lag is None
                        or max_overlay_frame_lag <= 0
                        or metadata_frame_lag <= max_overlay_frame_lag
                    )
                )

                display_frame = frame
            else:
                display_frame = frame
                yolo_future = None  # 清除未完成的 future
                yolo_future_submitted_at = 0.0
                yolo_future_timeout_logged_at = 0.0
                monitor_uses_overlay = False
                latest_metadata = None
                overlay_metadata_fresh = False
            monitor_source_frame = display_frame if monitor_uses_overlay else frame

            # ✅ 優化 2: 訂閱者檢查 - 只在有訂閱者時才編碼
            if mjpeg_manager is not None and config.ENABLE_SUBSCRIBER_CHECK:
                monitor_active = mjpeg_manager.monitor._active_connections > 0
                
                if monitor_active:
                    try:
                        # 監控流：原始或處理後的幀 (1280×720)
                        monitor_start = time.time()
                        if (
                            monitor_uses_overlay
                            and tracker is not None
                            and isinstance(latest_metadata, dict)
                            and overlay_metadata_fresh
                        ):
                            overlay_start = time.time()
                            monitor_frame = tracker.render_annotations_scaled(monitor_source_frame, latest_metadata, (1280, 720))
                            stage_timings["monitor_overlay_compose"] = time.time() - overlay_start
                        else:
                            monitor_frame = cv2.resize(monitor_source_frame, (1280, 720))
                        mjpeg_manager.update_monitor(monitor_frame)
                        stage_timings["mjpeg_monitor_update"] = time.time() - monitor_start
                    except Exception as e:
                        print(f"⚠️ MJPEG frame update error: {e}")
            elif mjpeg_manager is not None:
                # 未啟用訂閱者檢查,總是編碼
                try:
                    monitor_start = time.time()
                    if (
                        monitor_uses_overlay
                        and tracker is not None
                        and isinstance(latest_metadata, dict)
                        and overlay_metadata_fresh
                    ):
                        overlay_start = time.time()
                        monitor_frame = tracker.render_annotations_scaled(monitor_source_frame, latest_metadata, (1280, 720))
                        stage_timings["monitor_overlay_compose"] = time.time() - overlay_start
                    else:
                        monitor_frame = cv2.resize(monitor_source_frame, (1280, 720))
                    mjpeg_manager.update_monitor(monitor_frame)
                    stage_timings["mjpeg_monitor_update"] = time.time() - monitor_start
                except Exception as e:
                    print(f"⚠️ MJPEG frame update error: {e}")
            
            # ✅ 錄影功能：寫入幀到錄影檔
            if recording_manager.is_recording:
                try:
                    recording_start = time.time()
                    recording_manager.write_frame(display_frame)
                    stage_timings["recording_enqueue"] = time.time() - recording_start
                except Exception as e:
                    print(f"⚠️ Recording frame write error: {e}")

            # 🖼️ 顯示相機即時畫面 (YOLO 輸入畫面)
            if getattr(config, "ENABLE_CAMERA_PREVIEW_WINDOW", False):
                preview_start = time.time()
                cv2.imshow('YOLO Input Frame', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("🛑 User pressed 'q', stopping camera...")
                    camera_running.clear()
                stage_timings["preview_window"] = time.time() - preview_start

            # ✅ 優化 3: 效能監控與智能幀率控制
            pre_sleep_frame_time = time.time() - frame_start
            # 練習/遊玩模式取消 30 FPS 上限，其餘模式維持原有限速。
            if not _is_high_fps_mode_active():
                target_time = 1.0 / NORMAL_RUNTIME_FPS_CAP
                sleep_time = max(0.001, target_time - pre_sleep_frame_time)
                sleep_start = time.time()
                time.sleep(sleep_time)
                stage_timings["fps_cap_sleep"] = time.time() - sleep_start

            frame_time = time.time() - frame_start
            stage_timings["frame_total"] = frame_time
            if getattr(config, "PERF_DIAGNOSTICS_ENABLED", True):
                perf_monitor.record_stages(stage_timings)
            perf_monitor.record_frame(frame_time)
            
            # 每 30 幀輸出一次效能統計
            #if frame_count % 30 == 0:
            #    stats = perf_monitor.get_stats()
            #    print(f"📊 Performance: FPS={stats['current_fps']:.1f}, Latency={stats['avg_latency_ms']:.1f}ms")


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
        "pid": os.getpid(),
        "uptime_sec": round(time.time() - APP_STARTED_AT, 3),
        "is_analyzing": system_state["is_analyzing"],
        "active_sessions": len(session_manager.get_active_sessions())
    }


@app.get("/api/diagnostics/runtime")
async def runtime_diagnostics():
    cap = camera_state.get("current_cap")
    cap_opened = False
    if cap is not None:
        try:
            cap_opened = bool(cap.isOpened())
        except Exception:
            cap_opened = False

    return {
        "status": "ok",
        "pid": os.getpid(),
        "uptime_sec": round(time.time() - APP_STARTED_AT, 3),
        "log_path": RUNTIME_LOG_PATH,
        "thread_count": threading.active_count(),
        "threads": [thread.name for thread in threading.enumerate()],
        "camera": {
            "running": camera_running.is_set(),
            "thread_alive": bool(camera_capture_thread and camera_capture_thread.is_alive()),
            "selected_device_id": camera_state.get("selected_device_id"),
            "selected_backend": camera_state.get("selected_backend"),
            "last_good_backend": camera_state.get("last_good_backend"),
            "last_frame_age_ms": (
                round((time.time() - camera_state.get("last_frame_time", 0.0)) * 1000.0, 3)
                if camera_state.get("last_frame_time", 0.0) > 0
                else None
            ),
            "capture_opened": cap_opened,
            "is_switching": camera_state.get("is_switching", False),
            "reconnect_backoff_sec": camera_state.get("reconnect_backoff_sec"),
        },
        "mjpeg": mjpeg_manager.get_stats() if mjpeg_manager else None,
    }


# ================== v1.5 WebSocket Control Channel ==================

# WebSocket 連線追蹤
ws_connections: dict[str, WebSocket] = {}  # connection_id -> websocket
ws_heartbeat_tasks: dict[str, asyncio.Task] = {}  # connection_id -> heartbeat task


def _is_expected_websocket_close(exc: Exception) -> bool:
    if isinstance(exc, WebSocketDisconnect):
        return True
    message = exc.lower()
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
        metadata_rate_hz = max(1, int(getattr(config, "METADATA_RATE_HZ", 20)))
        metadata_interval = 1.0 / metadata_rate_hz
        receive_timeout = max(0.005, min(0.05, metadata_interval / 2.0))
        
        while True:
            # 非阻塞接收消息（超時檢查）
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=receive_timeout)
                
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
                ar_best_route = latest_analysis_data.get("ar_best_route", {})
                multi_plan_payload = data_packet.get("multi_plan") if isinstance(data_packet, dict) else None
                ai_coach_payload = coach_bridge.get_latest_result()
                monitor_detections = data_packet.get("balls", [])
                monitor_packet = data_packet
                monitor_multi_plan_payload = multi_plan_payload
                monitor_img_w = 1280
                monitor_img_h = 720
                source_w = int(data_packet.get("_source_img_w") or monitor_img_w) if isinstance(data_packet, dict) else monitor_img_w
                source_h = int(data_packet.get("_source_img_h") or monitor_img_h) if isinstance(data_packet, dict) else monitor_img_h
                if tracker is not None and isinstance(data_packet, dict):
                    try:
                        scale_x = monitor_img_w / max(1.0, float(source_w))
                        scale_y = monitor_img_h / max(1.0, float(source_h))
                        scaled_packet = tracker._scale_annotation_packet(data_packet, scale_x, scale_y)
                        monitor_packet = scaled_packet
                        monitor_detections = scaled_packet.get("balls", monitor_detections)
                        if isinstance(scaled_packet.get("multi_plan"), dict):
                            monitor_multi_plan_payload = scaled_packet.get("multi_plan")
                    except Exception as e:
                        print(f"⚠️ Failed to scale YOLO metadata for monitor view: {e}")
                if not isinstance(monitor_multi_plan_payload, dict):
                    ar_paths = []
                    ar_route_segments = []
                    ar_best_route = {
                        "route_segments": [],
                        "cue_landing_point": None,
                        "cue_landing_zone": None,
                        "position_play": None,
                        "lookahead": None,
                    }
                
                # 構造 metadata payload
                metadata_payload = {
                    "frame_id": metadata_counter,
                    "ts_backend": int(current_time * 1000),
                    "source_frame_id": data_packet.get("_source_frame_id") if isinstance(data_packet, dict) else None,
                    "source_timestamp": data_packet.get("_source_timestamp") if isinstance(data_packet, dict) else None,
                    "source_img_w": source_w,
                    "source_img_h": source_h,
                    "img_w": monitor_img_w,
                    "img_h": monitor_img_h,
                    "detected_count": len(data_packet.get("balls", [])),
                    "tracking_state": "active" if system_state["is_analyzing"] else "idle",
                    "detections": data_packet.get("balls", []),
                    "detections_view": monitor_detections,
                    "white_ball": monitor_packet.get("white_ball") if isinstance(monitor_packet, dict) else None,
                    "table_roi": monitor_packet.get("table_roi") if isinstance(monitor_packet, dict) else None,
                    "table_roi_raw": monitor_packet.get("table_roi_raw") if isinstance(monitor_packet, dict) else None,
                    "table_roi_points": monitor_packet.get("table_roi_points") if isinstance(monitor_packet, dict) else None,
                    "table_roi_status": monitor_packet.get("table_roi_status") if isinstance(monitor_packet, dict) else None,
                    "holes": monitor_packet.get("holes", []) if isinstance(monitor_packet, dict) else [],
                    "prediction": data_packet.get("prediction"),
                    "multi_plan": monitor_multi_plan_payload,
                    "ai_coach": ai_coach_payload,
                    "ar_paths": ar_paths,
                    "ar_route_segments": ar_route_segments,
                    "ar_best_route": ar_best_route,
                    "cue": monitor_packet.get("cue") if isinstance(monitor_packet, dict) else None,
                    "cue_axis": monitor_packet.get("cue_axis") if isinstance(monitor_packet, dict) else None,
                    "cue_laser_line": monitor_packet.get("cue_laser_line") if isinstance(monitor_packet, dict) else None,
                    "cue_laser_only": bool(monitor_packet.get("cue_laser_only")) if isinstance(monitor_packet, dict) else False,
                    "raw_yolo_boxes": monitor_packet.get("raw_yolo_boxes", []) if isinstance(monitor_packet, dict) else [],
                    "bbox": None,  # 可以添加
                    "keypoints": None,  # 可以添加
                    "rate_hz": metadata_rate_hz
                }
                
                await send_ws_envelope(
                    websocket,
                    "metadata.update",
                    metadata_payload,
                    session_id,
                    session.stream_id
                )

                if isinstance(monitor_multi_plan_payload, dict):
                    await send_ws_envelope(
                        websocket,
                        "planner.update",
                        monitor_multi_plan_payload,
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
    "overlay_data": {},
    "overlay_timestamp": 0.0,
    "ar_paths": [],
    "ar_route_segments": [],
    "ar_best_route": {
        "route_segments": [],
        "cue_landing_point": None,
        "cue_landing_zone": None,
        "position_play": None,
        "lookahead": None,
    },
    "multi_plan": None,
    "planner_error": None,
    "status": "Idle",
    "timestamp": 0,
}


def _empty_ar_best_route() -> dict[str, Any]:
    return {
        "route_segments": [],
        "cue_landing_point": None,
        "cue_landing_zone": None,
        "position_play": None,
        "lookahead": None,
    }


def _runtime_table_roi_snapshot() -> dict[str, Any]:
    if tracker is None:
        return {
            "table_roi": None,
            "table_roi_raw": None,
            "table_roi_points": None,
            "table_roi_adjustment": {"left": 0, "top": 0, "right": 0, "bottom": 0},
            "table_roi_status": "tracker_unavailable",
            "holes": [],
        }

    return {
        "table_roi": list(tracker.table_roi) if isinstance(tracker.table_roi, list) else tracker.table_roi,
        "table_roi_raw": list(tracker.table_roi_raw) if isinstance(tracker.table_roi_raw, list) else tracker.table_roi_raw,
        "table_roi_points": [list(point) for point in (getattr(tracker, "table_roi_points", None) or [])] or None,
        "table_roi_adjustment": dict(getattr(tracker, "table_roi_adjustment", {"left": 0, "top": 0, "right": 0, "bottom": 0})),
        "table_roi_status": getattr(tracker, "table_roi_status", "unknown"),
        "holes": [list(hole) for hole in (getattr(tracker, "holes", []) or [])],
    }


def _runtime_source_size(default_w: int = 1280, default_h: int = 720) -> tuple[int, int]:
    data_packet = latest_analysis_data.get("data") if isinstance(latest_analysis_data, dict) else None
    if isinstance(data_packet, dict):
        try:
            source_w = int(data_packet.get("_source_img_w") or 0)
            source_h = int(data_packet.get("_source_img_h") or 0)
            if source_w > 0 and source_h > 0:
                return source_w, source_h
        except (TypeError, ValueError):
            pass

    if tracker is not None and hasattr(tracker, "_last_frame_shape"):
        try:
            frame_h, frame_w = getattr(tracker, "_last_frame_shape")
            frame_w = int(frame_w)
            frame_h = int(frame_h)
            if frame_w > 0 and frame_h > 0:
                return frame_w, frame_h
        except (TypeError, ValueError):
            pass

    return default_w, default_h


def _scale_roi_points(points: Any, from_w: int, from_h: int, to_w: int, to_h: int) -> list[list[int]]:
    if not isinstance(points, list) or from_w <= 0 or from_h <= 0 or to_w <= 0 or to_h <= 0:
        return []

    scale_x = float(to_w) / float(from_w)
    scale_y = float(to_h) / float(from_h)
    scaled_points: list[list[int]] = []
    for point in points[:4]:
        try:
            if isinstance(point, dict):
                x = float(point.get("x"))
                y = float(point.get("y"))
            else:
                x = float(point[0])
                y = float(point[1])
        except (TypeError, ValueError, IndexError):
            continue
        scaled_points.append([int(round(x * scale_x)), int(round(y * scale_y))])
    return scaled_points


def _monitor_roi_points(points: Any) -> list[list[int]]:
    source_w, source_h = _runtime_source_size()
    return _scale_roi_points(points, source_w, source_h, 1280, 720)


def _sync_runtime_table_roi_packet(data_packet: Any, snapshot: dict[str, Any]) -> None:
    if not isinstance(data_packet, dict):
        return

    data_packet["table_roi"] = snapshot["table_roi"]
    data_packet["table_roi_raw"] = snapshot["table_roi_raw"]
    data_packet["table_roi_points"] = snapshot["table_roi_points"]
    data_packet["table_roi_adjustment"] = snapshot["table_roi_adjustment"]
    data_packet["table_roi_status"] = snapshot["table_roi_status"]
    data_packet["holes"] = snapshot["holes"]
    data_packet["multi_plan"] = None
    data_packet["planner_error"] = "TABLE_ROI_CHANGED_REPLAN_REQUIRED"


def _clear_route_planner_runtime_cache() -> None:
    if tracker is None:
        return

    route_planner = getattr(tracker, "route_planner", None)
    if route_planner is not None:
        route_planner.last_plan = None
        route_planner.last_error = None
        if hasattr(route_planner, "_last_state_hash"):
            route_planner._last_state_hash = None
        if hasattr(route_planner, "_last_state_hash_plan"):
            route_planner._last_state_hash_plan = None
        if hasattr(route_planner, "_held_target_number"):
            route_planner._held_target_number = None
        if hasattr(route_planner, "_held_target_miss_frames"):
            route_planner._held_target_miss_frames = 0

    if hasattr(tracker, "_route_plan_missing_frames"):
        tracker._route_plan_missing_frames = 0


def _apply_runtime_table_roi_change() -> dict[str, Any]:
    snapshot = _runtime_table_roi_snapshot()
    _sync_runtime_table_roi_packet(latest_analysis_data.get("data"), snapshot)
    _sync_runtime_table_roi_packet(latest_analysis_data.get("overlay_data"), snapshot)

    latest_analysis_data["multi_plan"] = None
    latest_analysis_data["planner_error"] = "TABLE_ROI_CHANGED_REPLAN_REQUIRED"
    latest_analysis_data["ar_route_segments"] = []
    latest_analysis_data["ar_best_route"] = _empty_ar_best_route()
    latest_analysis_data["timestamp"] = time.time()
    _clear_route_planner_runtime_cache()
    return snapshot


def _ball_centers_from_packet(data_packet: dict[str, Any]) -> list[list[float]]:
    centers: list[list[float]] = []
    white_ball = data_packet.get("white_ball")
    if isinstance(white_ball, list) and len(white_ball) >= 4:
        try:
            centers.append([
                float(white_ball[0]) + float(white_ball[2]) / 2.0,
                float(white_ball[1]) + float(white_ball[3]) / 2.0,
            ])
        except (TypeError, ValueError):
            pass

    for ball in data_packet.get("balls", []) or []:
        if not isinstance(ball, dict):
            continue
        try:
            centers.append([
                float(ball["x"]) + float(ball["w"]) / 2.0,
                float(ball["y"]) + float(ball["h"]) / 2.0,
            ])
        except (KeyError, TypeError, ValueError):
            continue
    return centers


def _round_point_for_coach_signature(point: Any, grid: float = 12.0) -> list[float] | None:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        return [
            round(float(point[0]) / grid) * grid,
            round(float(point[1]) / grid) * grid,
        ]
    except (TypeError, ValueError):
        return None


def _semantic_context_signature(semantic_context: dict[str, Any], multi_plan: Any = None) -> str:
    balls_signature: list[dict[str, Any]] = []
    for ball in semantic_context.get("balls", []) or []:
        if not isinstance(ball, dict):
            continue
        nearest_pocket = ball.get("nearest_pocket") if isinstance(ball.get("nearest_pocket"), dict) else {}
        balls_signature.append(
            {
                "id": ball.get("id"),
                "number": ball.get("number"),
                "center": _round_point_for_coach_signature(ball.get("center")),
                "nearest_pocket": nearest_pocket.get("name"),
                "path_clear": nearest_pocket.get("path_clear"),
                "cue_path_clear": ball.get("cue_path_clear"),
            }
        )

    plan_signature = None
    if isinstance(multi_plan, dict):
        best_route = multi_plan.get("best_route") if isinstance(multi_plan.get("best_route"), dict) else {}
        plan_signature = {
            "route_type": best_route.get("route_type"),
            "target_ball_number": best_route.get("target_ball_number"),
            "success_prob": round(float(best_route.get("success_prob", 0.0)), 2) if best_route else None,
        }

    payload = {
        "stable_ball_count": semantic_context.get("stable_ball_count"),
        "cue_center": _round_point_for_coach_signature(
            (semantic_context.get("cue_ball") or {}).get("center")
            if isinstance(semantic_context.get("cue_ball"), dict)
            else None
        ),
        "balls": balls_signature,
        "plan": plan_signature,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _submit_ai_coach_analysis(data_packet: dict[str, Any], frame_id: int | None = None) -> None:
    multi_plan = latest_analysis_data.get("multi_plan") or data_packet.get("multi_plan")
    semantic_context = coach_semantics.update(data_packet, multi_plan)
    latest_analysis_data["coach_semantic_snapshot_at"] = semantic_context.get("snapshot_at")
    coach_payload = coach_payload_builder.build(
        request_type="analysis",
        message=None,
        runtime_packet=data_packet,
        semantic_context=semantic_context,
        multi_plan=multi_plan,
        system_status=_build_coach_system_status(data_packet),
        shot_event=latest_coach_shot_event or {},
        frame_id=frame_id if frame_id is not None else data_packet.get("frame_count"),
        ts_backend=int(time.time() * 1000),
    )

    if not getattr(config, "AI_COACH_AUTO_SUGGESTIONS_ENABLED", False):
        return

    if not semantic_context.get("valid") or not semantic_context.get("stable"):
        return

    now = time.time()
    signature = str((coach_payload.get("debug") or {}).get("signature") or _semantic_context_signature(semantic_context, multi_plan))
    interval = max(3.0, getattr(config, "AI_COACH_AUTO_ANALYSIS_INTERVAL_SECONDS", 20.0))
    if (
        signature == ai_coach_auto_state.get("last_signature")
        and now - float(ai_coach_auto_state.get("last_submitted_at", 0.0)) < interval
    ):
        return

    submitted = coach_bridge.submit_analysis(coach_payload)
    if submitted:
        ai_coach_auto_state["last_submitted_at"] = now
        ai_coach_auto_state["last_signature"] = signature


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
                "ar_best_route": latest_analysis_data.get("ar_best_route", {}),
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
    if not getattr(config, "ENABLE_LEGACY_VIDEO_WS", False):
        await _safe_websocket_send_text(
            websocket,
            json.dumps(
                {
                    "status": "disabled",
                    "message": "Legacy /ws/video is disabled. Use /burnin/*.mjpg plus /ws/control.",
                }
            ),
        )
        await websocket.close(code=1000, reason="Legacy video websocket disabled")
        return

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
        last_ar_best_route: dict[str, Any] = {
            "route_segments": [],
            "cue_landing_point": None,
            "cue_landing_zone": None,
            "position_play": None,
            "lookahead": None,
        }

        while True:
            # 檢查是否需要切換攝像頭
            if camera_state["needs_switch"] and not camera_state["is_switching"]:
                print(f"📱 WebSocket: Initiating async camera switch to device {camera_state['new_device_id']}")
                camera_state["is_switching"] = True
                camera_state["needs_switch"] = False
                loop = asyncio.get_event_loop()
                loop.run_in_executor(
                    executor,
                    switch_camera_background,
                    camera_state["new_device_id"],
                    camera_state.get("selected_backend"),
                )
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
            data_packet: dict[str, Any]
            try:
                # ✅ 推論跳幀：每 N 幀執行一次 YOLO（減少 CPU 負載）
                skip_yolo = frame_count % (system_state.get("yolo_skip_frames", 0) + 1) != 0

                if system_state["is_analyzing"] and tracker is not None and not skip_yolo:
                    loop = asyncio.get_event_loop()
                    process_result = await loop.run_in_executor(executor, lambda: tracker.process_frame(frame))
                    processed_frame = process_result[0]
                    result_packet = process_result[1]
                    data_packet = result_packet if isinstance(result_packet, dict) else {"status": "invalid_result"}
                elif skip_yolo and last_processed_frame is not None and last_data_packet is not None:
                    processed_frame = last_processed_frame.copy()
                    data_packet = {**last_data_packet, "status": last_data_packet.get("status", "cached"), "skipped": True, "frame_count": frame_count}
                    used_cached = True
                else:
                    processed_frame = frame.copy()
                    skip_reason = "skipped" if skip_yolo else "idle"
                    data_packet = {"status": skip_reason, "frame_count": frame_count}
                _apply_manual_ball_identity_locks(data_packet)
            except Exception as e:
                print(f"❌ Frame processing error: {e}")
                processed_frame = frame.copy()
                data_packet = {"error": e, "frame_count": frame_count}
            yolo_elapsed = time.time() - yolo_start
            record_perf("yolo", yolo_elapsed)

            # ✅ AR 座標轉換
            ar_paths: list[Any] = []
            ar_route_segments: list[Any] = []
            ar_best_route: dict[str, Any] = {
                "route_segments": [],
                "cue_landing_point": None,
                "cue_landing_zone": None,
                "position_play": None,
                "lookahead": None,
            }
            if used_cached:
                ar_paths = list(last_ar_paths)
                ar_route_segments = list(last_ar_route_segments)
                ar_best_route = dict(last_ar_best_route)
            else:
                try:
                    ar_best_route = transform_best_route_for_ar(data_packet)
                    ar_route_segments = ar_best_route.get("route_segments", []) or []
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
                last_ar_best_route = ar_best_route

            # ✅ 添加幀到 MJPEG 串流（監控）
            if mjpeg_manager is not None:
                try:
                    # 監控流：原始或處理後的幀 (1280×720)
                    monitor_frame = cv2.resize(processed_frame, (1280, 720))
                    mjpeg_manager.update_monitor(monitor_frame)
                except Exception as e:
                    print(f"⚠️  MJPEG frame update error: {e}")

            # ✅ 更新低頻分析數據（供 HLS 模式的 /ws/analytics 使用）
            latest_analysis_data["data"] = data_packet
            latest_analysis_data["ar_paths"] = ar_paths
            latest_analysis_data["ar_route_segments"] = ar_route_segments
            latest_analysis_data["ar_best_route"] = ar_best_route
            latest_analysis_data["multi_plan"] = data_packet.get("multi_plan")
            latest_analysis_data["planner_error"] = data_packet.get("multi_plan", {}).get("error") if isinstance(data_packet.get("multi_plan"), dict) else None
            latest_analysis_data["status"] = "Analyzing" if system_state["is_analyzing"] else "Idle"
            latest_analysis_data["timestamp"] = time.time()
            if system_state["is_analyzing"] and not used_cached:
                _submit_ai_coach_analysis(data_packet, frame_count)

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
                "ar_best_route": ar_best_route,
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
    if _is_yolo_stalled():
        system_state["is_analyzing"] = False
        return {
            "status": "yolo_stalled",
            "is_analyzing": False,
            "message": "YOLO inference stalled; restart backend before enabling analysis again.",
        }
    ensure_camera_capture_started()
    system_state["is_analyzing"] = not system_state["is_analyzing"]
    if system_state["is_analyzing"]:
        restore_live_annotation_mode()
    else:
        config.TRACKER_ANNOTATION_MODE = "none"
    print(f"🎛️  YOLO Analysis toggled: {system_state['is_analyzing']}")
    print(f"   Tracker available: {tracker is not None}")
    return {"status": "success", "is_analyzing": system_state["is_analyzing"]}


@app.post("/api/control/analysis")
async def set_analysis_enabled(request: Annotated[dict, Body(...)]):
    """明確啟用或停用 YOLO 辨識，避免前端因狀態不同步誤觸 toggle。"""
    enabled = bool(request.get("enabled", True))
    if enabled and _is_yolo_stalled():
        system_state["is_analyzing"] = False
        return {
            "status": "yolo_stalled",
            "is_analyzing": False,
            "message": "YOLO inference stalled; restart backend before enabling analysis again.",
        }
    if enabled:
        ensure_camera_capture_started()
        restore_live_annotation_mode()
    else:
        config.TRACKER_ANNOTATION_MODE = "none"
    system_state["is_analyzing"] = enabled
    print(f"🎛️  YOLO Analysis set: {system_state['is_analyzing']}")
    print(f"   Tracker available: {tracker is not None}")
    return {"status": "success", "is_analyzing": system_state["is_analyzing"]}


# ✅ 動態調整跳幀設置
@app.post("/api/control/yolo-skip")
async def set_yolo_skip(request: Annotated[dict, Body(...)]):
    """設置推論跳幀數量（0=每幀執行，2=每3幀執行一次）"""
    skip_frames = request.get("skip_frames", 0)
    if skip_frames < 0 or skip_frames > 10:
        return {"status": "error", "message": "skip_frames must be 0-10"}
    system_state["yolo_skip_frames"] = skip_frames
    return {"status": "success", "yolo_skip_frames": skip_frames, "inference_frequency": f"1/{skip_frames + 1} frames"}


@app.post("/api/control/overlay-mode")
async def set_overlay_mode(request: Annotated[dict, Body(...)]):
    """切換後端影像標註模式：none=不繪圖，tactical=精簡戰術，full=完整標註。"""
    mode = str(request.get("mode", "")).strip().lower()
    if mode not in {"none", "tactical", "full"}:
        return {"status": "error", "message": "mode must be none, tactical, or full"}

    config.TRACKER_ANNOTATION_MODE = mode
    return {"status": "success", "tracker_annotation_mode": mode}


# --- 新增 API: 列舉攝像頭設備 ---
@app.get("/api/camera/enumerate")
async def enumerate_cameras():
    """掃描並回傳所有可用的攝像頭設備"""
    devices = enumerate_camera_devices()
    camera_state["available_devices"] = devices
    return {
        "devices": devices,
        "current_device_id": camera_state["selected_device_id"],
        "current_backend": camera_state.get("selected_backend"),
    }


# --- 新增 API: 選擇攝像頭設備 ---
@app.post("/api/camera/select")
async def select_camera(request: Annotated[dict, Body(...)]):
    """切換到指定的攝像頭設備 (立即在 WebSocket 中生效)"""
    device_id = request.get("device_id", 0)
    backend = normalize_camera_backend(request.get("backend"))

    if device_id < 0 or device_id > 10:
        return {"status": "error", "message": "Invalid device ID"}

    # 設置切換標記，WebSocket 迴圈會偵測並執行切換
    camera_state["new_device_id"] = device_id
    camera_state["selected_backend"] = backend or camera_state.get("selected_backend", cv2.CAP_DSHOW)
    camera_state["needs_switch"] = True

    print(f"Camera switch requested: device_id={device_id}")
    return {
        "status": "success",
        "requested_device_id": device_id,
        "requested_backend": backend,
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
        stage_latency = perf_stats_data.get("stage_latency_ms", {})
        total_frames = perf_stats_data.get("total_frames", 0)
    else:
        # 如果 monitor 還未初始化,使用預設值
        current_fps = 0.0
        avg_latency = 0.0
        stage_latency = {}
        total_frames = 0
    
    stats = {
        "current_fps": current_fps,
        "avg_latency_ms": avg_latency,
        "total_frames": total_frames,
        "stage_latency_ms": stage_latency,
        "diagnostics_enabled": getattr(config, "PERF_DIAGNOSTICS_ENABLED", True),
        "camera_preview_window": getattr(config, "ENABLE_CAMERA_PREVIEW_WINDOW", False),
        "camera_grab_flush_frames": getattr(config, "CAMERA_GRAB_FLUSH_FRAMES", -1),
        "projector_render_max_fps": getattr(config, "PROJECTOR_RENDER_MAX_FPS", 12),
        "projector_render_cache_enabled": getattr(config, "PROJECTOR_RENDER_CACHE_ENABLED", False),
        "projector_position_avoid_zones": {
            "enabled": getattr(config, "PROJECTOR_SHOW_POSITION_AVOID_ZONES", True),
            "show_pocket_scratch": getattr(config, "PROJECTOR_SHOW_POCKET_AVOID_ZONES", False),
            "max_zones": getattr(config, "PROJECTOR_MAX_AVOID_ZONES", 3),
        },
        "projector_render_worker_active": (
            projector_render_thread is not None and projector_render_thread.is_alive()
        ),
        "projector_render_stats": (
            projector_renderer.get_render_stats() if projector_renderer is not None else {}
        ),
        "monitor_stream_use_yolo_overlay": getattr(config, "MONITOR_STREAM_USE_YOLO_OVERLAY", False),
        "monitor_overlay_cache_enabled": getattr(config, "MONITOR_OVERLAY_CACHE_ENABLED", False),
        "tracker_annotation_mode": getattr(config, "TRACKER_ANNOTATION_MODE", "full"),
        "monitor_overlay_cache": (
            tracker.get_monitor_overlay_cache_stats() if tracker is not None else {}
        ),
        "monitor_effective_overlay": (
            getattr(config, "MONITOR_STREAM_USE_YOLO_OVERLAY", False)
            and str(getattr(config, "TRACKER_ANNOTATION_MODE", "full")).strip().lower() != "none"
        ),
        "overlay_metadata_max_age_ms": getattr(config, "OVERLAY_METADATA_MAX_AGE_MS", 350),
        "monitor_overlay_max_frame_lag": getattr(config, "MONITOR_OVERLAY_MAX_FRAME_LAG", 12),
        "projector_ar_metadata_max_age_ms": getattr(config, "PROJECTOR_AR_METADATA_MAX_AGE_MS", 160),
        "last_good_overlay_hold_ms": getattr(config, "LAST_GOOD_OVERLAY_HOLD_MS", 5000),
        "last_good_projector_ar_hold_ms": getattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", 5000),
        "stream_active": camera_state.get("last_frame_time", 0) > 0,
        "is_analyzing": system_state.get("is_analyzing", False),
        "camera": {
            "selected_device_id": camera_state.get("selected_device_id"),
            "last_good_backend": camera_state.get("last_good_backend"),
            "last_good_backend_name": camera_backend_name(camera_state.get("last_good_backend")),
            "last_good_profile": camera_state.get("last_good_profile"),
            "actual_profile": camera_state.get("actual_profile"),
            "fourcc_info": camera_state.get("fourcc_info"),
            "last_frame_age_ms": (
                round((time.time() - camera_state.get("last_frame_time", 0.0)) * 1000.0, 3)
                if camera_state.get("last_frame_time", 0.0) > 0
                else None
            ),
        },
    }

    overlay_data_packet = latest_analysis_data.get("overlay_data")
    latest_data_packet = overlay_data_packet or latest_analysis_data.get("data")
    overlay_timestamp = latest_analysis_data.get("overlay_timestamp") if latest_data_packet is overlay_data_packet else None
    metadata_age = _overlay_metadata_age_ms(latest_data_packet, overlay_timestamp)
    if metadata_age is not None:
        metadata_age_ms = round(metadata_age, 3)
        max_overlay_age_ms = int(getattr(config, "OVERLAY_METADATA_MAX_AGE_MS", 350))
        stats["overlay_metadata_age_ms"] = metadata_age_ms
        stats["overlay_metadata_fresh"] = (
            max_overlay_age_ms <= 0
            or metadata_age_ms <= max_overlay_age_ms
        )
        source_frame_lag = _overlay_metadata_frame_lag(latest_data_packet, int(camera_state.get("frame_count", 0) or 0))
        if source_frame_lag is not None:
            stats["overlay_metadata_frame_lag"] = source_frame_lag
    
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
    if session is None:
        return JSONResponse(
            status_code=404,
            content=create_error_response(ERR_SESSION_EXPIRED, "Session not found or expired")
        )
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
def _get_monitor_frame_copy() -> Optional[np.ndarray]:
    if mjpeg_manager is None:
        return None
    lock = getattr(mjpeg_manager.monitor, "_frame_lock", None)
    if lock is None:
        return None
    with lock:
        raw = getattr(mjpeg_manager.monitor, "_current_raw_frame", None)
        return raw.copy() if raw is not None else None


BALL_OVERLAY_HEX_BY_NUMBER: dict[int, str] = {
    0: "#f8fafc",
    1: "#facc15",
    2: "#2563eb",
    3: "#dc2626",
    4: "#7c3aed",
    5: "#f97316",
    6: "#16a34a",
    7: "#92400e",
    8: "#111827",
    9: "#facc15",
    10: "#2563eb",
    11: "#dc2626",
    12: "#7c3aed",
    13: "#f97316",
    14: "#16a34a",
    15: "#92400e",
}

BALL_OVERLAY_HEX_BY_COLOR: dict[str, str] = {
    "white": "#f8fafc",
    "black": "#111827",
    "yellow": "#facc15",
    "blue": "#2563eb",
    "red": "#dc2626",
    "purple": "#7c3aed",
    "orange": "#f97316",
    "green": "#16a34a",
    "brown": "#92400e",
}


def _ball_overlay_color_hex(ball: dict[str, Any]) -> str:
    raw_number = ball.get("number")
    try:
        number = int(raw_number) if raw_number is not None else None
    except (TypeError, ValueError):
        number = None
    if number is not None and number in BALL_OVERLAY_HEX_BY_NUMBER:
        return BALL_OVERLAY_HEX_BY_NUMBER[number]

    color_name = str(ball.get("color") or ball.get("label") or "").lower()
    for token, hex_color in BALL_OVERLAY_HEX_BY_COLOR.items():
        if token in color_name:
            return hex_color
    return "#22d3ee"


def _scale_bbox_to_frame(
    bbox: list[Any],
    source_w: int,
    source_h: int,
    frame_w: int,
    frame_h: int,
) -> list[int] | None:
    if len(bbox) < 4 or source_w <= 0 or source_h <= 0 or frame_w <= 0 or frame_h <= 0:
        return None
    try:
        x = float(bbox[0])
        y = float(bbox[1])
        w = float(bbox[2])
        h = float(bbox[3])
    except (TypeError, ValueError):
        return None

    sx = frame_w / float(source_w)
    sy = frame_h / float(source_h)
    x0 = int(round(x * sx))
    y0 = int(round(y * sy))
    x1 = int(round((x + w) * sx))
    y1 = int(round((y + h) * sy))
    x0 = max(0, min(frame_w - 1, x0))
    y0 = max(0, min(frame_h - 1, y0))
    x1 = max(x0 + 1, min(frame_w, x1))
    y1 = max(y0 + 1, min(frame_h, y1))
    return [x0, y0, x1 - x0, y1 - y0]


def _sample_ball_roi_color(frame: np.ndarray, bbox: list[int]) -> dict[str, Any] | None:
    if frame is None or len(bbox) < 4:
        return None
    x, y, w, h = [int(v) for v in bbox[:4]]
    frame_h, frame_w = frame.shape[:2]
    if w <= 2 or h <= 2 or x >= frame_w or y >= frame_h:
        return None

    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(frame_w, x + w)
    y1 = min(frame_h, y + h)
    roi = frame[y0:y1, x0:x1]
    if roi.size == 0:
        return None

    roi_h, roi_w = roi.shape[:2]
    cx = roi_w // 2
    cy = roi_h // 2
    radius = max(2, int(min(roi_w, roi_h) * 0.38))
    yy, xx = np.ogrid[:roi_h, :roi_w]
    circle_mask = ((xx - cx) ** 2 + (yy - cy) ** 2) <= radius ** 2

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = cv2.split(hsv)
    valid = circle_mask & (v_ch >= 18) & (v_ch <= 252)
    if np.count_nonzero(valid) < 8:
        valid = circle_mask
    if np.count_nonzero(valid) < 8:
        return None

    hsv_pixels = hsv[valid].reshape(-1, 3)
    bgr_pixels = roi[valid].reshape(-1, 3)
    hsv_median = np.median(hsv_pixels, axis=0)
    bgr_median = np.median(bgr_pixels, axis=0)

    return {
        "sample_pixels": int(hsv_pixels.shape[0]),
        "hsv_median": [int(round(float(v))) for v in hsv_median],
        "rgb_median": [
            int(round(float(bgr_median[2]))),
            int(round(float(bgr_median[1]))),
            int(round(float(bgr_median[0]))),
        ],
    }


COLOR_SAMPLE_DIR = PROJECT_ROOT / "backend" / "data" / "color_calibration_samples"


def _clean_numeric_triplet(values: Any) -> list[float] | None:
    if not isinstance(values, list) or len(values) != 3:
        return None
    try:
        result = [float(v) for v in values]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in result):
        return None
    return result


def _lab_from_rgb_triplet(rgb: Any) -> list[float] | None:
    values = _clean_numeric_triplet(rgb)
    if values is None:
        return None
    rgb_pixel = np.uint8([[[int(max(0, min(255, round(values[0])))), int(max(0, min(255, round(values[1])))), int(max(0, min(255, round(values[2]))))]]])
    bgr_pixel = cv2.cvtColor(rgb_pixel, cv2.COLOR_RGB2BGR)
    lab_pixel = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2LAB)[0, 0]
    return [float(v) for v in lab_pixel.tolist()]


def _color_feature_from_diagnostic(diag: dict[str, Any]) -> dict[str, Any]:
    classifier_debug = diag.get("classifier_debug") if isinstance(diag.get("classifier_debug"), dict) else {}
    sample = diag.get("sample") if isinstance(diag.get("sample"), dict) else {}

    hsv = _clean_numeric_triplet(classifier_debug.get("hsv_median")) or _clean_numeric_triplet(sample.get("hsv_median"))
    lab = _clean_numeric_triplet(classifier_debug.get("lab_median")) or _lab_from_rgb_triplet(sample.get("rgb_median"))
    rgb = _clean_numeric_triplet(sample.get("rgb_median"))

    return {
        "hsv_median": hsv,
        "lab_median": lab,
        "rgb_median": rgb,
        "sample_pixels": sample.get("sample_pixels"),
        "template_score": classifier_debug.get("template_score"),
        "template_margin": classifier_debug.get("template_margin"),
    }


def _latest_color_diagnostics_snapshot() -> tuple[dict[str, Any], np.ndarray | None, int, int, int, int]:
    data = latest_analysis_data.get("data", {}) if isinstance(latest_analysis_data, dict) else {}
    if not isinstance(data, dict) or not data:
        raise HTTPException(status_code=404, detail="No latest YOLO data available")
    frame = _get_monitor_frame_copy()
    frame_h = frame_w = 0
    if frame is not None:
        frame_h, frame_w = frame.shape[:2]
    source_w = int(data.get("_source_img_w") or data.get("img_w") or frame_w or 1280)
    source_h = int(data.get("_source_img_h") or data.get("img_h") or frame_h or 720)
    if frame_w <= 0 or frame_h <= 0:
        frame_w = 1280
        frame_h = 720
    return data, frame, source_w, source_h, frame_w, frame_h


def _parse_sample_assignments(raw_assignments: Any) -> dict[int, dict[str, Any]]:
    if isinstance(raw_assignments, dict):
        iterator = raw_assignments.items()
    elif isinstance(raw_assignments, list):
        iterator = []
        for item in raw_assignments:
            if isinstance(item, dict):
                iterator.append((item.get("index"), item.get("number", item.get("actual_number"))))
    else:
        raise HTTPException(status_code=400, detail="assignments must be object or list")

    assignments: dict[int, dict[str, Any]] = {}
    for raw_index, raw_number in iterator:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid assignment index: {raw_index}")
        identity = _ball_identity_from_number(raw_number)
        if identity["number"] == 0:
            continue
        assignments[index] = identity
    if not assignments:
        raise HTTPException(status_code=400, detail="No color ball assignments provided")
    return assignments


def _save_color_sample_crop(frame: np.ndarray | None, bbox: Any, profile_id: int, color: str, sample_id: str) -> str | None:
    if frame is None or not isinstance(bbox, list) or len(bbox) < 4:
        return None
    x, y, w, h = [int(v) for v in bbox[:4]]
    frame_h, frame_w = frame.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(frame_w, x + max(1, w))
    y1 = min(frame_h, y + max(1, h))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    target_dir = COLOR_SAMPLE_DIR / f"profile_{profile_id}" / color.lower()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{sample_id}.jpg"
    if not cv2.imwrite(str(path), crop):
        return None
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def _circular_hue_mean_values(values: list[float]) -> float:
    if not values:
        return 0.0
    angles = np.array(values, dtype=np.float32) / 180.0 * (2.0 * np.pi)
    s = float(np.sum(np.sin(angles)))
    c = float(np.sum(np.cos(angles)))
    if abs(s) < 1e-6 and abs(c) < 1e-6:
        return float(np.median(np.array(values, dtype=np.float32)))
    theta = math.atan2(s, c)
    if theta < 0:
        theta += 2.0 * np.pi
    return float((theta / (2.0 * np.pi)) * 180.0)


def _rebuild_learned_templates_from_samples(mappings: dict[str, Any], min_samples: int = 3) -> dict[str, Any]:
    sample_sets = mappings.get("_sample_sets") if isinstance(mappings.get("_sample_sets"), dict) else {}
    templates: dict[str, Any] = {}
    for color, samples in sample_sets.items():
        if color not in COLOR_CALIBRATION_MODES["pool"] or not isinstance(samples, list):
            continue
        hsv_rows: list[list[float]] = []
        lab_rows: list[list[float]] = []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            hsv = _clean_numeric_triplet(sample.get("hsv_median"))
            lab = _clean_numeric_triplet(sample.get("lab_median"))
            if hsv is None or lab is None:
                continue
            hsv_rows.append(hsv)
            lab_rows.append(lab)
        if len(hsv_rows) < min_samples:
            continue
        hsv_arr = np.array(hsv_rows, dtype=np.float32)
        lab_arr = np.array(lab_rows, dtype=np.float32)
        templates[color] = {
            "hsv_median": [
                round(_circular_hue_mean_values([float(v) for v in hsv_arr[:, 0].tolist()]), 3),
                round(float(np.median(hsv_arr[:, 1])), 3),
                round(float(np.median(hsv_arr[:, 2])), 3),
            ],
            "lab_median": [round(float(v), 3) for v in np.median(lab_arr, axis=0).tolist()],
            "sample_count": len(hsv_rows),
            "source": "sample_sets",
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    return templates


def _template_distance_for_feature(color: str, hsv: list[float], lab: list[float], templates: dict[str, Any]) -> float:
    tpl = templates.get(color)
    if not isinstance(tpl, dict):
        return 999.0
    ref_hsv = _clean_numeric_triplet(tpl.get("hsv_median"))
    ref_lab = _clean_numeric_triplet(tpl.get("lab_median"))
    if ref_hsv is None or ref_lab is None:
        return 999.0
    hue_d = min(abs(hsv[0] - ref_hsv[0]), 180.0 - abs(hsv[0] - ref_hsv[0])) / 90.0
    sat_d = abs(hsv[1] - ref_hsv[1]) / 255.0
    val_d = abs(hsv[2] - ref_hsv[2]) / 255.0
    lab_d = float(np.linalg.norm(np.array(lab, dtype=np.float32) - np.array(ref_lab, dtype=np.float32))) / 64.0
    return 0.35 * hue_d + 0.20 * sat_d + 0.15 * val_d + 0.30 * lab_d


def _classify_feature_with_templates(hsv: list[float], lab: list[float], templates: dict[str, Any]) -> dict[str, Any]:
    scores = {
        color: _template_distance_for_feature(color, hsv, lab, templates)
        for color in templates.keys()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1])
    if not ranked:
        return {"label": "Unknown", "score": None, "second_label": None, "second_score": None, "margin": None, "scores": {}}
    best_label, best_score = ranked[0]
    second_label = ranked[1][0] if len(ranked) > 1 else None
    second_score = float(ranked[1][1]) if len(ranked) > 1 else None
    margin = float(second_score - best_score) if second_score is not None else 999.0
    label = best_label
    if best_score > 0.72 or margin < 0.012:
        label = "Unknown"
    return {
        "label": label,
        "score": float(best_score),
        "second_label": second_label,
        "second_score": second_score,
        "margin": margin,
        "scores": {name: round(float(score), 4) for name, score in ranked},
    }

def _color_diagnostic_ball(
    ball: dict[str, Any],
    index: int,
    frame: np.ndarray | None,
    source_w: int,
    source_h: int,
    frame_w: int,
    frame_h: int,
    kind: str = "color",
) -> dict[str, Any]:
    raw_bbox = [
        ball.get("x"),
        ball.get("y"),
        ball.get("w"),
        ball.get("h"),
    ]
    source_bbox = None
    try:
        source_bbox = [int(round(float(v))) for v in raw_bbox]
    except (TypeError, ValueError):
        source_bbox = None

    view_bbox = _scale_bbox_to_frame(raw_bbox, source_w, source_h, frame_w, frame_h)
    sample = _sample_ball_roi_color(frame, view_bbox) if frame is not None and view_bbox else None
    color_debug = ball.get("color_debug") if isinstance(ball.get("color_debug"), dict) else {}
    temporal_debug = ball.get("temporal_debug") if isinstance(ball.get("temporal_debug"), dict) else {}

    return {
        "index": index,
        "kind": kind,
        "source_bbox": source_bbox,
        "view_bbox": view_bbox,
        "conf": ball.get("conf"),
        "detected": {
            "color": ball.get("color"),
            "style": ball.get("style"),
            "number": ball.get("number"),
            "white_ratio": ball.get("white_ratio"),
            "dark_ratio": ball.get("dark_ratio"),
            "color_ratio": ball.get("color_ratio"),
        },
        "frontend_overlay_color": _ball_overlay_color_hex(ball),
        "sample": sample,
        "classifier_debug": {
            "hsv_median": color_debug.get("hsv_median"),
            "lab_median": color_debug.get("lab_median"),
            "template_score": color_debug.get("template_score"),
            "score_by_name": color_debug.get("score_by_name"),
            "template_best_label": color_debug.get("template_best_label"),
            "template_second_label": color_debug.get("template_second_label"),
            "template_second_score": color_debug.get("template_second_score"),
            "template_margin": color_debug.get("template_margin"),
            "learned_template_count": color_debug.get("learned_template_count"),
            "final_label": color_debug.get("final_label"),
            "final_style": color_debug.get("final_style"),
            "temporal_matched": temporal_debug.get("matched"),
            "temporal_distance": temporal_debug.get("distance"),
            "temporal_history_len": temporal_debug.get("history_len"),
            "label_raw": temporal_debug.get("label_raw"),
            "label_smoothed": temporal_debug.get("label_smoothed"),
            "label_lock": temporal_debug.get("label_lock"),
            "label_switch_candidate": temporal_debug.get("label_switch_candidate"),
            "label_switch_hits": temporal_debug.get("label_switch_hits"),
            "label_signal_strength": temporal_debug.get("label_signal_strength"),
            "style_raw": temporal_debug.get("style_raw"),
            "style_smoothed": temporal_debug.get("style_smoothed"),
            "style_lock": temporal_debug.get("style_lock"),
            "style_switch_candidate": temporal_debug.get("switch_candidate"),
            "style_switch_hits": temporal_debug.get("switch_hits"),
            "style_signal_strength": temporal_debug.get("style_signal_strength"),
        },
    }


@app.get("/api/color-diagnostics/latest")
async def latest_color_diagnostics():
    """回傳最新球色分類診斷資料，不改變目前追蹤狀態。"""
    data = latest_analysis_data.get("data", {}) if isinstance(latest_analysis_data, dict) else {}
    if not isinstance(data, dict) or not data:
        raise HTTPException(status_code=404, detail="No latest YOLO data available")

    frame = _get_monitor_frame_copy()
    frame_h = frame_w = 0
    if frame is not None:
        frame_h, frame_w = frame.shape[:2]
    source_w = int(data.get("_source_img_w") or data.get("img_w") or frame_w or 1280)
    source_h = int(data.get("_source_img_h") or data.get("img_h") or frame_h or 720)
    if frame_w <= 0 or frame_h <= 0:
        frame_w = 1280
        frame_h = 720

    balls: list[dict[str, Any]] = []
    for index, ball in enumerate(data.get("balls", []) or []):
        if isinstance(ball, dict):
            balls.append(_color_diagnostic_ball(ball, index, frame, source_w, source_h, frame_w, frame_h))

    white_ball = data.get("white_ball")
    if isinstance(white_ball, list) and len(white_ball) >= 4:
        white_packet = {
            "x": white_ball[0],
            "y": white_ball[1],
            "w": white_ball[2],
            "h": white_ball[3],
            "conf": None,
            "color": "White",
            "style": "Cue",
            "number": 0,
        }
        balls.insert(0, _color_diagnostic_ball(white_packet, -1, frame, source_w, source_h, frame_w, frame_h, kind="white"))

    return {
        "status": "success",
        "timestamp": data.get("timestamp"),
        "source_frame_id": data.get("_source_frame_id"),
        "source_size": {"width": source_w, "height": source_h},
        "view_size": {"width": frame_w, "height": frame_h},
        "tracking_state": "active" if system_state.get("is_analyzing") else "idle",
        "detected_count": len(data.get("balls", []) or []),
        "white_ball": data.get("white_ball"),
        "cue_laser_only": bool(data.get("cue_laser_only")),
        "raw_yolo_boxes": data.get("raw_yolo_boxes", []) if isinstance(data.get("raw_yolo_boxes"), list) else [],
        "white_fallback_debug": data.get("white_fallback_debug"),
        "table": {
            "roi": data.get("table_roi"),
            "roi_status": data.get("table_roi_status"),
            "cloth_color": getattr(tracker, "current_table_color", None) if tracker is not None else None,
            "hsv_lower": getattr(tracker, "hsv_lower", None).tolist() if tracker is not None and hasattr(tracker, "hsv_lower") else None,
            "hsv_upper": getattr(tracker, "hsv_upper", None).tolist() if tracker is not None and hasattr(tracker, "hsv_upper") else None,
        },
        "color_calibration": dict(color_calibration_state),
        "notes": [
            "frontend_overlay_color mirrors StreamPage number-first color mapping.",
            "sample.hsv_median is sampled from the current monitor frame and is for diagnosis only.",
            "classifier_debug is populated only when COLOR_DEBUG_ENABLED=true.",
        ],
        "balls": balls,
    }


def _score_table_color_candidate(frame: np.ndarray, hsv_lower: Any, hsv_upper: Any) -> dict[str, Any]:
    hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_img, np.array(hsv_lower, dtype=np.uint8), np.array(hsv_upper, dtype=np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    frame_h, frame_w = frame.shape[:2]
    frame_area = float(frame_w * frame_h)
    best: dict[str, Any] = {"score": 0.0, "area": 0.0, "ratio": 0.0, "rect": None, "aspect": 0.0}

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < max(8000.0, frame_area * 0.02):
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            continue
        aspect = w / h
        area_ratio = area / frame_area
        aspect_penalty = max(0.0, 1.0 - abs(aspect - 2.05) / 1.35)
        coverage_penalty = 1.0 if 0.18 <= area_ratio <= 0.78 else 0.45
        score = area * max(0.2, aspect_penalty) * coverage_penalty
        if score > best["score"]:
            best = {
                "score": score,
                "area": area,
                "ratio": area_ratio,
                "rect": [x, y, w, h],
                "aspect": aspect,
            }
    return best


def _clear_table_overlay_cache() -> None:
    latest_analysis_data["data"] = {}
    latest_analysis_data["overlay_data"] = None
    latest_analysis_data["multi_plan"] = None
    latest_analysis_data["planner_error"] = None
    latest_analysis_data["ar_route_segments"] = []


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
        cast(Any, config).TABLE_CLOTH_COLOR = "custom"
        config.TABLE_COLOR_PRESETS["custom"]["hsv_lower"] = np.array(hsv_lower, dtype=np.uint8)
        config.TABLE_COLOR_PRESETS["custom"]["hsv_upper"] = np.array(hsv_upper, dtype=np.uint8)
        config.save_table_color_preference("custom", hsv_lower, hsv_upper)
    else:
        # 使用預設顏色
        success = tracker.update_table_color(color_name)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid color name: {color_name}. Available: {list(config.TABLE_COLOR_PRESETS.keys())}"
            )
        cast(Any, config).TABLE_CLOTH_COLOR = color_name
        config.save_table_color_preference(color_name)

    _clear_table_overlay_cache()
    latest_analysis_data["ar_best_route"] = {
        "route_segments": [],
        "cue_landing_point": None,
        "cue_landing_zone": None,
        "position_play": None,
        "lookahead": None,
    }

    return {
        "status": "success",
        "color": color_name,
        "message": f"Table color updated to {color_name}",
        "hsv_lower": tracker.hsv_lower.tolist(),
        "hsv_upper": tracker.hsv_upper.tolist(),
    }


@app.post("/api/table/color/auto-detect")
async def auto_detect_table_color():
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")

    frame = _get_monitor_frame_copy()
    if frame is None:
        raise HTTPException(status_code=404, detail="No camera frame available")

    candidates = []
    for key, preset in config.TABLE_COLOR_PRESETS.items():
        if key == "custom":
            continue
        result = _score_table_color_candidate(frame, preset["hsv_lower"], preset["hsv_upper"])
        candidates.append({"color": key, **result})

    candidates.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    if not candidates or float(candidates[0].get("score", 0.0)) <= 0:
        raise HTTPException(status_code=404, detail="Unable to detect table cloth color")

    selected = candidates[0]
    color_name = str(selected["color"])
    if not tracker.update_table_color(color_name):
        raise HTTPException(status_code=500, detail=f"Failed to apply detected color: {color_name}")

    cast(Any, config).TABLE_CLOTH_COLOR = color_name
    config.save_table_color_preference(color_name)
    _clear_table_overlay_cache()

    return {
        "status": "success",
        "color": color_name,
        "score": selected["score"],
        "rect": selected["rect"],
        "candidates": candidates,
        "hsv_lower": tracker.hsv_lower.tolist(),
        "hsv_upper": tracker.hsv_upper.tolist(),
    }


@app.get("/api/table/roi-adjustment")
async def get_table_roi_adjustment():
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    source_w, source_h = _runtime_source_size()
    return {
        "status": "success",
        "adjustment": tracker.table_roi_adjustment,
        "table_roi_raw": tracker.table_roi_raw,
        "table_roi": tracker.table_roi,
        "table_roi_status": tracker.table_roi_status,
        "image_width": source_w,
        "image_height": source_h,
        "source_width": source_w,
        "source_height": source_h,
    }


@app.post("/api/table/roi-adjustment")
async def update_table_roi_adjustment(request: dict = Body(...)):
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    adjustment = tracker.set_table_roi_adjustment(request)
    snapshot = _apply_runtime_table_roi_change()
    source_w, source_h = _runtime_source_size()
    return {
        "status": "success",
        "adjustment": adjustment,
        "table_roi_raw": snapshot.get("table_roi_raw"),
        "table_roi": snapshot.get("table_roi"),
        "table_roi_points": snapshot.get("table_roi_points"),
        "table_roi_status": snapshot.get("table_roi_status"),
        "image_width": source_w,
        "image_height": source_h,
        "source_width": source_w,
        "source_height": source_h,
    }


@app.post("/api/table/roi-adjustment/reset")
async def reset_table_roi_adjustment():
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    adjustment = tracker.reset_table_roi_adjustment()
    snapshot = _apply_runtime_table_roi_change()
    source_w, source_h = _runtime_source_size()
    return {
        "status": "success",
        "adjustment": adjustment,
        "table_roi_raw": snapshot.get("table_roi_raw"),
        "table_roi": snapshot.get("table_roi"),
        "table_roi_points": snapshot.get("table_roi_points"),
        "table_roi_status": snapshot.get("table_roi_status"),
        "image_width": source_w,
        "image_height": source_h,
        "source_width": source_w,
        "source_height": source_h,
    }


@app.get("/api/table/roi-polygon")
async def get_table_roi_polygon():
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    source_w, source_h = _runtime_source_size()
    return {
        "status": "success",
        "points": _monitor_roi_points(getattr(tracker, "table_roi_points", None)),
        "table_roi": tracker.table_roi,
        "table_roi_points": _monitor_roi_points(getattr(tracker, "table_roi_points", None)),
        "table_roi_status": tracker.table_roi_status,
        "image_width": source_w,
        "image_height": source_h,
        "source_width": source_w,
        "source_height": source_h,
        "points_image_width": 1280,
        "points_image_height": 720,
    }


@app.post("/api/table/roi-polygon")
async def update_table_roi_polygon(request: Any = Body(...)):
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    points = request.get("points") if isinstance(request, dict) else request
    source_w, source_h = _runtime_source_size()
    try:
        editor_w = int((request or {}).get("image_width") or (request or {}).get("img_w") or 1280) if isinstance(request, dict) else 1280
        editor_h = int((request or {}).get("image_height") or (request or {}).get("img_h") or 720) if isinstance(request, dict) else 720
    except (TypeError, ValueError):
        editor_w, editor_h = 1280, 720
    source_points = _scale_roi_points(points, editor_w, editor_h, source_w, source_h)
    try:
        saved_points = tracker.set_table_roi_polygon(source_points)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    snapshot = _apply_runtime_table_roi_change()
    monitor_points = _monitor_roi_points(saved_points)
    return {
        "status": "success",
        "points": monitor_points,
        "table_roi": snapshot["table_roi"],
        "table_roi_points": monitor_points,
        "table_roi_status": snapshot["table_roi_status"],
        "holes": snapshot["holes"],
        "image_width": source_w,
        "image_height": source_h,
        "source_width": source_w,
        "source_height": source_h,
        "points_image_width": 1280,
        "points_image_height": 720,
    }


@app.post("/api/table/roi-polygon/reset")
async def reset_table_roi_polygon():
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    tracker.reset_table_roi_polygon()
    snapshot = _apply_runtime_table_roi_change()
    source_w, source_h = _runtime_source_size()
    return {
        "status": "success",
        "points": None,
        "table_roi": snapshot["table_roi"],
        "table_roi_points": None,
        "table_roi_status": snapshot["table_roi_status"],
        "holes": snapshot["holes"],
        "image_width": source_w,
        "image_height": source_h,
        "source_width": source_w,
        "source_height": source_h,
    }


def _build_coach_chat_prompt(message: str, context: dict[str, Any]) -> str:
    def _short_json(value: Any, limit: int = 900) -> str:
        if value in (None, "", [], {}):
            return "無"
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return text if len(text) <= limit else f"{text[:limit]}..."

    def _summarize_balls(raw_balls: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_balls, list):
            return []

        summarized: list[dict[str, Any]] = []
        for ball in raw_balls[:12]:
            if not isinstance(ball, dict):
                continue

            center = ball.get("center") or ball.get("position") or {}
            if isinstance(center, (list, tuple)) and len(center) >= 2:
                x_value, y_value = center[0], center[1]
            elif isinstance(center, dict):
                x_value = center.get("x")
                y_value = center.get("y")
            else:
                x_value = ball.get("x")
                y_value = ball.get("y")

            item: dict[str, Any] = {
                "label": ball.get("label") or ball.get("name") or ball.get("class_name"),
                "number": ball.get("number") or ball.get("ball_number"),
                "color": ball.get("color"),
                "type": ball.get("type"),
            }
            if x_value is not None and y_value is not None:
                try:
                    item["center"] = [round(x_value, 1), round(y_value, 1)]
                except (TypeError, ValueError):
                    pass
            confidence_val = ball.get("confidence")
            if confidence_val is not None:
                try:
                    item["confidence"] = round(confidence_val, 3)
                except (TypeError, ValueError):
                    pass

            summarized.append({key: value for key, value in item.items() if value not in (None, "", [])})

        return summarized

    def _summarize_ai_coach(raw_ai_coach: Any) -> dict[str, Any] | None:
        if not isinstance(raw_ai_coach, dict):
            return None
        keep_keys = ("semantic_description", "recommendation", "confidence", "error")
        return {key: raw_ai_coach.get(key) for key in keep_keys if raw_ai_coach.get(key) not in (None, "")}

    def _summarize_multi_plan(raw_multi_plan: Any) -> dict[str, Any] | None:
        if not isinstance(raw_multi_plan, dict):
            return None

        best_plan = raw_multi_plan.get("best_plan") or raw_multi_plan.get("best") or raw_multi_plan
        if not isinstance(best_plan, dict):
            return None

        keep_keys = (
            "route_type",
            "target_ball",
            "target_ball_number",
            "success_prob",
            "success_rate",
            "difficulty",
            "difficulty_level",
            "stroke_hint",
            "cue_action",
        )
        return {key: best_plan.get(key) for key in keep_keys if best_plan.get(key) not in (None, "")}

    return (
        "你是撞球 AI Coach，請用繁體中文回答。"
        "回答要短、具體、可執行，優先說下一桿建議、目標球、母球控制與風險。\n\n"
        f"玩家問題：{message}\n\n"
        f"目前偵測球資料摘要：{_short_json(_summarize_balls(context.get('balls')))}\n"
        f"目前 AI Coach 自動分析：{_short_json(_summarize_ai_coach(context.get('ai_coach')))}\n"
        f"目前最佳路徑規劃：{_short_json(_summarize_multi_plan(context.get('multi_plan')))}\n"
    )


def _legacy_disabled_ai_coach_chat_sync(message: str, context: dict[str, Any]) -> str:
    raise RuntimeError("Direct AI Coach vLLM calls are disabled; use CoachBridge WebSocket.")
    payload = {
        "model": str(getattr(config, "AI_COACH_MODEL", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")),
        "messages": [
            {
                "role": "system",
                "content": "你是專業撞球教練，請用繁體中文給出精簡、實戰導向的建議。",
            },
            {
                "role": "user",
                "content": _build_coach_chat_prompt(message, context),
            },
        ],
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 220,
    }
    raise RuntimeError("Direct AI Coach vLLM calls are disabled; use CoachBridge WebSocket.")


def _read_upstream_error(exc: Any) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    if not body:
        return f"HTTP {exc.code}: {exc.reason}"
    return f"HTTP {exc.code}: {body[:600]}"


def _current_fps_for_coach() -> float:
    if global_perf_monitor:
        try:
            return float(global_perf_monitor.get_stats().get("current_fps", 0.0) or 0.0)
        except Exception:
            return 0.0
    return 0.0


def _balls_outside_table_roi(data_packet: dict[str, Any]) -> list[dict[str, Any]]:
    roi = data_packet.get("table_roi")
    if not isinstance(roi, (list, tuple)) or len(roi) < 4:
        return []
    try:
        x0, y0, w, h = [float(value) for value in roi[:4]]
    except (TypeError, ValueError):
        return []
    x1 = x0 + w
    y1 = y0 + h
    outside: list[dict[str, Any]] = []
    for ball in data_packet.get("balls", []) or []:
        if not isinstance(ball, dict):
            continue
        try:
            cx = float(ball.get("x", 0.0)) + float(ball.get("w", 0.0)) / 2.0
            cy = float(ball.get("y", 0.0)) + float(ball.get("h", 0.0)) / 2.0
        except (TypeError, ValueError):
            continue
        if cx < x0 or cx > x1 or cy < y0 or cy > y1:
            outside.append({
                "number": ball.get("number"),
                "label": ball.get("label") or ball.get("color"),
                "center": [round(cx, 1), round(cy, 1)],
            })
    return outside[:6]


def _lighting_status_from_hsv(hsv_avg: Any) -> str:
    if not isinstance(hsv_avg, (list, tuple)) or len(hsv_avg) < 3:
        return "unknown"
    try:
        value = float(hsv_avg[2])
    except (TypeError, ValueError):
        return "unknown"
    if value < 45:
        return "too_dark"
    if value > 235:
        return "too_bright"
    return "normal"


def _build_coach_system_status(data_packet: dict[str, Any]) -> dict[str, Any]:
    data_packet = data_packet if isinstance(data_packet, dict) else {}
    hsv_avg = data_packet.get("hsv_avg") or data_packet.get("hsv_center")
    balls_outside_roi = _balls_outside_table_roi(data_packet)
    return {
        "yolo_status": "offline" if _is_yolo_stalled() else "online",
        "fps": round(_current_fps_for_coach(), 2),
        "roi_status": "outside_bounds" if balls_outside_roi else str(data_packet.get("table_roi_status") or "normal"),
        "balls_outside_roi": balls_outside_roi,
        "hsv_avg": hsv_avg,
        "lighting_status": _lighting_status_from_hsv(hsv_avg),
        "detected_count": len(data_packet.get("balls", []) or []),
    }


def _build_coach_ui_context(provided_context: dict[str, Any] | None) -> dict[str, Any]:
    source = provided_context.get("ui_context") if isinstance(provided_context, dict) else None
    if not isinstance(source, dict):
        source = provided_context if isinstance(provided_context, dict) else {}
    return {
        "auth_type": source.get("auth_type") or source.get("type"),
        "user_id": source.get("user_id"),
        "username": source.get("username"),
        "accent_color": source.get("accent_color"),
    }


def _context_signature_value(context: dict[str, Any]) -> str | None:
    debug = context.get("debug") if isinstance(context.get("debug"), dict) else {}
    signature = debug.get("signature")
    return str(signature) if signature else None


def _is_action_suggestion_context(context: dict[str, Any]) -> bool:
    request = context.get("request") if isinstance(context, dict) and isinstance(context.get("request"), dict) else {}
    mode = request.get("response_mode") or request.get("type")
    if not mode and isinstance(context, dict):
        mode = context.get("active_response_mode")
    return str(mode or "").strip() == "action_suggestion"


def _is_analytics_advice_context(context: dict[str, Any]) -> bool:
    request = context.get("request") if isinstance(context, dict) and isinstance(context.get("request"), dict) else {}
    analytics_context = context.get("analytics_context") if isinstance(context, dict) and isinstance(context.get("analytics_context"), dict) else {}
    return (
        str(request.get("intent") or "").strip() == "analytics_advice"
        or str(request.get("response_mode") or "").strip() == "analytics_advice"
        or str(analytics_context.get("schema_version") or "").strip() == "coach.analytics_context.v1"
    )


def _format_coach_analytics_rate(value: Any) -> str:
    if value is None:
        return "尚無"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if 0 <= number <= 1:
        return f"{round(number * 100)}%"
    return f"{round(number, 1)}"


def _fallback_analytics_advice_from_context(context: dict[str, Any]) -> str:
    analytics = context.get("analytics_context") if isinstance(context.get("analytics_context"), dict) else {}
    player = str(analytics.get("player") or "目前帳號").strip()
    if not analytics.get("has_data"):
        return (
            f"{player} 目前可分析資料還少，還不足以判斷穩定弱點或趨勢。"
            "先完成幾次練習或對戰累積出桿與練習紀錄；下一步可先做直球準度和定點停球各 10 分鐘。"
        )

    player_stats = analytics.get("player_stats") if isinstance(analytics.get("player_stats"), dict) else {}
    overview = analytics.get("overview") if isinstance(analytics.get("overview"), dict) else {}
    mobile = analytics.get("mobile_analytics_v1") if isinstance(analytics.get("mobile_analytics_v1"), dict) else {}
    trainings = mobile.get("recommended_trainings") if isinstance(mobile.get("recommended_trainings"), list) else []
    first_training = trainings[0] if trainings and isinstance(trainings[0], dict) else {}
    weakest = str(mobile.get("weakest_ability") or "母球控制").strip()
    strongest = str(mobile.get("strongest_ability") or "目前強項").strip()
    training_title = str(first_training.get("title") or "定點停球訓練").strip()
    total_practice = int(player_stats.get("total_practice_sessions") or 0)
    total_games = int(player_stats.get("total_games") or 0)
    pocket_rate = _format_coach_analytics_rate(overview.get("pocket_rate"))
    return (
        f"目前資料顯示你累積 {total_practice} 次練習、{total_games} 場對戰，進球率約 {pocket_rate}。"
        f"{strongest}相對穩，但{weakest}是下一個優先加強點。"
        f"下一步先做「{training_title}」10 到 12 分鐘，重點放在固定出桿節奏與母球停位。"
    )


def _is_analytics_advice_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    return str(result.get("source") or "").strip().startswith("analytics_advice")


def _fallback_action_suggestion_from_context(context: dict[str, Any]) -> str:
    planner = context.get("planner") if isinstance(context.get("planner"), dict) else {}
    best_route = planner.get("best_route") if isinstance(planner.get("best_route"), dict) else {}
    result = planner.get("result") if isinstance(planner.get("result"), dict) else {}
    risk_flags: list[str] = []
    for source in (best_route, result):
        flags = source.get("risk_flags") if isinstance(source, dict) else None
        if isinstance(flags, list):
            risk_flags.extend(str(flag).lower() for flag in flags)
    risk_text = " ".join(risk_flags)
    if any(token in risk_text for token in ("scratch", "cue_ball_potted", "洗袋", "母球落袋")):
        return "這條線容易把母球帶向袋口，直接推進有洗袋風險。建議改用低桿擊打母球中心偏下方位，並降低出桿力道。這樣能抵消向前動能，保留母球控制。"
    if "thick" in risk_text:
        return "目前切球點過厚，母球容易吃太多角度而偏離預期路線。請將瞄準點向薄邊修正約 5mm，並降低出桿力道。這樣能讓目標球路更乾淨，維持母球控制。"
    if "thin" in risk_text:
        return "目前切球點偏薄，目標球容易少吃角度而偏出袋線。請將瞄準點向厚邊修正約 5mm，並用中等力道出桿。這樣能補足撞擊厚度，穩定母球走位。"
    if best_route:
        return "目前路線以穩定送球為主，過度加塞會讓母球路徑變難控。請保持中線瞄準，使用中桿與中等力道穩定送桿。這樣能讓母球停在下一桿容易銜接的位置。"
    return "目前進袋路線不穩，強攻容易讓母球失位或留下空檔。請用中桿小力完成合法碰球，讓母球停在檯面中區。這樣能降低失誤成本，保留下一桿選擇。"


def _clean_action_suggestion_reply(reply: str, context: dict[str, Any], *, allow_fallback: bool = True) -> str:
    text = str(reply or "").strip()
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"</?[^>]+>", "", text)
    text = re.sub(r"[*_`#>|-]+", " ", text)
    text = re.sub(r"\s+", " ", text.replace("\r", " ").replace("\n", " ")).strip()
    banned = re.compile(
        r"(FPS|VRAM|Coordinates|Deviation|座標|坐標|debug|JSON|planner|YOLO|系統|硬體|原始|"
        r"目標球/袋|風險：|力道：|桿法：|母球走位：|下一球目的：)",
        re.IGNORECASE,
    )
    if banned.search(text):
        parts = [part.strip() for part in re.split(r"[。！？!?]", text) if part.strip()]
        safe_parts = [part for part in parts if not banned.search(part)]
        text = "。".join(safe_parts[:2]).strip()
        if text:
            text += "。"
    if (not text or banned.search(text)) and allow_fallback:
        text = _fallback_action_suggestion_from_context(context)
    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", text)
    if sentences:
        text = "".join(sentences[:3]).strip()
    text = text[:260].strip()
    if not re.search(r"[。！？!?]$", text):
        text += "。"
    return text


def _is_action_suggestion_reply_usable(reply: str) -> bool:
    text = str(reply or "").strip()
    if not text:
        return False
    banned = re.compile(
        r"(FPS|VRAM|Coordinates|Deviation|座標|坐標|debug|JSON|planner|YOLO|系統|硬體|原始|"
        r"目標球/袋|風險：|力道：|桿法：|母球走位：|下一球目的：)",
        re.IGNORECASE,
    )
    return not bool(banned.search(text))


def _action_suggestion_unavailable_reply(locale: str) -> str:
    if locale == "zh-CN":
        return "AI Coach 这次没有生成可用的击球建议，请等球位稳定后再按一次产生建议。"
    if locale == "en-US":
        return "AI Coach did not produce a usable shot suggestion this time. Let the balls settle, then generate another suggestion."
    return "AI Coach 這次沒有產生可用的擊球建議，請等球位穩定後再按一次產生建議。"


def _strip_coach_reply_preface(reply: str) -> str:
    text = str(reply or "").strip()
    patterns = (
        r"^根據你(?:詢問|問)的(?:規則)?問題[，,：:\s]*",
        r"^根據您的(?:詢問|問題)[，,：:\s]*",
        r"^根據(?:九號球|Nine\s*ball|9\s*ball).*?(?:定義如下|如下)[：:\s]*",
        r"^.*?的定義如下[：:\s]*",
        r"^定義如下[：:\s]*",
    )
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    if text.startswith("合法碰球定義："):
        text = "合法碰球是" + text[len("合法碰球定義：") :].lstrip()
    return text


def _is_coach_rule_question(message: str) -> bool:
    text = str(message or "").lower()
    return any(
        keyword in text
        for keyword in (
            "合法碰球",
            "合法撞球",
            "合法擊球",
            "犯規",
            "九號球規則",
            "9號球規則",
            "nine ball rule",
            "rule",
        )
    )


def _coach_rule_reply(message: str) -> str:
    text = str(message or "")
    if re.search(r"(合法碰球|合法撞球|合法擊球)", text, re.IGNORECASE):
        return "合法碰球是在九號球中，母球必須先碰到檯面上號碼最小的目標球。若先碰到其他球、沒有碰到任何球，或擊球後沒有任何球進袋且沒有球碰到顆星，通常會被判犯規。"
    if re.search(r"(犯規|foul)", text, re.IGNORECASE):
        return "九號球常見犯規包含：母球未先碰到最低號目標球、母球洗袋、擊球後沒有球進袋也沒有球碰到顆星、球跳離球桌，或出桿時連擊。犯規後通常由對手取得自由球。"
    return "九號球的核心規則是每次出桿都要先碰檯面上號碼最小的球，但不一定要打進最低號球；只要合法碰球後讓任一目標球進袋，就可以繼續出桿。"


def _is_coach_ui_question(message: str) -> bool:
    text = str(message or "").lower()
    return any(
        keyword in text
        for keyword in (
            "設定",
            "设置",
            "介面",
            "界面",
            "顏色",
            "颜色",
            "配色",
            "主題",
            "主题",
            "強調色",
            "强调色",
            "外觀",
            "外观",
            "邊框",
            "边框",
            "roi",
            "校正",
            "存不了",
            "儲存",
            "保存",
            "語言",
            "语言",
            "換語言",
            "换语言",
            "切換語言",
            "切换语言",
        )
    )


def _coach_ui_reply(message: str, provided_context: Any = None) -> str:
    text = str(message or "")
    provided_context_payload = provided_context if isinstance(provided_context, dict) else {}
    ui_context = provided_context_payload.get("ui_context") if isinstance(provided_context_payload.get("ui_context"), dict) else {}
    auth_type = str(ui_context.get("auth_type") or ui_context.get("type") or "").lower()

    if re.search(r"(語言|语言|換語言|换语言|切換語言|切换语言)", text, re.IGNORECASE):
        return "你說的換語言比較像是一般設定，請到「設定 > 一般」調整語言。"
    if re.search(r"(顏色|颜色|配色|主題|主题|強調色|强调色|介面|界面|外觀|外观)", text, re.IGNORECASE):
        return "到「設定 > 外觀」可以更改介面顏色。進入後選擇「介面主題」或「強調色」，套用後聊天視窗、按鈕與重要狀態色會一起更新；如果想維持撞球桌的清爽感，翡翠綠是最穩的選擇。"
    if re.search(r"(邊框|边框|roi|球桌校正|桌面|球桌|校正)", text, re.IGNORECASE):
        return "到「設定 > 球桌校正」調整桌面邊框。進入後使用 ROI 微調，把四個角對準球桌內緣；若球常被判定跑出桌外，通常就是這裡需要重新校正。"
    if re.search(r"(存不了|保存|儲存|储存|sqlite|登入|登录|帳號|账号)", text, re.IGNORECASE):
        if auth_type == "guest":
            return "目前是訪客模式，所以個人設定不會寫入帳號資料庫。請到「設定 > 帳號管理」登入，登入後介面設定、對話紀錄與分析結果才會保存。"
        return "你已經是登入狀態，可以到「設定 > 一般」調整並保存設定；如果按下保存後沒有變化，先重新整理頁面再試一次。"
    return "到「設定」可以調整帳號、外觀、球桌校正與儲存相關選項。若你要改畫面顏色，請進「設定 > 外觀」。"


def _is_coach_social_question(message: str) -> bool:
    text = str(message or "").lower()
    return any(
        keyword in text
        for keyword in (
            "嗨",
            "你好",
            "哈囉",
            "哈啰",
            "在嗎",
            "在吗",
            "早安",
            "早上好",
            "早啊",
            "午安",
            "晚安",
            "hi",
            "hello",
            "good morning",
            "女朋友",
            "男朋友",
            "幾歲",
            "几岁",
            "戀愛",
            "恋爱",
            "很爛",
            "很烂",
            "心情不好",
            "先這樣",
            "先这样",
            "掰掰",
            "拜拜",
            "再見",
            "再见",
        )
    )


def _coach_social_fallback_reply(message: str) -> str:
    text = str(message or "").lower()
    if any(keyword in text for keyword in ("先這樣", "先这样", "掰掰", "拜拜", "再見", "再见")):
        return "好，今天先收桿。下次回來，我們再把節奏慢慢調順。"
    if any(keyword in text for keyword in ("女朋友", "男朋友", "幾歲", "几岁", "戀愛", "恋爱")):
        return "這題我先打安全球：我的私生活很單純，主要跟物理法則長期合作。"
    if any(keyword in text for keyword in ("很爛", "很烂", "心情不好")):
        return "手感差很正常，先別急著否定自己。下一桿只抓一件事：出桿穩住。"
    if any(keyword in text for keyword in ("早安", "早上好", "早啊", "good morning")):
        return "早，今天先順順開局。要不要先用幾桿暖手，把節奏找回來？"
    return "我在，今天先用輕鬆節奏開局。你想暖手，還是先聊一下今天的狀態？"


def _is_coach_billiards_knowledge_question(message: str) -> bool:
    text = str(message or "").lower()
    if not any(keyword in text for keyword in ("撞球", "台球", "pool", "billiard", "snooker", "斯諾克", "斯诺克")):
        return False
    return any(
        keyword in text
        for keyword in (
            "選手",
            "选手",
            "球員",
            "球员",
            "名將",
            "名将",
            "有名",
            "著名",
            "知名",
            "世界上",
            "世界級",
            "世界级",
            "冠軍",
            "冠军",
            "高手",
            "有哪些",
            "誰",
            "谁",
            "介紹",
            "介绍",
        )
    )


def _coach_billiards_knowledge_reply(message: str) -> str:
    text = str(message or "").lower()
    if any(keyword in text for keyword in ("斯諾克", "斯诺克", "snooker")):
        return "斯諾克領域常被提到的名將有 Ronnie O'Sullivan、Stephen Hendry、Steve Davis、Mark Selby 和 Judd Trump；如果你想看母球控制與長台準度，O'Sullivan 和 Selby 很值得研究。"
    return "撞球界常被提到的選手有 Efren Reyes、Shane Van Boening、Earl Strickland、Francisco Bustamante 和 Ko Pin Yi。新手可以先看 Efren Reyes 的走位與解球，他的選擇很像在提前三桿布局。"


def _is_coach_status_question(message: str) -> bool:
    text = str(message or "").lower()
    return any(keyword in text for keyword in ("yolo", "辨識", "识别", "穩定", "稳定", "畫面", "画面", "fps", "正常嗎", "準嗎", "准吗"))


def _is_coach_table_analysis_question(message: str) -> bool:
    text = str(message or "").lower()
    return any(
        keyword in text
        for keyword in (
            "翻袋",
            "中袋",
            "中間",
            "中间",
            "可以打",
            "怎麼打",
            "怎么打",
            "下一桿",
            "下一杆",
            "球路",
            "走位",
            "力道",
            "切球",
            "bank",
            "combo",
            "安全球",
        )
    )


def _coach_message_requires_visual_analysis(message: str, active_response_mode: str | None = None) -> bool:
    text = str(message or "").lower()
    visual_patterns = (
        r"這一桿|这一杆|這桿|这杆|剛剛那桿|刚刚那杆|這球|这球",
        r"下一桿|下一杆|下一顆|下一颗|打哪|怎麼打|怎么打|球路|走位|力道|切球|翻袋|下中袋|下中洞",
        r"可以打|能不能打|可不可以|目標球|目标球|袋口|母球|安全球|bank|combo",
        r"畫面正常嗎|画面正常吗|辨識準嗎|辨識准吗|辨識穩|辨識稳|yolo|偵測狀態|侦测状态",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in visual_patterns)


def _coach_message_requires_analytics(message: str) -> bool:
    text = str(message or "").lower()
    analytics_patterns = (
        r"數據|数据|資料|资料|統計|统计|勝率|胜率|進球率|进球率|命中率",
        r"弱點|弱点|弱項|弱项|哪裡弱|哪里弱|最弱|需要加強|需要加强",
        r"練習量|练习量|練習數|练习数|訓練量|训练量|趨勢|趋势|表現|表现",
        r"母球控制|走位能力|進攻表現|进攻表现|準度|准度|力道控制|出桿穩定|出杆稳定",
        r"最近狀態|最近状态|能力分數|能力分数|總場次|总场次|練習紀錄|练习记录",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in analytics_patterns)


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization[7:].strip()


def _authenticated_coach_user(authorization: str | None) -> dict[str, Any] | None:
    token = _extract_bearer_token(authorization)
    if not token:
        return None
    try:
        user = auth_account_store.authenticate_token(token)
    except Exception as exc:
        print(f"⚠️ AI Coach auth token lookup failed: {exc}")
        return None
    return user if isinstance(user, dict) else None


def _coach_auth_sources(provided_context: Any) -> list[dict[str, Any]]:
    if not isinstance(provided_context, dict):
        return []
    sources: list[dict[str, Any]] = []
    for key in ("ui_context", "user"):
        value = provided_context.get(key)
        if isinstance(value, dict):
            sources.append(value)
    sources.append(provided_context)
    return sources


def _coach_user_from_context_identity(provided_context: Any) -> dict[str, Any] | None:
    for source in _coach_auth_sources(provided_context):
        auth_type = str(source.get("auth_type") or source.get("type") or "").strip().lower()
        if auth_type == "guest":
            continue
        username = str(source.get("username") or "").strip()
        if username:
            return {"username": username, "id": source.get("user_id") or source.get("id")}
        user_id = source.get("user_id") or source.get("id")
        if user_id in (None, ""):
            continue
        try:
            user = auth_account_store.get_public_user_by_id(int(user_id))
        except Exception as exc:
            print(f"⚠️ AI Coach user_id lookup failed: {exc}")
            continue
        if isinstance(user, dict) and str(user.get("username") or "").strip():
            return user
    return None


def _coach_user_from_session(coach_session_id: str | None) -> dict[str, Any] | None:
    session_id = str(coach_session_id or "").strip()
    if not session_id:
        return None
    try:
        session = session_manager.get_session(session_id)
    except Exception as exc:
        print(f"⚠️ AI Coach session lookup failed: {exc}")
        return None
    if session is None:
        return None
    client_info = getattr(session, "client_info", None)
    return _coach_user_from_context_identity(client_info)


def _resolve_coach_analytics_user(
    provided_context: Any,
    authorization: str | None,
    coach_session_id: str | None = None,
) -> dict[str, Any] | None:
    token_user = _authenticated_coach_user(authorization)
    if token_user:
        return token_user
    context_user = _coach_user_from_context_identity(provided_context)
    if context_user:
        return context_user
    return _coach_user_from_session(coach_session_id)


def _trend_delta(points: list[dict[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        value = point.get(key)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if len(values) < 2:
        return None
    return round(values[-1] - values[0], 4)


def _build_coach_analytics_context(
    username: str,
    user: dict[str, Any] | None = None,
    range_name: str = "week",
    bucket: str = "day",
) -> dict[str, Any]:
    username = str(username or "").strip()
    if not username:
        return {
            "schema_version": "coach.analytics_context.v1",
            "has_data": False,
            "reason": "NO_AUTHENTICATED_PLAYER",
        }

    player_stats = replay_db.get_player_analytics(username)
    overview = replay_db.get_analytics_overview(username, range_name)
    offense = replay_db.get_analytics_offense(username, range_name)
    trends = replay_db.get_analytics_trends(username, bucket)
    mobile_user = user if isinstance(user, dict) else {"username": username}
    mobile_analytics_v1 = _build_mobile_analytics_v1(player_stats, username, mobile_user)
    trend_points = trends.get("points") if isinstance(trends.get("points"), list) else []

    has_data = bool(
        overview.get("has_data")
        or player_stats.get("total_games")
        or player_stats.get("total_practice_sessions")
        or (mobile_analytics_v1.get("score_confidence") == "medium")
    )
    return {
        "schema_version": "coach.analytics_context.v1",
        "player": username,
        "range": range_name,
        "trend_bucket": bucket,
        "has_data": has_data,
        "player_stats": player_stats,
        "overview": overview,
        "offense": offense,
        "trends": trends,
        "trend_summary": {
            "points": len(trend_points),
            "performance_score_delta": _trend_delta(trend_points, "performance_score"),
            "pocket_rate_delta": _trend_delta(trend_points, "pocket_rate"),
            "cue_control_score_delta": _trend_delta(trend_points, "cue_control_score"),
        },
        "mobile_analytics_v1": mobile_analytics_v1,
    }


def _coach_status_reply(context: dict[str, Any]) -> str:
    status = context.get("system_status") if isinstance(context.get("system_status"), dict) else {}
    yolo_status = str(status.get("yolo_status") or "unknown").lower()
    detected_count = status.get("detected_count")
    try:
        fps_value = float(status.get("fps"))
    except (TypeError, ValueError):
        fps_value = 0.0

    if yolo_status == "offline":
        return "目前偵測服務沒有連上，請先確認後端服務與模型都已啟動。"
    if 0 < fps_value < 15:
        return "目前畫面負載偏高，球路判斷可能會受影響。建議先降低解析度或關閉不必要的背景程式。"
    if detected_count is not None:
        return f"目前畫面有持續辨識到 {detected_count} 顆球，可以用來輔助判斷；若要精準路線，請等球完全靜止後再產生建議。"
    return "目前畫面有持續辨識到球，可以用來輔助判斷；若要精準路線，請等球完全靜止後再產生建議。"


def _coach_table_fallback_reply(message: str, provided_context: Any = None) -> str:
    text = str(message or "").lower()
    if any(keyword in text for keyword in ("翻袋", "bank")):
        if any(keyword in text for keyword in ("中洞", "中袋", "中間", "中间")):
            return "這球目前不建議強攻下中袋，翻袋角度容易讓母球失控。先用中小力碰球，讓母球留在檯面中區，保留下一桿選擇。"
        return "這球翻袋風險偏高，先不要硬攻袋口。用中小力完成合法碰球，讓母球停在檯面中區，下一桿會更好處理。"
    if any(keyword in text for keyword in ("走位", "母球", "下一桿", "下一杆")):
        return "先把母球控制在檯面中區，不要追求一次做到位。用中桿小力出桿，降低失位風險，下一桿會有更多選擇。"
    if any(keyword in text for keyword in ("力道", "速度", "speed")):
        return "這桿先把力道降到中小力，重點是讓母球停得住。不要加速硬推，避免目標球進攻失敗後母球跑到難處理的位置。"
    return "這球目前不適合強攻，先以完成合法碰球和保留母球位置為主。用中桿小力出桿，讓母球留在檯面中區，下一桿再找更清楚的進攻角度。"


def _build_coach_conversation_context(history: Any, current_message: str) -> dict[str, Any]:
    raw_messages = history if isinstance(history, list) else []
    messages: list[dict[str, Any]] = []
    for item in raw_messages[-20:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        text = str(item.get("text") or item.get("message") or "").strip()
        if role not in {"player", "coach", "user", "assistant"} or not text:
            continue
        normalized_role = "player" if role in {"player", "user"} else "coach"
        messages.append({
            "role": normalized_role,
            "text": text[:1000],
            "timestamp": item.get("timestamp"),
            "kind": item.get("kind"),
        })

    prior_messages = messages[:-1] if messages and messages[-1]["role"] == "player" and messages[-1]["text"] == current_message else messages
    last_user_question = next((m["text"] for m in reversed(prior_messages) if m["role"] == "player"), "")
    last_coach_answer = next((m["text"] for m in reversed(prior_messages) if m["role"] == "coach"), "")
    compact = re.sub(r"\s+", "", str(current_message or ""))
    social_self_question = bool(re.search(
        r"(我帥|我帅|我漂亮|我好看|我醜|我丑|你覺得我|你觉得我|長得帥|长得帅|長得好看|长得好看)",
        str(current_message or ""),
        re.IGNORECASE,
    ))
    follow_up_pattern = re.compile(
        r"(呢|那個|那個呢|為什麼|为什么|怎麼設定|怎么设置|怎麼改|怎么改|還有嗎|还有吗|剛剛|刚刚|上面|前面)",
        re.IGNORECASE,
    )
    has_explicit_follow_up_marker = bool(follow_up_pattern.search(str(current_message or "")))
    is_very_short_fragment = (
        len(compact) <= 3
        and bool(last_user_question or last_coach_answer)
        and not social_self_question
    )
    possible_follow_up = bool(
        not social_self_question
        and (has_explicit_follow_up_marker or is_very_short_fragment)
    )
    return {
        "recent_messages": messages,
        "last_user_question": last_user_question,
        "last_coach_answer": last_coach_answer,
        "possible_follow_up": possible_follow_up,
    }


def _coach_message_for_model(message: str, context: dict[str, Any]) -> str:
    conversation = context.get("conversation_context") if isinstance(context.get("conversation_context"), dict) else {}
    if not conversation.get("possible_follow_up"):
        return message
    if _coach_message_requires_visual_analysis(message):
        return message

    last_user = str(conversation.get("last_user_question") or "").strip()
    last_coach = str(conversation.get("last_coach_answer") or "").strip()
    if not last_user and not last_coach:
        return message

    parts = ["延續同一聊天室前文，直接回答玩家目前追問。"]
    if last_user:
        parts.append(f"上一題：{last_user[:500]}")
    if last_coach:
        parts.append(f"上一答：{last_coach[:700]}")
    parts.append(f"目前追問：{message}")
    parts.append("自然回答，不要要求玩家重問完整句。")
    return "\n".join(parts)


def _sanitize_coach_reply_for_user(reply: str, message: str, provided_context: Any = None) -> str:
    text = str(reply or "").strip()
    has_frontend_tag = bool(re.search(r"\[[a-zA-Z_][^\]]*\]|\[/[a-zA-Z_][^\]]*\]", text))
    if has_frontend_tag:
        text = re.sub(r"\[/?[a-zA-Z_][^\]]*\]", "", text).strip()
    context = provided_context if isinstance(provided_context, dict) else {}
    request = context.get("request") if isinstance(context.get("request"), dict) else {}
    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    is_non_analysis = (
        str(request.get("intent") or "").strip() == "non_analysis"
        or str(semantic_context.get("reason") or "").strip() == "NON_ANALYSIS_CHAT"
    )
    is_non_visual_message = (
        is_non_analysis
        or _is_coach_rule_question(message)
        or _is_coach_ui_question(message)
        or _is_coach_social_question(message)
        or _is_coach_billiards_knowledge_question(message)
    )
    conversation = context.get("conversation_context") if isinstance(context.get("conversation_context"), dict) else {}
    stale_clarification = bool(re.search(r"(需要更明確的情境|指定目標球|指定.*袋口|控制的母球位置)", text))
    internal = re.compile(
        r"(planner|NON_ANALYSIS_CHAT|資料不足|资料不足|best_route|position_play|semantic_context|"
        r"無法針對具體的擊球動作|无法针对具体的击球动作|需要更明確的情境)",
        re.IGNORECASE,
    )
    if _is_analytics_advice_context(context):
        cleaned = re.sub(r"shot[_\s-]*events?", "出桿紀錄", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"practice[_\s-]*records?", "練習紀錄", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"(planner|NON_ANALYSIS_CHAT|best_route|position_play|semantic_context|YOLO|debug|原始\s*JSON)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"(資料不足|资料不足)", "目前可分析資料還少", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or _fallback_analytics_advice_from_context(context)
    if not internal.search(text):
        return text
    if is_non_visual_message:
        cleaned = re.sub(
            r"(planner|NON_ANALYSIS_CHAT|best_route|position_play|semantic_context)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"(資料不足|资料不足)", "目前資訊有限", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(需要更明確的情境)", "我先照最可能的意思回答", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or text
    if _is_coach_rule_question(message):
        return _coach_rule_reply(message)
    if _is_coach_ui_question(message):
        return _coach_ui_reply(message, provided_context)
    if _is_coach_social_question(message):
        return _coach_social_fallback_reply(message)
    if _is_coach_billiards_knowledge_question(message):
        return _coach_billiards_knowledge_reply(message)
    if _is_coach_status_question(message):
        context = provided_context if isinstance(provided_context, dict) else {}
        return _coach_status_reply(context)
    if _is_coach_table_analysis_question(message):
        return _coach_table_fallback_reply(message, provided_context)
    if conversation.get("possible_follow_up") or stale_clarification:
        return "我先照前面的脈絡接著答；如果你指的是另一件事，再補我一個關鍵字。"
    return "我先用一般教練判斷回覆；如果你是在問當前球局，再補目標球或想打的袋口。"


def _persist_coach_exchange(
    *,
    session_id: str,
    user_message: str | None,
    coach_reply: str,
    locale: str,
    context: dict[str, Any],
    result: dict[str, Any],
) -> None:
    try:
        signature = _context_signature_value(context)
        if user_message:
            recording_manager.db.insert_coach_message({
                "session_id": session_id,
                "role": "player",
                "message": user_message,
                "locale": locale,
                "source": "user",
                "context_signature": signature,
                "metadata": {"request": context.get("request")},
            })
        recording_manager.db.insert_coach_message({
            "session_id": session_id,
            "role": "coach",
            "message": coach_reply,
            "locale": locale,
            "source": result.get("source"),
            "context_signature": signature,
            "metadata": {"confidence": result.get("confidence"), "error": result.get("error")},
        })
        recording_manager.db.insert_coach_analysis_result({
            "session_id": session_id,
            "analysis_type": result.get("source") or (context.get("request") or {}).get("type") or "chat",
            "result": result,
            "context_signature": signature,
            "source": result.get("source"),
        })
    except Exception as exc:
        print(f"⚠️ Failed to persist AI Coach exchange: {exc}")


def _get_current_coach_context(
    message: str,
    provided_context: Any = None,
    request_type: str = "chat",
    response_mode: str | None = None,
) -> tuple[str, dict[str, Any]]:
    runtime_packet = latest_analysis_data.get("data", {}) if isinstance(latest_analysis_data, dict) else {}
    semantic_context = coach_semantics.latest()
    if not isinstance(semantic_context, dict) or semantic_context.get("snapshot_at") != latest_analysis_data.get("coach_semantic_snapshot_at"):
        semantic_context = coach_semantics.update(
            runtime_packet if isinstance(runtime_packet, dict) else {},
            latest_analysis_data.get("multi_plan") if isinstance(latest_analysis_data, dict) else None,
        )
        latest_analysis_data["coach_semantic_snapshot_at"] = semantic_context.get("snapshot_at")

    intent = classify_coach_intent(message)
    provided_context_payload = provided_context if isinstance(provided_context, dict) else None
    multi_plan = latest_analysis_data.get("multi_plan") or (runtime_packet.get("multi_plan") if isinstance(runtime_packet, dict) else None)
    ai_coach = coach_bridge.get_latest_result()
    if provided_context_payload and provided_context_payload.get("ai_coach") is not None:
        ai_coach = provided_context_payload.get("ai_coach")

    context = coach_payload_builder.build(
        request_type=request_type,
        message=message,
        intent=intent,
        response_mode=response_mode,
        runtime_packet=runtime_packet if isinstance(runtime_packet, dict) else {},
        semantic_context=semantic_context,
        multi_plan=multi_plan,
        ai_coach=ai_coach,
        system_status=_build_coach_system_status(runtime_packet if isinstance(runtime_packet, dict) else {}),
        shot_event=latest_coach_shot_event or {},
        ui_context=_build_coach_ui_context(provided_context_payload),
        provided_context=provided_context_payload,
        ts_backend=int(time.time() * 1000),
    )
    return intent, context


SUPPORTED_COACH_LOCALES = {"zh-TW", "zh-CN", "en-US"}


def _normalize_coach_locale(value: Any) -> str:
    locale = str(value or "zh-TW").replace("_", "-")
    aliases = {
        "zh": "zh-TW",
        "zh-tw": "zh-TW",
        "zh-hant": "zh-TW",
        "zh-cn": "zh-CN",
        "zh-hans": "zh-CN",
        "en": "en-US",
        "en-us": "en-US",
    }
    normalized = aliases.get(locale.lower(), locale)
    return normalized if normalized in SUPPORTED_COACH_LOCALES else "zh-TW"


def _coach_message_for_locale(key: str, locale: str) -> str:
    messages = {
        "suggest_unstable": {
            "zh-TW": "目前檯面狀態變動中，請等球停妥後再產生建議。",
            "zh-CN": "目前台面状态仍在变化，请等球停稳后再生成建议。",
            "en-US": "The table is still changing. Wait for the balls to settle before generating a suggestion.",
        },
        "chat_unstable": {
            "zh-TW": "目前檯面狀態變動中，請等球停妥後再詢問。",
            "zh-CN": "目前台面状态仍在变化，请等球停稳后再提问。",
            "en-US": "The table is still changing. Wait for the balls to settle before asking.",
        },
        "suggest_yolo_unavailable": {
            "zh-TW": "YOLO 辨識已停擺，暫停產生建議。請重啟後端後再啟動辨識。",
            "zh-CN": "YOLO 识别已停摆，暂停生成建议。请重启后端后再启动识别。",
            "en-US": "YOLO analysis is stalled, so suggestions are paused. Restart the backend before enabling analysis again.",
        },
        "chat_yolo_unavailable": {
            "zh-TW": "YOLO 辨識已停擺，目前不能依球桌畫面回答。請重啟後端後再啟動辨識。",
            "zh-CN": "YOLO 识别已停摆，目前不能根据球桌画面回答。请重启后端后再启动识别。",
            "en-US": "YOLO analysis is stalled, so table-dependent answers are paused. Restart the backend before enabling analysis again.",
        },
    }
    return messages.get(key, {}).get(locale) or messages.get(key, {}).get("zh-TW") or ""


def _coach_message_can_skip_live_analysis(message: str) -> bool:
    return not _coach_message_requires_visual_analysis(message)


def _get_non_analysis_coach_context(
    message: str,
    provided_context: Any = None,
    request_type: str = "chat",
    response_mode: str | None = None,
) -> dict[str, Any]:
    """Build a context that intentionally excludes YOLO/planner data for social/UI chat."""
    provided_context_payload = provided_context if isinstance(provided_context, dict) else None
    return coach_payload_builder.build(
        request_type=request_type,
        message=message,
        intent="non_analysis",
        response_mode=response_mode,
        runtime_packet={},
        semantic_context={"valid": False, "reason": "NON_ANALYSIS_CHAT"},
        multi_plan=None,
        ai_coach=None,
        system_status={"yolo_status": "unknown", "fps": 0.0},
        shot_event={},
        ui_context=_build_coach_ui_context(provided_context_payload),
        provided_context=provided_context_payload,
        ts_backend=int(time.time() * 1000),
    )


def _get_analytics_coach_context(
    message: str,
    provided_context: Any = None,
    authorization: str | None = None,
    coach_session_id: str | None = None,
    request_type: str = "chat",
) -> dict[str, Any]:
    provided_context_payload = provided_context if isinstance(provided_context, dict) else None
    user = _resolve_coach_analytics_user(provided_context_payload, authorization, coach_session_id)
    username = str((user or {}).get("username") or "").strip()
    analytics_context = _build_coach_analytics_context(username, user)
    return coach_payload_builder.build(
        request_type=request_type,
        message=message,
        intent="analytics_advice",
        response_mode="analytics_advice",
        runtime_packet={},
        semantic_context={"valid": False, "reason": "ANALYTICS_ADVICE"},
        multi_plan=None,
        ai_coach=None,
        system_status={"yolo_status": "not_required", "fps": 0.0},
        shot_event={},
        ui_context=_build_coach_ui_context(provided_context_payload),
        analytics_context=analytics_context,
        provided_context=provided_context_payload,
        ts_backend=int(time.time() * 1000),
    )


async def _send_coach_chat(message: str, context: dict[str, Any], locale: str) -> dict[str, Any]:
    try:
        model_message = _coach_message_for_model(message, context)
        result = await coach_bridge.chat(model_message, context, locale=locale)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI Coach WebSocket unavailable: {exc}")

    if _is_analytics_advice_context(context) and not _is_analytics_advice_result(result):
        result = {
            **result,
            "recommendation": _fallback_analytics_advice_from_context(context),
            "source": "analytics_advice_backend_fallback",
        }

    reply = str(result.get("recommendation") or result.get("reply") or "").strip()
    if not reply:
        raise HTTPException(status_code=503, detail="AI Coach returned empty reply")
    reply = _strip_coach_reply_preface(reply)
    reply = _sanitize_coach_reply_for_user(reply, message, context)
    if _is_action_suggestion_context(context):
        reply = _clean_action_suggestion_reply(reply, context, allow_fallback=False)
        if not _is_action_suggestion_reply_usable(reply):
            reply = _action_suggestion_unavailable_reply(locale)
            result = {**result, "error": "AI Coach action suggestion was not usable"}
        result = {**result, "recommendation": reply, "source": "action_suggestion"}

    request_context = context.get("request") if isinstance(context.get("request"), dict) else {}
    session_id = str(request_context.get("coach_session_id") or getattr(config, "AI_COACH_SESSION_ID", "backend_yolo"))
    _persist_coach_exchange(
        session_id=session_id,
        user_message=message,
        coach_reply=reply,
        locale=locale,
        context=context,
        result=result,
    )

    return {
        "status": "success",
        "reply": reply,
        "timestamp": result.get("timestamp") or datetime.now().isoformat(),
    }


def _coach_stream_event(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _stream_preview_coach_reply(reply: str, context: dict[str, Any]) -> str:
    text = _strip_coach_reply_preface(str(reply or ""))
    text = re.sub(r"\[/?[a-zA-Z_][^\]]*\]", "", text)
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[^>]+>", "", text)

    if _is_action_suggestion_context(context):
        text = re.sub(r"[*_`#>|-]+", " ", text)
        text = re.sub(r"\s+", " ", text.replace("\r", " ").replace("\n", " ")).strip()
        banned = re.compile(
            r"(FPS|VRAM|Coordinates|Deviation|座標|坐標|debug|JSON|planner|YOLO|系統|硬體|原始|"
            r"目標球/袋|風險：|力道：|桿法：|母球走位：|下一球目的：)",
            re.IGNORECASE,
        )
        if banned.search(text):
            parts = [part.strip() for part in re.split(r"[。！？!?]", text) if part.strip()]
            safe_parts = [part for part in parts if not banned.search(part)]
            text = "。".join(safe_parts[:3]).strip()
    else:
        text = re.sub(r"\s+\n", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def _finalize_coach_stream_reply(
    reply: str,
    message: str,
    context: dict[str, Any],
    locale: str,
    result: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    final_reply = _strip_coach_reply_preface(reply)
    final_reply = _sanitize_coach_reply_for_user(final_reply, message, context)
    if _is_action_suggestion_context(context):
        final_reply = _clean_action_suggestion_reply(final_reply, context, allow_fallback=False)
        if not _is_action_suggestion_reply_usable(final_reply):
            final_reply = _action_suggestion_unavailable_reply(locale)
            result = {**result, "error": "AI Coach action suggestion was not usable"}
        result = {**result, "recommendation": final_reply, "source": "action_suggestion"}
    return final_reply, result


async def _send_coach_chat_stream(message: str, context: dict[str, Any], locale: str):
    if _is_analytics_advice_context(context):
        try:
            model_message = _coach_message_for_model(message, context)
            result = await coach_bridge.chat(model_message, context, locale=locale)
        except Exception as exc:
            result = {"error": str(exc)}

        if not _is_analytics_advice_result(result):
            result = {
                **result,
                "recommendation": _fallback_analytics_advice_from_context(context),
                "source": "analytics_advice_backend_fallback",
            }
        reply = str(result.get("recommendation") or result.get("reply") or "").strip()
        reply, result = _finalize_coach_stream_reply(reply, message, context, locale, result)

        request_context = context.get("request") if isinstance(context.get("request"), dict) else {}
        session_id = str(request_context.get("coach_session_id") or getattr(config, "AI_COACH_SESSION_ID", "backend_yolo"))
        _persist_coach_exchange(
            session_id=session_id,
            user_message=message,
            coach_reply=reply,
            locale=locale,
            context=context,
            result=result,
        )
        yield _coach_stream_event({"type": "delta", "delta": reply})
        yield _coach_stream_event(
            {
                "type": "done",
                "status": "success",
                "reply": reply,
                "timestamp": result.get("timestamp") or datetime.now().isoformat(),
            }
        )
        return

    try:
        model_message = _coach_message_for_model(message, context)
        final_result: dict[str, Any] | None = None
        raw_streamed_reply = ""
        visible_streamed_reply = ""
        async for event in coach_bridge.chat_stream(model_message, context, locale=locale):
            if event.get("type") == "delta":
                delta = str(event.get("delta") or "")
                if delta:
                    raw_streamed_reply += delta
                    next_visible_reply = _stream_preview_coach_reply(raw_streamed_reply, context)
                    if not next_visible_reply or next_visible_reply == visible_streamed_reply:
                        continue
                    if next_visible_reply.startswith(visible_streamed_reply):
                        yield _coach_stream_event(
                            {
                                "type": "delta",
                                "delta": next_visible_reply[len(visible_streamed_reply) :],
                            }
                        )
                    else:
                        yield _coach_stream_event({"type": "replace", "reply": next_visible_reply})
                    visible_streamed_reply = next_visible_reply
                continue
            if event.get("type") == "result":
                payload = event.get("payload")
                final_result = payload if isinstance(payload, dict) else {}
                break
    except Exception as exc:
        yield _coach_stream_event({"type": "error", "message": f"AI Coach WebSocket unavailable: {exc}"})
        return

    result = final_result or {}
    reply = str(result.get("recommendation") or result.get("reply") or "").strip()
    if not reply:
        yield _coach_stream_event({"type": "error", "message": "AI Coach returned empty reply"})
        return

    reply, result = _finalize_coach_stream_reply(reply, message, context, locale, result)
    if reply != visible_streamed_reply:
        yield _coach_stream_event({"type": "replace", "reply": reply})

    request_context = context.get("request") if isinstance(context.get("request"), dict) else {}
    session_id = str(request_context.get("coach_session_id") or getattr(config, "AI_COACH_SESSION_ID", "backend_yolo"))
    _persist_coach_exchange(
        session_id=session_id,
        user_message=message,
        coach_reply=reply,
        locale=locale,
        context=context,
        result=result,
    )

    yield _coach_stream_event(
        {
            "type": "done",
            "status": "success",
            "reply": reply,
            "timestamp": result.get("timestamp") or datetime.now().isoformat(),
        }
    )


def _single_coach_stream_reply(reply: str, locale: str):
    async def iterator():
        yield _coach_stream_event(
            {
                "type": "done",
                "status": "paused",
                "reply": reply,
                "timestamp": datetime.now().isoformat(),
                "locale": locale,
            }
        )

    return StreamingResponse(iterator(), media_type="text/event-stream")


@app.post("/api/coach/suggest")
async def coach_suggest(request: dict = Body(default={})):
    """Generate one AI Coach suggestion on demand. No background auto suggestion is triggered."""
    provided_context = request.get("context") if isinstance(request, dict) else None
    locale = _normalize_coach_locale(request.get("locale") if isinstance(request, dict) else None)
    response_mode = str(request.get("response_mode") or "action_suggestion") if isinstance(request, dict) else "action_suggestion"
    if not ensure_live_analysis_for_coach():
        return {
            "status": "paused",
            "reply": _coach_message_for_locale("suggest_yolo_unavailable", locale),
            "timestamp": datetime.now().isoformat(),
        }
    message = "請根據目前 YOLO 辨識後的球局畫面，交由 Gemma 產生一段擊球建議。"
    _, context = _get_current_coach_context(
        message,
        provided_context,
        request_type="action_suggestion",
        response_mode=response_mode,
    )
    return await _send_coach_chat(message, context, locale)


@app.post("/api/coach/chat")
async def coach_chat(request: dict = Body(...), authorization: Annotated[str | None, Header()] = None):
    """Forward a manual AI Coach chat request to the remote Coach WebSocket service."""
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="Invalid request body")

    message = str(request.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' parameter")

    provided_context = request.get("context")
    locale = _normalize_coach_locale(request.get("locale"))
    active_response_mode = ""
    if isinstance(request.get("active_response_mode"), str):
        active_response_mode = request["active_response_mode"].strip()
    elif isinstance(provided_context, dict) and isinstance(provided_context.get("active_response_mode"), str):
        active_response_mode = provided_context["active_response_mode"].strip()
    active_response_mode = active_response_mode if active_response_mode == "action_suggestion" else None
    coach_session_id = str(request.get("coach_session_id") or "").strip()
    conversation_context = _build_coach_conversation_context(request.get("conversation_history"), message)
    requires_analytics = _coach_message_requires_analytics(message)
    requires_visual_analysis = _coach_message_requires_visual_analysis(message, active_response_mode)
    if requires_analytics:
        context = _get_analytics_coach_context(
            message,
            provided_context,
            authorization,
            coach_session_id,
            request_type="chat",
        )
    elif requires_visual_analysis and not ensure_live_analysis_for_coach():
        return {
            "status": "paused",
            "reply": _coach_message_for_locale("chat_yolo_unavailable", locale),
            "timestamp": datetime.now().isoformat(),
        }
    elif not requires_visual_analysis:
        intent = "non_analysis"
        context = _get_non_analysis_coach_context(message, provided_context, request_type="chat")
    else:
        intent, context = _get_current_coach_context(
            message,
            provided_context,
            request_type="chat",
            response_mode=active_response_mode,
        )
    context["conversation_context"] = conversation_context
    context.setdefault("request", {})
    if isinstance(context["request"], dict):
        context["request"]["coach_session_id"] = coach_session_id or None
    return await _send_coach_chat(message, context, locale)


@app.post("/api/coach/suggest/stream")
async def coach_suggest_stream(request: dict = Body(default={})):
    """Stream one AI Coach suggestion on demand through SSE chunks."""
    provided_context = request.get("context") if isinstance(request, dict) else None
    locale = _normalize_coach_locale(request.get("locale") if isinstance(request, dict) else None)
    response_mode = str(request.get("response_mode") or "action_suggestion") if isinstance(request, dict) else "action_suggestion"
    if not ensure_live_analysis_for_coach():
        return _single_coach_stream_reply(_coach_message_for_locale("suggest_yolo_unavailable", locale), locale)
    message = "請根據目前 YOLO 辨識後的球局畫面，交由 Gemma 產生一段擊球建議。"
    _, context = _get_current_coach_context(
        message,
        provided_context,
        request_type="action_suggestion",
        response_mode=response_mode,
    )
    return StreamingResponse(_send_coach_chat_stream(message, context, locale), media_type="text/event-stream")


@app.post("/api/coach/chat/stream")
async def coach_chat_stream(request: dict = Body(...), authorization: Annotated[str | None, Header()] = None):
    """Stream a manual AI Coach chat request through SSE chunks."""
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="Invalid request body")

    message = str(request.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' parameter")

    provided_context = request.get("context")
    locale = _normalize_coach_locale(request.get("locale"))
    active_response_mode = ""
    if isinstance(request.get("active_response_mode"), str):
        active_response_mode = request["active_response_mode"].strip()
    elif isinstance(provided_context, dict) and isinstance(provided_context.get("active_response_mode"), str):
        active_response_mode = provided_context["active_response_mode"].strip()
    active_response_mode = active_response_mode if active_response_mode == "action_suggestion" else None
    coach_session_id = str(request.get("coach_session_id") or "").strip()
    conversation_context = _build_coach_conversation_context(request.get("conversation_history"), message)
    requires_analytics = _coach_message_requires_analytics(message)
    requires_visual_analysis = _coach_message_requires_visual_analysis(message, active_response_mode)
    if requires_analytics:
        context = _get_analytics_coach_context(
            message,
            provided_context,
            authorization,
            coach_session_id,
            request_type="chat",
        )
    elif requires_visual_analysis and not ensure_live_analysis_for_coach():
        return _single_coach_stream_reply(_coach_message_for_locale("chat_yolo_unavailable", locale), locale)
    elif not requires_visual_analysis:
        context = _get_non_analysis_coach_context(message, provided_context, request_type="chat")
    else:
        _, context = _get_current_coach_context(
            message,
            provided_context,
            request_type="chat",
            response_mode=active_response_mode,
        )
    context["conversation_context"] = conversation_context
    context.setdefault("request", {})
    if isinstance(context["request"], dict):
        context["request"]["coach_session_id"] = coach_session_id or None
    return StreamingResponse(_send_coach_chat_stream(message, context, locale), media_type="text/event-stream")


@app.get("/api/coach/state")
async def coach_state():
    """Return remote AI Coach WebSocket bridge state."""
    return {
        "status": "success",
        **coach_bridge.get_state(),
        **coach_semantics.state(),
        "streaming_enabled": bool(getattr(config, "AI_COACH_STREAMING_ENABLED", True)),
    }


@app.get("/api/coach/debug-payload")
async def coach_debug_payload():
    """Return the latest coach.context.v1 payload built by the backend."""
    payload = coach_payload_builder.latest()
    if payload is None:
        _, payload = _get_current_coach_context("debug payload", request_type="debug")
    return {"status": "success", "payload": payload}



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
    mappings.update(_extract_color_profile_assets(profile.get("mappings", {})))
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

    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    mode = profile.get("mode", "pool")
    mappings = _build_tracker_color_mappings(mode, profile.get("mappings", {}))
    apply_result = tracker.apply_color_calibration(mode, mappings)
    seeded_identity_locks = _seed_manual_identity_locks_from_sample_sets(profile_id, profile.get("mappings", {}))

    color_calibration_state["profile_id"] = profile.get("id")
    color_calibration_state["profile_name"] = profile.get("name")
    color_calibration_state["mode"] = mode
    color_calibration_state["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_color_calibration_state()

    return {
        "status": "success",
        "profile_id": profile.get("id"),
        "mode": mode,
        "applied": apply_result.get("applied", 0),
        "learned_templates": len((mappings.get("_learned_templates") if isinstance(mappings.get("_learned_templates"), dict) else {}) or {}),
        "seeded_identity_locks": seeded_identity_locks,
    }


@app.post("/api/color-calibration/profiles/{profile_id}/samples/capture")
async def capture_color_calibration_samples(profile_id: int, request: dict = Body(...)):
    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    mode = str(profile.get("mode") or "pool")
    if mode != "pool":
        raise HTTPException(status_code=400, detail="Sample capture currently supports pool mode")

    assignments = _parse_sample_assignments(request.get("assignments"))
    max_samples_per_color = int(request.get("max_samples_per_color", 240) or 240)
    max_samples_per_color = max(20, min(1000, max_samples_per_color))

    data, frame, source_w, source_h, frame_w, frame_h = _latest_color_diagnostics_snapshot()
    source_frame_id = data.get("_source_frame_id")
    captured: list[dict[str, Any]] = []
    identity_locks: list[dict[str, Any]] = []
    balls = data.get("balls", []) if isinstance(data.get("balls"), list) else []

    for index, identity in assignments.items():
        if index < 0 or index >= len(balls) or not isinstance(balls[index], dict):
            raise HTTPException(status_code=400, detail=f"Ball index not found in latest detections: {index}")
        diag = _color_diagnostic_ball(balls[index], index, frame, source_w, source_h, frame_w, frame_h)
        features = _color_feature_from_diagnostic(diag)
        if features.get("hsv_median") is None or features.get("lab_median") is None:
            raise HTTPException(status_code=400, detail=f"Insufficient color feature for ball index: {index}")

        sample_id = uuid.uuid4().hex
        color = str(identity["color"])
        crop_path = _save_color_sample_crop(frame, diag.get("view_bbox"), profile_id, color, sample_id)
        sample = {
            "id": sample_id,
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source_frame_id": source_frame_id,
            "index": index,
            "actual_number": identity["number"],
            "actual_color": color,
            "actual_style": identity["style"],
            "detected": diag.get("detected"),
            "source_bbox": diag.get("source_bbox"),
            "view_bbox": diag.get("view_bbox"),
            "hsv_median": features["hsv_median"],
            "lab_median": features["lab_median"],
            "rgb_median": features["rgb_median"],
            "sample_pixels": features["sample_pixels"],
            "template_score": features["template_score"],
            "template_margin": features["template_margin"],
            "crop_path": crop_path,
        }
        captured.append(sample)
        lock = _add_manual_ball_identity_lock(
            profile_id=profile_id,
            sample_id=sample_id,
            index=index,
            identity=identity,
            ball=balls[index],
            source_frame_id=source_frame_id,
        )
        if lock is not None:
            identity_locks.append(lock)

    raw_mappings = profile.get("mappings") if isinstance(profile.get("mappings"), dict) else {}
    next_mappings = dict(raw_mappings)
    sample_sets = dict(next_mappings.get("_sample_sets") if isinstance(next_mappings.get("_sample_sets"), dict) else {})
    for sample in captured:
        color = str(sample["actual_color"])
        samples = list(sample_sets.get(color) if isinstance(sample_sets.get(color), list) else [])
        samples.append(sample)
        if len(samples) > max_samples_per_color:
            samples = samples[-max_samples_per_color:]
        sample_sets[color] = samples
    next_mappings["_sample_sets"] = sample_sets
    next_mappings["_learned_templates"] = _rebuild_learned_templates_from_samples(next_mappings, min_samples=3)
    next_mappings["_validation"] = {
        "last_capture_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sample_counts": {color: len(samples) for color, samples in sample_sets.items() if isinstance(samples, list)},
    }

    ok = recording_manager.db.update_color_calibration_profile(profile_id, next_mappings)
    if not ok:
        raise HTTPException(status_code=500, detail="Update sample set failed")

    return {
        "status": "success",
        "profile_id": profile_id,
        "captured": captured,
        "identity_locks": identity_locks,
        "sample_counts": next_mappings["_validation"]["sample_counts"],
        "learned_templates": next_mappings["_learned_templates"],
    }


@app.post("/api/color-calibration/profiles/{profile_id}/learned-templates/rebuild")
async def rebuild_color_calibration_templates(profile_id: int, request: dict = Body(default={})):
    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    min_samples = int(request.get("min_samples", 3) or 3) if isinstance(request, dict) else 3
    min_samples = max(2, min(30, min_samples))

    raw_mappings = profile.get("mappings") if isinstance(profile.get("mappings"), dict) else {}
    next_mappings = dict(raw_mappings)
    templates = _rebuild_learned_templates_from_samples(next_mappings, min_samples=min_samples)
    next_mappings["_learned_templates"] = templates
    next_mappings.setdefault("_validation", {})
    if isinstance(next_mappings["_validation"], dict):
        next_mappings["_validation"]["last_rebuild_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        next_mappings["_validation"]["min_samples"] = min_samples

    ok = recording_manager.db.update_color_calibration_profile(profile_id, next_mappings)
    if not ok:
        raise HTTPException(status_code=500, detail="Rebuild templates failed")
    return {"status": "success", "profile_id": profile_id, "min_samples": min_samples, "learned_templates": templates}


@app.post("/api/color-calibration/profiles/{profile_id}/samples/delete")
async def delete_color_calibration_samples(profile_id: int, request: dict = Body(...)):
    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    raw_mappings = profile.get("mappings") if isinstance(profile.get("mappings"), dict) else {}
    next_mappings = dict(raw_mappings)
    sample_sets = dict(next_mappings.get("_sample_sets") if isinstance(next_mappings.get("_sample_sets"), dict) else {})
    sample_ids = request.get("sample_ids")
    colors = request.get("colors")
    clear_all = bool(request.get("clear_all", False))

    removed: list[dict[str, Any]] = []
    if clear_all:
        for color, samples in sample_sets.items():
            if isinstance(samples, list):
                for sample in samples:
                    if isinstance(sample, dict):
                        removed.append({"color": color, "id": sample.get("id")})
        sample_sets = {}
    elif isinstance(sample_ids, list) and sample_ids:
        target_ids = {str(item) for item in sample_ids}
        for color, samples in list(sample_sets.items()):
            if not isinstance(samples, list):
                continue
            kept = []
            for sample in samples:
                sample_id = str(sample.get("id")) if isinstance(sample, dict) else ""
                if sample_id in target_ids:
                    removed.append({"color": color, "id": sample_id})
                else:
                    kept.append(sample)
            if kept:
                sample_sets[color] = kept
            else:
                sample_sets.pop(color, None)
    elif isinstance(colors, list) and colors:
        target_colors = {str(color) for color in colors}
        for color in list(sample_sets.keys()):
            if color in target_colors:
                samples = sample_sets.pop(color)
                if isinstance(samples, list):
                    for sample in samples:
                        if isinstance(sample, dict):
                            removed.append({"color": color, "id": sample.get("id")})
    else:
        raise HTTPException(status_code=400, detail="Provide clear_all, sample_ids, or colors")

    next_mappings["_sample_sets"] = sample_sets
    next_mappings["_learned_templates"] = _rebuild_learned_templates_from_samples(next_mappings, min_samples=3)
    removed_locks = _remove_manual_ball_identity_locks(
        profile_id=profile_id,
        sample_ids={str(item) for item in sample_ids} if isinstance(sample_ids, list) and sample_ids else None,
        colors={str(color) for color in colors} if isinstance(colors, list) and colors else None,
        clear_all=clear_all,
    )
    next_mappings.setdefault("_validation", {})
    if isinstance(next_mappings["_validation"], dict):
        next_mappings["_validation"].update({
            "last_delete_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sample_counts": {color: len(samples) for color, samples in sample_sets.items() if isinstance(samples, list)},
        })

    ok = recording_manager.db.update_color_calibration_profile(profile_id, next_mappings)
    if not ok:
        raise HTTPException(status_code=500, detail="Delete samples failed")
    return {
        "status": "success",
        "profile_id": profile_id,
        "removed": removed,
        "removed_identity_locks": removed_locks,
        "sample_counts": next_mappings["_validation"].get("sample_counts", {}) if isinstance(next_mappings.get("_validation"), dict) else {},
        "learned_templates": next_mappings["_learned_templates"],
    }


@app.get("/api/color-calibration/identity-locks")
async def get_color_calibration_identity_locks():
    now = time.time()
    with manual_ball_identity_lock_guard:
        locks = []
        for lock in manual_ball_identity_locks:
            item = dict(lock)
            item["expires_in_sec"] = round(max(0.0, float(item.get("expires_at") or now) - now), 3)
            locks.append(item)
    return {"status": "success", "count": len(locks), "locks": locks}


@app.get("/api/color-calibration/profiles/{profile_id}/validation")
async def validate_color_calibration_profile(profile_id: int):
    profile = recording_manager.db.get_color_calibration_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    raw_mappings = profile.get("mappings") if isinstance(profile.get("mappings"), dict) else {}
    templates = raw_mappings.get("_learned_templates") if isinstance(raw_mappings.get("_learned_templates"), dict) else {}
    sample_sets = raw_mappings.get("_sample_sets") if isinstance(raw_mappings.get("_sample_sets"), dict) else {}
    if not templates:
        raise HTTPException(status_code=400, detail="No learned templates available")

    total = 0
    correct = 0
    unknown = 0
    confusion: dict[str, dict[str, int]] = {}
    details: list[dict[str, Any]] = []
    for actual_color, samples in sample_sets.items():
        if not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            hsv = _clean_numeric_triplet(sample.get("hsv_median"))
            lab = _clean_numeric_triplet(sample.get("lab_median"))
            if hsv is None or lab is None:
                continue
            pred = _classify_feature_with_templates(hsv, lab, templates)
            predicted = str(pred.get("label") or "Unknown")
            total += 1
            if predicted == actual_color:
                correct += 1
            if predicted == "Unknown":
                unknown += 1
            confusion.setdefault(str(actual_color), {})
            confusion[str(actual_color)][predicted] = confusion[str(actual_color)].get(predicted, 0) + 1
            details.append({
                "sample_id": sample.get("id"),
                "actual_color": actual_color,
                "actual_number": sample.get("actual_number"),
                "predicted_color": predicted,
                "score": pred.get("score"),
                "second_label": pred.get("second_label"),
                "margin": pred.get("margin"),
            })

    accuracy = (correct / total) if total else 0.0
    strict_accuracy = (correct / max(1, total - unknown)) if total > unknown else 0.0
    result = {
        "status": "success",
        "profile_id": profile_id,
        "total_samples": total,
        "correct": correct,
        "unknown": unknown,
        "accuracy": round(accuracy, 4),
        "strict_accuracy_excluding_unknown": round(strict_accuracy, 4),
        "confusion": confusion,
        "details": details[-200:],
        "meets_90_percent": accuracy >= 0.90,
    }

    next_mappings = dict(raw_mappings)
    next_mappings.setdefault("_validation", {})
    if isinstance(next_mappings["_validation"], dict):
        next_mappings["_validation"].update({
            "last_validated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "accuracy": result["accuracy"],
            "total_samples": total,
            "correct": correct,
            "unknown": unknown,
        })
        recording_manager.db.update_color_calibration_profile(profile_id, next_mappings)
    return result


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
        "roi": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0},
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
    _save_color_calibration_state()

    return {
        "status": "success",
        "message": "Color calibration reset to default templates",
        "state": color_calibration_state,
    }


@app.get("/api/color-calibration/auto-scan")
async def auto_scan_color_rois(mode: str = Query("pool"), target_color: str | None = Query(None)):
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
    if target_color and str(target_color).strip().lower() == "white" and isinstance(data, dict):
        white_ball = data.get("white_ball")
        if isinstance(white_ball, list) and len(white_ball) >= 4:
            balls = list(balls) if isinstance(balls, list) else []
            balls.append({
                "x": white_ball[0],
                "y": white_ball[1],
                "w": white_ball[2],
                "h": white_ball[3],
                "label": "white ball",
            })
    if not isinstance(balls, list) or len(balls) == 0:
        raise HTTPException(status_code=404, detail="No YOLO balls available, please enable analyzing and keep balls visible")

    target_color_norm = str(target_color or "").strip()

    color_hue_targets = {
        "yellow": 30.0,
        "blue": 110.0,
        "red": 0.0,
        "purple": 140.0,
        "pink": 165.0,
        "orange": 15.0,
        "green": 60.0,
        "brown": 12.0,
    }
    color_number_targets = {
        "yellow": {1, 9},
        "blue": {2, 10},
        "red": {3, 11},
        "purple": {4, 12},
        "orange": {5, 13},
        "green": {6, 14},
        "brown": {7, 15},
        "black": {8},
    }
    color_label_tokens = {
        "yellow": {"yellow", "yel"},
        "blue": {"blue", "blu"},
        "red": {"red"},
        "purple": {"purple", "pur"},
        "orange": {"orange", "org"},
        "green": {"green", "grn"},
        "brown": {"brown", "brn"},
        "black": {"black", "blk"},
        "white": {"white", "cue"},
    }

    def _hue_distance(a: float, b: float) -> float:
        diff = abs(float(a) - float(b))
        return min(diff, 180.0 - diff)

    def _hue_bounds(center: int, tolerance: int) -> tuple[int, int]:
        center = int(max(0, min(179, center)))
        tolerance = int(max(2, min(60, tolerance)))
        return (center - tolerance) % 180, (center + tolerance) % 180

    def _target_score(color_name: str, hsv_center: list[int]) -> float:
        key = color_name.lower().strip()
        h_val, s_val, v_val = hsv_center
        if key == "white":
            return float((max(0, 255 - s_val) / 255.0) * 0.55 + (v_val / 255.0) * 0.45)
        if key == "black":
            return float((max(0, 255 - v_val) / 255.0) * 0.75 + (max(0, 180 - s_val) / 180.0) * 0.25)
        target_h = color_hue_targets.get(key)
        if target_h is None:
            return 0.0
        if s_val < 45:
            return 0.0
        hue_score = max(0.0, 1.0 - (_hue_distance(h_val, target_h) / 45.0))
        sat_score = min(1.0, max(0.0, (s_val - 45) / 105.0))
        val_score = min(1.0, max(0.0, (v_val - 25) / 120.0))
        return float(hue_score * 0.75 + sat_score * 0.2 + val_score * 0.05)

    def _detection_score(color_name: str, ball: dict[str, Any]) -> float:
        key = color_name.lower().strip()
        score = 0.0
        raw_number = ball.get("number")
        try:
            number = int(raw_number) if raw_number is not None else None
        except (TypeError, ValueError):
            number = None
        if number is not None and number in color_number_targets.get(key, set()):
            score += 2.0

        label = str(ball.get("label") or ball.get("ball_color") or ball.get("color") or "").lower()
        if label:
            if any(token in label for token in color_label_tokens.get(key, set())):
                score += 1.0
            elif key != "white" and any(token in label for token in color_label_tokens.get("white", set())):
                score -= 1.0
        return score

    def _is_detection_allowed_for_target(color_name: str, ball: dict[str, Any]) -> bool:
        key = color_name.lower().strip()
        label = str(ball.get("label") or ball.get("ball_color") or ball.get("color") or "").lower()
        if not label:
            return True
        if "cue" in label:
            return False
        if key == "white":
            return "white" in label
        if "white" in label:
            return False
        return True

    h_img, w_img = frame.shape[:2]

    def _roi_hsv_stats(img, x0, y0, x1, y1, expected_color: str):
        roi = img[y0:y1, x0:x1]
        if roi.size == 0:
            return None

        roi_h, roi_w = roi.shape[:2]
        center = (roi_w // 2, roi_h // 2)
        radius = int(min(roi_w, roi_h) * 0.42)

        y_grid, x_grid = np.ogrid[:roi_h, :roi_w]
        dist_from_center = np.sqrt((x_grid - center[0])**2 + (y_grid - center[1])**2)
        circle_mask = dist_from_center <= radius

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = cv2.split(hsv)
        valid_mask = circle_mask & (v_ch >= 18) & (v_ch <= 252)

        if tracker is not None:
            table_mask = cv2.inRange(hsv, tracker.hsv_lower, tracker.hsv_upper) == 255
            keep_for_target = expected_color.lower() in {"blue", "green"}
            if not keep_for_target:
                filtered_mask = valid_mask & ~table_mask
                if np.count_nonzero(filtered_mask) >= 10:
                    valid_mask = filtered_mask

        if np.count_nonzero(valid_mask) < 10:
            return None

        expected_key = expected_color.lower().strip()

        if expected_key == "white":
            pick_mask = valid_mask & (s_ch <= 80) & (v_ch >= 100)
            if np.count_nonzero(pick_mask) < 10:
                pick_mask = valid_mask
            h_med = int(np.median(h_ch[pick_mask]))
            s_med = int(np.median(s_ch[pick_mask]))
            v_med = int(np.median(v_ch[pick_mask]))
            h_low, h_up = 0, 180
            s_low = 0
            s_up = min(255, max(80, s_med + 45))
            v_low = max(0, min(220, v_med - 45))
            v_up = 255
            sample_bgr = np.median(roi[pick_mask].reshape(-1, 3), axis=0)
            return {
                "hsv_center": [h_med, s_med, v_med],
                "hsv_lower": [h_low, s_low, v_low],
                "hsv_upper": [h_up, s_up, v_up],
                "rgb_center": [int(sample_bgr[2]), int(sample_bgr[1]), int(sample_bgr[0])],
                "sample_pixels": int(np.count_nonzero(pick_mask)),
            }

        if expected_key == "black":
            pick_mask = valid_mask & (v_ch <= 115)
            if np.count_nonzero(pick_mask) < 10:
                pick_mask = valid_mask
            h_med = int(np.median(h_ch[pick_mask]))
            s_med = int(np.median(s_ch[pick_mask]))
            v_med = int(np.median(v_ch[pick_mask]))
            sample_bgr = np.median(roi[pick_mask].reshape(-1, 3), axis=0)
            return {
                "hsv_center": [h_med, s_med, v_med],
                "hsv_lower": [0, max(0, s_med - 70), 0],
                "hsv_upper": [180, min(255, s_med + 90), min(160, max(80, v_med + 70))],
                "rgb_center": [int(sample_bgr[2]), int(sample_bgr[1]), int(sample_bgr[0])],
                "sample_pixels": int(np.count_nonzero(pick_mask)),
            }

        color_mask = valid_mask & (s_ch >= 45) & (v_ch >= 35) & ~((s_ch <= 55) & (v_ch >= 145))
        if np.count_nonzero(color_mask) < 10:
            color_mask = valid_mask & (s_ch >= 30) & (v_ch >= 25)
        if np.count_nonzero(color_mask) < 10:
            color_mask = valid_mask

        bgr_pixels = roi[color_mask].reshape((-1, 3)).astype(np.float32)
        if len(bgr_pixels) < 10:
            return None

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        best_labels = np.empty((0, 1), dtype=np.int32)
        _, labels, centers = cv2.kmeans(
            bgr_pixels,
            min(3, len(bgr_pixels)),
            best_labels,
            criteria,
            10,
            cv2.KMEANS_RANDOM_CENTERS,
        )

        counts = np.bincount(labels.flatten())
        centers_uint8 = np.clip(centers, 0, 255).astype(np.uint8).reshape(-1, 1, 3)
        center_hsv = cv2.cvtColor(centers_uint8, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        cluster_scores = []
        for idx, hsv_center in enumerate(center_hsv):
            h_c, s_c, v_c = [int(v) for v in hsv_center]
            score = float(counts[idx]) * (0.25 + min(1.0, s_c / 120.0)) * (0.35 + min(1.0, v_c / 180.0))
            if s_c < 35 or v_c < 30:
                score *= 0.25
            if s_c <= 55 and v_c >= 145:
                score *= 0.2
            target_h = color_hue_targets.get(expected_key)
            if target_h is not None:
                score *= 0.45 + max(0.0, 1.0 - (_hue_distance(h_c, target_h) / 60.0))
            cluster_scores.append(score)

        dominant_idx = int(np.argmax(cluster_scores))
        cluster_mask_flat = labels.flatten() == dominant_idx
        dominant_bgr = centers[dominant_idx]
        dominant_hsv = center_hsv[dominant_idx]

        selected_hsv = cv2.cvtColor(
            np.clip(bgr_pixels[cluster_mask_flat], 0, 255).astype(np.uint8).reshape(-1, 1, 3),
            cv2.COLOR_BGR2HSV,
        ).reshape(-1, 3)

        h_dom, s_dom, v_dom = [int(v) for v in dominant_hsv]
        h_vals = selected_hsv[:, 0].astype(np.float32)
        h_diff = np.abs(h_vals - float(h_dom))
        h_diff = np.minimum(h_diff, 180.0 - h_diff)
        h_tol = int(max(6, min(18, np.percentile(h_diff, 85) + 4)))
        s_low = int(max(0, np.percentile(selected_hsv[:, 1], 10) - 20))
        s_up = int(min(255, np.percentile(selected_hsv[:, 1], 90) + 30))
        v_low = int(max(0, np.percentile(selected_hsv[:, 2], 10) - 25))
        v_up = int(min(255, np.percentile(selected_hsv[:, 2], 90) + 35))

        h_low, h_up = _hue_bounds(h_dom, h_tol)

        return {
            "hsv_center": [h_dom, s_dom, v_dom],
            "hsv_lower": [h_low, s_low, v_low],
            "hsv_upper": [h_up, s_up, v_up],
            "rgb_center": [int(dominant_bgr[2]), int(dominant_bgr[1]), int(dominant_bgr[0])], # R, G, B
            "sample_pixels": int(np.count_nonzero(cluster_mask_flat)),
        }

    scanned = []
    for i, b in enumerate(balls):
        if not isinstance(b, dict):
            continue
        if target_color_norm and not _is_detection_allowed_for_target(target_color_norm, b):
            continue
        x = int(b.get("x", 0))
        y = int(b.get("y", 0))
        w = int(b.get("w", 0))
        h = int(b.get("h", 0))
        if w <= 2 or h <= 2:
            continue

        source_w = int(data.get("_source_img_w") or data.get("img_w") or w_img) if isinstance(data, dict) else w_img
        source_h = int(data.get("_source_img_h") or data.get("img_h") or h_img) if isinstance(data, dict) else h_img
        if source_w > 0 and source_h > 0 and (source_w != w_img or source_h != h_img):
            scale_x = w_img / float(source_w)
            scale_y = h_img / float(source_h)
            x = int(round(x * scale_x))
            y = int(round(y * scale_y))
            w = int(round(w * scale_x))
            h = int(round(h * scale_y))

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

        stats = _roi_hsv_stats(frame, rx0, ry0, rx1, ry1, target_color_norm)
        if stats is None:
            continue
        hsv_center_raw = stats.get("hsv_center")
        hsv_center: list[int] | None = None
        if isinstance(hsv_center_raw, list) and len(hsv_center_raw) >= 3:
            try:
                hsv_center = [int(hsv_center_raw[0]), int(hsv_center_raw[1]), int(hsv_center_raw[2])]
            except (TypeError, ValueError):
                hsv_center = None
        score = (
            _detection_score(target_color_norm, b) + _target_score(target_color_norm, hsv_center)
            if target_color_norm
            and hsv_center is not None
            else 0.0
        )

        scanned.append({
            "index": i,
            "bbox": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0},
            "roi": {"x": rx0, "y": ry0, "w": rx1 - rx0, "h": ry1 - ry0},
            "detected_number": b.get("number"),
            "detected_label": b.get("label") or b.get("ball_color"),
            "target_score": score,
            **stats,
        })

    if len(scanned) == 0:
        raise HTTPException(status_code=404, detail="No valid ball ROI from current YOLO result")

    if target_color_norm:
        scanned.sort(key=lambda it: (-float(it.get("target_score", 0.0)), it["bbox"]["x"], it["bbox"]["y"]))
    else:
        # 穩定排序：由左到右、由上到下
        scanned.sort(key=lambda it: (it["bbox"]["x"], it["bbox"]["y"]))

    return {
        "status": "success",
        "mode": mode,
        "target_color": target_color_norm,
        "system_colors": COLOR_CALIBRATION_MODES[mode],
        "count": len(scanned),
        "scans": scanned,
        "frame_size": {"width": w_img, "height": h_img},
    }


# ================== MJPEG 流媒體 API ==================

# ✅ v1.5 Burn-in MJPEG 端點
MJPEG_LOW_LATENCY_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "X-Accel-Buffering": "no",
}


@app.get("/burnin/{stream_id}.mjpg")
async def burnin_stream(
    stream_id: str,
    quality: str = Query("med"),
    client_id: Optional[str] = Query(None),
):
    """
    Burn-in 串流端點（v1.5 規範）
    支持 camera1, camera2, projector, file1
    quality: low | med | high
    """
    if mjpeg_manager is None:
        return Response("MJPEG not available", status_code=503)

    ensure_camera_capture_started()

    # 質量映射
    quality_map = {"low": 50, "med": 70, "high": 85}
    jpeg_quality = quality_map.get(quality, 70)
    
    print(f"🎬 Burnin stream requested: {stream_id}, quality={quality} (JPEG={jpeg_quality})")
    
    # 根據 stream_id 選擇對應的 MJPEG 流並傳入畫質參數
    if stream_id in ["camera1", "file1"]:
        return StreamingResponse(
            mjpeg_manager.monitor.generate(
                quality=jpeg_quality,
                client_id=client_id,
                exclusive_group="monitor",
            ),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers=MJPEG_LOW_LATENCY_HEADERS,
        )
    elif stream_id == "projector":
        return StreamingResponse(
            mjpeg_manager.projector.generate(
                quality=jpeg_quality,
                client_id=client_id,
                exclusive_group="projector",
            ),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers=MJPEG_LOW_LATENCY_HEADERS,
        )
    else:
        raise HTTPException(status_code=404, detail="Stream not found")


# ✅ MJPEG 串流端點 - 監控畫面
@app.get("/stream/monitor")
async def mjpeg_monitor_stream(client_id: Optional[str] = Query(None)):
    """監控畫面 MJPEG 串流 - 直接用 <img src="..."> 即可顯示"""
    if mjpeg_manager is None:
        return Response("MJPEG not available", status_code=503)

    ensure_camera_capture_started()

    return StreamingResponse(
        mjpeg_manager.monitor.generate(client_id=client_id, exclusive_group="monitor"),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=MJPEG_LOW_LATENCY_HEADERS,
    )


# ✅ MJPEG 串流端點 - 投影畫面
@app.get("/stream/projector")
async def mjpeg_projector_stream(client_id: Optional[str] = Query(None)):
    """投影畫面 MJPEG 串流 - 直接用 <img src="..."> 即可顯示"""
    if mjpeg_manager is None:
        return Response("MJPEG not available", status_code=503)

    ensure_camera_capture_started()

    return StreamingResponse(
        mjpeg_manager.projector.generate(client_id=client_id, exclusive_group="projector"),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=MJPEG_LOW_LATENCY_HEADERS,
    )


# ✅ 投影畫面滿版顯示頁 - 直接拖到投影機螢幕全螢幕即可
@app.get("/projector", response_class=HTMLResponse)
async def projector_fullscreen_page():
    """
    投影畫面滿版包裝頁。

    直接開 /stream/projector 是原始 MJPEG，瀏覽器會用預設文件把圖片置中（有邊距、
    不縮放）。此頁用 CSS 讓 <img> 撐滿整個視窗，把瀏覽器視窗全螢幕化（F11）拉到
    投影機螢幕即為 1:1 滿版投影。
    """
    html = """<!doctype html>
<html lang=\"zh-Hant\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, maximum-scale=1\">
<title>Projector</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: #000; overflow: hidden; cursor: none; }
  #projector { position: fixed; inset: 0; width: 100vw; height: 100vh; object-fit: fill; display: block; }
</style>
</head>
<body>
  <img id=\"projector\" src=\"/stream/projector\" alt=\"projector stream\">
  <script>
    // 串流若中斷自動重連，避免投影畫面卡住
    const img = document.getElementById('projector');
    img.addEventListener('error', () => {
      setTimeout(() => { img.src = '/stream/projector?t=' + Date.now(); }, 1000);
    });
    // 點一下嘗試進入全螢幕
    document.body.addEventListener('click', () => {
      if (document.fullscreenElement) return;
      document.documentElement.requestFullscreen().catch(() => {});
    });
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


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


# ================== Game Mode APIs ==================

@app.post("/api/game/start")
async def start_game(request: Annotated[dict, Body(...)]):
    """開始遊戲"""
    mode = request.get("mode", "nine_ball")
    player1 = request.get("player1", "玩家1")
    player2 = request.get("player2", "玩家2")
    target_rounds = request.get("target_rounds", 5)
    shot_time_limit = request.get("shot_time_limit", 0)
    raw_options = request.get("game_options") if isinstance(request.get("game_options"), dict) else {}
    
    print(f"🎮 Starting game: mode={mode}, players={player1} vs {player2}, rounds={target_rounds}, time_limit={shot_time_limit}")
    
    try:
        if mode == "nine_ball":
            result = game_manager.start_nine_ball(player1, player2, target_rounds, shot_time_limit, raw_options)
            
            if "error" in result:
                print(f"❌ Game start failed: {result['error']}")
                return create_error_response(ERR_INVALID_ARGUMENT, result["error"])

            options = result.get("game_options", {}) if isinstance(result.get("game_options"), dict) else {}
            _reset_game_auto_tracking_state()
            if not game_runtime_state["boost_enabled"]:
                game_runtime_state["prev_yolo_skip_frames"] = system_state.get("yolo_skip_frames", 0)
                game_runtime_state["prev_is_analyzing"] = system_state.get("is_analyzing", False)
            needs_analysis = bool(
                options.get("auto_pot_detection", True)
                or options.get("foul_detection", True)
                or options.get("auto_scoring", True)
                or options.get("target_ar_hint_enabled", True)
            )
            system_state["yolo_skip_frames"] = 0
            system_state["is_analyzing"] = needs_analysis
            game_runtime_state["boost_enabled"] = True

            target_ar_enabled = bool(options.get("target_ar_hint_enabled", True))
            set_route_planner_runtime(target_ar_enabled, "9ball")
            if tracker is not None:
                tracker.set_aim_assist(target_ar_enabled)
                if hasattr(tracker, "set_route_target_ball_number"):
                    tracker.set_route_target_ball_number(1 if target_ar_enabled else None)
            if projector_renderer is not None:
                projector_renderer.set_mode(
                    ProjectorMode.GAME
                    if target_ar_enabled or int(shot_time_limit or 0) > 0
                    else ProjectorMode.IDLE
                )
            _sync_game_timer_projection()
            
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
        if result.get("is_foul"):
            if tracker is not None and hasattr(tracker, "set_route_target_ball_number") and game_manager.game_state:
                tracker.set_route_target_ball_number(game_manager.game_state.target_ball)
            _sync_game_timer_projection()
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
        if tracker is not None and hasattr(tracker, "set_route_target_ball_number"):
            tracker.set_route_target_ball_number(game_manager.game_state.target_ball)
        _sync_game_timer_projection()
        
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
        game_manager.game_state.visual_remaining_balls = []
        game_manager.game_state.remaining_balls_source = "rules"
        game_manager.game_state.foul_detected = False
        game_manager.game_state.foul_reason = None
        game_manager.game_state.current_player = opponent_player
        
        # 重置計時器和延時
        if game_manager.game_state.shot_time_limit > 0:
            game_manager.game_state.remaining_time = game_manager.game_state.shot_time_limit
            game_manager.game_state.delay_used = [False, False]
            game_manager.game_state.last_update_time = time.time()
        if tracker is not None and hasattr(tracker, "set_route_target_ball_number"):
            tracker.set_route_target_ball_number(game_manager.game_state.target_ball)
        _sync_game_timer_projection()
        
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


@app.post("/api/game/options")
async def update_game_options(request: Annotated[dict, Body(...)]):
    """遊玩模式中即時切換自動進球、犯規、計分與目前應擊打球 AR 提示。"""
    game_options_val = request.get("game_options")
    raw_options: dict = game_options_val if isinstance(game_options_val, dict) else request
    try:
        result = game_manager.update_game_options(raw_options)
        if result.get("error"):
            return create_error_response(ERR_INVALID_ARGUMENT, result["error"])

        options = result.get("game_options", {})
        target_ar_enabled = bool(options.get("target_ar_hint_enabled", True))
        set_route_planner_runtime(target_ar_enabled, "9ball")
        if tracker is not None:
            tracker.set_aim_assist(target_ar_enabled)
            if hasattr(tracker, "set_route_target_ball_number"):
                state = game_manager.get_game_state()
                target = state.get("target_ball") if state else None
                tracker.set_route_target_ball_number(target if target_ar_enabled and isinstance(target, int) else None)
        if projector_renderer is not None:
            if target_ar_enabled:
                projector_renderer.set_mode(ProjectorMode.GAME)
            elif game_manager.game_state and game_manager.game_state.shot_time_limit > 0:
                projector_renderer.set_mode(ProjectorMode.GAME)
            else:
                projector_renderer.update_ar_data({"route_segments": [], "aim_lines": [], "ghost_balls": []})

        needs_analysis = bool(
            options.get("auto_pot_detection", True)
            or options.get("foul_detection", True)
            or options.get("auto_scoring", True)
            or target_ar_enabled
        )
        if game_runtime_state["boost_enabled"]:
            system_state["is_analyzing"] = needs_analysis
        _sync_game_timer_projection()
        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/game/end")
async def end_game():
    """結束遊戲"""
    try:
        game_manager.end_game()
        _reset_game_auto_tracking_state()
        if game_runtime_state["boost_enabled"]:
            system_state["yolo_skip_frames"] = game_runtime_state["prev_yolo_skip_frames"]
            system_state["is_analyzing"] = game_runtime_state["prev_is_analyzing"]
            game_runtime_state["boost_enabled"] = False
        if tracker:
            tracker.set_aim_assist(False)
            if hasattr(tracker, "set_route_target_ball_number"):
                tracker.set_route_target_ball_number(None)
        set_route_planner_runtime(False, "practice")
        if projector_renderer is not None:
            projector_renderer.set_mode(ProjectorMode.IDLE)
        _sync_game_timer_projection()
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
    pattern_layout = _sanitize_pattern_layout(request.get("pattern_layout")) if mode in {"pattern", "accuracy"} else None
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
                practice_runtime_state["prev_yolo_skip_frames"] = system_state.get("yolo_skip_frames", 0)
                practice_runtime_state["prev_is_analyzing"] = system_state.get("is_analyzing", False)
            system_state["yolo_skip_frames"] = 0
            system_state["is_analyzing"] = True
            practice_runtime_state["boost_enabled"] = True
            set_route_planner_runtime(True, "practice")
        else:
            set_route_planner_runtime(False, "practice")
            guide_options = pattern_layout.get("guide_options", {}) if isinstance(pattern_layout, dict) else {}
            if tracker is not None and hasattr(tracker, "set_cue_laser_only"):
                tracker.set_cue_laser_only(False)
            if not practice_runtime_state["boost_enabled"]:
                practice_runtime_state["prev_yolo_skip_frames"] = system_state.get("yolo_skip_frames", 0)
                practice_runtime_state["prev_is_analyzing"] = system_state.get("is_analyzing", False)
            system_state["yolo_skip_frames"] = 0
            system_state["is_analyzing"] = True
            practice_runtime_state["boost_enabled"] = True
            _apply_pattern_practice_projection(pattern_layout)
        # 單球練習模式啟用進球輔助線
        if tracker and mode == 'single':
            tracker.set_aim_assist(True)
        # 切換投影機至練習模式
        if projector_renderer is not None and mode not in {"pattern", "accuracy"}:
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
        practice_state = game_manager.get_practice_state() or {}
        event_result = {
            "first_contact": None,
            "potted_balls": [1] if success else [],
            "cue_ball_potted": False,
            "is_foul": False,
            "foul_reason": None,
            "practice_result": result,
        }
        _queue_shot_event_record(
            _build_shot_event_record(
                mode=str(practice_state.get("mode") or "practice_single"),
                result=event_result,
                player_name=str(practice_state.get("player_name")) if practice_state.get("player_name") else None,
                start_white=None,
                end_white=None,
                shot_frames=0,
                multi_plan=latest_analysis_data.get("multi_plan"),
            )
        )
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
            tracker.set_cue_laser_only(False)

        if practice_runtime_state["boost_enabled"]:
            system_state["is_analyzing"] = True

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
        if active_mode in {"practice_pattern", "practice_accuracy"}:
            if tracker is not None and hasattr(tracker, "set_cue_laser_only"):
                tracker.set_cue_laser_only(False)
            if practice_runtime_state["boost_enabled"]:
                system_state["is_analyzing"] = True

        if projector_renderer is not None and not cue_laser_enabled:
            projector_renderer.update_ar_data({"cue_laser_lines": []})

        pattern_layout = result.get("pattern_layout")
        if isinstance(pattern_layout, dict):
            _apply_pattern_practice_projection(pattern_layout)

        return JSONResponse(result)
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


@app.post("/api/practice/layout")
async def update_practice_layout(request: Annotated[dict, Body(...)]):
    """更新固定投影練習題目，不重置練習統計。"""
    pattern_layout = _sanitize_pattern_layout(request.get("pattern_layout"))
    if not pattern_layout:
        return create_error_response(ERR_INVALID_ARGUMENT, "Invalid pattern_layout")

    try:
        result = game_manager.update_practice_layout(pattern_layout)
        if result.get("error"):
            return create_error_response(ERR_INVALID_ARGUMENT, result["error"])

        guide_options = result.get("guide_options", {})
        if tracker is not None and hasattr(tracker, "set_cue_laser_only"):
            tracker.set_cue_laser_only(False)
        if practice_runtime_state["boost_enabled"]:
            system_state["is_analyzing"] = True
        _apply_pattern_practice_projection(result.get("pattern_layout"))
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
        restore_live_annotation_mode()
        # 切換投影機回待機模式
        if projector_renderer is not None:
            projector_renderer.set_mode(ProjectorMode.IDLE)
        _apply_runtime_fps_cap()
        return JSONResponse({"status": "practice_ended"})
    except Exception as e:
        return create_error_response(ERR_INTERNAL, str(e))


def _held_rest_multi_plan(reason: str) -> Optional[dict[str, Any]]:
    plan = latest_analysis_data.get("multi_plan") if isinstance(latest_analysis_data, dict) else None
    if not isinstance(plan, dict) or not isinstance(plan.get("best_route"), dict):
        route_planner = getattr(tracker, "route_planner", None) if tracker is not None else None
        plan = getattr(route_planner, "last_plan", None) if route_planner is not None else None
    if not isinstance(plan, dict) or not isinstance(plan.get("best_route"), dict):
        return None

    try:
        held_plan = json.loads(json.dumps(plan, ensure_ascii=False))
    except (TypeError, ValueError):
        held_plan = dict(plan)

    notes = list(held_plan.get("coach_notes") or [])
    hold_note = "偵測短暫不穩，REST 規劃暫時沿用上一條有效路線。"
    if hold_note not in notes:
        notes.insert(0, hold_note)
    held_plan["coach_notes"] = notes[:4]
    held_plan["error"] = reason
    held_plan["hysteresis_hold"] = True
    held_plan["rest_hold_reason"] = reason
    return held_plan


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
    lookahead_options = _sanitize_lookahead_request(request)

    runtime_packet = latest_analysis_data.get("data", {})
    if not isinstance(runtime_packet, dict) or not runtime_packet:
        held_plan = _held_rest_multi_plan("NO_ANALYSIS_DATA_HELD")
        if held_plan is None:
            return create_error_response(ERR_INVALID_ARGUMENT, "No analysis data available")
        latest_analysis_data["multi_plan"] = held_plan
        latest_analysis_data["planner_error"] = held_plan.get("error")
        return JSONResponse({"status": "success", "multi_plan": held_plan, "held": True})

    target_ball_number = request.get("target_ball_number")
    if target_ball_number is None and rule_profile == "9ball":
        g_state = game_manager.get_game_state()
        if g_state and isinstance(g_state.get("target_ball"), int):
            target_ball_number = g_state["target_ball"]

    tracker.set_route_rule_profile(rule_profile)
    tracker.configure_route_planner(top_n=top_n, max_bounces=max_bounces, combo_depth=combo_depth)
    _configure_tracker_lookahead(lookahead_options)
    set_route_planner_runtime(True, rule_profile)
    if "stroke" in request and hasattr(tracker, "set_route_stroke_override"):
        tracker.set_route_stroke_override(_sanitize_stroke_override(request.get("stroke")))

    plan = tracker.plan_routes_from_packet(
        runtime_packet,
        rule_profile=rule_profile,
        top_n=top_n,
        target_ball_number=target_ball_number if isinstance(target_ball_number, int) else None,
        max_bounces=max_bounces,
        combo_depth=combo_depth,
        **lookahead_options,
    )
    if plan is None:
        held_plan = _held_rest_multi_plan("INSUFFICIENT_STATE_HELD")
        if held_plan is None:
            return create_error_response(ERR_INVALID_ARGUMENT, "Insufficient state for route planning")
        plan = held_plan

    latest_analysis_data["multi_plan"] = plan
    latest_analysis_data["planner_error"] = plan.get("error")
    ar_best_route = transform_best_route_for_ar({**runtime_packet, "multi_plan": plan})
    latest_analysis_data["ar_best_route"] = ar_best_route
    latest_analysis_data["ar_route_segments"] = ar_best_route.get("route_segments", []) or []
    _publish_route_projection(ar_best_route, "planner_plan")

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
                **lookahead_options,
            },
        }
    )


@app.post("/api/planner/disable")
async def planner_disable():
    """關閉即時多球路徑規劃並清空舊 AR/metadata 路線。"""
    set_route_planner_runtime(False, "practice")
    restore_live_annotation_mode()
    return JSONResponse({"status": "success", "enabled": False})


@app.post("/api/planner/select-route")
async def planner_select_route(request: Annotated[dict, Body(...)]):
    """切換目前顯示的進球線路。"""
    route_id = str(request.get("route_id", "")).strip()
    if not route_id:
        return create_error_response(ERR_INVALID_ARGUMENT, "Missing route_id")

    current_plan = latest_analysis_data.get("multi_plan")
    if not isinstance(current_plan, dict) and tracker is not None:
        route_planner = getattr(tracker, "route_planner", None)
        fallback_plan = getattr(route_planner, "last_plan", None) if route_planner is not None else None
        if isinstance(fallback_plan, dict):
            current_plan = fallback_plan
    if not isinstance(current_plan, dict):
        return create_error_response(ERR_INVALID_ARGUMENT, "No planner state available")

    route_hint = request.get("route") if isinstance(request.get("route"), dict) else None
    updated_plan = _select_route_in_plan(current_plan, route_id, route_hint)
    best_route = updated_plan.get("best_route")
    if not isinstance(best_route, dict):
        return create_error_response(ERR_NOT_FOUND, "Route not found")
    selected_route_id = str(updated_plan.get("selected_route_id") or best_route.get("id") or route_id)

    if tracker is not None:
        set_route_planner_runtime(True, "practice")
        tracker.set_selected_route_id(selected_route_id)
        route_planner = getattr(tracker, "route_planner", None)
        if route_planner is not None and hasattr(route_planner, "last_plan"):
            route_planner.last_plan = updated_plan

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

    ar_best_route = transform_best_route_for_ar({**(data_packet if isinstance(data_packet, dict) else {}), "multi_plan": updated_plan})
    latest_analysis_data["ar_best_route"] = ar_best_route
    latest_analysis_data["ar_route_segments"] = ar_best_route.get("route_segments", []) or []
    _publish_route_projection(ar_best_route, "planner_select_route")

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
    lookahead_options = _sanitize_lookahead_request(request)
    tracker.set_route_stroke_override(stroke)
    _configure_tracker_lookahead(lookahead_options)
    set_route_planner_runtime(True, "practice")

    runtime_packet = latest_analysis_data.get("data", {})
    if not isinstance(runtime_packet, dict) or not runtime_packet:
        held_plan = _held_rest_multi_plan("NO_ANALYSIS_DATA_HELD")
        if held_plan is None:
            return create_error_response(ERR_INVALID_ARGUMENT, "No analysis data available")
        latest_analysis_data["multi_plan"] = held_plan
        latest_analysis_data["planner_error"] = held_plan.get("error")
        return JSONResponse({"status": "success", "stroke": stroke, "multi_plan": held_plan, "held": True})

    plan = tracker.plan_routes_from_packet(runtime_packet, **lookahead_options)
    if plan is None:
        held_plan = _held_rest_multi_plan("INSUFFICIENT_STATE_HELD")
        if held_plan is None:
            return create_error_response(ERR_INVALID_ARGUMENT, "Insufficient state for route planning")
        plan = held_plan

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

    ar_best_route = transform_best_route_for_ar({**(runtime_packet if isinstance(runtime_packet, dict) else {}), "multi_plan": plan})
    latest_analysis_data["ar_best_route"] = ar_best_route
    latest_analysis_data["ar_route_segments"] = ar_best_route.get("route_segments", []) or []
    _publish_route_projection(ar_best_route, "planner_stroke")

    return JSONResponse({"status": "success", "stroke": stroke, "multi_plan": plan})


@app.get("/api/planner/state")
async def planner_state():
    if not isinstance(latest_analysis_data, dict):
        return create_error_response(ERR_INTERNAL, "Planner state unavailable")

    runtime_packet = latest_analysis_data.get("data", {})
    if not isinstance(runtime_packet, dict):
        runtime_packet = {}

    return JSONResponse(
        {
            "status": "success",
            "multi_plan": latest_analysis_data.get("multi_plan"),
            "planner_error": latest_analysis_data.get("planner_error"),
            "runtime_table_roi": runtime_packet.get("table_roi"),
            "runtime_table_roi_raw": runtime_packet.get("table_roi_raw"),
            "table_roi_adjustment": runtime_packet.get("table_roi_adjustment"),
            "table_roi_status": runtime_packet.get("table_roi_status"),
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
        if not isinstance(player, int):
            return create_error_response(ERR_INVALID_ARGUMENT, "player must be an integer")
        
        try:
            result = game_manager.apply_delay(player)
            if "error" in result:
                return create_error_response("DELAY_ERROR", result["error"])
            _sync_game_timer_projection()
            return JSONResponse(result)
        except Exception as e:
            return create_error_response(ERR_INTERNAL, str(e))
    
    if not is_tcp_port_available("0.0.0.0", 8001):
        message = (
            "Backend startup blocked: port 8001 is already in use. "
            "Close the existing backend window or stop the process shown by: netstat -ano | findstr :8001"
        )
        print(f"ERROR {message}")
        logger.error(message)
        sys.exit(1)

    logger.info("Starting uvicorn server host=0.0.0.0 port=8001 pid=%s", os.getpid())
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8001,
            use_colors=False,
            access_log=False,
        )
    except BaseException:
        logger.exception("Uvicorn server exited with exception")
        raise
    finally:
        logger.warning("Uvicorn run returned pid=%s uptime_sec=%.3f", os.getpid(), time.time() - APP_STARTED_AT)

# ================== Recording APIs ==================

@app.post("/api/recording/start")
async def start_recording(request: Annotated[dict, Body(...)]):
    """開始錄影"""
    game_type = request.get("game_type")
    players = request.get("players", [])
    if not isinstance(game_type, str):
        return create_error_response(ERR_INVALID_ARGUMENT, "game_type must be a string")
    
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
    if not isinstance(event_type, str):
        return create_error_response(ERR_INVALID_ARGUMENT, "event_type must be a string")
    
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




































