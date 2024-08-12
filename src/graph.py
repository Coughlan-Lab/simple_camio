from json import JSONEncoder
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from src.utils import ArithmeticBuffer, Buffer


class Coords:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def distance_to(self, other: "Coords") -> float:
        return float(((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5)

    def manhattan_distance_to(self, other: "Coords") -> float:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def distance_to_edge(self, edge: "Edge") -> float:
        num = abs(edge.m * self.x + edge.q - self.y)
        den = (edge.m**2 + 1) ** 0.5

        return float(num / den)

    def project_on(self, edge: "Edge") -> "Coords":
        p_x = (self.x + edge.m * self.y - edge.m * edge.q) / (edge.m**2 + 1)
        p_y = (edge.m * self.x + edge.m**2 * self.y + edge.q) / (edge.m**2 + 1)

        return Coords(p_x, p_y)

    def dot_product(self, other: "Coords") -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return self.distance_to(Coords(0, 0))

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
    def __init__(self, index: int, coords: Coords, on_border: bool = False) -> None:
        self.coords = coords
        self.index = index
        self.adjacents_street: Set[str] = set()
        self.on_border = on_border

    @property
    def id(self) -> str:
        return f"n{self.index}"

    def is_dead_end(self) -> bool:
        return not self.on_border and len(self.adjacents_street) == 1

    @property
    def description(self) -> str:
        if len(self.adjacents_street) == 1:
            if self.on_border:
                return f"{next(iter(self.adjacents_street))}, limit of the map"
            return f"end of {next(iter(self.adjacents_street))}"

        streets = list(self.adjacents_street)
        streets_str = ", ".join(streets[:-1]) + " and " + streets[-1]

        return f"intersection between {streets_str}"

    def distance_from(self, other: Union["Node", Coords]) -> float:
        if isinstance(other, Node):
            return self.coords.distance_to(other.coords)
        return self.coords.distance_to(other)

    def manhattan_distance_from(self, other: Union["Node", Coords]) -> float:
        if isinstance(other, Node):
            return self.coords.manhattan_distance_to(other.coords)
        return self.coords.manhattan_distance_to(other)

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
    def __init__(
        self,
        node1: Node,
        node2: Node,
        street_name: str,
        features: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.node1 = node1
        self.node2 = node2
        self.street = street_name
        self.features = features if features is not None else dict()

        self.between_streets: Set[str] = set()
        self.length = self.node1.distance_from(self.node2)

    @property
    def id(self) -> str:
        return f"{self.node1.id} - {self.node2.id}"

    def get_description(self, moving_towards_node2: Optional[bool] = None) -> str:
        description = self.street

        if self.node1.is_dead_end() or self.node2.is_dead_end():
            description += ", dead end"

        if "surface" in self.features:
            description += f", {self.features['surface']}"

        if "one_way" in self.features:
            description += ", one way"

        if (
            moving_towards_node2 is not None
            and (uphill := self.features.get("uphill", None)) is not None
        ):
            if uphill == moving_towards_node2:
                description += ", uphill"
            else:
                description += ", downhill"

        if self.features.get("work_in_progress", False):
            description += ", work in progress"

        return description

    @property
    def m(self) -> float:
        return (self.node1[1] - self.node2[1]) / (self.node1[0] - self.node2[0])

    @property
    def q(self) -> float:
        return (self.node1[0] * self.node2[1] - self.node2[0] * self.node1[1]) / (
            self.node1[0] - self.node2[0]
        )

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

        border: Set[int] = set(graph_dict["border"])
        for node in graph_dict["nodes"]:
            self.nodes.append(
                Node(
                    len(self.nodes), Coords(node[0], node[1]), len(self.nodes) in border
                )
            )

    def __load_edges(self, graph_dict: Dict[str, Any]) -> None:
        self.edges: List[Edge] = list()
        self.streets: List[Street] = list()

        edges_data: List[Tuple[int, int]] = graph_dict["edges"]
        edges_features: List[Dict[str, Any]] = graph_dict["edges_features"]
        for street_name, edges_indexes in graph_dict["streets"].items():
            street_edges: List[Edge] = list()

            for edge_index in edges_indexes:
                edge_data = edges_data[edge_index]

                node1 = self.nodes[edge_data[0]]
                node1.adjacents_street.add(street_name)
                node2 = self.nodes[edge_data[1]]
                node2.adjacents_street.add(street_name)

                edge = Edge(node1, node2, street_name, edges_features[edge_index])

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
        self.pois: List[Dict[str, Any]] = graph_dict["points_of_interest"]

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

    @property
    def bounds(self) -> Tuple[Coords, Coords]:
        min_x = min(self.nodes, key=lambda node: node[0])[0]
        max_x = max(self.nodes, key=lambda node: node[0])[0]
        min_y = min(self.nodes, key=lambda node: node[1])[1]
        max_y = max(self.nodes, key=lambda node: node[1])[1]

        return Coords(min_x, min_y), Coords(max_x, max_y)

    def get_nearest_node(self, coords: Coords) -> Tuple[Node, float]:
        node = min(
            self.nodes,
            key=lambda node: node.distance_from(coords),
        )
        return node, node.distance_from(coords)

    def get_nearest_edge(self, coords: Coords) -> Tuple[Edge, float]:
        candidate_edges = list(
            filter(lambda edge: edge.contains(coords.project_on(edge)), self.edges)
        )

        if len(candidate_edges) > 0:
            edge = min(
                candidate_edges,
                key=lambda edge: coords.distance_to_edge(edge),
            )
            distance = coords.distance_to_edge(edge)
        else:
            edge = min(
                self.edges,
                key=lambda edge: min(
                    coords.distance_to(edge[0].coords),
                    coords.distance_to(edge[1].coords),
                ),
            )
            distance = min(
                coords.distance_to(edge[0].coords),
                coords.distance_to(edge[1].coords),
            )

        return edge, distance

    def get_distance(self, p1: Coords, p2: Coords) -> float:
        e1, dist_to_e1 = self.get_nearest_edge(p1)
        e2, dist_to_e2 = self.get_nearest_edge(p2)

        return (
            self.__get_edge_distance(
                e1,
                e2,
                p1.project_on(e1).distance_to(e1[0].coords),
                p2.project_on(e2).distance_to(e2[0].coords),
            )
            + dist_to_e1
            + dist_to_e2
        )

    def get_distance_to_poi(self, p1: Coords, poi_index: int) -> float:
        poi = self.pois[poi_index]

        e1, dist_to_e1 = self.get_nearest_edge(p1)
        e2 = poi["edge"]

        return (
            self.__get_edge_distance(
                e1,
                e2,
                p1.project_on(e1).distance_to(e1[0].coords),
                poi["coords"].project_on(e2).distance_to(e2[0].coords),
            )
            + dist_to_e1
            + float(poi["coords"].distance_to_edge(e2))
        )

    def am_i_at(self, p1: Coords, poi: int) -> bool:
        p2 = self.pois[poi]["coords"]

        return p1.distance_to(p2) < Graph.AM_I_THRESHOLD

    def get_poi_details(self, poi_index: int) -> Dict[str, Any]:
        if poi_index < 0 or poi_index >= len(self.pois):
            raise ValueError("Invalid POI index")

        return self.pois[poi_index]

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

        if threshold < 0:
            return [poi["name"] for poi in self.pois]

        res = []
        e1, dist_to_e1 = self.get_nearest_edge(coords)

        projection_distance = coords.project_on(e1).distance_to(e1[0].coords)
        threshold -= dist_to_e1

        for poi in self.pois:
            e2 = poi["edge"]
            try:
                d = self.__get_edge_distance(
                    e1,
                    e2,
                    projection_distance,
                    poi["coords"].project_on(e2).distance_to(e2[0].coords),
                ) + poi["coords"].distance_to_edge(e2)
            except ValueError:
                continue

            if d <= threshold:
                res.append(poi["name"])

        return res


class PositionHandler:
    MARGIN = 50
    NODE_DISTANCE_THRESHOLD = 20
    EDGE_DISTANCE_THRESHOLD = 15

    def __init__(self, graph: Graph, meters_per_pixel: float) -> None:
        self.graph = graph
        self.min_corner, self.max_corner = self.graph.bounds
        self.min_corner -= PositionHandler.MARGIN
        self.max_corner += PositionHandler.MARGIN

        self.meters_per_pixel = meters_per_pixel

        self.positions_buffer = ArithmeticBuffer[Coords](3)
        self.edge_buffer = Buffer[Edge](10)

        self.last_announced: Optional[str] = None
        self.last_position: Optional[Coords] = None

    def clear(self) -> None:
        self.positions_buffer.clear()
        self.edge_buffer.clear()

        self.last_announced = None
        self.last_position = None

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
                and last_pos.distance_to_edge(nearest_edge)
                <= PositionHandler.EDGE_DISTANCE_THRESHOLD
            ):
                to_announce = nearest_edge.get_description(
                    self.get_movement_direction(nearest_edge)
                )
            else:
                to_announce = None

        if to_announce is None or to_announce == self.last_announced:
            return None

        self.last_announced = to_announce
        self.last_position = avg_pos

        return to_announce

    def get_movement_direction(self, edge: Edge) -> Optional[bool]:
        a = edge[1].coords - edge[0].coords
        b = (self.positions_buffer.average() or Coords(0, 0)) - (
            self.last_position or Coords(0, 0)
        )

        dot = a.dot_product(b)
        print(f"Dot: {dot}")
        if dot == 0:
            return None
        return dot > 0


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
