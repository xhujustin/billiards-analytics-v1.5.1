"""
ArUco 標記檢測器
用於投影機自動校正,檢測 ID 0-3 的 ArUco 標記
"""

import cv2
import numpy as np
import os
import time
from typing import Optional, Dict

class ArucoDetector:
    """ArUco 標記自動檢測器"""

    def __init__(self):
        # 使用 4x4 字典 (50 個標記)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        
        # 設定檢測參數 (優化投影標記檢測)
        self.aruco_params = cv2.aruco.DetectorParameters()
        # 大幅降低最小標記周長閾值
        self.aruco_params.minMarkerPerimeterRate = 0.005  # 預設 0.03, 降低以檢測更小標記
        # 提高最大標記周長閾值
        self.aruco_params.maxMarkerPerimeterRate = 4.0   # 預設 4.0
        # 調整多邊形逼近精度（更寬容）
        self.aruco_params.polygonalApproxAccuracyRate = 0.08  # 預設 0.03, 提高容錯性
        # 角點精細化方法
        self.aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        # 自適應閾值視窗：標記在相機畫面已放大，且環境光強對比低，
        # 擴大視窗範圍涵蓋更多尺度，提高低對比下找到方形的機率
        self.aruco_params.adaptiveThreshWinSizeMin = 3
        self.aruco_params.adaptiveThreshWinSizeMax = 45
        self.aruco_params.adaptiveThreshWinSizeStep = 10
        
        # 建立 ArUco 檢測器 (OpenCV 4.7+ 新版 API)
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        self.last_corners = None

        # CLAHE 對比強化器（環境光強、投影標記偏淡時拉開 bit 對比）
        self._clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))

        # 偵測失敗時的除錯影像輸出目錄
        self._debug_dir = os.path.join(os.path.dirname(__file__), "debug_frames")

    # 校正只關心這 4 個 ID，其餘（含反轉誤讀出的合法 ID）一律忽略
    EXPECTED_IDS = (0, 1, 2, 3)

    def _save_debug_frame(self, frame: np.ndarray, gray: np.ndarray) -> None:
        """偵測失敗時，存下相機原始畫面與灰階圖，方便確認相機實際吃到什麼。"""
        try:
            os.makedirs(self._debug_dir, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(os.path.join(self._debug_dir, f"fail_{stamp}_bgr.png"), frame)
            cv2.imwrite(os.path.join(self._debug_dir, f"fail_{stamp}_gray.png"), gray)
            print(f"[ArUco] 偵測失敗，已存除錯影像至 {self._debug_dir}")
        except Exception as exc:  # 除錯存圖不可影響主流程
            print(f"[ArUco] 除錯影像儲存失敗: {exc}")

    def detect(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        檢測 ArUco 標記 (ID 0-3)

        Args:
            frame: 輸入影像 (BGR)

        Returns:
            corners: 4個角點座標 [[x,y], [x,y], [x,y], [x,y]]
                    順序: 左上(ID=0), 右上(ID=1), 右下(ID=2), 左下(ID=3)
            None: 未檢測到完整的 4 個標記
        """
        # 轉灰階
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 多道前處理各自偵測，跨道「只收期望 ID 0-3」並逐一湊齊。
        # 不再整道取代：避免反轉道把 bit 翻轉後解出的錯誤合法 ID（如 17）
        # 蓋掉正常道的正確讀值。順序＝優先序（先到的 ID 不被後面覆蓋）：
        #   normal  : 原始灰階（白底黑標記，標準渲染下最準）
        #   clahe   : 對比強化（環境光強、標記偏淡時補強）
        #   inverted: 反轉（萬一相機端呈深底白標記才有用，故放最後且只收 0-3）
        passes = [
            ("normal", gray),
            ("clahe", self._clahe.apply(gray)),
            ("inverted", cv2.bitwise_not(gray)),
        ]

        detected_corners: Dict[int, np.ndarray] = {}
        for name, img in passes:
            corners, ids, _ = self.detector.detectMarkers(img)
            if ids is None:
                print(f"[ArUco] {name}: 無標記")
                continue
            id_list = ids.flatten().tolist()
            print(f"[ArUco] {name}: 檢測到 {len(id_list)} 個, IDs: {id_list}")
            for i, marker_id in enumerate(id_list):
                if marker_id in self.EXPECTED_IDS and marker_id not in detected_corners:
                    detected_corners[marker_id] = corners[i][0].mean(axis=0)
            if len(detected_corners) == len(self.EXPECTED_IDS):
                break  # 4 個期望 ID 都湊齊，提早結束

        found = sorted(detected_corners.keys())
        print(f"[ArUco] 合併後有效 ID（0-3）: {found}")

        # 檢查是否湊齊全部 4 個期望標記
        if len(detected_corners) != len(self.EXPECTED_IDS):
            self._save_debug_frame(frame, gray)
            return None

        # 按 ID 順序排列
        result = np.array([
            detected_corners[0],  # 左上
            detected_corners[1],  # 右上
            detected_corners[2],  # 右下
            detected_corners[3]   # 左下
        ], dtype=np.float32)
        
        self.last_corners = result
        return result
    
    def draw_detection(self, frame: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """
        繪製檢測結果 (綠色框線 + 位置標籤)
        
        Args:
            frame: 輸入影像
            corners: 檢測到的角點
        
        Returns:
            繪製後的影像
        """
        result = frame.copy()
        
        # 繪製外框 (綠色)
        pts = corners.astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(result, [pts], True, (0, 255, 0), 3, cv2.LINE_AA)
        
        # 繪製角點和位置標籤（使用英文避免亂碼）
        labels = ['TL', 'TR', 'BR', 'BL']  # Top-Left, Top-Right, Bottom-Right, Bottom-Left
        for i, corner in enumerate(corners):
            pos = tuple(corner.astype(int))
            # 角點圓圈
            cv2.circle(result, pos, 8, (0, 0, 255), -1)
            # 位置標籤
            cv2.putText(result, labels[i], 
                       (pos[0] + 15, pos[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return result
