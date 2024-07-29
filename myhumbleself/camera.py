import logging
from threading import Thread
from time import sleep

import cv2
import numpy as np

# https://github.com/ptomato/REP-instrumentation/blob/master/rep/generic/opencv_webcam.py

logger = logging.getLogger(__name__)


class Camera:
    def __init__(self) -> None:
        # TODO: choose appropriate camera resolution dynamically or downscale image
        self.available_cameras = self._get_available_cameras()
        self._cam_id: int | None = None
        self._capture: cv2.VideoCapture | None = None
        self.frame: np.ndarray | None = None
        self.fps: list[float] = [0]
        self.fps_window = 100
        # TODO: Use placeholder image
        self.placeholder_image = np.ones((480, 640, 3), np.uint8)

    def _get_available_cameras(self) -> list[int]:
        """Heuristically determine available video inputs.

        OpenCV does not provide a reliable way to list available cameras. Therefore,
        we try to open /video0 - /video9 and check if we can read some metadata. If we
        can't we deduce that the camera is not available, but it might just be already
        in use. We also won't detect inputs with a higher index.

        Returns:
            IDs of available cameras
        """
        cams = []
        for idx in range(10):
            cap = cv2.VideoCapture(idx)
            try:
                # TODO: Grab frame and use for input source dropdown
                _ = cap.getBackendName()
            except cv2.error:
                logger.debug("Camera at /video%s seems unavailable", idx)
            else:
                cams.append(idx)
            finally:
                cap.release()

        return cams

    def start(self, cam_id: int | None = None) -> None:
        if not self.available_cameras:
            logger.error("No camera accessible! Is another application using the it?")
            logger.info("Loading placeholder image.")
            self._capture = None
            self.frame = self.placeholder_image
            return

        if cam_id in self.available_cameras:
            self._cam_id = cam_id
        elif not cam_id:
            logger.info("No camera specified. Fallback to first one.")
            self._cam_id = self.available_cameras[0]
        else:
            logger.warning("Camera %s not available. Fallback to first one.", cam_id)
            self._cam_id = self.available_cameras[0]

        self._capture = cv2.VideoCapture(self._cam_id, cv2.CAP_V4L2)

        # Set compressed codec for way better performance:
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # type: ignore # FP

        # Max resolution & FPS. OpenCV automatically selects lower one, if needed:
        self._capture.set(cv2.CAP_PROP_FPS, 60)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

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
                self.frame = self.placeholder_image
                break

            self.grabbed, self.frame = self._capture.read()

            tick = cv2.getTickCount()
            fps = 1 / ((tick - last_tick) * clock_period)
            last_tick = tick

            self.fps.append(fps)
            if len(self.fps) > self.fps_window:
                self.fps.pop(0)

        if self._capture:
            self._capture.release()
