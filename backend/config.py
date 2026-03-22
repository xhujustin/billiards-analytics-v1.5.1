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
_model_path_env = os.getenv("MODEL_PATH", "yolo-weight/pool.pt")
# 如果是相對路徑，轉為絕對路徑
if not os.path.isabs(_model_path_env):
    MODEL_PATH = os.path.join(BASE_DIR, _model_path_env)
else:
    MODEL_PATH = _model_path_env

# YOLO 推論參數
CONF_THR = get_env("CONF_THR", "0.08", float)
IOU_THR = get_env("IOU_THR", "0.50", float)
IMG_SIZE = get_env("IMG_SIZE", "640", int)
SECOND_PASS_ENABLED = get_bool_env("SECOND_PASS_ENABLED", "true")
SECOND_PASS_MIN_OBJECTS = get_env("SECOND_PASS_MIN_OBJECTS", "4", int)
SECOND_PASS_CONF_THR = get_env("SECOND_PASS_CONF_THR", "0.04", float)
SECOND_PASS_IOU_THR = get_env("SECOND_PASS_IOU_THR", "0.45", float)
SECOND_PASS_IMG_SIZE = get_env("SECOND_PASS_IMG_SIZE", "960", int)

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
MJPEG_MAX_FPS = get_env("MJPEG_MAX_FPS", "30", int)

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

