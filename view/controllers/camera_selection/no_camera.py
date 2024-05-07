import customtkinter as tk  # type: ignore
from tkinter.constants import CENTER
from controllers.screen import Screen
import gui

from res import Fonts, Colors
from typing import Union


class NoCamera(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]) -> None:
        Screen.__init__(self, gui, parent, show_back=True)

        title = tk.CTkLabel(
            self, text="No camera found", height=44, font=Fonts.title, text_color=Colors.text
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        description = tk.CTkLabel(
            self,
            text="Connect one via USB",
            font=Fonts.subtitle,
            justify=CENTER,
            text_color=Colors.text,
            padx=1,
            pady=1,
        )
        description.place(
            relx=0.5, rely=0.289, relheight=0.16, relwidth=0.6, anchor=CENTER
        )

        retry = tk.CTkButton(
            self, text="Retry", height=50, width=120, font=Fonts.button, text_color=Colors.button_text
        )
        retry.place(relx=0.5, rely=0.579, anchor=CENTER)
        retry.configure(command=self.on_retry)

    def on_retry(self) -> None:
        self.gui.back()
