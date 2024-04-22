import customtkinter as tk  # type: ignore
from tkinter.constants import CENTER

import gui
from controllers.screen import Screen
from res import Fonts, Colors
from typing import Union
from model import ContentManager


class HomePage(Screen):
    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent)

        title = tk.CTkLabel(
            self, text="CamIO", height=44, text_color=Colors.text, font=Fonts.title
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        description = tk.CTkLabel(
            self,
            text="CamIO is an accessibility tool for visually impaired people",
            text_color=Colors.text,
            justify=CENTER,
            font=Fonts.subtitle,
        )
        description.place(
            relx=0.5, rely=0.289, relheight=0.16, relwidth=0.6, anchor=CENTER
        )

        start = tk.CTkButton(
            self,
            text="Start",
            font=Fonts.button,
            height=50,
            width=120,
            text_color=Colors.button_text,
        )
        start.place(relx=0.5, rely=0.6, anchor=CENTER)
        start.configure(command=self.show_content_selector)

    def show_content_selector(self) -> None:
        if not ContentManager.has_content_dir():
            next_screen = gui.ScreenName.NoContent
        else:
            next_screen = gui.ScreenName.ContentSelector
        self.gui.show_screen(next_screen)
