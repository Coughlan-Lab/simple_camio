import math
import time
from enum import Enum
from typing import Optional

from src.graph import Edge, Node, PoI
from src.utils import Coords, Position


class MovementDirection(Enum):
    NONE = 0
    FORWARD = 1
    BACKWARD = 2


class PositionInfo:
    NONE: "PositionInfo"

    DEFAULT_MAX_LIFE = 6.0  # seconds

    def __init__(
        self,
        real_pos: Coords,
        graph_element: Optional[Position] = None,
        description: str = "",
        movement: MovementDirection = MovementDirection.NONE,
        max_life: float = DEFAULT_MAX_LIFE,
    ) -> None:
        self.description = description
        self.real_pos = real_pos
        self.graph_element = graph_element
        self.distance = self.get_distance_to_graph_element(real_pos)
        self.movement = movement

        self.max_life = max_life
        self.timestamp = time.time()

    def get_distance_to_graph_element(self, pos: Coords) -> float:
        if self.graph_element is None:
            return math.inf

        return self.graph_element.distance_to(pos)

    def is_still_valid(self) -> bool:
        return time.time() - self.timestamp < self.max_life

    def snap_to_graph(self) -> Coords:
        if self.graph_element is None:
            return self.real_pos

        return self.graph_element.closest_point(self.real_pos)

    def is_node(self) -> bool:
        return isinstance(self.graph_element, Node)

    def is_edge(self) -> bool:
        return isinstance(self.graph_element, Edge)

    def is_poi(self) -> bool:
        return isinstance(self.graph_element, PoI)

    def __str__(self) -> str:
        return self.description

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def copy(info: "PositionInfo", pos: Coords) -> "PositionInfo":
        return PositionInfo(
            pos, info.graph_element, info.description, max_life=info.max_life
        )


PositionInfo.NONE = PositionInfo(Coords.ZERO)
