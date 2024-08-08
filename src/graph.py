from json import JSONEncoder
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from src.utils import ArithmeticBuffer, Buffer, str_dict


class Coords:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def distance_from(self, other: "Coords") -> float:
        return float(((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5)

    def manhattan_distance_from(self, other: "Coords") -> float:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def __add__(self, other: Union["Coords", float]) -> "Coords":
        if isinstance(other, Coords):
            return Coords(self.x + other.x, self.y + other.y)
        return Coords(self.x + other, self.y + other)

    def __sub__(self, other: Union["Coords", float]) -> "Coords":
        if isinstance(other, Coords):
            return Coords(self.x - other.x, self.y - other.y)
        return Coords(self.x - other, self.y - other)

    def __mul__(self, other: float) -> "Coords":
        return Coords(self.x * other, self.y * other)

    def __truediv__(self, other: float) -> "Coords":
        return Coords(self.x / other, self.y / other)

    def __getitem__(self, index: int) -> float:
        return self.x if index == 0 else self.y

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"

    def __repr__(self) -> str:
        return str(self)


class Node:
    def __init__(self, index: int, coords: Coords) -> None:
        self.coords = coords
        self.index = index
        self.adjacents_street: Set[str] = set()

    @property
    def id(self) -> str:
        return f"n{self.index}"

    @property
    def description(self) -> str:
        if len(self.adjacents_street) == 1:
            return f"end of {next(iter(self.adjacents_street))}"

        streets = list(self.adjacents_street)
        streets_str = ", ".join(streets[:-1]) + " and " + streets[-1]

        return f"intersection between {streets_str}"

    def distance_from(self, other: Union["Node", Coords]) -> float:
        if isinstance(other, Node):
            return self.coords.distance_from(other.coords)
        return self.coords.distance_from(other)

    def manhattan_distance_from(self, other: Union["Node", Coords]) -> float:
        if isinstance(other, Node):
            return self.coords.manhattan_distance_from(other.coords)
        return self.coords.manhattan_distance_from(other)

    def __getitem__(self, index: int) -> float:
        return self.coords[index]

    def __str__(self) -> str:
        return f"{self.id}: {self.coords}"

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Node):
            return False
        return self.index == other.index


class Edge:
    def __init__(self, node1: Node, node2: Node, street_name: str) -> None:
        self.node1 = node1
        self.node2 = node2
        self.street = street_name
        self.between_streets: Set[str] = set()
        self.length = self.node1.distance_from(self.node2)

    @property
    def id(self) -> str:
        return f"{self.node1.id} - {self.node2.id}"

    @property
    def m(self) -> float:
        return (self.node1[1] - self.node2[1]) / (self.node1[0] - self.node2[0])

    @property
    def q(self) -> float:
        return (self.node1[0] * self.node2[1] - self.node2[0] * self.node1[1]) / (
            self.node1[0] - self.node2[0]
        )

    def distance_from(self, coords: Coords) -> float:
        num = abs(self.m * coords.x + self.q - coords.y)
        den = (self.m**2 + 1) ** 0.5
        return float(num / den)

    def contains(self, coords: Coords) -> bool:
        return (
            self.node1[0] <= coords[0] <= self.node2[0]
            or self.node2[0] <= coords[0] <= self.node1[0]
            or self.node1[1] <= coords[1] <= self.node2[1]
            or self.node2[1] <= coords[1] <= self.node1[1]
        )

    def is_adjacent(self, other: "Edge") -> bool:
        return (
            self.node1 == other.node1
            or self.node1 == other.node2
            or self.node2 == other.node1
            or self.node2 == other.node2
        )

    def __getitem__(self, index: int) -> Node:
        return self.node1 if index == 0 else self.node2

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Edge):
            return False
        return self.node1 == other.node1 and self.node2 == other.node2

    def __hash__(self) -> int:
        return hash(self.id)


class Street:
    def __init__(self, index: int, name: str, edges: List[Edge]) -> None:
        self.index = index
        self.name = name
        self.edges = edges

    @property
    def id(self) -> str:
        return f"s{self.index}"

    def __str__(self) -> str:
        return self.id

    def __eq__(self, other: Any) -> bool:
        return bool(self.index == other.index)


class Graph:
    AM_I_THRESHOLD = 50.0  # meters
    NEARBY_THRESHOLD = 250.0  # meters
    INF = 999999

    def __init__(self, graph_dict: Dict[str, Any]) -> None:
        self.__load_nodes(graph_dict)
        self.__load_edges(graph_dict)
        self.__load_pois(graph_dict)
        self.distances = self.__precompute_distances()

        self.reference_system = {
            "north": Coords(*graph_dict["reference_system"]["north"]),
            "south": Coords(*graph_dict["reference_system"]["south"]),
            "west": Coords(*graph_dict["reference_system"]["west"]),
            "east": Coords(*graph_dict["reference_system"]["east"]),
        }

    def __load_nodes(self, graph_dict: Dict[str, Any]) -> None:
        self.nodes: List[Node] = list()
        for node in graph_dict["nodes"]:
            self.nodes.append(Node(len(self.nodes), Coords(node[0], node[1])))

    def __load_edges(self, graph_dict: Dict[str, Any]) -> None:
        self.edges: List[Edge] = list()
        self.streets: List[Street] = list()

        edges_data: List[Tuple[int, int]] = graph_dict["edges"]
        for street_name, edges_indexes in graph_dict["streets"].items():
            street_edges: List[Edge] = list()

            for edge_index in edges_indexes:
                edge_data = edges_data[edge_index]

                node1 = self.nodes[edge_data[0]]
                node1.adjacents_street.add(street_name)
                node2 = self.nodes[edge_data[1]]
                node2.adjacents_street.add(street_name)

                edge = Edge(
                    node1,
                    node2,
                    street_name,
                )

                street_edges.append(edge)

            self.edges.extend(street_edges)
            self.streets.append(Street(len(self.streets), street_name, street_edges))

        for i, e1 in enumerate(self.edges):
            for j in range(i + 1, len(self.edges)):
                e2 = self.edges[j]

                if e1.street == e2.street:
                    continue

                if e1.is_adjacent(e2):
                    e1.between_streets.add(e2.street)
                    e2.between_streets.add(e1.street)

    def __load_pois(self, graph_dict: Dict[str, Any]) -> None:
        self.pois = graph_dict["points_of_interest"]

        for i, poi in enumerate(self.pois):
            poi["index"] = i
            poi["edge"] = self.edges[poi["edge"]]
            poi["coords"] = Coords(*poi["coords"])

    def __precompute_distances(self) -> Dict[str, Dict[str, float]]:
        dist = {
            n1.id: {n2.id: Graph.INF + 1.0 for n2 in self.nodes} for n1 in self.nodes
        }

        for node in self.nodes:
            dist[node.id][node.id] = 0.0

        for edge in self.edges:
            dist[edge.node1.id][edge.node2.id] = edge.length
            dist[edge.node2.id][edge.node1.id] = edge.length

        for n1 in self.nodes:
            for n2 in self.nodes:
                for n3 in self.nodes:
                    dist[n2.id][n3.id] = min(
                        dist[n2.id][n3.id], dist[n2.id][n1.id] + dist[n1.id][n3.id]
                    )

        return dist

    def get_nearest_node(self, coords: Coords) -> Tuple[Node, float]:
        node = min(
            self.nodes,
            key=lambda node: node.distance_from(coords),
        )
        return node, node.distance_from(coords)

    def get_nearest_edge(self, coords: Coords) -> Tuple[Edge, float]:
        edge = min(
            filter(lambda edge: edge.contains(coords), self.edges),
            key=lambda edge: edge.distance_from(coords),
        )
        # TODO: fix distance
        return edge, edge.distance_from(coords)

    def get_distance(self, p1: Coords, p2: Coords) -> float:
        print(f"Getting distance from {p1} to {p2}")
        e1, dist_e1 = self.get_nearest_edge(p1)
        e2, dist_e2 = self.get_nearest_edge(p2)

        return self.__get_edge_distance(e1, e2, dist_e1, dist_e2)

    def get_distance_from_poi(self, p1: Coords, poi: int) -> float:
        print(f"Getting distance from {p1} to {poi}")
        e1, dist_e1 = self.get_nearest_edge(p1)
        e2 = self.pois[poi]["edge"]
        dist_e2 = self.pois[poi]["distance"]

        return self.__get_edge_distance(e1, e2, dist_e1, dist_e2)

    def am_i_at(self, p1: Coords, poi: int) -> bool:
        print(f"Checking if {p1} is at {poi}")

        p2 = self.pois[poi]["coords"]

        return p1.distance_from(p2) < Graph.AM_I_THRESHOLD

    def __get_edge_distance(
        self,
        e1: Edge,
        e2: Edge,
        distance_to_e1_n1: float = 0.0,
        distance_from_e2_n1: float = 0.0,
    ) -> float:
        to_distances = [distance_to_e1_n1, e1.length - distance_to_e1_n1]
        from_distances = [distance_from_e2_n1, e2.length - distance_from_e2_n1]

        d = min(
            [
                self.distances[e1[i].id][e2[j].id] + to_distances[i] + from_distances[j]
                for i in range(2)
                for j in range(2)
            ]
        )

        if d >= Graph.INF:
            raise ValueError("Points are not connected")
        return d

    def get_nearby_pois(self, coords: Coords, threshold: Optional[float]) -> List[str]:
        if threshold is None:
            threshold = Graph.NEARBY_THRESHOLD
        print(f"Getting nearby POIs from {coords} at {threshold} meters")

        if threshold < 0:
            return [poi["name"] for poi in self.pois]

        res = []
        e1, dist_e1 = self.get_nearest_edge(coords)

        for poi in self.pois:
            e2 = poi["edge"]
            try:
                d = self.__get_edge_distance(e1, e2, dist_e1, poi["distance"])
            except ValueError:
                continue

            if d <= threshold:
                res.append(poi["name"])

        return res

    @property
    def bounds(self) -> Tuple[Coords, Coords]:
        min_x = min(self.nodes, key=lambda node: node[0])[0]
        max_x = max(self.nodes, key=lambda node: node[0])[0]
        min_y = min(self.nodes, key=lambda node: node[1])[1]
        max_y = max(self.nodes, key=lambda node: node[1])[1]

        return Coords(min_x, min_y), Coords(max_x, max_y)

    def nodes_prompt(self) -> str:
        return "\n".join([str(node) for node in self.nodes])

    def edges_prompt(self) -> str:
        return "\n".join(
            [
                "{}: {}".format(
                    street,
                    ", ".join([str(edge) for edge in street.edges]),
                )
                for street in self.streets
            ]
        )

    def streets_prompt(self) -> str:
        return "\n".join([f"{street}: {street.name}" for street in self.streets])

    def poi_prompt(self) -> str:
        return "\n\n".join([str_dict(poi) for poi in self.pois])


class PositionHandler:
    MARGIN = 50
    NODE_DISTANCE_THRESHOLD = 25
    EDGE_DISTANCE_THRESHOLD = 15

    def __init__(self, graph: Graph, meters_per_pixel: float) -> None:
        self.graph = graph
        self.min_corner, self.max_corner = self.graph.bounds
        self.min_corner -= PositionHandler.MARGIN
        self.max_corner += PositionHandler.MARGIN

        self.meters_per_pixel = meters_per_pixel

        self.positions_buffer = ArithmeticBuffer[Coords](5)
        self.edge_buffer = Buffer[Edge](10)

        self.last_announced: Optional[str] = None

    def clear(self) -> None:
        self.positions_buffer.clear()
        self.edge_buffer.clear()

        self.last_announced = None

    def process_position(self, pos: Coords) -> None:
        pos *= self.meters_per_pixel

        # print(f"Position detected: {pos}")

        if (
            self.min_corner[0] <= pos.x < self.max_corner[0]
            and self.min_corner[1] <= pos.y < self.max_corner[1]
        ):
            self.positions_buffer.add(pos)

    def get_current_position(self) -> Optional[Coords]:
        if self.positions_buffer.time_from_last_update < 1:
            return self.positions_buffer.average()
        return None

    def get_next_announcement(self) -> Optional[str]:
        last_pos = self.positions_buffer.last()
        avg_pos = self.positions_buffer.average()

        if last_pos is None or avg_pos is None:
            return None

        to_announce: Optional[str] = None

        nearest_node, distance = self.graph.get_nearest_node(avg_pos)
        to_announce = nearest_node.description

        # print(f"N: {nearest_node}, D: {distance}")

        if distance > PositionHandler.NODE_DISTANCE_THRESHOLD:
            edge, distance = self.graph.get_nearest_edge(last_pos)
            self.edge_buffer.add(edge)
            nearest_edge = self.edge_buffer.mode()
            # print(f"E: {nearest_edge}, D: {distance}")

            if (
                nearest_edge is not None
                and nearest_edge.distance_from(last_pos)
                <= PositionHandler.EDGE_DISTANCE_THRESHOLD
            ):
                to_announce = nearest_edge.street
            else:
                to_announce = None

        if to_announce is None or to_announce == self.last_announced:
            return None

        self.last_announced = to_announce
        return to_announce


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
