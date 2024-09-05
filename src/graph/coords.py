import math
from abc import ABC, abstractmethod
from typing import Iterator, Union


class StraightLine(ABC):
    @property
    @abstractmethod
    def m(self) -> float:
        pass

    @property
    @abstractmethod
    def q(self) -> float:
        pass


class Position(ABC):
    @abstractmethod
    def distance_to(self, coords: "Coords") -> float:
        pass

    @abstractmethod
    def closest_point(self, coords: "Coords") -> "Coords":
        pass

    @abstractmethod
    def get_complete_description(self) -> str:
        pass


class Coords:
    def __init__(self, x: float, y: float) -> None:
        self.coords = (x, y)

    @property
    def x(self) -> float:
        return self.coords[0]

    @property
    def y(self) -> float:
        return self.coords[1]

    def distance_to(self, coords: "Coords") -> float:
        return float(((self.x - coords.x) ** 2 + (self.y - coords.y) ** 2) ** 0.5)

    def manhattan_distance_to(self, other: "Coords") -> float:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def distance_to_line(self, line: StraightLine) -> float:
        if math.isinf(line.m):
            return abs(self.x - line.q)

        num = abs(line.m * self.x + line.q - self.y)
        den = (line.m**2 + 1) ** 0.5

        return float(num / den)

    def project_on(self, line: StraightLine) -> "Coords":
        if math.isinf(line.m):
            return Coords(line.q, self.y)

        p_x = (self.x + line.m * self.y - line.m * line.q) / (line.m**2 + 1)
        p_y = (line.m * self.x + line.m**2 * self.y + line.q) / (line.m**2 + 1)

        return Coords(p_x, p_y)

    def dot_product(self, other: "Coords") -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return self.distance_to(ZERO)

    def normalized(self) -> "Coords":
        return self / self.length()

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

    def __floordiv__(self, other: float) -> "Coords":
        return Coords(self.x // other, self.y // other)

    def __getitem__(self, index: int) -> float:
        return self.coords[index]

    def __iter__(self) -> Iterator[float]:
        return iter((self.x, self.y))

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"

    def __repr__(self) -> str:
        return str(self)


ZERO = Coords(0, 0)
INF = Coords(math.inf, math.inf)
