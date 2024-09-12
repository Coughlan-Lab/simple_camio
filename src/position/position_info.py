import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Optional

from src.graph import Edge, Node, PoI
from src.utils import Coords, Position


class MovementDirection(Enum):
    NONE = 0
    FORWARD = 1
    BACKWARD = 2


@dataclass(frozen=True)
class PositionInfo:
    DEFAULT_MAX_LIFE: ClassVar[float] = 6.0  # seconds
    NONE: ClassVar["PositionInfo"]

    real_pos: Coords = field()
    graph_element: Optional[Position] = field(default=None)
    description: str = field(default="")
    movement: MovementDirection = field(default=MovementDirection.NONE)
    max_life: float = field(default=DEFAULT_MAX_LIFE)
    timestamp: float = field(default_factory=time.time)

    @property
    def distance(self) -> float:
        return self.get_distance_to_graph_element(self.real_pos)

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

    @property
    def complete_description(self) -> str:
        if self.graph_element is None:
            return ""

        return self.graph_element.get_complete_description()

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
