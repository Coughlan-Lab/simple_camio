import threading as th
from typing import List, Optional

from src.config import config
from src.graph import Graph, WayPoint
from src.modules_repository import ModulesRepository
from src.position import PositionInfo

from .fly_over_navigator import FlyOverNavigator
from .navigator import ActionHandler, NavigationAction, Navigator
from .street_by_street_navigator import StreetByStreetNavigator


class NavigationController:
    ARRIVED_THRESHOLD = 0.3  # inch
    FAR_THRESHOLD = 4.0  # inch
    WRONG_DIRECTION_MARGIN = 0.2  # inch

    def __init__(self, repository: ModulesRepository, on_action: ActionHandler) -> None:
        self.repository = repository

        self.arrived_threshold = self.ARRIVED_THRESHOLD * config.feets_per_inch
        self.far_threshold = self.FAR_THRESHOLD * config.feets_per_inch
        self.wrong_direction_margin = (
            self.WRONG_DIRECTION_MARGIN * config.feets_per_inch
        )

        self.on_action = on_action
        self.navigator: Optional[Navigator] = None

        self.__lock = th.RLock()

    def __on_action(self, action: "NavigationAction", **kwargs) -> None:
        if action == NavigationAction.DESTINATION_REACHED:
            self.clear()
        self.on_action(action, **kwargs)

    def is_navigation_running(self) -> bool:
        return self.navigator is not None

    def navigate_street_by_street(self, waypoints: List[WayPoint]) -> bool:
        print("Starting street by street navigation")
        if len(waypoints) == 0:
            return False

        with self.__lock:
            self.navigator = StreetByStreetNavigator(
                self.__graph,
                self.arrived_threshold,
                self.wrong_direction_margin,
                self.__on_action,
                waypoints,
            )

        return True

    def navigate(self, destination: WayPoint) -> bool:
        print("Starting fly-me-there navigation")

        with self.__lock:
            self.navigator = FlyOverNavigator(
                self.__graph,
                self.arrived_threshold,
                self.far_threshold,
                self.__on_action,
                destination,
            )

        return True

    def update(self, position: PositionInfo, ignore_not_moving: bool = False) -> None:
        if self.navigator is None:
            return

        with self.__lock:
            if self.navigator is None:
                return

            if not self.navigator.is_running():
                # ignore_not_moving is used to avoid starting the navigator when the LLM or the TTS are running
                if not ignore_not_moving:
                    self.navigator.start(position)

            elif self.navigator.is_running():
                self.navigator.update(position, ignore_not_moving)

    def clear(self) -> None:
        with self.__lock:
            self.navigator = None

    @property
    def __graph(self) -> Graph:
        return self.repository[Graph]
