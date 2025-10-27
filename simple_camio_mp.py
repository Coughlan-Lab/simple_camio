"""
Simple CamIO MediaPipe module - Legacy compatibility layer.

This module re-exports classes from the new modular structure for backward compatibility
with existing code that imports from simple_camio_mp.
"""

# Import from new modular structure
from pose_detector import PoseDetectorMP
from sift_detector import SIFTModelDetectorMP

# Re-export for backward compatibility
__all__ = ['PoseDetectorMP', 'SIFTModelDetectorMP']

