from controllers.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from typing import Union


class ContentUsage(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent, show_back=True)