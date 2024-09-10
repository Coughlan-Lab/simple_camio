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


class Coords(Position):
    def __init__(self, x: float, y: float) -> None:
        self.coords = (x, y)

    @property
    def x(self) -> float:
        return self.coords[0]

    @property
    def y(self) -> float:
        return self.coords[1]

    def closest_point(self, coords: "Coords") -> "Coords":
        return self

    def get_complete_description(self) -> str:
        return str(self)

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

    def dot(self, other: "Coords") -> float:
        return self.x * other.x + self.y * other.y

    def cross_2d(self, other: "Coords") -> float:
        return self.x * other.y - self.y * other.x

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

    def __round__(self, n: int = 0) -> "Coords":
        return Coords(round(self.x, n), round(self.y, n))

    def __repr__(self) -> str:
        return str(self)


ZERO = Coords(0, 0)
INF = Coords(math.inf, math.inf)


class LatLngReference:
    def __init__(self, coords: Coords, lat: float, lng: float) -> None:
        self.coords = coords
        self.lat = lat
        self.lng = lng


feets_per_meter = 3.280839895
R = 6378137 * feets_per_meter  # Earth radius in feets


def coords_to_latlng(latlng_reference: LatLngReference, coords: Coords) -> Coords:
    diff = coords - latlng_reference.coords
    de = diff[0]
    dn = -(diff[1])

    dLat = dn / R
    dLon = de / (R * math.cos(math.pi * latlng_reference.lat / 180))

    latO = latlng_reference.lat + dLat * 180 / math.pi
    lonO = latlng_reference.lng + dLon * 180 / math.pi

    return Coords(latO, lonO)


def latlng_to_coords(reference: LatLngReference, latlng: Coords) -> Coords:
    dx = latlng_distance(reference.lat, reference.lng, reference.lat, latlng.y)
    dy = latlng_distance(reference.lat, reference.lng, latlng.x, reference.lng)

    if reference.lat > latlng.x:
        dy *= -1
    if reference.lng > latlng.y:
        dx *= -1

    return Coords(reference.coords.x + dx, reference.coords.y - dy)


def latlng_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1 = math.radians(lat1)
    lng1 = math.radians(lng1)
    lat2 = math.radians(lat2)
    lng2 = math.radians(lng2)

    dLat = lat2 - lat1
    dLon = lng2 - lng1

    a = (
        math.sin(dLat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dLon / 2) ** 2
    )

    c = 2 * math.asin(math.sqrt(a))
    return R * c
