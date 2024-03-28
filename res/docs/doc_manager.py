import os
import json
from typing import Any


class DocManager:
    DOCS_DIR = os.path.dirname(__file__)

    def __init__(self) -> None:
        self.calibration_map = os.path.join(DocManager.DOCS_DIR, "calibration_map.pdf")
        self.marker_pointer = os.path.join(DocManager.DOCS_DIR, "marker_pointer.pdf")
        self.__marker_pointer_data_path = os.path.join(
            DocManager.DOCS_DIR, "marker_pointer.json"
        )

    @property
    def marker_pointer_data(self) -> Any:
        with open(self.__marker_pointer_data_path, "r") as file:
            return json.load(file)


singleton: DocManager = DocManager()
