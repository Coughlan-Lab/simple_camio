from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params import FunctionDefinition

from src.graph import Graph
from src.utils import StrEnum


class ToolCall(StrEnum):
    GET_DISTANCE = "get_distance"
    GET_DISTANCE_TO_POINT_OF_INTEREST = "get_distance_to_point_of_interest"
    AM_I_AT_POINT_OF_INTEREST = "am_i_at_point_of_interest"
    GET_NEARBY_POINTS_OF_INTEREST = "get_nearby_points_of_interest"
    GET_POINT_OF_INTEREST_DETAILS = "get_point_of_interest_details"
    GUIDE_TO_DESTINATION = "guide_to_destination"
    GUIDE_TO_POINT_OF_INTEREST = "guide_to_point_of_interest"
    ENABLE_POINTS_OF_INTERESTS = "enable_points_of_interests"

    @classmethod
    def get(cls, function_name: str) -> "ToolCall":
        return cls(function_name)


tool_calls = [
    ChatCompletionToolParam(
        type="function",
        function=FunctionDefinition(
            name=ToolCall.GET_DISTANCE,
            description="Get the distance between two points on the road network graph. The distance unit is feet.",
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
                "which will include its precise location, city, suburb, district, nearest intersection "
                "and accessibility information specifically designed for blind individuals. "
                "Additionally, it may provide a description, contact information, website, payment options, building data, "
                "details about public transport networks, and its operator. "
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
            name=ToolCall.GUIDE_TO_DESTINATION,
            description=(
                "Guide me to a specific position. You MUST call this function everytime I ask for directions to a specific position, like an intersection."
                "This function does not return a response. It is used to guide me to a specific position. "
            ),
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
                    "step_by_step": {
                        "type": "boolean",
                        "description": (
                            "If true, provide step-by-step directions. "
                            "If false, provide direct navigation to the destination. "
                            "If unsure, ask me if I want step-by-step directions or direct navigation to the destination."
                        ),
                    },
                    "alternative_route_index": {
                        "type": "number",
                        "description": (
                            "The index of the alternative route to calculate. Must be a positive integer greater than 0. "
                            "If not provided, the default route is calculated."
                        ),
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
            name=ToolCall.GUIDE_TO_POINT_OF_INTEREST,
            description=(
                "Guide me to a specific point of interest. You MUST call this function everytime I ask for directions to a point of interest."
                "This function does not return a response. It is used to guide me to a specific point of interest. "
            ),
            parameters={
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "description": "The x coordinate of the starting position",
                    },
                    "y": {
                        "type": "number",
                        "description": "The y coordinate of the starting position",
                    },
                    "poi_index": {
                        "type": "number",
                        "description": "The index of the point of interest to reach",
                    },
                    "step_by_step": {
                        "type": "boolean",
                        "description": (
                            "If true, provide step-by-step directions. "
                            "If false, provide direct navigation to the destination. "
                            "If unsure, ask me if I want step-by-step directions or direct navigation to the destination."
                        ),
                    },
                    "alternative_route_index": {
                        "type": "number",
                        "description": (
                            "The index of the alternative route to calculate. Must be a positive integer greater than 0. "
                            "If not provided, the default route is calculated."
                        ),
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
            name=ToolCall.ENABLE_POINTS_OF_INTERESTS,
            description=(
                "Enable points of interest to be used in the conversation. "
                "You MUST call this function everytime I ask you a question; otherwise, I won't be able to locate them. "
                "Include all the points of interest that are relevant to the conversation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "points_of_interest": {
                        "type": "array",
                        "items": {
                            "type": "number",
                        },
                        "description": (
                            "An array of point of interest indices to be enabled. "
                            "Include all the points of interest that are relevant to the current question. "
                            "Include more than one index to enable multiple points of interest. "
                            "Pass an empty array along with disable_previous set to true to disable all points of interest."
                        ),
                    },
                    "disable_previous": {
                        "type": "boolean",
                        "description": (
                            "If true, disable all the previously enabled points of interest. "
                            "Set it to false if you want to keep the previously enabled points of interest. "
                            "If unsure, set it to true to disable all the previously enabled points of interest. "
                            "Don't keep old points of interest enabled if they are not relevant to the current question."
                        ),
                    },
                },
                "required": ["points_of_interest", "disable_previous"],
                "additionalProperties": False,
            },
        ),
    ),
]
