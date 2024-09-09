import time
from collections import deque
from enum import Enum
from typing import Deque, List

from src.graph import (NONE_POSITION_INFO, Coords, MovementDirection,
                       PositionInfo, WayPoint)


def on_action_placeholder(action: "NavigationManager.Action", **kwargs) -> None:
    return


class NavigationManager:
    NEXT_STEP_THRESHOLD = 1.5  # seconds
    ARRIVED_THRESHOLD = 0.35  # inch

    class Action(Enum):
        NEW_ROUTE = 1
        WAYPOINT_REACHED = 2
        DESTINATION_REACHED = 3
        ANNOUNCE_STEP = 4

    def __init__(self, feets_per_inch: float) -> None:
        self.arrived_threshold = self.ARRIVED_THRESHOLD * feets_per_inch

        self.waypoints: Deque[WayPoint] = deque()
        self.on_action = on_action_placeholder

        self.last_position = NONE_POSITION_INFO
        self.__stop_timestamp = 0.0

        self.on_waypoint = False
        self.__waiting_new_route = False

    @property
    def running(self) -> bool:
        return len(self.waypoints) > 0

    def update(self, position: PositionInfo, ignore_not_moving: bool = False) -> None:
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

        else:
            self.on_waypoint = False

        self.last_position = position

    def navigate(
        self, waypoints: List[WayPoint], current_position: PositionInfo
    ) -> None:
        first_waypoint = waypoints[0]
        if (
            first_waypoint.coords.distance_to(current_position.real_pos)
            < self.arrived_threshold
        ):
            waypoints.pop(0)

        self.waypoints = deque(waypoints)
        self.on_waypoint = False
        self.last_position = NONE_POSITION_INFO
        self.__announce_step()
        self.__waiting_new_route = False

    def clear(self) -> None:
        self.waypoints.clear()
        self.on_waypoint = False
        self.__waiting_new_route = False
        self.__stop_timestamp = 0.0
        self.last_position = NONE_POSITION_INFO

    def __new_route_needed(self, start: Coords) -> None:
        self.__waiting_new_route = True
        self.on_action(
            self.Action.NEW_ROUTE, start=start, destination=self.waypoints[-1].coords
        )

    def __waypoint_reached(self, waypoint: WayPoint) -> None:
        self.on_action(self.Action.WAYPOINT_REACHED, waypoint=waypoint)

    def __destination_reached(self, waypoint: WayPoint) -> None:
        self.on_action(self.Action.DESTINATION_REACHED, waypoint=waypoint)

    def __announce_step(self) -> None:
        self.on_action(self.Action.ANNOUNCE_STEP, waypoint=self.waypoints[0])
