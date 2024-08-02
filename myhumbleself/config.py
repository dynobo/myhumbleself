import logging
import os
from configparser import ConfigParser
from pathlib import Path

if xdg_conf := os.getenv("XDG_CONFIG_HOME", None):
    CONFIG_PATH = Path(xdg_conf) / "myhumbleself"
else:
    CONFIG_PATH = Path.home() / ".config" / "myhumbleself"
CONFIG_FILE = CONFIG_PATH / "myhumbleself.ini"

logger = logging.getLogger("myhumbleself")


class WritingConfigParser(ConfigParser):
    def set_persistent(
        self, option: str, value: str | bool | int, section: str = "main"
    ) -> None:
        """Updates the config file on disk, in case the value has changed.

        Args:
            section: Config section in the toml file.
            option: Setting name in the section.
            value: Setting value to be updated.
        """
        if self.get(section, option) == str(value):
            return
        self.set(section, option, str(value))
        if not CONFIG_FILE.parent.exists():
            CONFIG_FILE.parent.mkdir(exist_ok=True, parents=True)

        self.write(CONFIG_FILE.open("w"))


def load() -> WritingConfigParser:
    """Load the settings file or create a default settings file if it doesn't exist."""
    config = WritingConfigParser(
        defaults={
            "zoom_factor": "1",
            "follow_face": "True",
            "offset_x": "0",
            "offset_y": "0",
            "shape": "01-circle.png",
            "last_active_camera": "0",
        },
    )
    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)
        logger.debug("Loaded config from %s.", CONFIG_FILE)
    if not config.has_section("main"):
        config.add_section("main")
        logger.debug("Created missing 'main' section.")
    return config


if __name__ == "__main__":
    load()
