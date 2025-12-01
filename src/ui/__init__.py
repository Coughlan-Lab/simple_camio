"""
UI Module - Display, rendering, and user interface components.

This module provides:
- Camera setup and configuration
- Overlay rendering (tracking rectangles, status text, FPS)
- UI drawing utilities
"""

from .display import (
    draw_map_tracking,
    draw_ui_overlay,
    setup_camera
)

__all__ = [
    'draw_map_tracking',
    'draw_ui_overlay',
    'setup_camera',
]
