from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params import FunctionDefinition

from src.graph import Graph

tool_calls = [
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
            name="am_i_at_point_of_interest",
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
            name="get_nearby_points_of_interest",
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
            name="get_point_of_interest_details",
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
            name="get_route",
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
            name="get_route_to_poi",
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
