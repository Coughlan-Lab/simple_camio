from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .coords import Coords, StraightLine, WithDistance
from .node import Node


class MovementDirection(Enum):
    NONE = 0
    FORWARD = 1
    BACKWARD = 2


class Edge(StraightLine, WithDistance):
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
        self.features = features if features is not None else dict()

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

    def get_complete_description(
        self, movement_direction: MovementDirection = MovementDirection.NONE
    ) -> str:
        description = self.street

        if (surface := self.features.get("surface", "concrete")) != "concrete":
            description += f", {surface}"

        if self.node1.is_dead_end() or self.node2.is_dead_end():
            description += ", dead end"

        if movement_direction == MovementDirection.NONE:
            return description

        if (slope := self.features.get("slope", "flat")) != "flat":
            forward = (
                MovementDirection.FORWARD
                if slope == "uphill"
                else MovementDirection.BACKWARD
            )
            if forward == movement_direction:
                description += ", uphill"
            else:
                description += ", downhill"

        if (
            traffic_direction := self.features.get("traffic_direction", "two_way")
        ) != "two_way":
            forward = (
                MovementDirection.FORWARD
                if traffic_direction == "one_way_forward"
                else MovementDirection.BACKWARD
            )
            if forward == movement_direction:
                description += ", heading with traffic"
            else:
                description += ", heading against traffic"

        return description

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
