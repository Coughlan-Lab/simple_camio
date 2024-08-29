import math
import time
from typing import Optional, Tuple, Union

from src.utils import ArithmeticBuffer, Buffer

from .coords import Coords
from .edge import Edge, MovementDirection
from .graph import Graph, PoI
from .node import Node


class PositionData:
    def __init__(
        self,
        description: str,
        pos: Coords,
        graph_nearest: Optional[Union[Node, Edge, PoI]],
    ) -> None:
        self.description = description
        self.pos = pos
        self.graph_nearest_element = graph_nearest
        self.time = time.time()
        self.__init_distance()

    def __init_distance(self) -> None:
        self.distance = math.inf

        if isinstance(self.graph_nearest_element, Node):
            self.distance = self.graph_nearest_element.distance_to(self.pos)

        elif isinstance(self.graph_nearest_element, Edge):
            self.distance = self.graph_nearest_element.distance_from(self.pos)

        elif isinstance(self.graph_nearest_element, dict):
            self.distance = self.graph_nearest_element["coords"].distance_to(self.pos)

    @staticmethod
    def none_announcement(
        pos: Coords = Coords(0, 0), graph_nearest: Optional[Union[Node, Edge]] = None
    ) -> "PositionData":
        return PositionData("", pos, graph_nearest)

    def __len__(self) -> int:
        return len(self.description)


NONE_ANNOUNCEMENT = PositionData.none_announcement()


class PositionHandler:
    MAP_MARGIN = 50
    MOVEMENT_THRESHOLD = 10
    COORS_DISTANCE_THRESHOLD = 25
    EDGE_DISTANCE_THRESHOLD = 20

    def __init__(self, graph: Graph, meters_per_pixel: float) -> None:
        self.graph = graph
        self.min_corner, self.max_corner = self.graph.bounds
        self.min_corner -= PositionHandler.MAP_MARGIN
        self.max_corner += PositionHandler.MAP_MARGIN

        self.meters_per_pixel = meters_per_pixel

        self.positions_buffer = ArithmeticBuffer[Coords](max_size=3)
        self.edge_buffer = Buffer[Edge](max_size=10)

        self.last_announcement = NONE_ANNOUNCEMENT

    def clear(self) -> None:
        self.positions_buffer.clear()
        self.edge_buffer.clear()

        self.last_announcement = NONE_ANNOUNCEMENT

    @property
    def last_position(self) -> Coords:
        return self.last_announcement.pos

    @property
    def current_position(self) -> Optional[Coords]:
        return self.positions_buffer.average()

    def process_position(self, pos: Coords) -> None:
        pos *= self.meters_per_pixel

        # print(f"Position detected: {pos}")

        if (
            self.min_corner[0] <= pos.x < self.max_corner[0]
            and self.min_corner[1] <= pos.y < self.max_corner[1]
        ):
            self.positions_buffer.add(pos)

            edge, _ = self.graph.get_nearest_edge(pos)
            self.edge_buffer.add(edge)

    def get_next_announcement(self) -> PositionData:
        def implementation() -> PositionData:
            node_announcement = self.get_node_announcement()
            poi_announcement = self.get_poi_announcement()

            announcement = (
                node_announcement
                if node_announcement.distance <= poi_announcement.distance
                else poi_announcement
            )
            if announcement.distance <= PositionHandler.COORS_DISTANCE_THRESHOLD:
                return announcement

            edge_announcement = self.edge_announcement()
            if edge_announcement.distance <= PositionHandler.EDGE_DISTANCE_THRESHOLD:
                return edge_announcement

            return PositionData.none_announcement(self.current_position or Coords(0, 0))

        announcement = implementation()
        self.last_announcement = announcement
        return announcement

    def get_node_announcement(self) -> PositionData:
        pos = self.current_position
        if pos is None:
            return NONE_ANNOUNCEMENT

        nearest_node, distance = self.graph.get_nearest_node(pos)

        if distance <= PositionHandler.COORS_DISTANCE_THRESHOLD:
            return PositionData(nearest_node.description, pos, nearest_node)

        return NONE_ANNOUNCEMENT

    def get_poi_announcement(self) -> PositionData:
        pos = self.current_position
        if pos is None:
            return NONE_ANNOUNCEMENT

        nearest_poi, distance = self.graph.get_nearest_poi(pos)

        if nearest_poi is None:
            return NONE_ANNOUNCEMENT

        if distance <= PositionHandler.COORS_DISTANCE_THRESHOLD:
            return PositionData(nearest_poi["name"], pos, nearest_poi)

        return NONE_ANNOUNCEMENT

    def edge_announcement(self) -> PositionData:
        pos = self.positions_buffer.last()
        nearest_edge = self.edge_buffer.mode()

        if pos is None or nearest_edge is None:
            return NONE_ANNOUNCEMENT

        distance_edge = pos.distance_to_line(nearest_edge)

        if distance_edge > PositionHandler.EDGE_DISTANCE_THRESHOLD:
            return NONE_ANNOUNCEMENT

        movement_dir = self.get_movement_direction(nearest_edge)

        if (
            movement_dir == MovementDirection.NONE
            and self.last_announcement.graph_nearest_element == nearest_edge
        ):
            # no movement and still on the same edge -> same announcement
            return PositionData(self.last_announcement.description, pos, nearest_edge)

        return PositionData(
            nearest_edge.get_complete_description(movement_dir), pos, nearest_edge
        )

    def get_movement_direction(self, edge: Edge) -> MovementDirection:
        current_position = self.current_position
        if current_position is None:
            return MovementDirection.NONE

        movement_vector = current_position - self.last_position

        if movement_vector.length() < PositionHandler.MOVEMENT_THRESHOLD:
            return MovementDirection.NONE

        edge_versor = (edge[1].coords - edge[0].coords).normalized()
        dot = edge_versor.dot_product(movement_vector.normalized())

        if abs(dot) < 0.5:  # Angle greater than 60 degrees
            return MovementDirection.NONE
        return MovementDirection.FORWARD if dot > 0 else MovementDirection.BACKWARD
