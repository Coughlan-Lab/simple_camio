from numpy import pad
from model import State
import customtkinter as tk  # type: ignore
from tkinter import CENTER, LEFT, N, RIGHT, SE, SW, Y
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

        title = tk.CTkLabel(self, text="Choose pointing option:", font=Fonts.title, text_color=Colors.text)
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        description = tk.CTkLabel(
            self,
            text="If you want to use the drop marker, print it before proceeding",
            font=Fonts.subtitle,
            justify=CENTER,
            text_color=Colors.text
        )
        description.place(relx=0.5, rely=0.21, relwidth=0.75, anchor=CENTER)

        finger_frame = tk.CTkFrame(self, fg_color="#3B8ED0", corner_radius=6)
        finger = tk.CTkButton(
            finger_frame,
            text="Finger",
            font=Fonts.button,
            height=42,
            width=120,
            text_color=Colors.button_text
        )
        finger.pack(padx=4, pady=4)
        finger.configure(command=lambda: self.on_select(State.Pointer.FINGER))
        finger_frame.place(relx=0.3, rely=0.6, anchor=SW)

        marker_frame = tk.CTkFrame(self, fg_color=Colors.button, corner_radius=6)

        stylus = tk.CTkButton(
            marker_frame,
            text="Stylus",
            font=Fonts.button,
            height=42,
            width=120,
            text_color=Colors.button_text
        )
        stylus.pack(side=LEFT, padx=(4, 0), pady=4)
        stylus.configure(command=lambda: self.on_select(State.Pointer.MARKER))

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        print_marker = tk.CTkButton(
            marker_frame, text="", image=icon, anchor=CENTER, width=15, height=42
        )
        print_marker.configure(command=self.print_marker)
        print_marker.pack(side=LEFT, padx=4, pady=4)
        marker_frame.place(relx=0.7, rely=0.6, anchor=SE)

        icon = tk.CTkImage(
            light_image=Image.open(ImgsManager.question_mark), size=(25, 25)
        )
        self.tutorial = tk.CTkButton(
            self, text="", image=icon, anchor=CENTER, width=10, height=30
        )
        self.tutorial.pack(side=RIGHT, padx=(0, 40), pady=(30, 0), anchor=N)
        self.tutorial.configure(command=self.show_tutorial)

    def on_select(self, pointer: State.Pointer) -> None:
        self.gui.current_state.pointer = pointer
        self.gui.show_screen(gui.ScreenName.CameraSelector)

    def print_marker(self) -> None:
        os.startfile(DocsManager.marker_pointer)

    def show_tutorial(self) -> None:
        self.gui.show_screen(gui.ScreenName.ContentVideoTutorial)
