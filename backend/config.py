import os

import numpy as np


# --- Helper function to get environment variables ---
def get_env(key, default, converter=str):
    """
    Retrieves an environment variable and converts its type.
    - key: The environment variable name.
    - default: The default value to use if the key is not found.
    - converter: The function to convert the string value (e.g., int, float).
    """
    value = os.getenv(key, default)
    try:
        return converter(value)
    except (ValueError, TypeError):
        print(f"Warning: Could not convert env var '{key}'. Using default: {default}")
        return default


def get_bool_env(key, default):
    """
    Retrieves a boolean environment variable. Accepts typical truthy strings.
    """
    value = os.getenv(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def get_np_array_env(key, default_csv):
    """
    Retrieves a comma-separated env var and converts it to a numpy array.
    """
    value_str = os.getenv(key, default_csv)
    try:
        return np.array([int(x.strip()) for x in value_str.split(",")])
    except (ValueError, TypeError):
        print(f"Warning: Could not parse np.array from env var '{key}'. Using default.")
        return np.array([int(x.strip()) for x in default_csv.split(",")])


# --- 專案根目錄 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 模型設定 ---
# 模型權重檔路徑 (相對於 backend 資料夾)
_model_path_env = os.getenv("MODEL_PATH", "yolo-weight/best.pt")
# 如果是相對路徑，轉為絕對路徑
if not os.path.isabs(_model_path_env):
    MODEL_PATH = os.path.join(BASE_DIR, _model_path_env)
else:
    MODEL_PATH = _model_path_env

# YOLO 推論參數
CONF_THR = get_env("CONF_THR", "0.40", float)
CUE_CONF_THR = get_env("CUE_CONF_THR", "0.50", float)
IOU_THR = get_env("IOU_THR", "0.50", float)
IMG_SIZE = get_env("IMG_SIZE", "640", int)
YOLO_DEVICE = get_env("YOLO_DEVICE", "auto", str)  # auto | cpu | cuda | cuda:0 | 0
YOLO_HALF = get_env("YOLO_HALF", "auto", str)  # auto | true | false
SECOND_PASS_ENABLED = get_bool_env("SECOND_PASS_ENABLED", "true")
SECOND_PASS_MIN_OBJECTS = get_env("SECOND_PASS_MIN_OBJECTS", "4", int)
SECOND_PASS_SKIP_WHEN_CUE_FOUND = get_bool_env("SECOND_PASS_SKIP_WHEN_CUE_FOUND", "true")
CUE_LASER_ONLY_DISABLE_SECOND_PASS = get_bool_env("CUE_LASER_ONLY_DISABLE_SECOND_PASS", "true")
SECOND_PASS_CONF_THR = get_env("SECOND_PASS_CONF_THR", "0.04", float)
SECOND_PASS_IOU_THR = get_env("SECOND_PASS_IOU_THR", "0.45", float)
SECOND_PASS_IMG_SIZE = get_env("SECOND_PASS_IMG_SIZE", "960", int)
# 顏色分類偵錯開關
# COLOR_DEBUG_ENABLED: 是否在 metadata 內輸出每顆球的中間特徵
# COLOR_DEBUG_PRINT: 是否在後端 console 輸出每顆球的偵錯資訊
COLOR_DEBUG_ENABLED = get_bool_env("COLOR_DEBUG_ENABLED", "false")
COLOR_DEBUG_PRINT = get_bool_env("COLOR_DEBUG_PRINT", "false")
TRACKER_DRAW_ANNOTATIONS = get_bool_env("TRACKER_DRAW_ANNOTATIONS", "true")

# 局部 Hough 幾何修正（僅在 YOLO bbox 內執行）
# LOCAL_HOUGH_REFINE_ENABLED: 開啟/關閉局部圓形修正
# LOCAL_HOUGH_PAD_RATIO: bbox 外擴比例，提供 Hough 搜尋邊界餘裕
# LOCAL_HOUGH_MIN_R_SCALE / MAX_R_SCALE: 以 YOLO 半徑為基準的最小/最大搜尋比例
# LOCAL_HOUGH_DP, PARAM1, PARAM2: OpenCV HoughCircles 參數
# LOCAL_HOUGH_MIN_SAT_MEDIAN / MIN_VAL_MEDIAN: 用於過濾陰影假圓的 HSV 中位數門檻
LOCAL_HOUGH_REFINE_ENABLED = get_bool_env("LOCAL_HOUGH_REFINE_ENABLED", "false")
LOCAL_HOUGH_PAD_RATIO = get_env("LOCAL_HOUGH_PAD_RATIO", "0.25", float)
LOCAL_HOUGH_MIN_R_SCALE = get_env("LOCAL_HOUGH_MIN_R_SCALE", "0.55", float)
LOCAL_HOUGH_MAX_R_SCALE = get_env("LOCAL_HOUGH_MAX_R_SCALE", "1.20", float)
LOCAL_HOUGH_DP = get_env("LOCAL_HOUGH_DP", "1.2", float)
LOCAL_HOUGH_PARAM1 = get_env("LOCAL_HOUGH_PARAM1", "110", float)
LOCAL_HOUGH_PARAM2 = get_env("LOCAL_HOUGH_PARAM2", "16", float)
LOCAL_HOUGH_MIN_SAT_MEDIAN = get_env("LOCAL_HOUGH_MIN_SAT_MEDIAN", "35", float)
LOCAL_HOUGH_MIN_VAL_MEDIAN = get_env("LOCAL_HOUGH_MIN_VAL_MEDIAN", "40", float)

# 多層半徑取樣參數（顏色分類）
# COLOR_MASK_CORE_RATIO: 核心層半徑比例（主色分類優先）
# COLOR_MASK_MID_RATIO: 中層半徑比例（補充主色統計）
# COLOR_MASK_OUTER_RATIO: 外層半徑比例（樣式判斷用）
COLOR_MASK_CORE_RATIO = get_env("COLOR_MASK_CORE_RATIO", "0.45", float)
COLOR_MASK_MID_RATIO = get_env("COLOR_MASK_MID_RATIO", "0.65", float)
COLOR_MASK_OUTER_RATIO = get_env("COLOR_MASK_OUTER_RATIO", "0.85", float)

# 局部背景環抑制（降低桌布顏色滲入）
# COLOR_BG_RING_ENABLED: 是否啟用背景環比對抑制
# COLOR_BG_RING_INNER_RATIO / OUTER_RATIO: 背景環半徑區間（相對 outer_r）
# COLOR_BG_HUE_TOL / SAT_TOL / VAL_TOL: 判定像素接近背景的容忍範圍
COLOR_BG_RING_ENABLED = get_bool_env("COLOR_BG_RING_ENABLED", "true")
COLOR_BG_RING_INNER_RATIO = get_env("COLOR_BG_RING_INNER_RATIO", "1.05", float)
COLOR_BG_RING_OUTER_RATIO = get_env("COLOR_BG_RING_OUTER_RATIO", "1.30", float)
COLOR_BG_HUE_TOL = get_env("COLOR_BG_HUE_TOL", "10.0", float)
COLOR_BG_SAT_TOL = get_env("COLOR_BG_SAT_TOL", "40.0", float)
COLOR_BG_VAL_TOL = get_env("COLOR_BG_VAL_TOL", "45.0", float)

# 顏色時序平滑（跨幀穩定）
# COLOR_TEMPORAL_SMOOTH_ENABLED: 是否啟用跨幀顏色/樣式平滑
# COLOR_TEMPORAL_WINDOW: 每顆球保留的歷史幀數
# COLOR_TEMPORAL_MATCH_DIST: 以球心匹配歷史軌跡的最大像素距離
# COLOR_TEMPORAL_MIN_STABLE: 票數達門檻才套用平滑結果
COLOR_TEMPORAL_SMOOTH_ENABLED = get_bool_env("COLOR_TEMPORAL_SMOOTH_ENABLED", "true")
COLOR_TEMPORAL_WINDOW = get_env("COLOR_TEMPORAL_WINDOW", "4", int)
COLOR_TEMPORAL_MATCH_DIST = get_env("COLOR_TEMPORAL_MATCH_DIST", "28.0", float)
COLOR_TEMPORAL_MIN_STABLE = get_env("COLOR_TEMPORAL_MIN_STABLE", "2", int)

# 球體重複/誤檢抑制
# BALL_DUPLICATE_CENTER_RATIO: 兩顆候選球中心距離小於 max(r1,r2)*ratio 時視為重複，保留高信心
# WHITE_OVERLAP_SUPPRESS_RATIO: 彩球中心若與主白球過度重疊，會被移除避免白球上疊色
BALL_DUPLICATE_CENTER_RATIO = get_env("BALL_DUPLICATE_CENTER_RATIO", "0.72", float)
WHITE_OVERLAP_SUPPRESS_RATIO = get_env("WHITE_OVERLAP_SUPPRESS_RATIO", "0.88", float)

# 球袋假球抑制
# POCKET_FALSE_POSITIVE_FILTER_ENABLED: 啟用袋口黑色假球過濾
# POCKET_FALSE_POSITIVE_CORE_RATIO: 袋口核心半徑比例（越小越保守）
POCKET_FALSE_POSITIVE_FILTER_ENABLED = get_bool_env("POCKET_FALSE_POSITIVE_FILTER_ENABLED", "true")
POCKET_FALSE_POSITIVE_CORE_RATIO = get_env("POCKET_FALSE_POSITIVE_CORE_RATIO", "0.62", float)

# --- 影像處理設定 ---
# 球桌顏色預設值（預設為綠色）
TABLE_CLOTH_COLOR = get_env("TABLE_CLOTH_COLOR", "green", str)

# 球桌顏色預設 HSV 範圍
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

# 球桌 HSV 閾值 (用於 detect_table)
# 在 .env 中以 "35, 40, 40" 格式設定
# 優先使用環境變數，否則使用預設顏色
if os.getenv("HSV_LOWER") and os.getenv("HSV_UPPER"):
    HSV_LOWER = get_np_array_env("HSV_LOWER", "35, 40, 40")
    HSV_UPPER = get_np_array_env("HSV_UPPER", "85, 255, 255")
else:
    # 使用預設顏色的 HSV 範圍
    color_preset = TABLE_COLOR_PRESETS.get(TABLE_CLOTH_COLOR, TABLE_COLOR_PRESETS["green"])
    HSV_LOWER = color_preset["hsv_lower"]
    HSV_UPPER = color_preset["hsv_upper"]


# 球桌偵測最小面積（降低閾值以檢測更小的球桌）
TABLE_MIN_AREA = get_env("TABLE_MIN_AREA", "50000", int)

# --- 相機與傳輸設定 ---
CAMERA_WIDTH = get_env("CAMERA_WIDTH", "1280", int)
CAMERA_HEIGHT = get_env("CAMERA_HEIGHT", "720", int)
CAMERA_FPS = get_env("CAMERA_FPS", "30", int)
JPEG_QUALITY = get_env("JPEG_QUALITY", "70", int)  # 影像傳輸品質 (0-100)

# ==================== 相機進階參數 ====================
CAMERA_EXPOSURE = get_env("CAMERA_EXPOSURE", "-6", int)  # 曝光時間 (-13 to -1, 負值表示自動)
CAMERA_ISO = get_env("CAMERA_ISO", "0", int)  # ISO 感光度 (0 for auto, 100-3200)
CAMERA_BRIGHTNESS = get_env("CAMERA_BRIGHTNESS", "128", int)  # 亮度 (0-255)
CAMERA_CONTRAST = get_env("CAMERA_CONTRAST", "128", int)  # 對比度 (0-255)
CAMERA_SATURATION = get_env("CAMERA_SATURATION", "128", int)  # 飽和度 (0-255)
CAMERA_SHARPNESS = get_env("CAMERA_SHARPNESS", "128", int)  # 銳利度 (0-255)
CAMERA_AUTO_WB = get_bool_env("CAMERA_AUTO_WB", "true")  # 自動白平衡
CAMERA_WB_TEMP = get_env("CAMERA_WB_TEMP", "4000", int)  # 白平衡色溫 (2800-6500K)

# ==================== 軟體降噪參數 ====================
DENOISE_ENABLED = get_bool_env("DENOISE_ENABLED", "false")  # 是否啟用降噪
DENOISE_STRENGTH = get_env("DENOISE_STRENGTH", "10", int)  # 降噪強度 (0-100)
DENOISE_METHOD = get_env("DENOISE_METHOD", "bilateral", str)  # 降噪演算法 (bilateral推薦, gaussian最快, fastNlMeans較慢)

VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "")
STREAM_PROJECTOR_VIEW = get_bool_env("STREAM_PROJECTOR_VIEW", "true")
LOOP_VIDEO_SOURCE = get_bool_env("LOOP_VIDEO_SOURCE", "true")

# --- Session Management (v1.5) ---
SESSION_TTL = get_env("SESSION_TTL", "3600", int)  # Session 有效期（秒）
SESSION_RENEW_WINDOW = get_env("SESSION_RENEW_WINDOW", "0.2", float)  # 續期視窗比例
SESSION_MIN_RENEW_WINDOW = get_env("SESSION_MIN_RENEW_WINDOW", "300", int)  # 最小續期視窗（秒）

# --- WebSocket Settings (v1.5) ---
WS_HEARTBEAT_INTERVAL = get_env("WS_HEARTBEAT_INTERVAL", "3", int)  # Heartbeat 間隔（秒）
WS_CLIENT_TIMEOUT = get_env("WS_CLIENT_TIMEOUT", "15", int)  # Client heartbeat 超時（秒）

# --- Stream Settings (v1.5) ---
MJPEG_QUALITY = get_env("MJPEG_QUALITY", "80", int)
MJPEG_MAX_FPS = get_env("MJPEG_MAX_FPS", "60", int)

# --- Metadata Settings (v1.5) ---
METADATA_RATE_HZ = get_env("METADATA_RATE_HZ", "10", int)  # Metadata 推送頻率
METADATA_BUFFER_SIZE = get_env("METADATA_BUFFER_SIZE", "100", int)  # Buffer 大小限制

# --- Feature Flags (v1.5) ---
ENABLE_DEV_MODE = get_bool_env("ENABLE_DEV_MODE", "false")
ENABLE_REPLAY = get_bool_env("ENABLE_REPLAY", "false")
ENABLE_MULTI_TABLE = get_bool_env("ENABLE_MULTI_TABLE", "false")

# --- Burn-in Performance Settings ---
ENABLE_ADAPTIVE_QUALITY = get_bool_env("ENABLE_ADAPTIVE_QUALITY", "false")  # 預設關閉,由用戶啟用
ENABLE_SUBSCRIBER_CHECK = get_bool_env("ENABLE_SUBSCRIBER_CHECK", "true")  # 啟用訂閱者檢查

