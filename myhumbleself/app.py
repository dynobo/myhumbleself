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
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk  # noqa: E402

RESOURCE_PATH = Path(__file__).parent / "resources"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# TODO: Support GTK4.6 (in window.ui)
# TODO: Support Camera inputs
# TODO: replace no-zoom-char in slider with something more common


class MyHumbleSelf(Gtk.Application):
    def __init__(self, application_id: str) -> None:
        super().__init__(application_id=application_id)
        self.win: Gtk.ApplicationWindow
        self.resource: Gio.Resource
        self.config = config.load()
        self.face_detection = face_detection.FaceDetection()
        self.camera = Camera()
        self.camera.start(cam_id=None)
        self.clock_period: float = 1 / cv2.getTickFrequency()
        self.shape: np.ndarray | None = None
        self.in_presentation_mode = False
        self.fps: list[float] = [0]
        self.fps_window = 50
        self.face_coords = face_detection.Rect(0, 0, 1080, 1920)

        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

    # TODO: split into smaller functions
    def on_activate(self, app: Gtk.Application) -> None:  # noqa: PLR0915
        self.resource = Gio.resource_load(
            str(Path(__file__).parent / "resources" / "myhumbleself.gresource")
        )
        Gio.Resource._register(self.resource)
        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/dynobo/myhumbleself/window.ui")

        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        theme.add_resource_path("/com/github/dynobo/myhumbleself/icons")

        self.win = builder.get_object("main_window")
        self.win.set_application(self)

        # TODO: Make picture centered and click through transparent areas
        # TODO: Show overlay on hover to indicate hide/show controls
        # TODO: Show pointer cursor only on overlay
        self.picture = builder.get_object("picture")
        self.picture.add_tick_callback(self.draw_image)

        evk = Gtk.GestureClick()
        evk.connect("pressed", self.on_picture_clicked)
        self.picture.add_controller(evk)

        evk2 = Gtk.EventControllerMotion()
        evk2.connect("leave", self.on_picture_leave)
        evk2.connect("motion", self.on_picture_enter)
        self.picture.add_controller(evk2)

        self.toggle_controls_button = builder.get_object("toggle_controls_button")
        self.toggle_controls_button.set_cursor_from_name("pointer")

        self.titlebar = builder.get_object("titlebar")

        self.follow_face_button = builder.get_object("follow_face_button")
        self.follow_face_button.set_icon_name("follow-face-symbolic")
        self.follow_face_button.connect("clicked", self.on_follow_face_clicked)
        self.follow_face_button.set_active(
            self.config["main"].getboolean("follow_face")
        )

        self.css_provider = builder.get_object("css_provider")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.css_provider.load_from_resource(
            "/com/github/dynobo/myhumbleself/style.css"
        )

        camera_list = Gtk.StringList()
        for cam in self.camera.available_cameras:
            camera_list.append(f"/dev/video{cam}")
        # TODO: Remove
        camera_list.append("/dev/video42")
        self.camera_combobox = builder.get_object("camera_dropdown")
        self.camera_combobox.props.model = camera_list

        self.shape_box = builder.get_object("shape_box")
        self.first_button = None
        for shape in self.resource.enumerate_children(
            "/com/github/dynobo/myhumbleself/shapes", Gio.ResourceLookupFlags.NONE
        ):
            button = Gtk.ToggleButton()
            button.set_size_request(32, 32)
            button.set_icon_name(f"{shape[:-4]}-symbolic")
            button.set_has_frame(False)
            button.connect("toggled", self.on_shape_toggled, shape)
            button.set_css_classes([*button.get_css_classes(), "shape-button"])
            # Activate stored shape:
            if shape == self.config["main"].get("shape"):
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

    def on_follow_face_clicked(self, button: Gtk.ToggleButton) -> None:
        self.config.set_persistent("follow_face", button.get_active())

    def on_shape_toggled(self, button: Gtk.ToggleButton, shape: str) -> None:
        if not button.get_active():
            return

        if "99" in shape:
            self.shape = None
        else:
            shape_png = self.resource.lookup_data(
                f"/com/github/dynobo/myhumbleself/shapes/{shape}",
                Gio.ResourceLookupFlags.NONE,
            ).get_data()
            self.shape = cv2.imdecode(
                np.frombuffer(shape_png, dtype=np.uint8), cv2.IMREAD_COLOR
            )

        self.config.set_persistent("shape", shape)

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
        image = self.camera.get_frame()
        if image is None:
            return None

        if self.config["main"].getboolean("follow_face"):
            face_coords = self.face_detection.get_focus_area(image)
        else:
            base_size = min(*image.shape[:2]) // 3
            face_coords = face_detection.Rect(
                top=(image.shape[0] - base_size) // 2,
                left=(image.shape[1] - base_size) // 2,
                width=base_size,
                height=base_size,
            )

        image = processing.convert_colorspace(image)
        if self.shape is not None:
            image = processing.crop_to_shape(
                image=image,
                shape=self.shape,
                face=face_coords,
                zoom_factor=self.config["main"].getint("zoom_factor", 100) / 100,
                offset_xy=(
                    self.config["main"].getint("offset_x", 0),
                    self.config["main"].getint("offset_y", 0),
                ),
            )
        return image

    def draw_fps(self, image: np.ndarray) -> np.ndarray:
        font_scale = max(*image.shape) / 500
        offset_x = int(font_scale * 10)
        offset_y = int(font_scale * 20)
        cv2.putText(
            img=image,
            text=f"FPS in: {np.mean(self.camera.fps):5.1f}",
            org=(offset_x, offset_y),
            fontFace=cv2.FONT_HERSHEY_PLAIN,
            fontScale=font_scale,
            color=(0, 255, 0, 255),
            thickness=2,
            lineType=cv2.LINE_AA,
        )
        cv2.putText(
            img=image,
            text=f"FPS out: {self.fps:5.1f}",
            org=(offset_x, offset_y * 2),
            fontFace=cv2.FONT_HERSHEY_PLAIN,
            fontScale=font_scale,
            color=(0, 255, 0, 255),
            thickness=2,
            lineType=cv2.LINE_AA,
        )
        return image

    def on_picture_clicked(
        self, event: Gtk.GestureClick, n_press: int, x: float, y: float
    ) -> None:
        double_clicks = 2
        if n_press == double_clicks:
            self.toggle_presentation_mode()

    def on_picture_enter(
        self, event: Gtk.EventControllerMotion, x: float, y: float
    ) -> None:
        self.toggle_controls_button.set_visible(True)

    def on_picture_leave(
        self,
        event: Gtk.EventControllerMotion,
    ) -> None:
        self.toggle_controls_button.set_visible(False)

    def toggle_presentation_mode(self) -> None:
        self.in_presentation_mode = not self.in_presentation_mode
        titlebar_height = self.win.get_titlebar().get_height()
        css_classes = self.win.get_css_classes()
        if self.in_presentation_mode:
            css_classes.append("transparent")
            self.win.set_decorated(False)
            self.picture.set_margin_top(titlebar_height)
        else:
            css_classes.remove("transparent")
            self.win.set_decorated(True)
            self.picture.set_margin_top(0)

        self.win.set_css_classes(css_classes)

    def draw_image(self, widget: Gtk.Widget, idle: Gdk.FrameClock) -> bool:
        tick_before = cv2.getTickCount()

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

        if not True and logger.getEffectiveLevel() == logging.DEBUG:
            self.win.set_title(
                f"MyHumbleSelf -"
                f"FPS in/out: {np.mean(self.camera.fps):.1f} / {np.mean(self.fps):.1f}"
            )

        tick_after = cv2.getTickCount()
        fps = 1 / ((tick_after - tick_before) * self.clock_period)
        self.fps.append(fps)
        if len(self.fps) > self.fps_window:
            self.fps.pop(0)

        return True


def main() -> None:
    app = MyHumbleSelf(application_id="com.example.App")
    app.run(None)


if __name__ == "__main__":
    main()
