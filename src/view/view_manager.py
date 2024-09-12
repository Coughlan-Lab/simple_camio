# type: ignore
import time
from typing import List

import cv2
import numpy as np
import numpy.typing as npt

from src.config import config
from src.graph import PoI
from src.modules_repository import Module
from src.position import PositionInfo
from src.utils import Coords


class FPSManager:
    def __init__(self) -> None:
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0.0

    def update(self) -> float:
        current_time = time.time()
        self.frame_count += 1
        elapsed_time = current_time - self.last_time

        if elapsed_time > 1.0:
            self.fps = self.frame_count / elapsed_time
            self.frame_count = 0
            self.last_time = current_time

        return self.fps

    def clear(self) -> None:
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0.0


class ViewManager(Module):
    def __init__(self, points_of_interest: List[PoI]) -> None:
        super().__init__()

        self.pois = points_of_interest

        self.fps_manager = FPSManager()

        self.template: npt.NDArray[np.uint8]
        self.waypoints: List[Coords] = list()

        if config.debug:
            self.template = cv2.imread(config.template_path, cv2.IMREAD_COLOR)

    @property
    def window_name(self) -> str:
        return config.name

    def update(self, frame: npt.NDArray[np.uint8], position: PositionInfo) -> None:
        self.fps_manager.update()

        if config.debug:
            self.__draw_debug_info(position)

        cv2.imshow(self.window_name, frame)
        cv2.waitKey(1)  # Necessary for the window to show

    def close(self) -> None:
        self.waypoints.clear()
        self.fps_manager.clear()
        cv2.destroyAllWindows()

    def __draw_debug_info(self, position: PositionInfo) -> None:
        template = self.template.copy()

        cv2.putText(
            template,
            f"FPS: {self.fps_manager.fps:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            2,
        )

        if len(self.waypoints) > 0:
            color_step = 155 // len(self.waypoints)
            for i, waypoint in enumerate(self.waypoints):
                x, y = waypoint / config.feets_per_pixel
                x, y = int(x), int(y)
                cv2.circle(template, (x, y), 10, (0, 100 + i * color_step, 0), -1)

        for poi in self.pois:
            if poi.enabled:
                x, y = poi.coords / config.feets_per_pixel
                x, y = int(x), int(y)
                cv2.circle(template, (x, y), 10, (0, 0, 255), -1)

        border = -1 if position.is_still_valid() else 2

        snapped_pos = position.snap_to_graph() / config.feets_per_pixel
        snapped_x, snapped_y = int(snapped_pos.x), int(snapped_pos.y)
        cv2.circle(template, (snapped_x, snapped_y), 10, (28, 172, 255), border)

        pos = position.real_pos / config.feets_per_pixel
        x, y = int(pos.x), int(pos.y)
        cv2.circle(template, (x, y), 10, (255, 0, 0), border)

        cv2.line(template, (snapped_x, snapped_y), (x, y), (0, 0, 0), 4)

        cv2.imshow(f"{self.window_name} - Debug", template)

    def clear_waypoints(self) -> None:
        self.waypoints.clear()

    def add_waypoint(self, coords: Coords) -> None:
        self.waypoints.append(coords)
