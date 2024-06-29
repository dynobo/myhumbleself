from pathlib import Path
from typing import cast

import cv2
import gi
import numpy as np

from myhumbleself import face_detection, processing
from myhumbleself.webcam import Webcam

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

CSS_TRANSPARENT = """
window.background {
    background: unset;
}
"""

RESOURCE_PATH = Path(__file__).parent / "resources"


@Gtk.Template(filename=f"{RESOURCE_PATH}/window.ui")
class SeeMeWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "main_window"

    picture = cast(Gtk.Picture, Gtk.Template.Child())

    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app)
        self.init_ui()
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext().add_provider_for_display(
            self.get_display(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.face_detection = face_detection.FaceDetection()
        self.connect("close-request", self.on_close_request)
        self.webcam = Webcam()
        self.webcam.start()
        self.last_tick_processing = 0.0
        self.clock_period = 1 / cv2.getTickFrequency()

    def init_ui(self) -> None:
        # self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.add_tick_callback(self.draw_image)

        evk = Gtk.GestureClick()
        evk.connect("pressed", self.on_picture_clicked)
        self.picture.add_controller(evk)

    def process_webcam_image(self) -> np.ndarray | None:
        tick_before = cv2.getTickCount()
        image = self.webcam.get_frame()
        if image is None:
            return None
        # image = cv2.imread(str((Path(__file__).parent / "image.jpg").resolve()))
        coords = self.face_detection.get_focus_area(image)
        image = processing.convert_colorspace(image)
        image = processing.crop_circle(frame=image, coords=coords)
        tick_after = cv2.getTickCount()
        fps = 1 / ((tick_after - tick_before) * self.clock_period)
        cv2.putText(
            image,
            f"FPS Postprocessing: {fps:5.2f}",
            (10, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
        return image

    def on_picture_clicked(
        self, event: Gtk.GestureClick, in_press: int, x: float, y: float
    ) -> None:
        self.set_decorated(not self.get_decorated())
        self.css_provider.load_from_string(
            "" if self.get_decorated() else CSS_TRANSPARENT
        )
        self.picture.set_margin_top(0 if self.get_decorated() else 35)

    def draw_image(self, widget: Gtk.Widget, idle: Gdk.FrameClock) -> bool:
        image = self.process_webcam_image()

        if image is None:
            return True

        height, width, channels = image.shape
        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            image.tobytes(),
            GdkPixbuf.Colorspace.RGB,
            True,
            8,
            width,
            height,
            width * channels,
        )
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        widget.set_paintable(texture)
        return True

    def on_close_request(self, widget: Gtk.Widget) -> bool:
        self.webcam.stop()
        return False


def on_activate(app: Gtk.Application) -> None:
    win = SeeMeWindow(app=app)
    win.present()


def main() -> None:
    app = Gtk.Application(application_id="com.example.App")
    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
