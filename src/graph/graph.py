import math
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from src.config import config
from src.modules_repository import Module
from src.utils import (
    CardinalDirection,
    Coords,
    LatLngReference,
    Position,
    coords_to_latlng,
    latlng_to_coords,
)

from .edge import Edge, Street
from .node import Node
from .poi import PoI

DistanceMatrix = Dict[str, Dict[str, float]]
PredecessorMatrix = Dict[str, Dict[str, Optional[Node]]]


class ReferenceSystem:
    def __init__(
        self, north: Coords, south: Coords, west: Coords, east: Coords
    ) -> None:
        self.north = north
        self.south = south
        self.west = west
        self.east = east


GOOGLE_ROUTES_API_FIELDS = [
    # "routes.legs.steps.navigationInstruction",
    "routes.legs.steps.startLocation",
    "routes.legs.steps.endLocation",
    # "routes.legs.steps.travelMode",
    # "routes.legs.steps.transitDetails.stopDetails.arrivalStop.name",
    # "routes.legs.steps.transitDetails.stopCount",
    # "routes.legs.steps.transitDetails.transitLine.name",
    # "routes.legs.steps.transitDetails.transitLine.vehicle.type",
    # "routes.legs.steps.localizedValues",
    # "routes.localizedValues",
]


@dataclass(frozen=True)
class WayPoint:
    coords: Coords
    destination: Position
    distance: Union[float, Coords]
    direction: CardinalDirection
    instructions: str = ""

    @property
    def name(self) -> Optional[str]:
        if isinstance(self.destination, Node):
            return self.destination.get_short_description()
        elif isinstance(self.destination, PoI):
            return self.destination.name
        return None


def on_new_route_placeholder(
    start: Coords, street_by_street: bool, waypoints: List[WayPoint]
) -> None:
    pass


class Graph(Module):
    DISTANCE_STEP = 10

    AM_I_THRESHOLD = 0.75  # inch
    SNAP_MIN_DISTANCE = 0.25  # inch
    NEARBY_THRESHOLD = 700.0  # feets

    INF = 999999

    def __init__(self, graph_dict: Dict[str, Any]) -> None:
        super().__init__()

        self.am_i_threshold = Graph.AM_I_THRESHOLD * config.feets_per_inch
        self.snap_min_distance = Graph.SNAP_MIN_DISTANCE * config.feets_per_inch

        self.nodes = load_nodes(graph_dict)
        self.edges, self.streets = load_edges(self.nodes, graph_dict)
        self.pois = load_pois(self.edges, graph_dict)
        self.distances, self.prev_distances = precompute_distances(self)

        self.reference_system = ReferenceSystem(
            north=Coords(*graph_dict["reference_system"]["north"]),
            south=Coords(*graph_dict["reference_system"]["south"]),
            west=Coords(*graph_dict["reference_system"]["west"]),
            east=Coords(*graph_dict["reference_system"]["east"]),
        )

        self.latlng_reference = LatLngReference(
            Coords(*graph_dict["latlng_reference"]["coords"]),
            graph_dict["latlng_reference"]["lat"],
            graph_dict["latlng_reference"]["lng"],
        )

        self.on_new_route = on_new_route_placeholder

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
            key=lambda node: node.distance_to(coords),
        )
        return node, node.distance_to(coords)

    def get_nearest_edge(self, coords: Coords) -> Tuple[Edge, float]:
        candidate_edges = list(
            filter(lambda edge: edge.contains(coords.project_on(edge)), self.edges)
        )

        if len(candidate_edges) > 0:
            edge = min(
                candidate_edges,
                key=lambda edge: coords.distance_to_line(edge),
            )
            distance = coords.distance_to_line(edge)

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

    def get_nearest_poi(self, coords: Coords) -> Tuple[Optional[PoI], float]:
        pois = list(filter(lambda p: p.enabled, self.pois))
        if len(pois) == 0:
            return None, math.inf

        poi = min(
            pois,
            key=lambda poi: poi.coords.distance_to(coords),
        )

        return poi, poi.coords.distance_to(coords)

    def get_distance(self, p1: Coords, p2: Coords) -> float:
        e1, dist_to_e1 = self.get_nearest_edge(p1)
        e2, dist_to_e2 = self.get_nearest_edge(p2)

        d = (
            self.__get_edge_distance(
                e1,
                e2,
                p1.project_on(e1).distance_to(e1[0].coords),
                p2.project_on(e2).distance_to(e2[0].coords),
            )
            + dist_to_e1
            + dist_to_e2
        )

        return round(d / Graph.DISTANCE_STEP) * Graph.DISTANCE_STEP

    def get_distance_to_poi(self, p1: Coords, poi_index: int) -> float:
        poi = self.pois[poi_index]

        e1, dist_to_e1 = self.get_nearest_edge(p1)
        e2 = poi.edge

        return (
            self.__get_edge_distance(
                e1,
                e2,
                p1.project_on(e1).distance_to(e1[0].coords),
                poi.coords.project_on(e2).distance_to(e2[0].coords),
            )
            + dist_to_e1
            + float(poi.coords.distance_to_line(e2))
        )

    def am_i_at(self, p1: Coords, poi: int) -> bool:
        p2 = self.pois[poi].coords

        return p1.distance_to(p2) < self.am_i_threshold

    def get_poi_details(self, poi_index: int) -> PoI:
        if poi_index < 0 or poi_index >= len(self.pois):
            raise ValueError("Invalid POI index")

        return self.pois[poi_index]

    def get_nearby_pois(self, coords: Coords, threshold: Optional[float]) -> List[str]:
        if threshold is None:
            threshold = Graph.NEARBY_THRESHOLD

        if threshold < 0:
            return [poi.name for poi in self.pois]

        res = []
        e1, dist_to_e1 = self.get_nearest_edge(coords)

        projection_distance = coords.project_on(e1).distance_to(e1[0].coords)
        threshold -= dist_to_e1

        for poi in self.pois:
            e2 = poi.edge
            try:
                d = self.__get_edge_distance(
                    e1,
                    e2,
                    projection_distance,
                    poi.coords.project_on(e2).distance_to(e2[0].coords),
                ) + poi.coords.distance_to_line(e2)
            except ValueError:
                continue

            if d <= threshold:
                res.append(poi.name)

        return res

    def snap_to_graph(
        self, coords: Coords, force: bool = False
    ) -> Tuple[Coords, Position]:
        node, distance = self.get_nearest_node(coords)
        if distance < Graph.SNAP_MIN_DISTANCE * config.feets_per_inch:
            return node.coords, node

        edge, distance = self.get_nearest_edge(coords)
        if force or distance < Graph.SNAP_MIN_DISTANCE * config.feets_per_inch:
            return coords.project_on(edge), edge

        return coords, coords

    def guide_to_poi(
        self,
        start: Coords,
        destination_poi_index: int,
        street_by_street: bool = True,
        route_index: int = 0,
    ) -> None:
        poi = self.pois[destination_poi_index]

        self.guide_to_destination(
            start,
            poi.coords,
            street_by_street,
            route_index,
        )

    def guide_to_destination(
        self,
        start: Coords,
        destination: Coords,
        street_by_street: bool = True,
        route_index: int = 0,
    ) -> None:
        start = self.snap_to_graph(start, force=True)[0]
        destination = self.snap_to_graph(destination, force=True)[0]

        if start == destination:
            return self.on_new_route(start, street_by_street, list())

        if not street_by_street:
            return self.on_new_route(
                start,
                street_by_street,
                [
                    WayPoint(
                        destination,
                        destination,
                        start.distance_to(destination),
                        get_direction((destination - start).normalized()),
                    )
                ],
            )

        start_latlng = coords_to_latlng(self.latlng_reference, start)
        destination_latlng = coords_to_latlng(self.latlng_reference, destination)

        response = requests.post(
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            json={
                "origin": {
                    "location": {
                        "latLng": {
                            "latitude": start_latlng[0],
                            "longitude": start_latlng[1],
                        }
                    }
                },
                "destination": {
                    "location": {
                        "latLng": {
                            "latitude": destination_latlng[0],
                            "longitude": destination_latlng[1],
                        }
                    }
                },
                "units": "IMPERIAL",
                "computeAlternativeRoutes": route_index > 0,
                "travel_mode": "WALK",
            },
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": os.environ["GOOGLE_ROUTES_API_KEY"],
                "X-Goog-FieldMask": ",".join(GOOGLE_ROUTES_API_FIELDS),
            },
        )

        instructions = (
            response.json()
            .get("routes", [dict()] * (route_index + 1))[route_index]
            .get("legs", [dict()])[0]
            .get("steps", [])
        )

        if len(instructions) == 0:
            raise ValueError("No route found")

        self.on_new_route(
            start, street_by_street, self.__process_instructions(instructions)
        )

    def get_min_path(self, start: Node, destination: Node) -> List[Node]:
        if self.prev_distances[start.id][destination.id] == None:
            return list()

        path: List[Node] = [destination]

        current = destination
        while start != current:
            current = self.prev_distances[start.id][current.id]
            assert (
                current is not None
            ), f"No path found between n{start.id} and n{destination.id}"
            path.append(current)

        return path[::-1]

    def enable_pois(self, indices: List[int]) -> None:
        for index in indices:
            self.pois[index].enable()

    def disable_pois(self) -> None:
        for poi in self.pois:
            poi.disable()

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

    def __process_instructions(self, steps: List[Dict[str, Any]]) -> List[WayPoint]:
        waypoints: List[WayPoint] = list()

        previous_versor = Coords(0, 0)
        for i, step in enumerate(steps):
            from_coords = latlng_to_coords(
                self.latlng_reference,
                Coords(
                    step["startLocation"]["latLng"]["latitude"],
                    step["startLocation"]["latLng"]["longitude"],
                ),
            )
            to_coords = latlng_to_coords(
                self.latlng_reference,
                Coords(
                    step["endLocation"]["latLng"]["latitude"],
                    step["endLocation"]["latLng"]["longitude"],
                ),
            )

            versor = (to_coords - from_coords).normalized()

            from_coords, start = self.snap_to_graph(from_coords, force=True)
            to_coords, destination = self.snap_to_graph(to_coords)

            distance = (
                round(
                    Coords(to_coords.x - from_coords.x, to_coords.y - from_coords.y)
                    * 10
                    / config.feets_per_inch
                )
                / 10
            )

            if i == 0:
                direction = get_direction(versor)
                same_direction = False
            else:
                direction = get_turning_direction(
                    versor, waypoints[-1].direction, previous_versor
                )
                same_direction = direction == waypoints[-1].direction

            description = "Continue straight" if same_direction else f"Head {direction}"

            crossings = self.get_crossings(start, destination)
            if crossings == 1 and not isinstance(destination, Node):
                description += ", pass the first intersection"
            elif crossings > 1:
                description += f" for {crossings} intersections"

            if isinstance(destination, Node):
                description += f" until {destination.get_short_description()}"
            elif isinstance(destination, Edge):
                if crossings > 0:
                    description += f", and then continue"
                description += f" for {destination.get_distance_description(to_coords)}"
            else:
                if crossings == 1:
                    description += ", and then continue"
                description += " until your final destination"

            waypoints.append(
                WayPoint(
                    coords=to_coords,
                    destination=destination,
                    distance=distance,
                    direction=direction,
                    instructions=description,
                )
            )
            previous_versor = versor

        return waypoints

    def get_crossings(self, start: Position, destination: Position) -> int:
        start_nodes: List[Node] = list()
        destination_nodes: List[Node] = list()

        if isinstance(start, Node):
            start_nodes.append(start)
        elif isinstance(start, PoI):
            start_nodes.extend([node for node in start.edge])
        elif isinstance(start, Edge):
            start_nodes.extend([start.node1, start.node2])
        elif isinstance(start, Coords):
            start_nodes.append(self.get_nearest_node(start)[0])

        if isinstance(destination, Node):
            destination_nodes.append(destination)
        elif isinstance(destination, PoI):
            destination_nodes.extend([node for node in destination.edge])
        elif isinstance(destination, Edge):
            destination_nodes.extend([destination.node1, destination.node2])
        elif isinstance(destination, Coords):
            destination_nodes.append(self.get_nearest_node(destination)[0])

        min_crossings = Graph.INF
        for start_node in start_nodes:
            for destination_node in destination_nodes:
                if start_node == destination_node:
                    return 0

                path = self.get_min_path(start_node, destination_node)
                min_crossings = min(min_crossings, len(path))

        if isinstance(start, Node):
            min_crossings -= 1

        return min_crossings


def load_nodes(graph_dict: Dict[str, Any]) -> List[Node]:
    nodes: List[Node] = list()

    for node, features in zip(graph_dict["nodes"], graph_dict["nodes_features"]):
        nodes.append(Node(len(nodes), Coords(node[0], node[1]), features))

    return nodes


def load_edges(
    nodes: List[Node], graph_dict: Dict[str, Any]
) -> Tuple[List[Edge], Dict[str, Street]]:
    edges: List[Edge] = list()
    streets: Dict[str, Street] = dict()

    edges_data: List[Tuple[int, int]] = graph_dict["edges"]
    edges_features: List[Dict[str, Any]] = graph_dict["edges_features"]
    for street_name, edges_indexes in graph_dict["streets"].items():
        street_edges: List[Edge] = list()

        for edge_index in edges_indexes:
            edge_data = edges_data[edge_index]

            node1 = nodes[edge_data[0]]
            node1.adjacents_streets.append(street_name)
            node2 = nodes[edge_data[1]]
            node2.adjacents_streets.append(street_name)

            edge = Edge(node1, node2, street_name, edges_features[edge_index])

            street_edges.append(edge)

        edges.extend(street_edges)
        streets[street_name] = Street(len(streets), street_name, street_edges)

    for i, e1 in enumerate(edges):
        for j in range(i + 1, len(edges)):
            e2 = edges[j]

            if e1.street == e2.street:
                continue

            if e1.is_adjacent(e2):
                e1.between_streets.add(e2.street)
                e2.between_streets.add(e1.street)

    return edges, streets


def load_pois(edges: List[Edge], graph_dict: Dict[str, Any]) -> List[PoI]:
    pois_data: List[Dict[str, Any]] = graph_dict["points_of_interest"]

    pois: List[PoI] = list()

    for i, poi_data in enumerate(pois_data):
        edge = edges[poi_data["edge"]]
        coords = Coords(*poi_data["coords"])

        poi = PoI(i, poi_data["name"], coords, edge, poi_data)
        pois.append(poi)

    if not config.llm_enabled:
        for poi in pois:
            poi.enable()

    return pois


def precompute_distances(
    graph: Graph,
) -> Tuple[DistanceMatrix, PredecessorMatrix]:
    dist: DistanceMatrix = {
        n1.id: {n2.id: Graph.INF + 1.0 for n2 in graph.nodes} for n1 in graph.nodes
    }
    prev: PredecessorMatrix = {
        n1.id: {n2.id: None for n2 in graph.nodes} for n1 in graph.nodes
    }

    for edge in graph.edges:
        dist[edge.node1.id][edge.node2.id] = edge.length
        dist[edge.node2.id][edge.node1.id] = edge.length
        prev[edge.node1.id][edge.node2.id] = edge.node1
        prev[edge.node2.id][edge.node1.id] = edge.node2

    for node in graph.nodes:
        dist[node.id][node.id] = 0.0
        prev[node.id][node.id] = node

    for k in graph.nodes:
        for i in graph.nodes:
            for j in graph.nodes:
                if dist[i.id][j.id] > dist[i.id][k.id] + dist[k.id][j.id]:
                    dist[i.id][j.id] = dist[i.id][k.id] + dist[k.id][j.id]
                    prev[i.id][j.id] = prev[k.id][j.id]

    return dist, prev


directions = list(CardinalDirection.__members__.values())


def get_direction(versor: Coords) -> CardinalDirection:
    return get_turning_direction(versor, CardinalDirection.NORTH, Coords(0, -1))


def get_turning_direction(
    new_versor: Coords, old_direction: CardinalDirection, old_versor: Coords
) -> CardinalDirection:
    dot = new_versor.dot(old_versor)
    angle = math.degrees(math.acos(dot))  # between 0 and 180

    direction_index = 0
    side = (
        1 if old_versor.cross_2d(new_versor) > 0 else -1
    )  # 1 to go down the list, -1 to go up

    threshold = 22.5
    while angle > threshold:
        direction_index += 1
        angle -= 45

    return directions[
        (directions.index(old_direction) + side * direction_index) % len(directions)
    ]
