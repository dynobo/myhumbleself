import logging
from collections.abc import Callable

import cv2
import numpy as np

from myhumbleself import camera, face_detection, structures

logger = logging.getLogger(__name__)


def cache(func: Callable) -> Callable:
    """Custom approximating cache decorator for numpy arrays.

    This is intended to be used in VideoHandler._process_frame method only!

    The reason is, that often the GTK gui will call get_frame faster than the FPS of
    the camera. This will result in the same frame being processed multiple times.

    This decorator instead caches the processed frame and serves it, if the frame is
    still the same.

    To estimate, if the frame is the same, only one channel of every 100th pixel of
    the frame is taken into account. The number is a trade-off between performance and
    accuracy. Still, due to subtle movements of camera & person, and due to camera
    noise, the chance of a false positive seem low.

    Rough tests show a speedup of 2x (cache is hit ~once per frame), but it highly
    depends on camera FPS and system.

    (functools.lru_cache does not work with numpy arrays, as they are not hashable.
    hashing the whole image is too slow, anyway.)
    """
    cache.id = 0  # type: ignore [attr-defined]
    cache.content = None  # type: ignore [attr-defined]

    def inner(cls, ary: np.ndarray) -> np.ndarray:  # noqa: ANN001
        new_cache_id = ary[::100, ::100, 1].data.tobytes()  # type: ignore [attr-defined]
        if new_cache_id != cache.id:  # type: ignore [attr-defined]
            cache.id = new_cache_id  # type: ignore [attr-defined]
            cache.content = func(cls, ary)  # type: ignore [attr-defined]
        return cache.content  # type: ignore [attr-defined]

    return inner


class VideoHandler:
    def __init__(  # noqa:PLR0913
        self,
        cam_id: int,
        shape_png_buffer: bytes,
        zoom_factor: float,
        offset_x: int,
        offset_y: int,
        follow_face: bool,
    ) -> None:
        self._shape_mask = cv2.imdecode(
            np.frombuffer(shape_png_buffer, dtype=np.uint8), cv2.IMREAD_GRAYSCALE
        )
        # Face detection area. Cached here to allow the use case, where face detection
        # is only used once to get the face, but then disabled to avoid tracking during
        # presentation.
        self._face_area: structures.Rect | None = None
        # User adjusted area, with padding, offset and zoom. Cached to allow allow
        # detection, if we are already at the edge of the image, to disable buttons
        self._focus_area: structures.Rect | None = None

        self._cam_id: int = cam_id
        self._camera = camera.Camera()
        self._face_detection = face_detection.FaceDetection()

        self.zoom_factor = zoom_factor
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.follow_face = follow_face
        self.ZOOM_STEP = 0.1
        self.MOVE_STEP = 20
        self.MIN_ZOOM_FACTOR = 0.1
        self.debug_mode = False

        self.available_cameras = self._camera.available_cameras
        self.FALLBACK_CAM_ID = self._camera.FALLBACK_CAM_ID

        self._camera.start(cam_id)

    def _get_face_area_placeholder(self) -> structures.Rect:
        base_size = int(min(*self._frame_size_hw) / 1.6)
        rect = structures.Rect(
            top=(self._frame_size_hw[0] - base_size) // 2,
            left=(self._frame_size_hw[1] - base_size) // 2,
            width=base_size,
            height=base_size,
        )
        return rect

    @property
    def _frame_size_hw(self) -> tuple[int, int]:
        cam_image = self.available_cameras[self._camera.cam_id]
        return (cam_image.shape[0], cam_image.shape[1])

    def can_zoom_out(self) -> bool:
        if self._focus_area is None:
            return False
        return (
            self._focus_area.width < self._frame_size_hw[1]
            and self._focus_area.height < self._frame_size_hw[0]
        )

    def can_zoom_in(self) -> bool:
        return self.zoom_factor > self.MIN_ZOOM_FACTOR + self.ZOOM_STEP

    def can_move_left(self) -> bool:
        # Note: those methods are implemented for each direction individually, because
        # it is faster to call different methods than using one method with conditions.
        if self._focus_area is None:
            return False
        return self._focus_area.left > 0

    def can_move_right(self) -> bool:
        if self._focus_area is None:
            return False
        return self._focus_area.right < self._frame_size_hw[1]

    def can_move_up(self) -> bool:
        if self._focus_area is None:
            return False
        return self._focus_area.top > 0

    def can_move_down(self) -> bool:
        if self._focus_area is None:
            return False
        return self._focus_area.bottom < self._frame_size_hw[0]

    def set_camera(self, cam_id: int | None) -> None:
        self._camera.stop()
        if cam_id is not None:
            self._camera.start(cam_id)

    def set_shape(self, png_buffer: bytes) -> None:
        self._shape_mask = cv2.imdecode(
            np.frombuffer(png_buffer, dtype=np.uint8), cv2.IMREAD_GRAYSCALE
        )

    def set_debug_mode(self, on: bool) -> None:
        self.debug_mode = on
        self._face_detection.debug_mode = on

    def reset_view(self) -> None:
        self._face_area = None
        self.offset_x = 0
        self.offset_y = 0
        self.zoom_factor = 1.0

    def _draw_bbox(
        self,
        rect: structures.Rect,
        image: np.ndarray,
        color: tuple[int, int, int],
        label: str = "",
    ) -> None:
        border_width = 2
        cv2.rectangle(
            image,
            rect.left_top,
            (rect.right - border_width, rect.bottom - border_width),
            color,
            border_width,
        )
        cv2.putText(
            image,
            f"{label} {rect}",
            (rect.left + 10, rect.top + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

    def get_frame(self) -> np.ndarray:
        frame = self._camera.get_frame()
        frame = self._process_frame(frame)
        return frame

    @cache
    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process frame and return it with applied shape mask.

        Three different areas are calculated
        - face_area: Area supposed to contain face. Should be stabilized.
        - focus_area: User adjusted area, with padding, offset and zoom.
        - mask_area: Final area, restrained to image size. Should match aspect ratio of
          shape mask. At best case, this will be close to focus_area.

        Returns:
            Image ready to be displayed.
        """
        if self.follow_face:
            self._face_area = self._face_detection.get_face(frame)
        elif self._face_area is None:
            self._face_area = self._get_face_area_placeholder()

        self._focus_area = self._get_focus_area(face_area=self._face_area)
        mask_area = self._get_mask_area(
            focus_area=self._focus_area,
            image_size_hw=(frame.shape[0], frame.shape[1]),
            shape_size_hw=(self._shape_mask.shape[0], self._shape_mask.shape[1]),
        )

        if self.debug_mode:
            self._draw_bbox(
                rect=self._face_area,
                image=frame,
                color=(0, 255, 0),
                label="Face",
            )
            self._draw_bbox(
                rect=self._focus_area,
                image=frame,
                color=(255, 0, 0),
                label="Focus",
            )
            self._draw_bbox(
                rect=mask_area,
                image=frame,
                color=(0, 0, 255),
                label="Mask",
            )
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)

        frame = self._crop_to_mask(image=frame, mask=mask_area)
        frame = self._apply_shape_mask(image=frame, shape_mask=self._shape_mask)
        return frame

    def _apply_shape_mask(
        self, image: np.ndarray, shape_mask: np.ndarray
    ) -> np.ndarray:
        image_height, image_width, _ = image.shape

        # Scale grayscale shape mask
        mask = cv2.resize(
            shape_mask, (image_width, image_height), interpolation=cv2.INTER_NEAREST
        )
        # ONHOLD: Converting to RGBA is very slow, but GdkPixbuf can't handle BGR
        # and OpenCV face detection doesn't work with RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)
        image[:, :, 3] = mask
        return image

    def _crop_to_mask(self, image: np.ndarray, mask: structures.Rect) -> np.ndarray:
        mask_height, mask_width = mask.height, mask.width
        mask_x, mask_y = mask.left, mask.top

        # Crop image to bounds
        cropped_image = image[
            mask_y : mask_y + mask_height, mask_x : mask_x + mask_width
        ]

        return cropped_image

    def _get_focus_area(self, face_area: structures.Rect) -> structures.Rect:
        focus_area = face_area.copy()
        focus_area.scale(self.zoom_factor)

        padding = int(max(face_area.width, face_area.height) / 1.5 * self.zoom_factor)
        focus_area.pad(padding=padding)

        focus_area.move_by(x=self.offset_x, y=self.offset_y)
        return focus_area

    def _get_mask_area(
        self,
        focus_area: structures.Rect,
        image_size_hw: tuple[int, int],
        shape_size_hw: tuple[int, int],
    ) -> structures.Rect:
        mask_area = focus_area.copy()
        shape_height, shape_width = shape_size_hw
        aspect_ratio = shape_width / shape_height

        # Adjust aspect ratio of mask area to match shape
        if mask_area.width / mask_area.height < aspect_ratio:
            new_width = int(mask_area.height * aspect_ratio)
            width_delta = new_width - mask_area.width
            mask_area.width = new_width
            mask_area.left = mask_area.left - width_delta // 2
        else:
            new_height = int(mask_area.width / aspect_ratio)
            height_delta = new_height - mask_area.height
            mask_area.height = new_height
            mask_area.top = mask_area.top - height_delta // 2

        image_height, image_width = image_size_hw
        mask_area.stay_within(width=image_width, height=image_height)
        return mask_area
