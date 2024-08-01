import math
from typing import List, Optional

from openai import OpenAI, OpenAIError
from openai.types.chat import (ChatCompletionAssistantMessageParam,
                               ChatCompletionMessageParam,
                               ChatCompletionSystemMessageParam,
                               ChatCompletionUserMessageParam)

from .graph import Coords, Graph


class LLM:
    MAX_TOKENS = 1000
    TEMPERATURE = 0.2

    def __init__(
        self,
        graph: Graph,
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
    ) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.client = OpenAI()
        self.prompt_formatter = PromptFormatter(graph)

        self.history: List[ChatCompletionMessageParam] = list()
        self.history.append(self.prompt_formatter.get_main_prompt())

    def reset(self) -> None:
        self.history.clear()

    def ask(self, question: str, position: Optional[Coords]) -> Optional[str]:
        new_message = self.prompt_formatter.get_user_message(question, position)
        self.history.append(new_message)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-05-13",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=self.history,
            )
        except OpenAIError as e:
            print(f"An error occurred: {e}")
            return None

        response_message = response.choices[0].message
        self.history.append(
            ChatCompletionAssistantMessageParam(
                content=response_message.content, role="assistant"
            )
        )

        return response_message.content

    def save_chat(self, filename: str) -> None:
        msgs: List[str] = list()
        for msg in self.history:
            if "content" in msg:
                msgs.append(f"{msg['role']}:\n{msg['content']}")

        with open(filename, "w") as f:
            f.write("\n\n".join(msgs))


class PromptFormatter:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def get_user_message(
        self, question: str, position: Optional[Coords]
    ) -> ChatCompletionUserMessageParam:
        if position is not None:
            edge = self.graph.get_nearest_edge(position)

            edge_pixels = edge[0].distance_from(edge[1])
            distance_pixels_node1 = edge[0].distance_from(position)
            distance_pixels_node2 = edge[1].distance_from(position)

            distance_m_node1 = distance_pixels_node1 * edge.length / edge_pixels
            distance_m_node1 = math.floor(distance_m_node1)
            distance_m_node2 = distance_pixels_node2 * edge.length / edge_pixels
            distance_m_node2 = math.floor(distance_m_node2)

            between_streets = ", ".join(edge.between_streets)

            instructions = (
                f"""My coordinates are {position}, """
                f"""the closest point of the road network is edge {edge.id}, """
                f"""which is part of {edge.street}, between {between_streets}.\n"""
                f"""I'm at a distance of {distance_m_node1} m from node {edge.node1.id} and {distance_m_node2} m from node {edge.node2.id}.\n"""
                """Continue answering my questions with the updated position\n"""
                """Remembet to not mention the underlying graph or the cartesian plane in your answers."""
            )

            question = f"{instructions}\n\n{question}"

        return ChatCompletionUserMessageParam(content=question, role="user")

    def get_main_prompt(self) -> ChatCompletionSystemMessageParam:
        prompt = ""

        prompt += "Consider the following points on a cartesian plane at the associated coordinates:\n"
        prompt += self.graph.nodes_prompt() + "\n\n"

        prompt += (
            """Each point is a node of a road network graph and represents the intersection of two or more streets. """
            """Each edge connects two nodes and is specified with this notation: nX - nY. """
            """For example the edge "n3 - n5" would connect node n3 with node n5. """
            """Each street is a sequence of connected edges on the graph. These are the streets of the road network graph:\n"""
        )
        prompt += self.graph.edges_prompt() + "\n\n"

        prompt += (
            f"""North is indicated by the vector {self.graph.reference_system['north']}, """
            f"""South by {self.graph.reference_system['south']}, """
            f""" West by {self.graph.reference_system['west']}, and """
            f"""East by {self.graph.reference_system['east']}\n\n"""
        )

        prompt += "These are the names of the streets in the graph; you will use them to identify each street."
        prompt += self.graph.streets_prompt() + "\n\n"

        prompt += (
            """Nodes are named after the edges intersecting at their coordinates. """
            """For example a node at the intersection between the Webster Street edge and the Washington Street edge """
            """will be named "Intersection of Webster Street and Fillmore Street". """
            """Streets without nodes in common can't intersect.\n"""
            """If the edges intersecting at a node belong to the same street, the node will be named after that street.\n"""
            """If a node is connected to only one edge the node's name will be that of the edge's street.\n\n"""
        )

        prompt += (
            """These are points of interest along the road network. Each point has three import parameters:\n"""
            """- edge: the edge the point is located on\n"""
            """- distance: the distance of the point from the first node of the edge\n"""
            """- street: the identifier of the street the edge belong to. Replace street ids with their respective names.\n\n"""
        )
        prompt += self.graph.poi_prompt() + "\n\n"

        prompt += (
            """I will now ask questions about the points of interest or the road network.\n"""
            """Answer without mentioning in your response the underlying graph and the cartesian plane; only use the provided information.\n"""
            """Give me a direct and precise answer and keep it as short as possible. Be objective.\n"""
            """Consider that I'm blind and I can't see the environment around me."""
        )

        return ChatCompletionSystemMessageParam(
            content=prompt,
            role="system",
        )
