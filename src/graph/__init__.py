from json import JSONEncoder
from typing import Any

from .coords import INF as Coords_INF
from .coords import ZERO as Coords_ZERO
from .coords import Coords, Position
from .edge import Edge
from .edge import Features as EdgeFeatures
from .edge import Street
from .graph import Graph, WayPoint
from .node import Features as NodeFeatures
from .node import Node
from .poi import PoI
from .position_handler import NONE_INFO as NONE_POSITION_INFO
from .position_handler import MovementDirection, PositionHandler, PositionInfo


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
        if isinstance(o, PoI):
            return {
                "index": o.index,
                "name": o.name,
                "coords": o.coords,
                "edge": o.edge,
                **o.info,
            }
        return super().default(o)


__all__ = [
    "Coords",
    "Node",
    "NodeFeatures",
    "Edge",
    "EdgeFeatures",
    "Street",
    "Graph",
    "GraphEncoder",
    "WayPoint",
    "PoI",
    "Coords_ZERO",
    "Coords_INF",
    "Position",
    "PositionHandler",
    "MovementDirection",
    "PositionInfo",
    "NONE_POSITION_INFO",
]
