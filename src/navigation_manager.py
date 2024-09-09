import time
from abc import ABC, abstractmethod
from collections import deque
from enum import Enum
from typing import List, Optional, Protocol

from src.graph import (NONE_POSITION_INFO, Coords, Graph, MovementDirection,
                       PositionInfo, WayPoint)


def on_action_placeholder(action: "NavigationManager.Action", **kwargs) -> None:
    return


class NavigationManager:
    ARRIVED_THRESHOLD = 0.35  # inch

    class Action(Enum):
        NEW_ROUTE = 1
        WAYPOINT_REACHED = 2
        DESTINATION_REACHED = 3
        ANNOUNCE_STEP = 4
        WRONG_DIRECTION = 5

    def __init__(self, graph: Graph, feets_per_inch: float) -> None:
        self.arrived_threshold = self.ARRIVED_THRESHOLD * feets_per_inch

        self.on_action = on_action_placeholder
        self.graph = graph
        self.navigator: Optional[Navigator] = None

    @property
    def running(self) -> bool:
        return self.navigator is not None and self.navigator.running

    def navigate_step_by_step(
        self, waypoints: List[WayPoint], current_position: PositionInfo
    ) -> None:
        first_waypoint = waypoints[0]
        if (
            first_waypoint.coords.distance_to(current_position.real_pos)
            < self.arrived_threshold
        ):
            waypoints.pop(0)

        self.navigator = StepByStepNavigator(
            self.graph, self.arrived_threshold, self.on_action, waypoints
        )

    def navigate(self, destination: WayPoint) -> None:
        pass

    def update(self, position: PositionInfo, ignore_not_moving: bool = False) -> None:
        if self.navigator is not None:
            self.navigator.update(position, ignore_not_moving)

    def clear(self) -> None:
        if self.navigator is not None:
            self.navigator.clear()

    class ActionHandler(Protocol):
        def __call__(self, action: "NavigationManager.Action", **kwargs) -> None: ...


class Navigator(ABC):
    def __init__(
        self,
        graph: Graph,
        arrived_threshold: float,
        on_action: NavigationManager.ActionHandler,
    ) -> None:
        self.graph = graph
        self.arrived_threshold = arrived_threshold
        self.on_action = on_action

    @property
    @abstractmethod
    def running(self) -> bool:
        pass

    @abstractmethod
    def update(self, position: PositionInfo, ignore_not_moving: bool) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class StepByStepNavigator(Navigator):
    NEXT_STEP_THRESHOLD = 1.5  # seconds

    def __init__(
        self,
        graph: Graph,
        arrived_threshold: float,
        on_action: NavigationManager.ActionHandler,
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
            NavigationManager.Action.NEW_ROUTE,
            start=start,
            destination=self.waypoints[-1].coords,
        )

    def __waypoint_reached(self, waypoint: WayPoint) -> None:
        self.on_action(NavigationManager.Action.WAYPOINT_REACHED, waypoint=waypoint)

    def __destination_reached(self, waypoint: WayPoint) -> None:
        self.on_action(NavigationManager.Action.DESTINATION_REACHED, waypoint=waypoint)

    def __wrong_direction(self) -> None:
        self.on_action(NavigationManager.Action.WRONG_DIRECTION)

    def __announce_step(self) -> None:
        self.on_action(
            NavigationManager.Action.ANNOUNCE_STEP, waypoint=self.waypoints[0]
        )

    def clear(self) -> None:
        self.waypoints.clear()
        self.on_waypoint = False
        self.__stop_timestamp = 0.0
        self.last_position = NONE_POSITION_INFO
        self.__waiting_new_route = False
