import logging
from threading import Thread

import cv2
import numpy as np

# https://github.com/ptomato/REP-instrumentation/blob/master/rep/generic/opencv_webcam.py

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Camera:
    def __init__(self) -> None:
        # TODO: choose appropriate camera resolution dynamically or downscale image
        self.available_cameras = self._get_available_cameras()
        self._cam_id = self.available_cameras[0]
        self.stopped = False
        self.frame: np.ndarray | None = None
        self.frame_rate: float = 0

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
                _ = cap.getBackendName()
            except cv2.error:
                logger.debug("Camera at /video%s seems unavailable", idx)
            else:
                cams.append(idx)
            finally:
                cap.release()

        if not cams:
            raise RuntimeError(
                "No accessible camera found! Is some other application using the it?"
            )

        return cams

    def start(self, cam_id: int | None = None) -> None:
        self._cam_id = cam_id or self.available_cameras[0]
        self._capture = cv2.VideoCapture(self._cam_id, cv2.CAP_V4L2)

        # Set compressed codec for way better performance:
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # type: ignore # FP

        # Max resolution & FPS. OpenCV automatically selects lower one, if needed:
        self._capture.set(cv2.CAP_PROP_FPS, 60)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        Thread(target=self.update, args=()).start()

    def stop(self) -> None:
        self.stopped = True

    def get_frame(self) -> np.ndarray | None:
        return self.frame

    def update(self) -> None:
        clock_period = 1 / cv2.getTickFrequency()
        last_tick = cv2.getTickCount()
        while True:
            if self.stopped:
                break

            self.grabbed, self.frame = self._capture.read()

            tick = cv2.getTickCount()
            fps = 1 / ((tick - last_tick) * clock_period)
            last_tick = tick

            cv2.putText(
                self.frame,
                f"FPS out: {fps:5.1f}",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        self._capture.release()
