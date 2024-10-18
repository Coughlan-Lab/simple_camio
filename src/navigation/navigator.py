from abc import ABC, abstractmethod
from enum import Enum
from typing import Protocol

from src.graph import Graph, WayPoint
from src.position import PositionInfo
from src.utils import Coords


class NavigationAction(Enum):
    NEW_ROUTE = 1
    WAYPOINT_REACHED = 2
    DESTINATION_REACHED = 3
    ANNOUNCE_DIRECTION = 4
    WRONG_DIRECTION = 5


class ActionHandler(Protocol):
    def __call__(self, action: "NavigationAction", **kwargs) -> None: ...


class Navigator(ABC):
    def __init__(
        self,
        graph: Graph,
        on_action: ActionHandler,
    ) -> None:
        self.graph = graph
        self.on_action = on_action

        self._running = False

    def start(self) -> None:
        self._running = True

    def is_running(self) -> bool:
        return self._running

    @abstractmethod
    def update(self, position: PositionInfo, ignore_not_moving: bool) -> None:
        pass

    def _new_route_needed(self, start: Coords, destination: Coords) -> None:
        self.on_action(
            NavigationAction.NEW_ROUTE,
            start=start,
            destination=destination,
        )

    def _waypoint_reached(self, waypoint: WayPoint) -> None:
        self.on_action(NavigationAction.WAYPOINT_REACHED, waypoint=waypoint)

    def _destination_reached(self, waypoint: WayPoint) -> None:
        self._running = False
        self.on_action(NavigationAction.DESTINATION_REACHED, waypoint=waypoint)

    def _wrong_direction(self) -> None:
        self.on_action(NavigationAction.WRONG_DIRECTION)

    def _announce_directions(self, instructions: str) -> None:
        self.on_action(NavigationAction.ANNOUNCE_DIRECTION, instructions=instructions)
