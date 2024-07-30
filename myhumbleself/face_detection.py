import logging
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from myhumbleself.structures import Rect

# TODO: Inherit loglevel or use same logger as in app (check normcap)
logger = logging.getLogger(__name__)


class FaceDetection:
    cnn_onnx = str(
        Path(__file__).parent / "resources" / "face_detection_yunet_2023mar_int8.onnx"
    )
    haarcascade_xml = f"{cv2.data.haarcascades}haarcascade_frontalface_default.xml"  # type: ignore # FP

    def __init__(self) -> None:
        self._history: list[Rect] = []
        self._max_history_len = 20
        self.fluctuation_threshold_factor = 0.03
        self.follow_face_speed_factor = 0.2
        self._last_smoothed_geometry: Rect | None = None

        self.detector_cnn = cv2.FaceDetectorYN.create(self.cnn_onnx, "", (42, 42))
        self.detector_haarcascade = cv2.CascadeClassifier(self.haarcascade_xml)

    @staticmethod
    def _draw_bounding_box(
        image: np.ndarray, face_coords: Rect, color: tuple[int, int, int]
    ) -> None:
        cv2.rectangle(
            img=image,
            pt1=face_coords.left_top,
            pt2=face_coords.right_bottom,
            color=color,
            thickness=1,
        )

    def _detect_faces_haarcascade(self, image: np.ndarray) -> list[Rect]:
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        face_detections = self.detector_haarcascade.detectMultiScale(
            gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
        )
        faces = [
            Rect(left=f[0], top=f[1], width=f[2], height=f[3]) for f in face_detections
        ]
        return faces

    def _detect_faces_cnn(self, image: np.ndarray) -> list[Rect]:
        # Scale down to speed up and improve detection
        target_width = 250  # based on little testing
        scale_factor = target_width / max(image.shape)
        image = cv2.resize(
            image,
            None,
            fx=scale_factor,
            fy=scale_factor,
            interpolation=cv2.INTER_AREA,
        )

        # Detect faces
        self.detector_cnn.setInputSize((image.shape[1], image.shape[0]))
        face_detections = self.detector_cnn.detect(image)

        # Convert to Rect objects and scale back up
        faces: list[Rect] = []
        if face_detections[1] is not None:
            for data in face_detections[1]:
                left = int(data[0] / scale_factor)
                top = int(data[1] / scale_factor)
                width = int(data[2] / scale_factor)
                height = int(data[3] / scale_factor)
                faces.append(Rect(left=left, top=top, width=width, height=height))

        return faces

    def _detect_faces(
        self, image: np.ndarray, method: Literal["cnn", "haarcascade"] = "cnn"
    ) -> list[Rect]:
        if method == "cnn":
            return self._detect_faces_cnn(image)
        if method == "haarcascade":
            return self._detect_faces_haarcascade(image)
        raise ValueError(f"Unknown face detection method: {method}")

    @staticmethod
    def _select_largest_face(faces: list[Rect]) -> Rect | None:
        largest_face = None

        for face in faces:
            if largest_face is None or face.area > largest_face.area:
                largest_face = face

        return largest_face

    def _smooth_geometry(self) -> Rect:
        mean = np.mean([f.geometry for f in self._history], axis=0, dtype=int).tolist()
        smoothed_geometry = Rect(
            left=mean[0], top=mean[1], width=mean[2], height=mean[3]
        )

        if not self._last_smoothed_geometry:
            # No last value, nothing to smooth
            self._last_smoothed_geometry = smoothed_geometry
            return smoothed_geometry

        # Stabilize dimensions by comparing with the last mean_rect
        for attr in ["left", "top", "width", "height"]:
            new_val = getattr(smoothed_geometry, attr)
            old_val = getattr(self._last_smoothed_geometry, attr)
            if abs(new_val - old_val) <= old_val * self.fluctuation_threshold_factor:
                # Use old value to avoid fluctuations
                setattr(smoothed_geometry, attr, old_val)
            else:
                # Move into direction of the new value, but smoothly to avoid jumps
                distance = new_val - old_val
                step_size = abs(distance) * self.follow_face_speed_factor
                correction_step = int(np.sign(distance) * max(1, step_size))
                setattr(smoothed_geometry, attr, old_val + correction_step)

        self._last_smoothed_geometry = smoothed_geometry
        return smoothed_geometry

    def get_focus_area(self, image: np.ndarray) -> Rect:
        if not self._history:
            # Start with full image
            self._history.append(
                Rect(top=0, left=0, width=image.shape[1] - 1, height=image.shape[0] - 1)
            )

        faces = self._detect_faces(image, method="cnn")

        if logger.getEffectiveLevel() == logging.DEBUG:
            # Draw BBox of all detected raw faces
            for f in faces:
                self._draw_bounding_box(image, f, color=(0, 125, 0))

        face = self._select_largest_face(faces=faces)

        if face:
            self._history.append(face)
            self._history = self._history[-self._max_history_len :]

        face = self._smooth_geometry()

        if logger.getEffectiveLevel() <= logging.INFO and face:
            # Draw smoothed BBox for largest face
            self._draw_bounding_box(image, face, color=(0, 255, 0))

        return face
