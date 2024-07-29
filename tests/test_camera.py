from myhumbleself import camera


def test_available_cameras():
    cam = camera.Camera()
    assert cam.available_cameras
