"""
Detection Module - Hand pose detection, gesture recognition, and SIFT tracking.

This module provides:
- Hand pose detection with MediaPipe (pose_detector.py)
- SIFT-based template tracking (sift_detector.py)
- Gesture analysis and filtering (gesture_detection.py)
"""

from .pose_detector import CombinedPoseDetector
from .sift_detector import SIFTModelDetectorMP
from .gesture_detection import GestureDetector, MovementMedianFilter

__all__ = [
    'CombinedPoseDetector',
    'SIFTModelDetectorMP',
    'GestureDetector',
    'MovementMedianFilter',
]
