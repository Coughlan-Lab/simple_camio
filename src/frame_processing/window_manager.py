# type: ignore
from typing import Optional

import cv2
import numpy as np
import numpy.typing as npt

from src.graph.position_handler import PositionHandler
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
        cv2.destroyAllWindows()

    def __draw_debug_info(self) -> None:
        template = self.template.copy()
        pos = self.position_handler.current_position

        if pos is not None:
            pos /= self.position_handler.meters_per_pixel
            x, y = int(pos.x), int(pos.y)
            cv2.circle(template, (x, y), 10, (255, 0, 0), -1)

        cv2.putText(
            template,
            f"FPS: {self.fps_manager.fps:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            2,
        )

        for poi in self.position_handler.graph.pois:
            if poi.enabled:
                x, y = poi.coords / self.position_handler.meters_per_pixel
                x, y = int(x), int(y)
                cv2.circle(template, (x, y), 10, (0, 0, 255), -1)

        cv2.imshow(f"{self.window_name} - Debug", template)
