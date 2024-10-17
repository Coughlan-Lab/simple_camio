import time
from collections import deque
from typing import List

from src.graph import Graph, WayPoint
from src.position import MovementDirection, PositionInfo
from src.utils import Buffer, Coords, ArithmeticBuffer

from .navigator import ActionHandler, Navigator


class StreetByStreetNavigator(Navigator):
    NEXT_STEP_INTERVAL = 1.0  # seconds

    def __init__(
        self,
        graph: Graph,
        arrived_threshold: float,
        wrong_direction_margin: float,
        on_action: ActionHandler,
        waypoints: List[WayPoint],
    ) -> None:
        super().__init__(graph, on_action)

        self.arrived_threshold = arrived_threshold
        self.wrong_direction_margin = wrong_direction_margin

        self.__waypoints = deque(waypoints)

        self.positions_buffer = ArithmeticBuffer[Coords](max_size=10, max_life=2.0)
        self.last_position_info = PositionInfo.NONE
        self.__stop_timestamp = 0.0

        self.__on_waypoint = False
        self.__waiting_new_route = False

    def is_running(self) -> bool:
        return super().is_running() and len(self.__waypoints) > 0

    def start(self) -> None:
        if len(self.__waypoints) == 0:
            self._destination_reached(WayPoint.NONE)
            return

        super().start()

        self._announce_directions(self.__waypoints[0].instructions)
        self.__stop_timestamp = time.time()

    @property
    def average_position(self) -> Coords:
        return self.positions_buffer.average() or Coords.ZERO

    def update(self, position: PositionInfo, ignore_not_moving: bool) -> None:
        if not self.is_running():
            return

        current_time = time.time()
        if ignore_not_moving or self.__has_changed_position(position):
            self.__stop_timestamp = current_time

        if self.__waiting_new_route or position.graph_element is None:
            return

        distance = position.real_pos.distance_to(self.__waypoints[0].coords)

        current_waypoint = self.__waypoints[0]
        if distance < self.arrived_threshold:
            if len(self.__waypoints) == 1:
                self.__waypoints.popleft()
                self._destination_reached(current_waypoint)

            elif not self.__on_waypoint:
                self.__on_waypoint = True
                self._waypoint_reached(current_waypoint)

            elif current_time - self.__stop_timestamp > self.NEXT_STEP_INTERVAL:
                self.__waypoints.popleft()
                self.__stop_timestamp = current_time
                self.__on_waypoint = False
                self._announce_directions(self.__waypoints[0].instructions)

        elif current_time - self.__stop_timestamp > self.NEXT_STEP_INTERVAL:
            self.__stop_timestamp = current_time
            self._new_route_needed(position.real_pos, self.__waypoints[-1].coords)

        elif self.__moving_in_wrong_direction(position):
            self.__on_waypoint = False
            self._wrong_direction()

        else:
            self.__on_waypoint = False

        self.last_position_info = position
        self.positions_buffer.add(position.real_pos)

    def __has_changed_position(self, position: PositionInfo) -> bool:
        return (
            position.graph_element != self.last_position_info.graph_element
            or position.movement != MovementDirection.NONE
        )

    def __moving_in_wrong_direction(self, position: PositionInfo) -> bool:
        average_position = self.average_position
        if average_position == Coords.ZERO:
            return False

        current_distance = self.graph.get_distance(
            position.real_pos, self.__waypoints[0].coords
        )

        last_distance = self.graph.get_distance(
            average_position, self.__waypoints[0].coords
        )

        return current_distance > last_distance + self.wrong_direction_margin

    def _new_route_needed(self, start: Coords, destination: Coords) -> None:
        self.__waiting_new_route = True
        return super()._new_route_needed(start, destination)
