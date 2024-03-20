from view.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from typing import Union


class Calibration(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, parent, show_back=True)
