"""
V1.5 Protocol Error Codes
與前端 types.ts 中的 CmdErrorPayload.code 保持一致
用於國際化錯誤消息和客戶端錯誤處理
"""

# P0 核心錯誤碼
ERR_INVALID_ARGUMENT = "ERR_INVALID_ARGUMENT"  # 請求參數無效
ERR_NOT_FOUND = "ERR_NOT_FOUND"  # 資源不存在（session/stream）
ERR_FORBIDDEN = "ERR_FORBIDDEN"  # 無權限操作
ERR_RATE_LIMIT = "ERR_RATE_LIMIT"  # 超過頻率限制
ERR_SESSION_EXPIRED = "ERR_SESSION_EXPIRED"  # Session 已過期
ERR_STREAM_UNAVAILABLE = "ERR_STREAM_UNAVAILABLE"  # Stream 不可用

# P1 進階錯誤碼
ERR_INVALID_COMMAND = "ERR_INVALID_COMMAND"  # 命令格式錯誤
ERR_UNSUPPORTED_VERSION = "ERR_UNSUPPORTED_VERSION"  # 不支援的協議版本
ERR_BACKEND_BUSY = "ERR_BACKEND_BUSY"  # 後端處理中，請稍後
ERR_CALIBRATION_REQUIRED = "ERR_CALIBRATION_REQUIRED"  # 需要校正
ERR_STREAM_CONFLICT = "ERR_STREAM_CONFLICT"  # Stream 衝突

# P2 系統錯誤
ERR_INTERNAL = "ERR_INTERNAL"  # 伺服器內部錯誤


def create_error_response(code: str, message: str, details: dict = None) -> dict:
    """
    建立標準化的錯誤響應
    
    Args:
        code: 錯誤碼（ERR_*）
        message: 人類可讀的錯誤訊息
        details: 額外的錯誤細節（選填）
    
    Returns:
        dict: 符合 ApiErrorResponse schema 的字典
    """
    error = {
        "code": code,
        "message": message
    }
    if details:
        error["details"] = details
    
    return {"error": error}
