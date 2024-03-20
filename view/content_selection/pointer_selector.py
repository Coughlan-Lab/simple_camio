from model import State
import customtkinter as tk  # type: ignore
from tkinter import CENTER, SE, SW
from res import Fonts, ImgsManager, DocsManager
from view.screen import Screen
from PIL import Image
import gui
import os
from typing import Union


class PointerSelector(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, parent, show_back=True)

        title = tk.CTkLabel(self, text="Choose a pointer:", font=Fonts.title)
        title.place(relx=0.5, rely=0.12, relwidth=1, anchor=CENTER)

        description = tk.CTkLabel(
            self,
            text="If you want to use the drop marker, print it before proceeding",
            font=Fonts.subtitle,
            justify=CENTER,
        )
        description.place(relx=0.5, rely=0.19, relwidth=0.75, anchor=CENTER)

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        marker = tk.CTkButton(
            self,
            text="Drop marker",
            font=Fonts.button,
            image=icon,
            height=50,
            width=120,
        )
        marker.place(relx=0.7, rely=0.6, anchor=SE)
        marker.configure(command=lambda: self.on_select(State.Pointer.MARKER))

        finger = tk.CTkButton(
            self,
            text="Finger",
            font=Fonts.button,
            height=50,
            width=120,
        )
        finger.place(relx=0.3, rely=0.6, anchor=SW)
        finger.configure(command=lambda: self.on_select(State.Pointer.FINGER))

    def on_select(self, pointer: State.Pointer) -> None:
        gui.get_gui().current_state.pointer = pointer
        gui.get_gui().show_screen(gui.ScreenName.CameraSelector)

    def print_content(self) -> None:
        os.startfile(DocsManager.marker_pointer)
