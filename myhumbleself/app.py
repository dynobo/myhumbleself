import argparse
import logging
import os
import platform
import time
from pathlib import Path
from statistics import mean

# Hide warnings shown during search for cameras
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"

import gi

from myhumbleself import __version__, config, converters, video_handler

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk  # noqa: E402

logger = logging.getLogger(__name__)


def init_logger(log_level: str = "WARNING") -> None:
    log_format = "%(asctime)s - %(levelname)-7s - %(name)s:%(lineno)d - %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(format=log_format, datefmt=datefmt, level=log_level)


class MyHumbleSelf(Gtk.Application):
    def __init__(self, application_id: str, args: argparse.Namespace) -> None:
        super().__init__(application_id=application_id)

        # Resource file
        self.resource = Gio.resource_load(
            str(Path(__file__).parent / "resources" / "myhumbleself.gresource")
        )
        Gio.Resource._register(self.resource)

        # Top level
        self.win: Gtk.ApplicationWindow

        # Webcam widget
        self.picture: Gtk.Picture

        # Headerbar widgets
        self.follow_face_button: Gtk.ToggleButton
        self.shape_box: Gtk.FlowBox
        self.camera_box: Gtk.FlowBox

        # Controls Container
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
        self.fps: list[float] = [0]
        self.fps_window = 50
        self.cam_item_prefix = "/dev/video"
        self.loglevel_debug = logger.getEffectiveLevel() == logging.DEBUG
        self.last_image_id = b""
        self.video_handler = video_handler.VideoHandler(
            cam_id=self.config["main"].getint("last_active_camera", 0),
            shape_png_buffer=self._load_active_shape_png(),
            zoom_factor=self.config["main"].getfloat("zoom_factor", 1),
            offset_x=self.config["main"].getint("offset_x", 0),
            offset_y=self.config["main"].getint("offset_y", 0),
            follow_face=self.config["main"].getboolean("follow_face", True),
        )

        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

    def on_activate(self, app: Gtk.Application) -> None:
        """Initialize window on application activation.

        Args:
            app: Gtk Application.
        """
        self.builder = Gtk.Builder()
        self.builder.add_from_resource("/com/github/dynobo/myhumbleself/window.ui")

        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        theme.add_resource_path("/com/github/dynobo/myhumbleself/icons")

        self.win = self.builder.get_object("main_window")
        self.win.set_application(self)
        self.win.set_icon_name("com.github.dynobo.myhumbleself")

        picture = self.builder.get_object("picture")
        picture.add_tick_callback(self.on_picture_tick)

        self.shape_box = self.init_shape_box()
        self.follow_face_button = self.init_follow_face_button()
        self.camera_box = self.init_camera_box()
        self.about_dialog = self.builder.get_object("about_dialog")
        self.about_button = self.builder.get_object("about_button")
        self.about_dialog.set_logo_icon_name("com.github.dynobo.myhumbleself")
        self.about_dialog.set_version(__version__)
        self.about_dialog.set_system_information(self.get_system_info())
        self.about_button.connect("clicked", lambda _: self.about_dialog.present())
        self.debug_mode_button = self.builder.get_object("debug_mode_button")
        if self.loglevel_debug:
            self.debug_mode_button.set_visible(True)
            self.debug_mode_button.connect("clicked", self.on_toggle_debug_position)

        self.overlay = self.builder.get_object("overlay")

        self.toggle_controls_button = self.builder.get_object("toggle_controls_button")
        self.toggle_controls_button.set_icon_name("controls-hide-symbolic")
        self.toggle_controls_button.connect("toggled", self.on_toggle_controls_clicked)

        self.reset_button = self.builder.get_object("reset_button")
        self.reset_button.set_icon_name("reset-symbolic")
        self.reset_button.set_tooltip_text("Reset view")
        self.reset_button.connect("clicked", self.on_reset_clicked)

        self.zoom_in_button = self.builder.get_object("zoom_in_button")
        self.zoom_in_button.connect("clicked", self.on_zoom, 1)

        self.zoom_out_button = self.builder.get_object("zoom_out_button")
        self.zoom_out_button.connect("clicked", self.on_zoom, -1)

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

    def create_camera_menu_button(self, cam_id: int) -> Gtk.ToggleButton:
        """Create a custom button for camera menu, with image and label underneath.

        Args:
            cam_id: ID of the camera for which the button is created.

        Returns:
            Button widget.
        """
        image = converters.cv2_image_to_gtk_image(
            self.video_handler.available_cameras[cam_id]
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
        for cam_id in self.video_handler.available_cameras:
            button = self.create_camera_menu_button(cam_id)

            # Activate button if it was the last active camera
            if cam_id == self.config["main"].getint("last_active_camera", 0):
                button.set_active(True)

            if cam_id == self.video_handler.FALLBACK_CAM_ID:
                button.set_visible(self.loglevel_debug)

            # Set button group
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)

            camera_box.append(button)

        # Hide camera menu if only one camera (plus fallback) is available, except
        # when in debug mode:
        is_visible = (
            len(self.video_handler.available_cameras) - 1 > 1 or self.loglevel_debug
        )
        camera_menu_button.set_visible(is_visible)

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
        follow_face = button.get_active()
        self.config.set_persistent("follow_face", follow_face)
        self.video_handler.follow_face = follow_face
        if follow_face:
            button.set_tooltip_text("Do not follow face")
            button.set_icon_name("follow-face-off-symbolic")
        else:
            button.set_tooltip_text("Follow face")
            button.set_icon_name("follow-face-symbolic")

    def _load_active_shape_png(self) -> bytes:
        shape = self.config["main"].get("shape")
        shape_png = self.resource.lookup_data(
            f"/com/github/dynobo/myhumbleself/shapes/{shape}",
            Gio.ResourceLookupFlags.NONE,
        ).get_data()
        return shape_png

    def on_shape_toggled(self, button: Gtk.ToggleButton, shape: str) -> None:
        if not button.get_active():
            return
        self.config.set_persistent("shape", shape)
        self.video_handler.set_shape(self._load_active_shape_png())

    def on_camera_toggled(self, button: Gtk.ToggleButton, cam_id: int) -> None:
        if not button.get_active():
            return
        self.video_handler.set_camera(cam_id)
        self.config.set_persistent("last_active_camera", cam_id)

    def on_reset_clicked(self, button: Gtk.Button) -> None:
        self.config.set_persistent("offset_x", 0)
        self.config.set_persistent("offset_y", 0)
        self.config.set_persistent("zoom_factor", 1)
        self.video_handler.reset_view()

    def on_move_clicked(self, button: Gtk.Button, factor_x: int, factor_y: int) -> None:
        self.video_handler.offset_x += factor_x * self.video_handler.MOVE_STEP
        self.video_handler.offset_y += factor_y * self.video_handler.MOVE_STEP
        self.config.set_persistent("offset_x", self.video_handler.offset_x)
        self.config.set_persistent("offset_y", self.video_handler.offset_y)

    def on_zoom(self, _: Gtk.Button, factor_z: int) -> None:
        zoom = self.config["main"].getfloat("zoom_factor", 1)
        zoom -= self.video_handler.ZOOM_STEP * factor_z
        self.video_handler.zoom_factor = max(zoom, self.video_handler.MIN_ZOOM_FACTOR)
        self.config.set_persistent("zoom_factor", zoom)

    def on_shutdown(self, _: Gtk.Application) -> None:
        self.video_handler.set_camera(None)

    def on_toggle_controls_clicked(self, btn: Gtk.Button) -> None:
        btn.set_icon_name(
            "controls-show-symbolic" if btn.get_active() else "controls-hide-symbolic"
        )
        self.toggle_presentation_mode(on=btn.get_active())

    def on_toggle_debug_position(self, button: Gtk.Button) -> None:
        debug_mode = button.get_active()
        self.video_handler.set_debug_mode(on=debug_mode)

    def on_picture_tick(self, widget: Gtk.Widget, _: Gdk.FrameClock) -> bool:
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

    def toggle_presentation_mode(self, on: bool) -> None:
        titlebar_height = self.win.get_titlebar().get_height()
        css_classes = self.win.get_css_classes()

        if on:
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
        tick_before = time.perf_counter()

        image = self.video_handler.get_processed_frame()

        # Compare an approx. image hash with the last one to avoid unnecessary updates:
        new_image_id = image[::100, ::100, 1].data.tobytes()
        if self.last_image_id != new_image_id:
            self.last_image_id = new_image_id

            self.left_button.set_sensitive(self.video_handler.can_move_left())
            self.right_button.set_sensitive(self.video_handler.can_move_right())
            self.up_button.set_sensitive(self.video_handler.can_move_up())
            self.down_button.set_sensitive(self.video_handler.can_move_down())
            self.zoom_out_button.set_sensitive(self.video_handler.can_zoom_out())
            self.zoom_in_button.set_sensitive(self.video_handler.can_zoom_in())

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
                f"FPS in/out: {mean(self.video_handler._camera.fps):.1f} "
                f"/ {mean(self.fps):.1f}"
            )

        tick_after = time.perf_counter()
        fps = 1 / (tick_after - tick_before)
        self.fps.append(fps)
        if len(self.fps) > self.fps_window:
            self.fps.pop(0)

    def get_system_info(self) -> str:
        xdg_session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        has_wayland_display_env = bool(os.environ.get("WAYLAND_DISPLAY", ""))
        is_wayland = "wayland" in xdg_session_type or has_wayland_display_env

        linux_info = platform.freedesktop_os_release()

        text = f"Distro: {linux_info.get('NAME', 'Unknown')} "
        text += f"({linux_info.get('BUILD_ID', 'Unknown')})\n"
        text += f"DE: {self.get_desktop_environment()}\n"
        text += f"Wayland: {is_wayland}\n"
        text += f"Flatpak: {os.getenv('FLATPAK_ID') is not None}\n"
        text += f"Python: {platform.python_version()}\n"
        text += f"GTK: {Gtk.get_major_version()}.{Gtk.get_minor_version()}\n"

        logger.debug("System information:\n%s", text)
        return text

    def get_desktop_environment(self) -> str:  # noqa: PLR0911 # too many returns
        """Detect used desktop environment."""
        kde_full_session = os.environ.get("KDE_FULL_SESSION", "").lower()
        xdg_current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()
        gnome_desktop_session_id = os.environ.get("GNOME_DESKTOP_SESSION_ID", "")
        hyprland_instance_signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")

        if gnome_desktop_session_id == "this-is-deprecated":
            gnome_desktop_session_id = ""

        if gnome_desktop_session_id or "gnome" in xdg_current_desktop:
            return "Gnome"
        if kde_full_session or "kde-plasma" in desktop_session:
            return "KDE"
        if "sway" in xdg_current_desktop or "sway" in desktop_session:
            return "Sway"
        if "unity" in xdg_current_desktop:
            return "Unity"
        if hyprland_instance_signature:
            return "Hyprland"
        if "awesome" in xdg_current_desktop:
            return "Awesome"

        return "Unknown"


def _parse_args() -> argparse.Namespace:
    """Configure and process cli arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser()
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
