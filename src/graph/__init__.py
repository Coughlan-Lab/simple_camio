from json import JSONEncoder
from typing import Any

from .coords import Coords
from .edge import Edge, Street
from .graph import Graph
from .node import Node
from .position_handler import PositionHandler, PositionInfo


class GraphEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Coords):
            return {"x": o.x, "y": o.y}
        if isinstance(o, Node):
            return o.id
        if isinstance(o, Edge):
            return o.id
        if isinstance(o, Street):
            return o.id
        return super().default(o)


__all__ = [
    "Coords",
    "Node",
    "Edge",
    "Street",
    "Graph",
    "GraphEncoder",
    "PositionHandler",
    "PositionInfo",
]
