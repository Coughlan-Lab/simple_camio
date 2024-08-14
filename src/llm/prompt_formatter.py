import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai.types.chat import (ChatCompletionMessageToolCall,
                               ChatCompletionSystemMessageParam,
                               ChatCompletionToolMessageParam,
                               ChatCompletionToolParam,
                               ChatCompletionUserMessageParam)

from src.graph import Coords, Edge, Graph, GraphEncoder, Node
from src.utils import str_dict

from .tool_calls import tool_calls

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


class PromptFormatter:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def handle_tool_call(
        self, tool_call: ChatCompletionMessageToolCall
    ) -> ChatCompletionToolMessageParam:
        params = json.loads(tool_call.function.arguments)

        result: Any = None

        print(f"Function call: {tool_call.function.name}")
        print(f"Parameters: {params}")

        try:
            if tool_call.function.name == "get_distance":
                result = self.graph.get_distance(
                    Coords(params["x1"], params["y1"]),
                    Coords(params["x2"], params["y2"]),
                )
            elif tool_call.function.name == "get_distance_to_point_of_interest":
                result = self.graph.get_distance_to_poi(
                    Coords(params["x"], params["y"]),
                    params["poi_index"],
                )
            elif tool_call.function.name == "get_nearby_points_of_interest":
                result = self.graph.get_nearby_pois(
                    Coords(params["x"], params["y"]), params.get("distance", None)
                )
            elif tool_call.function.name == "am_i_at_point_of_interest":
                result = self.graph.am_i_at(
                    Coords(params["x"], params["y"]), params["poi_index"]
                )
            elif tool_call.function.name == "get_point_of_interest_details":
                poi = self.graph.get_poi_details(params["poi_index"])
                result = str_dict(poi)
            elif tool_call.function.name == "get_route_to_poi":
                result = self.graph.get_route_to_poi(
                    Coords(params["x1"], params["y1"]),
                    params["poi_index"],
                    params.get("walk", True),
                    params.get("transports", None),
                    params.get("transport_preference", None),
                )
            else:
                result = "Unknown function call."
        except Exception as e:
            print(f"An error occurred during a function call: {e}")
            result = "An error occurred while processing the function call."

        if not isinstance(result, str):
            result = json.dumps(result, cls=GraphEncoder)

        print(f"Result: {result}")

        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=tool_call.id,
            content=result,
        )

    def get_user_message(
        self, question: str, position: Optional[Coords]
    ) -> ChatCompletionUserMessageParam:
        position_description = ""

        if position is not None:
            edge, _ = self.graph.get_nearest_edge(position)

            distance_m_node1 = math.floor(edge[0].distance_from(position))
            distance_m_node2 = math.floor(edge[1].distance_from(position))

            if len(edge.between_streets) == 0:
                street_str = f"at the end of {edge.street}."
            elif len(edge.between_streets) == 1:
                street_str = f"part of {edge.street}, at the intersection with {next(iter(edge.between_streets))}."
            else:
                streets = list(edge.between_streets)
                street_str = f"part of {edge.street}, between {', '.join(streets[:-1])} and {streets[-1]}."

            position_description = (
                f"""My coordinates are {position}, """
                f"""the closest point on the road network is on edge {edge.id}, """
                f"""which is {street_str}\n"""
                f"""I'm at a distance of {distance_m_node1} m from the {edge.node1.description} ({edge.node1.id}) """
                f"""and {distance_m_node2} m from the {edge.node2.description} ({edge.node2.id}).\n"""
                """Considering the updated position continue answering my questions while keeping the previous context in mind.\n"""
            )

        instructions = (
            """Answer without mentioning in your response the underlying graph, its nodes and edges and the cartesian plane; only use the provided information.\n"""
            """Give me a direct, detailed and precise answer and keep it as short as possible. Be objective.\n"""
            """Do not make anythings up: if you don't have enough information to answer a question, """
            """respond by saying you don't know the answer and suggest a way for me to find one.\n"""
            """Consider that I'm blind and I can't see the road network. """
            """For this reason when giving directions include road features and clearly visible landmarks I can use to orient myself better, """
            """like smells I might sense coming from nearby points of interest (specify which ones), """
            """a particular road surface, the presence of tactile paving, walk lights, round-abouts, and work in progress."""
            """Only include features which are actually present; for example avoid mentioning that a street is flat or """
            """that its surface is asphalt as this is the norm. Include scents, sounds, and textures.\n"""
        )

        prompt = f"{position_description}\n{question}\n\n{instructions}"

        return ChatCompletionUserMessageParam(content=prompt, role="user")

    def get_main_prompt(
        self, context: Dict[str, str]
    ) -> ChatCompletionSystemMessageParam:
        prompt = "I'm a blind person who needs help to navigate a new neighborhood. You are my assistant.\n"

        prompt += "Consider the following points on a cartesian plane at the associated coordinates:\n"
        prompt += self.__nodes_prompt() + "\n\n"

        prompt += (
            """Each point is a node of a road network graph and represents the intersection of two or more streets. """
            """Each edge connects two nodes and is specified with this notation: nX - nY. """
            """For example the edge "n3 - n5" would connect node n3 with node n5.\n"""
            """Each street is a sequence of connected edges on the graph. These are the streets of the road network graph:\n"""
        )
        prompt += self.__edges_prompt() + "\n\n"

        prompt += "These are the names of the streets in the graph; you will use them to identify each street.\n"
        prompt += self.__streets_prompt() + "\n\n"

        prompt += (
            """Nodes are named after the edges intersecting at their coordinates. """
            """For example a node at the intersection between the Webster Street edge and the Washington Street edge """
            """will be named "Intersection of Webster Street and Washington Street". """
            """Streets without nodes in common can't intersect.\n"""
            """If the edges intersecting at a node belong to the same street, the node will be named after that street.\n"""
            """If a node is connected to only one edge the node's name will be that of the edge's street.\n\n"""
        )

        prompt += (
            """These are points of interest along the road network. Each point has five important fields:\n"""
            """- index: the index of the point in the list of points of interest\n"""
            """- coords: the coordinates of the point on the cartesian plane\n"""
            """- edge: the nearest edge to the point of interest\n"""
            """- street: the name of the street the point of interest belongs to\n"""
            """- categories: a list of categories the point of interest belongs to\n\n"""
        )
        prompt += self.__poi_prompt() + "\n\n"

        prompt += (
            """These are features of the road network. """
            """Include them when giving directions to reach a certain point of interest; """
            """as I'm blind, they will help me to orient myself better and to avoid hazards.\n"""
        )
        prompt += self.__road_features_prompt() + "\n\n"

        prompt += (
            """All units are in meters. """
            f"""North is indicated by the vector {self.graph.reference_system.north}, """
            f"""South by {self.graph.reference_system.south}, """
            f"""West by {self.graph.reference_system.west}, and """
            f"""East by {self.graph.reference_system.east}\n\n"""
        )

        prompt += (
            """Finally, these are addictional information about the context of the map:\n"""
            f"""current time: {datetime.now().isoformat()}\n"""
            f"""{str_dict(context)}\n\n"""
        )

        prompt += (
            """I will now ask questions about the points of interest and the road network.\n"""
            """Answer without mentioning in your response the underlying graph, its nodes and edges and the cartesian plane; only use the provided information.\n"""
            """Give me a direct, detailed and precise answer and keep it as short as possible. Be objective.\n"""
            """Do not make anythings up: if you don't have enough information to answer a question, """
            """respond by saying you don't know the answer and suggest a way for me to find one.\n"""
            """Consider that I'm blind and I can't see the road network. """
            """For this reason when giving directions include road features and clearly visible landmarks I can use to orient myself better, """
            """like smells I might sense coming from nearby points of interest (specify which ones), """
            """a particular road surface, the presence of tactile paving, walk lights, round-abouts, and work in progress."""
            """Only include features which are actually present; for example avoid mentioning that a street is flat or """
            """that its surface is asphalt as this is the norm. Include scents, sounds, and textures.\n"""
        )

        return ChatCompletionSystemMessageParam(
            content=prompt,
            role="system",
        )

    def get_tool_calls(self) -> List[ChatCompletionToolParam]:
        return tool_calls

    def __nodes_prompt(self) -> str:
        return "\n".join([str(node) for node in self.graph.nodes])

    def __edges_prompt(self) -> str:
        return "\n".join(
            [
                "{}: {}".format(
                    street.id,
                    ", ".join([str(edge) for edge in street.edges]),
                )
                for street in self.graph.streets
            ]
        )

    def __streets_prompt(self) -> str:
        return "\n".join(
            [f"{street.id}: {street.name}" for street in self.graph.streets]
        )

    def __poi_prompt(self) -> str:
        return "\n".join(
            [
                str_dict({k: poi[k] for k in POIS_IMPORTANT_KEYS if k in poi})
                for poi in self.graph.pois
            ]
        )

    def __road_features_prompt(self) -> str:
        return (
            "\n".join(
                [
                    self.__edge_features_prompt(edge)
                    for edge in self.graph.edges
                    if len(edge.features) > 0
                ]
            )
            + "\n"
            + "\n".join(
                [
                    self.__node_features_prompt(node)
                    for node in self.graph.nodes
                    if len(node.features) > 1  # 1 is the on_border feature
                ]
            )
        )

    def __edge_features_prompt(self, edge: Edge) -> str:
        features = dict(edge.features)

        if features.get("uphill", "flat") != "flat":
            n1, n2 = edge.node1, edge.node2
            if not features["uphill"]:
                n1, n2 = n2, n1
            features["uphill"] = (
                f"from {n1.description} ({n1.id}) to {n2.description} ({n2.id})"
            )

        return str_dict({"edge": edge.id, "features": features})

    def __node_features_prompt(self, node: Node) -> str:
        features = dict(node.features)
        del features["on_border"]

        return str_dict({"node": node.id, "features": features})
