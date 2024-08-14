from typing import Optional

from src.utils import ArithmeticBuffer, Buffer

from .coords import Coords
from .edge import Edge
from .graph import Graph


class PositionHandler:
    MARGIN = 50
    NODE_DISTANCE_THRESHOLD = 20
    EDGE_DISTANCE_THRESHOLD = 20

    def __init__(self, graph: Graph, meters_per_pixel: float) -> None:
        self.graph = graph
        self.min_corner, self.max_corner = self.graph.bounds
        self.min_corner -= PositionHandler.MARGIN
        self.max_corner += PositionHandler.MARGIN

        self.meters_per_pixel = meters_per_pixel

        self.positions_buffer = ArithmeticBuffer[Coords](max_size=3)
        self.edge_buffer = Buffer[Edge](max_size=10)

        self.last_announced: Optional[str] = None
        self.last_position: Optional[Coords] = None

    def clear(self) -> None:
        self.positions_buffer.clear()
        self.edge_buffer.clear()

        self.last_announced = None
        self.last_position = None

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

    def get_next_announcement(self) -> Optional[str]:
        last_pos = self.positions_buffer.last()
        avg_pos = self.positions_buffer.average()

        if last_pos is None or avg_pos is None:
            return None

        to_announce: Optional[str] = None

        nearest_node, distance = self.graph.get_nearest_node(avg_pos)
        to_announce = nearest_node.description

        # print(f"N: {nearest_node}, D: {distance}")

        if distance > PositionHandler.NODE_DISTANCE_THRESHOLD:
            edge, distance = self.graph.get_nearest_edge(last_pos)
            self.edge_buffer.add(edge)
            nearest_edge = self.edge_buffer.mode()
            # print(f"E: {nearest_edge}, D: {distance}")

            if (
                nearest_edge is not None
                and last_pos.distance_to_line(nearest_edge)
                <= PositionHandler.EDGE_DISTANCE_THRESHOLD
            ):
                moving_towards_node2: Optional[bool] = None
                if self.last_announced is not None:
                    if nearest_edge.street not in self.last_announced:
                        moving_towards_node2 = None
                    else:
                        moving_towards_node2 = self.get_movement_direction(nearest_edge)

                to_announce = nearest_edge.get_description(moving_towards_node2)
            else:
                to_announce = None

        if to_announce is None or to_announce == self.last_announced:
            return None

        self.last_announced = to_announce
        self.last_position = avg_pos

        return to_announce

    def get_movement_direction(self, edge: Edge) -> Optional[bool]:
        a = edge[1].coords - edge[0].coords
        b = (self.positions_buffer.average() or Coords(0, 0)) - (
            self.last_position or Coords(0, 0)
        )

        dot = a.dot_product(b)
        if dot == 0:
            return None
        return dot > 0
