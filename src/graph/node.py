from typing import Any, Dict, List, Optional, Union

from src.utils import Coords, Position, StrEnum


class Features(StrEnum):
    ON_BORDER = "on_border"
    CROSSWALK = "crosswalk"
    WALK_LIGHT = "walk_light"
    WALK_LIGHT_DURATION = "walk_light_duration"
    ROUND_ABOUT = "round-about"
    STREET_WIDTH = "street_width"
    TACTILE_PAVING = "tactile_paving"


default_features = {
    "on_border": False,
    "crosswalk": False,
    "walk_light": False,
    "round-about": False,
    "street_width": "unknown",
    "tactile_paving": False,
}


class IntersectionType(StrEnum):
    FOUR_WAY = "four-way"
    T = "T"
    UNKNOWN = ""

    def __add__(self, other: str) -> str:
        if self == IntersectionType.UNKNOWN:
            return other
        return f"{self.value} {other}"


class Node(Position):
    def __init__(
        self, index: int, coords: Coords, features: Optional[Dict[str, Any]] = None
    ) -> None:
        self.coords = coords
        self.index = index
        self.adjacents_streets: List[str] = list()

        self.features = features if features is not None else default_features

    @property
    def id(self) -> str:
        return f"n{self.index}"

    @property
    def on_border(self) -> bool:
        return bool(self.features.get(Features.ON_BORDER, False))

    @property
    def intersection_type(self) -> IntersectionType:
        if len(self.adjacents_streets) == 4:
            return IntersectionType.FOUR_WAY

        elif not self.on_border and len(self.adjacents_streets) == 3:
            return IntersectionType.T

        return IntersectionType.UNKNOWN

    def get_short_description(self) -> str:
        if len(self.adjacents_streets) == 1:
            if self.on_border:
                return f"{self.adjacents_streets[0]}, at the limit of the map"
            return f"end of {self.adjacents_streets[0]}"

        streets = sorted(set(self.adjacents_streets))
        streets_str = streets[0]
        if len(streets) == 2:
            streets_str += f" at {streets[1]}"
        else:
            streets_str += " at " + ", ".join(streets[1:-1]) + f" and {streets[-1]}"

        return streets_str

    def get_llm_description(self) -> str:
        if len(self.adjacents_streets) == 1:
            if self.on_border:
                return f"{self.adjacents_streets[0]}, at the limit of the map"
            return f"end of {self.adjacents_streets[0]}"

        streets = list(set(self.adjacents_streets))
        streets_str = ", ".join(streets[:-1]) + " and " + streets[-1]

        return self.intersection_type + "intersection of " + streets_str

    def get_complete_description(self) -> str:
        description = self.get_llm_description()

        if self.on_border:
            description += ", at the limit of the map"

        tactile_paving = self.features.get(Features.TACTILE_PAVING, False)
        crosswalk = self.features.get(Features.CROSSWALK, False)
        walk_light = self.features.get(Features.WALK_LIGHT, False)
        walk_light_duration = self.features.get(Features.WALK_LIGHT_DURATION, "unknown")
        street_width = self.features.get(Features.STREET_WIDTH, "unknown")

        if tactile_paving or crosswalk:
            description += (
                ", with tactile paving" if tactile_paving else ", with crosswalks"
            )
            if walk_light:
                description += f" and walk lights"
                if walk_light_duration != "unknown":
                    description += f" that last {walk_light_duration} seconds"

        if street_width != "unknown":
            description += f", {street_width} feet wide"

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

    def is_on_same_street(self, other: "Node") -> bool:
        return bool(set(self.adjacents_streets) & set(other.adjacents_streets))

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
