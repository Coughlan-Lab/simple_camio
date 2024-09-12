from json import JSONEncoder
from typing import Any

from .edge import Edge
from .edge import Features as EdgeFeatures
from .edge import Street
from .graph import Graph, WayPoint
from .node import Features as NodeFeatures
from .node import Node
from .poi import PoI


class GraphEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
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
    "Node",
    "NodeFeatures",
    "Edge",
    "EdgeFeatures",
    "Street",
    "Graph",
    "GraphEncoder",
    "WayPoint",
    "PoI",
]
