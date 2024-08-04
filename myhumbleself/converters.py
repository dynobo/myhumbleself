import tempfile

import cv2
import gi
import numpy as np

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def cv2_image_to_gtk_image(cv2_image: np.ndarray) -> Gtk.Image:
    """Create Gtk.Image from cv2 image via a temporary file.

    Args:
        cv2_image: OpenCV input image.

    Returns:
        GTK image widget.
    """
    with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_file:
        temp_image = cv2.resize(cv2_image, fx=0.20, fy=0.20, dsize=(0, 0))
        cv2.imwrite(temp_file.name, temp_image)
        image = Gtk.Image.new_from_file(temp_file.name)
    return image
