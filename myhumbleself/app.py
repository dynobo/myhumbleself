import logging
import os
from pathlib import Path

# Hide warnings show during search for cameras
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"

import cv2
import gi
import numpy as np

from myhumbleself import config, face_detection, processing
from myhumbleself.camera import Camera

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

RESOURCE_PATH = Path(__file__).parent / "resources"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MyHumbleSelf(Gtk.Application):
    def __init__(self, application_id: str) -> None:
        super().__init__(application_id=application_id)
        self.win: Gtk.ApplicationWindow
        self.config = config.load()
        self.face_detection = face_detection.FaceDetection()
        self.camera = Camera()
        self.camera.start(cam_id=None)
        self.clock_period = 1 / cv2.getTickFrequency()
        self.shape: np.ndarray | None = None

        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

    def on_activate(self, app: Gtk.Application) -> None:
        builder = Gtk.Builder()
        builder.add_from_file(f"{RESOURCE_PATH}/window.ui")

        self.win = builder.get_object("main_window")
        self.win.set_application(self)

        self.picture = builder.get_object("picture")
        self.picture.add_tick_callback(self.draw_image)
        evk = Gtk.GestureClick()
        evk.connect("pressed", self.on_picture_clicked)
        self.picture.add_controller(evk)

        self.titlebar = builder.get_object("titlebar")

        self.css_provider = builder.get_object("css_provider")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.css_provider.load_from_string((RESOURCE_PATH / "style.css").read_text())

        camera_list = Gtk.StringList()
        for cam in self.camera.available_cameras:
            camera_list.append(f"/dev/video{cam}")
        # TODO: Remove
        camera_list.append("/dev/video42")
        self.camera_combobox = builder.get_object("camera_dropdown")
        self.camera_combobox.props.model = camera_list

        self.shape_box = builder.get_object("shape_box")
        self.first_button = None
        for png in sorted((RESOURCE_PATH / "shapes").glob("*.png")):
            icon = Gtk.Image.new_from_file(str(png))
            button = Gtk.ToggleButton()
            button.set_size_request(48, 48)
            button.set_child(icon)
            button.set_has_frame(False)
            button.connect("toggled", self.on_shape_toggled, png)

            # Activate stored shape:
            if png == RESOURCE_PATH / "shapes" / self.config["main"].get("shape"):
                button.set_active(True)

            if self.first_button is None:
                self.first_button = button
            else:
                button.set_group(self.first_button)
            self.shape_box.append(button)

        self.center_button = builder.get_object("center_button")
        self.center_button.connect("clicked", self.on_center_clicked)

        self.left_button = builder.get_object("left_button")
        self.left_button.connect("clicked", self.on_move_clicked, 1, 0)

        self.right_button = builder.get_object("right_button")
        self.right_button.connect("clicked", self.on_move_clicked, -1, 0)

        self.up_button = builder.get_object("up_button")
        self.up_button.connect("clicked", self.on_move_clicked, 0, 1)

        self.down_button = builder.get_object("down_button")
        self.down_button.connect("clicked", self.on_move_clicked, 0, -1)

        self.zoom_scale = builder.get_object("zoom_scale")
        self.zoom_scale.set_value(self.config["main"].getint("zoom_factor", 100))
        self.zoom_scale.connect("value-changed", self.on_zoom_changed)

        self.win.present()

    def on_shape_toggled(self, button: Gtk.ToggleButton, shape_png: Path) -> None:
        if not button.get_active():
            return

        self.shape = None if "99_" in shape_png.name else cv2.imread(str(shape_png))
        self.config.set_persistent("shape", shape_png.name)

    def on_center_clicked(self, button: Gtk.Button) -> None:
        self.config.set_persistent("offset_x", 0)
        self.config.set_persistent("offset_y", 0)

    def on_move_clicked(self, button: Gtk.Button, factor_x: int, factor_y: int) -> None:
        step_size = 20
        self.config.set_persistent(
            "offset_x",
            self.config["main"].getint("offset_x", 0) + factor_x * step_size,
        )
        self.config.set_persistent(
            "offset_y",
            self.config["main"].getint("offset_y", 0) + factor_y * step_size,
        )

    def on_zoom_changed(self, scale: Gtk.Scale) -> None:
        self.config.set_persistent("zoom_factor", int(scale.get_value()))

    def on_shutdown(self, app: Gtk.Application) -> None:
        self.camera.stop()

    def get_processed_image(self) -> np.ndarray | None:
        tick_before = cv2.getTickCount()
        image = self.camera.get_frame()
        if image is None:
            return None

        coords = self.face_detection.get_focus_area(image)

        image = processing.convert_colorspace(image)
        if self.shape is not None:
            image = processing.crop_to_shape(
                image=image,
                shape=self.shape,
                face=coords,
                zoom_factor=self.config["main"].getint("zoom_factor", 100) / 100,
                offset_xy=(
                    self.config["main"].getint("offset_x", 0),
                    self.config["main"].getint("offset_y", 0),
                ),
            )

        if logger.getEffectiveLevel() == logging.DEBUG:
            tick_after = cv2.getTickCount()
            fps = 1 / ((tick_after - tick_before) * self.clock_period)
            cv2.putText(
                image,
                f"FPS post: {fps:5.1f}",
                (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0, 255),
                2,
                cv2.LINE_AA,
            )

        return image

    def on_picture_clicked(
        self, event: Gtk.GestureClick, in_press: int, x: float, y: float
    ) -> None:
        is_decorated = not self.win.get_decorated()
        titlebar_height = self.win.get_titlebar().get_height()
        css_classes = self.win.get_css_classes()
        if is_decorated:
            css_classes.remove("transparent")
        else:
            css_classes.append("transparent")

        self.win.set_css_classes(css_classes)

        self.win.set_decorated(is_decorated)
        self.picture.set_margin_top(0 if is_decorated else titlebar_height)

    def draw_image(self, widget: Gtk.Widget, idle: Gdk.FrameClock) -> bool:
        image = self.get_processed_image()

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


def main() -> None:
    app = MyHumbleSelf(application_id="com.example.App")
    app.run(None)


if __name__ == "__main__":
    main()
