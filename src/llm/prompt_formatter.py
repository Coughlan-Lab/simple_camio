import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai.types.chat import (ChatCompletionMessageToolCall,
                               ChatCompletionSystemMessageParam,
                               ChatCompletionToolMessageParam,
                               ChatCompletionToolParam,
                               ChatCompletionUserMessageParam)

from src.graph import Coords, Edge, Graph, GraphEncoder, Node, PositionHandler
from src.utils import str_dict

from .tool_calls import ToolCall, tool_calls

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
        self.tool_call_response_needs_processing = False

    def handle_tool_call(
        self, tool_call: ChatCompletionMessageToolCall
    ) -> ChatCompletionToolMessageParam:
        params = json.loads(tool_call.function.arguments)

        result: Any = None

        print(f"Function call: {tool_call.function.name}")
        print(f"Parameters: {params}")

        fnc = ToolCall.get(tool_call.function.name)
        error = False

        try:
            if fnc == ToolCall.GET_DISTANCE:
                result = self.graph.get_distance(
                    Coords(params["x1"], params["y1"]),
                    Coords(params["x2"], params["y2"]),
                )

            elif fnc == ToolCall.GET_DISTANCE_TO_POINT_OF_INTEREST:
                result = self.graph.get_distance_to_poi(
                    Coords(params["x"], params["y"]),
                    params["poi_index"],
                )

            elif fnc == ToolCall.GET_NEARBY_POINTS_OF_INTEREST:
                result = self.graph.get_nearby_pois(
                    Coords(params["x"], params["y"]), params.get("distance", None)
                )

            elif fnc == ToolCall.AM_I_AT_POINT_OF_INTEREST:
                result = self.graph.am_i_at(
                    Coords(params["x"], params["y"]), params["poi_index"]
                )

            elif fnc == ToolCall.GET_POINT_OF_INTEREST_DETAILS:
                poi = self.graph.get_poi_details(params["poi_index"])
                result = str_dict(poi)

            elif fnc == ToolCall.GET_ROUTE:
                result = self.graph.get_route(
                    Coords(params["x1"], params["y1"]),
                    Coords(params["x2"], params["y2"]),
                    params["only_by_walking"],
                    params.get("transports", None),
                    params.get("transport_preference", None),
                    params.get("alternative_route_index", 0),
                )

            elif fnc == ToolCall.GET_ROUTE_TO_POINT_OF_INTEREST:
                result = self.graph.get_route_to_poi(
                    Coords(params["x"], params["y"]),
                    params["poi_index"],
                    params["only_by_walking"],
                    params.get("transports", None),
                    params.get("transport_preference", None),
                    params.get("alternative_route_index", 0),
                )

            elif fnc == ToolCall.ENABLE_POINTS_OF_INTERESTS:
                if params["disable_previous"]:
                    self.graph.disable_pois()
                self.graph.enable_pois(params["points_of_interest"])
                result = "Points of interest are now enabled."

            else:
                result = "Unknown function call."

        except Exception as e:
            print(f"An error occurred during a function call: {e}")
            result = "An error occurred while processing the function call."
            error = True

        if not isinstance(result, str):
            result = json.dumps(result, cls=GraphEncoder)

        if not error:
            self.tool_call_response_needs_processing = (
                self.tool_call_response_needs_processing or fnc.needs_further_processing
            )

        print(f"Result:\n{result}")

        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=tool_call.id,
            content=result,
        )

    def get_process_message(self, response: str) -> ChatCompletionUserMessageParam:
        assert self.tool_call_response_needs_processing

        prompt = (
            "Divide these directions into steps. "
            "For each step, you MUST include the distance to the next point, the direction to follow, and my current destination, like the intersection where I need to turn.\n"
            # "If directions are generic or not detailed enough, add further details, like the intersections along the way.\n"
            # "Also, convert egocentric directions into allocentric ones, like 'turn left' into 'turn north' if I'm walking east.\n"
            "Build a coherent speech that includes ALL this information.\n"
            "Provide only the first step of the directions; when I ask for more, give me the next one, and so on.\n"
            # "When I'm on the street where my destination is located, tell me how to find the point of interest and what streets I need to cross.\n"
            "If I get lost, call get_route or get_route_to_point_of_interest again to provide the best route to the destination.\n\n"
        )

        prompt += (
            "Remember that you MUST follow these instructions:\n"
            f"{self.instructions}\n"
        )

        prompt += f"{response}"

        self.tool_call_response_needs_processing = False

        return ChatCompletionUserMessageParam(content=prompt, role="user")

    def get_user_message(
        self, question: str, position: Optional[Coords]
    ) -> ChatCompletionUserMessageParam:
        position_description = ""

        if position is not None:
            node, distance = self.graph.get_nearest_node(position)
            graph_position: str

            if distance > PositionHandler.DISTANCE_THRESHOLD:
                edge, _ = self.graph.get_nearest_edge(position)

                distance_m_node1 = math.floor(edge[0].distance_to(position))
                distance_m_node2 = math.floor(edge[1].distance_to(position))

                graph_position = (
                    f"the closest point on the road network is on edge {edge.id}, "
                    f"which is {edge.get_llm_description()}\n"
                    f"I'm at a distance of {distance_m_node1} m from the {edge.node1.get_llm_description()} ({edge.node1.id}) "
                    f"and {distance_m_node2} m from the {edge.node2.get_llm_description()} ({edge.node2.id})."
                )
            else:
                graph_position = f"the closest point on the road network is at node {node.id}, which is the {node.description}."

            position_description = (
                "###Position Update###\n"
                f"My coordinates are {position}, "
                f"{graph_position}\n"
                "Continue answering my questions considering the updated position and keeping the previous context in mind.\n"
                "If appropriate, include the updated position in your response.\n"
                "If the following question is related to the previous one, keep the flow consistent.\n"
            )

        question = f"###Question###\n{question}"
        instructions = (
            "\nRemember that you MUST follow these instructions:\n"
            f"{self.instructions}\n"
        )

        prompt = f"{position_description}\n{question}\n{instructions}"

        return ChatCompletionUserMessageParam(content=prompt, role="user")

    def get_main_prompt(
        self, context: Dict[str, str]
    ) -> ChatCompletionSystemMessageParam:
        prompt = "I'm a blind person who needs help to navigate a new neighborhood.\n"
        prompt += "You are a resident of the neighborhood who knows it perfectly in every detail.\n\n"

        prompt += "###Context###\n\n"
        prompt += "Consider the following points on a cartesian plane at the associated coordinates:\n"
        prompt += self.__nodes_prompt() + "\n\n"

        prompt += (
            "Each point is a node of a road network graph and represents the intersection of two or more streets.\n"
            "Each edge of the graph connects two nodes and is specified with this notation: nX - nY. "
            'For example the edge "n3 - n5" would connect node n3 with node n5.\n'
            "Each street then is a sequence of connected edges on the graph. These are the streets of the road network graph:\n"
        )
        prompt += self.__edges_prompt() + "\n\n"

        prompt += (
            "The graph includes only streets that can be traveled by car. "
            "For this reason, certain streets with pedestrian-only segments might break off at some point and then continue. "
            "Base your responses solely on the information contained in the graph, even if it contradicts your personal knowledge of the area."
        )

        prompt += "These are the names of the streets in the graph. Use them to identify each street.\n"
        prompt += self.__streets_prompt() + "\n\n"

        prompt += (
            "Nodes are named based on the streets intersecting at their coordinates. "
            "For example, a node at the intersection of the Webster Street edge and the Washington Street edge "
            'will be named "Intersection of Webster Street and Washington Street." '
            "Streets without nodes in common can't intersect.\n"
            "If all the edges intersecting at a node belong to the same street, the node is named after that street."
            "A node with four edges intersecting is an X intersection, "
            "while a node with three edges intersecting forms a T intersection. "
            "A node connected to only one edge marks the end of a street.\n\n"
        )

        prompt += (
            "These are points of interest along the road network. Each point has five key fields:\n"
            "- index: the index of the point in the list of points of interest\n"
            "- street: the name of the street the point of interest belongs to\n"
            "- coords: the coordinates of the point on the cartesian plane\n"
            "- edge: the nearest edge to the point of interest. Edge's nodes are in no particular order\n"
            "- categories: a list of categories the point of interest belongs to\n\n"
        )
        prompt += self.__poi_prompt() + "\n\n"

        prompt += (
            "These are features of the road network. "
            "Include them when giving directions to reach a certain point; "
            "as I'm blind, they will help me to orient myself better and to avoid hazards.\n\n"
        )
        prompt += self.__road_features_prompt() + "\n\n"

        prompt += (
            "All units are in meters.\n"
            f"North is indicated by the vector {self.graph.reference_system.north}, "
            f"South by {self.graph.reference_system.south}, "
            f"West by {self.graph.reference_system.west}, and "
            f"East by {self.graph.reference_system.east}\n\n"
        )

        prompt += (
            "Finally, these are addictional information about the context of the map:\n"
            f"current time: {datetime.now().strftime('%A %m-%d-%Y %H:%M:%S')}\n"
            f"{str_dict(context)}\n\n"
        )

        prompt += (
            "###Instructions###\n\n"
            "I will now ask questions about the points of interest and the road network. "
            "You MUST follow these instructions:\n"
            f"{self.instructions}"
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

        if features.get("slope", "flat") != "flat":
            n1, n2 = edge.node1, edge.node2
            if features["slope"] == "downhill":
                n1, n2 = n2, n1
            features["slope"] = (
                f"uphill, from {n1.description} ({n1.id}) to {n2.description} ({n2.id})"
            )

        if features.get("traffic_direction", "two_way") != "two_way":
            n1, n2 = edge.node1, edge.node2
            if features["traffic_direction"] == "one_way_backward":
                n1, n2 = n2, n1
            features["traffic_direction"] = (
                f"one-way, from {n1.description} ({n1.id}) to {n2.description} ({n2.id})"
            )

        return str_dict({"edge": edge.id, "features": features})

    def __node_features_prompt(self, node: Node) -> str:
        features = dict(node.features)
        del features["on_border"]

        return str_dict({"node": node.id, "features": features})

    instructions = (
        "- Answer without mentioning in your response the underlying graph, its nodes and edges and the cartesian plane; only use the provided information.\n"
        "- Give me a direct, detailed and precise answer and keep it as short as possible; be objective.\n"
        "- Ensure that your answer is unbiased and does not rely on stereotypes.\n"
        "- Stick to the provided information: when information is insufficient to answer a question, "
        "respond by acknowledging the lack of an answer and suggest a way for me to find one.\n"
        "- If my question is ambiguous or unclear, ask for clarification.\n"
        # "- When giving directions, you MUST call get_route or get_route_to_point_of_interest to provide the best route to the destination.\n"
        "- When I ask where a point of interest is located or what's its nearest intersection, call get_point_of_interest_details to get more information about it.\n"
        "- Everytime I ask a question, you MUST call enable_points_of_interest to enable the points of interest relevant to the conversation, "
        "even if they are not explicitly mentioned in my question.\n"
    )
