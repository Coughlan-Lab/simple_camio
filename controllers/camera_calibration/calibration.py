from tkinter import CENTER, DISABLED, N, NORMAL, RIGHT, SE, SW

from ..components import Camera
from view import FrameViewer
from controllers.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from typing import Any, Dict, Literal, Union
from res import Fonts, Colors, ImgsManager, DocsManager
from PIL import Image
from model.simple_calibration import Calibration as Calibrator
import numpy as np
import threading
import cv2
from model.utils import open_file


class Calibration(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent, show_back=True)

        title = tk.CTkLabel(
            self,
            text="Print the calibration map, frame it with you camera and\nmatch its corners with the on-screen preview",
            font=Fonts.subtitle,
            height=44,
            text_color=Colors.text,
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        icon = tk.CTkImage(
            light_image=Image.open(ImgsManager.question_mark), size=(25, 25)
        )
        self.tutorial = tk.CTkButton(
            self, text="", image=icon, anchor=CENTER, width=10, height=30
        )
        self.tutorial.pack(side=RIGHT, padx=(0, 40), pady=(30, 0), anchor=N)
        self.tutorial.configure(command=self.show_tutorial)

        self.confirm = tk.CTkButton(
            self,
            text="Confirm",
            font=Fonts.button,
            text_color=Colors.button_text,
            height=50,
            width=120,
        )
        self.confirm.place(relx=0.7, rely=0.9, anchor=SE)
        self.confirm.configure(command=self.on_confirm)

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        print = tk.CTkButton(
            self,
            text="Calibration map",
            font=Fonts.button,
            text_color=Colors.button_text,
            image=icon,
            height=50,
            width=120,
        )
        print.place(relx=0.3, rely=0.9, anchor=SW)
        print.configure(command=self.print_calibration_map)

        self.camera = Camera(self)
        self.camera.set_on_error_listener(self.on_error)
        self.camera.set_frame_listener(self.on_frame)

        self.preview = FrameViewer(self, (500, 320))
        self.preview.place(relx=0.5, rely=0.5, anchor=CENTER)

        self.semaphore = threading.Semaphore()

    def on_focus(self) -> None:
        camera_index = self.gui.current_state.camera_index
        self.calibrator = Calibrator(get_calibration_map_dict())
        self.camera.start(camera_index)

    def on_error(self) -> None:
        self.confirm.configure(state=DISABLED)
        self.preview.show_error()

    def on_unfocus(self) -> None:
        self.camera.stop()

    def print_calibration_map(self) -> None:
        open_file(DocsManager.calibration_map)

    def on_frame(self, img: np.ndarray) -> None:
        if self.semaphore.acquire(blocking=False):
            return

        img, focal, center_x, center_y = self.calibrator.calibrate(img)
        self.data = {
            "focal_length_x": focal,
            "focal_length_y": focal,
            "camera_center_x": center_x,
            "camera_center_y": center_y,
        }

        confirm_state: Literal["disabled", "normal"]
        if focal is None or center_x is None or center_y is None:
            confirm_state = DISABLED
        else:
            confirm_state = NORMAL
        self.confirm.configure(state=confirm_state)

        self.preview.show_frame(
            cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_BGR2RGB)
        )

        self.semaphore.release()

    def show_tutorial(self) -> None:
        self.gui.show_screen(gui.ScreenName.CalibrationVideoTutorial)

    def on_confirm(self) -> None:
        self.gui.current_state.save_calibration(self.data)
        self.gui.show_screen(gui.ScreenName.ContentUsage)


def get_calibration_map_dict() -> Dict[str, Any]:
    return {
        "positioningData": {
            "arucoType": "DICT_4X4_50",
            "arucoCodes": [
                {"position": [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]], "id": 0},
                {
                    "position": [
                        [17.0, 0, 0],
                        [19.0, 0, 0],
                        [19.0, 2, 0],
                        [17.0, 2, 0],
                    ],
                    "id": 1,
                },
                {"position": [[0, 24, 0], [2, 24, 0], [2, 26, 0], [0, 26, 0]], "id": 2},
                {
                    "position": [
                        [17.0, 24, 0],
                        [19.0, 24, 0],
                        [19.0, 26, 0],
                        [17.0, 26, 0],
                    ],
                    "id": 3,
                },
            ],
        }
    }
