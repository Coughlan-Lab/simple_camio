"""
Gesture detection and movement filtering for Simple CamIO.

This module contains classes for detecting hand gestures, filtering movement,
and recognizing interaction patterns like dwelling and tapping.
"""

import time
import numpy as np
from collections import deque
import logging
from src.config import MovementFilterConfig, GestureDetectorConfig

logger = logging.getLogger(__name__)


class MovementFilter:
    """
    Simple exponential smoothing filter for position data.

    This filter reduces jitter in hand tracking by applying exponential
    weighted averaging to position updates.
    """

    def __init__(self, beta=None):
        """
        Initialize the movement filter.

        Args:
            beta (float): Smoothing factor (0-1). If None, uses config default.
        """
        self.prev_position = None
        self.BETA = beta if beta is not None else MovementFilterConfig.BETA

    def push_position(self, position):
        """
        Update filter with new position and return smoothed position.

        Args:
            position (numpy.ndarray): New position [x, y, z]

        Returns:
            numpy.ndarray: Smoothed position
        """
        if self.prev_position is None:
            self.prev_position = position
        else:
            self.prev_position = (self.prev_position * (1 - self.BETA) +
                                  position * self.BETA)
        return self.prev_position


class MovementMedianFilter:
    """
    Median filter for robust position tracking.

    This filter uses a sliding window of recent positions and returns
    the median value for each coordinate, which is more robust to
    outliers than simple averaging.
    """

    def __init__(self):
        """Initialize the median filter with position and time queues."""
        self.MAX_QUEUE_LENGTH = MovementFilterConfig.MAX_QUEUE_LENGTH
        self.positions = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.times = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.AVERAGING_TIME = MovementFilterConfig.AVERAGING_TIME

    def push_position(self, position):
        """
        Update filter with new position and return median-filtered position.

        Args:
            position (numpy.ndarray): New position [x, y, z]

        Returns:
            numpy.ndarray: Median-filtered position over recent time window
        """
        self.positions.append(position)
        now = time.time()
        self.times.append(now)

        # Collect positions within the averaging time window
        i = len(self.times) - 1
        Xs, Ys, Zs = [], [], []

        while i >= 0 and now - self.times[i] < self.AVERAGING_TIME:
            Xs.append(self.positions[i][0])
            Ys.append(self.positions[i][1])
            Zs.append(self.positions[i][2])
            i -= 1

        # Return median of each coordinate
        return np.array([np.median(Xs), np.median(Ys), np.median(Zs)])


class GestureDetector:
    """
    Detector for dwell gestures (staying still vs moving).

    This class analyzes position history to determine if the user is
    dwelling (staying relatively still) at a location or actively moving.
    """

    def __init__(self):
        """Initialize the gesture detector with configuration parameters."""
        self.MAX_QUEUE_LENGTH = GestureDetectorConfig.MAX_QUEUE_LENGTH
        self.positions = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.times = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.DWELL_TIME_THRESH = GestureDetectorConfig.DWELL_TIME_THRESH
        self.X_MVMNT_THRESH = GestureDetectorConfig.X_MVMNT_THRESH
        self.Y_MVMNT_THRESH = GestureDetectorConfig.Y_MVMNT_THRESH
        self.Z_MVMNT_THRESH = GestureDetectorConfig.Z_MVMNT_THRESH

    def push_position(self, position):
        """
        Analyze new position and determine if user is dwelling or moving.

        Args:
            position (numpy.ndarray): Current position [x, y, z]

        Returns:
            tuple: (averaged_position, status) where status is 'still' or 'moving'
        """
        self.positions.append(position)
        now = time.time()
        self.times.append(now)

        # Collect positions within dwell time threshold
        i = len(self.times) - 1
        Xs, Ys, Zs = [], [], []

        while i >= 0 and now - self.times[i] < self.DWELL_TIME_THRESH:
            Xs.append(self.positions[i][0])
            Ys.append(self.positions[i][1])
            Zs.append(self.positions[i][2])
            i -= 1

        # Calculate movement range in each dimension
        Xdiff = max(Xs) - min(Xs)
        Ydiff = max(Ys) - min(Ys)
        Zdiff = max(Zs) - min(Zs)

        logger.debug(f"(i: {i}) X: {Xdiff}, Y: {Ydiff}, Z: {Zdiff}")

        # Determine if position is stable (dwelling)
        if (Xdiff < self.X_MVMNT_THRESH and
            Ydiff < self.Y_MVMNT_THRESH and
            Zdiff < self.Z_MVMNT_THRESH):
            # Calculate average position during dwell
            avg_position = np.array([
                sum(Xs) / float(len(Xs)),
                sum(Ys) / float(len(Ys)),
                sum(Zs) / float(len(Zs))
            ])
            return avg_position, 'still'
        else:
            return position, 'moving'

