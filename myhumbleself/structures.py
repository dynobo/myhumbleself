from dataclasses import dataclass


@dataclass
class Rect:
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
        return self.width * self.height

    @property
    def geometry(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)

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
        return Rect(top=self.top, left=self.left, width=self.width, height=self.height)

    def move_by(self, x: int, y: int) -> None:
        """Move the rectangle by the provided x and y values.

        Args:
            x: Value to move the rectangle by on the x-axis.
            y: Value to move the rectangle by on the y-axis.
        """
        self.top += y
        self.left += x

    def stay_within(self, width: int, height: int) -> None:
        """Ensure the rectangle is within the bounds of the provided width and height.

        Preserves aspect ratio.

        Args:
            width: Width of the bounding box.
            height: Height of the bounding box.
        """
        # Scale self to fit within width and height
        scale_factor = min(width / self.width, height / self.height)
        if scale_factor < 1:
            self.scale(scale_factor)

        self.top = min(max(0, self.top), height - self.height)
        self.left = min(max(0, self.left), width - self.width)
