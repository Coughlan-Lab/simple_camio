import customtkinter as tk  # type: ignore
from tkinter.constants import CENTER
from tkinter import filedialog
import os

import gui
from controllers.screen import Screen
from res import Fonts, Colors
from typing import Union


class NoContent(Screen):
    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent)

        title = tk.CTkLabel(
            self,
            text="CamIO Content directory not found",
            font=Fonts.title,
            text_color=Colors.text,
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        description = tk.CTkLabel(
            self,
            text="Please, select its location",
            font=Fonts.subtitle,
            justify=CENTER,
            text_color=Colors.text,
        )
        description.place(
            relx=0.5, rely=0.289, relheight=0.16, relwidth=0.6, anchor=CENTER
        )

        select = tk.CTkButton(
            self,
            text="Select",
            font=Fonts.button,
            height=50,
            width=120,
            text_color=Colors.button_text,
        )
        select.place(relx=0.5, rely=0.6, anchor=CENTER)
        select.configure(command=self.show_directory_dialog)

    def show_directory_dialog(self) -> None:
        content_dir = filedialog.askdirectory(initialdir=os.path.expanduser("~"))

        if content_dir is None or content_dir == "":
            return
        
        self.gui.current_state.set_content_dir(content_dir)

        self.gui.show_screen(gui.ScreenName.ContentSelector)
