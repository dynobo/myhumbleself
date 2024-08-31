import threading
from collections.abc import Callable
from time import sleep

import pytest
from gi.repository import GLib

from myhumbleself import app


def get_value(func: Callable, key: str, result: dict):
    result[key] = func()


def do_actions(funcs: list[Callable]):
    delay = 200

    for idx, func in enumerate(funcs):
        GLib.timeout_add(idx * delay, func)

    sleep(1 + len(funcs) * delay / 1000)  # Wait for all actions to be executed


@pytest.fixture()
def _init_config(monkeypatch):
    monkeypatch.setattr(
        app.config.WritingConfigParser,
        "set_persistent",
        app.config.WritingConfigParser.set,
    )

    def load_parser():
        parser = app.config.WritingConfigParser(
            defaults={
                "zoom_factor": "1",
                "follow_face": "True",
                "offset_x": "0",
                "offset_y": "0",
                "shape": "01-circle.png",
                "last_active_camera": "0",
            },
        )
        parser.add_section("main")
        return parser

    monkeypatch.setattr(app.config, "load", load_parser)


@pytest.fixture()
def mhs_app(_init_config):
    mhs = app.MyHumbleSelf(application_id="com.github.dynobo.myhumbleself", args={})
    thread = threading.Thread(target=mhs.run)
    thread.start()

    sleep(1)  # Time to get up and running

    yield mhs

    GLib.idle_add(mhs.quit)
    thread.join()


@pytest.mark.gui()
def test_about_button(mhs_app):
    result = {}
    do_actions(
        [
            lambda: mhs_app.about_button.emit("clicked"),
            lambda: get_value(mhs_app.about.get_visible, "is_visible", result),
        ]
    )
    assert result["is_visible"]
