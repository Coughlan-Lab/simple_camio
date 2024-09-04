import math
import time
from typing import Optional, Protocol, TypeVar, Union

from src.utils import ArithmeticBuffer, Buffer

from .coords import ZERO as Coords_ZERO
from .coords import Coords
from .edge import Edge, MovementDirection
from .graph import Graph
from .node import Node
from .poi import PoI


class PositionInfo:
    MAX_LIFE_DEFAULT = 6.0  # seconds

    def __init__(
        self,
        description: str,
        pos: Coords,
        graph_nearest: Optional[Union[Node, Edge, PoI]],
        max_life: float = MAX_LIFE_DEFAULT,
    ) -> None:
        self.description = description
        self.pos = pos
        self.graph_element = graph_nearest
        self.distance = self.get_distance_to_graph_element(pos)

        self.max_life = max_life
        self.timestamp = time.time()

    def get_distance_to_graph_element(self, pos: Coords) -> float:
        distance = math.inf

        if isinstance(self.graph_element, Node):
            distance = self.graph_element.distance_to(pos)

        elif isinstance(self.graph_element, Edge):
            distance = self.graph_element.distance_from(pos)

        elif isinstance(self.graph_element, dict):
            distance = self.graph_element["coords"].distance_to(pos)

        return distance

    def is_still_valid(self) -> bool:
        return time.time() - self.timestamp < self.max_life

    @staticmethod
    def none_info(
        pos: Coords = Coords_ZERO,
        graph_nearest: Optional[Union[Node, Edge]] = None,
    ) -> "PositionInfo":
        return PositionInfo("", pos, graph_nearest, max_life=0.0)

    @staticmethod
    def copy(info: "PositionInfo", pos: Coords) -> "PositionInfo":
        return PositionInfo(
            info.description, pos, info.graph_element, max_life=info.max_life
        )


NONE_INFO = PositionInfo.none_info()


class PositionHandler:
    MAP_MARGIN = 2.0  # cm
    MOVEMENT_THRESHOLD = 0.15  # cm
    DISTANCE_THRESHOLD = 0.5  # cm
    BORDER_THICKNESS = 0.5  # cm

    def __init__(
        self, graph: Graph, meters_per_pixel: float, meters_per_cm: float
    ) -> None:
        self.meters_per_pixel = meters_per_pixel
        self.meters_per_cm = meters_per_cm

        self.map_margin = self.__to_meters(PositionHandler.MAP_MARGIN)
        self.movement_threshold = self.__to_meters(PositionHandler.MOVEMENT_THRESHOLD)
        self.distance_threshold = self.__to_meters(PositionHandler.DISTANCE_THRESHOLD)
        self.border_thickness = self.__to_meters(PositionHandler.BORDER_THICKNESS)

        self.graph = graph
        self.min_corner, self.max_corner = self.graph.bounds
        self.min_corner -= self.map_margin
        self.max_corner += self.map_margin

        self.positions_buffer = ArithmeticBuffer[Coords](max_size=3)
        self.edge_buffer = Buffer[Edge](max_size=10)

        self.last_info = NONE_INFO

    def clear(self) -> None:
        self.positions_buffer.clear()
        self.edge_buffer.clear()

        self.last_info = NONE_INFO

    @property
    def last_position(self) -> Coords:
        return self.last_info.pos

    @property
    def current_position(self) -> Optional[Coords]:
        return self.positions_buffer.average()

    def is_valid_position(self, pos: Coords) -> bool:
        return (
            self.min_corner[0] <= pos.x < self.max_corner[0]
            and self.min_corner[1] <= pos.y < self.max_corner[1]
        )

    def process_position(self, pos: Coords) -> bool:
        pos *= self.meters_per_pixel

        # print(f"Position detected: {pos}")

        if self.is_valid_position(pos):
            self.positions_buffer.add(pos)

            edge, _ = self.graph.get_nearest_edge(pos)
            self.edge_buffer.add(edge)

            return True

        return False

    def get_position_info(self) -> PositionInfo:
        def implementation() -> PositionInfo:
            pos = self.current_position

            in_range = (
                pos is not None
                and self.last_info.get_distance_to_graph_element(pos)
                <= self.distance_threshold + self.border_thickness
            )

            nearest_node_info = self.get_nearest_node_info()
            if (
                in_range
                and nearest_node_info.graph_element == self.last_info.graph_element
            ):
                self.last_info = PositionInfo.copy(self.last_info, pos or Coords_ZERO)
                return self.last_info

            nearest_poi_info = self.get_nearest_poi_info()
            if (
                in_range
                and nearest_poi_info.graph_element == self.last_info.graph_element
            ):
                self.last_info = PositionInfo.copy(self.last_info, pos or Coords_ZERO)
                return self.last_info

            info = (
                nearest_node_info
                if nearest_node_info.distance <= nearest_poi_info.distance
                else nearest_poi_info
            )
            if info.distance <= self.distance_threshold:
                self.last_info = info
                return info

            nearest_edge_info = self.get_nearest_edge_info()
            if nearest_edge_info.distance <= self.distance_threshold:
                return nearest_edge_info

            return PositionInfo.none_info(self.current_position or Coords_ZERO)

        announcement = implementation()
        self.last_info = announcement
        return announcement

    def get_nearest_node_info(self) -> PositionInfo:
        pos = self.current_position
        if pos is None:
            return NONE_INFO

        nearest_node, distance = self.graph.get_nearest_node(pos)

        if distance <= self.distance_threshold:
            return PositionInfo(nearest_node.description, pos, nearest_node)

        return NONE_INFO

    def get_nearest_poi_info(self) -> PositionInfo:
        pos = self.current_position
        if pos is None:
            return NONE_INFO

        nearest_poi, distance = self.graph.get_nearest_poi(pos)

        if nearest_poi is None:
            return NONE_INFO

        if distance <= self.distance_threshold:
            return PositionInfo(nearest_poi["name"], pos, nearest_poi)

        return NONE_INFO

    def get_nearest_edge_info(self) -> PositionInfo:
        pos = self.positions_buffer.last()
        nearest_edge = self.edge_buffer.mode()

        if pos is None or nearest_edge is None:
            return NONE_INFO

        distance_edge = pos.distance_to_line(nearest_edge)

        if distance_edge > self.distance_threshold:
            return NONE_INFO

        movement_dir = self.get_movement_direction(nearest_edge)

        return PositionInfo(
            nearest_edge.get_complete_description(movement_dir), pos, nearest_edge
        )

    def get_movement_direction(self, edge: Edge) -> MovementDirection:
        if not self.last_info.is_still_valid():
            return MovementDirection.NONE

        current_position = self.current_position
        if current_position is None:
            return MovementDirection.NONE

        movement_vector = current_position - self.last_position
        print(movement_vector.length())
        if movement_vector.length() < self.movement_threshold:
            return MovementDirection.NONE

        edge_versor = (edge[1].coords - edge[0].coords).normalized()
        dot = edge_versor.dot_product(movement_vector.normalized())

        if abs(dot) < 0.5:  # Angle greater than 60 degrees
            return MovementDirection.NONE
        return MovementDirection.FORWARD if dot > 0 else MovementDirection.BACKWARD

    def __to_meters(self, value: float) -> float:
        return value * self.meters_per_cm
