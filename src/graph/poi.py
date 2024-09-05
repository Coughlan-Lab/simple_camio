from types import MappingProxyType
from typing import Any, Dict, Mapping

from src.utils import str_dict

from .coords import Coords, Position
from .edge import Edge

POIS_IMPORTANT_KEYS = [
    "name",
    "name_other",
    "index",
    "street",
    "coords",
    "edge",
    "opening_hours",
    "brand",
    "categories",
    "facilities",
    "catering",
    "commercial",
]


class PoI(Position):

    def __init__(
        self, index: int, name: str, coords: Coords, edge: Edge, info: Dict[str, Any]
    ) -> None:
        self.index = index
        self.name = name
        self.__info = info
        self.coords = coords
        self.edge = edge

        if "name" in self.__info:
            del self.__info["name"]
        if "coords" in self.__info:
            del self.__info["coords"]
        if "edge" in self.__info:
            del self.__info["edge"]

        self.enabled = False

    def get_complete_description(self) -> str:
        return self.name + " on " + self.street

    def distance_to(self, coords: "Coords") -> float:
        return self.coords.distance_to(coords)

    def closest_point(self, coords: "Coords") -> "Coords":
        return self.coords

    @property
    def street(self) -> str:
        return self.edge.street

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    @property
    def info(self) -> Mapping[str, Any]:
        return MappingProxyType(self.__info)

    def __hash__(self) -> int:
        return hash(self.index)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PoI):
            return False
        return self.index == other.index

    def __getitem__(self, key: str) -> Any:
        return self.__info[key]

    def __str__(self) -> str:
        return str_dict(
            {
                "index": self.index,
                "name": self.name,
                "coords": self.coords,
                "edge": self.edge,
                **{
                    key: value
                    for key, value in self.__info.items()
                    if key in POIS_IMPORTANT_KEYS
                },
            }
        )

    def __repr__(self) -> str:
        return str(self)
