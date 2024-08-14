from typing import Any, Dict, Optional, Set, Union

from .coords import Coords


class Node:
    def __init__(
        self, index: int, coords: Coords, features: Optional[Dict[str, Any]] = None
    ) -> None:
        self.coords = coords
        self.index = index
        self.adjacents_street: Set[str] = set()

        self.features = features if features is not None else dict()
        self.on_border = self.features.get("on_border", False)

    @property
    def id(self) -> str:
        return f"n{self.index}"

    def is_dead_end(self) -> bool:
        return not self.on_border and len(self.adjacents_street) == 1

    @property
    def description(self) -> str:
        if len(self.adjacents_street) == 1:
            if self.on_border:
                return f"{next(iter(self.adjacents_street))}, at the limit of the map"
            return f"end of {next(iter(self.adjacents_street))}"

        streets = list(self.adjacents_street)
        streets_str = ", ".join(streets[:-1]) + " and " + streets[-1]

        return f"intersection between {streets_str}"

    def distance_from(self, other: Union["Node", Coords]) -> float:
        if isinstance(other, Node):
            return self.coords.distance_to(other.coords)
        return self.coords.distance_to(other)

    def manhattan_distance_from(self, other: Union["Node", Coords]) -> float:
        if isinstance(other, Node):
            return self.coords.manhattan_distance_to(other.coords)
        return self.coords.manhattan_distance_to(other)

    def __getitem__(self, index: int) -> float:
        return self.coords[index]

    def __str__(self) -> str:
        return f"{self.id}: {self.coords}"

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Node):
            return False
        return self.index == other.index
