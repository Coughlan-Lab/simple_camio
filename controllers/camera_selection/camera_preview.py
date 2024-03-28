import customtkinter as tk  # type: ignore
from tkinter import DISABLED
import gui

from res import Fonts, Colors
from typing import Any, Union

from ..components import Camera
from view import FrameViewer
import cv2
import numpy as np
from model import State, utils


class CameraPreview:
    def __init__(
        self,
        gui: "gui.GUI",
        parent: Union[tk.CTkFrame, tk.CTk],
        camera_info: utils.CameraInfo,
    ):
        self.gui = gui
        self.camera = camera_info

        self.button = tk.CTkButton(
            parent,
            text=f"{camera_info.name}",
            font=Fonts.button,
            text_color=Colors.button_text,
            width=50,
        )
        self.button.configure(command=self.on_click)

        self.frame_producer = Camera(parent)
        self.preview = FrameViewer(parent, (250, 250))
        self.frame_producer.set_on_error_listener(self.show_error)
        self.frame_producer.set_frame_listener(self.show_frame)

    @property
    def camera_index(self) -> int:
        return self.camera.index

    @property
    def camera_name(self) -> str:
        return self.camera.name

    def grid(self, row: int, column: int, **kwargs: Any) -> None:
        self.button.grid(row=row, column=column, **kwargs)
        self.preview.grid(row=row + 1, column=column, pady=5, **kwargs)

    def grid_forget(self) -> None:
        self.button.grid_forget()
        self.preview.grid_forget()

    @property
    def running(self) -> bool:
        return self.frame_producer.running

    def start(self) -> None:
        self.frame_producer.start(self.camera_index)

    def show_error(self) -> None:
        self.button.configure(state=DISABLED)
        self.preview.show_error()

    def show_frame(self, img: np.ndarray) -> None:
        self.preview.show_frame(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    def stop(self) -> None:
        self.frame_producer.stop()

    def on_click(self) -> None:
        g = self.gui
        state = g.current_state
        state.camera = self.camera

        if state.pointer == state.Pointer.FINGER and state.content.is_2D():
            next_screen = gui.ScreenName.ContentUsage
        elif state.is_calibrated(self.camera_name):
            if utils.SYSTEM == utils.OS.MACOS:
                next_screen = gui.ScreenName.CalibrationFound
            else:
                next_screen = gui.ScreenName.ContentUsage
        elif state.calibration_tutorial_watched:
            next_screen = gui.ScreenName.Calibration
        else:
            next_screen = gui.ScreenName.CalibrationVideoTutorial
        g.show_screen(next_screen)
