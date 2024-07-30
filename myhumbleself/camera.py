import logging
from pathlib import Path
from threading import Thread
from time import sleep

import cv2
import numpy as np

# https://github.com/ptomato/REP-instrumentation/blob/master/rep/generic/opencv_webcam.py

logger = logging.getLogger(__name__)

PLACEHOLDER_CAM_ID = 99


class PlaceholderVideoCapture:
    def __init__(self) -> None:
        self._placeholder_image = cv2.imread(
            str(Path(__file__).parent / "resources" / "placeholder.jpg")
        )

    def read(self) -> tuple[bool, np.ndarray]:
        sleep(0.01)
        return True, self._placeholder_image.copy()

    def release(self) -> None:
        pass

    def isOpened(self) -> bool:  # noqa: N802 # camelCase used by OpenCV
        return True

    @staticmethod
    def set(prop_id: int, value: int) -> None:
        pass


class Camera:
    def __init__(self) -> None:
        # TODO: choose appropriate camera resolution dynamically or downscale image
        self.available_cameras = self._get_available_cameras()
        self._cam_id: int
        self._capture: cv2.VideoCapture | PlaceholderVideoCapture | None = None
        self.frame: np.ndarray | None = None
        self.fps: list[float] = [0]
        self.fps_window = 100

    def _get_video_capture(
        self, cam_id: int
    ) -> cv2.VideoCapture | PlaceholderVideoCapture:
        if cam_id == PLACEHOLDER_CAM_ID:
            return PlaceholderVideoCapture()

        return cv2.VideoCapture(cam_id, cv2.CAP_V4L2)

    def _get_available_cameras(self) -> dict[int, np.ndarray]:
        """Heuristically determine available video inputs.

        OpenCV does not provide a reliable way to list available cameras. Therefore,
        we try to open /video0 - /video9 and check if we can read some metadata. If we
        can't we deduce that the camera is not available, but it might just be already
        in use. We also won't detect inputs with a higher index.

        Returns:
            IDs of available cameras
        """
        cams = {}
        cam_ids_to_try = [*range(10), PLACEHOLDER_CAM_ID]

        for idx in cam_ids_to_try:
            cap = self._get_video_capture(idx)
            try:
                read_status, frame = cap.read()
            except cv2.error:
                logger.debug("Camera at /video%s seems unavailable (cv2.error)", idx)
            else:
                if read_status:
                    logger.debug("Camera at /video%s is available", idx)
                    cams[idx] = frame
                else:
                    logger.debug("Camera at /video%s seems unavailable (no frame)", idx)
            finally:
                cap.release()

        return cams

    def start(self, cam_id: int) -> None:
        first_cam_id = next(iter(self.available_cameras), None)
        cam_is_available = cam_id in self.available_cameras

        if cam_is_available:
            self._cam_id = cam_id
        elif not cam_is_available and first_cam_id is not None:
            logger.warning("Camera %s not available. Fallback to first one.", cam_id)
            self._cam_id = first_cam_id
        else:
            logger.error("No camera accessible! Is another application using it?")
            self._cam_id = 99

        if self._cam_id == PLACEHOLDER_CAM_ID:
            logger.info("Using placeholder camera")
            self._capture = PlaceholderVideoCapture()
        else:
            self._capture = cv2.VideoCapture(self._cam_id, cv2.CAP_V4L2)

        # Set compressed codec for way better performance:
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # type: ignore # FP

        Thread(target=self.update, args=()).start()

    def stop(self) -> None:
        if self._capture and self._capture.isOpened():
            self._capture.release()
            sleep(0.1)

    def get_frame(self) -> np.ndarray | None:
        return self.frame

    def update(self) -> None:
        clock_period = 1 / cv2.getTickFrequency()
        last_tick = cv2.getTickCount()
        while True:
            if not self._capture or not self._capture.isOpened():
                break

            self.grabbed, self.frame = self._capture.read()

            tick = cv2.getTickCount()
            fps = 1 / ((tick - last_tick) * clock_period)
            last_tick = tick

            self.fps.append(fps)
            if len(self.fps) > self.fps_window:
                self.fps.pop(0)
