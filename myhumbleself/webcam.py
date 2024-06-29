from threading import Thread

import cv2
import numpy as np

# https://github.com/ptomato/REP-instrumentation/blob/master/rep/generic/opencv_webcam.py


class Webcam:
    def __init__(self) -> None:
        # TODO: choose appropriate camera resolution dynamically or downscale image
        self._cam_id = 0
        self.stopped = False
        self.frame: np.ndarray | None = None
        self.frame_rate: float = 0

    def start(self) -> None:
        self._capture = cv2.VideoCapture(self._cam_id, cv2.CAP_V4L2)
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
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
                f"FPS Webcam Output: {fps:5.2f}",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        self._capture.release()
