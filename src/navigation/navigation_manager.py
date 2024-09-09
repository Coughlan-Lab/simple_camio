from typing import List, Optional

from src.graph import Graph, PositionInfo, WayPoint

from .navigator import Navigator
from .step_by_step_navigator import StepByStepNavigator


def on_action_placeholder(action: "NavigationManager.Action", **kwargs) -> None:
    return


class NavigationManager:
    ARRIVED_THRESHOLD = 0.35  # inch

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
