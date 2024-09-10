# type: ignore
from typing import List, Optional, Tuple

import cv2
import numpy as np
import numpy.typing as npt


class VideoCapture:
    HEIGHT = 1080
    WIDTH = 1920

    def __init__(self, capture_index: int) -> None:
        self.capture_index = capture_index
        self.__capture = cv2.VideoCapture(self.capture_index)

        self.__capture.set(cv2.CAP_PROP_FRAME_HEIGHT, VideoCapture.HEIGHT)
        self.__capture.set(cv2.CAP_PROP_FRAME_WIDTH, VideoCapture.WIDTH)
        self.__capture.set(cv2.CAP_PROP_FOCUS, 0)

    def is_opened(self) -> bool:
        return self.__capture.isOpened()

    def read(self) -> Optional[npt.NDArray[np.uint8]]:
        ok, frame = self.__capture.read()
        return frame if ok else None

    def stop(self) -> None:
        self.__capture.release()

    @staticmethod
    def get_capture() -> Optional[cv2.VideoCapture]:
        cam_port = 1  # select_camera_port()
        if cam_port is None:
            return None

        return VideoCapture(cam_port)


def select_camera_port() -> Optional[int]:
    ports = get_working_camera_ports()

    if len(ports) == 0:
        return None

    if len(ports) == 1:
        return int(ports[0][0])

    print("\nAvailable cameras:")

    for i in range(len(ports)):
        print(f"{i + 1}) Camera {ports[i][0]}: {ports[i][1]} x {ports[i][2]}")

    while True:
        selected_index = input("Please, select which camera you would like to use: ")

        if selected_index.isnumeric() and 1 <= int(selected_index) <= len(ports):
            break

        print(f"Invalid selection. Please, insert a number between 1 and {len(ports)}.")

    return int(ports[int(selected_index) - 1][0])


def get_working_camera_ports(max_non_working: int = 3) -> List[Tuple[int, int, int]]:
    non_working = 0
    working_ports = list()

    dev_port = 0
    while non_working < max_non_working:
        camera = cv2.VideoCapture(dev_port)

        if not camera.isOpened():
            non_working += 1
        else:
            is_reading, _ = camera.read()
            w = camera.get(3)
            h = camera.get(4)

            if is_reading:
                working_ports.append((dev_port, h, w))

        dev_port += 1

    return working_ports
