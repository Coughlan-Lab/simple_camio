import math
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from .coords import Coords
from .edge import Edge, Street
from .node import Node

PoI = Dict[str, Any]


class LatLngReference:
    def __init__(self, coords: Coords, lat: float, lng: float) -> None:
        self.coords = coords
        self.lat = lat
        self.lng = lng


class ReferenceSystem:
    def __init__(
        self, north: Coords, south: Coords, west: Coords, east: Coords
    ) -> None:
        self.north = north
        self.south = south
        self.west = west
        self.east = east


GOOGLE_ROUTES_API_FIELDS = [
    "routes.legs.steps.navigationInstruction",
    "routes.legs.steps.travelMode",
    "routes.legs.steps.transitDetails.stopDetails.arrivalStop.name",
    "routes.legs.steps.transitDetails.stopCount",
    "routes.legs.steps.transitDetails.transitLine.name",
    "routes.legs.steps.transitDetails.transitLine.vehicle.type",
    "routes.legs.steps.localizedValues",
    # "routes.localizedValues",
]


class Graph:
    AM_I_THRESHOLD = 50.0  # meters
    NEARBY_THRESHOLD = 250.0  # meters
    INF = 999999

    def __init__(self, graph_dict: Dict[str, Any]) -> None:
        self.nodes = load_nodes(graph_dict)
        self.edges, self.streets = load_edges(self.nodes, graph_dict)
        self.pois = load_pois(self.edges, graph_dict)
        self.distances = precompute_distances(self)

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

        # round to nearest 5 multiple
        return 5 * round(d / 5)

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
            + float(poi["coords"].distance_to_line(e2))
        )

    def am_i_at(self, p1: Coords, poi: int) -> bool:
        p2 = self.pois[poi]["coords"]

        return p1.distance_to(p2) < Graph.AM_I_THRESHOLD

    def get_poi_details(self, poi_index: int) -> PoI:
        if poi_index < 0 or poi_index >= len(self.pois):
            raise ValueError("Invalid POI index")

        return self.pois[poi_index]

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
                ) + poi["coords"].distance_to_line(e2)
            except ValueError:
                continue

            if d <= threshold:
                res.append(poi["name"])

        return res

    def get_route_to_poi(
        self,
        start: Coords,
        destination_poi_index: int,
        only_by_walking: bool = True,
        transports: Optional[List[str]] = None,
        transport_preference: Optional[str] = "LESS_WALKING",
        route_index: int = 0,
    ) -> List[Dict[str, Any]]:
        poi = self.pois[destination_poi_index]

        return self.get_route(
            start,
            poi["coords"],
            only_by_walking,
            transports,
            transport_preference,
            route_index,
        )

    def get_route(
        self,
        start: Coords,
        destination: Coords,
        only_by_walking: bool = True,
        transports: Optional[List[str]] = None,
        transport_preference: Optional[str] = "LESS_WALKING",
        route_index: int = 0,
    ) -> List[Dict[str, Any]]:
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
                "units": "METRIC",
                "computeAlternativeRoutes": True,
                "travel_mode": "WALK" if only_by_walking else "TRANSIT",
                "transitPreferences": (
                    {
                        "allowedTravelModes": (
                            transports if transports and len(transports) > 0 else None
                        ),
                        "routingPreference": transport_preference,
                    }
                    if not only_by_walking
                    else None
                ),
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
            return [{"navigationInstruction": "No route found"}]
        return instructions

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


def coords_to_latlng(latlng_reference: LatLngReference, coords: Coords) -> Coords:
    R = 6378137

    diff = coords - latlng_reference.coords
    de = diff[0]
    dn = -(diff[1])

    dLat = dn / R
    dLon = de / (R * math.cos(math.pi * latlng_reference.lat / 180))

    latO = latlng_reference.lat + dLat * 180 / math.pi
    lonO = latlng_reference.lng + dLon * 180 / math.pi

    return Coords(latO, lonO)


def load_nodes(graph_dict: Dict[str, Any]) -> List[Node]:
    nodes: List[Node] = list()

    for node, features in zip(graph_dict["nodes"], graph_dict["nodes_features"]):
        nodes.append(Node(len(nodes), Coords(node[0], node[1]), features))

    return nodes


def load_edges(
    nodes: List[Node], graph_dict: Dict[str, Any]
) -> Tuple[List[Edge], List[Street]]:
    edges: List[Edge] = list()
    streets: List[Street] = list()

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
        streets.append(Street(len(streets), street_name, street_edges))

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
    pois: List[Dict[str, Any]] = graph_dict["points_of_interest"]

    for i, poi in enumerate(pois):
        poi["index"] = i
        poi["edge"] = edges[poi["edge"]]
        poi["coords"] = Coords(*poi["coords"])

    return pois


def precompute_distances(graph: Graph) -> Dict[str, Dict[str, float]]:
    dist = {n1.id: {n2.id: Graph.INF + 1.0 for n2 in graph.nodes} for n1 in graph.nodes}

    for node in graph.nodes:
        dist[node.id][node.id] = 0.0

    for edge in graph.edges:
        dist[edge.node1.id][edge.node2.id] = edge.length
        dist[edge.node2.id][edge.node1.id] = edge.length

    for n1 in graph.nodes:
        for n2 in graph.nodes:
            for n3 in graph.nodes:
                dist[n2.id][n3.id] = min(
                    dist[n2.id][n3.id], dist[n2.id][n1.id] + dist[n1.id][n3.id]
                )

    return dist
