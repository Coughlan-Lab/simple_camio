from types import MappingProxyType
from typing import Any, Dict, List, Mapping

from src.utils import StrEnum, str_dict

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


class Features(StrEnum):
    WHEELCHAIR_ACCESSIBLE = "wheelchair_accessible"
    TACTILE_PAVING = "tactile_paving"
    TACTILE_MAP = "tactile_map"
    RECEPTION = "reception"
    STAIRS = "stairs"
    ELEVATOR = "elevator"


default_features = {
    "wheelchair_accessible": False,
    "tactile_paving": False,
    "tactile_map": False,
    "reception": False,
    "stairs": False,
    "elevator": False,
}


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

    def accessibility(self) -> Dict[str, Any]:
        return dict(self.__info.get("accessibility", default_features))

    def get_complete_description(self) -> str:
        description = f"{self.name} on {self.street}"

        accessibility = self.accessibility()

        if accessibility[Features.WHEELCHAIR_ACCESSIBLE]:
            description += ", wheelchair accessible"

        tactile_features: List[str] = list()
        if accessibility[Features.TACTILE_PAVING]:
            tactile_features.append("tactile paving")
        if accessibility[Features.TACTILE_MAP]:
            tactile_features.append("tactile map")

        if len(tactile_features) > 1:
            description += f", with {' and '.join(tactile_features)}"

        if accessibility[Features.ELEVATOR]:
            description += ", accessible via elevator"
        elif accessibility[Features.STAIRS]:
            description += ", accessible via stairs"

        if accessibility[Features.RECEPTION]:
            description += ", includes a reception area"

        return description

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
