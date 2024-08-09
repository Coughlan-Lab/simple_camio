import argparse
import json
import os
import time
from functools import reduce
from typing import Any, Dict, Generic, List, Optional, Protocol, Tuple, TypeVar

import cv2
import pyglet


def str_dict(d: Dict[Any, Any], indent: int = 0) -> str:
    res = ""

    for key, value in d.items():
        res += " " * indent + str(key) + ": "
        if isinstance(value, dict):
            res += "\n" + str_dict(value, indent + 4)
        elif isinstance(value, list):
            if len(value) == 0:
                res += "[]\n"
            elif len(value) == 1:
                res += "[ " + str(value[0]) + " ]\n"
            else:
                res += "[\n"
                for item in value:
                    res += " " * (indent + 4) + str(item) + ",\n"
                res += " " * indent + "]\n"
        else:
            res += str(value) + "\n"

    return res


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
        camera = cv2.VideoCapture(dev_port)
        if not camera.isOpened():
            non_working_ports.append(dev_port)
            print("Port %s is not working." % dev_port)
        else:
            is_reading, _ = camera.read()
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


def load_map_parameters(filename: str) -> Optional[Dict[str, Any]]:
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            map_params = json.load(f)
            print("loaded map parameters from file.")
    else:
        return None
    return dict(map_params)


T = TypeVar("T")


class Buffer(Generic[T]):
    def __init__(self, max_size: int) -> None:
        assert max_size > 0

        self.max_size = max_size
        self.buffer: List[T] = list()
        self.time_last_update = time.time()

    @property
    def time_from_last_update(self) -> float:
        return time.time() - self.time_last_update

    def add(self, value: T) -> None:
        if len(self.buffer) == self.max_size:
            self.buffer.pop(0)
        self.buffer.append(value)
        self.time_last_update = time.time()

    def clear(self) -> None:
        self.buffer.clear()

    def mode(self) -> Optional[T]:
        if len(self.buffer) == 0:
            return None
        return max(set(self.buffer), key=self.buffer.count)

    def last(self) -> Optional[T]:
        if len(self.buffer) == 0:
            return None
        return self.buffer[-1]

    def __str__(self) -> str:
        return str(self.buffer)

    def __repr__(self) -> str:
        return str(self)


U = TypeVar("U", bound="UBound")


class UBound(Protocol):
    def __add__(self: T, other: T) -> T: ...
    def __truediv__(self: T, other: int) -> T: ...


class ArithmeticBuffer(Buffer[U]):
    def __init__(self, max_size: int) -> None:
        self.max_size = max_size
        self.buffer: List[U] = list()
        self.time_last_update = time.time()

    def average(self) -> Optional[U]:
        if len(self.buffer) == 0:
            return None

        return reduce(lambda x, y: x + y, self.buffer) / len(self.buffer)


class FPSManager:
    def __init__(self) -> None:
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0.0

    def update(self) -> float:
        pyglet.clock.tick()
        pyglet.app.platform_event_loop.dispatch_posted_events()

        current_time = time.time()
        self.frame_count += 1
        elapsed_time = current_time - self.last_time

        if elapsed_time > 1.0:
            self.fps = self.frame_count / elapsed_time
            self.frame_count = 0
            self.last_time = current_time

        return self.fps


camio_parser = argparse.ArgumentParser(description="CamIO, with LLM integration")
camio_parser.add_argument(
    "--model",
    help="Path to model json file.",
    default="models/new_york/new_york.json",
)
camio_parser.add_argument(
    "--out",
    help="Path to chat save file.",
    default="out/last_chat.txt",
)
camio_parser.add_argument(
    "--debug",
    help="Debug mode.",
    action="store_true",
    default=False,
)
