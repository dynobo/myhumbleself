import logging

import cv2
import numpy as np

from myhumbleself.face_detection import Rect

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def convert_colorspace(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)


def crop_circle(
    frame: np.ndarray, coords: Rect, padding_factor: float = 0.5
) -> np.ndarray:
    mask = np.zeros(frame.shape, dtype=np.uint8)
    height, width, _ = frame.shape

    padding = int(max(coords.width, coords.height) * padding_factor)
    radius = min(coords.width // 2, coords.height // 2) + padding
    if radius > min(width, height) // 2:
        radius = min(width, height) // 2

    # Limit to image bounds
    center_x = max(radius, min(width - radius, coords.center_xy[0]))
    center_y = max(radius, min(height - radius, coords.center_xy[1]))

    cv2.circle(mask, (center_x, center_y), radius, (255, 255, 255), -1)

    mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    x, y, w, h = cv2.boundingRect(mask)
    result = frame[y : y + h, x : x + w]
    mask = mask[y : y + h, x : x + w]
    result[mask == 0] = (255, 255, 255, 0)

    return result
