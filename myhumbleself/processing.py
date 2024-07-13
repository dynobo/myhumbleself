import logging

import cv2
import numpy as np

from myhumbleself.face_detection import Rect

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def convert_colorspace(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)


def crop_to_shape(
    image: np.ndarray,
    shape: np.ndarray,
    face: Rect,
    zoom_factor: float = 1,
    offset_xy: tuple[int, int] = (0, 0),
) -> np.ndarray:
    shape_height, shape_width, _ = shape.shape
    image_height, image_width, _ = image.shape

    # Add padding around face rect (for zoom effect)
    base_pad = max(face.width, face.height) / 3
    padding = int(-base_pad + base_pad / zoom_factor / 0.5)
    face = Rect(
        top=max(0, face.top - padding + offset_xy[1]),
        left=max(0, face.left - padding + offset_xy[0]),
        width=min(image_width, face.width + padding * 2),
        height=min(image_height, face.height + padding * 2),
    )

    # Calculate scale for shape to contain face
    scale_y = face.height / shape_height
    scale_x = face.width / shape_width
    scale = max(scale_y, scale_x)

    # Sanitize scale to stay within image bounds
    if shape_height * scale > image_height:
        scale = image_height / shape_height
    if shape_width * scale > image_width:
        scale = image_width / shape_width

    # Scale shape
    mask = cv2.resize(shape, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    mask_height, mask_width, _ = mask.shape

    # Calculate mask position
    mask_x = face.left - (mask_width - face.width) // 2
    mask_y = face.top - (mask_height - face.height) // 2

    # Sanitize mask position to stay within image bounds
    mask_x = max(0, min(mask_x, image_width - mask_width))
    mask_y = max(0, min(mask_y, image_height - mask_height))

    # Crop image to  bounds
    cropped_image = image[mask_y : mask_y + mask_height, mask_x : mask_x + mask_width]

    # Apply alpha channel from mask onto image
    # TODO: Check why semi-transparent pixels do not work
    mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    cropped_image[:, :, 3] = mask
    return cropped_image
