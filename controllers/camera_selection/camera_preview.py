import customtkinter as tk  # type: ignore
from tkinter import DISABLED

from cv2_enumerate_cameras import CameraInfo  # type: ignore
import gui

from res import Fonts
from typing import Any, Union

from ..components import Camera, FrameViewer


class CameraPreview:
    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk], camera_info: CameraInfo):
        self.camera_name = camera_info.name
        self.camera_index = camera_info.index

        self.button = tk.CTkButton(parent, text=f"{camera_info.name}", width=50)
        self.button.configure(font=Fonts.button)
        self.button.configure(command=self.on_click)

        self.camera = Camera(parent)
        self.camera.set_on_error_listener(self.show_error)
        self.preview = FrameViewer(parent, (250, 250))
        self.camera.set_frame_listener(self.preview.show_frame)

    def grid(self, row: int, column: int, **kwargs: Any) -> None:
        self.button.grid(row=row, column=column, **kwargs)
        self.preview.grid(row=row + 1, column=column, pady=5, **kwargs)

    @property
    def running(self) -> bool:
        return self.camera.running

    def focus(self) -> None:
        self.camera.start(self.camera_index)

    def show_error(self) -> None:
        self.button.configure(state=DISABLED)
        self.preview.show_error()

    def unfocus(self) -> None:
        self.camera.stop()

    def on_click(self) -> None:
        g = gui.get_gui()
        state = g.current_state
        state.camera_index = self.camera_index

        if state.pointer == state.Pointer.FINGER and state.content.is_2D():
            next_screen = gui.ScreenName.CamIO
        elif state.is_calibrated(self.camera_name):
            next_screen = gui.ScreenName.CamIO
        elif state.calibration_tutorial_watched:
            next_screen = gui.ScreenName.Calibration
        else:
            next_screen = gui.ScreenName.CalibrationVideoTutorial

        g.show_screen(next_screen)
