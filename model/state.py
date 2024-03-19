from enum import Enum
from model.content_manager import Content
import os
import json


class State:
    class Pointer(Enum):
        FINGER = "finger"
        MARKER = "marker"

    def __init__(self, config_filepath: str) -> None:
        self.config_filepath = config_filepath

        self.__content_tutorial_watched = False
        self.__camera_tutorial_watched = False

        if os.path.exists(self.config_filepath):
            self.__read_config()

        self.content: Content
        self.pointer: State.Pointer

    def set_content_tutorial_watched(self):
        if not self.__content_tutorial_watched:
            self.__content_tutorial_watched = True
            self.__save_config()

    def set_camera_tutorial_watched(self):
        if not self.__camera_tutorial_watched:
            self.__camera_tutorial_watched = True
            self.__save_config()

    content_tutorial_watched = property(
        lambda self: self.__content_tutorial_watched
    )

    camera_tutorial_watched = property(
        lambda self: self.__camera_tutorial_watched
    )

    def __read_config(self):
        with open(self.config_filepath, "r") as f:
            config = json.load(f)

        if "config" not in config:
            return
        config = config["config"]

        self.__content_tutorial_watched = config.get(
            "content_tutorial_watched")
        self.__camera_tutorial_watched = config.get("camera_tutorial_watched")

    def __save_config(self):
        config = {
            "config": {
                "content_tutorial_watched": self.__content_tutorial_watched,
                "camera_tutorial_watched": self.__camera_tutorial_watched
            }
        }

        with open(self.config_filepath, "w") as f:
            json.dump(config, f)
