from enum import Enum
import os
import shutil
import json
from typing import Any, Dict, List, Union
from res import AudioManager
from . import utils


class Content:
    class ModelDimensions(Enum):
        TWO_D = "2D"
        THREE_D = "3D"

    class ModelDetectionType(Enum):
        ARUCO = "aruco"
        SIFT = "sift"

    def __init__(self, name: str, content: Dict[str, Any]) -> None:
        self.__name = name

        if "welcome_message" not in content or not os.path.exists(content["welcome_message"]):
            content["welcome_message"] = AudioManager.welcome
        if "goodbye_message" not in content or not os.path.exists(content["goodbye_message"]):
            content["goodbye_message"] = AudioManager.goodbye
        if "blipsound" not in content or not os.path.exists(content["blipsound"]):
            content["blipsound"] = AudioManager.blip
        if "map_description" in content and not os.path.exists(content["map_description"]):
            del content["map_description"]

        self.__content = content

    @property
    def name(self) -> str:
        name = self.full_name
        return name[:12] + ("..." if len(name) >= 13 else "")

    @property
    def full_name(self) -> str:
        return str(self.__content["name"])

    @property
    def description(self) -> str:
        description = str(self.__content.get("description", ""))
        return description[:65] + ("..." if len(description) >= 64 else "")

    @property
    def preview(self) -> Union[str, None]:
        if "preview" not in self.__content:
            return None

        path: str = self.__content["preview"]

        if not os.path.exists(path):
            return None
        return path

    @property
    def model_dimensions(self) -> ModelDimensions:
        model_type = self.__content["modelType"]
        if model_type == "2D_aruco_stylus":
            return Content.ModelDimensions.TWO_D
        elif model_type == "3D_sift_stylus":
            return Content.ModelDimensions.THREE_D
        elif model_type == "2D_sift_mediapipe":
            return Content.ModelDimensions.TWO_D
        elif model_type == "2d_aruco_mediapipe":
            return Content.ModelDimensions.TWO_D
        elif model_type == "3d_sift_mediapipe":
            return Content.ModelDimensions.THREE_D
        elif model_type == "3d_aruco_stylus":
            return Content.ModelDimensions.THREE_D
        elif model_type == "3d_aruco_mediapipe_object":
            return Content.ModelDimensions.THREE_D
        raise ValueError(f"Unknown model type {model_type}")

    @property
    def model_detection(self) -> ModelDetectionType:
        model_type = self.__content["modelType"]
        if model_type == "2D_aruco_stylus":
            return Content.ModelDetectionType.ARUCO
        elif model_type == "2D_sift_mediapipe":
            return Content.ModelDetectionType.SIFT
        elif model_type == "3D_sift_stylus":
            return Content.ModelDetectionType.SIFT
        elif model_type == "2d_aruco_mediapipe":
            return Content.ModelDetectionType.ARUCO
        elif model_type == "3d_sift_mediapipe":
            return Content.ModelDetectionType.SIFT
        elif model_type == "3d_aruco_stylus":
            return Content.ModelDetectionType.ARUCO
        elif model_type == "3d_aruco_mediapipe_object":
            return Content.ModelDetectionType.ARUCO
        raise ValueError(f"Unknown model type {model_type}")

    def is_2D(self) -> bool:
        return self.model_dimensions == Content.ModelDimensions.TWO_D

    def is_3D(self) -> bool:
        return not self.is_2D()

    def use_aruco(self) -> bool:
        return self.model_detection == Content.ModelDetectionType.ARUCO

    def use_sift_features(self) -> bool:
        return not self.use_aruco()

    @property
    def to_print(self) -> str:
        return os.path.join(self.__name, "toPrint.pdf")

    def as_dict(self) -> Dict[str, Any]:
        return self.__content

    def crickets(self) -> str:
        path: str = self.__content.get("crickets", "")
        if path == "" or not os.path.exists(path):
            return AudioManager.crickets
        return path

    def heartbeat(self) -> str:
        path: str = self.__content.get("heartbeat", "")
        if path == "" or not os.path.exists(path):
            return AudioManager.heartbeat
        return path


class ContentManager:
    DEFAULT_CONTENT_FOLDER_PATH = "CamIO Content"
    
    def set_content_dir(self, path: str) -> None:
        if not os.path.exists(path):
            return
        self.__has_content_dir = True
        os.chdir(path)
    
    def has_content_dir(self) -> bool:
        return self.__has_content_dir

    def __init__(self) -> None:
        self.__content: Dict[str, Content] = dict()
        self.__has_content_dir = False
        self.set_content_dir(ContentManager.DEFAULT_CONTENT_FOLDER_PATH)

    def load_content(self) -> None:
        self.__content.clear()
        
        contentDirs = list(
            filter(
                lambda c: os.path.isdir(c),
                os.listdir("."),
            )
        )

        for content_name in contentDirs:
            content_path = os.path.join(content_name, f"{content_name}.json")
            if os.path.exists(content_path):
                model = self.__load_json(content_path).get("model", None)
                if model is None:
                    continue

                content = Content(content_name, model)
                try:
                    # Check if model type is valid
                    content.model_dimensions
                    content.model_detection
                    print(f'Loaded content {model["name"]}')
                except ValueError as e:
                    continue

                self.__content[model["name"]] = content

    @property
    def content(self) -> List[str]:
        return sorted(self.__content.keys())

    def get_content_data(self, content: str) -> Content:
        if content not in self.__content.keys():
            raise ValueError(f"Content {content} not found")
        return self.__content[content]

    def __load_json(self, path: str) -> Any:
        if os.path.exists(path) and path[-5:] == ".json":
            with open(path, "r") as file:
                return json.load(file)
        return None


singleton: ContentManager = ContentManager()
