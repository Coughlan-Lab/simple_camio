from abc import ABC, abstractmethod
from typing import Union


class StraightLine(ABC):
    @property
    @abstractmethod
    def m(self) -> float:
        pass

    @property
    @abstractmethod
    def q(self) -> float:
        pass


class Coords:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def distance_to(self, other: "Coords") -> float:
        return float(((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5)

    def manhattan_distance_to(self, other: "Coords") -> float:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def distance_to_line(self, line: StraightLine) -> float:
        num = abs(line.m * self.x + line.q - self.y)
        den = (line.m**2 + 1) ** 0.5

        return float(num / den)

    def project_on(self, line: StraightLine) -> "Coords":
        p_x = (self.x + line.m * self.y - line.m * line.q) / (line.m**2 + 1)
        p_y = (line.m * self.x + line.m**2 * self.y + line.q) / (line.m**2 + 1)

        return Coords(p_x, p_y)

    def dot_product(self, other: "Coords") -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return self.distance_to(Coords(0, 0))

    def __add__(self, other: Union["Coords", float]) -> "Coords":
        if isinstance(other, Coords):
            return Coords(self.x + other.x, self.y + other.y)
        return Coords(self.x + other, self.y + other)

    def __sub__(self, other: Union["Coords", float]) -> "Coords":
        if isinstance(other, Coords):
            return Coords(self.x - other.x, self.y - other.y)
        return Coords(self.x - other, self.y - other)

    def __mul__(self, other: float) -> "Coords":
        return Coords(self.x * other, self.y * other)

    def __truediv__(self, other: float) -> "Coords":
        return Coords(self.x / other, self.y / other)

    def __getitem__(self, index: int) -> float:
        return self.x if index == 0 else self.y

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"

    def __repr__(self) -> str:
        return str(self)