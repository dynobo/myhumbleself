from dataclasses import dataclass


@dataclass
class Rect:
    top: int
    left: int
    width: int
    height: int

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
    def center_xy(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    @property
    def geometry(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)

    @property
    def is_empty(self) -> bool:
        return any((self.left, self.top, self.width, self.height))
