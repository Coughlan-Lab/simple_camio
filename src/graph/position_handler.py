import time
from typing import Optional, Union

from src.utils import ArithmeticBuffer, Buffer

from .coords import Coords
from .edge import Edge, MovementDirection
from .graph import Graph
from .node import Node


class PositionData:
    def __init__(
        self, description: str, pos: Coords, graph_nearest: Optional[Union[Node, Edge]]
    ) -> None:
        self.description = description
        self.pos = pos
        self.graph_nearest_element = graph_nearest
        self.time = time.time()

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
    NODE_DISTANCE_THRESHOLD = 25
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

    def process_position(self, pos: Coords) -> None:
        pos *= self.meters_per_pixel

        # print(f"Position detected: {pos}")

        if (
            self.min_corner[0] <= pos.x < self.max_corner[0]
            and self.min_corner[1] <= pos.y < self.max_corner[1]
        ):
            self.positions_buffer.add(pos)

    def get_current_position(self) -> Optional[Coords]:
        if self.positions_buffer.time_from_last_update < 1:
            return self.positions_buffer.average()
        return None

    def get_next_announcement(self) -> PositionData:
        last_pos = self.positions_buffer.last()
        avg_pos = self.positions_buffer.average()

        if last_pos is None or avg_pos is None:
            return NONE_ANNOUNCEMENT

        to_announce: PositionData = PositionData.none_announcement(avg_pos)

        nearest_node, distance = self.graph.get_nearest_node(avg_pos)

        # print(f"N: {nearest_node}, D: {distance}")

        if distance <= PositionHandler.NODE_DISTANCE_THRESHOLD:
            to_announce = PositionData(nearest_node.description, avg_pos, nearest_node)

        else:
            edge, distance = self.graph.get_nearest_edge(last_pos)
            self.edge_buffer.add(edge)
            nearest_edge = self.edge_buffer.mode()
            # print(f"E: {nearest_edge}, D: {distance}")

            if (
                nearest_edge is not None
                and last_pos.distance_to_line(nearest_edge)
                <= PositionHandler.EDGE_DISTANCE_THRESHOLD
            ):
                movement_dir = self.get_movement_direction(nearest_edge)

                if (
                    movement_dir != MovementDirection.NONE
                    or self.last_announcement.graph_nearest_element != nearest_edge
                ):
                    to_announce = PositionData(
                        nearest_edge.get_complete_description(movement_dir),
                        avg_pos,
                        nearest_edge,
                    )
                else:
                    to_announce = self.last_announcement
            else:
                to_announce = PositionData.none_announcement(avg_pos)

        self.last_announcement = to_announce
        return to_announce

    def get_movement_direction(self, edge: Edge) -> MovementDirection:
        position = self.positions_buffer.average() or Coords(0, 0)
        movement_vector = position - self.last_announcement.pos

        if movement_vector.length() < PositionHandler.MOVEMENT_THRESHOLD:
            return MovementDirection.NONE

        edge_versor = (edge[1].coords - edge[0].coords).normalized()
        dot = edge_versor.dot_product(movement_vector.normalized())

        if abs(dot) < 0.5:  # Angle greater than 60 degrees
            return MovementDirection.NONE
        return MovementDirection.FORWARD if dot > 0 else MovementDirection.BACKWARD
