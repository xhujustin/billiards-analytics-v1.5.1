"""
投影機校正 API 模組

提供 ArUco 標記校正和投影機控制 API
"""

from fastapi import APIRouter, HTTPException
import time
import cv2
import numpy as np

# 創建 API Router
router = APIRouter()

# 這些變數需要從 main.py 導入或共享
# 暫時使用全域變數,後續可以優化
calibration_state = None
projector_renderer = None
camera_state = None
aruco_detector = None
projector_overlay = None
calibrator = None
ProjectorMode = None


def init_calibration_api(main_module):
    """初始化校正 API,從 main 模組導入必要的變數"""
    global calibration_state, projector_renderer, camera_state
    global aruco_detector, projector_overlay, calibrator, ProjectorMode
    
    calibration_state = main_module.calibration_state
    projector_renderer = main_module.projector_renderer
    camera_state = main_module.camera_state
    aruco_detector = main_module.aruco_detector
    projector_overlay = main_module.projector_overlay
    calibrator = main_module.calibrator
    ProjectorMode = main_module.ProjectorMode


# ==================== 測試端點 ====================

@router.get("/api/calibration/test")
async def test_calibration_api():
    """測試端點"""
    return {"status": "ok", "message": "Calibration API module is loaded", "timestamp": time.time()}


# ==================== 投影機校正 API ====================

@router.post("/api/calibration/start")
async def start_calibration():
    """開始校正流程"""
    calibration_state["is_calibrating"] = True
    calibration_state["detected_corners"] = None
    
    # 切換投影機到校正模式
    if projector_renderer is not None:
        projector_renderer.set_mode(ProjectorMode.CALIBRATION)
    
    return {"status": "ok", "message": "校正已啟動"}


@router.post("/api/calibration/move-corner")
async def move_corner(data: dict):
    """
    移動指定角落的標記
    """
    corner = data.get("corner")
    offset = data.get("offset", {})
    
    if corner not in calibration_state["corner_offsets"]:
        raise HTTPException(status_code=400, detail="Invalid corner")
    
    # 更新偏移量
    calibration_state["corner_offsets"][corner] = offset
    
    # 更新投影機渲染器
    if projector_renderer is not None:
        projector_renderer.update_calibration_offsets(calibration_state["corner_offsets"])
    
    return {"status": "ok", "corner": corner, "offset": offset}


@router.get("/api/calibration/detect")
async def detect_aruco_markers():
    """檢測當前相機畫面中的 ArUco 標記"""
    cap = camera_state.get("current_cap")
    if cap is None:
        raise HTTPException(status_code=500, detail="相機未初始化")
    
    ret, frame = cap.read()
    if not ret:
        raise HTTPException(status_code=500, detail="無法讀取相機畫面")
    
    if aruco_detector is None:
        raise HTTPException(status_code=500, detail="ArUco 檢測器未初始化")
    
    # 執行檢測（調試信息會在後端控制台輸出）
    corners = aruco_detector.detect(frame)
    
    if corners is None:
        # 返回更詳細的診斷信息
        return {
            "detected": False,
            "message": "未檢測到完整的 4 個 ArUco 標記",
            "hint": "請檢查: 1) 投影機是否顯示 ArUco 標記 2) 攝像頭是否能拍到投影區域 3) 查看後端控制台調試日誌"
        }
    
    calibration_state["detected_corners"] = corners.tolist()
    
    return {
        "detected": True,
        "corners": corners.tolist(),
        "marker_ids": [0, 1, 2, 3],
        "message": "ArUco 標記檢測成功"
    }


@router.get("/api/calibration/preview")
async def get_calibration_preview():
    """獲取校正預覽畫面"""
    from fastapi import Response
    
    cap = camera_state.get("current_cap")
    if cap is None:
        raise HTTPException(status_code=500, detail="相機未初始化")
    
    ret, frame = cap.read()
    if not ret:
        raise HTTPException(status_code=500, detail="無法讀取相機畫面")
    
    if aruco_detector is not None:
        corners = aruco_detector.detect(frame)
        
        if corners is not None and projector_overlay is not None:
            frame = projector_overlay.draw_preview_overlay(frame, corners)
    
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(content=buffer.tobytes(), media_type="image/jpeg")


@router.post("/api/calibration/confirm")
async def confirm_calibration():
    """確認校正並計算矩陣"""
    corners = calibration_state.get("detected_corners")
    if corners is None:
        raise HTTPException(status_code=400, detail="尚未檢測到 ArUco 標記")
    
    if calibrator is None:
        raise HTTPException(status_code=500, detail="Calibrator 未初始化")
    
    # 計算投影機座標
    corner_offsets = calibration_state["corner_offsets"]
    center_x, center_y = 1920 // 2, 1080 // 2
    
    projector_corners = []
    for corner_key in ["top-left", "top-right", "bottom-right", "bottom-left"]:
        offset = corner_offsets[corner_key]
        projector_corners.append([center_x + offset["x"], center_y + offset["y"]])
    
    # 計算校準矩陣
    src_points = np.array(corners, dtype="float32")
    dst_points = np.array(projector_corners, dtype="float32")
    
    calibrator.homography_matrix, _ = cv2.findHomography(src_points, dst_points)
    np.save("calibration_matrix.npy", calibrator.homography_matrix)
    
    # 計算投影範圍
    xs = [p[0] for p in projector_corners]
    ys = [p[1] for p in projector_corners]
    bounds = {
        "x": int(min(xs)),
        "y": int(min(ys)),
        "width": int(max(xs) - min(xs)),
        "height": int(max(ys) - min(ys))
    }
    calibrator.set_projection_bounds(bounds)
    
    calibration_state["is_calibrating"] = False
    
    if projector_renderer is not None:
        projector_renderer.set_mode(ProjectorMode.IDLE)
    
    return {"status": "ok", "message": "校正完成", "bounds": bounds}


# ==================== 投影機控制 API ====================

@router.post("/api/projector/mode")
async def set_projector_mode(data: dict):
    """設定投影機模式"""
    mode_str = data.get("mode", "idle")
    try:
        mode = ProjectorMode(mode_str)
        if projector_renderer is not None:
            projector_renderer.set_mode(mode)
        return {"status": "ok", "mode": mode.value}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mode")


@router.post("/api/projector/ar/update")
async def update_ar_data(ar_data: dict):
    """更新 AR 疊加資料"""
    if projector_renderer is not None:
        projector_renderer.update_ar_data(ar_data)
    return {"status": "ok"}
