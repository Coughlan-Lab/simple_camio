from typing import List, Optional, Callable, Dict, Any

from src.config import config
from src.graph import Graph, WayPoint
from src.modules_repository import ModulesRepository
from src.position import PositionInfo

from .direct_navigator import DirectNavigator
from .navigator import Navigator
from .step_by_step_navigator import StepByStepNavigator


class NavigationController:
    ARRIVED_THRESHOLD = 0.3  # inch
    FAR_THRESHOLD = 4.0  # inch
    WRONG_DIRECTION_MARGIN = 0.2  # inch

    def __init__(
        self,
        repository: ModulesRepository,
        on_action: Callable[["NavigationController.Action", Dict[str, Any]], None],
    ) -> None:
        self.repository = repository

        self.arrived_threshold = self.ARRIVED_THRESHOLD * config.feets_per_inch
        self.far_threshold = self.FAR_THRESHOLD * config.feets_per_inch
        self.wrong_direction_margin = (
            self.WRONG_DIRECTION_MARGIN * config.feets_per_inch
        )

        self.on_action = on_action
        self.navigator: Optional[Navigator] = None

    def is_running(self) -> bool:
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
            self.__graph,
            self.arrived_threshold,
            self.wrong_direction_margin,
            self.on_action,
            waypoints,
        )

    def navigate(self, destination: WayPoint) -> None:
        self.navigator = DirectNavigator(
            self.__graph,
            self.arrived_threshold,
            self.far_threshold,
            self.on_action,
            destination,
        )

    def update(self, position: PositionInfo, ignore_not_moving: bool = False) -> None:
        if self.navigator is not None and self.navigator.running:
            self.navigator.update(position, ignore_not_moving)

    def clear(self) -> None:
        self.navigator = None

    @property
    def __graph(self) -> Graph:
        return self.repository[Graph]
