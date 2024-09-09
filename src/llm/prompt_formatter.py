import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from openai.types.chat import (ChatCompletionMessageToolCall,
                               ChatCompletionSystemMessageParam,
                               ChatCompletionToolMessageParam,
                               ChatCompletionToolParam,
                               ChatCompletionUserMessageParam)

from src.graph import (Coords, Edge, EdgeFeatures, Graph, GraphEncoder, Node,
                       NodeFeatures, PoI, PositionInfo)
from src.utils import str_dict

from .tool_calls import ToolCall, tool_calls


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

        fnc = ToolCall.get(tool_call.function.name)

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
                result = str_dict(poi.info)

            elif fnc == ToolCall.GUIDE_TO_DESTINATION:
                self.graph.guide_to_destination(
                    Coords(params["x1"], params["y1"]),
                    Coords(params["x2"], params["y2"]),
                    params.get("alternative_route_index", 0),
                )
                result = "Navigation mode is now enabled."

            elif fnc == ToolCall.GUIDE_TO_POINT_OF_INTEREST:
                self.graph.guide_to_poi(
                    Coords(params["x"], params["y"]),
                    params["poi_index"],
                    params.get("alternative_route_index", 0),
                )
                result = "Navigation mode is now enabled."

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

        if not isinstance(result, str):
            result = json.dumps(result, cls=GraphEncoder)

        print(f"Result:\n{result}")

        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=tool_call.id,
            content=result,
        )

    def get_user_message(
        self, question: str, position: Optional[PositionInfo]
    ) -> ChatCompletionUserMessageParam:
        position_description = ""

        if position is not None and position.is_still_valid():
            coords = position.snap_to_graph()

            graph_position: str
            if not position.is_node():
                if position.is_edge():
                    edge = cast(Edge, position.graph_element)
                elif position.is_poi():
                    edge = cast(PoI, position.graph_element).edge
                else:
                    edge, _ = self.graph.get_nearest_edge(coords)

                distance_m_node1 = math.floor(edge[0].distance_to(coords))
                distance_m_node2 = math.floor(edge[1].distance_to(coords))

                graph_position = (
                    f"on edge {edge.id}, "
                    f"which is {edge.get_llm_description()}\n"
                    f"I'm at a distance of {distance_m_node1} m from the {edge.node1.get_llm_description()} (node {edge.node1.id}) "
                    f"and {distance_m_node2} m from the {edge.node2.get_llm_description()} (node {edge.node2.id})."
                )
            else:
                node = cast(Node, position.graph_element)

                graph_position = (
                    f"node {node.id}, which is the {node.get_llm_description()}."
                )

            position_description = (
                "###Position Update###\n"
                f"My coordinates are {position.snap_to_graph()}; "
                f"the closest point on the road network is {graph_position}\n"
                "Continue answering my questions considering the updated position and keeping the previous context in mind.\n"
                "If appropriate, include the updated position in your response.\n"
                "If the following question is related to the previous one, keep the flow consistent.\n"
            )

        question = f"###Question###\n{question}"
        instructions = self.get_instructions_prompt()["content"]

        prompt = f"{position_description}\n{question}\n{instructions}"

        return ChatCompletionUserMessageParam(content=prompt, role="user")

    def get_instructions_prompt(self) -> ChatCompletionUserMessageParam:
        instructions = (
            "\nRemember that you MUST follow these instructions:\n"
            f"{self.instructions}\n"
            "Include with your answer a tool call to the enable_points_of_interest function to enable the points of interest relevant to my question and the previous context.\n"
        )

        return ChatCompletionUserMessageParam(content=instructions, role="user")

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
            "All units are in feets.\n"
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
                for street in self.graph.streets.values()
            ]
        )

    def __streets_prompt(self) -> str:
        return "\n".join(
            [f"{street.id}: {street.name}" for street in self.graph.streets.values()]
        )

    def __poi_prompt(self) -> str:
        return "\n".join([str(poi) for poi in self.graph.pois])

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

        if features.get(EdgeFeatures.SLOPE, "flat") != "flat":
            n1, n2 = edge.node1, edge.node2
            if features[EdgeFeatures.SLOPE] == "downhill":
                n1, n2 = n2, n1
            features[EdgeFeatures.SLOPE] = (
                f"uphill, from {n1.get_llm_description()} ({n1.id}) to {n2.get_llm_description()} ({n2.id})"
            )

        if features.get(EdgeFeatures.TRAFFIC_DIRECTION, "two_way") != "two_way":
            n1, n2 = edge.node1, edge.node2
            if features[EdgeFeatures.TRAFFIC_DIRECTION] == "one_way_backward":
                n1, n2 = n2, n1
            features[EdgeFeatures.TRAFFIC_DIRECTION] = (
                f"one-way, from {n1.get_llm_description()} ({n1.id}) to {n2.get_llm_description()} ({n2.id})"
            )

        return str_dict(
            {"edge": f"{edge.id} ({edge.get_llm_description()})", "features": features}
        )

    def __node_features_prompt(self, node: Node) -> str:
        features = dict(node.features)

        del features[NodeFeatures.ON_BORDER]

        features[NodeFeatures.STREET_WIDTH] = (
            f"{features[NodeFeatures.STREET_WIDTH]} ft"
        )

        if NodeFeatures.WALK_LIGHT_DURATION in features:
            features[NodeFeatures.WALK_LIGHT_DURATION] = (
                f"{features[NodeFeatures.WALK_LIGHT_DURATION]} s"
            )

        return str_dict(
            {"node": f"{node.id} ({node.get_llm_description()})", "features": features}
        )

    instructions = (
        "- Answer without mentioning in your response the underlying graph, its nodes and edges and the cartesian plane; only use the provided information.\n"
        "- Give me a direct, detailed and precise answer and keep it as short as possible; be objective. Do not include unnecessary information.\n"
        "- Ensure that your answer is unbiased and does not rely on stereotypes.\n"
        "- Stick to the provided information: when information is insufficient to answer a question, "
        "respond by acknowledging the lack of an answer and suggest a way for me to find one.\n"
        "- If my question is ambiguous or unclear, ask for clarification.\n"
        "- When I ask where a point of interest is located or what's its nearest intersection, call get_point_of_interest_details to get more information about it.\n"
        "- Everytime I ask a question, you MUST call enable_points_of_interest to enable the points of interest relevant to the conversation, "
        "even if they are not explicitly mentioned in my question.\n"
    )
