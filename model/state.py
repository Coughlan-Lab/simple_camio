from enum import Enum
from typing import Any, Dict, Optional

from model import Content, utils
import os
import json
import cv2


class Camera:
    def __init__(self, info: utils.CameraInfo, capture: cv2.VideoCapture):
        self.info = info
        self.capture = capture

    def __str__(self) -> str:
        return str(self.info)


class State:
    class Pointer(Enum):
        FINGER = "finger"
        STYLUS = "stylus"

    def __init__(self, config_folder: str) -> None:
        os.makedirs(config_folder, exist_ok=True)
        self.config_folder = config_folder

        self.__content_tutorial_watched = False
        self.__calibration_tutorial_watched = False

        if os.path.exists(self.config_file):
            self.__read_config()

        self.content: Optional[Content] = None
        self.pointer: Optional[State.Pointer] = None
        self.camera: Optional[Camera] = None

    def set_camera(
        self, camera_info: utils.CameraInfo, capture: cv2.VideoCapture
    ) -> None:
        self.camera = Camera(camera_info, capture)

    def set_content_tutorial_watched(self) -> None:
        if not self.__content_tutorial_watched:
            self.__content_tutorial_watched = True
            self.__save_config()

    def set_calibration_tutorial_watched(self) -> None:
        if not self.__calibration_tutorial_watched:
            self.__calibration_tutorial_watched = True
            self.__save_config()

    @property
    def config_file(self) -> str:
        return os.path.join(self.config_folder, "config.json")

    content_tutorial_watched = property(lambda self: self.__content_tutorial_watched)

    calibration_tutorial_watched = property(
        lambda self: self.__calibration_tutorial_watched
    )

    def __read_config(self) -> None:
        with open(self.config_file, "r") as f:
            config = json.load(f)

        if "config" not in config:
            return
        config = config["config"]

        self.__content_tutorial_watched = config.get("content_tutorial_watched")
        self.__calibration_tutorial_watched = config.get("calibration_tutorial_watched")

    def __save_config(self) -> None:
        config = {
            "config": {
                "content_tutorial_watched": self.__content_tutorial_watched,
                "calibration_tutorial_watched": self.__calibration_tutorial_watched,
            }
        }

        with open(self.config_file, "w") as f:
            json.dump(config, f)

    def is_calibrated(self, camera: str) -> bool:
        return os.path.exists(self.get_calibration_filename(camera))

    def save_calibration(self, calibration_data: Dict[str, Any]) -> None:
        with open(self.get_calibration_filename(), "w") as f:
            json.dump(calibration_data, f)

    def get_calibration_filename(self, camera_name: Optional[str] = None) -> str:
        if self.camera is None:
            return ""

        if camera_name is None:
            camera_name = self.camera.info.name
        if utils.SYSTEM == utils.OS.MACOS:
            camera_name = "last"

        return os.path.join(self.config_folder, f"{camera_name}_calibration.json")

    def clear(self) -> None:
        self.content = None
        self.clearPointer()
        self.clearCamera()

    def clearPointer(self) -> None:
        self.pointer = None

    def clearCamera(self) -> None:
        if self.camera is None:
            return
        if self.camera.capture.isOpened():
            self.camera.capture.release()
        self.camera = None
