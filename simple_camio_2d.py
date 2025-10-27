"""
Simple CamIO 2D module - Legacy compatibility layer.

This module re-exports classes from the new modular structure for backward compatibility
with existing code that imports from simple_camio_2d.
"""

# Import from new modular structure
from interaction_policy import InteractionPolicy2D
from audio import ZoneAudioPlayer as CamIOPlayer2D

# Re-export for backward compatibility
__all__ = ['InteractionPolicy2D', 'CamIOPlayer2D']

