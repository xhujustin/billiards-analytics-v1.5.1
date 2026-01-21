"""
縮圖 API - 提供錄影縮圖圖片（支援分類資料夾）
"""
from fastapi import APIRouter, Response
import os

router = APIRouter()

@router.get("/api/recordings/{game_id}/thumbnail")
async def get_thumbnail(game_id: str):
    """
    獲取錄影縮圖（支援分類資料夾結構）
    """
    # 使用絕對路徑
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    recordings_dir = os.path.join(project_root, "recordings")
    
    # 在所有分類資料夾中搜尋該 game_id 的縮圖
    thumbnail_path = None
    if os.path.exists(recordings_dir):
        for root, dirs, files in os.walk(recordings_dir):
            if "thumbnail.jpg" in files and game_id in root:
                thumbnail_path = os.path.join(root, "thumbnail.jpg")
                break
    
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        # 如果縮圖不存在，返回 404
        return Response(status_code=404)
    
    # 讀取並返回縮圖
    with open(thumbnail_path, "rb") as f:
        return Response(content=f.read(), media_type="image/jpeg")

