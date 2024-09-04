import math
import time
from typing import Optional, Union

from src.utils import ArithmeticBuffer

from .coords import ZERO as Coords_ZERO
from .coords import Coords, WithDistance
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
        graph_element: Optional[WithDistance],
        max_life: float = MAX_LIFE_DEFAULT,
    ) -> None:
        self.description = description
        self.pos = pos
        self.graph_element = graph_element
        self.distance = self.get_distance_to_graph_element(pos)

        self.max_life = max_life
        self.timestamp = time.time()

        self.valid = True

    def get_distance_to_graph_element(self, pos: Coords) -> float:
        if self.graph_element is None:
            return math.inf

        return self.graph_element.distance_to(pos)

    def is_still_valid(self) -> bool:
        return self.valid and time.time() - self.timestamp < self.max_life

    def invalidate(self) -> None:
        self.valid = False

    def is_node(self) -> bool:
        return isinstance(self.graph_element, Node)

    def is_edge(self) -> bool:
        return isinstance(self.graph_element, Edge)

    def is_poi(self) -> bool:
        return isinstance(self.graph_element, PoI)

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

    EDGES_MIN_DISTANCE = 0.5  # cm
    NODES_MIN_DISTANCE = 0.25  # cm
    POIS_MIN_DISTANCE = 0.5  # cm

    GRAVITY_EFFECT = 0.25  # cm
    MOVEMENT_THRESHOLD = 0.5  # cm

    def __init__(
        self, graph: Graph, meters_per_pixel: float, meters_per_cm: float
    ) -> None:
        self.meters_per_pixel = meters_per_pixel
        self.meters_per_cm = meters_per_cm

        self.map_margin = self.__to_meters(PositionHandler.MAP_MARGIN)
        self.movement_threshold = self.__to_meters(PositionHandler.MOVEMENT_THRESHOLD)
        self.edges_min_distance = self.__to_meters(PositionHandler.EDGES_MIN_DISTANCE)
        self.nodes_min_distance = self.__to_meters(PositionHandler.NODES_MIN_DISTANCE)
        self.pois_min_distance = self.__to_meters(PositionHandler.POIS_MIN_DISTANCE)
        self.points_gravity = self.__to_meters(PositionHandler.GRAVITY_EFFECT)

        self.graph = graph
        self.min_corner, self.max_corner = self.graph.bounds
        self.min_corner -= self.map_margin
        self.max_corner += self.map_margin

        self.positions_buffer = ArithmeticBuffer[Coords](
            max_size=20  # should be set to target FPS
        )

        self.last_info = NONE_INFO

    def clear(self) -> None:
        self.positions_buffer.clear()
        self.last_info = NONE_INFO

    @property
    def last_position(self) -> Optional[Coords]:
        return self.positions_buffer.first()

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

        if self.is_valid_position(pos):
            self.positions_buffer.add(pos)
            return True

        return False

    def get_position_info(self) -> PositionInfo:
        def implementation() -> PositionInfo:
            pos = self.current_position
            if pos is None:
                return NONE_INFO

            if self.__should_stick_to_last(pos):
                return PositionInfo.copy(self.last_info, pos)

            nearest_node_info = self.get_nearest_node_info()
            nearest_poi_info = self.get_nearest_poi_info()

            if (
                nearest_node_info.distance < nearest_poi_info.distance
                and nearest_node_info.distance <= self.nodes_min_distance
            ):
                self.last_info = nearest_node_info
                return nearest_node_info
            elif nearest_poi_info.distance <= self.pois_min_distance:
                self.last_info = nearest_poi_info
                return nearest_poi_info

            nearest_edge_info = self.get_nearest_edge_info()
            if nearest_edge_info.distance <= self.edges_min_distance:
                return nearest_edge_info

            return PositionInfo.none_info(pos)

        announcement = implementation()
        self.last_info = announcement
        return announcement

    def __should_stick_to_last(self, pos: Coords) -> bool:
        if not self.last_info.is_node() and not self.last_info.is_poi():
            return False

        base_distance = (
            self.nodes_min_distance
            if self.last_info.is_node()
            else self.pois_min_distance
        )

        return (
            self.last_info.get_distance_to_graph_element(pos)
            <= base_distance + self.points_gravity
        )

    def get_nearest_node_info(self) -> PositionInfo:
        pos = self.current_position
        if pos is None:
            return NONE_INFO

        nearest_node, distance = self.graph.get_nearest_node(pos)

        if distance > self.nodes_min_distance:
            return NONE_INFO

        return PositionInfo(nearest_node.description, pos, nearest_node)

    def get_nearest_poi_info(self) -> PositionInfo:
        pos = self.current_position
        if pos is None:
            return NONE_INFO

        nearest_poi, distance = self.graph.get_nearest_poi(pos)

        if nearest_poi is None or distance > self.pois_min_distance:
            return NONE_INFO

        return PositionInfo(nearest_poi.name, pos, nearest_poi)

    def get_nearest_edge_info(self) -> PositionInfo:
        pos = self.positions_buffer.last()
        if pos is None:
            return NONE_INFO

        nearest_edge, distance_edge = self.graph.get_nearest_edge(pos)
        if distance_edge > self.edges_min_distance:
            return NONE_INFO

        movement_dir = self.get_movement_direction(nearest_edge)
        if (
            self.last_info.graph_element == nearest_edge
            and movement_dir == MovementDirection.NONE
        ):
            # no movement and still on the same edge -> same announcement
            # this prevents the system from announcing the street name as soon as the user stops
            return PositionInfo.copy(self.last_info, pos)

        return PositionInfo(
            nearest_edge.get_complete_description(movement_dir), pos, nearest_edge
        )

    def get_movement_direction(self, edge: Edge) -> MovementDirection:
        if not self.last_info.is_still_valid():
            return MovementDirection.NONE

        current_position = self.current_position
        if current_position is None:
            return MovementDirection.NONE

        last_position = self.last_position
        if last_position is None:
            return MovementDirection.NONE

        movement_vector = current_position - last_position
        if movement_vector.length() < self.movement_threshold:
            return MovementDirection.NONE

        edge_versor = (edge[1].coords - edge[0].coords).normalized()
        dot = edge_versor.dot_product(movement_vector.normalized())

        if abs(dot) < 0.5:  # Angle greater than 60 degrees
            return MovementDirection.NONE
        return MovementDirection.FORWARD if dot > 0 else MovementDirection.BACKWARD

    def __to_meters(self, value: float) -> float:
        return value * self.meters_per_cm
