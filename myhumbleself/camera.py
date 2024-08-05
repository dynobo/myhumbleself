import logging
import time
from pathlib import Path
from threading import Thread
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class DemoVideoCapture:
    def __init__(self) -> None:
        self._demo_video_file = str(Path(__file__).parent / "resources" / "demo.mp4")
        self.capture = cv2.VideoCapture(self._demo_video_file)
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.last_frame = time.perf_counter()

    def read(self) -> tuple[bool, np.ndarray]:
        while self.last_frame + 1 / self.fps > time.perf_counter():
            pass
        self.last_frame = time.perf_counter()
        return_code, frame = self.capture.read()
        if not return_code:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return_code, frame = self.capture.read()
        return (return_code, frame)

    def release(self) -> None:
        pass

    def isOpened(self) -> bool:  # noqa: N802 # camelCase used by OpenCV
        return True

    def set(self, _: Any, __: Any) -> int:  # noqa: ANN401
        return 0


class Camera:
    def __init__(self) -> None:
        self.FALLBACK_CAM_ID = 99
        self.available_cameras = self._get_available_cameras()
        self.cam_id: int
        self._capture: cv2.VideoCapture | DemoVideoCapture | None = None
        self.frame: np.ndarray = np.zeros((1080, 1920, 3), np.uint8)
        self.fps: list[float] = [0]
        self.fps_window = 100
        self.stop_video_thread = False
        self.video_thread: Thread | None = None

    def _get_video_capture(self, cam_id: int) -> cv2.VideoCapture | DemoVideoCapture:
        if cam_id == self.FALLBACK_CAM_ID:
            return DemoVideoCapture()

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
        cam_ids_to_try = [*range(10), self.FALLBACK_CAM_ID]

        for idx in cam_ids_to_try:
            cap = self._get_video_capture(idx)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # type: ignore # FP
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)  # type: ignore # FP
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

        logger.info("Available cameras: %s", cams.keys())
        return cams

    def start(self, cam_id: int) -> None:
        if self.video_thread is not None:
            raise ValueError("Camera needs to be stopped before starting!")

        first_cam_id = next(iter(self.available_cameras), None)
        cam_is_available = cam_id in self.available_cameras

        if cam_is_available:
            logger.info("Using camera %s.", cam_id)
            self.cam_id = cam_id
        elif not cam_is_available and first_cam_id is not None:
            logger.warning("Camera %s not available. Fallback to first one.", cam_id)
            self.cam_id = first_cam_id
        else:
            logger.error("No camera accessible! Is another application using it?")
            self.cam_id = 99

        if self.cam_id == self.FALLBACK_CAM_ID:
            logger.info("Using demo video camera.")
            self._capture = DemoVideoCapture()
        else:
            self._capture = cv2.VideoCapture(self.cam_id, cv2.CAP_V4L2)

        # Set compressed codec for way better performance:
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # type: ignore # FP

        # Max resolution & FPS. OpenCV automatically selects lower one, if needed:
        self._capture.set(cv2.CAP_PROP_FPS, 60)  # type: ignore # FP
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # type: ignore # FP
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)  # type: ignore # FP

        self.stop_video_thread = False
        self.video_thread = Thread(target=self.update, args=())
        self.video_thread.start()

    def stop(self) -> None:
        if self.video_thread is None:
            return

        self.stop_video_thread = True
        self.video_thread.join()

        if self._capture and self._capture.isOpened():
            self._capture.release()

        self.video_thread = None

    def get_frame(self) -> np.ndarray:
        return self.frame

    def update(self) -> None:
        logger.info("Camera thread started.")
        clock_period = 1 / cv2.getTickFrequency()
        last_tick = cv2.getTickCount()
        while not self.stop_video_thread:
            try:
                if not self._capture:
                    logger.error("Capture device not ready.")
                    break

                _, self.frame = self._capture.read()

                tick = cv2.getTickCount()
                fps = 1 / ((tick - last_tick) * clock_period)
                last_tick = tick

                self.fps.append(fps)
                if len(self.fps) > self.fps_window:
                    self.fps.pop(0)

            except cv2.error:  # type: ignore # FP
                logger.exception("Error in camera update.")
                break

        logger.info("Camera thread stopped.")
