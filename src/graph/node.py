from typing import Any, Dict, List, Optional, Union

from src.utils import StrEnum

from .coords import Coords, Position


class Features(StrEnum):
    ON_BORDER = "on_border"
    CROSSWALK = "crosswalk"
    WALK_LIGHT = "walk_light"
    WALK_LIGHT_DURATION = "walk_light_duration"
    ROUND_ABOUT = "round-about"
    STREET_WIDTH = "street_width"
    TACTILE_PAVING = "tactile_paving"


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
        return bool(self.features.get(Features.ON_BORDER, False))

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
            description += f", {street_width} feets wide"

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
