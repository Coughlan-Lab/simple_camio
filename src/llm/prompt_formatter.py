import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import yaml
from httpx import main
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
    def __init__(self, prompt_file: str, graph: Graph) -> None:
        self.graph = graph

        if not os.path.exists(prompt_file):
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        with open(prompt_file, "r") as file:
            self.prompt_components = yaml.safe_load(file)

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
                    params.get("step_by_step", True),
                    params.get("alternative_route_index", 0),
                )
                result = "Navigation mode is now enabled."

            elif fnc == ToolCall.GUIDE_TO_POINT_OF_INTEREST:
                self.graph.guide_to_poi(
                    Coords(params["x"], params["y"]),
                    params["poi_index"],
                    params.get("step_by_step", True),
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
        components = self.prompt_components["question"]
        position_prompt = ""

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

                graph_position = components["position"]["edge"].format(
                    edge.id,
                    edge.get_llm_description(),
                    distance_m_node1,
                    edge.node1.get_llm_description(),
                    edge.node1.id,
                    distance_m_node2,
                    edge.node2.get_llm_description(),
                    edge.node2.id,
                )

            else:
                node = cast(Node, position.graph_element)

                graph_position = components["position"]["node"].format(
                    node.id, node.get_llm_description()
                )

            position_prompt = "###Position Update###\n\n"
            position_prompt += components["position"]["structure"].format(
                position.snap_to_graph(), graph_position.strip()
            )

        question_prompt = f"###Question###\n\n"
        question_prompt += question + "\n"

        instructions = self.get_instructions_prompt()["content"]

        prompt = f"{position_prompt}\n{question_prompt}\n{instructions}"

        return ChatCompletionUserMessageParam(content=prompt, role="user")

    def get_instructions_prompt(self) -> ChatCompletionUserMessageParam:
        instructions = "###Instructions###\n\n"
        instructions += self.prompt_components["question"]["instructions"].format(
            self.prompt_components["base_instructions"].strip()
        )

        return ChatCompletionUserMessageParam(content=instructions, role="user")

    def get_main_prompt(
        self, context: Dict[str, str]
    ) -> ChatCompletionSystemMessageParam:
        main_prompts = self.prompt_components["main"]
        prompt = main_prompts["header"] + "\n"

        prompt += "###Context###\n\n"
        prompt += main_prompts["graph"]["nodes"]
        prompt += self.__nodes_prompt() + "\n\n"

        prompt += main_prompts["graph"]["edges"]
        prompt += self.__edges_prompt() + "\n\n"

        prompt += main_prompts["graph"]["streets"]
        prompt += self.__streets_prompt() + "\n\n"

        prompt += main_prompts["graph"]["nodes_naming"] + "\n"

        prompt += main_prompts["graph"]["points_of_interest"] + "\n"
        prompt += self.__poi_prompt() + "\n\n"

        prompt += main_prompts["graph"]["accessibility_features"] + "\n"
        prompt += self.__road_features_prompt() + "\n\n"

        prompt += (
            main_prompts["units"].format(
                self.graph.reference_system.north,
                self.graph.reference_system.south,
                self.graph.reference_system.west,
                self.graph.reference_system.east,
            )
            + "\n"
        )

        prompt += main_prompts["context"].format(
            datetime.now().strftime("%A %m-%d-%Y %H:%M:%S"), str_dict(context)
        )

        prompt += "###Instructions###\n\n"
        prompt += main_prompts["instructions"].format(
            self.prompt_components["base_instructions"].strip()
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
