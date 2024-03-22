from numpy import pad
from model import State
import customtkinter as tk  # type: ignore
from tkinter import CENTER, LEFT, RIGHT, SE, SW, Y
from res import Fonts, Colors, ImgsManager, DocsManager
from controllers.screen import Screen
from PIL import Image
import gui
import os
from typing import Union


class PointerSelector(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent, show_back=True)

        title = tk.CTkLabel(self, text="Choose a pointer:", font=Fonts.title)
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        description = tk.CTkLabel(
            self,
            text="If you want to use the drop marker, print it before proceeding",
            font=Fonts.subtitle,
            justify=CENTER,
        )
        description.place(relx=0.5, rely=0.21, relwidth=0.75, anchor=CENTER)

        finger_frame = tk.CTkFrame(self, fg_color="#3B8ED0", corner_radius=6)
        finger = tk.CTkButton(
            finger_frame,
            text="Finger",
            font=Fonts.button,
            height=42,
            width=120,
        )
        finger.pack(padx=4, pady=4)
        finger.configure(command=lambda: self.on_select(State.Pointer.FINGER))
        finger_frame.place(relx=0.3, rely=0.6, anchor=SW)

        marker_frame = tk.CTkFrame(self, fg_color=Colors.button, corner_radius=6)

        marker = tk.CTkButton(
            marker_frame,
            text="Drop marker",
            font=Fonts.button,
            height=42,
            width=120,
        )
        marker.pack(side=LEFT, padx=(4, 0), pady=4)
        marker.configure(command=lambda: self.on_select(State.Pointer.MARKER))

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        print_marker = tk.CTkButton(
            marker_frame, text="", image=icon, anchor=CENTER, width=15, height=42
        )
        print_marker.configure(command=self.print_marker)
        print_marker.pack(side=LEFT, padx=4, pady=4)
        marker_frame.place(relx=0.7, rely=0.6, anchor=SE)

    def on_select(self, pointer: State.Pointer) -> None:
        self.gui.current_state.pointer = pointer
        self.gui.show_screen(gui.ScreenName.CameraSelector)

    def print_marker(self) -> None:
        os.startfile(DocsManager.marker_pointer)
