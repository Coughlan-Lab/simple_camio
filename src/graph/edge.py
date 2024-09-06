from typing import Any, Dict, List, Optional, Set

from src.utils import StrEnum

from .coords import Coords, Position, StraightLine
from .node import Node


class Features(StrEnum):
    ROADWORK = "roadwork"
    SLOPE = "slope"
    BIKE_LANE = "bike_lane"
    SURFACE = "surface"
    TRAFFIC_DIRECTION = "traffic_direction"
    STAIRS = "stairs"


default_features = {
    "roadwork": False,
    "slope": "flat",
    "bike_lane": False,
    "surface": "concrete",
    "traffic_direction": "two_way",
    "stairs": False,
}


class Edge(StraightLine, Position):
    def __init__(
        self,
        node1: Node,
        node2: Node,
        street_name: str,
        features: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.node1 = node1
        self.node2 = node2
        self.street = street_name
        self.features = features if features is not None else default_features

        self.between_streets: Set[str] = set()
        self.length = self.node1.distance_to(self.node2)

    @property
    def id(self) -> str:
        return f"{self.node1.id} - {self.node2.id}"

    @property
    def m(self) -> float:
        if self.node1[0] == self.node2[0]:
            return float("inf")

        return (self.node1[1] - self.node2[1]) / (self.node1[0] - self.node2[0])

    @property
    def q(self) -> float:
        if self.node1[0] == self.node2[0]:
            return self.node1[0]

        return (self.node1[0] * self.node2[1] - self.node2[0] * self.node1[1]) / (
            self.node1[0] - self.node2[0]
        )

    def contains(self, coords: Coords) -> bool:
        return (
            self.node1[0] < coords[0] < self.node2[0]
            or self.node2[0] < coords[0] < self.node1[0]
            or self.node1[1] < coords[1] < self.node2[1]
            or self.node2[1] < coords[1] < self.node1[1]
        )

    def is_adjacent(self, other: "Edge") -> bool:
        return (
            self.node1 == other.node1
            or self.node1 == other.node2
            or self.node2 == other.node1
            or self.node2 == other.node2
        )

    def distance_to(self, coords: "Coords") -> float:
        if self.contains(coords.project_on(self)):
            return coords.distance_to_line(self)

        return min(
            self.node1.distance_to(coords),
            self.node2.distance_to(coords),
        )

    def closest_point(self, coords: "Coords") -> "Coords":
        projection = coords.project_on(self)
        if self.contains(projection):
            return projection

        return min(
            [self.node1, self.node2],
            key=lambda node: node.distance_to(coords),
        ).coords

    def __getitem__(self, index: int) -> Node:
        return (self.node1, self.node2)[index]

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Edge):
            return False
        return self.node1 == other.node1 and self.node2 == other.node2

    def __hash__(self) -> int:
        return hash(self.id)

    def get_llm_description(self) -> str:
        if len(self.between_streets) == 0:
            return f"at the end of {self.street}."

        if len(self.between_streets) == 1:
            return f"on {self.street}, at the intersection with {next(iter(self.between_streets))}"

        streets = list(self.between_streets)
        street_str = (
            f"on {self.street}, between {', '.join(streets[:-1])} and {streets[-1]}"
        )

        return street_str

    def get_complete_description(self) -> str:
        description = self.street

        description += f", {self.features[Features.SURFACE]}"

        if self.node1.is_dead_end() or self.node2.is_dead_end():
            description += ", dead end"

        if self.features[Features.TRAFFIC_DIRECTION] != "two_way":
            description += ", one-way"

        if self.features[Features.SLOPE] != "flat":
            description += ", sloped"

        hazards: List[str] = list()
        if self.features[Features.ROADWORK]:
            hazards.append("roadwork")
        if self.features[Features.STAIRS]:
            hazards.append("stairs on the way")
        if self.features[Features.BIKE_LANE]:
            hazards.append("a bike lane")

        if len(hazards) == 1:
            description += f", with {hazards[0]}"
        elif len(hazards) > 1:
            description += f", with {', '.join(hazards[:-1])} and {hazards[-1]}"

        return description


class Street:
    def __init__(self, index: int, name: str, edges: List[Edge]) -> None:
        self.index = index
        self.name = name
        self.edges = edges

    @property
    def id(self) -> str:
        return f"s{self.index}"

    def __str__(self) -> str:
        return self.id

    def __eq__(self, other: Any) -> bool:
        return bool(self.index == other.index)
