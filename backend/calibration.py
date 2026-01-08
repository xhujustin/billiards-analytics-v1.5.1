# backend/calibration.py

import cv2
import numpy as np


class Calibrator:
    def __init__(self):
        self.homography_matrix = None
        # 預設的投影畫面解析度 (假設投影機是 1080p)
        self.projector_width = 1920
        self.projector_height = 1080

    def has_homography(self) -> bool:
        """Return True if a homography matrix is available on disk or in memory."""
        if self.homography_matrix is not None:
            return True
        try:
            self.homography_matrix = np.load("calibration_matrix.npy")
            return True
        except Exception:
            return False

    def compute_homography(self, camera_points):
        """
        camera_points: 使用者在前端點擊的 4 個攝影機座標點 (順序: 左上, 右上, 右下, 左下)
        """
        # 定義投影機的 4 個角落 (全螢幕)
        # 我們會讓投影機投射一張全黑圖片，四個角落有亮點
        dst_points = np.array(
            [
                [0, 0],  # 左上
                [self.projector_width, 0],  # 右上
                [self.projector_width, self.projector_height],  # 右下
                [0, self.projector_height],  # 左下
            ],
            dtype="float32",
        )

        src_points = np.array(camera_points, dtype="float32")

        # 計算矩陣
        self.homography_matrix, status = cv2.findHomography(src_points, dst_points)

        # 儲存矩陣到檔案，下次不用重校正
        np.save("calibration_matrix.npy", self.homography_matrix)
        # Use ASCII log to avoid encoding issues in some consoles
        print("Calibration saved to calibration_matrix.npy")
        return True

    def transform_points(self, points_list):
        """
        將預測路徑 (Camera Coords) -> 轉換為 -> 投影路徑 (Projector Coords)
        points_list: [[x,y], [x,y]...]
        """
        if not self.has_homography():
            return []  # 尚未校正

        if not points_list:
            return []

        # OpenCV 的 perspectiveTransform 需要這種形狀: (N, 1, 2)
        pts = np.array([points_list], dtype="float32")
        dst_pts = cv2.perspectiveTransform(pts, self.homography_matrix)

        # 轉回 List 格式 [[x, y], ...]
        return dst_pts[0].astype(int).tolist()

    def warp_frame_to_projector(self, frame):
        """
        將相機畫面透過 homography 轉換成投影機座標大小；失敗則回傳原始畫面。
        """
        if not self.has_homography():
            return frame
        try:
            return cv2.warpPerspective(
                frame,
                self.homography_matrix,
                (self.projector_width, self.projector_height),
            )
        except Exception:
            return frame
