import os
import json
from typing import Callable, Optional, TypeVar

import numpy as np

_T = TypeVar("_T")


# ==================== 環境變數讀取工具 ====================
def get_env(key: str, default: str, converter: Callable[[str], _T] = str) -> _T:  # type: ignore[assignment]
    """
    讀取環境變數並轉型；轉型失敗時回退到預設值。
    """
    value = os.getenv(key, default)
    try:
        return converter(value)
    except (ValueError, TypeError):
        print(f"Warning: Could not convert env var '{key}'. Using default: {default}")
        return converter(default)  # type: ignore[return-value]


def get_bool_env(key: str, default: str) -> bool:
    """
    讀取布林環境變數，支援 1/true/yes/y/on 作為 True。
    """
    value = os.getenv(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def get_np_array_env(key: str, default_csv: str, expected_len: Optional[int] = 3) -> np.ndarray:
    """
    讀取逗號分隔的環境變數並轉成 numpy array。
    """
    value_str = os.getenv(key, default_csv)
    try:
        values = [int(x.strip()) for x in value_str.split(",")]
        if expected_len is not None and len(values) != expected_len:
            raise ValueError(f"Expected {expected_len} values, got {len(values)}")
        return np.array(values, dtype=np.uint8)
    except (ValueError, TypeError):
        print(f"Warning: Could not parse np.array from env var '{key}'. Using default.")
        return np.array([int(x.strip()) for x in default_csv.split(",")], dtype=np.uint8)


# 環境變數讀取工具結束。


# ==================== 專案路徑與模型權重 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
RUNTIME_DIR = os.path.join(PROJECT_ROOT, "runtime")


def resolve_project_path(value: str, base_dir: str = PROJECT_ROOT) -> str:
    """將 .env 相對路徑固定解析到專案根目錄，避免受啟動 cwd 影響。"""
    return value if os.path.isabs(value) else os.path.join(base_dir, value)


def get_path_env(key: str, default_path: str, base_dir: str = PROJECT_ROOT) -> str:
    return resolve_project_path(os.getenv(key, default_path), base_dir=base_dir)


TABLE_COLOR_PREFERENCES_PATH = get_path_env(
    "TABLE_COLOR_PREFERENCES_PATH",
    os.path.join("runtime", "table_color.json"),
)
TABLE_ROI_ADJUSTMENT_PATH = get_path_env(
    "TABLE_ROI_ADJUSTMENT_PATH",
    os.path.join("runtime", "table_roi_adjustment.json"),
)
TABLE_ROI_POLYGON_PATH = get_path_env(
    "TABLE_ROI_POLYGON_PATH",
    os.path.join("runtime", "table_roi_polygon.json"),
)


def load_table_color_preferences() -> dict:
    try:
        with open(TABLE_COLOR_PREFERENCES_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return {}


def load_table_color_preference(default_color: str = "green") -> str:
    """
    從本機 runtime 偏好檔讀取上次套用的球桌布料顏色。
    """
    data = load_table_color_preferences()
    color = data.get("color")
    return color if isinstance(color, str) and color else default_color


def save_table_color_preference(color: str, hsv_lower=None, hsv_upper=None) -> None:
    """
    寫入球桌布料顏色偏好，供下次後端啟動時載入。
    """
    os.makedirs(os.path.dirname(TABLE_COLOR_PREFERENCES_PATH), exist_ok=True)
    payload: dict = {"color": color}
    if hsv_lower is not None:
        payload["hsv_lower"] = list(hsv_lower)
    if hsv_upper is not None:
        payload["hsv_upper"] = list(hsv_upper)
    with open(TABLE_COLOR_PREFERENCES_PATH, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

MODEL_PATH = get_path_env("MODEL_PATH", os.path.join("yolo-weight", "best.pt"), base_dir=BASE_DIR)

# 專案路徑與模型權重設定結束。


# ==================== YOLO 推論基礎參數 ====================
CONF_THR = get_env("CONF_THR", "0.60", float)
CUE_CONF_THR = get_env("CUE_CONF_THR", "0.60", float)
IOU_THR = get_env("IOU_THR", "0.50", float)
IMG_SIZE = get_env("IMG_SIZE", "640", int)
YOLO_DEVICE = get_env("YOLO_DEVICE", "auto", str)  # auto | cpu | cuda | cuda:0 | 0
YOLO_HALF = get_env("YOLO_HALF", "auto", str)  # auto | true | false

# YOLO 推論基礎參數結束。


# ==================== YOLO 第二階段推論與分割遮罩 ====================
SECOND_PASS_ENABLED = get_bool_env("SECOND_PASS_ENABLED", "true")
SECOND_PASS_MIN_OBJECTS = get_env("SECOND_PASS_MIN_OBJECTS", "3", int)
SECOND_PASS_MIN_BALLS = get_env("SECOND_PASS_MIN_BALLS", "0", int)
SECOND_PASS_SKIP_WHEN_CUE_FOUND = get_bool_env("SECOND_PASS_SKIP_WHEN_CUE_FOUND", "true")
CUE_LASER_ONLY_DISABLE_SECOND_PASS = get_bool_env("CUE_LASER_ONLY_DISABLE_SECOND_PASS", "true")
CUE_SEGMENTATION_MASK_ENABLED = get_bool_env("CUE_SEGMENTATION_MASK_ENABLED", "true")
SECOND_PASS_CONF_THR = get_env("SECOND_PASS_CONF_THR", "0.08", float)
SECOND_PASS_IOU_THR = get_env("SECOND_PASS_IOU_THR", "0.45", float)
SECOND_PASS_IMG_SIZE = get_env("SECOND_PASS_IMG_SIZE", "640", int)
SECOND_PASS_COOLDOWN_FRAMES = get_env("SECOND_PASS_COOLDOWN_FRAMES", "4", int)

# 第二階段推論用於低檢出幀補強；SECOND_PASS_MIN_BALLS=0 時不依球數強制補框，cue laser only 可停用第二階段以降低延遲。
# SECOND_PASS_COOLDOWN_FRAMES 可避免低檢出狀態下每幀重跑第二階段 YOLO。


# ==================== 球桿雷射軸線時序穩定 ====================
CUE_AXIS_CACHE_MAX_MISSING_FRAMES = get_env("CUE_AXIS_CACHE_MAX_MISSING_FRAMES", "3", int)
CUE_AXIS_SMOOTH_ALPHA = get_env("CUE_AXIS_SMOOTH_ALPHA", "0.55", float)
CUE_AXIS_LASER_ONLY_SMOOTH_ALPHA = get_env("CUE_AXIS_LASER_ONLY_SMOOTH_ALPHA", "0.62", float)
CUE_AXIS_RESET_SHIFT_RATIO = get_env("CUE_AXIS_RESET_SHIFT_RATIO", "0.48", float)
CUE_AXIS_RESET_SHIFT_MIN = get_env("CUE_AXIS_RESET_SHIFT_MIN", "32.0", float)
CUE_AXIS_RESET_SHIFT_MAX = get_env("CUE_AXIS_RESET_SHIFT_MAX", "110.0", float)
CUE_AXIS_NORMAL_DEADBAND_PX = get_env("CUE_AXIS_NORMAL_DEADBAND_PX", "3.0", float)
CUE_AXIS_FAST_CONVERGE_SHIFT_PX = get_env("CUE_AXIS_FAST_CONVERGE_SHIFT_PX", "14.0", float)
CUE_AXIS_FAST_CONVERGE_ALPHA = get_env("CUE_AXIS_FAST_CONVERGE_ALPHA", "0.34", float)
CUE_AXIS_LASER_ONLY_FAST_CONVERGE_ALPHA = get_env("CUE_AXIS_LASER_ONLY_FAST_CONVERGE_ALPHA", "0.26", float)
CUE_TIP_WHITE_SUPPRESS_ENABLED = get_bool_env("CUE_TIP_WHITE_SUPPRESS_ENABLED", "true")
CUE_TIP_WHITE_SUPPRESS_PAD_RATIO = get_env("CUE_TIP_WHITE_SUPPRESS_PAD_RATIO", "0.20", float)
CUE_TIP_WHITE_AXIS_DISTANCE_RATIO = get_env("CUE_TIP_WHITE_AXIS_DISTANCE_RATIO", "0.72", float)
CUE_TIP_WHITE_AXIS_ENDPOINT_MARGIN_RATIO = get_env("CUE_TIP_WHITE_AXIS_ENDPOINT_MARGIN_RATIO", "0.08", float)

# 球桿軸線設定控制短暫漏檢沿用、平滑權重、換桿重置與大位移快速收斂。


# ==================== 顏色分類偵錯與即時影像 Overlay ====================
COLOR_DEBUG_ENABLED = get_bool_env("COLOR_DEBUG_ENABLED", "false")
COLOR_DEBUG_PRINT = get_bool_env("COLOR_DEBUG_PRINT", "false")
TRACKER_DRAW_ANNOTATIONS = get_bool_env("TRACKER_DRAW_ANNOTATIONS", "true")
TRACKER_ANNOTATION_MODE = get_env("TRACKER_ANNOTATION_MODE", "full", str)  # none | tactical | full
OVERLAY_METADATA_MAX_AGE_MS = get_env("OVERLAY_METADATA_MAX_AGE_MS", "350", int)
PROJECTOR_AR_METADATA_MAX_AGE_MS = get_env("PROJECTOR_AR_METADATA_MAX_AGE_MS", "1200", int)
LAST_GOOD_OVERLAY_HOLD_MS = get_env("LAST_GOOD_OVERLAY_HOLD_MS", "5000", int)
MONITOR_OVERLAY_MAX_FRAME_LAG = get_env("MONITOR_OVERLAY_MAX_FRAME_LAG", "12", int)
LAST_GOOD_PROJECTOR_AR_HOLD_MS = get_env("LAST_GOOD_PROJECTOR_AR_HOLD_MS", "5000", int)
PROJECTOR_MANUAL_ROUTE_HOLD_MS = get_env("PROJECTOR_MANUAL_ROUTE_HOLD_MS", "30000", int)
YOLO_FUTURE_TIMEOUT_MS = get_env("YOLO_FUTURE_TIMEOUT_MS", "2500", int)
YOLO_FUTURE_HARD_TIMEOUT_MS = get_env("YOLO_FUTURE_HARD_TIMEOUT_MS", "30000", int)

# ==================== AI Coach 整合 ====================
# 主後端只把 YOLO context 送到獨立 AI Coach WebSocket service，不直接呼叫 Gemma/vLLM。
def build_websocket_url_from_base_url(base_url: str, path: str) -> str:
    normalized_base_url = str(base_url).strip().rstrip("/")
    normalized_path = "/" + str(path).strip().lstrip("/")
    if normalized_base_url.startswith("https://"):
        return "wss://" + normalized_base_url[len("https://"):] + normalized_path
    if normalized_base_url.startswith("http://"):
        return "ws://" + normalized_base_url[len("http://"):] + normalized_path
    if normalized_base_url.startswith("wss://") or normalized_base_url.startswith("ws://"):
        return normalized_base_url + normalized_path
    return "wss://" + normalized_base_url + normalized_path


def get_ai_coach_ws_url() -> str:
    public_base_url = os.getenv("AI_COACH_PUBLIC_BASE_URL", "").strip()
    if public_base_url:
        return build_websocket_url_from_base_url(public_base_url, os.getenv("AI_COACH_WS_PATH", "/ws/coach"))
    return os.getenv("AI_COACH_WS_URL", "ws://localhost:8010/ws/coach")


AI_COACH_ENABLED = get_bool_env("AI_COACH_ENABLED", "true")
AI_COACH_MODE = os.getenv("AI_COACH_MODE", "websocket")
AI_COACH_PUBLIC_BASE_URL = os.getenv("AI_COACH_PUBLIC_BASE_URL", "").strip().rstrip("/")
AI_COACH_WS_PATH = os.getenv("AI_COACH_WS_PATH", "/ws/coach")
AI_COACH_WS_URL = get_ai_coach_ws_url()
AI_COACH_RECONNECT_SECONDS = get_env("AI_COACH_RECONNECT_SECONDS", "3", float)
AI_COACH_REQUEST_TIMEOUT_SECONDS = get_env("AI_COACH_REQUEST_TIMEOUT_SECONDS", "90", float)
AI_COACH_WS_PING_INTERVAL = get_env("AI_COACH_WS_PING_INTERVAL", "0", float)
AI_COACH_WS_PING_TIMEOUT = get_env("AI_COACH_WS_PING_TIMEOUT", "0", float)
AI_COACH_STREAMING_ENABLED = get_bool_env("AI_COACH_STREAMING_ENABLED", "true")
AI_COACH_AUTO_SUGGESTIONS_ENABLED = get_bool_env("AI_COACH_AUTO_SUGGESTIONS_ENABLED", "false")
AI_COACH_AUTO_ANALYSIS_INTERVAL_SECONDS = get_env("AI_COACH_AUTO_ANALYSIS_INTERVAL_SECONDS", "20", float)
AI_COACH_STABLE_FRAMES = get_env("AI_COACH_STABLE_FRAMES", "5", int)
AI_COACH_STABLE_MAX_SHIFT = get_env("AI_COACH_STABLE_MAX_SHIFT", "18", float)
AI_COACH_MIN_BALLS = get_env("AI_COACH_MIN_BALLS", "1", int)
AI_COACH_API_URL = os.getenv("AI_COACH_API_URL", "http://localhost:8002/v1/chat/completions")
AI_COACH_MODEL = os.getenv("AI_COACH_MODEL", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
if AI_COACH_MODEL == "/home/lucian039/gemma-4-awq":
    AI_COACH_MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
AI_COACH_SESSION_ID = os.getenv("AI_COACH_SESSION_ID", "backend_yolo")

# 局部 Hough 幾何修正（僅在 YOLO bbox 內執行）
# LOCAL_HOUGH_REFINE_ENABLED: 開啟/關閉局部圓形修正
# LOCAL_HOUGH_PAD_RATIO: bbox 外擴比例，提供 Hough 搜尋邊界餘裕
# LOCAL_HOUGH_MIN_R_SCALE / MAX_R_SCALE: 以 YOLO 半徑為基準的最小/最大搜尋比例
# LOCAL_HOUGH_DP, PARAM1, PARAM2: OpenCV HoughCircles 參數
# LOCAL_HOUGH_MIN_SAT_MEDIAN / MIN_VAL_MEDIAN: 用於過濾陰影假圓的 HSV 中位數門檻
# 本段控制 metadata 偵錯輸出、monitor 疊圖模式與過期資料保留時間。


# ==================== 局部 Hough 幾何修正 ====================
LOCAL_HOUGH_REFINE_ENABLED = get_bool_env("LOCAL_HOUGH_REFINE_ENABLED", "false")
LOCAL_HOUGH_PAD_RATIO = get_env("LOCAL_HOUGH_PAD_RATIO", "0.25", float)
LOCAL_HOUGH_MIN_R_SCALE = get_env("LOCAL_HOUGH_MIN_R_SCALE", "0.55", float)
LOCAL_HOUGH_MAX_R_SCALE = get_env("LOCAL_HOUGH_MAX_R_SCALE", "1.20", float)
LOCAL_HOUGH_DP = get_env("LOCAL_HOUGH_DP", "1.2", float)
LOCAL_HOUGH_PARAM1 = get_env("LOCAL_HOUGH_PARAM1", "110", float)
LOCAL_HOUGH_PARAM2 = get_env("LOCAL_HOUGH_PARAM2", "16", float)
LOCAL_HOUGH_MIN_SAT_MEDIAN = get_env("LOCAL_HOUGH_MIN_SAT_MEDIAN", "35", float)
LOCAL_HOUGH_MIN_VAL_MEDIAN = get_env("LOCAL_HOUGH_MIN_VAL_MEDIAN", "40", float)

# Hough 修正只在 YOLO bbox 內執行，用於微調球心與半徑。


# ==================== 顏色分類半徑取樣 ====================
COLOR_MASK_CORE_RATIO = get_env("COLOR_MASK_CORE_RATIO", "0.45", float)
COLOR_MASK_MID_RATIO = get_env("COLOR_MASK_MID_RATIO", "0.65", float)
COLOR_MASK_OUTER_RATIO = get_env("COLOR_MASK_OUTER_RATIO", "0.85", float)

# 核心層偏主色判斷，中層補充統計，外層主要用於實心/條紋樣式判定。


# ==================== 顏色分類背景環抑制 ====================
COLOR_BG_RING_ENABLED = get_bool_env("COLOR_BG_RING_ENABLED", "true")
COLOR_BG_RING_INNER_RATIO = get_env("COLOR_BG_RING_INNER_RATIO", "1.05", float)
COLOR_BG_RING_OUTER_RATIO = get_env("COLOR_BG_RING_OUTER_RATIO", "1.30", float)
COLOR_BG_HUE_TOL = get_env("COLOR_BG_HUE_TOL", "10.0", float)
COLOR_BG_SAT_TOL = get_env("COLOR_BG_SAT_TOL", "40.0", float)
COLOR_BG_VAL_TOL = get_env("COLOR_BG_VAL_TOL", "45.0", float)

# 背景環用於辨識桌布顏色並抑制滲入球 ROI 的背景像素。


# ==================== 顏色分類時序平滑 ====================
COLOR_TEMPORAL_SMOOTH_ENABLED = get_bool_env("COLOR_TEMPORAL_SMOOTH_ENABLED", "true")
COLOR_TEMPORAL_WINDOW = get_env("COLOR_TEMPORAL_WINDOW", "4", int)
COLOR_TEMPORAL_MATCH_DIST = get_env("COLOR_TEMPORAL_MATCH_DIST", "28.0", float)
COLOR_TEMPORAL_MIN_STABLE = get_env("COLOR_TEMPORAL_MIN_STABLE", "2", int)

# 顏色時序平滑透過跨幀投票降低球色與樣式跳動。


# ==================== 球體候選抑制與幾何平滑 ====================
BALL_DUPLICATE_CENTER_RATIO = get_env("BALL_DUPLICATE_CENTER_RATIO", "0.72", float)
WHITE_OVERLAP_SUPPRESS_RATIO = get_env("WHITE_OVERLAP_SUPPRESS_RATIO", "0.88", float)
BALL_ANNOTATION_RADIUS_PADDING = get_env("BALL_ANNOTATION_RADIUS_PADDING", "2", int)
BALL_GEOMETRY_TEMPORAL_SMOOTH_ENABLED = get_bool_env("BALL_GEOMETRY_TEMPORAL_SMOOTH_ENABLED", "true")
BALL_GEOMETRY_TEMPORAL_MATCH_DIST = get_env("BALL_GEOMETRY_TEMPORAL_MATCH_DIST", "24.0", float)
BALL_GEOMETRY_TEMPORAL_ALPHA = get_env("BALL_GEOMETRY_TEMPORAL_ALPHA", "0.68", float)
BALL_GEOMETRY_TEMPORAL_MAX_AGE = get_env("BALL_GEOMETRY_TEMPORAL_MAX_AGE", "8", int)

# 本段控制重複球框去重、白球重疊抑制、診斷外框半徑與球心/半徑平滑。


# ==================== 球袋假球抑制 ====================
POCKET_FALSE_POSITIVE_FILTER_ENABLED = get_bool_env("POCKET_FALSE_POSITIVE_FILTER_ENABLED", "true")
POCKET_FALSE_POSITIVE_CORE_RATIO = get_env("POCKET_FALSE_POSITIVE_CORE_RATIO", "0.62", float)

# 球袋假球抑制用於過濾袋口黑色區域造成的球體誤判。


# ==================== 球桌顏色與 HSV 預設 ====================
_TABLE_COLOR_PREFERENCES = load_table_color_preferences()
TABLE_CLOTH_COLOR = get_env("TABLE_CLOTH_COLOR", load_table_color_preference("green"), str)
TABLE_COLOR_PRESETS = {
    "green": {
        "hsv_lower": np.array([35, 40, 40]),
        "hsv_upper": np.array([85, 255, 255]),
        "name": "綠色",
    },
    "gray": {
        "hsv_lower": np.array([0, 0, 60]),
        "hsv_upper": np.array([180, 50, 200]),
        "name": "灰色",
    },
    "blue": {
        "hsv_lower": np.array([90, 50, 50]),
        "hsv_upper": np.array([130, 255, 255]),
        "name": "藍色",
    },
    "pink": {
        "hsv_lower": np.array([140, 50, 100]),
        "hsv_upper": np.array([170, 255, 255]),
        "name": "粉色",
    },
    "purple": {
        "hsv_lower": np.array([125, 50, 50]),
        "hsv_upper": np.array([155, 255, 255]),
        "name": "紫色",
    },
    "custom": {
        "hsv_lower": np.array([35, 40, 40]),
        "hsv_upper": np.array([85, 255, 255]),
        "name": "自訂",
    },
}

if TABLE_CLOTH_COLOR not in TABLE_COLOR_PRESETS:
    TABLE_CLOTH_COLOR = "green"

if os.getenv("HSV_LOWER") and os.getenv("HSV_UPPER"):
    HSV_LOWER = get_np_array_env("HSV_LOWER", "35, 40, 40")
    HSV_UPPER = get_np_array_env("HSV_UPPER", "85, 255, 255")
elif (
    TABLE_CLOTH_COLOR == "custom"
    and isinstance(_TABLE_COLOR_PREFERENCES.get("hsv_lower"), list)
    and isinstance(_TABLE_COLOR_PREFERENCES.get("hsv_upper"), list)
):
    HSV_LOWER = np.array(_TABLE_COLOR_PREFERENCES["hsv_lower"], dtype=np.uint8)
    HSV_UPPER = np.array(_TABLE_COLOR_PREFERENCES["hsv_upper"], dtype=np.uint8)
    TABLE_COLOR_PRESETS["custom"]["hsv_lower"] = HSV_LOWER
    TABLE_COLOR_PRESETS["custom"]["hsv_upper"] = HSV_UPPER
else:
    color_preset = TABLE_COLOR_PRESETS.get(TABLE_CLOTH_COLOR, TABLE_COLOR_PRESETS["green"])
    HSV_LOWER = color_preset["hsv_lower"]
    HSV_UPPER = color_preset["hsv_upper"]

TABLE_MIN_AREA = get_env("TABLE_MIN_AREA", "50000", int)

# 球桌 HSV 會優先使用環境變數；未指定時依 TABLE_CLOTH_COLOR 套用預設。


# ==================== 相機解析度與串流來源 ====================
CAMERA_WIDTH = get_env("CAMERA_WIDTH", "1280", int)
CAMERA_HEIGHT = get_env("CAMERA_HEIGHT", "720", int)
CAMERA_FPS = get_env("CAMERA_FPS", "30", int)
CAMERA_ENABLE_ANY_BACKEND = get_bool_env("CAMERA_ENABLE_ANY_BACKEND", "false")
JPEG_QUALITY = get_env("JPEG_QUALITY", "70", int)
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "")
STREAM_PROJECTOR_VIEW = get_bool_env("STREAM_PROJECTOR_VIEW", "true")
LOOP_VIDEO_SOURCE = get_bool_env("LOOP_VIDEO_SOURCE", "true")

# 本段控制相機基本格式、OpenCV backend 掃描、JPEG 傳輸品質、影片檔來源與投影視圖串流。


# ==================== 相機硬體影像參數 ====================
CAMERA_EXPOSURE = get_env("CAMERA_EXPOSURE", "-6", int)
CAMERA_ISO = get_env("CAMERA_ISO", "0", int)
CAMERA_BRIGHTNESS = get_env("CAMERA_BRIGHTNESS", "128", int)
CAMERA_CONTRAST = get_env("CAMERA_CONTRAST", "128", int)
CAMERA_SATURATION = get_env("CAMERA_SATURATION", "128", int)
CAMERA_SHARPNESS = get_env("CAMERA_SHARPNESS", "128", int)
CAMERA_AUTO_WB = get_bool_env("CAMERA_AUTO_WB", "true")
CAMERA_WB_TEMP = get_env("CAMERA_WB_TEMP", "4000", int)

# 相機硬體參數會在後端開啟 camera capture 後套用；不同裝置可能只支援部分欄位。


# ==================== 軟體降噪 ====================
DENOISE_ENABLED = get_bool_env("DENOISE_ENABLED", "false")
DENOISE_STRENGTH = get_env("DENOISE_STRENGTH", "10", int)
DENOISE_METHOD = get_env("DENOISE_METHOD", "bilateral", str)

# 軟體降噪可改善低光源雜訊，但會增加 CPU 成本與處理延遲。


# ==================== Session 管理 ====================
SESSION_TTL = get_env("SESSION_TTL", "3600", int)
SESSION_RENEW_WINDOW = get_env("SESSION_RENEW_WINDOW", "0.2", float)
SESSION_MIN_RENEW_WINDOW = get_env("SESSION_MIN_RENEW_WINDOW", "300", int)
AUTH_SESSION_TTL_SECONDS = get_env("AUTH_SESSION_TTL_SECONDS", str(7 * 24 * 60 * 60), int)
MOBILE_PUBLIC_BASE_URL = get_env("MOBILE_PUBLIC_BASE_URL", "", str).rstrip("/")
MOBILE_REQUIRE_HTTPS_QR = get_bool_env("MOBILE_REQUIRE_HTTPS_QR", "false")
SUPABASE_URL = get_env("SUPABASE_URL", "", str).rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY", "", str)
SUPABASE_STORAGE_BUCKET = get_env("SUPABASE_STORAGE_BUCKET", "community-uploads", str)

# Session 設定控制前端串流會話有效期與自動續期窗口。


# ==================== WebSocket 設定 ====================
WS_HEARTBEAT_INTERVAL = get_env("WS_HEARTBEAT_INTERVAL", "3", int)
WS_CLIENT_TIMEOUT = get_env("WS_CLIENT_TIMEOUT", "15", int)

# WebSocket heartbeat 用於偵測斷線 client 並釋放連線資源。


# ==================== MJPEG 串流設定 ====================
MJPEG_QUALITY = get_env("MJPEG_QUALITY", "80", int)
MJPEG_MAX_FPS = get_env("MJPEG_MAX_FPS", "60", int)

# MJPEG 設定控制 monitor/projector 串流的壓縮品質與最高輸出 FPS。


# ==================== Metadata 推送設定 ====================
METADATA_RATE_HZ = get_env("METADATA_RATE_HZ", "20", int)
METADATA_BUFFER_SIZE = get_env("METADATA_BUFFER_SIZE", "100", int)

# Metadata 設定控制 WebSocket 分析資料推送頻率與緩衝上限。


# ==================== 功能旗標 ====================
ENABLE_DEV_MODE = get_bool_env("ENABLE_DEV_MODE", "false")
ENABLE_REPLAY = get_bool_env("ENABLE_REPLAY", "false")
ENABLE_MULTI_TABLE = get_bool_env("ENABLE_MULTI_TABLE", "false")

# 功能旗標用於開關開發模式、回放功能與多桌支援。


# ==================== Burn-in 與效能診斷 ====================
ENABLE_ADAPTIVE_QUALITY = get_bool_env("ENABLE_ADAPTIVE_QUALITY", "false")
ENABLE_SUBSCRIBER_CHECK = get_bool_env("ENABLE_SUBSCRIBER_CHECK", "true")
PERF_DIAGNOSTICS_ENABLED = get_bool_env("PERF_DIAGNOSTICS_ENABLED", "true")
ENABLE_CAMERA_PREVIEW_WINDOW = get_bool_env("ENABLE_CAMERA_PREVIEW_WINDOW", "false")
CAMERA_GRAB_FLUSH_FRAMES = get_env("CAMERA_GRAB_FLUSH_FRAMES", "-1", int)
CAMERA_EXPOSURE_CACHE_FRAMES = get_env("CAMERA_EXPOSURE_CACHE_FRAMES", "30", int)
ENABLE_LEGACY_VIDEO_WS = get_bool_env("ENABLE_LEGACY_VIDEO_WS", "false")
CAMERA_FOURCC_PRIORITY = get_env("CAMERA_FOURCC_PRIORITY", "MJPG,YUY2,YUYV", str)
PROJECTOR_RENDER_MAX_FPS = get_env("PROJECTOR_RENDER_MAX_FPS", "15", int)
MONITOR_STREAM_USE_YOLO_OVERLAY = get_bool_env("MONITOR_STREAM_USE_YOLO_OVERLAY", "false")
MONITOR_OVERLAY_CACHE_ENABLED = get_bool_env("MONITOR_OVERLAY_CACHE_ENABLED", "false")
PROJECTOR_RENDER_CACHE_ENABLED = get_bool_env("PROJECTOR_RENDER_CACHE_ENABLED", "false")
PROJECTOR_SHOW_EMPTY_STATUS = get_bool_env("PROJECTOR_SHOW_EMPTY_STATUS", "true")
PROJECTOR_SHOW_POSITION_AVOID_ZONES = get_bool_env("PROJECTOR_SHOW_POSITION_AVOID_ZONES", "true")
PROJECTOR_SHOW_POCKET_AVOID_ZONES = get_bool_env("PROJECTOR_SHOW_POCKET_AVOID_ZONES", "false")
PROJECTOR_MAX_AVOID_ZONES = get_env("PROJECTOR_MAX_AVOID_ZONES", "3", int)

# Burn-in 與效能診斷設定控制自適應品質、訂閱者檢查、相機緩衝、編碼格式與投影限速。
# PROJECTOR_SHOW_EMPTY_STATUS 只在 practice/game 無任何可見 AR 時顯示淡色診斷提示；idle 仍維持純黑。
