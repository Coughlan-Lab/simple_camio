import customtkinter as tk
from tkinter.constants import CENTER
from view.screen import Screen
import gui

from res import Fonts
from typing import Union


class NoCamera(Screen):
    @property
    def back_screen(self):
        return gui.ScreenName.HomePage

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]) -> None:
        Screen.__init__(self, parent, show_back=True)

        self.title = tk.CTkLabel(self, text="No camera found", height=44)
        self.title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)
        self.title.configure(compound="left")
        self.title.configure(font=Fonts.title)

        self.description = tk.CTkLabel(self, text="Connect one via USB")
        self.description.place(
            relx=0.5, rely=0.289, relheight=0.16, relwidth=0.6, anchor=CENTER
        )
        self.description.configure(font=Fonts.subtitle)
        self.description.configure(justify="center")
        self.description.configure(padx="1")
        self.description.configure(pady="1")

        self.retry = tk.CTkButton(self, text="Retry", height=50, width=120)
        self.retry.place(relx=0.5, rely=0.579, anchor=CENTER)
        self.retry.configure(font=Fonts.button)
        self.retry.configure(
            command=lambda: gui.get_gui().show_screen(gui.ScreenName.CameraSelector)
        )
