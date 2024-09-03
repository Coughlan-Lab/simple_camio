import argparse
import json
import os
import time
from functools import reduce
from typing import (Any, Dict, Generic, List, Mapping, Optional, Protocol,
                    Tuple, TypeVar, Union)

import cv2


def str_format(v: Any) -> str:
    return str(v).replace("_", " ")


def str_dict(d: Union[Dict[Any, Any], Mapping[Any, Any]], indent: int = 0) -> str:
    res = ""

    for key, value in d.items():
        res += " " * indent + str_format(key) + ": "
        if isinstance(value, dict):
            res += "\n" + str_dict(value, indent + 4)
        elif isinstance(value, list):
            if len(value) == 0:
                res += "[]\n"
            elif len(value) == 1:
                res += "[ " + str_format(value[0]) + " ]\n"
            else:
                res += "[\n"
                for item in value:
                    res += " " * (indent + 4) + str_format(item) + ",\n"
                res += " " * indent + "]\n"
        else:
            res += str_format(value) + "\n"

    return res


def select_camera_port() -> Optional[int]:
    ports = get_working_camera_ports()

    if len(ports) == 0:
        return None
    elif len(ports) == 1:
        return int(ports[0][0])
    else:
        print("The following cameras were detected:")

        for i in range(len(ports)):
            print(f"{i}) Port {ports[i][0]}: {ports[i][1]} x {ports[i][2]}")

        while True:
            selected_index = input("Please select which camera you would like to use: ")

            if selected_index.isnumeric() and 0 <= int(selected_index) < len(ports):
                break

            print(
                f"Invalid selection. Please, insert a number between 0 and {len(ports) - 1}."
            )

        return int(ports[int(selected_index)][0])


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
    def __init__(self, max_size: int, max_life: float = 1) -> None:
        assert max_size > 0
        assert max_life > 0

        self.max_size = max_size
        self.max_life = max_life
        self.buffer: List[Tuple[T, float]] = list()

    def add(self, value: T) -> None:
        if len(self.buffer) == self.max_size:
            self.buffer.pop(0)
        self.buffer.append((value, time.time()))

    def items(self) -> List[T]:
        now = time.time()
        self.buffer = [
            (item, timestamp)
            for item, timestamp in self.buffer
            if now - timestamp < self.max_life
        ]
        return [item for item, _ in self.buffer]

    def clear(self) -> None:
        self.buffer.clear()

    def mode(self) -> Optional[T]:
        items = self.items()

        if len(items) == 0:
            return None
        return max(set(items), key=items.count)

    def last(self) -> Optional[T]:
        if len(self.buffer) == 0:
            return None

        if time.time() - self.buffer[-1][1] > self.max_life:
            return None

        return self.buffer[-1][0]

    def __str__(self) -> str:
        return str(self.items())

    def __repr__(self) -> str:
        return str(self)


U = TypeVar("U", bound="UBound")


class UBound(Protocol):
    def __add__(self: T, other: T) -> T: ...
    def __truediv__(self: T, other: int) -> T: ...


class ArithmeticBuffer(Buffer[U]):
    def __init__(self, max_size: int, max_life: float = 1) -> None:
        super().__init__(max_size, max_life)

    def average(self) -> Optional[U]:
        items = self.items()

        if len(items) == 0:
            return None
        return reduce(lambda x, y: x + y, items) / len(items)


class FPSManager:
    def __init__(self) -> None:
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0.0

    def update(self) -> float:
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
    "--tts_rate",
    help="TTS speed rate (words per minute).",
    type=int,
    default=200,
)
camio_parser.add_argument(
    "--debug",
    help="Debug mode.",
    action="store_true",
    default=False,
)
