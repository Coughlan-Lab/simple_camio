from enum import Enum

from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params import FunctionDefinition

from src.graph import Graph


class ToolCall(str, Enum):
    # function name, response after tool call should be further processed
    GET_DISTANCE = "get_distance", False
    GET_DISTANCE_TO_POINT_OF_INTEREST = "get_distance_to_point_of_interest", False
    AM_I_AT_POINT_OF_INTEREST = "am_i_at_point_of_interest", False
    GET_NEARBY_POINTS_OF_INTEREST = "get_nearby_points_of_interest", False
    GET_POINT_OF_INTEREST_DETAILS = "get_point_of_interest_details", False
    GET_ROUTE = "get_route", True
    GET_ROUTE_TO_POINT_OF_INTEREST = "get_route_to_point_of_interest", True

    def __new__(cls, *args):
        obj = str.__new__(cls, args[0])
        obj._value_ = args[0]
        return obj

    def __init__(self, _: str, needs_further_processing: bool):
        self.__needs_further_processing = needs_further_processing

    def __str__(self) -> str:
        return self.value

    @property
    def needs_further_processing(self) -> bool:
        return self.__needs_further_processing

    @classmethod
    def get(cls, function_name: str) -> "ToolCall":
        return cls(function_name)


tool_calls = [
    ChatCompletionToolParam(
        type="function",
        function=FunctionDefinition(
            name=ToolCall.GET_DISTANCE,
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
            name=ToolCall.GET_DISTANCE_TO_POINT_OF_INTEREST,
            description=(
                "Get the distance between a point and a point of interest. "
                "Use this function to determine how far I am from a point of interest by providing "
                "the coordinates of my position and the index of the point of interest."
            ),
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
            name=ToolCall.AM_I_AT_POINT_OF_INTEREST,
            description=(
                "Check if a point is near a point of interest. "
                "Use this function to determine if I'm near a point of interest by providing "
                "the coordinates of my position and the index of the point of interest. "
                "If the result is negative, give me instructions on how to get there."
            ),
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
            name=ToolCall.GET_NEARBY_POINTS_OF_INTEREST,
            description=(
                "Get the points of interest within a certain maximum distance from a point. "
                "Call this function only if I specifically ask for nearby points of interest; "
                "If I ask for a point of interest, use the information provided in the prompt."
            ),
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
                        "description": (
                            "The maximum distance from the point. "
                            f"If not provided, a maximum distance of {Graph.NEARBY_THRESHOLD} m is used. "
                            f"If not told otherwise, use a distance of at least {Graph.NEARBY_THRESHOLD} m."
                        ),
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
            name=ToolCall.GET_POINT_OF_INTEREST_DETAILS,
            description=(
                "Get the details of a point of interest. "
                "Use this function to retrieve comprehensive information about a specific point of interest, "
                "which can include a description, city, suburb, district, and accessibility information "
                "specifically designed for blind individuals. "
                "Additionally, it may provide contact information, website, payment options, building data, "
                "details about public transport networks, and the operator. "
                "Depending on the point of interest, other relevant information might also be available. "
                "When in doubt call this function to get more information about a point of interest."
            ),
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
    ChatCompletionToolParam(
        type="function",
        function=FunctionDefinition(
            name=ToolCall.GET_ROUTE,
            description="Get directions to reach a certain position.",
            parameters={
                "type": "object",
                "properties": {
                    "x1": {
                        "type": "number",
                        "description": "The x coordinate of the starting position",
                    },
                    "y1": {
                        "type": "number",
                        "description": "The y coordinate of the starting position",
                    },
                    "x2": {
                        "type": "number",
                        "description": "The x coordinate of the destination",
                    },
                    "y2": {
                        "type": "number",
                        "description": "The y coordinate of the destination",
                    },
                    "only_by_walking": {
                        "type": "boolean",
                        "description": (
                            "If true public transports are not considered and the route is calculated only by walking. "
                            "Set it to false if you want to use public transports to reach the destination."
                        ),
                    },
                    "transports": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "BUS",
                                "SUBWAY",
                                "TRAIN",
                                "LIGHT_RAIL",
                                "RAIL",
                            ],
                        },
                        "description": (
                            "An array of public transport types to consider in the route calculation. "
                            "Include more than one type to consider multiple public transport types. "
                            "If only_by_walking is true, this parameter is ignored."
                        ),
                    },
                    "transport_preference": {
                        "type": "string",
                        "enum": ["LESS_WALKING", "FEWER_TRANSFERS"],
                        "description": (
                            "The preference for the route calculation. "
                            "If only_by_walking is true, this parameter is ignored."
                        ),
                    },
                },
                "required": ["x1", "y1", "x2", "y2", "only_by_walking"],
                "additionalProperties": False,
            },
        ),
    ),
    ChatCompletionToolParam(
        type="function",
        function=FunctionDefinition(
            name=ToolCall.GET_ROUTE_TO_POINT_OF_INTEREST,
            description="Get directions to reach a point of interest.",
            parameters={
                "type": "object",
                "properties": {
                    "x1": {
                        "type": "number",
                        "description": "The x coordinate of the starting position",
                    },
                    "y1": {
                        "type": "number",
                        "description": "The y coordinate of the starting position",
                    },
                    "poi_index": {
                        "type": "number",
                        "description": "The index of the point of interest to reach",
                    },
                    "only_by_walking": {
                        "type": "boolean",
                        "description": (
                            "If true public transports are not considered and the route is calculated only by walking. "
                            "Set it to false if you want to use public transports to reach the point of interest."
                        ),
                    },
                    "transports": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "BUS",
                                "SUBWAY",
                                "TRAIN",
                                "LIGHT_RAIL",
                                "RAIL",
                            ],
                        },
                        "description": (
                            "An array of public transport types to consider in the route calculation. "
                            "Include more than one type to consider multiple public transport types. "
                            "If only_by_walking is true, this parameter is ignored."
                        ),
                    },
                    "transport_preference": {
                        "type": "string",
                        "enum": ["LESS_WALKING", "FEWER_TRANSFERS"],
                        "description": (
                            "The preference for the route calculation. "
                            "If only_by_walking is true, this parameter is ignored."
                        ),
                    },
                },
                "required": ["x1", "y1", "poi_index", "only_by_walking"],
                "additionalProperties": False,
            },
        ),
    ),
]
