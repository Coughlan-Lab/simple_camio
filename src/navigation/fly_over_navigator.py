import time

from src.graph import Graph, WayPoint
from src.position import PositionInfo
from src.utils import CardinalDirection

from .navigator import ActionHandler, Navigator

directions = list(CardinalDirection.__members__.values())
north_index = directions.index(CardinalDirection.NORTH)


class FlyOverNavigator(Navigator):
    ANNOUNCEMENTS_INTERVAL = 1.25  # seconds

    def __init__(
        self,
        graph: Graph,
        arrived_threshold: float,
        far_threshold: float,
        on_action: ActionHandler,
        destination: WayPoint,
    ) -> None:
        super().__init__(graph, on_action)

        self.arrived_threshold = arrived_threshold
        self.far_threshold = far_threshold

        self.destination = destination
        self.last_announcement_timestamp = 0.0

    def update(self, position: PositionInfo, ignore_not_moving: bool) -> None:
        if not self.running:
            return

        distance = position.real_pos.distance_to(self.destination.coords)
        if distance < self.arrived_threshold:
            self._destination_reached(self.destination)
            return

        current_time = position.timestamp
        if (
            current_time - self.last_announcement_timestamp
            < self.ANNOUNCEMENTS_INTERVAL
        ):
            return

        error = self.destination.coords - position.real_pos
        max_index = max(range(2), key=lambda i: abs(error[i]))

        direction = directions[
            (north_index + (max_index + 1) * 2 + (4 if error[max_index] < 0 else 0))
            % len(directions)
        ].value

        if distance > self.far_threshold:
            direction = f"far {direction}"

        self._announce_directions(direction)

    def _announce_directions(self, instructions: str) -> None:
        self.last_announcement_timestamp = time.time()
        return super()._announce_directions(instructions)
