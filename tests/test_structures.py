import pytest

from myhumbleself import structures


def test_rect_repr():
    y, x, h, w = (5, 10, 20, 40)
    rect = structures.Rect(top=y, left=x, height=h, width=w)
    rect_repr = str(rect)
    assert f"y={y}" in rect_repr
    assert f"x={x}" in rect_repr
    assert f"w={w}" in rect_repr
    assert f"h={h}" in rect_repr


@pytest.mark.parametrize(
    ("left", "width", "expected_right"),
    [
        (0, 100, 100),
        (100, 100, 200),
        (-100, 100, 0),
        (-200, 100, -100),
        (50, -100, -50),
    ],
)
def test_rect_right(left, width, expected_right):
    rect = structures.Rect(top=0, left=left, height=100, width=width)
    assert rect.right == expected_right


@pytest.mark.parametrize(
    ("top", "height", "expected_bottom"),
    [
        (0, 100, 100),
        (100, 100, 200),
        (-100, 100, 0),
        (-200, 100, -100),
        (50, -100, -50),
    ],
)
def test_rect_bottom(top, height, expected_bottom):
    rect = structures.Rect(top=top, left=0, height=height, width=100)
    assert rect.bottom == expected_bottom


def test_rect_left_top():
    left, top = 10, 20
    rect = structures.Rect(top=top, left=left, width=10, height=10)
    assert rect.left_top == (left, top)


def test_rect_right_bottom():
    right, bottom = 10, 20
    rect = structures.Rect(top=0, left=0, width=right, height=bottom)
    assert rect.right_bottom == (right, bottom)


@pytest.mark.parametrize(
    ("yxhw", "expected_area"),
    [
        ((0, 0, 50, 100), 5000),
        ((-50, -100, 50, 100), 5000),
        ((0, 0, -50, 100), 5000),
    ],
)
def test_rect_area(yxhw, expected_area):
    rect = structures.Rect(top=yxhw[0], left=yxhw[1], height=yxhw[2], width=yxhw[3])
    assert rect.area == expected_area


def test_rect_geometry():
    y, x, h, w = (5, 10, 20, 40)
    rect = structures.Rect(top=y, left=x, height=h, width=w)
    assert rect.geometry == (y, x, h, w)


@pytest.mark.parametrize(
    ("yxhw", "factor", "expected_yxhw"),
    [
        ((0, 0, 50, 100), 2.0, (-25, -50, 100, 200)),
        ((-100, -100, 50, 100), 2.0, (-125, -150, 100, 200)),
        ((-10, -10, 5, 20), 0.5, (-9, -5, 2, 10)),
    ],
)
def test_rect_scale(yxhw, factor, expected_yxhw):
    rect = structures.Rect(top=yxhw[0], left=yxhw[1], height=yxhw[2], width=yxhw[3])
    rect.scale(factor=factor)
    assert rect.top == expected_yxhw[0]
    assert rect.left == expected_yxhw[1]
    assert rect.height == expected_yxhw[2]
    assert rect.width == expected_yxhw[3]


@pytest.mark.parametrize(
    ("yxhw", "padding", "expected_yxhw"),
    [
        ((0, 0, 5, 10), 5, (-5, -5, 15, 20)),
        ((-10, -5, 5, 10), 2, (-12, -7, 9, 14)),
        ((10, 20, 30, 40), -2, (12, 22, 26, 36)),
    ],
)
def test_rect_pad(yxhw, padding, expected_yxhw):
    rect = structures.Rect(top=yxhw[0], left=yxhw[1], height=yxhw[2], width=yxhw[3])
    rect.pad(padding)
    assert rect.top == expected_yxhw[0]
    assert rect.left == expected_yxhw[1]
    assert rect.height == expected_yxhw[2]
    assert rect.width == expected_yxhw[3]


def test_rect_copy():
    rect = structures.Rect(0, 5, 10, 15)
    rect_copy = rect.copy()
    assert rect.top == rect_copy.top
    assert rect.left == rect_copy.left
    assert rect.height == rect_copy.height
    assert rect.width == rect_copy.width
    assert rect is not rect_copy


def test_rect_move_by():
    y, x, h, w = (5, 10, 20, 40)
    delta_y, delta_x = -10, 5
    rect = structures.Rect(top=y, left=x, height=h, width=w)
    rect.move_by(y=delta_y, x=delta_x)
    assert rect.top == y + delta_y
    assert rect.left == x + delta_x
    assert rect.height == h
    assert rect.width == w


@pytest.mark.parametrize(
    ("yxhw", "max_height", "max_width", "expected_yxhw"),
    [
        ((5, 5, 10, 10), 20, 20, (5, 5, 10, 10)),
        ((0, 0, 20, 20), 10, 10, (0, 0, 10, 10)),
        ((0, 5, 20, 20), 10, 10, (0, 0, 10, 10)),
        ((0, 5, 20, 10), 10, 10, (0, 5, 10, 5)),
        ((10, 20, 40, 60), 20, 10, (14, 0, 6, 10)),
    ],
)
def test_rect_stay_within(yxhw, max_height, max_width, expected_yxhw):
    rect = structures.Rect(top=yxhw[0], left=yxhw[1], height=yxhw[2], width=yxhw[3])
    rect.stay_within(height=max_height, width=max_width)
    assert rect.top == expected_yxhw[0]
    assert rect.left == expected_yxhw[1]
    assert rect.height == expected_yxhw[2]
    assert rect.width == expected_yxhw[3]
