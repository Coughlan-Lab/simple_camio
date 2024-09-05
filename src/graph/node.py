from typing import Any, Dict, List, Optional, Union

from .coords import Coords, Position


class Node(Position):
    def __init__(
        self, index: int, coords: Coords, features: Optional[Dict[str, Any]] = None
    ) -> None:
        self.coords = coords
        self.index = index
        self.adjacents_streets: List[str] = list()

        self.features = features if features is not None else dict()

    @property
    def id(self) -> str:
        return f"n{self.index}"

    @property
    def on_border(self) -> bool:
        return bool(self.features.get("on_border", False))

    @property
    def intersection_type(self) -> str:
        if len(self.adjacents_streets) == 4:
            return "four-way"

        elif not self.on_border and len(self.adjacents_streets) == 3:
            return "T"

        return ""

    def get_llm_description(self) -> str:
        if len(self.adjacents_streets) == 1:
            if self.on_border:
                return f"{self.adjacents_streets[0]}, at the limit of the map"
            return f"end of {self.adjacents_streets[0]}"

        streets = list(set(self.adjacents_streets))
        streets_str = ", ".join(streets[:-1]) + " and " + streets[-1]

        intersection_type = self.intersection_type
        if len(intersection_type) > 0:
            intersection_type += " "

        return f"{intersection_type}intersection of {streets_str}"

    def get_complete_description(self) -> str:
        description = self.get_llm_description()

        if self.on_border:
            description += ", at the limit of the map"

        return description

    def is_dead_end(self) -> bool:
        return not self.on_border and len(self.adjacents_streets) == 1

    def distance_to(self, coords: Union["Node", Coords]) -> float:
        if isinstance(coords, Node):
            return self.coords.distance_to(coords.coords)
        return self.coords.distance_to(coords)

    def manhattan_distance_to(self, other: Union["Node", Coords]) -> float:
        if isinstance(other, Node):
            return self.coords.manhattan_distance_to(other.coords)
        return self.coords.manhattan_distance_to(other)

    def closest_point(self, coords: Coords) -> Coords:
        return self.coords

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
