from abc import ABC, abstractmethod
from enum import Enum
from typing import Protocol

from src.graph import Graph, PositionInfo


class NavigationAction(Enum):
    NEW_ROUTE = 1
    WAYPOINT_REACHED = 2
    DESTINATION_REACHED = 3
    ANNOUNCE_STEP = 4
    WRONG_DIRECTION = 5


class ActionHandler(Protocol):
    def __call__(self, action: "NavigationAction", **kwargs) -> None: ...


class Navigator(ABC):
    def __init__(
        self,
        graph: Graph,
        arrived_threshold: float,
        on_action: ActionHandler,
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
