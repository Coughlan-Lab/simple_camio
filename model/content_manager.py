from enum import Enum
import os
import json
from typing import Any, Union


class Content:
    class ModelType(Enum):
        TWO_D = "2D"
        THREE_D = "3D"

    def __init__(self, name: str, content: dict[str, Any]) -> None:
        self.__name = name
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

        path = self.get_path(self.__content["preview"])

        if not os.path.exists(path):
            return None
        return path

    @property
    def model_type(self) -> ModelType:
        model_type = self.__content["modelType"]
        if model_type == "2D":
            return Content.ModelType.TWO_D
        elif model_type == "3D":
            return Content.ModelType.THREE_D
        raise ValueError(f"Unknown model type {model_type}")

    def is_2D(self) -> bool:
        return self.model_type == Content.ModelType.TWO_D

    def is_3D(self) -> bool:
        return not self.is_2D()

    @property
    def to_print(self) -> str:
        path = os.path.join(singleton.get_content_path(self.__name), "toPrint.")
        return path + ("pdf" if self.is_2D() else "obj")

    def get_path(self, file: str) -> str:
        return os.path.join(ContentManager.CONTENT_DIR, file)


class ContentManager:
    CONTENT_DIR = os.path.join(os.getcwd(), "content")

    def __init__(self) -> None:
        self.__content: dict[str, Content] = dict()
        self.__calibration_map: str
        self.__pointer: str

        self.reload()

    def reload(self) -> None:
        if not os.path.exists(ContentManager.CONTENT_DIR):
            return

        content = os.listdir(ContentManager.CONTENT_DIR)
        contentDirs = list(
            filter(
                lambda c: os.path.isdir(os.path.join(ContentManager.CONTENT_DIR, c)),
                content,
            )
        )

        for content_name in contentDirs:
            content_path = self.get_content_path(content_name)
            content_path = os.path.join(content_path, f"{content_name}.json")
            if os.path.exists(content_path):
                model = self.__load_json(content_path)["model"]
                self.__content[model["name"]] = Content(content_name, model)

        self.__pointer = os.path.join(
            ContentManager.CONTENT_DIR, "teardrop_stylus.json"
        )

    @property
    def content(self) -> list[str]:
        return sorted(self.__content.keys())

    def get_content_data(self, content: str) -> Content:
        if content not in self.__content.keys():
            raise ValueError(f"Content {content} not found")
        return self.__content[content]

    def get_content_path(self, content: str) -> str:
        return os.path.join(ContentManager.CONTENT_DIR, content)

    def __load_json(self, path: str) -> Any:
        if os.path.exists(path) and path[-5:] == ".json":
            with open(path, "r") as file:
                return json.load(file)
        return None


singleton: ContentManager = ContentManager()
