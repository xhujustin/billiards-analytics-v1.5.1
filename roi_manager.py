"""Interactive ROI selection and polygon mask utilities.

This module intentionally keeps the original image coordinates. Do not use
perspective transform or image warping here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


WINDOW_NAME = "ROI Manager - click 4 table inner corners"
POINT_RADIUS = 10
POINT_OUTLINE_RADIUS = 14
POINT_OUTLINE_THICKNESS = 3
LINE_THICKNESS = 4
TEXT_THICKNESS = 3


def _normalize_points(points: Iterable[Any]) -> list[list[int]]:
    normalized: list[list[int]] = []

    for point in points:
        if isinstance(point, dict):
            x = point.get("x")
            y = point.get("y")
        else:
            x, y = point
        normalized.append([int(round(float(x))), int(round(float(y)))])

    if len(normalized) != 4:
        raise ValueError(f"ROI config must contain exactly 4 points, got {len(normalized)}")

    return normalized


def _load_roi_points(config_path: str | Path) -> list[list[int]]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    points = data.get("points") if isinstance(data, dict) else data
    if points is None:
        raise ValueError(f"ROI config missing 'points': {path}")

    return _normalize_points(points)


def _save_roi_points(points: list[tuple[int, int]], config_path: str | Path) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "points": [{"x": int(x), "y": int(y)} for x, y in points],
        "coordinate_space": "original_image",
        "point_order": "clicked_order",
        "transform": "none",
    }

    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")


def _draw_preview(image: np.ndarray, points: list[tuple[int, int]]) -> np.ndarray:
    preview = image.copy()

    for index, point in enumerate(points):
        cv2.circle(preview, point, POINT_OUTLINE_RADIUS, (0, 0, 0), POINT_OUTLINE_THICKNESS)
        cv2.circle(preview, point, POINT_RADIUS, (0, 255, 255), -1)
        cv2.putText(
            preview,
            str(index + 1),
            (point[0] + 14, point[1] - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            TEXT_THICKNESS,
            cv2.LINE_AA,
        )

    if len(points) >= 2:
        for start, end in zip(points, points[1:]):
            cv2.line(preview, start, end, (0, 255, 0), LINE_THICKNESS, cv2.LINE_AA)

    if len(points) == 4:
        cv2.line(preview, points[-1], points[0], (0, 255, 0), LINE_THICKNESS, cv2.LINE_AA)
        cv2.putText(
            preview,
            "Press 's' to save, 'q' to cancel",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            TEXT_THICKNESS,
            cv2.LINE_AA,
        )
    else:
        cv2.putText(
            preview,
            f"Click table inner corners: {len(points)}/4",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            TEXT_THICKNESS,
            cv2.LINE_AA,
        )

    return preview


def interactive_select_roi(image_path: str | Path, config_path: str | Path = "roi_config.json") -> bool:
    """Select four ROI points interactively and save them to JSON.

    Left click adds points until four points are selected. Press ``s`` after the
    fourth point to save. Press ``q`` to cancel and exit.

    Returns:
        True when the ROI config is saved, False when cancelled.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Unable to read image: {image_path}")

    points: list[tuple[int, int]] = []

    def on_mouse(event: int, x: int, y: int, _flags: int, _param: Any) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or len(points) >= 4:
            return
        points.append((int(x), int(y)))

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    saved = False
    try:
        while True:
            cv2.imshow(WINDOW_NAME, _draw_preview(image, points))
            key = cv2.waitKey(20) & 0xFF

            if key == ord("q"):
                break
            if key == ord("s") and len(points) == 4:
                _save_roi_points(points, config_path)
                saved = True
                break
    finally:
        cv2.destroyWindow(WINDOW_NAME)

    return saved


def apply_roi_mask(frame: np.ndarray, config_path: str | Path = "roi_config.json") -> np.ndarray:
    """Black out pixels outside the configured polygon ROI.

    The output keeps the same shape, dtype, and coordinate space as ``frame``.
    No perspective transform or warp is performed.
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("frame must be a numpy.ndarray")
    if frame.ndim not in (2, 3):
        raise ValueError(f"frame must be a 2D or 3D image, got shape {frame.shape}")

    points = np.array([_load_roi_points(config_path)], dtype=np.int32)
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, points, 255)

    return cv2.bitwise_and(frame, frame, mask=mask)


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive billiards table ROI selector")
    parser.add_argument("image_path", help="Path to the source image")
    parser.add_argument("--config", default="roi_config.json", help="Path to write ROI JSON")
    args = parser.parse_args()

    return 0 if interactive_select_roi(args.image_path, args.config) else 1


if __name__ == "__main__":
    raise SystemExit(main())
