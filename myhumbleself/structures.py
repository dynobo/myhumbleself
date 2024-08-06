from dataclasses import dataclass


@dataclass
class Rect:
    """Data structure to represent and transform rectangles.

    Note: Using OpenCV style geometry ordering (y, x, height, width)
    """

    top: int
    left: int
    width: int
    height: int

    def __str__(self) -> str:
        return f"Rect(x={self.left}, y={self.top}, w={self.width}, h={self.height})"

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def left_top(self) -> tuple[int, int]:
        return (self.left, self.top)

    @property
    def right_bottom(self) -> tuple[int, int]:
        return (self.left + self.width, self.top + self.height)

    @property
    def area(self) -> int:
        return abs(self.width * self.height)

    @property
    def geometry(self) -> tuple[int, int, int, int]:
        return (self.top, self.left, self.height, self.width)

    def pad(self, padding: int) -> None:
        """Centered padding of the rectangle.

        Args:
            padding: Absolute padding value.
        """
        self.top = self.top - padding
        self.left = self.left - padding
        self.width = self.width + 2 * padding
        self.height = self.height + 2 * padding

    def scale(self, factor: float) -> None:
        """Centered scaling of the rectangle.

        Note: Using int() instead of more accurate round(), because we care less about
          single pixel accuracy than about speed.

        Args:
            factor: Multiplication factor.
        """
        new_width = int(self.width * factor)
        new_height = int(self.height * factor)
        self.top -= int((new_height - self.height) / 2)
        self.left -= int((new_width - self.width) / 2)
        self.width = new_width
        self.height = new_height

    def copy(self) -> "Rect":
        return Rect(top=self.top, left=self.left, height=self.height, width=self.width)

    def move_by(self, y: int, x: int) -> None:
        """Move the rectangle by the provided x and y values.

        Args:
            y: Value to move the rectangle by on the y-axis.
            x: Value to move the rectangle by on the x-axis.
        """
        self.left += x
        self.top += y

    def stay_within(self, height: int, width: int) -> None:
        """Ensure the rectangle is within the bounds of the provided width and height.

        Preserves aspect ratio.

        Args:
            height: Height of the bounding box.
            width: Width of the bounding box.
        """
        # Scale self to fit within width and height
        scale_factor = min(width / self.width, height / self.height)
        if scale_factor < 1:
            self.scale(scale_factor)

        self.top = min(max(0, self.top), height - self.height)
        self.left = min(max(0, self.left), width - self.width)
