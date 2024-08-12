import json
import math
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from openai import OpenAI, OpenAIError
from openai.types import CompletionUsage
from openai.types.chat import (ChatCompletionAssistantMessageParam,
                               ChatCompletionMessage,
                               ChatCompletionMessageParam,
                               ChatCompletionMessageToolCall,
                               ChatCompletionMessageToolCallParam,
                               ChatCompletionSystemMessageParam,
                               ChatCompletionToolMessageParam,
                               ChatCompletionToolParam,
                               ChatCompletionUserMessageParam)
from openai.types.chat.chat_completion_message_tool_call_param import \
    Function as FunctionParam
from openai.types.shared_params import FunctionDefinition

from src.graph import Coords, Edge, Graph, GraphEncoder, Node
from src.utils import str_dict


class LLM:
    MODEL = "gpt-4o-2024-08-06"  # "gpt-4o-mini-2024-07-18"
    MAX_TOKENS = 2000
    TEMPERATURE = 0.2

    def __init__(
        self,
        graph: Graph,
        context: Dict[str, str],
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
    ) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.client = OpenAI()
        self.prompt_formatter = PromptFormatter(graph)

        self.history: List[ChatCompletionMessageParam] = list()
        self.history.append(self.prompt_formatter.get_main_prompt(context))

        self.running = False
        self.usage: Optional[CompletionUsage] = None

    def is_waiting_for_response(self) -> bool:
        return self.running

    def stop(self) -> None:
        self.running = False

    def reset(self) -> None:
        self.history.clear()

    def ask(self, question: str, position: Optional[Coords]) -> Optional[str]:
        new_message = self.prompt_formatter.get_user_message(question, position)
        self.history.append(new_message)
        self.running = True

        output = ""

        try:
            while self.running:
                print("Sending API request...")

                response = self.client.chat.completions.create(
                    model=LLM.MODEL,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=self.history,
                    tools=self.prompt_formatter.get_tool_calls(),
                )
                self.usage = response.usage

                if not self.running:
                    break
                print("Got API response")

                response_message = response.choices[0].message
                if (
                    response_message.content is not None
                    and response_message.content != ""
                ):
                    output += response_message.content + "\n"

                self.history.append(self.convert_assistant_message(response_message))

                if response_message.tool_calls is None:
                    break

                for tool_call in response_message.tool_calls:
                    self.history.append(
                        self.prompt_formatter.handle_tool_call(tool_call)
                    )

        except OpenAIError as e:
            print(f"An error occurred: {e}")
            self.running = False
            return None

        self.running = False

        return output[:-1]

    def convert_assistant_message(
        self, msg: ChatCompletionMessage
    ) -> ChatCompletionMessageParam:
        return ChatCompletionAssistantMessageParam(
            role="assistant",
            content=msg.content,
            tool_calls=self.convert_tool_calls(msg.tool_calls),
        )

    def convert_tool_calls(
        self, tool_calls: Optional[List[ChatCompletionMessageToolCall]]
    ) -> Optional[Iterable[ChatCompletionMessageToolCallParam]]:
        if tool_calls is None:
            return None

        return [
            ChatCompletionMessageToolCallParam(
                id=tool_call.id,
                function=FunctionParam(
                    arguments=tool_call.function.arguments, name=tool_call.function.name
                ),
                type=tool_call.type,
            )
            for tool_call in tool_calls
        ]

    def save_chat(self, filename: str) -> None:
        msgs: List[str] = list()
        for msg in self.history:
            if "content" in msg and msg["content"] is not None and msg["content"] != "":
                msgs.append(f"{msg['role']}:\n{msg['content']}")

        if self.usage is not None:
            msgs.append(f"Usage: {str(self.usage.total_tokens)} tokens")

        with open(filename, "w") as f:
            f.write("\n\n".join(msgs))


class PromptFormatter:
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
        "catering",
        "commercial",
        "facilities",
    ]

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

            edge_pixels = edge[0].distance_from(edge[1])
            distance_pixels_node1 = edge[0].distance_from(position)
            distance_pixels_node2 = edge[1].distance_from(position)

            distance_m_node1 = distance_pixels_node1 * edge.length / edge_pixels
            distance_m_node1 = math.floor(distance_m_node1)
            distance_m_node2 = distance_pixels_node2 * edge.length / edge_pixels
            distance_m_node2 = math.floor(distance_m_node2)

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
            """like the road surface (if not asphalt), tactile paving, semaphores, round-abouts, work in progress """
            """and smells I might sense coming from nearby points of interest (specify which ones)."""
            """Only include features which are among those provided with the graph. Be detailed."""
        )

        prompt = f"{position_description}\n{question}\n\n{instructions}"

        return ChatCompletionUserMessageParam(content=prompt, role="user")

    def get_main_prompt(
        self, context: Dict[str, str]
    ) -> ChatCompletionSystemMessageParam:
        prompt = "I'm a blind person who needs help to navigate a new neighborhood. You are my assistant.\n"

        prompt += "Consider the following points on a cartesian plane at the associated coordinates:\n"
        prompt += self.nodes_prompt() + "\n\n"

        prompt += (
            """Each point is a node of a road network graph and represents the intersection of two or more streets. """
            """Each edge connects two nodes and is specified with this notation: nX - nY. """
            """For example the edge "n3 - n5" would connect node n3 with node n5.\n"""
            """Each street is a sequence of connected edges on the graph. These are the streets of the road network graph:\n"""
        )
        prompt += self.edges_prompt() + "\n\n"

        prompt += (
            """All units are in meters. """
            f"""North is indicated by the vector {self.graph.reference_system['north']}, """
            f"""South by {self.graph.reference_system['south']}, """
            f"""West by {self.graph.reference_system['west']}, and """
            f"""East by {self.graph.reference_system['east']}\n\n"""
        )

        prompt += "These are the names of the streets in the graph; you will use them to identify each street."
        prompt += self.streets_prompt() + "\n\n"

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
            """- coords: the coordinates of the point\n"""
            """- edge: the edge the point is located on\n"""
            """- street: the name of the street the edge belong to\n"""
            """- categories: a list of categories the point belongs to\n"""
        )
        prompt += self.poi_prompt() + "\n\n"

        prompt += (
            """These are features of the road network. """
            """Include them when giving directions to reach a certain point of interest; """
            """as I'm blind, they will help me to orient myself better and to avoid hazards. """
        )
        prompt += self.road_features_prompt() + "\n\n"

        prompt += (
            """Finally, these are addictional information about the context of the map:\n"""
            f"""current time: {datetime.now().isoformat()}\n"""
            f"""{str_dict(context)}\n\n"""
        )

        prompt += (
            """I will now ask questions about the points of interest or the road network.\n"""
            """Answer without mentioning in your response the underlying graph, its nodes and edges and the cartesian plane; only use the provided information.\n"""
            """Give me a direct, detailed and precise answer and keep it as short as possible. Be objective.\n"""
            """Do not make anythings up: if you don't have enough information to answer a question, """
            """respond by saying you don't know the answer and suggest a way for me to find one.\n"""
            """Consider that I'm blind and I can't see the road network. """
            """For this reason when giving directions include road features and clearly visible landmarks I can use to orient myself better, """
            """like the road surface (if not asphalt), tactile paving, semaphores, round-abouts, work in progress """
            """and smells I might sense coming from nearby points of interest (specify which ones)."""
            """Only include features which are among those provided with the graph. Be detailed.\n"""
        )

        return ChatCompletionSystemMessageParam(
            content=prompt,
            role="system",
        )

    def get_tool_calls(self) -> List[ChatCompletionToolParam]:
        return [
            ChatCompletionToolParam(
                type="function",
                function=FunctionDefinition(
                    name="get_distance",
                    description="Get the distance between two points on the road network graph.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "x1": {
                                "type": "number",
                                "description": "The x coordinate of the first point",
                            },
                            "y1": {
                                "type": "number",
                                "description": "The y coordinate of the first point",
                            },
                            "x2": {
                                "type": "number",
                                "description": "The x coordinate of the second point",
                            },
                            "y2": {
                                "type": "number",
                                "description": "The y coordinate of the second point",
                            },
                        },
                        "required": ["x1", "y1", "x2", "y2"],
                        "additionalProperties": False,
                    },
                ),
            ),
            ChatCompletionToolParam(
                type="function",
                function=FunctionDefinition(
                    name="get_distance_to_point_of_interest",
                    description="Get the distance between a point and a point of interest. You can use this function to determine how far I am from a point of interest by providing the coordinates of my position and the index of the point of interest.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "The x coordinate of the point",
                            },
                            "y": {
                                "type": "number",
                                "description": "The y coordinate of the point",
                            },
                            "poi_index": {
                                "type": "number",
                                "description": "The index of the point of interest",
                            },
                        },
                        "required": ["x", "y", "poi_index"],
                        "additionalProperties": False,
                    },
                ),
            ),
            ChatCompletionToolParam(
                type="function",
                function=FunctionDefinition(
                    name="am_i_at_point_of_interest",
                    description="Check if a point is near a point of interest. Use this function to determine if I'm near a point of interest by providing the coordinates of my position and the index of the point of interest. If the result is false, give me instructions on how to get there.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "The x coordinate of the point",
                            },
                            "y": {
                                "type": "number",
                                "description": "The y coordinate of the point",
                            },
                            "poi_index": {
                                "type": "number",
                                "description": "The index of the point of interest",
                            },
                        },
                        "required": ["x", "y", "poi_index"],
                        "additionalProperties": False,
                    },
                ),
            ),
            ChatCompletionToolParam(
                type="function",
                function=FunctionDefinition(
                    name="get_nearby_points_of_interest",
                    description="Get the points of interest within a certain maximum distance from a point. Call this function only if I specifically ask for nearby points of interest; otherwise use the information provided in the prompt. If I just ask for a point of interest, don't use this function.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "The x coordinate of the point",
                            },
                            "y": {
                                "type": "number",
                                "description": "The y coordinate of the point",
                            },
                            "distance": {
                                "type": "number",
                                "description": f"The maximum distance from the point. If not provided, a maximum distance of {Graph.NEARBY_THRESHOLD} m is used. If not told otherwise, use a distance of at least {Graph.NEARBY_THRESHOLD} m.",
                            },
                        },
                        "required": ["x", "y"],
                        "additionalProperties": False,
                    },
                ),
            ),
            ChatCompletionToolParam(
                type="function",
                function=FunctionDefinition(
                    name="get_point_of_interest_details",
                    description="Get the details of a point of interest. Use this function to get information you need to answer a question about a point of interest; otherwise use the information provided in the prompt. Points of interest details can include for example a description, city, suburb, district, contact information, website, payment options, building data, public transport network and operator",
                    parameters={
                        "type": "object",
                        "properties": {
                            "poi_index": {
                                "type": "number",
                                "description": "The index of the point of interest",
                            },
                        },
                        "required": ["poi_index"],
                        "additionalProperties": False,
                    },
                ),
            ),
        ]

    def nodes_prompt(self) -> str:
        return "\n".join([str(node) for node in self.graph.nodes])

    def edges_prompt(self) -> str:
        return "\n".join(
            [
                "{}: {}".format(
                    street,
                    ", ".join([str(edge) for edge in street.edges]),
                )
                for street in self.graph.streets
            ]
        )

    def streets_prompt(self) -> str:
        return "\n".join([f"{street}: {street.name}" for street in self.graph.streets])

    def poi_prompt(self) -> str:
        return "\n".join(
            [
                str_dict(
                    {k: poi[k] for k in PromptFormatter.POIS_IMPORTANT_KEYS if k in poi}
                )
                for poi in self.graph.pois
            ]
        )

    def road_features_prompt(self) -> str:
        return (
            "\n".join(
                [
                    self.edge_features_prompt(edge)
                    for edge in self.graph.edges
                    if len(edge.features) > 0
                ]
            )
            + "\n"
            + "\n".join(
                [
                    self.node_features_prompt(node)
                    for node in self.graph.nodes
                    if len(node.features) > 1  # 1 is the on_border feature
                ]
            )
        )

    def edge_features_prompt(self, edge: Edge) -> str:
        features = dict(edge.features)
        if "uphill" in features:
            n1, n2 = edge.node1, edge.node2
            if not features["uphill"]:
                n1, n2 = n2, n1
            features["uphill"] = (
                f"from {n1.description} ({n1.id}) to {n2.description} ({n2.id})"
            )

        return str_dict({"edge": edge.id, "features": features})

    def node_features_prompt(self, node: Node) -> str:
        features = dict(node.features)
        del features["on_border"]

        return str_dict({"node": node.id, "features": features})
