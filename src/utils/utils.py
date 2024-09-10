import json
import os
from enum import Enum
from typing import Any, Dict, Mapping, Optional


def str_format(v: Any) -> str:
    return str(v).replace("_", " ")


def str_dict(d: Mapping[Any, Any], indent: int = 0) -> str:
    res = ""

    for key, value in d.items():
        res += " " * indent + str_format(key) + ": "
        if isinstance(value, dict):
            res += "\n" + str_dict(value, indent + 4)
        elif isinstance(value, list):
            if len(value) == 0:
                res += "[]\n"
            elif len(value) == 1:
                res += "[ " + str_format(value[0]) + " ]\n"
            else:
                res += "[\n"
                for item in value:
                    res += " " * (indent + 4) + str_format(item) + ",\n"
                res += " " * indent + "]\n"
        else:
            res += str_format(value) + "\n"

    return res


def load_map_parameters(filename: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(filename) or not os.path.isfile(filename):
        return None

    try:
        with open(filename, "r") as f:
            map_params = json.load(f)
    except Exception as e:
        return None

    return dict(map_params)


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self)


class CardinalDirection(StrEnum):
    SOUTH_WEST = "south-west"
    WEST = "west"
    NORTH_WEST = "north-west"
    NORTH = "north"
    NORTH_EAST = "north-east"
    EAST = "east"
    SOUTH_EAST = "south-east"
    SOUTH = "south"
