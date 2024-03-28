import os
import platform
import subprocess
from typing import Any, List, Generator
import cv2
from enum import Enum


class OS(Enum):
    MACOS = "Darwin"
    WINDOWS = "Windows"
    LINUX = "Linux"


if platform.system() == "Darwin":
    SYSTEM = OS.MACOS
elif platform.system() == "Windows":
    SYSTEM = OS.WINDOWS
elif platform.system() == "Linux":
    SYSTEM = OS.LINUX
else:
    raise NotImplementedError(f"Unknown os: {platform.system()}")

if SYSTEM == OS.MACOS:

    def open_file(path: str) -> None:
        if not os.path.exists(path):
            return
        subprocess.call(["open", path])

elif SYSTEM == OS.WINDOWS:

    def open_file(path: str) -> None:
        os.startfile(path)

else:

    def open_file(path: str) -> None:
        raise NotImplementedError(f"Unknown os: {SYSTEM}")


class CameraInfo:
    def __init__(self, index: int, name: str) -> None:
        self.index = index
        self.name = name

    index: int
    name: str


if SYSTEM == OS.WINDOWS or SYSTEM == OS.LINUX:
    from cv2_enumerate_cameras import (
        enumerate_cameras as camera_enumerator,
    )  #  type: ignore

else:

    def camera_enumerator(unused: Any = None) -> Generator[CameraInfo, Any, None]:
        non_working_ports = 0
        working_ports = 0

        dev_port = 0
        while working_ports < 3 and non_working_ports < 3:
            camera = cv2.VideoCapture(dev_port)
            if not camera.isOpened():
                non_working_ports += 1
            else:
                is_reading, _ = camera.read()
                w = camera.get(3)
                h = camera.get(4)
                if is_reading:
                    working_ports += 1
                    yield CameraInfo(dev_port, f"Camera {dev_port} {w}x{h}")
                else:
                    non_working_ports += 1
            dev_port += 1


def enumerate_cameras(prefs: Any = None) -> List[CameraInfo]:
    return list(camera_enumerator(prefs))
