import os

import numpy as np


# ==================== 環境變數讀取工具 ====================
def get_env(key, default, converter=str):
    """
    讀取環境變數並轉型；轉型失敗時回退到預設值。
    """
    value = os.getenv(key, default)
    try:
        return converter(value)
    except (ValueError, TypeError):
        print(f"Warning: Could not convert env var '{key}'. Using default: {default}")
        return default


def get_bool_env(key, default):
    """
    讀取布林環境變數，支援 1/true/yes/y/on 作為 True。
    """
    value = os.getenv(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def get_np_array_env(key, default_csv):
    """
    讀取逗號分隔的環境變數並轉成 numpy array。
    """
    value_str = os.getenv(key, default_csv)
    try:
        return np.array([int(x.strip()) for x in value_str.split(",")])
    except (ValueError, TypeError):
        print(f"Warning: Could not parse np.array from env var '{key}'. Using default.")
        return np.array([int(x.strip()) for x in default_csv.split(",")])


# 環境變數讀取工具結束。


# ==================== 專案路徑與模型權重 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_model_path_env = os.getenv("MODEL_PATH", "yolo-weight/best.pt")
if not os.path.isabs(_model_path_env):
    MODEL_PATH = os.path.join(BASE_DIR, _model_path_env)
else:
    MODEL_PATH = _model_path_env

# 專案路徑與模型權重設定結束。


# ==================== YOLO 推論基礎參數 ====================
CONF_THR = get_env("CONF_THR", "0.60", float)
CUE_CONF_THR = get_env("CUE_CONF_THR", "0.50", float)
IOU_THR = get_env("IOU_THR", "0.50", float)
IMG_SIZE = get_env("IMG_SIZE", "640", int)
YOLO_DEVICE = get_env("YOLO_DEVICE", "auto", str)  # auto | cpu | cuda | cuda:0 | 0
YOLO_HALF = get_env("YOLO_HALF", "auto", str)  # auto | true | false

# YOLO 推論基礎參數結束。


# ==================== YOLO 第二階段推論與分割遮罩 ====================
SECOND_PASS_ENABLED = get_bool_env("SECOND_PASS_ENABLED", "true")
SECOND_PASS_MIN_OBJECTS = get_env("SECOND_PASS_MIN_OBJECTS", "4", int)
SECOND_PASS_SKIP_WHEN_CUE_FOUND = get_bool_env("SECOND_PASS_SKIP_WHEN_CUE_FOUND", "true")
CUE_LASER_ONLY_DISABLE_SECOND_PASS = get_bool_env("CUE_LASER_ONLY_DISABLE_SECOND_PASS", "true")
CUE_SEGMENTATION_MASK_ENABLED = get_bool_env("CUE_SEGMENTATION_MASK_ENABLED", "true")
SECOND_PASS_CONF_THR = get_env("SECOND_PASS_CONF_THR", "0.04", float)
SECOND_PASS_IOU_THR = get_env("SECOND_PASS_IOU_THR", "0.45", float)
SECOND_PASS_IMG_SIZE = get_env("SECOND_PASS_IMG_SIZE", "960", int)

# 第二階段推論用於低檢出幀補強；cue laser only 可停用第二階段以降低延遲。


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

# 球桿軸線設定控制短暫漏檢沿用、平滑權重、換桿重置與大位移快速收斂。


# ==================== 顏色分類偵錯與即時影像 Overlay ====================
COLOR_DEBUG_ENABLED = get_bool_env("COLOR_DEBUG_ENABLED", "false")
COLOR_DEBUG_PRINT = get_bool_env("COLOR_DEBUG_PRINT", "false")
TRACKER_DRAW_ANNOTATIONS = get_bool_env("TRACKER_DRAW_ANNOTATIONS", "true")
TRACKER_ANNOTATION_MODE = get_env("TRACKER_ANNOTATION_MODE", "full", str)  # none | tactical | full
OVERLAY_METADATA_MAX_AGE_MS = get_env("OVERLAY_METADATA_MAX_AGE_MS", "1000", int)
PROJECTOR_AR_METADATA_MAX_AGE_MS = get_env("PROJECTOR_AR_METADATA_MAX_AGE_MS", "1200", int)
LAST_GOOD_OVERLAY_HOLD_MS = get_env("LAST_GOOD_OVERLAY_HOLD_MS", "5000", int)
LAST_GOOD_PROJECTOR_AR_HOLD_MS = get_env("LAST_GOOD_PROJECTOR_AR_HOLD_MS", "5000", int)

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
TABLE_CLOTH_COLOR = get_env("TABLE_CLOTH_COLOR", "green", str)
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

if os.getenv("HSV_LOWER") and os.getenv("HSV_UPPER"):
    HSV_LOWER = get_np_array_env("HSV_LOWER", "35, 40, 40")
    HSV_UPPER = get_np_array_env("HSV_UPPER", "85, 255, 255")
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
JPEG_QUALITY = get_env("JPEG_QUALITY", "70", int)
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "")
STREAM_PROJECTOR_VIEW = get_bool_env("STREAM_PROJECTOR_VIEW", "true")
LOOP_VIDEO_SOURCE = get_bool_env("LOOP_VIDEO_SOURCE", "true")

# 本段控制相機基本格式、JPEG 傳輸品質、影片檔來源與投影視圖串流。


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
METADATA_RATE_HZ = get_env("METADATA_RATE_HZ", "10", int)
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
PROJECTOR_RENDER_MAX_FPS = get_env("PROJECTOR_RENDER_MAX_FPS", "12", int)
MONITOR_STREAM_USE_YOLO_OVERLAY = get_bool_env("MONITOR_STREAM_USE_YOLO_OVERLAY", "true")

# Burn-in 與效能診斷設定控制自適應品質、訂閱者檢查、相機緩衝、編碼格式與投影限速。
