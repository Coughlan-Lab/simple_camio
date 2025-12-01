"""
Utility functions for Simple CamIO.

This module contains helper functions for camera management, file loading,
drawing, and other common operations.
"""

import os
import sys
import json
import cv2 as cv
import numpy as np
import logging

logger = logging.getLogger(__name__)


# ==================== Camera Management ====================

def list_camera_ports():
    """
    Test camera ports and return available and working ports.

    Returns:
        tuple: (available_ports, working_ports, non_working_ports)
               working_ports contains tuples of (port, height, width)
    """
    non_working_ports = []
    dev_port = 0
    working_ports = []
    available_ports = []

    # Stop testing after 3 consecutive non-working ports
    while len(non_working_ports) < 3:
        camera = cv.VideoCapture(dev_port)
        if not camera.isOpened():
            non_working_ports.append(dev_port)
            logger.info(f"Port {dev_port} is not working.")
        else:
            is_reading, img = camera.read()
            w = camera.get(3)
            h = camera.get(4)
            if is_reading:
                logger.info(f"Port {dev_port} is working and reads images ({h} x {w})")
                working_ports.append((dev_port, h, w))
            else:
                logger.info(f"Port {dev_port} for camera ({h} x {w}) is present but does not read.")
                available_ports.append(dev_port)
        camera.release()
        dev_port += 1

    return available_ports, working_ports, non_working_ports


def select_camera_port():
    """
    Automatically select or prompt user to select a camera port.

    Returns:
        int: Selected camera port number
    """
    available_ports, working_ports, non_working_ports = list_camera_ports()

    if len(working_ports) == 1:
        logger.info(f"Auto-selected camera port {working_ports[0][0]}")
        return working_ports[0][0]
    elif len(working_ports) > 1:
        print("The following cameras were detected:")
        for i in range(len(working_ports)):
            print(f'{i}) Port {working_ports[i][0]}: {working_ports[i][1]} x {working_ports[i][2]}')
        cam_selection = input("Please select which camera you would like to use: ")
        return working_ports[int(cam_selection)][0]
    else:
        logger.warning("No working cameras detected, using default port 0")
        return 0


# ==================== File Loading ====================

def load_map_parameters(filename):
    """
    Load map parameters from a JSON configuration file.

    Args:
        filename (str): Path to the JSON configuration file

    Returns:
        dict: Map model parameters

    Raises:
        SystemExit: If file not found or invalid
    """
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            map_params = json.load(f)
            logger.info(f"Loaded map parameters from {filename}")
            return map_params['model']
    else:
        logger.error(f"No map parameters file found at {filename}")
        print("No map parameters file found at " + filename)
        print("Usage: simple_camio.exe --input1 <filename>")
        print(" ")
        print("Press any key to exit.")
        _ = sys.stdin.read(1)
        sys.exit(1)


# ==================== Drawing Functions ====================

def draw_rectangle_on_image(image, map_shape, homography):
    """
    Draw a rectangle showing the detected map region.

    Args:
        image (numpy.ndarray): Image to draw on
        map_shape (tuple): Shape of the map image (height, width)
        homography (numpy.ndarray): 3x3 homography matrix

    Returns:
        numpy.ndarray: Image with rectangle drawn
    """
    img_corners = np.array([
        [0, 0],
        [map_shape[1], 0],
        [map_shape[1], map_shape[0]],
        [0, map_shape[0]]
    ], dtype=np.float32).reshape(-1, 1, 2)

    H_inv = np.linalg.inv(homography)
    pts = cv.perspectiveTransform(img_corners, H_inv)

    # Draw rectangle with lines
    pts_int = np.int32(pts)
    cv.polylines(image, [pts_int], isClosed=True, color=(0, 255, 0), thickness=3)

    # Draw corner dots for emphasis
    for pt in pts:
        cv.circle(image, (int(pt[0][0]), int(pt[0][1])), 5, (0, 255, 0), -1)

    return image


def draw_rectangle_from_points(image, pts, color=(0, 255, 0), thickness=3):
    """
    Draw a polygon from pre-computed transformed points.

    Args:
        image (numpy.ndarray): Image to draw on
        pts (numpy.ndarray): Points in cv.perspectiveTransform output format
        color (tuple): BGR color for the rectangle
        thickness (int): Line thickness

    Returns:
        numpy.ndarray: Image with rectangle drawn
    """
    if pts is None:
        return image

    try:
        pts_int = np.int32(pts)
        cv.polylines(image, [pts_int], isClosed=True, color=color, thickness=thickness)

        # Draw corner dots as subtle markers
        for pt in pts.reshape(-1, 2):
            cv.circle(image, (int(pt[0]), int(pt[1])), 4, color, -1)
    except Exception as e:
        logger.debug(f"Error drawing rectangle: {e}")

    return image


# ==================== Validation Functions ====================

def is_gesture_valid(gesture):
    """
    Check if a gesture location is valid.

    Args:
        gesture: Gesture location (should be array-like with at least 3 elements)

    Returns:
        bool: True if gesture is valid, False otherwise
    """
    if gesture is None:
        return False
    if not hasattr(gesture, "__len__"):
        return False
    try:
        arr = np.asarray(gesture)
        return arr.size >= 3
    except Exception:
        return False


def normalize_gesture_location(gesture_loc):
    """
    Normalize gesture location to ensure it's a 1D array with 3 elements.

    Args:
        gesture_loc: Raw gesture location data

    Returns:
        numpy.ndarray or None: Normalized [x, y, z] array or None if invalid
    """
    if gesture_loc is None:
        return None

    try:
        arr = np.asarray(gesture_loc)

        if arr.size == 0:
            return None
        elif arr.size >= 3:
            # If multiple triplets, take the last (most recent)
            if arr.size % 3 == 0 and arr.size > 3:
                return arr.reshape(-1, 3)[-1].astype(float)
            else:
                # Take first 3 elements as fallback
                return arr.flatten()[:3].astype(float)
        else:
            return None
    except Exception as e:
        logger.debug(f"Error normalizing gesture: {e}")
        return None


# ==================== Color Conversion ====================

def color_to_index(color):
    """
    Convert BGR color tuple to a unique integer index.

    Args:
        color (tuple/list): BGR color values [B, G, R]

    Returns:
        int: Unique index for the color
    """
    return 256 * 256 * color[2] + 256 * color[1] + color[0]

