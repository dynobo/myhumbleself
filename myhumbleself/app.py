import argparse
import logging
import os
import tempfile
import time
from pathlib import Path

# Hide warnings show during search for cameras
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"

import cv2
import gi
import numpy as np

from myhumbleself import config, face_detection, processor

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk  # noqa: E402

RESOURCE_PATH = Path(__file__).parent / "resources"

logger = logging.getLogger(__name__)


def init_logger(log_level: str = "WARNING") -> None:
    """Initializes a logger with a specified log level.

    Args:
        log_level: The log level to set.
    """
    log_format = "%(asctime)s - %(levelname)-7s - %(name)s:%(lineno)d - %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(format=log_format, datefmt=datefmt, level=log_level)


class MyHumbleSelf(Gtk.Application):
    def __init__(self, application_id: str, args: argparse.Namespace) -> None:
        super().__init__(application_id=application_id)

        # Top level
        self.win: Gtk.ApplicationWindow
        self.resource: Gio.Resource

        # Webcam widget
        self.picture: Gtk.Picture

        # Headerbar widgets
        self.follow_face_button: Gtk.ToggleButton
        self.shape_box: Gtk.FlowBox
        self.camera_box: Gtk.FlowBox

        # Controls Container
        self.controls_grid: Gtk.Grid
        self.overlay: Gtk.Overlay

        # Controls
        self.reset_button: Gtk.Button
        self.toggle_controls_button: Gtk.Button
        self.right_button: Gtk.Button
        self.left_button: Gtk.Button
        self.down_button: Gtk.Button
        self.up_button: Gtk.Button
        self.zoom_in_button: Gtk.Button
        self.zoom_out_button: Gtk.Button

        # Init values
        self.config = config.load()
        self.in_presentation_mode = False
        self.fps: list[float] = [0]
        self.fps_window = 50
        self.cam_item_prefix = "/dev/video"
        self.hide_controls_timeout_id: int | None = None
        self.debug_mode = logger.getEffectiveLevel() == logging.DEBUG
        self.frame_processor = processor.FrameProcessor(
            face_detection_model=face_detection.DetectionModels[
                args.face_detection.upper()
            ],
            get_zoom_factor=lambda: self.config["main"].getfloat("zoom_factor", 1),
            get_offset_x=lambda: self.config["main"].getint("offset_x", 0),
            get_offset_y=lambda: self.config["main"].getint("offset_y", 0),
            get_follow_face=lambda: self.config["main"].getboolean("follow_face", True),
        )

        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

    def on_activate(self, app: Gtk.Application) -> None:
        """Initialize window on application activation.

        Args:
            app: Gtk Application.
        """
        self.resource = Gio.resource_load(
            str(Path(__file__).parent / "resources" / "myhumbleself.gresource")
        )
        Gio.Resource._register(self.resource)

        self.builder = Gtk.Builder()
        self.builder.add_from_resource("/com/github/dynobo/myhumbleself/window.ui")

        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        theme.add_resource_path("/com/github/dynobo/myhumbleself/icons")

        self.win = self.builder.get_object("main_window")
        self.win.set_application(self)

        picture = self.builder.get_object("picture")
        picture.add_tick_callback(self.on_picture_tick)

        self.shape_box = self.init_shape_box()
        self.follow_face_button = self.init_follow_face_button()
        self.camera_box = self.init_camera_box()
        self.debug_mode_button = self.builder.get_object("debug_mode_button")
        if self.debug_mode:
            self.debug_mode_button.set_visible(True)
            self.debug_mode_button.connect("clicked", self.on_toggle_debug_position)

        self.controls_grid = self.builder.get_object("controls_grid")
        self.overlay = self.builder.get_object("overlay")

        self.toggle_controls_button = self.builder.get_object("toggle_controls_button")
        self.toggle_controls_button.connect("clicked", self.on_toggle_controls_clicked)

        self.reset_button = self.builder.get_object("reset_button")
        self.reset_button.connect("clicked", self.on_reset_clicked)

        self.zoom_in_button = self.builder.get_object("zoom_in_button")
        self.zoom_in_button.connect("clicked", self.on_zoom_in)

        self.zoom_out_button = self.builder.get_object("zoom_out_button")
        self.zoom_out_button.connect("clicked", self.on_zoom_out)

        self.left_button = self.builder.get_object("left_button")
        self.left_button.connect("clicked", self.on_move_clicked, -1, 0)

        self.right_button = self.builder.get_object("right_button")
        self.right_button.connect("clicked", self.on_move_clicked, 1, 0)

        self.up_button = self.builder.get_object("up_button")
        self.up_button.connect("clicked", self.on_move_clicked, 0, -1)

        self.down_button = self.builder.get_object("down_button")
        self.down_button.connect("clicked", self.on_move_clicked, 0, 1)

        self.init_css()

        self.win.present()

    def _create_camera_menu_button(self, cam_id: int) -> Gtk.ToggleButton:
        """Create a custom button for camera menu, with image and label underneath.

        Args:
            cam_id: ID of the camera for which the button is created.

        Returns:
            Button widget.
        """
        image = self._cv2_image_to_gtk_image(
            self.frame_processor.camera.available_cameras[cam_id]
        )
        label = Gtk.Label()
        label.set_text(f"{self.cam_item_prefix}{cam_id}")

        button_box = Gtk.Box()
        button_box.set_orientation(Gtk.Orientation.VERTICAL)
        button_box.append(image)
        button_box.append(label)

        button = Gtk.ToggleButton()
        button.set_size_request(56, 56)
        button.set_has_frame(False)
        button.set_child(button_box)
        button.connect("toggled", self.on_camera_toggled, cam_id)
        button.set_css_classes([*button.get_css_classes(), "camera-button"])
        return button

    def init_camera_box(self) -> Gtk.FlowBox:
        """Fill the camera menu's flow box with buttons for each camera.

        Also hide the camera menu if only one camera is available.

        Returns:
            Widget containing the camera selection buttons.
        """
        camera_menu_button = self.builder.get_object("camera_menu_button")
        camera_box = self.builder.get_object("camera_box")
        first_button = None
        for cam_id in self.frame_processor.camera.available_cameras:
            # Show test image in camera menu only in debug mode:
            if (
                cam_id == self.frame_processor.camera.FALLBACK_CAM_ID
                and not self.debug_mode
            ):
                continue

            button = self._create_camera_menu_button(cam_id)

            # Activate button if it was the last active camera
            if cam_id == self.config["main"].getint("last_active_camera", 0):
                button.set_active(True)

            # Set button group
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)

            camera_box.append(button)

        # Hide camera menu if only one camera is available, except when in debug mode:
        if len(self.frame_processor.camera.available_cameras) == 1 and self.debug_mode:
            camera_menu_button.set_visible(False)

        return camera_box

    def init_shape_box(self) -> Gtk.FlowBox:
        """Setup widget for selecting shape overlay.

        Returns:
            Widget containing shape selection buttons.
        """
        shape_menu_button = self.builder.get_object("shape_menu_button")
        shape_menu_button.set_icon_name("shapes-symbolic")

        shape_box = self.builder.get_object("shape_box")

        first_button = None
        for shape in self.resource.enumerate_children(
            "/com/github/dynobo/myhumbleself/shapes", Gio.ResourceLookupFlags.NONE
        ):
            button = Gtk.ToggleButton()
            button.set_size_request(56, 56)
            button.set_icon_name(f"{shape[:-4]}-symbolic")
            button.set_has_frame(False)
            button.connect("toggled", self.on_shape_toggled, shape)
            button.set_css_classes([*button.get_css_classes(), "shape-button"])

            # Activate stored shape:
            if shape == self.config["main"].get("shape"):
                button.set_active(True)

            # Set button group
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)

            shape_box.append(button)

        return shape_box

    def init_follow_face_button(self) -> Gtk.ToggleButton:
        """Setup widget for toggling face detection mode.

        Returns:
            Toggle Button.
        """
        is_follow_face = self.config["main"].getboolean("follow_face")
        follow_face_button = self.builder.get_object("follow_face_button")
        follow_face_button.set_active(is_follow_face)
        follow_face_button.set_tooltip_text(
            "Do not follow face" if is_follow_face else "Follow face"
        )
        follow_face_button.set_icon_name(
            "follow-face-off-symbolic" if is_follow_face else "follow-face-symbolic"
        )
        follow_face_button.connect("clicked", self.on_follow_face_clicked)
        return follow_face_button

    def init_css(self) -> None:
        """Apply style from css file to the application."""
        self.css_provider = self.builder.get_object("css_provider")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.css_provider.load_from_resource(
            "/com/github/dynobo/myhumbleself/style.css"
        )

    def on_follow_face_clicked(self, button: Gtk.ToggleButton) -> None:
        self.config.set_persistent("follow_face", button.get_active())

        if button.get_active():
            button.set_tooltip_text("Do not follow face")
            button.set_icon_name("follow-face-off-symbolic")
        else:
            button.set_tooltip_text("Follow face")
            button.set_icon_name("follow-face-symbolic")

    def on_shape_toggled(self, button: Gtk.ToggleButton, shape: str) -> None:
        if not button.get_active():
            return

        shape_png = self.resource.lookup_data(
            f"/com/github/dynobo/myhumbleself/shapes/{shape}",
            Gio.ResourceLookupFlags.NONE,
        ).get_data()
        self.frame_processor.shape = cv2.imdecode(
            np.frombuffer(shape_png, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        self.config.set_persistent("shape", shape)

    def on_camera_toggled(self, button: Gtk.ToggleButton, cam_id: int) -> None:
        if not button.get_active():
            return
        self.frame_processor.camera.stop()
        self.frame_processor.camera.start(cam_id)
        self.config.set_persistent("last_active_camera", cam_id)

    def on_reset_clicked(self, button: Gtk.Button) -> None:
        self.config.set_persistent("offset_x", 0)
        self.config.set_persistent("offset_y", 0)
        self.config.set_persistent("zoom_factor", 1)

    def on_move_clicked(self, button: Gtk.Button, factor_x: int, factor_y: int) -> None:
        self.config.set_persistent(
            "offset_x",
            self.config["main"].getint("offset_x", 0)
            + factor_x * self.frame_processor.move_step,
        )
        self.config.set_persistent(
            "offset_y",
            self.config["main"].getint("offset_y", 0)
            + factor_y * self.frame_processor.move_step,
        )

    def on_zoom_in(self, btn: Gtk.Button) -> None:
        zoom = self.config["main"].getfloat("zoom_factor", 1)
        self.config.set_persistent(
            "zoom_factor", zoom + self.frame_processor.zoom_step * 1
        )

    def on_zoom_out(self, btn: Gtk.Button) -> None:
        zoom = self.config["main"].getfloat("zoom_factor", 1)
        self.config.set_persistent(
            "zoom_factor", zoom + self.frame_processor.zoom_step * -1
        )

    def on_shutdown(self, app: Gtk.Application) -> None:
        self.frame_processor.camera.stop()

    def on_toggle_controls_clicked(self, button: Gtk.Button) -> None:
        self.toggle_presentation_mode()

    def on_toggle_debug_position(self, button: Gtk.Button) -> None:
        debug_mode = button.get_active()
        self.debug_mode = debug_mode
        self.frame_processor.debug_mode = debug_mode
        self.frame_processor.face_detection.debug_mode = debug_mode

    def on_picture_tick(self, widget: Gtk.Widget, idle: Gdk.FrameClock) -> bool:
        """Tick callback on picture container.

        Used to update the webcam image on every application tick.

        Args:
            widget: Tick owner widget.
            idle: The frame clock for the widget.

        Returns:
            True if the tick callback should continue to be called.
        """
        self.draw_image(widget)
        return True

    def toggle_presentation_mode(self) -> None:
        self.in_presentation_mode = not self.in_presentation_mode
        titlebar_height = self.win.get_titlebar().get_height()
        css_classes = self.win.get_css_classes()

        if self.in_presentation_mode:
            css_classes.append("transparent")
            self.win.set_decorated(False)
            self.overlay.set_margin_top(titlebar_height)
        else:
            css_classes.remove("transparent")
            self.win.set_decorated(True)
            self.overlay.set_margin_top(0)

        self.win.set_css_classes(css_classes)

    def draw_image(self, widget: Gtk.Widget) -> None:
        """Draw webcam image on container widget.

        Args:
            widget: Tick owner widget.
        """
        if not self.frame_processor:
            return

        tick_before = time.perf_counter()

        image = self.frame_processor.get_process_frame()
        if image is None:
            return

        self.left_button.set_sensitive(self.frame_processor.can_move_left)
        self.right_button.set_sensitive(self.frame_processor.can_move_right)
        self.up_button.set_sensitive(self.frame_processor.can_move_up)
        self.down_button.set_sensitive(self.frame_processor.can_move_down)

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

        if logger.getEffectiveLevel() <= logging.INFO:
            self.win.set_title(
                f"MyHumbleSelf - "
                f"FPS in/out: {np.mean(self.frame_processor.camera.fps):.1f} "
                f"/ {np.mean(self.fps):.1f}"
            )

        tick_after = time.perf_counter()
        fps = 1 / (tick_after - tick_before)
        self.fps.append(fps)
        if len(self.fps) > self.fps_window:
            self.fps.pop(0)

    @staticmethod
    def _cv2_image_to_gtk_image(cv2_image: np.ndarray) -> Gtk.Image:
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


def _parse_args() -> argparse.Namespace:
    """Configure and process cli arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--face-detection",
        type=str,
        choices=[m.name.lower() for m in face_detection.DetectionModels],
        help="Model to use for face detection. "
        "The default 'cnn' is more accurate but requires more compute.",
        default="cnn",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable info logging."
    )
    parser.add_argument(
        "-vv", "--very-verbose", action="store_true", help="Enable debug logging."
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.very_verbose:
        log_level = "DEBUG"
    elif args.verbose:
        log_level = "INFO"
    else:
        log_level = "WARNING"

    init_logger(log_level=log_level)

    app = MyHumbleSelf(application_id="com.github.dynobo.myhumbleself", args=args)
    app.run(None)


if __name__ == "__main__":
    main()
