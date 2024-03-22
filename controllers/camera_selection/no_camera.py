import customtkinter as tk  # type: ignore
from tkinter.constants import CENTER
from controllers.screen import Screen
import gui

from res import Fonts
from typing import Union


class NoCamera(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]) -> None:
        Screen.__init__(self, gui, parent, show_back=True)

        title = tk.CTkLabel(
            self, text="No camera found", height=44, font=Fonts.title, compound="left"
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        description = tk.CTkLabel(
            self,
            text="Connect one via USB",
            font=Fonts.subtitle,
            justify=CENTER,
            padx=1,
            pady=1,
        )
        description.place(
            relx=0.5, rely=0.289, relheight=0.16, relwidth=0.6, anchor=CENTER
        )

        retry = tk.CTkButton(
            self, text="Retry", height=50, width=120, font=Fonts.button
        )
        retry.place(relx=0.5, rely=0.579, anchor=CENTER)
        retry.configure(command=self.on_retry)

    def on_retry(self) -> None:
        self.gui.show_screen(gui.ScreenName.CameraSelector)
