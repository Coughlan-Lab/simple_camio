import time
from typing import Optional, Union

from src.utils import ArithmeticBuffer, Buffer

from .coords import Coords
from .edge import Edge
from .graph import Graph
from .node import Node


class Announcement:
    def __init__(
        self, text: str, pos: Coords, graph_nearest: Optional[Union[Node, Edge]]
    ) -> None:
        self.text = text
        self.pos = pos
        self.graph_nearest = graph_nearest
        self.time = time.time()

    @staticmethod
    def none_announcement(pos: Coords = Coords(0, 0)) -> "Announcement":
        return Announcement("", pos, None)


NONE_ANNOUNCEMENT = Announcement.none_announcement()


class PositionHandler:
    MAP_MARGIN = 50
    NODE_DISTANCE_THRESHOLD = 20
    EDGE_DISTANCE_THRESHOLD = 20
    SILENCE_BETWEEN_ANNOUNCEMENTS = 1.5

    def __init__(self, graph: Graph, meters_per_pixel: float) -> None:
        self.graph = graph
        self.min_corner, self.max_corner = self.graph.bounds
        self.min_corner -= PositionHandler.MAP_MARGIN
        self.max_corner += PositionHandler.MAP_MARGIN

        self.meters_per_pixel = meters_per_pixel

        self.positions_buffer = ArithmeticBuffer[Coords](max_size=3)
        self.edge_buffer = Buffer[Edge](max_size=10)

        self.last_announcement: Announcement = NONE_ANNOUNCEMENT

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

    def get_next_announcement(self) -> Optional[Announcement]:
        if (
            time.time() - self.last_announcement.time
            < PositionHandler.SILENCE_BETWEEN_ANNOUNCEMENTS
        ):
            return None

        last_pos = self.positions_buffer.last()
        avg_pos = self.positions_buffer.average()

        if last_pos is None or avg_pos is None:
            return None

        to_announce: Announcement = Announcement.none_announcement(avg_pos)

        nearest_node, distance = self.graph.get_nearest_node(avg_pos)

        # print(f"N: {nearest_node}, D: {distance}")

        if distance <= PositionHandler.NODE_DISTANCE_THRESHOLD:
            to_announce = Announcement(nearest_node.description, avg_pos, nearest_node)

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
                if self.last_announcement.graph_nearest != nearest_edge:
                    to_announce = Announcement(
                        nearest_edge.description, avg_pos, nearest_edge
                    )
                else:
                    moving_towards_node2 = self.get_movement_direction(nearest_edge)
                    to_announce = Announcement(
                        nearest_edge.get_complete_description(moving_towards_node2),
                        avg_pos,
                        nearest_edge,
                    )
            else:
                to_announce = Announcement.none_announcement(avg_pos)

        if to_announce.text == self.last_announcement.text:
            return None

        self.last_announcement = to_announce
        return to_announce

    def get_movement_direction(self, edge: Edge) -> Optional[bool]:
        a = edge[1].coords - edge[0].coords
        b = (
            self.positions_buffer.average() or Coords(0, 0)
        ) - self.last_announcement.pos

        dot = a.dot_product(b)
        if dot == 0:
            return None
        return dot > 0
