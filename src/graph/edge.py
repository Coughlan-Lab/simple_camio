from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .coords import Coords, StraightLine
from .node import Node


class MovementDirection(Enum):
    NONE = 0
    FORWARD = 1
    BACKWARD = 2


class Edge(StraightLine):
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
        self.length = self.node1.distance_from(self.node2)

    @property
    def id(self) -> str:
        return f"{self.node1.id} - {self.node2.id}"

    @property
    def description(self) -> str:
        description = self.street

        if (surface := self.features.get("surface", "concrete")) != "concrete":
            description += f", {surface}"

        if self.node1.is_dead_end() or self.node2.is_dead_end():
            description += ", dead end"

        return description

    def get_complete_description(
        self, movement_direction: MovementDirection = MovementDirection.NONE
    ) -> str:
        description = self.description
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
            self.node1[0] <= coords[0] <= self.node2[0]
            or self.node2[0] <= coords[0] <= self.node1[0]
            or self.node1[1] <= coords[1] <= self.node2[1]
            or self.node2[1] <= coords[1] <= self.node1[1]
        )

    def is_adjacent(self, other: "Edge") -> bool:
        return (
            self.node1 == other.node1
            or self.node1 == other.node2
            or self.node2 == other.node1
            or self.node2 == other.node2
        )

    def __getitem__(self, index: int) -> Node:
        return self.node1 if index == 0 else self.node2

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
