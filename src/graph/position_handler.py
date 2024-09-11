import math
import time
from enum import Enum
from typing import Optional

from src.graph import Coords, Coords_ZERO, Edge, Graph, Node, PoI, Position
from src.utils import ArithmeticBuffer


class MovementDirection(Enum):
    NONE = 0
    FORWARD = 1
    BACKWARD = 2


class PositionInfo:
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


NONE_INFO = PositionInfo(Coords_ZERO)


class PositionHandler:
    MAP_MARGIN = 1.0  # inch

    EDGES_MIN_DISTANCE = 0.3  # inch
    NODES_MIN_DISTANCE = 0.15  # inch
    POIS_MIN_DISTANCE = 0.25  # inch

    GRAVITY_EFFECT = 0.2  # inch
    MOVEMENT_THRESHOLD = 0.25  # inch

    def __init__(
        self, graph: Graph, feets_per_pixel: float, feets_per_inch: float
    ) -> None:
        self.feets_per_pixel = feets_per_pixel
        self.feets_per_inch = feets_per_inch

        self.map_margin = self.__to_feets(PositionHandler.MAP_MARGIN)
        self.edges_min_distance = self.__to_feets(PositionHandler.EDGES_MIN_DISTANCE)
        self.nodes_min_distance = self.__to_feets(PositionHandler.NODES_MIN_DISTANCE)
        self.pois_min_distance = self.__to_feets(PositionHandler.POIS_MIN_DISTANCE)
        self.points_gravity = self.__to_feets(PositionHandler.GRAVITY_EFFECT)
        self.movement_threshold = self.__to_feets(PositionHandler.MOVEMENT_THRESHOLD)

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
        return self.last_info.real_pos

    def is_valid_position(self, pos: Coords) -> bool:
        return (
            self.min_corner[0] <= pos.x < self.max_corner[0]
            and self.min_corner[1] <= pos.y < self.max_corner[1]
        )

    def process_position(self, pos: Coords) -> bool:
        pos *= self.feets_per_pixel

        if self.is_valid_position(pos):
            self.positions_buffer.add(pos)
            return True

        return False

    def get_position_info(self) -> PositionInfo:
        def implementation() -> PositionInfo:
            pos = self.positions_buffer.average()
            if pos is None:
                return NONE_INFO

            if self.__should_stick_to_last(pos):
                return PositionInfo.copy(self.last_info, pos)

            nearest_poi_info = self.get_nearest_poi_info(pos)
            if nearest_poi_info.distance <= self.pois_min_distance:
                return nearest_poi_info

            nearest_node_info = self.get_nearest_node_info(pos)
            if nearest_node_info.distance <= self.nodes_min_distance:
                return nearest_node_info

            nearest_edge_info = self.get_nearest_edge_info(pos)
            if nearest_edge_info.distance <= self.edges_min_distance:
                return nearest_edge_info

            return PositionInfo(pos)

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

    def get_nearest_node_info(self, pos: Coords) -> PositionInfo:
        nearest_node, distance = self.graph.get_nearest_node(pos)

        if distance > self.nodes_min_distance:
            return NONE_INFO

        return PositionInfo(
            pos,
            nearest_node,
            max_life=PositionInfo.DEFAULT_MAX_LIFE * 2,
        )  # Nodes are not immediately announced

    def get_nearest_poi_info(self, pos: Coords) -> PositionInfo:
        nearest_poi, distance = self.graph.get_nearest_poi(pos)

        if nearest_poi is None or distance > self.pois_min_distance:
            return NONE_INFO

        return PositionInfo(
            pos,
            nearest_poi,
            nearest_poi.name,
            max_life=PositionInfo.DEFAULT_MAX_LIFE * 2,
        )

    def get_nearest_edge_info(self, pos: Coords) -> PositionInfo:
        nearest_edge, distance_edge = self.graph.get_nearest_edge(pos)
        if distance_edge > self.edges_min_distance:
            return NONE_INFO

        movement_dir = self.get_movement_direction(pos, nearest_edge)
        if (
            self.last_info.graph_element == nearest_edge
            and movement_dir == MovementDirection.NONE
        ):
            # no movement and still on the same edge -> same announcement
            # this prevents the system from announcing the street name as soon as the user stops
            return PositionInfo.copy(self.last_info, pos)

        return PositionInfo(
            pos,
            nearest_edge,
            nearest_edge.street,
            movement=movement_dir,
        )

    def get_movement_direction(
        self, current_position: Coords, edge: Edge
    ) -> MovementDirection:
        if not self.last_info.is_still_valid():
            return MovementDirection.NONE

        last_position = self.last_position
        if last_position is None:
            return MovementDirection.NONE

        movement_vector = current_position - last_position
        if movement_vector.length() < self.movement_threshold:
            return MovementDirection.NONE

        edge_versor = (edge[1].coords - edge[0].coords).normalized()
        dot = edge_versor.dot(movement_vector.normalized())

        if abs(dot) < 0.5:  # Angle greater than 60 degrees
            return MovementDirection.NONE
        return MovementDirection.FORWARD if dot > 0 else MovementDirection.BACKWARD

    def __to_feets(self, value: float) -> float:
        return value * self.feets_per_inch
