"""
Interaction policy for zone-based map interactions.

This module handles the logic for determining which zone on the map
the user is interacting with based on their finger position.
"""

import cv2 as cv
import numpy as np
import logging
from config import InteractionConfig
from utils import color_to_index

logger = logging.getLogger(__name__)


class InteractionPolicy2D:
    """
    2D interaction policy for zone detection on a color-coded map.

    This class maps 3D finger positions to 2D map zones using color coding,
    applies filtering to reduce noise, and checks Z-axis threshold for
    touch detection.
    """

    def __init__(self, model):
        """
        Initialize the interaction policy.

        Args:
            model (dict): Map model configuration containing the color-coded map image
        """
        self.model = model
        self.image_map_color = cv.imread(model['filename'], cv.IMREAD_COLOR)
        self.ZONE_FILTER_SIZE = InteractionConfig.ZONE_FILTER_SIZE
        self.Z_THRESHOLD = InteractionConfig.Z_THRESHOLD

        # Ring buffer for zone filtering (mode filter)
        self.zone_filter = -1 * np.ones(self.ZONE_FILTER_SIZE, dtype=int)
        self.zone_filter_cnt = 0

        logger.info(f"Initialized interaction policy with Z threshold: {self.Z_THRESHOLD} cm")

    def _mode_int(self, arr):
        """
        Fast mode for small integer arrays; ignores values < 0 (e.g., -1 placeholders).
        """
        valid = arr[arr >= 0]
        if valid.size == 0:
            return -1
        vals, counts = np.unique(valid, return_counts=True)
        return int(vals[np.argmax(counts)])

    def push_gesture(self, position):
        """
        Process a gesture position and return the active zone ID.

        This method:
        1. Maps the position to a zone color on the map
        2. Converts color to zone ID
        3. Applies mode filtering to reduce noise
        4. Checks Z-threshold to determine if user is "touching" the map

        Args:
            position (numpy.ndarray): 3D position [x, y, z] in map coordinates

        Returns:
            int: Zone ID if touching (z < threshold), -1 otherwise
        """
        # Get zone color at the position
        zone_color = self._get_zone_color(position, self.image_map_color)

        # Convert color to zone index
        zone_idx = color_to_index(zone_color)

        # Update ring buffer
        self.zone_filter[self.zone_filter_cnt] = zone_idx
        self.zone_filter_cnt = (self.zone_filter_cnt + 1) % self.ZONE_FILTER_SIZE

        # Get mode (most common zone in buffer) without SciPy
        zone = self._mode_int(self.zone_filter)

        # Check Z-threshold for touch detection
        if np.abs(position[2]) < self.Z_THRESHOLD:
            return zone
        else:
            return -1

    def _get_zone_color(self, point_of_interest, img_map):
        """
        Retrieve the color at a specific point on the map.

        Args:
            point_of_interest (numpy.ndarray): Point coordinates [x, y, z]
            img_map (numpy.ndarray): Color-coded map image

        Returns:
            list: BGR color values [B, G, R] or [0, 0, 0] if out of bounds
        """
        x = int(point_of_interest[0])
        y = int(point_of_interest[1])

        # Check if point is within map bounds
        if 0 <= x < img_map.shape[1] and 0 <= y < img_map.shape[0]:
            return img_map[y, x]
        else:
            logger.debug(f"Point ({x}, {y}) out of bounds")
            return [0, 0, 0]
