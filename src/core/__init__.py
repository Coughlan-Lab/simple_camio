"""
Core Module - Utilities, workers, and interaction logic.

This module contains fundamental building blocks of the CamIO system:
- Utility functions (utils.py)
- Background worker threads (workers.py)
- Interaction policies (interaction_policy.py)

Note: Configuration has been moved to src.config for easier access.
"""

from .utils import (
    select_camera_port,
    load_map_parameters,
    draw_rectangle_on_image,
    draw_rectangle_from_points,
    is_gesture_valid,
    normalize_gesture_location
)

from .workers import (
    PoseWorker,
    SIFTWorker,
    AudioWorker,
    AudioCommand
)

from .interaction_policy import InteractionPolicy2D

from .camera_thread import ThreadedCamera

from .display_thread import DisplayThread

__all__ = [
    # Utilities
    'select_camera_port',
    'load_map_parameters',
    'draw_rectangle_on_image',
    'draw_rectangle_from_points',
    'is_gesture_valid',
    'normalize_gesture_location',
    # Workers
    'PoseWorker',
    'SIFTWorker',
    'AudioWorker',
    'AudioCommand',
    # Interaction
    'InteractionPolicy2D',
    # Camera
    'ThreadedCamera',
    # Display
    'DisplayThread',
]
