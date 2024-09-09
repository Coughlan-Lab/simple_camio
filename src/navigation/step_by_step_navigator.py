import time
from collections import deque
from typing import List

from src.graph import (NONE_POSITION_INFO, Coords, Graph, MovementDirection,
                       PositionInfo, WayPoint)

from .navigator import ActionHandler, NavigationAction, Navigator


class StepByStepNavigator(Navigator):
    NEXT_STEP_THRESHOLD = 1.5  # seconds

    def __init__(
        self,
        graph: Graph,
        arrived_threshold: float,
        on_action: ActionHandler,
        waypoints: List[WayPoint],
    ) -> None:
        super().__init__(graph, arrived_threshold, on_action)

        self.waypoints = deque(waypoints)

        self.last_position = NONE_POSITION_INFO
        self.__stop_timestamp = 0.0

        self.on_waypoint = False
        self.__waiting_new_route = False

        self.__announce_step()

    @property
    def running(self) -> bool:
        return len(self.waypoints) > 0

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
                self.clear()
                self.__destination_reached(current_waypoint)

            elif not self.on_waypoint:
                self.on_waypoint = True
                self.__waypoint_reached(current_waypoint)

            elif current_time - self.__stop_timestamp > self.NEXT_STEP_THRESHOLD:
                self.waypoints.popleft()
                self.__stop_timestamp = current_time
                self.on_waypoint = False
                self.__announce_step()

        elif current_time - self.__stop_timestamp > self.NEXT_STEP_THRESHOLD:
            self.__stop_timestamp = current_time
            self.__new_route_needed(position.real_pos)

        elif position.movement != MovementDirection.NONE and self.graph.get_distance(
            position.real_pos, current_waypoint.coords
        ) > self.graph.get_distance(
            self.last_position.real_pos, current_waypoint.coords
        ):
            self.on_waypoint = False
            self.__wrong_direction()

        else:
            self.on_waypoint = False

        self.last_position = position

    def __new_route_needed(self, start: Coords) -> None:
        self.__waiting_new_route = True
        self.on_action(
            NavigationAction.NEW_ROUTE,
            start=start,
            destination=self.waypoints[-1].coords,
        )

    def __waypoint_reached(self, waypoint: WayPoint) -> None:
        self.on_action(NavigationAction.WAYPOINT_REACHED, waypoint=waypoint)

    def __destination_reached(self, waypoint: WayPoint) -> None:
        self.on_action(NavigationAction.DESTINATION_REACHED, waypoint=waypoint)

    def __wrong_direction(self) -> None:
        self.on_action(NavigationAction.WRONG_DIRECTION)

    def __announce_step(self) -> None:
        self.on_action(NavigationAction.ANNOUNCE_STEP, waypoint=self.waypoints[0])

    def clear(self) -> None:
        self.waypoints.clear()
        self.on_waypoint = False
        self.__stop_timestamp = 0.0
        self.last_position = NONE_POSITION_INFO
        self.__waiting_new_route = False
