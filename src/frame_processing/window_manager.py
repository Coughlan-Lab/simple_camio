# type: ignore
from typing import List, Optional

import cv2
import numpy as np
import numpy.typing as npt

from src.graph import Coords, PositionHandler
from src.utils import FPSManager


class WindowManager:
    def __init__(
        self,
        window_name: str,
        debug_mode: bool = False,
        template_path: Optional[str] = None,
        position_handler: Optional[PositionHandler] = None,
    ) -> None:
        self.window_name = window_name
        self.fps_manager = FPSManager()
        self.debug = debug_mode

        self.template: npt.NDArray[np.uint8]
        self.position_handler: PositionHandler
        self.waypoints: List[Coords] = list()

        if self.debug:
            assert (
                template_path is not None
            ), "Template path must be provided in debug mode"
            assert (
                position_handler is not None
            ), "Position handler must be provided in debug mode"

            self.template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if self.template is None:
                raise ValueError("Template image not found")
            self.position_handler = position_handler

    def update(self, frame: npt.NDArray[np.uint8]) -> None:
        self.fps_manager.update()

        if self.debug:
            self.__draw_debug_info()

        cv2.imshow(self.window_name, frame)
        cv2.waitKey(1)  # Necessary for the window to show

    def close(self) -> None:
        self.waypoints.clear()
        self.fps_manager.clear()
        cv2.destroyAllWindows()

    def __draw_debug_info(self) -> None:
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

        for waypoint in self.waypoints:
            x, y = waypoint / self.position_handler.feets_per_pixel
            x, y = int(x), int(y)
            cv2.circle(template, (x, y), 10, (0, 255, 0), -1)

        for poi in self.position_handler.graph.pois:
            if poi.enabled:
                x, y = poi.coords / self.position_handler.feets_per_pixel
                x, y = int(x), int(y)
                cv2.circle(template, (x, y), 10, (0, 0, 255), -1)

        last_pos_info = self.position_handler.last_info
        border = -1 if last_pos_info.is_still_valid() else 2

        snapped_pos = (
            last_pos_info.snap_to_graph() / self.position_handler.feets_per_pixel
        )
        snapped_x, snapped_y = int(snapped_pos.x), int(snapped_pos.y)
        cv2.circle(template, (snapped_x, snapped_y), 10, (28, 172, 255), border)

        pos = last_pos_info.real_pos / self.position_handler.feets_per_pixel
        x, y = int(pos.x), int(pos.y)
        cv2.circle(template, (x, y), 10, (255, 0, 0), border)

        cv2.line(template, (snapped_x, snapped_y), (x, y), (0, 0, 0), 4)

        cv2.imshow(f"{self.window_name} - Debug", template)

    def clear_waypoints(self) -> None:
        self.waypoints.clear()

    def add_waypoint(self, coords: Coords) -> None:
        self.waypoints.append(coords)
