from enum import Enum
from typing import Any, Dict

from model.content_manager import Content
import os
import json
import platform


class State:
    class Pointer(Enum):
        FINGER = "finger"
        MARKER = "marker"

    class OS(Enum):
        MACOS = "Darwin"
        WINDOWS = "Windows"
        LINUX = "Linux"

    def __init__(self, config_folder: str) -> None:
        self.initOS()

        os.makedirs(config_folder, exist_ok=True)
        self.config_folder = config_folder

        self.__content_tutorial_watched = False
        self.__calibration_tutorial_watched = False

        if os.path.exists(self.config_file):
            self.__read_config()

        self.content: Content
        self.pointer: State.Pointer
        self.camera_index: int
        self.camera_name: str

    def initOS(self) -> None:
        system = platform.system()
        if system == "Darwin":
            self.os = State.OS.MACOS
        elif system == "Windows":
            self.os == State.OS.WINDOWS
        elif system.os == "Linux":
            self.os = State.OS.LINUX
        else:
            raise NotImplementedError(f"Unknown os: {system}")

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
        if self.os == State.OS.MACOS:
            camera = "last"

        return os.path.exists(
            os.path.join(self.config_folder, f"{camera}_calibration.json")
        )

    def save_calibration(self, calibration_data: Dict[str, Any]) -> None:
        camera_name = self.camera_name
        if self.os == State.OS.MACOS:
            camera_name = "last"

        with open(
            os.path.join(self.config_folder, f"{camera_name}_calibration.json"),
            "w",
        ) as f:
            json.dump(calibration_data, f)
