import json
import os
import sys
from typing import Any, Dict, List, Tuple

import cv2 as cv
import numpy as np
import numpy.typing as npt


def select_cam_port() -> int:
    _, working_ports, _ = list_ports()
    if len(working_ports) == 1:
        return int(working_ports[0][0])
    elif len(working_ports) > 1:
        print("The following cameras were detected:")
        for i in range(len(working_ports)):
            print(
                f"{i}) Port {working_ports[i][0]}: {working_ports[i][1]} x {working_ports[i][2]}"
            )
        cam_selection = input("Please select which camera you would like to use: ")
        return int(working_ports[int(cam_selection)][0])
    else:
        return 0


def list_ports() -> Tuple[List[int], List[Tuple[int, int, int]], List[int]]:
    """
    Test the ports and returns a tuple with the available ports and the ones that are working.
    """
    non_working_ports: List[int] = list()
    dev_port = 0
    working_ports = list()
    available_ports = list()
    while (
        len(non_working_ports) < 3
    ):  # if there are more than 2 non working ports stop the testing.
        camera = cv.VideoCapture(dev_port)
        if not camera.isOpened():
            non_working_ports.append(dev_port)
            print("Port %s is not working." % dev_port)
        else:
            is_reading, img = camera.read()
            w = camera.get(3)
            h = camera.get(4)
            if is_reading:
                print(
                    "Port %s is working and reads images (%s x %s)" % (dev_port, h, w)
                )
                working_ports.append((dev_port, h, w))
            else:
                print(
                    "Port %s for camera ( %s x %s) is present but does not read."
                    % (dev_port, h, w)
                )
                available_ports.append(dev_port)
        dev_port += 1
    return available_ports, working_ports, non_working_ports


def load_map_parameters(filename: str) -> Dict[str, Any]:
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            map_params = json.load(f)
            print("loaded map parameters from file.")
    else:
        print("No map parameters file found at " + filename)
        print("Usage: simple_camio.exe --input1 <filename>")
        print(" ")
        print("Press any key to exit.")
        _ = sys.stdin.read(1)
        exit(0)
    return dict(map_params["model"])


# Function to sort corners by id based on the order specified in the id_list,
# such that the scene array matches the obj array in terms of aruco marker ids
# and the appropriate corners.
def sort_corners_by_id(corners, ids, id_list):
    use_index = np.zeros(len(id_list) * 4, dtype=bool)
    scene = np.empty((len(id_list) * 4, 2), dtype=np.float32)
    for i in range(len(corners)):
        id = ids[i, 0]
        if id in id_list:
            corner_num = id_list.index(id)
            for j in range(4):
                use_index[4 * corner_num + j] = True
                scene[4 * corner_num + j, :] = corners[i][0][j]
    return scene, use_index
