import time
from collections import deque
from typing import List

from src.graph import (NONE_POSITION_INFO, Coords, Graph, MovementDirection,
                       PositionInfo, WayPoint)

from .navigator import ActionHandler, Navigator


class StepByStepNavigator(Navigator):
    NEXT_STEP_THRESHOLD = 1.5  # seconds

    def __init__(
        self,
        graph: Graph,
        arrived_threshold: float,
        far_threshold: float,
        on_action: ActionHandler,
        waypoints: List[WayPoint],
    ) -> None:
        super().__init__(graph, arrived_threshold, far_threshold, on_action)

        self.waypoints = deque(waypoints)

        self.last_position = NONE_POSITION_INFO
        self.__stop_timestamp = 0.0

        self.on_waypoint = False
        self.__waiting_new_route = False

        self._announce_directions(self.waypoints[0].instructions)

    @property
    def running(self) -> bool:
        return not self.destination_reached and len(self.waypoints) > 0

    def update(self, position: PositionInfo, ignore_not_moving: bool) -> None:
        if not self.running:
            return

        current_time = time.time()
        if (
            ignore_not_moving
            or position.graph_element != self.last_position.graph_element
            or position.movement != MovementDirection.NONE
        ):
            self.__stop_timestamp = current_time

        if self.__waiting_new_route or position.graph_element is None:
            return

        distance = position.real_pos.distance_to(self.waypoints[0].coords)

        current_waypoint = self.waypoints[0]
        if distance < self.arrived_threshold:
            if len(self.waypoints) == 1:
                self._destination_reached(current_waypoint)

            elif not self.on_waypoint:
                self.on_waypoint = True
                self._waypoint_reached(current_waypoint)

            elif current_time - self.__stop_timestamp > self.NEXT_STEP_THRESHOLD:
                self.waypoints.popleft()
                self.__stop_timestamp = current_time
                self.on_waypoint = False
                self._announce_directions(self.waypoints[0].instructions)

        elif current_time - self.__stop_timestamp > self.NEXT_STEP_THRESHOLD:
            self.__stop_timestamp = current_time
            self.__new_route_needed(position.real_pos, self.waypoints[-1].coords)

        elif position.movement != MovementDirection.NONE and self.graph.get_distance(
            position.real_pos, current_waypoint.coords
        ) > self.graph.get_distance(
            self.last_position.real_pos, current_waypoint.coords
        ):
            self.on_waypoint = False
            self._wrong_direction()

        else:
            self.on_waypoint = False

        self.last_position = position

    def __new_route_needed(self, start: Coords, destination: Coords) -> None:
        self.__waiting_new_route = True
        return super()._new_route_needed(start, destination)
