import customtkinter as tk  # type: ignore
from tkinter.constants import CENTER

import gui
from controllers.screen import Screen
from res import Fonts
from typing import Union


class HomePage(Screen):
    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent)

        title = tk.CTkLabel(self, text="CamIO", height=44)
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)
        title.configure(compound="left")
        title.configure(font=Fonts.title)

        description = tk.CTkLabel(
            self, text="CamIO is an accessibility tool for visually impaired people"
        )
        description.place(
            relx=0.5, rely=0.289, relheight=0.16, relwidth=0.6, anchor=CENTER
        )
        description.configure(font=Fonts.subtitle)
        description.configure(justify="center")

        start = tk.CTkButton(self, text="Start", height=50, width=120)
        start.place(relx=0.5, rely=0.6, anchor=CENTER)
        start.configure(font=Fonts.button)
        start.configure(command=self.show_content_selector)

    def show_content_selector(self) -> None:
        self.gui.show_screen(gui.ScreenName.ContentSelector)
