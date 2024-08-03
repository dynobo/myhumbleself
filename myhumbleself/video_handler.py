import logging
from copy import deepcopy

import cv2
import numpy as np

from myhumbleself import camera, face_detection, structures

logger = logging.getLogger(__name__)


def _convert_colorspace(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)


class VideoHandler:
    def __init__(
        self,
        face_detection_model: face_detection.DetectionModels,
        zoom_factor: float,
        offset_x: int,
        offset_y: int,
        follow_face: bool,
    ) -> None:
        self.frame: np.ndarray | None = None
        self.frame_size: tuple[int, int] | None = None
        self.shape: np.ndarray | None = None

        self.face_detection = face_detection.FaceDetection(method=face_detection_model)
        self._camera = camera.Camera()

        self.zoom_factor = zoom_factor
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.follow_face = follow_face
        self.ZOOM_STEP = 0.1
        self.MOVE_STEP = 20

        self.focus_area: structures.Rect | None = None
        self.face_area: structures.Rect | None = None

        self.debug_mode = False

    def _get_padding(self) -> int:
        if not self.focus_area:
            return 0

        base_pad = (
            max(self.focus_area.width, self.focus_area.height) / 3
            if self.focus_area
            else 0
        )
        padding = int(-base_pad + base_pad / self.zoom_factor / 0.5)

        return padding

    @property
    def can_zoom_out(self) -> bool:
        return False

    @property
    def can_move_left(self) -> bool:
        if not self.focus_area:
            return True

        next_left = (
            self.focus_area.left - self._get_padding() + self.offset_x - self.MOVE_STEP
        )
        return next_left > 0

    @property
    def can_move_right(self) -> bool:
        if self.frame is None:
            return False

        if not self.focus_area:
            return True

        next_right = (
            self.focus_area.right + self._get_padding() + self.offset_x + self.MOVE_STEP
        )
        return next_right < self.frame.shape[1]

    @property
    def can_move_up(self) -> bool:
        if not self.focus_area:
            return True

        next_top = (
            self.focus_area.top - self._get_padding() + self.offset_y - self.MOVE_STEP
        )
        return next_top > 0

    @property
    def can_move_down(self) -> bool:
        if self.frame is None:
            return False

        if not self.focus_area:
            return True

        next_top = (
            self.focus_area.bottom
            + self._get_padding()
            + self.offset_y
            + self.MOVE_STEP
        )
        return next_top > self.frame.shape[0]

    def set_camera(self, cam_id: int | None) -> None:
        self._camera.stop()
        if cam_id is not None:
            self._camera.start(cam_id)

    def set_shape(self, png_buffer: bytes) -> None:
        self.shape = cv2.imdecode(
            np.frombuffer(png_buffer, dtype=np.uint8), cv2.IMREAD_COLOR
        )

    def set_debug_mode(self, on: bool) -> None:
        self.debug_mode = on
        self.face_detection.debug_mode = on

    def get_available_cameras(self) -> dict[int, np.ndarray]:
        # Show test image in camera menu only in debug mode:
        cams = deepcopy(self._camera.available_cameras)
        if not self.debug_mode:
            del cams[self._camera.FALLBACK_CAM_ID]
        return cams

    def _get_focus_area(
        self, face_area: structures.Rect | None, frame_size: tuple[int, int]
    ) -> structures.Rect:
        if face_area is not None:
            focus_area = face_area
        else:
            base_size = min(*frame_size) // 3
            focus_area = structures.Rect(
                top=(frame_size[0] - base_size) // 2,
                left=(frame_size[1] - base_size) // 2,
                width=base_size,
                height=base_size,
            )

        return focus_area

    def get_frame(self) -> np.ndarray | None:
        self.frame = self._camera.get_frame()

        if self.frame is None:
            logger.debug("Frame is None, skip processing.")
            return None
        if self.shape is None:
            logger.debug("Shape is None, skip processing.")
            return None

        if self.follow_face:
            self.face_area = self.face_detection.get_face(self.frame)

        frame_size = (self.frame.shape[0], self.frame.shape[1])
        self.focus_area = self._get_focus_area(
            face_area=self.face_area, frame_size=frame_size
        )

        image = _convert_colorspace(self.frame)

        image = self._crop_to_shape(
            image=image,
            shape=self.shape,
            focus_area=self.focus_area,
        )
        return image

    def _crop_to_shape(
        self,
        image: np.ndarray,
        shape: np.ndarray,
        focus_area: structures.Rect,
    ) -> np.ndarray:
        shape_height, shape_width, _ = shape.shape
        image_height, image_width, _ = image.shape

        padding = self._get_padding()

        # Sanitize focus area to stay within image bounds
        area = structures.Rect(
            top=max(0, focus_area.top - padding + self.offset_y),
            left=max(0, focus_area.left - padding + self.offset_x),
            width=min(image_width, focus_area.width + padding * 2),
            height=min(image_height, focus_area.height + padding * 2),
        )

        # Calculate scale for shape to contain face
        scale_y = area.height / shape_height
        scale_x = area.width / shape_width
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
        mask_x = area.left - (mask_width - area.width) // 2
        mask_y = area.top - (mask_height - area.height) // 2

        # Sanitize mask position to stay within image bounds
        mask_x = max(0, min(mask_x, image_width - mask_width))
        mask_y = max(0, min(mask_y, image_height - mask_height))

        if self.debug_mode:
            cv2.rectangle(
                image,
                (mask_x, mask_y),
                (mask_x + mask_width, mask_y + mask_height),
                (0, 0, 255, 255),
                2,
            )
            cv2.putText(
                image,
                "Crop",
                (mask_x + 10, mask_y + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255, 255),
                2,
            )
            return image

        # Crop image to bounds
        cropped_image = image[
            mask_y : mask_y + mask_height, mask_x : mask_x + mask_width
        ]

        # Apply alpha channel from mask onto image
        # TODO: Check why semi-transparent pixels do not work
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        cropped_image[:, :, 3] = mask
        return cropped_image
